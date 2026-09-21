"""
Unit tests for Feature 4: "Almost Qualified" Near-Miss Watchlist.
Validates gatekeeper evaluations, continuous/boolean margins, and near-miss filtering logic.
"""

import unittest
from engine.radar import evaluate_gatekeepers, build_near_miss_candidates


class TestNearMissWatchlist(unittest.TestCase):

    def setUp(self):
        # Base snapshot that passes all 7 gatekeepers
        self.base_snapshot = {
            "price": 105.0,
            "ema50": 100.0,
            "ema50_dist_pct": 5.0,
            "sma200": 95.0,
            "has_200sma": True,
            "overhead_runway_pct": 8.0,
            "overhead_clearance_ok": True,
            "rsi": 55.0,
            "macd_hook_ok": True,
            "market_structure": {"regime": "BULLISH_HH_HL"}
        }

    def test_evaluate_gatekeepers_all_pass(self):
        gates = evaluate_gatekeepers(self.base_snapshot, reclaim_days=2, retrace_type="EMA50")
        self.assertEqual(len(gates), 7)
        for name, gate in gates.items():
            self.assertTrue(gate["pass"], f"Gate {name} unexpectedly failed")

    def test_evaluate_gatekeepers_failed_single_ema50(self):
        snap = dict(self.base_snapshot)
        snap["price"] = 98.0
        snap["ema50"] = 100.0
        snap["ema50_dist_pct"] = -2.0

        gates = evaluate_gatekeepers(snap, reclaim_days=2, retrace_type="EMA50")
        self.assertFalse(gates["price_above_ema50"]["pass"])
        self.assertEqual(gates["price_above_ema50"]["type"], "CONTINUOUS")
        self.assertAlmostEqual(gates["price_above_ema50"]["margin"], -2.0)
        # Other 6 pass
        passed_count = sum(1 for g in gates.values() if g["pass"])
        self.assertEqual(passed_count, 6)

    def test_evaluate_gatekeepers_failed_reclaim_freshness(self):
        # reclaim_days > 3 fails freshness gate
        gates = evaluate_gatekeepers(self.base_snapshot, reclaim_days=5, retrace_type="EMA50")
        self.assertFalse(gates["reclaim_freshness"]["pass"])
        self.assertEqual(gates["reclaim_freshness"]["margin"], -2)
        passed_count = sum(1 for g in gates.values() if g["pass"])
        self.assertEqual(passed_count, 6)

    def test_evaluate_gatekeepers_failed_retrace_taxonomy(self):
        gates = evaluate_gatekeepers(self.base_snapshot, reclaim_days=2, retrace_type="OTHER")
        self.assertFalse(gates["retrace_taxonomy"]["pass"])
        self.assertEqual(gates["retrace_taxonomy"]["type"], "CATEGORICAL")
        passed_count = sum(1 for g in gates.values() if g["pass"])
        self.assertEqual(passed_count, 6)

    def test_evaluate_gatekeepers_failed_overhead_runway(self):
        snap = dict(self.base_snapshot)
        snap["price"] = 90.0
        snap["sma200"] = 100.0
        snap["overhead_runway_pct"] = 2.0  # Needs >= 5.0%
        gates = evaluate_gatekeepers(snap, reclaim_days=2, retrace_type="EMA50")
        self.assertFalse(gates["overhead_200sma_runway"]["pass"])
        self.assertAlmostEqual(gates["overhead_200sma_runway"]["margin"], -3.0)

    def test_evaluate_gatekeepers_failed_rsi_floor(self):
        snap = dict(self.base_snapshot)
        snap["rsi"] = 41.5
        gates = evaluate_gatekeepers(snap, reclaim_days=2, retrace_type="EMA50")
        self.assertFalse(gates["rsi_floor"]["pass"])
        self.assertAlmostEqual(gates["rsi_floor"]["margin"], -3.5)
        passed_count = sum(1 for g in gates.values() if g["pass"])
        self.assertEqual(passed_count, 6)

    def test_evaluate_gatekeepers_failed_macd_hook(self):
        snap = dict(self.base_snapshot)
        snap["macd_hook_ok"] = False
        gates = evaluate_gatekeepers(snap, reclaim_days=2, retrace_type="EMA50")
        self.assertFalse(gates["macd_hook"]["pass"])
        self.assertEqual(gates["macd_hook"]["type"], "BOOLEAN")
        passed_count = sum(1 for g in gates.values() if g["pass"])
        self.assertEqual(passed_count, 6)

    def test_evaluate_gatekeepers_failed_dow_structure(self):
        snap = dict(self.base_snapshot)
        snap["market_structure"] = {"regime": "BEARISH_LH_LL"}
        gates = evaluate_gatekeepers(snap, reclaim_days=2, retrace_type="EMA50")
        self.assertFalse(gates["dow_market_structure"]["pass"])
        self.assertEqual(gates["dow_market_structure"]["type"], "CATEGORICAL")
        passed_count = sum(1 for g in gates.values() if g["pass"])
        self.assertEqual(passed_count, 6)

    def test_build_near_miss_candidates_filters_exactly_one_failure(self):
        # Setup 3 candidate records:
        # Candidate 1: Passes all 7 (Qualified)
        gates_all_pass = evaluate_gatekeepers(self.base_snapshot, reclaim_days=2, retrace_type="EMA50")
        rec_pass = {
            "ticker": "PASS1",
            "price": 105.0,
            "ema50": 100.0,
            "gate_results": gates_all_pass
        }

        # Candidate 2: Fails exactly 1 (reclaim_days=4 -> Near Miss)
        gates_one_fail = evaluate_gatekeepers(self.base_snapshot, reclaim_days=4, retrace_type="EMA50")
        rec_one_fail = {
            "ticker": "NEAR1",
            "price": 105.0,
            "ema50": 100.0,
            "alpha_score": 75.0,
            "beta": 2.0,
            "gate_results": gates_one_fail
        }

        # Candidate 3: Fails 2 gates (reclaim_days=5 and price < ema50)
        snap_two_fail = dict(self.base_snapshot)
        snap_two_fail["price"] = 90.0
        snap_two_fail["ema50"] = 100.0
        snap_two_fail["ema50_dist_pct"] = -10.0
        gates_two_fail = evaluate_gatekeepers(snap_two_fail, reclaim_days=5, retrace_type="EMA50")
        rec_two_fail = {
            "ticker": "FAIL2",
            "price": 90.0,
            "ema50": 100.0,
            "gate_results": gates_two_fail
        }

        ticker_records = [rec_pass, rec_one_fail, rec_two_fail]
        qualified_candidates = [{"ticker": "PASS1"}]
        qualified_stock_candidates = []

        near_misses = build_near_miss_candidates(
            ticker_records=ticker_records,
            qualified_candidates=qualified_candidates,
            qualified_stock_candidates=qualified_stock_candidates
        )

        # Must only return NEAR1
        self.assertEqual(len(near_misses), 1)
        self.assertEqual(near_misses[0]["ticker"], "NEAR1")
        self.assertEqual(near_misses[0]["failed_gate"], "reclaim_freshness")
        self.assertEqual(near_misses[0]["failed_gate_label"], "Reclaim Freshness")
        self.assertIn("Day 4 reclaim", near_misses[0]["failed_reason"])

    def test_build_near_miss_candidates_freshness_sorting(self):
        # Two candidates: one Day 1 reclaim with lower score, one Day 3 reclaim with higher score
        gates1 = evaluate_gatekeepers(self.base_snapshot, reclaim_days=1, retrace_type="OTHER")
        gates2 = evaluate_gatekeepers(self.base_snapshot, reclaim_days=3, retrace_type="OTHER")

        rec_day1 = {
            "ticker": "DAY1",
            "price": 105.0,
            "ema50": 100.0,
            "alpha_score": 60.0,
            "reclaim_days": 1,
            "reclaim_date": "2026-09-20",
            "gate_results": gates1
        }
        rec_day3 = {
            "ticker": "DAY3",
            "price": 105.0,
            "ema50": 100.0,
            "alpha_score": 90.0,
            "reclaim_days": 3,
            "reclaim_date": "2026-09-18",
            "gate_results": gates2
        }

        # Submit in reverse order
        near_misses = build_near_miss_candidates(
            ticker_records=[rec_day3, rec_day1],
            qualified_candidates=[],
            qualified_stock_candidates=[]
        )

        self.assertEqual(len(near_misses), 2)
        # Freshness first: Day 1 should be at index 0
        self.assertEqual(near_misses[0]["ticker"], "DAY1")
        self.assertEqual(near_misses[0]["reclaim_days"], 1)
        self.assertEqual(near_misses[0]["reclaim_date"], "2026-09-20")
        self.assertEqual(near_misses[1]["ticker"], "DAY3")
        self.assertEqual(near_misses[1]["reclaim_days"], 3)


if __name__ == "__main__":
    unittest.main()
