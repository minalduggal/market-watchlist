"""
Database layer for Smart Market Watchlist.
Utilizes SQLite with Write-Ahead Logging (WAL) for concurrent read/write performance,
foreign key constraints, and automatic schema initialization.
"""

import sqlite3
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.db")


@contextmanager
def get_db_connection():
    """Creates a thread-safe connection to SQLite with WAL mode, ensuring clean closure."""
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    """Initializes the database schema and seeds default watchlists."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # User / Session table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_name TEXT NOT NULL DEFAULT 'Investor',
                last_active_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP NOT NULL,
                baseline_preference TEXT NOT NULL DEFAULT 'last_visit'
            );
        """)

        # Watchlists table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlists (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                name TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
            );
        """)

        # Watchlist items
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_items (
                id TEXT PRIMARY KEY,
                watchlist_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                added_at TIMESTAMP NOT NULL,
                alert_threshold_pct REAL DEFAULT 2.0,
                alert_threshold_rvol REAL DEFAULT 2.5,
                UNIQUE(watchlist_id, symbol),
                FOREIGN KEY (watchlist_id) REFERENCES watchlists (id) ON DELETE CASCADE
            );
        """)

        # Session snapshots for "Since Last Seen" baseline comparison
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                volume REAL NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_session_sym ON session_snapshots(session_id, symbol);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_time ON session_snapshots(timestamp);")

        # Alert history log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                flag_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                is_read INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
            );
        """)

        conn.commit()


def get_or_create_session(session_id: Optional[str] = None, user_name: str = "Investor") -> Dict[str, Any]:
    """Retrieves an existing session or creates a new one with seed watchlists."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if session_id:
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        
        # Create new session
        new_id = session_id or str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO sessions (session_id, user_name, last_active_at, created_at, baseline_preference)
            VALUES (?, ?, ?, ?, 'last_visit')
        """, (new_id, user_name, now, now))

        # Create default watchlists for the new session
        default_lists = [
            ("Core Portfolio", [("NVDA", 2.0, 2.5), ("AAPL", 1.5, 2.0), ("MSFT", 1.5, 2.0), ("GOOGL", 2.0, 2.0), ("AMZN", 2.0, 2.0), ("TSLA", 3.0, 3.0), ("SPY", 1.0, 1.5)], True),
            ("High Beta & Crypto", [("BTC-USD", 3.5, 2.5), ("ETH-USD", 4.0, 2.5), ("TSLA", 3.0, 2.5), ("NVDA", 2.5, 2.5)], False),
            ("Macro & Defensive", [("SPY", 1.0, 1.5), ("QQQ", 1.2, 1.8), ("XLE", 1.8, 2.0), ("JNJ", 1.0, 1.5), ("SO", 1.0, 1.5)], False)
        ]

        for wl_name, items, is_def in default_lists:
            wl_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO watchlists (id, session_id, name, is_default, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (wl_id, new_id, wl_name, 1 if is_def else 0, now))

            for sym, alert_pct, alert_rvol in items:
                item_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO watchlist_items (id, watchlist_id, symbol, added_at, alert_threshold_pct, alert_threshold_rvol)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (item_id, wl_id, sym, now, alert_pct, alert_rvol))

        conn.commit()
        return {
            "session_id": new_id,
            "user_name": user_name,
            "last_active_at": now,
            "created_at": now,
            "baseline_preference": "last_visit"
        }


def update_session_activity(session_id: str, timestamp: Optional[str] = None):
    """Updates the last_active_at timestamp for a session."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        conn.execute("UPDATE sessions SET last_active_at = ? WHERE session_id = ?", (ts, session_id))
        conn.commit()


def save_session_snapshots(session_id: str, symbol_prices: Dict[str, Dict[str, float]], timestamp: Optional[str] = None):
    """
    Saves price snapshots for a session's tickers.
    symbol_prices is {symbol: {"price": float, "volume": float}}
    """
    get_or_create_session(session_id)
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for sym, data in symbol_prices.items():
            cursor.execute("""
                INSERT INTO session_snapshots (session_id, symbol, price, volume, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, sym.upper(), data.get("price", 0.0), data.get("volume", 0.0), ts))
        conn.commit()


def get_latest_snapshot_before(session_id: str, before_timestamp: str) -> Dict[str, Dict[str, Any]]:
    """
    Retrieves the most recent snapshot for each symbol prior to a specific timestamp.
    Used for 'Since Last Visit' or time-window comparisons.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s1.symbol, s1.price, s1.volume, s1.timestamp
            FROM session_snapshots s1
            INNER JOIN (
                SELECT symbol, MAX(timestamp) as max_ts
                FROM session_snapshots
                WHERE session_id = ? AND timestamp <= ?
                GROUP BY symbol
            ) s2 ON s1.symbol = s2.symbol AND s1.timestamp = s2.max_ts
            WHERE s1.session_id = ?
        """, (session_id, before_timestamp, session_id))
        
        results = {}
        for row in cursor.fetchall():
            results[row["symbol"]] = {
                "price": row["price"],
                "volume": row["volume"],
                "timestamp": row["timestamp"]
            }
        return results


def get_user_watchlists(session_id: str) -> List[Dict[str, Any]]:
    """Fetches all watchlists for a session including item count and symbols."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM watchlists WHERE session_id = ? ORDER BY is_default DESC, created_at ASC", (session_id,))
        watchlists = []
        for wl in cursor.fetchall():
            wl_dict = dict(wl)
            cursor.execute("SELECT * FROM watchlist_items WHERE watchlist_id = ? ORDER BY added_at ASC", (wl["id"],))
            items = [dict(item) for item in cursor.fetchall()]
            wl_dict["items"] = items
            wl_dict["symbols"] = [item["symbol"] for item in items]
            watchlists.append(wl_dict)
        return watchlists


def create_watchlist(session_id: str, name: str, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
    """Creates a new watchlist."""
    now = datetime.now(timezone.utc).isoformat()
    wl_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO watchlists (id, session_id, name, is_default, created_at)
            VALUES (?, ?, ?, 0, ?)
        """, (wl_id, session_id, name, now))
        
        if symbols:
            for sym in symbols:
                item_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO watchlist_items (id, watchlist_id, symbol, added_at)
                    VALUES (?, ?, ?, ?)
                """, (item_id, wl_id, sym.upper(), now))
        conn.commit()
    
    return {"id": wl_id, "session_id": session_id, "name": name, "symbols": symbols or []}


def delete_watchlist(session_id: str, watchlist_id: str) -> bool:
    """Deletes a watchlist belonging to a session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlists WHERE id = ? AND session_id = ?", (watchlist_id, session_id))
        conn.commit()
        return cursor.rowcount > 0


def add_ticker_to_watchlist(watchlist_id: str, symbol: str, threshold_pct: float = 2.0, threshold_rvol: float = 2.5) -> bool:
    """Adds a ticker to a watchlist if not already present."""
    now = datetime.now(timezone.utc).isoformat()
    item_id = str(uuid.uuid4())
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO watchlist_items (id, watchlist_id, symbol, added_at, alert_threshold_pct, alert_threshold_rvol)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (item_id, watchlist_id, symbol.upper(), now, threshold_pct, threshold_rvol))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def remove_ticker_from_watchlist(watchlist_id: str, symbol: str) -> bool:
    """Removes a ticker from a watchlist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist_items WHERE watchlist_id = ? AND symbol = ?", (watchlist_id, symbol.upper()))
        conn.commit()
        return cursor.rowcount > 0


def log_alert(session_id: str, symbol: str, flag_type: str, severity: str, message: str):
    """Records an anomaly or alert in the history log."""
    get_or_create_session(session_id)
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alert_history (session_id, symbol, flag_type, severity, message, created_at, is_read)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (session_id, symbol.upper(), flag_type, severity, message, now))
        conn.commit()


def get_alert_history(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves recent alerts for a session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM alert_history WHERE session_id = ? ORDER BY created_at DESC LIMIT ?
        """, (session_id, limit))
        return [dict(row) for row in cursor.fetchall()]
