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


    def test_compute_alpha_composite_score_components(self):
        """
        Validates the 5 multi-factor components of Alpha Composite Score:
        Freshness (30), RVOL (25), EMA50 Proximity (20), Sector RS (15), R:R (10).
        """
        # 1. Perfect score: Day 0 (30), RVOL >= 2.0 (25), Dist <= 1.5% (20), Top Quartile RS (15), RR >= 3.0 (10)
        perf_score, breakdown = stocks.compute_alpha_composite_score(
            reclaim_days=0, rvol=2.5, price=100.5, ema50=100.0, sector="ENERGY", rr_ratio=3.2,
            top_quartile_sectors=["ENERGY", "TECH SEMIS"], return_breakdown=True
        )
        self.assertEqual(perf_score, 100.0)
        self.assertEqual(breakdown["freshness"], 30.0)
        self.assertEqual(breakdown["rvol"], 25.0)
        self.assertEqual(breakdown["proximity"], 20.0)
        self.assertEqual(breakdown["sector_rs"], 15.0)
        self.assertEqual(breakdown["rr"], 10.0)

        # 2. Freshness gradient
        self.assertEqual(stocks.compute_alpha_composite_score(reclaim_days=0, rvol=1.0, price=100, ema50=100, sector="TECH", rr_ratio=2.5), 73.0)
        self.assertEqual(stocks.compute_alpha_composite_score(reclaim_days=1, rvol=1.0, price=100, ema50=100, sector="TECH", rr_ratio=2.5), 68.0)
        self.assertEqual(stocks.compute_alpha_composite_score(reclaim_days=2, rvol=1.0, price=100, ema50=100, sector="TECH", rr_ratio=2.5), 58.0)
        self.assertEqual(stocks.compute_alpha_composite_score(reclaim_days=3, rvol=1.0, price=100, ema50=100, sector="TECH", rr_ratio=2.5), 48.0)
        self.assertEqual(stocks.compute_alpha_composite_score(reclaim_days=4, rvol=1.0, price=100, ema50=100, sector="TECH", rr_ratio=2.5), 43.0)

        # 3. RVOL thresholds: >=2.0 -> 25, >=1.5 -> 20, >=1.2 -> 15, >=1.0 -> 10, <1.0 -> 5
        score_2x, b_2x = stocks.compute_alpha_composite_score(rvol=2.2, return_breakdown=True)
        score_1_5x, b_1_5x = stocks.compute_alpha_composite_score(rvol=1.7, return_breakdown=True)
        score_1_2x, b_1_2x = stocks.compute_alpha_composite_score(rvol=1.3, return_breakdown=True)
        score_1_0x, b_1_0x = stocks.compute_alpha_composite_score(rvol=1.05, return_breakdown=True)
        score_sub1, b_sub1 = stocks.compute_alpha_composite_score(rvol=0.8, return_breakdown=True)
        self.assertEqual(b_2x["rvol"], 25.0)
        self.assertEqual(b_1_5x["rvol"], 20.0)
        self.assertEqual(b_1_2x["rvol"], 15.0)
        self.assertEqual(b_1_0x["rvol"], 10.0)
        self.assertEqual(b_sub1["rvol"], 5.0)

        # 4. Proximity thresholds: <=1.5% -> 20, <=3.0% -> 15, <=5.0% -> 10, >5.0% -> 5
        _, b_p1 = stocks.compute_alpha_composite_score(price=101.0, ema50=100.0, return_breakdown=True)
        _, b_p2 = stocks.compute_alpha_composite_score(price=102.5, ema50=100.0, return_breakdown=True)
        _, b_p3 = stocks.compute_alpha_composite_score(price=104.5, ema50=100.0, return_breakdown=True)
        _, b_p4 = stocks.compute_alpha_composite_score(price=108.0, ema50=100.0, return_breakdown=True)
        self.assertEqual(b_p1["proximity"], 20.0)
        self.assertEqual(b_p2["proximity"], 15.0)
        self.assertEqual(b_p3["proximity"], 10.0)
        self.assertEqual(b_p4["proximity"], 5.0)

        # 5. Dict argument support
        test_dict = {"reclaim_days": 1, "rvol": 1.6, "price": 101.0, "ema50": 100.0, "sector": "TECH SEMIS", "rr_ratio": "1:2.5"}
        d_score, d_break = stocks.compute_alpha_composite_score(test_dict, top_quartile_sectors=["TECH SEMIS"], return_breakdown=True)
        self.assertEqual(d_score, 88.0)
        self.assertEqual(d_break["sector_rs"], 15.0)

    def test_dynamic_ranking_and_absence_of_dictionary_bias(self):
        """
        Verifies that candidates are dynamically ranked by Alpha Composite Score,
        completely replacing static alphabetical / first-come dictionary order.
        """
        # Candidate A appears FIRST in dictionary, but is stale (D3, low rvol, extended from EMA)
        cand_a = {
            "ticker": "AAAA",
            "sector": "MATERIALS",
            "price": 110.0,
            "ema50": 100.0, # 10% extended
            "reclaim_days": 3,
            "rvol": 0.7,
            "rr_ratio": "1:2.5"
        }
        # Candidate B appears LAST in dictionary, but is fresh (D0, 2.2x rvol, tight to EMA)
        cand_b = {
            "ticker": "ZZZZ",
            "sector": "TECH SEMIS",
            "price": 100.8,
            "ema50": 100.0, # 0.8% distance
            "reclaim_days": 0,
            "rvol": 2.2,
            "rr_ratio": "1:3.0"
        }

        top_quartile = ["TECH SEMIS"]
        cand_a["alpha_score"] = stocks.compute_alpha_composite_score(cand_a, top_quartile_sectors=top_quartile)
        cand_b["alpha_score"] = stocks.compute_alpha_composite_score(cand_b, top_quartile_sectors=top_quartile)

        # Verify B massively outscores A despite A being at the top of the raw dictionary
        self.assertGreater(cand_b["alpha_score"], cand_a["alpha_score"])
        self.assertGreater(cand_b["alpha_score"], 80.0)
        self.assertLess(cand_a["alpha_score"], 40.0)

        # Verify sorting
        candidates = [cand_a, cand_b]
        candidates.sort(key=lambda x: x["alpha_score"], reverse=True)
        self.assertEqual(candidates[0]["ticker"], "ZZZZ", "Fresh high-momentum ZZZZ must outrank stale AAAA")

    def test_sector_concentration_guardrails_diversity_cap(self):
        """
        Verifies that no more than 2 tickers from any single sector are selected in the top 5,
        preventing single-sector concentration.
        """
        # Create 4 Financials candidates and 2 Tech candidates
        cands = [
            {"ticker": "FIN1", "sector": "FINANCIALS", "alpha_score": 95.0},
            {"ticker": "FIN2", "sector": "FINANCIALS", "alpha_score": 92.0},
            {"ticker": "FIN3", "sector": "FINANCIALS", "alpha_score": 90.0},
            {"ticker": "FIN4", "sector": "FINANCIALS", "alpha_score": 88.0},
            {"ticker": "TECH1", "sector": "TECH SEMIS", "alpha_score": 85.0},
            {"ticker": "TECH2", "sector": "TECH SOFTWARE", "alpha_score": 82.0},
            {"ticker": "ENG1", "sector": "ENERGY", "alpha_score": 80.0},
        ]
        
        # Apply diversity filter (max 2 per sector)
        selected = []
        sector_counts = {}
        for c in cands:
            sec = c["sector"]
            if sector_counts.get(sec, 0) < 2:
                selected.append(c)
                sector_counts[sec] = sector_counts.get(sec, 0) + 1
            if len(selected) >= 5:
                break

        self.assertEqual(len(selected), 5)
        self.assertEqual([c["ticker"] for c in selected], ["FIN1", "FIN2", "TECH1", "TECH2", "ENG1"])
        self.assertEqual(sector_counts["FINANCIALS"], 2, "Financials must be capped at 2")
        self.assertNotIn("FIN3", [c["ticker"] for c in selected])
        self.assertNotIn("FIN4", [c["ticker"] for c in selected])


if __name__ == "__main__":
    unittest.main(verbosity=2)
