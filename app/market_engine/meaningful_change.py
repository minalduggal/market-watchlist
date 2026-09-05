"""
Meaningful Change Engine (MCE).
Calculates volatility-adjusted moves, relative volume surges, benchmark divergence,
technical milestone flags, and composite 0-100 Attention Scores.
Generates natural-language executive briefings.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import math
from .models import Quote, MeaningfulChangeMetrics, SignificanceFlag, SinceLastSeenBriefing
from .universe import UNIVERSE


def evaluate_ticker_change(
    quote: Quote,
    baseline_price: float,
    baseline_timestamp: Optional[str],
    baseline_type: str,
    spy_day_change_pct: float,
    custom_threshold_pct: float = 2.0,
    custom_threshold_rvol: float = 2.5,
    sparkline_history: Optional[List[float]] = None,
) -> MeaningfulChangeMetrics:
    """
    Evaluates a single quote against a baseline, generating statistical significance flags
    and a composite Attention Score (0-100).
    """
    # 1. Delta calculations
    day_change_abs = round(quote.price - quote.previous_close, 2)
    day_change_pct = round(((quote.price - quote.previous_close) / quote.previous_close) * 100, 2)

    delta_since_abs = round(quote.price - baseline_price, 2)
    delta_since_pct = round(((quote.price - baseline_price) / baseline_price) * 100, 2) if baseline_price > 0 else 0.0

    # 2. Volatility Normalization (Z-Score)
    # Expected daily move in % = daily_volatility * 100
    expected_pct = max(0.005, quote.expected_daily_volatility) * 100
    # Z-score of the move relative to expected standard volatility
    volatility_z_score = round(delta_since_pct / expected_pct, 2)
    abs_z = abs(volatility_z_score)

    # 3. Relative Volume (RVOL)
    # Volume relative to standard average volume
    rvol = round(quote.volume / max(1.0, quote.average_daily_volume), 2)

    # 4. Benchmark Divergence (Alpha relative to SPY and Beta)
    univ_meta = UNIVERSE.get(quote.symbol, {})
    beta = univ_meta.get("beta", 1.0)
    expected_return_vs_spy = beta * spy_day_change_pct
    divergence_pct = round(day_change_pct - expected_return_vs_spy, 2)

    flags: List[SignificanceFlag] = []

    # Flag: Volatility Anomaly
    if abs_z >= 2.5:
        flags.append(SignificanceFlag(
            type="VOLATILITY_ANOMALY",
            severity="critical",
            label=f"🚨 {abs_z:.1f}σ Anomaly",
            description=f"Move is {abs_z:.1f}x higher than expected volatility for {quote.symbol} ({expected_pct:.1f}% normal).",
            score_contribution=25.0
        ))
    elif abs_z >= 1.6:
        flags.append(SignificanceFlag(
            type="VOLATILITY_ANOMALY",
            severity="warning",
            label=f"⚡ {abs_z:.1f}σ Move",
            description=f"Elevated price swing relative to historical volatility.",
            score_contribution=14.0
        ))

    # Flag: Relative Volume (RVOL) Shock
    if rvol >= 3.5:
        flags.append(SignificanceFlag(
            type="RVOL_SPIKE",
            severity="critical",
            label=f"🔥 RVOL {rvol:.1f}x Shock",
            description=f"Trading volume is {rvol:.1f}x normal daily average — heavy institutional participation.",
            score_contribution=25.0
        ))
    elif rvol >= 2.0:
        flags.append(SignificanceFlag(
            type="RVOL_SPIKE",
            severity="warning",
            label=f"⚡ RVOL {rvol:.1f}x Surge",
            description=f"Volume is 2x+ normal baseline.",
            score_contribution=15.0
        ))

    # Flag: Benchmark Divergence (Idiosyncratic Catalyst)
    if quote.symbol != "SPY" and abs(divergence_pct) >= 2.5:
        sev = "critical" if abs(divergence_pct) >= 4.0 else "warning"
        direction = "outperforming" if divergence_pct > 0 else "decoupling lower from"
        flags.append(SignificanceFlag(
            type="BENCHMARK_DIVERGENCE",
            severity=sev,
            label=f"📉 Div {divergence_pct:+.1f}% vs SPY",
            description=f"Significantly {direction} the S&P 500 benchmark on idiosyncratic flow.",
            score_contribution=18.0
        ))

    # Flag: Key Technical Milestones (52W High/Low, VWAP)
    if quote.fifty_two_week_high > 0 and quote.price >= (quote.fifty_two_week_high * 0.985):
        flags.append(SignificanceFlag(
            type="52W_HIGH",
            severity="critical" if quote.price >= quote.fifty_two_week_high else "info",
            label="🎯 At 52W High" if quote.price >= quote.fifty_two_week_high else "🎯 Near 52W High",
            description=f"Trading at or right at 52-week peak (${quote.fifty_two_week_high:.2f}).",
            score_contribution=15.0
        ))
    elif quote.fifty_two_week_low > 0 and quote.price <= (quote.fifty_two_week_low * 1.015):
        flags.append(SignificanceFlag(
            type="52W_LOW",
            severity="critical",
            label="⚠️ Near 52W Low",
            description=f"Pressing 52-week support (${quote.fifty_two_week_low:.2f}).",
            score_contribution=15.0
        ))

    # Flag: Custom Alert Breach
    if custom_threshold_pct > 0 and abs(delta_since_pct) >= custom_threshold_pct:
        flags.append(SignificanceFlag(
            type="CUSTOM_PRICE_ALERT",
            severity="warning",
            label=f"🔔 Alert: |Δ| ≥ {custom_threshold_pct}%",
            description=f"Price moved {delta_since_pct:+.2f}%, exceeding your alert threshold of {custom_threshold_pct}%.",
            score_contribution=20.0
        ))

    if custom_threshold_rvol > 0 and rvol >= custom_threshold_rvol:
        # If not already flagged by generic RVOL
        if not any(f.type == "RVOL_SPIKE" for f in flags):
            flags.append(SignificanceFlag(
                type="CUSTOM_RVOL_ALERT",
                severity="warning",
                label=f"🔔 Alert: RVOL ≥ {custom_threshold_rvol}x",
                description=f"RVOL reached {rvol:.1f}x, exceeding custom trigger.",
                score_contribution=15.0
            ))

    # 5. Composite Attention Score (0 to 100)
    # Combines baseline delta, statistical Z-score, RVOL surge, and flag contributions
    delta_component = min(25.0, abs(delta_since_pct) * 5.0)
    z_component = min(30.0, abs_z * 10.0)
    rvol_component = min(25.0, max(0.0, (rvol - 1.0) * 8.0))
    flags_bonus = sum(min(15.0, f.score_contribution) for f in flags)

    raw_attention = delta_component + z_component + rvol_component + flags_bonus
    # Scale and clamp between 5 and 100
    attention_score = min(100.0, max(5.0, round(raw_attention, 1)))

    # Plain English Mood & Explanation Synthesis
    if quote.is_halted:
        plain_mood = "Trading Halted"
        plain_expl = "Trading is temporarily suspended by regulatory circuit breakers."
    elif rvol >= 2.5 and delta_since_pct >= 3.0:
        plain_mood = "Bullish Surge"
        plain_expl = f"Surging {delta_since_pct:+.1f}% on {rvol:.1f}x volume. Heavy buyer demand."
    elif rvol >= 2.5 and delta_since_pct <= -3.0:
        plain_mood = "Heavy Selloff"
        plain_expl = f"Plunging {delta_since_pct:+.1f}% on {rvol:.1f}x volume. Aggressive distribution."
    elif abs_z >= 2.5:
        plain_mood = "Statistical Anomaly"
        plain_expl = f"Unusually large {abs_z:.1f}σ swing (occurs in <1% of normal trading sessions)."
    elif quote.fifty_two_week_high > 0 and quote.price >= (quote.fifty_two_week_high * 0.985):
        plain_mood = "Near 52W High"
        plain_expl = f"Hovering right at its 52-week peak (${quote.fifty_two_week_high:.2f})."
    elif quote.fifty_two_week_low > 0 and quote.price <= (quote.fifty_two_week_low * 1.015):
        plain_mood = "Near 52W Low"
        plain_expl = f"Hovering near its 52-week support (${quote.fifty_two_week_low:.2f})."
    elif delta_since_pct >= 1.0:
        plain_mood = "Positive Drift"
        plain_expl = f"Modest gain of {delta_since_pct:+.2f}% on regular volume."
    elif delta_since_pct <= -1.0:
        plain_mood = "Mild Pullback"
        plain_expl = f"Down {delta_since_pct:+.2f}% within normal daily range."
    else:
        plain_mood = "Consolidating"
        plain_expl = "Flat price action with standard volume."

    return MeaningfulChangeMetrics(
        symbol=quote.symbol,
        name=quote.name,
        sector=quote.sector,
        current_price=quote.price,
        day_change_abs=day_change_abs,
        day_change_pct=day_change_pct,
        baseline_type=baseline_type,
        baseline_price=baseline_price,
        baseline_timestamp=baseline_timestamp,
        delta_since_baseline_abs=delta_since_abs,
        delta_since_baseline_pct=delta_since_pct,
        volatility_z_score=volatility_z_score,
        relative_volume=rvol,
        benchmark_divergence_pct=divergence_pct,
        attention_score=attention_score,
        flags=flags,
        sparkline=sparkline_history or [baseline_price, quote.price],
        is_stale=quote.is_stale,
        is_halted=quote.is_halted,
        plain_explanation=plain_expl,
        plain_mood=plain_mood,
    )


def generate_executive_briefing(
    session_id: str,
    last_visit_iso: str,
    evaluated_tickers: List[MeaningfulChangeMetrics],
) -> SinceLastSeenBriefing:
    """
    Synthesizes an intelligent natural-language summary explaining what has changed
    since the user's last visit in both Quant and Plain-English modes.
    """
    # Calculate elapsed time
    try:
        last_dt = datetime.fromisoformat(last_visit_iso.replace("Z", "+00:00"))
        now_dt = datetime.now(timezone.utc)
        elapsed_minutes = max(0.1, round((now_dt - last_dt).total_seconds() / 60.0, 1))
    except Exception:
        elapsed_minutes = 15.0

    total = len(evaluated_tickers)
    anomalies = [t for t in evaluated_tickers if any(f.severity == "critical" for f in t.flags)]
    warnings = [t for t in evaluated_tickers if any(f.severity == "warning" for f in t.flags)]

    # Time string formatting
    if elapsed_minutes < 60:
        time_str = f"{int(elapsed_minutes)}m ago" if elapsed_minutes >= 1 else "just now"
    elif elapsed_minutes < 1440:
        hours = elapsed_minutes / 60.0
        time_str = f"{hours:.1f}h ago"
    else:
        days = elapsed_minutes / 1440.0
        time_str = f"{days:.1f}d ago"

    # Sort tickers by attention score descending
    sorted_by_attention = sorted(evaluated_tickers, key=lambda t: t.attention_score, reverse=True)

    # Market Mood determination
    pos_count = sum(1 for t in evaluated_tickers if t.delta_since_baseline_pct > 0.5)
    neg_count = sum(1 for t in evaluated_tickers if t.delta_since_baseline_pct < -0.5)
    if pos_count > neg_count * 1.5 and pos_count >= 3:
        market_mood = "Risk-On (Bullish)"
    elif neg_count > pos_count * 1.5 and neg_count >= 3:
        market_mood = "Risk-Off (Bearish)"
    elif len(anomalies) > 0:
        market_mood = "High Volatility (Alert)"
    else:
        market_mood = "Balanced & Calm"

    # Quant Takeaways
    takeaways: List[str] = []
    plain_takeaways: List[str] = []

    if not evaluated_tickers:
        summary_headline = "Your watchlist is currently empty."
        plain_headline = "Your watchlist is currently empty."
        takeaways.append("Add symbols using the search bar above to begin tracking smart market signals.")
        plain_takeaways.append("Type a company name or ticker symbol above to start tracking.")
    elif len(anomalies) > 0:
        summary_headline = f"Significant regime changes detected in {len(anomalies)} asset{'s' if len(anomalies) > 1 else ''} since {time_str}."
        plain_headline = f"Notable moves: {len(anomalies)} stock{'s have' if len(anomalies) > 1 else ' has'} shifted meaningfully since {time_str}."

        for a in anomalies[:3]:
            crit_flag = next((f for f in a.flags if f.severity == "critical"), a.flags[0] if a.flags else None)
            flag_msg = f" ({crit_flag.label})" if crit_flag else ""
            takeaways.append(
                f"**{a.symbol}** ({a.name}): Moved {a.delta_since_baseline_pct:+.2f}% since last visit{flag_msg} with Attention Score of {a.attention_score}."
            )
            plain_takeaways.append(
                f"**{a.symbol}** ({a.plain_mood}): {a.plain_explanation}"
            )
        
        # Sector / macro context
        divergences = [t for t in evaluated_tickers if any(f.type == "BENCHMARK_DIVERGENCE" for f in t.flags)]
        if divergences:
            top_div = divergences[0]
            takeaways.append(
                f"**{top_div.symbol}** is decoupling from the broad market (SPY divergence of {top_div.benchmark_divergence_pct:+.1f}%)."
            )
    elif len(warnings) > 0:
        summary_headline = f"Moderate volume or volatility shifts observed in {len(warnings)} ticker{'s' if len(warnings) > 1 else ''} since {time_str}."
        plain_headline = f"The market is moving steadily with {len(warnings)} active stock{'s' if len(warnings) > 1 else ''} since {time_str}."
        for w in warnings[:2]:
            w_flag = w.flags[0] if w.flags else None
            flag_msg = f" [{w_flag.label}]" if w_flag else ""
            takeaways.append(f"**{w.symbol}** shifted {w.delta_since_baseline_pct:+.2f}%{flag_msg}.")
            plain_takeaways.append(f"**{w.symbol}**: {w.plain_explanation}")
    else:
        summary_headline = f"Market conditions have remained calm since your last visit ({time_str})."
        plain_headline = f"Everything is steady. No sharp moves since your last visit ({time_str})."
        if sorted_by_attention:
            leader = sorted_by_attention[0]
            takeaways.append(f"Highest mover is **{leader.symbol}** ({leader.delta_since_baseline_pct:+.2f}% since last checkpoint).")
            plain_takeaways.append(f"Top mover is **{leader.symbol}** ({leader.delta_since_baseline_pct:+.2f}%). Normal daily fluctuation.")

    return SinceLastSeenBriefing(
        session_id=session_id,
        last_visit_time=last_visit_iso,
        elapsed_minutes=elapsed_minutes,
        total_tracked=total,
        anomalies_detected=len(anomalies),
        summary_headline=summary_headline,
        key_takeaways=takeaways,
        plain_headline=plain_headline,
        plain_takeaways=plain_takeaways,
        market_mood=market_mood,
        tickers=sorted_by_attention,
    )
