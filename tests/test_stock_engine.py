"""
Unit & Functional Test Suite for Equity / Stock Strategy Engine (engine/stocks.py)
Validates fixed-fractional dollar-at-risk sizing, 20% capital ceiling safeguard,
Two-Tranche Scale & Trail exits, gap slippage modeling, and independent ledger auditing.
"""

import os
import sys
import unittest
import tempfile
import json

ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine")
sys.path.insert(0, ENGINE_DIR)

# Robust loader for stocks.py
try:
    import stocks
except ModuleNotFoundError:
    import importlib.util
    stocks_path = os.path.join(ENGINE_DIR, "stocks.py")
    spec = importlib.util.spec_from_file_location("stocks", stocks_path)
    stocks = importlib.util.module_from_spec(spec)
    sys.modules["stocks"] = stocks
    spec.loader.exec_module(stocks)


class TestStockStrategyEngine(unittest.TestCase):
    def setUp(self):
        self.portfolio_capital = 50000.0
        self.snapshot = {
            "price": 68.41,
            "ema50": 55.70,
            "sma150": 52.00,
            "sma200": 48.50,
            "rvol": 1.35,
            "weekly_stage": "STAGE 2 (Advancing)"
        }

    def test_stock_position_sizing_fixed_risk(self):
        """Validates that shares are sized strictly on Dollar-at-Risk (1.5% = $750)."""
        entry = 68.41
        stop = 54.60
        sizing = stocks.calculate_stock_position_size(entry, stop, self.portfolio_capital, risk_pct=0.015, max_alloc_pct=0.20)
        
        self.assertGreater(sizing["shares"], 0)
        self.assertLessEqual(sizing["capital_deployed"], self.portfolio_capital * 0.20)
        self.assertAlmostEqual(sizing["actual_risk_dollars"], 750.0, delta=25.0)
        self.assertFalse(sizing["capped_by_max_alloc"])

    def test_tight_stop_capital_ceiling_safeguard(self):
        """Verifies that an ultra-tight stop ($100 price, $99 stop) does NOT blow up the account."""
        entry = 100.0
        tight_stop = 99.0  # $1.00 risk/share -> Naive formula would want 750 shares ($75k)
        sizing = stocks.calculate_stock_position_size(entry, tight_stop, self.portfolio_capital, risk_pct=0.015, max_alloc_pct=0.20)
        
        self.assertTrue(sizing["capped_by_max_alloc"], "Must be capped by 20% allocation ceiling")
        self.assertLessEqual(sizing["capital_deployed"], 10000.0, "Position value must not exceed 20% ($10k)")
        self.assertEqual(sizing["shares"], 100)

    def test_structure_stock_trade(self):
        """Validates tactical equity swing structuring, 1:2.5+ R:R, and execution ticket."""
        trade = stocks.structure_stock_trade("DOCU", "TECH SOFTWARE", self.snapshot, "EMA50", 1, regime="RISK-ON", portfolio_capital=self.portfolio_capital)
        
        self.assertEqual(trade["action"], "BUY")
        self.assertEqual(trade["asset_class"], "EQUITY")
        self.assertEqual(trade["ticker"], "DOCU")
        self.assertLess(trade["stop"], trade["price"])
        self.assertGreater(trade["tp1"], trade["price"])
        self.assertGreater(trade["tp2"], trade["tp1"])
        self.assertIn("1:2.5", trade["rr_ratio"])
        self.assertIn("BUY", trade["order_ticket"])
        self.assertIn("LIMIT", trade["order_ticket"])
        self.assertIn("Scale 50% at TP1", trade["execution_guidance"])

    def test_structure_core_stock_accumulation(self):
        """Validates secular Stage 2 compounder structuring with 200 SMA macro stop."""
        core = stocks.structure_core_stock_accumulation("NVDA", "TECH SEMIS", self.snapshot, portfolio_capital=self.portfolio_capital)
        
        self.assertEqual(core["asset_class"], "CORE_EQUITY")
        self.assertLess(core["macro_stop"], core["price"])
        self.assertIn("Macro Trailing Stop on 200 SMA", core["execution_guidance"])

    def test_two_tranche_scale_and_trail_exit_model(self):
        """
        Validates Two-Tranche lifecycle:
        - TP1 touch scales 50% and moves stop to breakeven.
        - Rising 50 EMA trails stop higher.
        - Gap-down executes at Open price (realistic slippage).
        """
        trades = [{
            "id": "STOCK_UNIT_TEST",
            "status": "OPEN",
            "ticker": "PLTR",
            "entry_price": 100.0,
            "stop_price": 92.0,
            "tp1": 120.0,
            "tp2": 135.0,
            "shares": 50,
            "days_active": 0,
            "capital_deployed": 5000.0
        }]

        # Day 1: Price touches TP1 (122.0 high) -> Tranche 1 scaled!
        bars_day1 = {"PLTR": {"High": 122.0, "Low": 98.0, "Open": 101.0, "Close": 121.0, "EMA50": 95.0}}
        audited_1 = stocks.audit_stock_positions(trades, bars_day1, "2026-09-01")
        self.assertEqual(audited_1[0]["status"], "TP1_SCALED")
        self.assertEqual(audited_1[0]["stop_price"], 100.0, "Stop must move to Breakeven upon TP1 touch")

        # Day 2: 50 EMA rises to 106.0 -> stop trails to 104.94
        bars_day2 = {"PLTR": {"High": 126.0, "Low": 115.0, "Open": 121.0, "Close": 125.0, "EMA50": 106.0}}
        audited_2 = stocks.audit_stock_positions(audited_1, bars_day2, "2026-09-02")
        self.assertGreater(audited_2[0]["stop_price"], 100.0, "Stop must trail above breakeven along rising 50 EMA")

        # Day 3: Gap-down below trailing stop (Open 97.0 vs Stop ~105.0) -> fills at Open (97.0)
        bars_day3 = {"PLTR": {"High": 100.0, "Low": 94.0, "Open": 97.0, "Close": 95.0, "EMA50": 106.0}}
        audited_3 = stocks.audit_stock_positions(audited_2, bars_day3, "2026-09-03")
        self.assertIn(audited_3[0]["status"], ["CLOSED_TRAILING_PROFIT", "CLOSED_BREAKEVEN"])
        self.assertEqual(audited_3[0]["exit_price"], 97.0, "Realistic slippage: must fill at Open price on gap-down")

    def test_stock_trades_log_persistence_and_summary(self):
        """Validates persistent JSON schema serialization and independent metrics calculation."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            recs = [stocks.structure_stock_trade("DOCU", "TECH SOFTWARE", self.snapshot, "EMA50", 1)]
            current_bars = {"DOCU": {"High": 70.0, "Low": 67.0, "Open": 68.0, "Close": 69.5, "EMA50": 55.7}}
            
            log_result = stocks.update_stock_trades_log(recs, current_bars, "2026-09-04", spy_ret=0.005, log_path=tmp_path)
            
            self.assertIn("summary", log_result)
            self.assertIn("trades", log_result)
            self.assertEqual(len(log_result["trades"]), 1)
            self.assertEqual(log_result["trades"][0]["ticker"], "DOCU")
            self.assertEqual(log_result["trades"][0]["status"], "OPEN")
            
            # Verify file exists on disk and is readable
            with open(tmp_path, "r") as f:
                saved = json.load(f)
            self.assertEqual(saved["summary"]["total_recommendations"], 1)
            self.assertEqual(saved["summary"]["active_open"], 1)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
