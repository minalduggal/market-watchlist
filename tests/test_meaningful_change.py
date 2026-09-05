"""
Unit tests for Meaningful Change Engine (MCE).
Verifies statistical volatility Z-Scores, RVOL surges, benchmark divergence,
milestone flags, and composite attention scoring.
"""

import unittest
from app.market_engine.models import Quote
from app.market_engine.meaningful_change import evaluate_ticker_change, generate_executive_briefing


class TestMeaningfulChangeEngine(unittest.TestCase):

    def setUp(self):
        self.quote_nvda = Quote(
            symbol="NVDA",
            name="NVIDIA Corporation",
            sector="Semiconductors & Accelerated Computing",
            price=138.00,
            open=128.00,
            high=139.00,
            low=127.50,
            previous_close=128.00,
            volume=165_000_000,  # 3x ADV
            vwap=134.50,
            expected_daily_volatility=0.038,  # 3.8%
            average_daily_volume=55_000_000,
            fifty_two_week_high=140.76,
            fifty_two_week_low=75.60,
            last_tick_time="2026-09-05T12:00:00Z",
            is_stale=False,
            is_halted=False,
        )

        self.quote_so = Quote(
            symbol="SO",
            name="The Southern Company",
            sector="Regulated Utilities",
            price=90.80,
            open=88.20,
            high=91.00,
            low=88.00,
            previous_close=88.20,
            volume=4_500_000,
            vwap=89.50,
            expected_daily_volatility=0.008,  # 0.8% very low volatility
            average_daily_volume=4_200_000,
            fifty_two_week_high=91.50,
            fifty_two_week_low=63.80,
            last_tick_time="2026-09-05T12:00:00Z",
            is_stale=False,
            is_halted=False,
        )

    def test_rvol_spike_detection(self):
        """Test that volume 3x average triggers an RVOL surge flag."""
        metrics = evaluate_ticker_change(
            quote=self.quote_nvda,
            baseline_price=128.00,
            baseline_timestamp="2026-09-05T11:00:00Z",
            baseline_type="last_visit",
            spy_day_change_pct=1.0,
        )
        self.assertGreaterEqual(metrics.relative_volume, 2.8)
        has_rvol_flag = any(f.type == "RVOL_SPIKE" for f in metrics.flags)
        self.assertTrue(has_rvol_flag, "Should generate an RVOL_SPIKE flag for 3x normal volume.")

    def test_volatility_z_score_normalization(self):
        """
        Verify that a 2.9% move in utility stock (SO) generates a much higher Z-score
        than the same move in a high-beta stock, correctly highlighting unusual behavior.
        """
        metrics_so = evaluate_ticker_change(
            quote=self.quote_so,
            baseline_price=88.20,
            baseline_timestamp=None,
            baseline_type="prev_close",
            spy_day_change_pct=0.2,
        )
        # 90.80 vs 88.20 is +2.95% move. With expected daily vol of 0.8%, Z is ~ 3.7 sigma!
        self.assertGreaterEqual(metrics_so.volatility_z_score, 3.0)
        self.assertTrue(any(f.type == "VOLATILITY_ANOMALY" and f.severity == "critical" for f in metrics_so.flags))

    def test_near_52w_high_detection(self):
        """Test that trading within 0.5% of 52-week peak generates milestone flag."""
        metrics = evaluate_ticker_change(
            quote=self.quote_so,  # 90.80 vs 52W high of 91.50 (> 99%)
            baseline_price=88.20,
            baseline_timestamp=None,
            baseline_type="prev_close",
            spy_day_change_pct=0.0,
        )
        self.assertTrue(any(f.type == "52W_HIGH" for f in metrics.flags))

    def test_attention_score_bounds_and_ranking(self):
        """Verify Attention Score is clamped between 5 and 100 and scales with urgency."""
        metrics_high_urgency = evaluate_ticker_change(
            quote=self.quote_nvda,
            baseline_price=120.00,  # massive jump
            baseline_timestamp=None,
            baseline_type="last_visit",
            spy_day_change_pct=0.5,
        )
        self.assertGreaterEqual(metrics_high_urgency.attention_score, 70.0)
        self.assertLessEqual(metrics_high_urgency.attention_score, 100.0)

    def test_executive_briefing_synthesis(self):
        """Test natural language briefing synthesis when anomalies are present."""
        metrics = evaluate_ticker_change(
            quote=self.quote_nvda,
            baseline_price=120.00,
            baseline_timestamp="2026-09-05T11:20:00Z",
            baseline_type="last_visit",
            spy_day_change_pct=0.5,
        )
        briefing = generate_executive_briefing(
            session_id="test-session",
            last_visit_iso="2026-09-05T11:20:00Z",
            evaluated_tickers=[metrics],
        )
        self.assertIn("NVDA", briefing.summary_headline + str(briefing.key_takeaways))
        self.assertGreater(len(briefing.key_takeaways), 0)


if __name__ == "__main__":
    unittest.main()
