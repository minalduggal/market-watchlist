"""
REST API Endpoints for Watchlist CRUD, Session Checkpoints,
Since-Last-Seen Intelligence Briefings, and Interactive Simulation Controls.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from ..database import (
    get_or_create_session,
    update_session_activity,
    save_session_snapshots,
    get_latest_snapshot_before,
    get_user_watchlists,
    create_watchlist,
    delete_watchlist,
    add_ticker_to_watchlist,
    remove_ticker_from_watchlist,
    log_alert,
    get_alert_history,
)
from ..market_engine.ingestion import market_engine
from ..market_engine.universe import UNIVERSE
from ..market_engine.meaningful_change import evaluate_ticker_change, generate_executive_briefing
from ..market_engine.models import (
    WatchlistCreateRequest,
    WatchlistAddItemRequest,
    MarketShockRequest,
    SinceLastSeenBriefing,
)

router = APIRouter(prefix="/api")


@router.get("/health")
def get_health():
    """Returns system diagnostic health and market feed status."""
    return market_engine.get_feed_health()


@router.get("/universe")
def get_universe(q: Optional[str] = None):
    """Returns searchable universe of instruments."""
    results = []
    query = (q or "").upper().strip()
    all_quotes = market_engine.get_all_quotes()

    for sym, meta in UNIVERSE.items():
        if not query or query in sym or query in meta["name"].upper() or query in meta["sector"].upper():
            cur_quote = all_quotes.get(sym)
            cur_price = cur_quote.price if cur_quote else meta["base_price"]
            results.append({
                "symbol": sym,
                "name": meta["name"],
                "sector": meta["sector"],
                "price": cur_price,
                "daily_volatility": meta["daily_volatility"],
                "beta": meta["beta"],
            })
    return results


@router.get("/session")
def get_session(session_id: Optional[str] = None, user_name: Optional[str] = "Investor"):
    """Retrieves an existing session or initializes a new one."""
    session = get_or_create_session(session_id, user_name or "Investor")
    # If first visit, seed snapshot
    all_quotes = market_engine.get_all_quotes()
    quote_data = {sym: {"price": q.price, "volume": q.volume} for sym, q in all_quotes.items()}
    save_session_snapshots(session["session_id"], quote_data)
    return session


@router.post("/session/checkpoint")
def save_checkpoint(session_id: str = Query(...)):
    """
    Saves an instantaneous snapshot checkpoint for all tracked symbols.
    Sets the new baseline for future 'Since Last Visit' calculations.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    all_quotes = market_engine.get_all_quotes()
    quote_data = {sym: {"price": q.price, "volume": q.volume} for sym, q in all_quotes.items()}
    save_session_snapshots(session_id, quote_data, now_iso)
    update_session_activity(session_id, now_iso)
    return {
        "status": "success",
        "checkpoint_time": now_iso,
        "message": "Snapshot saved. Future comparisons will calculate deltas against this moment."
    }


@router.get("/watchlists")
def list_watchlists(session_id: str = Query(...)):
    """Returns all watchlists belonging to the session."""
    return get_user_watchlists(session_id)


@router.post("/watchlists")
def add_watchlist(session_id: str = Query(...), payload: WatchlistCreateRequest = None):
    """Creates a new watchlist."""
    if not payload or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Watchlist name is required.")
    return create_watchlist(session_id, payload.name.strip(), payload.symbols)


@router.delete("/watchlists/{watchlist_id}")
def remove_watchlist(watchlist_id: str, session_id: str = Query(...)):
    """Deletes a watchlist."""
    success = delete_watchlist(session_id, watchlist_id)
    if not success:
        raise HTTPException(status_code=404, detail="Watchlist not found or unauthorized.")
    return {"status": "deleted", "watchlist_id": watchlist_id}


@router.post("/watchlists/{watchlist_id}/items")
def add_item_to_watchlist(watchlist_id: str, payload: WatchlistAddItemRequest):
    """Adds a ticker to a specific watchlist with custom alert thresholds."""
    sym = payload.symbol.upper().strip()
    market_engine.subscribe(sym)
    success = add_ticker_to_watchlist(
        watchlist_id=watchlist_id,
        symbol=sym,
        threshold_pct=payload.alert_threshold_pct or 2.0,
        threshold_rvol=payload.alert_threshold_rvol or 2.5,
    )
    if not success:
        raise HTTPException(status_code=409, detail=f"{sym} is already in this watchlist.")
    return {"status": "added", "symbol": sym, "watchlist_id": watchlist_id}


@router.delete("/watchlists/{watchlist_id}/items/{symbol}")
def remove_item_from_watchlist(watchlist_id: str, symbol: str):
    """Removes a ticker from a watchlist."""
    sym = symbol.upper().strip()
    success = remove_ticker_from_watchlist(watchlist_id, sym)
    if not success:
        raise HTTPException(status_code=404, detail=f"{sym} not found in watchlist.")
    return {"status": "removed", "symbol": sym, "watchlist_id": watchlist_id}


@router.get("/market/since-last-seen")
def get_since_last_seen_report(
    session_id: str = Query(...),
    watchlist_id: Optional[str] = None,
    baseline_type: str = Query("last_visit"),  # 'last_visit', '15m', '1h', 'open'
) -> SinceLastSeenBriefing:
    """
    Core Intelligence Endpoint:
    Compares current quotes with the user's recorded session snapshot or historical window,
    evaluating volatility Z-Scores, RVOL, benchmark divergence, and synthesizing
    an executive natural language briefing.
    """
    session = get_or_create_session(session_id)
    all_quotes = market_engine.get_all_quotes()
    spy_quote = all_quotes.get("SPY")
    spy_day_pct = round(((spy_quote.price - spy_quote.previous_close) / spy_quote.previous_close) * 100, 2) if spy_quote else 0.0

    # Determine symbols to evaluate
    symbols_to_check = []
    custom_thresholds = {}
    if watchlist_id:
        user_wls = get_user_watchlists(session_id)
        target_wl = next((w for w in user_wls if w["id"] == watchlist_id), None)
        if target_wl:
            for itm in target_wl.get("items", []):
                sym = itm["symbol"]
                symbols_to_check.append(sym)
                custom_thresholds[sym] = {
                    "pct": itm.get("alert_threshold_pct", 2.0),
                    "rvol": itm.get("alert_threshold_rvol", 2.5),
                }

    if not symbols_to_check:
        # Default to all subscribed quotes
        symbols_to_check = list(all_quotes.keys())

    # Baseline selection
    last_visit = session.get("last_active_at", datetime.now(timezone.utc).isoformat())
    snapshots = get_latest_snapshot_before(session_id, last_visit)

    evaluated_tickers = []
    for sym in symbols_to_check:
        q = all_quotes.get(sym)
        if not q:
            continue

        c_thresh = custom_thresholds.get(sym, {"pct": 2.0, "rvol": 2.5})
        b_ts = None

        if baseline_type == "last_visit":
            if sym in snapshots:
                b_price = snapshots[sym]["price"]
                b_ts = snapshots[sym]["timestamp"]
            else:
                b_price = q.previous_close
        elif baseline_type == "open":
            b_price = q.open
        else:
            b_price = q.previous_close

        spark = market_engine.get_sparkline(sym)
        metrics = evaluate_ticker_change(
            quote=q,
            baseline_price=b_price,
            baseline_timestamp=b_ts,
            baseline_type=baseline_type,
            spy_day_change_pct=spy_day_pct,
            custom_threshold_pct=c_thresh["pct"],
            custom_threshold_rvol=c_thresh["rvol"],
            sparkline_history=spark,
        )
        evaluated_tickers.append(metrics)

        # Log alerts for critical anomalies
        for f in metrics.flags:
            if f.severity == "critical":
                log_alert(session_id, sym, f.type, f.severity, f.description)

    return generate_executive_briefing(session_id, last_visit, evaluated_tickers)


@router.get("/market/tickers/{symbol}")
def get_ticker_deep_dive(symbol: str, session_id: Optional[str] = None):
    """Returns deep-dive intelligence, technical metrics, and factor breakdown for a symbol."""
    sym = symbol.upper()
    q = market_engine.get_quote(sym)
    if not q:
        raise HTTPException(status_code=404, detail=f"Symbol {sym} not found.")

    all_quotes = market_engine.get_all_quotes()
    spy_quote = all_quotes.get("SPY")
    spy_day_pct = round(((spy_quote.price - spy_quote.previous_close) / spy_quote.previous_close) * 100, 2) if spy_quote else 0.0

    b_price = q.previous_close
    b_ts = None
    if session_id:
        session = get_or_create_session(session_id)
        snaps = get_latest_snapshot_before(session_id, session.get("last_active_at", ""))
        if sym in snaps:
            b_price = snaps[sym]["price"]
            b_ts = snaps[sym]["timestamp"]

    metrics = evaluate_ticker_change(
        quote=q,
        baseline_price=b_price,
        baseline_timestamp=b_ts,
        baseline_type="last_visit" if b_ts else "prev_close",
        spy_day_change_pct=spy_day_pct,
        sparkline_history=market_engine.get_sparkline(sym),
    )

    univ_meta = UNIVERSE.get(sym, {})
    return {
        "metrics": metrics,
        "universe_meta": univ_meta,
        "sparkline": market_engine.get_sparkline(sym),
    }


@router.post("/simulate/shock")
def trigger_market_shock(payload: MarketShockRequest, session_id: Optional[str] = None):
    """
    Market Lab testing endpoint:
    Triggers sudden volatility, volume explosions, flash crashes, or time-jumps.
    """
    sym = payload.symbol.upper()
    
    if payload.shock_type == "time_jump":
        # Fast-forward simulated time away
        jump_mins = payload.time_jump_minutes or 45
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=jump_mins)).isoformat()
        if session_id:
            update_session_activity(session_id, past_time)
            # Drift snapshot prices backwards to make current prices reflect changes over that period
            all_quotes = market_engine.get_all_quotes()
            past_snapshots = {}
            for s, q in all_quotes.items():
                drift_factor = 1.0 - (0.0008 * jump_mins)
                if s == "NVDA":
                    drift_factor = 0.94  # NVDA was 6% lower 45 mins ago
                elif s == "TSLA":
                    drift_factor = 1.05  # TSLA was 5% higher
                past_snapshots[s] = {"price": round(q.price * drift_factor, 2), "volume": q.volume * 0.4}
            save_session_snapshots(session_id, past_snapshots, past_time)

        return {
            "status": "success",
            "message": f"Time machine activated: Simulated {jump_mins} minutes away. Baseline set to {past_time}.",
            "jump_minutes": jump_mins,
        }

    if payload.shock_type == "stale_toggle":
        cur_health = market_engine.get_feed_health()
        new_stale = not cur_health["is_stale"]
        market_engine.set_force_stale(new_stale)
        return {
            "status": "success",
            "message": f"Feed status set to {'STALE (Simulating network lag)' if new_stale else 'ACTIVE (Real-Time)'}",
            "is_stale": new_stale,
        }

    # Otherwise, apply asset price or volume shock
    updated_quote = market_engine.inject_shock(
        symbol=sym,
        shock_type=payload.shock_type,
        magnitude_pct=payload.magnitude_pct or 5.0,
        rvol_multiplier=payload.rvol_multiplier or 4.0,
    )

    return {
        "status": "success",
        "message": f"Injected '{payload.shock_type}' on {sym}.",
        "new_price": updated_quote.price,
        "volume": updated_quote.volume,
    }


@router.get("/alerts")
def get_session_alerts(session_id: str = Query(...)):
    """Retrieves alert audit history for the session."""
    return get_alert_history(session_id)
