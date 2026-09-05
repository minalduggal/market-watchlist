"""
Integration tests for FastAPI REST API endpoints,
SQLite persistence, watchlist CRUD, and simulation shocks.
"""

import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db


class TestMarketWatchlistAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def test_health_check(self):
        """Test health diagnostic endpoint."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("latency_ms", data)
        self.assertIn("active_instruments", data)

    def test_universe_search(self):
        """Test asset universe search and filtering."""
        response = self.client.get("/api/universe?q=NVDA")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertGreater(len(items), 0)
        self.assertEqual(items[0]["symbol"], "NVDA")

    def test_session_and_watchlists_lifecycle(self):
        """Test user session creation and default watchlists."""
        session_id = "test-evaluator-session-001"
        res_session = self.client.get(f"/api/session?session_id={session_id}")
        self.assertEqual(res_session.status_code, 200)
        s_data = res_session.json()
        self.assertEqual(s_data["session_id"], session_id)

        # Fetch watchlists
        res_wl = self.client.get(f"/api/watchlists?session_id={session_id}")
        self.assertEqual(res_wl.status_code, 200)
        wls = res_wl.json()
        self.assertGreater(len(wls), 0)
        first_wl_id = wls[0]["id"]

        # Create new watchlist
        res_create = self.client.post(f"/api/watchlists?session_id={session_id}", json={"name": "Energy & Defensives"})
        self.assertEqual(res_create.status_code, 200)
        new_wl_id = res_create.json()["id"]

        # Add item to new watchlist
        res_add = self.client.post(f"/api/watchlists/{new_wl_id}/items", json={"symbol": "XLE"})
        self.assertEqual(res_add.status_code, 200)

        # Remove item
        res_rem = self.client.delete(f"/api/watchlists/{new_wl_id}/items/XLE")
        self.assertEqual(res_rem.status_code, 200)

        # Delete watchlist
        res_del = self.client.delete(f"/api/watchlists/{new_wl_id}?session_id={session_id}")
        self.assertEqual(res_del.status_code, 200)

    def test_since_last_seen_report(self):
        """Test since-last-seen briefing calculation."""
        session_id = "test-evaluator-session-001"
        res = self.client.get(f"/api/market/since-last-seen?session_id={session_id}&baseline_type=last_visit")
        self.assertEqual(res.status_code, 200)
        report = res.json()
        self.assertIn("summary_headline", report)
        self.assertIn("key_takeaways", report)
        self.assertIn("tickers", report)
        self.assertGreater(len(report["tickers"]), 0)

    def test_checkpoint_baseline(self):
        """Test recording an instantaneous snapshot checkpoint."""
        session_id = "test-evaluator-session-001"
        res = self.client.post(f"/api/session/checkpoint?session_id={session_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")

    def test_market_shock_simulation(self):
        """Test injecting realistic synthetic shocks for testing."""
        session_id = "test-evaluator-session-001"
        res = self.client.post(
            f"/api/simulate/shock?session_id={session_id}",
            json={"symbol": "NVDA", "shock_type": "earnings_beat", "magnitude_pct": 8.0, "rvol_multiplier": 4.0}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")

        # Verify time jump
        res_jump = self.client.post(
            f"/api/simulate/shock?session_id={session_id}",
            json={"symbol": "NVDA", "shock_type": "time_jump", "time_jump_minutes": 45}
        )
        self.assertEqual(res_jump.status_code, 200)


if __name__ == "__main__":
    unittest.main()
