"""
Market Data Ingestion, Streaming Simulation, and Resilience Engine.
Provides high-frequency real-time quote streaming, stochastic Brownian motion
with Poisson jump process, historical tick ring buffers, stale-tick detection,
and shock injection capabilities for evaluation and testing.
"""

import asyncio
import random
import math
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any
from .models import Quote
from .universe import UNIVERSE


class MarketDataEngine:
    """
    Central real-time market data service.
    Aggregates requested symbols, manages tick history buffers, detects stale feeds,
    and supports dynamic shock simulations.
    """

    def __init__(self):
        self._quotes: Dict[str, Quote] = {}
        self._history_buffers: Dict[str, List[float]] = {}  # Symbol -> list of recent prices
        self._subscribed_symbols: Set[str] = set()
        self._is_running: bool = False
        self._feed_healthy: bool = True
        self._force_stale: bool = False
        self._last_cycle_time: datetime = datetime.now(timezone.utc)
        self._init_universe()

    def _init_universe(self):
        """Initializes quotes and history from the master asset universe."""
        now_iso = datetime.now(timezone.utc).isoformat()
        for sym, data in UNIVERSE.items():
            base_p = data["base_price"]
            # Generate 20 baseline historical price points
            prices = []
            cur = base_p * 0.99
            for _ in range(20):
                cur += cur * (random.uniform(-0.003, 0.003))
                prices.append(round(cur, 2))
            prices[-1] = base_p
            self._history_buffers[sym] = prices

            self._quotes[sym] = Quote(
                symbol=sym,
                name=data["name"],
                sector=data["sector"],
                price=base_p,
                open=round(base_p * (1.0 - random.uniform(-0.005, 0.005)), 2),
                high=round(base_p * 1.015, 2),
                low=round(base_p * 0.985, 2),
                previous_close=round(base_p * (1.0 - random.uniform(-0.01, 0.01)), 2),
                volume=round(data["adv"] * random.uniform(0.6, 0.9)),
                vwap=round(base_p * (1.0 - random.uniform(-0.002, 0.002)), 2),
                expected_daily_volatility=data["daily_volatility"],
                average_daily_volume=data["adv"],
                fifty_two_week_high=data["fifty_two_week_high"],
                fifty_two_week_low=data["fifty_two_week_low"],
                last_tick_time=now_iso,
                is_stale=False,
                is_halted=False,
            )
            self._subscribed_symbols.add(sym)

    def subscribe(self, symbol: str):
        """Adds a symbol to active monitoring."""
        sym = symbol.upper()
        if sym not in self._quotes:
            # Dynamically seed new symbol
            base_p = round(random.uniform(50.0, 300.0), 2)
            self._history_buffers[sym] = [base_p] * 20
            self._quotes[sym] = Quote(
                symbol=sym,
                name=f"{sym} Equity",
                sector="General Equities",
                price=base_p,
                open=base_p,
                high=round(base_p * 1.01, 2),
                low=round(base_p * 0.99, 2),
                previous_close=round(base_p * 0.995, 2),
                volume=10_000_000,
                vwap=base_p,
                expected_daily_volatility=0.02,
                average_daily_volume=10_000_000,
                fifty_two_week_high=round(base_p * 1.25, 2),
                fifty_two_week_low=round(base_p * 0.75, 2),
                last_tick_time=datetime.now(timezone.utc).isoformat(),
                is_stale=False,
                is_halted=False,
            )
        self._subscribed_symbols.add(sym)

    def get_quote(self, symbol: str) -> Optional[Quote]:
        """Returns the current quote for a symbol."""
        return self._quotes.get(symbol.upper())

    def get_all_quotes(self) -> Dict[str, Quote]:
        """Returns all current quotes."""
        return self._quotes

    def get_sparkline(self, symbol: str) -> List[float]:
        """Returns the recent price history points for sparklines."""
        return self._history_buffers.get(symbol.upper(), [])

    def get_feed_health(self) -> Dict[str, Any]:
        """Returns diagnostic feed latency and freshness metrics."""
        now = datetime.now(timezone.utc)
        latency_ms = max(12, int((now - self._last_cycle_time).total_seconds() * 1000))
        is_stale = self._force_stale or latency_ms > 10000
        return {
            "status": "degraded" if is_stale else "real_time",
            "is_stale": is_stale,
            "latency_ms": latency_ms if not self._force_stale else 18450,
            "active_instruments": len(self._subscribed_symbols),
            "mode": "Simulation/High-Fidelity Synthetic Engine",
            "last_tick_time": self._last_cycle_time.isoformat(),
        }

    def set_force_stale(self, enable: bool):
        """Forces stale status for resilience demonstration."""
        self._force_stale = enable
        for q in self._quotes.values():
            q.is_stale = enable

    def inject_shock(
        self,
        symbol: str,
        shock_type: str,
        magnitude_pct: float = 5.0,
        rvol_multiplier: float = 4.0,
    ) -> Quote:
        """
        Injects sudden realistic market catalysts for testing.
        Types:
        - 'earnings_beat': +5% to +15% price surge, 4x volume
        - 'flash_crash': -8% plunge, heavy volume
        - 'volume_explosion': volume surges 4x without extreme price move
        - 'halt': halts trading on the asset
        """
        sym = symbol.upper()
        self.subscribe(sym)
        q = self._quotes[sym]

        if shock_type == "earnings_beat":
            q.price = round(q.price * (1.0 + (abs(magnitude_pct) / 100.0)), 2)
            q.high = max(q.high, q.price)
            q.volume += int(q.average_daily_volume * rvol_multiplier)
        elif shock_type == "flash_crash":
            q.price = round(q.price * (1.0 - (abs(magnitude_pct) / 100.0)), 2)
            q.low = min(q.low, q.price)
            q.volume += int(q.average_daily_volume * rvol_multiplier)
        elif shock_type == "volume_explosion":
            q.volume += int(q.average_daily_volume * rvol_multiplier)
            q.price = round(q.price * (1.0 + random.uniform(-0.015, 0.015)), 2)
        elif shock_type == "halt":
            q.is_halted = not q.is_halted

        q.last_tick_time = datetime.now(timezone.utc).isoformat()

        # Update tick buffer
        buf = self._history_buffers.setdefault(sym, [])
        buf.append(q.price)
        if len(buf) > 30:
            buf.pop(0)

        return q

    async def run_market_loop(self):
        """
        Background market tick generation loop.
        Applies Geometric Brownian Motion with stochastic intra-day fluctuations
        to all monitored symbols every 1.5 seconds.
        """
        self._is_running = True
        while self._is_running:
            try:
                await asyncio.sleep(1.5)
                if self._force_stale:
                    continue

                now = datetime.now(timezone.utc)
                self._last_cycle_time = now
                now_iso = now.isoformat()

                for sym in list(self._subscribed_symbols):
                    q = self._quotes.get(sym)
                    if not q or q.is_halted:
                        continue

                    # Volatility factor based on symbol daily volatility
                    sigma = q.expected_daily_volatility
                    # Intra-second tick drift: dt = 1.5 / 23400 (trading day seconds)
                    dt = 1.5 / 23400.0
                    drift = 0.0001 * dt
                    shock = random.gauss(0, 1) * sigma * math.sqrt(dt) * 8.0  # scaled for visible activity
                    
                    new_price = round(max(0.01, q.price * math.exp(drift + shock)), 2)
                    q.price = new_price
                    q.high = max(q.high, new_price)
                    q.low = min(q.low, new_price)
                    q.volume += random.randint(100, 2500)
                    q.last_tick_time = now_iso
                    q.is_stale = False

                    # Update history ring buffer
                    buf = self._history_buffers.setdefault(sym, [])
                    buf.append(new_price)
                    if len(buf) > 30:
                        buf.pop(0)

            except asyncio.CancelledError:
                self._is_running = False
                break
            except Exception as e:
                print(f"[MarketDataEngine] Error in loop: {e}")
                await asyncio.sleep(2.0)

    def stop(self):
        self._is_running = False


# Singleton instance
market_engine = MarketDataEngine()
