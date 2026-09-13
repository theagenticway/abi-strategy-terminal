"""
Test Suite for Multi-Horizon 3-Prong Architecture, Scalable Capital ($100K - $500K+),
Stagnation Stops, Liquid Route Auto-Switch, and Bifurcated IV Scoring.
"""

import os
import sys
import unittest

ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine")
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

import importlib.util

def load_mod(name):
    mod_path = os.path.join(ENGINE_DIR, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, mod_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

try:
    import stocks
except ModuleNotFoundError:
    stocks = load_mod("stocks")

try:
    import patterns
except ModuleNotFoundError:
    patterns = load_mod("patterns")

try:
    import indicators
except ModuleNotFoundError:
    indicators = load_mod("indicators")


class TestMultiHorizonAndSizingArchitecture(unittest.TestCase):
    def setUp(self):
        self.sample_snapshot = {
            "price": 100.0,
            "ema50": 98.0,
            "sma150": 92.0,
            "sma200": 85.0,
            "beta": 1.9,
            "adr_pct": 3.8,
            "rsi": 58.0,
            "macd_hook_ok": True,
            "rvol": 2.2,
            "market_structure": {
                "regime": "BULLISH_HH_HL",
                "overhead_resistance_runway": 12.0,
                "badge": "🟢 HH/HL (CONFIRMED)"
            }
        }

    def test_scalable_capital_sizing_100k_to_500k(self):
        """Validates that position sizing scales proportionally from $100K to $500K+"""
        size_100k = stocks.calculate_stock_position_size(
            entry_price=100.0, stop_price=95.0, portfolio_capital=100000.0
        )
        self.assertEqual(size_100k["shares"], 60)
        self.assertLessEqual(size_100k["capital_deployed"], 6000.0)
        self.assertLessEqual(size_100k["actual_risk_dollars"], 450.0)

        size_500k = stocks.calculate_stock_position_size(
            entry_price=100.0, stop_price=95.0, portfolio_capital=500000.0
        )
        self.assertEqual(size_500k["shares"], 300)
        self.assertLessEqual(size_500k["capital_deployed"], 30000.0)
        self.assertLessEqual(size_500k["actual_risk_dollars"], 2250.0)

    def test_three_prong_structure_generators(self):
        """Validates the 3 distinct execution prongs: High-Risk Sprint, Balanced Swing, Core Accumulation"""
        hr = stocks.structure_high_risk_stock_trade(
            "SPRINT", "TECH SEMIS", self.sample_snapshot, "EMA50", 1, portfolio_capital=100000.0
        )
        self.assertEqual(hr["strategy_prong"], "HIGH_RISK")
        self.assertEqual(hr["stagnation_limit_days"], 10)
        self.assertIn("Sprint", hr["structure"])
        self.assertIn("10–14 Sessions", hr["holding_horizon"])

        bal = stocks.structure_balanced_stock_trade(
            "SWING", "TECH SOFTWARE", self.sample_snapshot, "EMA50", 1, portfolio_capital=100000.0
        )
        self.assertEqual(bal["strategy_prong"], "BALANCED")
        self.assertEqual(bal["stagnation_limit_days"], 14)
        self.assertIn("15–25 Sessions", bal["holding_horizon"])

        core = stocks.structure_core_stock_accumulation(
            "CORE", "TECH CORE", self.sample_snapshot, portfolio_capital=100000.0
        )
        self.assertEqual(core["strategy_prong"], "CORE")
        self.assertIsNone(core["stagnation_limit_days"])
        self.assertIn("40–120+ Sessions", core["holding_horizon"])

    def test_stagnation_exits_high_risk_and_balanced(self):
        """Validates stagnation exits: Day 10 for High-Risk (<1.0R) and Day 14 for Balanced (<50% TP1)"""
        hr_trade = [{
            "id": "HR_TEST", "ticker": "HR1", "status": "OPEN", "strategy_prong": "HIGH_RISK",
            "entry_price": 100.0, "stop_price": 95.0, "tp1": 111.0, "tp2": 117.5, "days_active": 9
        }]
        bars_d10 = {"HR1": {"Close": 102.0, "High": 103.0, "Low": 101.5, "Open": 102.0, "EMA50": 96.0}}
        audited_hr = stocks.audit_stock_positions(hr_trade, bars_d10, "2026-09-11")
        self.assertEqual(audited_hr[0]["status"], "STAGNATION_EXIT")
        self.assertIn("Day 10", audited_hr[0]["exit_reason"])
        self.assertEqual(audited_hr[0]["invalidation_driver"], "STAGNATION RECYCLE")

        bal_trade = [{
            "id": "BAL_TEST", "ticker": "BAL1", "status": "OPEN", "strategy_prong": "BALANCED",
            "entry_price": 100.0, "stop_price": 92.0, "tp1": 120.0, "tp2": 128.0, "days_active": 13
        }]
        bars_d14 = {"BAL1": {"Close": 99.0, "High": 101.0, "Low": 98.5, "Open": 99.5, "EMA50": 94.0}}
        audited_bal = stocks.audit_stock_positions(bal_trade, bars_d14, "2026-09-11")
        self.assertEqual(audited_bal[0]["status"], "STAGNATION_EXIT")
        self.assertIn("Day 14", audited_bal[0]["exit_reason"])

    def test_bifurcated_iv_scoring_behavior(self):
        """Validates that High-Risk rewards High IV Rank, while Core LEAPS rewards Low IV Rank"""
        _, b_hr_high = patterns.compute_options_alpha_score(strategy_prong="HIGH_RISK", iv_rank=75.0, return_breakdown=True)
        _, b_hr_low = patterns.compute_options_alpha_score(strategy_prong="HIGH_RISK", iv_rank=20.0, return_breakdown=True)
        self.assertGreater(b_hr_high["iv_rank_efficiency"], b_hr_low["iv_rank_efficiency"])

        _, b_core_low = patterns.compute_options_alpha_score(strategy_prong="CORE", iv_rank=20.0, return_breakdown=True)
        _, b_core_high = patterns.compute_options_alpha_score(strategy_prong="CORE", iv_rank=75.0, return_breakdown=True)
        self.assertGreater(b_core_low["iv_rank_efficiency"], b_core_high["iv_rank_efficiency"])

    def test_liquid_route_auto_switch(self):
        """Validates auto-routing to Stock Portfolio when options chain fails liquidity criteria"""
        illiquid_opt = {"passed": False, "long_oi": 150, "short_oi": 120, "long_bid": 1.0, "long_ask": 1.5}
        is_liq, reason, route_to_stock = patterns.is_liquid_options(illiquid_opt, min_oi=500, max_spread_pct=0.08)
        self.assertFalse(is_liq)
        self.assertTrue(route_to_stock)
        self.assertIn("Low Open Interest", reason)

        liquid_opt = {"passed": True, "long_oi": 800, "short_oi": 600, "long_bid": 2.0, "long_ask": 2.1}
        is_liq_ok, _, route_to_stock_ok = patterns.is_liquid_options(liquid_opt, min_oi=500, max_spread_pct=0.08)
        self.assertTrue(is_liq_ok)
        self.assertFalse(route_to_stock_ok)


if __name__ == "__main__":
    unittest.main(verbosity=2)
