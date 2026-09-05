"""
WebSocket Broadcaster and Pub/Sub Hub.
Maintains active client connections, streams live ticker deltas,
and manages client-specific watchlist filters with heartbeat pings.
"""

import asyncio
import json
from typing import Dict, Set, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect
from .ingestion import market_engine
from .meaningful_change import evaluate_ticker_change
from ..database import get_latest_snapshot_before, get_or_create_session, log_alert


class ConnectionManager:
    """Manages active WebSockets and dispatches differential market updates."""

    def __init__(self):
        self._active_connections: Dict[WebSocket, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, session_id: str, watchlist_id: Optional[str] = None):
        """Registers a newly connected WebSocket client."""
        await websocket.accept()
        async with self._lock:
            self._active_connections[websocket] = {
                "session_id": session_id,
                "watchlist_id": watchlist_id,
                "symbols": set(),
                "baseline_type": "last_visit",
            }

    async def disconnect(self, websocket: WebSocket):
        """Unregisters a disconnected client."""
        async with self._lock:
            if websocket in self._active_connections:
                del self._active_connections[websocket]

    async def update_client_filter(
        self,
        websocket: WebSocket,
        watchlist_id: Optional[str] = None,
        symbols: Optional[Set[str]] = None,
        baseline_type: Optional[str] = None,
    ):
        """Updates subscription filters for a connected client."""
        async with self._lock:
            if websocket in self._active_connections:
                if watchlist_id is not None:
                    self._active_connections[websocket]["watchlist_id"] = watchlist_id
                if symbols is not None:
                    self._active_connections[websocket]["symbols"] = symbols
                if baseline_type is not None:
                    self._active_connections[websocket]["baseline_type"] = baseline_type

    async def broadcast_tick_cycle(self):
        """
        Periodically pushes differential updates to all connected clients.
        Computes meaningful change relative to each client's baseline.
        """
        if not self._active_connections:
            return

        all_quotes = market_engine.get_all_quotes()
        spy_quote = all_quotes.get("SPY")
        spy_day_pct = round(((spy_quote.price - spy_quote.previous_close) / spy_quote.previous_close) * 100, 2) if spy_quote else 0.0

        async with self._lock:
            clients = list(self._active_connections.items())

        for ws, client_data in clients:
            try:
                session_id = client_data["session_id"]
                sub_symbols = client_data.get("symbols", set())
                baseline_type = client_data.get("baseline_type", "last_visit")

                # If no specific symbols filtered, track all available
                symbols_to_send = sub_symbols if sub_symbols else set(all_quotes.keys())

                # Fetch session baseline snapshots
                session_meta = get_or_create_session(session_id)
                last_visit = session_meta.get("last_active_at")
                snapshots = get_latest_snapshot_before(session_id, last_visit)

                updates = []
                for sym in symbols_to_send:
                    q = all_quotes.get(sym)
                    if not q:
                        continue

                    # Determine baseline price
                    if baseline_type == "last_visit" and sym in snapshots:
                        b_price = snapshots[sym]["price"]
                        b_ts = snapshots[sym]["timestamp"]
                    elif baseline_type == "open":
                        b_price = q.open
                        b_ts = None
                    else:
                        b_price = q.previous_close
                        b_ts = None

                    spark = market_engine.get_sparkline(sym)
                    eval_metrics = evaluate_ticker_change(
                        quote=q,
                        baseline_price=b_price,
                        baseline_timestamp=b_ts,
                        baseline_type=baseline_type,
                        spy_day_change_pct=spy_day_pct,
                        sparkline_history=spark,
                    )
                    updates.append(eval_metrics.model_dump())

                # Sort updates by attention score
                updates.sort(key=lambda x: x["attention_score"], reverse=True)

                payload = {
                    "type": "market_tick",
                    "health": market_engine.get_feed_health(),
                    "tickers": updates,
                }
                await ws.send_text(json.dumps(payload))

            except (WebSocketDisconnect, ConnectionResetError):
                await self.disconnect(ws)
            except Exception as e:
                # Silently handle individual socket send failures
                pass


# Global singleton
broadcaster = ConnectionManager()


async def run_broadcaster_loop():
    """Background task streaming deltas to WebSockets every 1.5 seconds."""
    while True:
        try:
            await asyncio.sleep(1.5)
            await broadcaster.broadcast_tick_cycle()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Broadcaster] Loop error: {e}")
            await asyncio.sleep(2.0)
