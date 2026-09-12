import unittest
import os
import sys
import tempfile
import json
import pandas as pd
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(ROOT_DIR, "engine")
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

import indicators
import patterns
import stocks
import scanner

class TestEndToEndScoringPipeline(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        self.dates = pd.date_range("2026-07-01", periods=60, freq="B")
        self.symbols = ["SPY", "QQQ", "RSP", "IWM", "NVDA", "AAPL", "MSFT", "INTC", "WBA"]
        
        data = {}
        for sym in self.symbols:
            base_p = 100.0 if sym not in ["INTC", "WBA"] else 30.0
            drift = -0.003 if sym in ["INTC", "WBA"] else 0.002
            returns = np.random.normal(drift, 0.012, len(self.dates))
            close_vals = base_p * np.cumprod(1 + returns)
            high_vals = close_vals * 1.01
            low_vals = close_vals * 0.99
            open_vals = (high_vals + low_vals) / 2
            vol_vals = [1500000] * len(self.dates) if sym != "WBA" else [100000] * len(self.dates)

            data[("Open", sym)] = open_vals
            data[("High", sym)] = high_vals
            data[("Low", sym)] = low_vals
            data[("Close", sym)] = close_vals
            data[("Volume", sym)] = vol_vals

        self.mock_df = pd.DataFrame(data, index=self.dates)
        self.mock_df.columns = pd.MultiIndex.from_tuples(self.mock_df.columns)

    def test_e2e_unified_pipeline_lifecycle(self):
        """
        Validates the entire unified lifecycle end-to-end:
        1. Multi-factor Alpha & Options scoring on technical snapshots.
        2. Active trade daily re-scoring & health tier progression.
        3. Decoupled Sprint vs Anchor capacity segregation.
        4. Relative strength replacement eviction under portfolio saturation.
        5. Strict breakeven accounting with separate metrics.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_options_log = os.path.join(tmpdir, "trades_log.json")
            tmp_stock_log = os.path.join(tmpdir, "stock_trades_log.json")

            # --- PART A: EQUITIES PIPELINE ---
            initial_stock_trades = [
                {
                    "id": "STOCK_NVDA",
                    "ticker": "NVDA",
                    "status": "OPEN",
                    "strategy_prong": "BALANCED",
                    "entry_price": 100.0,
                    "stop_price": 90.0,
                    "tp1": 115.0,
                    "tp2": 130.0,
                    "current_price": 106.0,
                    "current_alpha_score": 82.0,
                    "days_active": 6,
                    "eviction_eligible": False,
                    "consecutive_low_score_days": 0
                },
                {
                    "id": "STOCK_INTC",
                    "ticker": "INTC",
                    "status": "OPEN",
                    "strategy_prong": "BALANCED",
                    "entry_price": 30.0,
                    "stop_price": 20.0,
                    "tp1": 34.0,
                    "tp2": 38.0,
                    "current_price": 24.0,
                    "current_alpha_score": 28.0,
                    "days_active": 7,
                    "eviction_eligible": True,
                    "consecutive_low_score_days": 3
                }
            ]
            with open(tmp_stock_log, "w") as f:
                json.dump({"summary": {}, "trades": initial_stock_trades}, f)

            current_market_bars = {
                "NVDA": {"Close": 108.0, "Open": 107.0, "High": 109.0, "Low": 106.5, "EMA50": 102.0, "rsi": 62.0, "macd_hist": 0.3, "rvol": 1.4, "market_structure": "BULLISH_HH_HL"},
                "INTC": {"Close": 28.0, "Open": 28.2, "High": 28.5, "Low": 27.8, "EMA50": 29.5, "rsi": 32.0, "macd_hist": -0.2, "rvol": 0.6, "market_structure": "BEARISH_LH_LL"}
            }

            new_stock_recs = [
                {
                    "ticker": "MSFT",
                    "price": 420.0,
                    "stop": 405.0,
                    "tp1": 445.0,
                    "tp2": 470.0,
                    "rr_ratio": 2.5,
                    "sector": "TECHNOLOGY",
                    "strategy_prong": "BALANCED",
                    "alpha_score": 88.0,
                    "score_breakdown": {"total": 88.0}
                }
            ]

            stock_res = stocks.update_stock_trades_log(
                new_recommendations=new_stock_recs,
                current_market_bars=current_market_bars,
                today_str="2026-09-12",
                log_path=tmp_stock_log,
                max_active_positions=2,
                confluence_score=4
            )

            st_trades = stock_res["trades"]
            intc_t = next(t for t in st_trades if t["ticker"] == "INTC")
            self.assertEqual(intc_t["status"], "CLOSED_EVICTED")
            self.assertEqual(intc_t["invalidation_driver"], "RELATIVE_STRENGTH_EVICTION")
            self.assertEqual(intc_t["driver_badge"], "purple")
            self.assertIn("Relative Strength Eviction", intc_t["exit_reason"])

            msft_t = next(t for t in st_trades if t["ticker"] == "MSFT")
            self.assertEqual(msft_t["status"], "OPEN")
            self.assertEqual(msft_t["current_alpha_score"], 88.0)
            self.assertEqual(msft_t["active_health_tier"], "TIER_B_ON_TRACK")

            nvda_t = next(t for t in st_trades if t["ticker"] == "NVDA")
            self.assertEqual(nvda_t["status"], "OPEN")
            self.assertGreater(nvda_t["current_alpha_score"], 60.0)
            self.assertEqual(nvda_t["active_health_tier"], "TIER_B_ON_TRACK")

            # --- PART B: OPTIONS DERIVATIVES PIPELINE ---
            initial_opt_trades = [
                {
                    "id": "OPT_AAPL",
                    "ticker": "AAPL",
                    "status": "OPEN",
                    "structure": "Bull Call Spread (45-60 DTE)",
                    "sector": "TECHNOLOGY",
                    "entry_price": 100.0,
                    "stop_price": 85.0,
                    "tp1": 115.0,
                    "tp2": 130.0,
                    "current_price": 102.0,
                    "current_alpha_score": 80.0,
                    "days_active": 6,
                    "eviction_eligible": False,
                    "consecutive_low_score_days": 0
                },
                {
                    "id": "OPT_WBA",
                    "ticker": "WBA",
                    "status": "OPEN",
                    "structure": "Bull Call Spread (45-60 DTE)",
                    "sector": "CONSUMER",
                    "entry_price": 25.0,
                    "stop_price": 15.0,
                    "tp1": 30.0,
                    "tp2": 35.0,
                    "current_price": 18.0,
                    "current_alpha_score": 25.0,
                    "strategy_prong": "HIGH_RISK",
                    "long_oi": 80,
                    "short_oi": 50,
                    "bid_ask_spread_pct": 0.12,
                    "days_active": 7,
                    "eviction_eligible": True,
                    "consecutive_low_score_days": 3
                }
            ]
            with open(tmp_options_log, "w") as f:
                json.dump({"summary": {}, "trades": initial_opt_trades}, f)

            new_opt_recs = [
                {
                    "ticker": "NVDA",
                    "price": 108.0,
                    "stop": 98.0,
                    "tp1": 120.0,
                    "tp2": 135.0,
                    "sector": "TECHNOLOGY",
                    "subsector": "Semiconductors",
                    "structure": "Bull Call Spread (45-60 DTE)",
                    "options_alpha_score": 86.0,
                    "alpha_score": 86.0,
                    "score_breakdown": {"total": 86.0}
                }
            ]

            orig_data_dir = scanner.DATA_DIR
            try:
                scanner.DATA_DIR = tmpdir
                opt_res = scanner.audit_and_update_trades(
                    raw_data=self.mock_df,
                    qualified_candidates=new_opt_recs,
                    today_str="2026-09-12",
                    max_options_slots=2,
                    confluence_score=4
                )

                opt_trades = opt_res["trades"]
                wba_t = next(t for t in opt_trades if t["ticker"] == "WBA")
                self.assertEqual(wba_t["status"], "CLOSED_EVICTED")
                self.assertEqual(wba_t["invalidation_driver"], "RELATIVE_STRENGTH_EVICTION")
                self.assertIn("Relative Strength Eviction", wba_t["exit_reason"])

                nvda_opt = next(t for t in opt_trades if t["ticker"] == "NVDA")
                self.assertEqual(nvda_opt["status"], "OPEN")
                self.assertEqual(nvda_opt["current_alpha_score"], 86.0)

                sum_opt = opt_res["summary"]
                self.assertEqual(sum_opt["active_open"], 2)
                self.assertEqual(sum_opt["evicted_trades"], 1)
                self.assertIn("sprint_open", sum_opt)
                self.assertIn("anchor_open", sum_opt)
            finally:
                scanner.DATA_DIR = orig_data_dir

if __name__ == "__main__":
    unittest.main()
