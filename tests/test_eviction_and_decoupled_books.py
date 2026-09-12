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

from stocks import update_stock_trades_log, MAX_STOCK_PORTFOLIO_SLOTS, MAX_STOCK_SPRINT_SLOTS, MAX_STOCK_ANCHOR_SLOTS
from indicators import compute_active_health_tier
import scanner

class TestEvictionAndDecoupledBooks(unittest.TestCase):

    def test_eviction_triggered_when_hurdle_cleared(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = os.path.join(tmpdir, "stock_trades_log.json")
            initial_trades = [
                {
                    "id": "TRADE_HEALTHY",
                    "ticker": "NVDA",
                    "status": "OPEN",
                    "strategy_prong": "BALANCED",
                    "entry_price": 100.0,
                    "stop_price": 92.0,
                    "tp1": 115.0,
                    "tp2": 130.0,
                    "current_price": 105.0,
                    "current_alpha_score": 85.0,
                    "days_active": 6,
                    "eviction_eligible": False,
                    "consecutive_low_score_days": 0
                },
                {
                    "id": "TRADE_DEGRADING",
                    "ticker": "INTC",
                    "status": "OPEN",
                    "strategy_prong": "BALANCED",
                    "entry_price": 30.0,
                    "stop_price": 25.0,
                    "tp1": 34.0,
                    "tp2": 38.0,
                    "current_price": 28.5,
                    "current_alpha_score": 32.0,
                    "days_active": 7,
                    "eviction_eligible": True,
                    "consecutive_low_score_days": 3
                }
            ]
            with open(tmp_log, "w") as f:
                json.dump({"summary": {}, "trades": initial_trades}, f)

            new_recs = [
                {
                    "ticker": "AMD",
                    "price": 160.0,
                    "stop": 152.0,
                    "tp1": 175.0,
                    "tp2": 190.0,
                    "rr_ratio": 2.5,
                    "sector": "TECHNOLOGY",
                    "strategy_prong": "BALANCED",
                    "alpha_score": 82.0,
                    "score_breakdown": {"total": 82.0}
                }
            ]
            market_bars = {
                "NVDA": {"Close": 105.0, "Open": 104.0, "High": 106.0, "Low": 104.0, "EMA50": 100.0, "rsi": 60.0, "macd_hist": 0.2, "rvol": 1.2, "market_structure": "BULLISH_HH_HL"},
                "INTC": {"Close": 28.5, "Open": 28.6, "High": 28.7, "Low": 28.3, "EMA50": 29.5, "rsi": 38.0, "macd_hist": -0.1, "rvol": 0.7, "market_structure": "BEARISH_LH_LL"},
                "AMD": {"Close": 160.0, "Open": 159.0, "High": 161.0, "Low": 158.0, "EMA50": 154.0, "rsi": 62.0, "macd_hist": 0.4, "rvol": 1.5, "market_structure": "BULLISH_HH_HL"}
            }

            res = update_stock_trades_log(
                new_recommendations=new_recs,
                current_market_bars=market_bars,
                today_str="2026-09-12",
                log_path=tmp_log,
                max_active_positions=2
            )

            trades = res["trades"]
            intc_trade = next(t for t in trades if t["ticker"] == "INTC")
            self.assertEqual(intc_trade["status"], "CLOSED_EVICTED")
            self.assertEqual(intc_trade["invalidation_driver"], "RELATIVE_STRENGTH_EVICTION")
            self.assertEqual(intc_trade["driver_badge"], "purple")
            self.assertIn("Relative Strength Eviction", intc_trade["exit_reason"])
            self.assertEqual(intc_trade["exit_date"], "2026-09-12")

            amd_trade = next(t for t in trades if t["ticker"] == "AMD")
            self.assertEqual(amd_trade["status"], "OPEN")
            self.assertEqual(amd_trade["current_alpha_score"], 82.0)

            active_open = [t for t in trades if t["status"] in ["OPEN", "TP1_SCALED"]]
            self.assertEqual(len(active_open), 2)
            self.assertEqual(set(t["ticker"] for t in active_open), {"NVDA", "AMD"})

    def test_eviction_blocked_when_hurdle_not_met(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = os.path.join(tmpdir, "stock_trades_log.json")
            initial_trades = [
                {
                    "id": "TRADE_DEGRADING",
                    "ticker": "INTC",
                    "status": "OPEN",
                    "strategy_prong": "BALANCED",
                    "entry_price": 30.0,
                    "stop_price": 25.0,
                    "tp1": 34.0,
                    "tp2": 38.0,
                    "current_price": 28.5,
                    "current_alpha_score": 38.0,
                    "days_active": 6,
                    "eviction_eligible": True,
                    "consecutive_low_score_days": 3
                }
            ]
            with open(tmp_log, "w") as f:
                json.dump({"summary": {}, "trades": initial_trades}, f)

            new_recs = [
                {
                    "ticker": "CSCO",
                    "price": 50.0,
                    "stop": 48.0,
                    "tp1": 55.0,
                    "tp2": 60.0,
                    "rr_ratio": 2.5,
                    "sector": "TECHNOLOGY",
                    "strategy_prong": "BALANCED",
                    "alpha_score": 48.0,
                    "score_breakdown": {"total": 48.0}
                }
            ]
            market_bars = {
                "INTC": {"Close": 28.5, "Open": 28.6, "High": 28.7, "Low": 28.3, "EMA50": 29.5, "rsi": 38.0, "macd_hist": -0.1, "rvol": 0.7, "market_structure": "BEARISH_LH_LL"}
            }

            res = update_stock_trades_log(
                new_recommendations=new_recs,
                current_market_bars=market_bars,
                today_str="2026-09-12",
                log_path=tmp_log,
                max_active_positions=1
            )

            trades = res["trades"]
            intc_trade = next(t for t in trades if t["ticker"] == "INTC")
            self.assertEqual(intc_trade["status"], "OPEN")
            self.assertFalse(any(t["ticker"] == "CSCO" for t in trades))

    def test_decoupled_book_capacity_isolation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = os.path.join(tmpdir, "stock_trades_log.json")
            initial_trades = [
                {
                    "id": "SPRINT_1",
                    "ticker": "PLTR",
                    "status": "OPEN",
                    "strategy_prong": "HIGH_RISK",
                    "entry_price": 30.0, "stop_price": 28.0, "tp1": 35.0, "tp2": 40.0,
                    "current_price": 31.0, "current_alpha_score": 80.0, "days_active": 3,
                    "eviction_eligible": False
                },
                {
                    "id": "SPRINT_2",
                    "ticker": "TSLA",
                    "status": "OPEN",
                    "strategy_prong": "BALANCED",
                    "entry_price": 220.0, "stop_price": 210.0, "tp1": 240.0, "tp2": 260.0,
                    "current_price": 225.0, "current_alpha_score": 75.0, "days_active": 4,
                    "eviction_eligible": False
                }
            ]
            with open(tmp_log, "w") as f:
                json.dump({"summary": {}, "trades": initial_trades}, f)

            new_recs = [
                {
                    "ticker": "BRK-B",
                    "price": 450.0,
                    "stop": 435.0,
                    "tp1": 480.0,
                    "tp2": 510.0,
                    "rr_ratio": 2.5,
                    "sector": "FINANCIAL",
                    "strategy_prong": "CORE",
                    "prong_badge": "🛡️ LOW RISK (CORE COMPOUNDER)",
                    "alpha_score": 88.0,
                    "score_breakdown": {"total": 88.0}
                }
            ]
            market_bars = {
                "PLTR": {"Close": 31.0, "Open": 30.5, "High": 31.5, "Low": 30.0, "EMA50": 29.0},
                "TSLA": {"Close": 225.0, "Open": 222.0, "High": 226.0, "Low": 220.0, "EMA50": 215.0}
            }

            res = update_stock_trades_log(
                new_recommendations=new_recs,
                current_market_bars=market_bars,
                today_str="2026-09-12",
                log_path=tmp_log,
                max_active_positions=4
            )

            trades = res["trades"]
            self.assertTrue(any(t["ticker"] == "BRK-B" for t in trades))
            brk = next(t for t in trades if t["ticker"] == "BRK-B")
            self.assertEqual(brk["status"], "OPEN")
            self.assertEqual(brk["strategy_prong"], "CORE")
            self.assertEqual(res["summary"]["sprint_open"], 2)
            self.assertEqual(res["summary"]["anchor_open"], 1)

    def test_options_eviction_triggered_when_hurdle_cleared(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = os.path.join(tmpdir, "trades_log.json")
            initial_trades = [
                {
                    "id": "OPT_HEALTHY",
                    "ticker": "NVDA",
                    "status": "OPEN",
                    "structure": "Bull Call Spread (45-60 DTE)",
                    "sector": "TECHNOLOGY",
                    "entry_price": 100.0,
                    "stop_price": 90.0,
                    "tp1": 115.0,
                    "tp2": 130.0,
                    "current_price": 105.0,
                    "current_alpha_score": 88.0,
                    "days_active": 6,
                    "eviction_eligible": False,
                    "consecutive_low_score_days": 0
                },
                {
                    "id": "OPT_DEGRADING",
                    "ticker": "WBA",
                    "status": "OPEN",
                    "structure": "Bull Call Spread (45-60 DTE)",
                    "sector": "CONSUMER",
                    "entry_price": 20.0,
                    "stop_price": 12.0,
                    "tp1": 24.0,
                    "tp2": 28.0,
                    "current_price": 15.0,
                    "current_alpha_score": 25.0,
                    "long_oi": 150,
                    "short_oi": 100,
                    "bid_ask_spread_pct": 0.12,
                    "days_active": 7,
                    "eviction_eligible": True,
                    "consecutive_low_score_days": 3
                }
            ]
            with open(tmp_log, "w") as f:
                json.dump({"summary": {}, "trades": initial_trades}, f)

            new_candidates = [
                {
                    "ticker": "AAPL",
                    "price": 220.0,
                    "stop": 210.0,
                    "tp1": 235.0,
                    "tp2": 250.0,
                    "sector": "TECHNOLOGY",
                    "subsector": "Consumer Electronics",
                    "structure": "Bull Call Spread (45-60 DTE)",
                    "options_alpha_score": 85.0,
                    "alpha_score": 85.0,
                    "score_breakdown": {"total": 85.0}
                }
            ]

            dates = pd.date_range("2026-08-01", periods=60, freq="B")
            data = {}
            for t in ["SPY", "NVDA", "WBA", "AAPL"]:
                close_vals = np.linspace(100, 110, len(dates)) if t != "WBA" else np.linspace(20, 15, len(dates))
                for col in ["Open", "High", "Low", "Close"]:
                    data[(col, t)] = close_vals
                data[("Volume", t)] = [1000000] if t != "WBA" else [100000]
                data[("Volume", t)] = data[("Volume", t)] * len(dates)
            mock_df = pd.DataFrame(data, index=dates)
            mock_df.columns = pd.MultiIndex.from_tuples(mock_df.columns)

            orig_data_dir = scanner.DATA_DIR
            try:
                scanner.DATA_DIR = tmpdir
                res = scanner.audit_and_update_trades(
                    raw_data=mock_df,
                    qualified_candidates=new_candidates,
                    today_str="2026-09-12",
                    max_options_slots=2
                )
                trades = res["trades"]
                wba = next(t for t in trades if t["ticker"] == "WBA")
                self.assertEqual(wba["status"], "CLOSED_EVICTED")
                self.assertEqual(wba["invalidation_driver"], "RELATIVE_STRENGTH_EVICTION")
                self.assertIn("Relative Strength Eviction", wba["exit_reason"])
                self.assertTrue(any(t["ticker"] == "AAPL" and t["status"] == "OPEN" for t in trades))
            finally:
                scanner.DATA_DIR = orig_data_dir

if __name__ == "__main__":
    unittest.main()
