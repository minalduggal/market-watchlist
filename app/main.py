"""
Main FastAPI Application Entry Point.
Configures lifespan tasks for market tick generation, WebSocket delta broadcasting,
CORS, database initialization, and static file serving.
"""

import asyncio
import os
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .database import init_db, get_or_create_session
from .market_engine.ingestion import market_engine
from .market_engine.broadcaster import broadcaster, run_broadcaster_loop
from .api.routes import router as api_router

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes database and boots asynchronous market & broadcast tasks."""
    # 1. Initialize SQLite Database
    init_db()
    print("[Server] Database initialized.")

    # 2. Seed initial session
    get_or_create_session("default-user-session", "Institutional Trader")

    # 3. Launch background async loops
    market_task = asyncio.create_task(market_engine.run_market_loop())
    broadcast_task = asyncio.create_task(run_broadcaster_loop())
    print("[Server] Market Data Engine and WebSocket Broadcaster started.")

    yield

    # Cleanup on shutdown
    market_engine.stop()
    market_task.cancel()
    broadcast_task.cancel()
    print("[Server] Gracefully stopped background engine tasks.")


app = FastAPI(
    title="NEXUS Market Intelligence Terminal",
    description="Quantitative market watchlist identifying statistical regime shifts and temporal deltas.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include REST routes
app.include_router(api_router)


# WebSocket Endpoint for real-time differential streaming
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    session_id = websocket.query_params.get("session_id", "default-user-session")
    watchlist_id = websocket.query_params.get("watchlist_id")
    await broadcaster.connect(websocket, session_id, watchlist_id)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            action = message.get("action")

            if action == "subscribe_watchlist":
                symbols = set(message.get("symbols", []))
                wl_id = message.get("watchlist_id")
                await broadcaster.update_client_filter(websocket, watchlist_id=wl_id, symbols=symbols)
            elif action == "change_baseline":
                base_type = message.get("baseline_type", "last_visit")
                await broadcaster.update_client_filter(websocket, baseline_type=base_type)
            elif action == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
    except Exception as e:
        await broadcaster.disconnect(websocket)


# Mount static assets
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    """Serves the primary Single Page Application interface."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Smart Market Watchlist API is live. Static interface initializing..."}
