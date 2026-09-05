"""
Pydantic data models for quotes, meaningful change signals, attention scores,
and API request/response structures.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime


class SignificanceFlag(BaseModel):
    """Represents a specific meaningful anomaly or signal."""
    type: str  # e.g., 'RVOL_SPIKE', 'VOLATILITY_ANOMALY', '52W_HIGH', 'BENCHMARK_DIVERGENCE'
    severity: str  # 'info', 'warning', 'critical'
    label: str  # Short tag: '⚡ RVOL 3.2x', '🚨 2.8σ Anomaly'
    description: str  # Plain English explanation
    score_contribution: float = 0.0


class Quote(BaseModel):
    """Real-time market quote with institutional context metrics."""
    symbol: str
    name: str
    sector: str
    price: float
    open: float
    high: float
    low: float
    previous_close: float
    volume: float
    vwap: float
    expected_daily_volatility: float  # e.g. 0.02 for 2%
    average_daily_volume: float
    fifty_two_week_high: float
    fifty_two_week_low: float
    last_tick_time: str
    is_stale: bool = False
    is_halted: bool = False


class MeaningfulChangeMetrics(BaseModel):
    """Evaluated change metrics comparing current quote to a specified baseline."""
    symbol: str
    name: str
    sector: str
    current_price: float
    day_change_abs: float
    day_change_pct: float
    baseline_type: str  # 'last_visit', '15m', '1h', 'open'
    baseline_price: float
    baseline_timestamp: Optional[str] = None
    delta_since_baseline_abs: float
    delta_since_baseline_pct: float
    volatility_z_score: float
    relative_volume: float  # RVOL: e.g. 2.4 means 240% normal
    benchmark_divergence_pct: float  # Out/under-performance vs SPY
    attention_score: float  # 0 to 100 urgency score
    flags: List[SignificanceFlag] = []
    sparkline: List[float] = []
    is_stale: bool = False
    is_halted: bool = False
    plain_explanation: str = ""
    plain_mood: str = "Neutral"


class SinceLastSeenBriefing(BaseModel):
    """Executive narrative digest summarizing what meaningfully shifted while user was away."""
    session_id: str
    last_visit_time: str
    elapsed_minutes: float
    total_tracked: int
    anomalies_detected: int
    summary_headline: str
    key_takeaways: List[str]
    plain_headline: str = ""
    plain_takeaways: List[str] = []
    market_mood: str = "Neutral"
    tickers: List[MeaningfulChangeMetrics]


class WatchlistCreateRequest(BaseModel):
    name: str
    symbols: Optional[List[str]] = []


class WatchlistAddItemRequest(BaseModel):
    symbol: str
    alert_threshold_pct: Optional[float] = 2.0
    alert_threshold_rvol: Optional[float] = 2.5


class MarketShockRequest(BaseModel):
    """Allows triggering realistic synthetic shocks for testing & demonstration."""
    symbol: str
    shock_type: str  # 'earnings_beat', 'flash_crash', 'volume_explosion', 'time_jump', 'feed_delay'
    magnitude_pct: Optional[float] = 5.0
    rvol_multiplier: Optional[float] = 4.0
    time_jump_minutes: Optional[int] = 60
