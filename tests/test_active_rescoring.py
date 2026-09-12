import unittest
import os
import sys
import tempfile
import json

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(ROOT_DIR, "engine")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

from indicators import compute_active_health_tier
from stocks import audit_stock_positions, update_stock_trades_log

class TestActiveRescoring(unittest.TestCase):

    def test_compute_active_health_tier_house_money(self):
        # When TP1 is hit or stop >= entry, must be TIER_A_HOUSE_MONEY and eviction_eligible=False
        res = compute_active_health_tier(
            status="TP1_HIT",
            stop_price=105.0,
            entry_price=100.0,
            current_alpha_score=35.0, # even if score dips, house money cannot be evicted!
            days_active=12,
            strategy_prong="BALANCED",
            prev_consecutive_low=4
        )
        self.assertEqual(res["tier"], "TIER_A_HOUSE_MONEY")
        self.assertIn("HOUSE MONEY", res["badge"])
        self.assertFalse(res["eviction_eligible"])
        self.assertEqual(res["consecutive_low_score_days"], 0)

    def test_compute_active_health_tier_on_track(self):
        # Healthy position
        res = compute_active_health_tier(
            status="OPEN",
            stop_price=95.0,
            entry_price=100.0,
            current_alpha_score=82.0,
            days_active=3,
            strategy_prong="BALANCED",
            prev_consecutive_low=0
        )
        self.assertEqual(res["tier"], "TIER_B_ON_TRACK")
        self.assertIn("ON-TRACK", res["badge"])
        self.assertFalse(res["eviction_eligible"])
        self.assertEqual(res["consecutive_low_score_days"], 0)

    def test_compute_active_health_tier_stagnant(self):
        # Score in 40-59 range or prolonged holding
        res = compute_active_health_tier(
            status="OPEN",
            stop_price=95.0,
            entry_price=100.0,
            current_alpha_score=52.0,
            days_active=8,
            strategy_prong="HIGH_RISK",
            prev_consecutive_low=0
        )
        self.assertEqual(res["tier"], "TIER_C_STAGNANT")
        self.assertIn("STAGNANT", res["badge"])
        self.assertFalse(res["eviction_eligible"])

    def test_compute_active_health_tier_eviction_candidate(self):
        # 3 consecutive days of low score (<40) and days_active >= 5
        res = compute_active_health_tier(
            status="OPEN",
            stop_price=95.0,
            entry_price=100.0,
            current_alpha_score=32.0,
            days_active=6,
            strategy_prong="BALANCED",
            prev_consecutive_low=2
        )
        self.assertEqual(res["tier"], "TIER_D_EVICTION_CANDIDATE")
        self.assertIn("EVICTION CANDIDATE", res["badge"])
        self.assertTrue(res["eviction_eligible"])
        self.assertEqual(res["consecutive_low_score_days"], 3)

    def test_audit_stock_positions_telemetry_population(self):
        stock_trades = [
            {
                "id": "TEST_001",
                "ticker": "AAPL",
                "status": "OPEN",
                "strategy_prong": "BALANCED",
                "entry_price": 200.0,
                "stop_price": 190.0,
                "tp1": 215.0,
                "tp2": 230.0,
                "days_active": 2,
                "capital_deployed": 5000.0,
                "shares": 25,
                "consecutive_low_score_days": 0
            }
        ]
        market_bars = {
            "AAPL": {
                "Open": 202.0,
                "High": 204.0,
                "Low": 201.0,
                "Close": 203.0,
                "EMA50": 198.0,
                "rsi": 58.0,
                "macd_hist": 0.35,
                "macd_crawling_up": True,
                "rvol": 1.4,
                "beta": 1.1,
                "adr_pct": 2.2,
                "market_structure": "BULLISH_HH_HL",
                "reclaim_days": 1
            }
        }
        audited = audit_stock_positions(stock_trades, market_bars, "2026-09-12")
        t = audited[0]
        self.assertIn("current_alpha_score", t)
        self.assertGreater(t["current_alpha_score"], 60.0)
        self.assertIn("score_breakdown", t)
        self.assertEqual(t["active_health_tier"], "TIER_B_ON_TRACK")
        self.assertFalse(t["eviction_eligible"])

    def test_isolated_stock_log_update_does_not_mutate_production(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = os.path.join(tmpdir, "stock_trades_log.json")
            new_recs = [
                {
                    "ticker": "MSFT",
                    "price": 420.0,
                    "stop": 405.0,
                    "tp1": 445.0,
                    "tp2": 470.0,
                    "rr_ratio": 2.5,
                    "sector": "TECHNOLOGY",
                    "alpha_score": 85.0,
                    "score_breakdown": {"total": 85.0}
                }
            ]
            bars = {
                "MSFT": {
                    "Open": 420.0, "High": 422.0, "Low": 418.0, "Close": 421.0, "EMA50": 415.0
                }
            }
            res = update_stock_trades_log(new_recs, bars, "2026-09-12", log_path=tmp_log)
            self.assertTrue(os.path.exists(tmp_log))
            trades = res.get("trades", [])
            self.assertEqual(len(trades), 1)
            t = trades[0]
            self.assertEqual(t["ticker"], "MSFT")
            self.assertEqual(t["current_alpha_score"], 85.0)
            self.assertEqual(t["active_health_tier"], "TIER_B_ON_TRACK")
            self.assertFalse(t["eviction_eligible"])

if __name__ == "__main__":
    unittest.main()
