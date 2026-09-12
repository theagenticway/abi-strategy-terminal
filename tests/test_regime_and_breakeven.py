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

from indicators import get_regime_tier_capacities
from stocks import update_stock_trades_log
import scanner

class TestRegimeAndBreakevenAccounting(unittest.TestCase):

    def test_get_regime_tier_capacities_mapping(self):
        # Confluence 4
        c4 = get_regime_tier_capacities(4)
        self.assertEqual(c4["HIGH_RISK"], 5)
        self.assertEqual(c4["BALANCED"], 5)
        self.assertEqual(c4["CORE"], 5)
        self.assertIn("BROAD EXPANSION", c4["regime"])

        # Confluence 3
        c3 = get_regime_tier_capacities(3)
        self.assertEqual(c3["HIGH_RISK"], 3)
        self.assertEqual(c3["BALANCED"], 5)
        self.assertEqual(c3["CORE"], 5)

        # Confluence 2
        c2 = get_regime_tier_capacities(2)
        self.assertEqual(c2["HIGH_RISK"], 1)
        self.assertEqual(c2["BALANCED"], 3)
        self.assertEqual(c2["CORE"], 4)

        # Confluence 1
        c1 = get_regime_tier_capacities(1)
        self.assertEqual(c1["HIGH_RISK"], 0)
        self.assertEqual(c1["BALANCED"], 1)
        self.assertEqual(c1["CORE"], 2)

        # Confluence 0
        c0 = get_regime_tier_capacities(0)
        self.assertEqual(c0["HIGH_RISK"], 0)
        self.assertEqual(c0["BALANCED"], 0)
        self.assertEqual(c0["CORE"], 0)
        self.assertIn("SYSTEMIC LIQUIDATION", c0["regime"])

    def test_regime_tier_throttling_in_defensive_market(self):
        # When Confluence is 1 (Defensive/Chop), HIGH_RISK capacity is 0 -> incoming high-risk sprint is throttled
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = os.path.join(tmpdir, "stock_trades_log.json")
            with open(tmp_log, "w") as f:
                json.dump({"summary": {}, "trades": []}, f)

            new_recs = [
                {
                    "ticker": "PLTR",
                    "price": 30.0,
                    "stop": 28.0,
                    "tp1": 35.0,
                    "tp2": 40.0,
                    "rr_ratio": 2.5,
                    "sector": "TECHNOLOGY",
                    "strategy_prong": "HIGH_RISK",
                    "alpha_score": 85.0
                }
            ]
            market_bars = {"PLTR": {"Close": 30.0, "Open": 29.5, "High": 30.5, "Low": 29.0, "EMA50": 28.5}}

            res = update_stock_trades_log(
                new_recommendations=new_recs,
                current_market_bars=market_bars,
                today_str="2026-09-12",
                log_path=tmp_log,
                confluence_score=1 # Defensive regime: HIGH_RISK cap = 0
            )

            # Trade should be throttled because HIGH_RISK cap is 0
            self.assertEqual(len(res["trades"]), 0)

    def test_strict_breakeven_accounting_equities(self):
        # Ledger with 1 Winner (+40%), 1 Loser (-10%), and 2 Breakevens (0.00%)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = os.path.join(tmpdir, "stock_trades_log.json")
            trades = [
                {"id": "T1", "ticker": "WIN", "status": "TP2_HIT", "entry_price": 100.0, "current_price": 140.0, "pnl_pct": 40.0, "capital_deployed": 1000.0, "days_active": 10},
                {"id": "T2", "ticker": "LOSS", "status": "STOPPED_OUT", "entry_price": 100.0, "current_price": 90.0, "pnl_pct": -10.0, "capital_deployed": 1000.0, "days_active": 5},
                {"id": "T3", "ticker": "BE1", "status": "CLOSED_BREAKEVEN", "entry_price": 100.0, "current_price": 100.0, "pnl_pct": 0.0, "capital_deployed": 1000.0, "days_active": 12},
                {"id": "T4", "ticker": "BE2", "status": "CLOSED_BREAKEVEN", "entry_price": 50.0, "current_price": 50.0, "pnl_pct": 0.0, "capital_deployed": 1000.0, "days_active": 8},
            ]
            with open(tmp_log, "w") as f:
                json.dump({"summary": {}, "trades": trades}, f)

            res = update_stock_trades_log(
                new_recommendations=[],
                current_market_bars={},
                today_str="2026-09-12",
                log_path=tmp_log
            )

            summary = res["summary"]
            self.assertEqual(summary["closed_trades"], 4)
            self.assertEqual(summary["breakeven_trades"], 2)
            self.assertEqual(summary["win_rate_pct"], 25.0) # 1 / 4
            self.assertEqual(summary["decisive_win_rate_pct"], 50.0) # 1 / (1 + 1)
            self.assertEqual(summary["avg_winner_pct"], 40.0) # Undiluted by 0% breakevens!
            self.assertEqual(summary["avg_loser_pct"], -10.0)
            self.assertEqual(summary["profit_factor"], 4.0) # $400 / $100

    def test_strict_breakeven_accounting_options(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_log = os.path.join(tmpdir, "trades_log.json")
            trades = [
                {"id": "O1", "ticker": "WIN", "status": "TP2_HIT", "entry_price": 5.0, "current_price": 8.0, "pnl_pct": 60.0, "days_active": 15},
                {"id": "O2", "ticker": "LOSS", "status": "STOPPED_OUT", "entry_price": 5.0, "current_price": 4.0, "pnl_pct": -20.0, "days_active": 6},
                {"id": "O3", "ticker": "BE", "status": "CLOSED_BREAKEVEN", "entry_price": 5.0, "current_price": 5.0, "pnl_pct": 0.0, "days_active": 18},
            ]
            with open(tmp_log, "w") as f:
                json.dump({"summary": {}, "trades": trades}, f)

            dates = pd.date_range("2026-08-01", periods=60, freq="B")
            data = {}
            for t in ["SPY"]:
                for col in ["Open", "High", "Low", "Close"]:
                    data[(col, t)] = [100.0] * len(dates)
                data[("Volume", t)] = [1000000] * len(dates)
            mock_df = pd.DataFrame(data, index=dates)
            mock_df.columns = pd.MultiIndex.from_tuples(mock_df.columns)

            orig_dir = scanner.DATA_DIR
            try:
                scanner.DATA_DIR = tmpdir
                res = scanner.audit_and_update_trades(mock_df, [], "2026-09-12")
                summary = res["summary"]
                self.assertEqual(summary["closed_trades"], 3)
                self.assertEqual(summary["breakeven_trades"], 1)
                self.assertEqual(summary["win_rate_pct"], 33.3) # 1 / 3
                self.assertEqual(summary["decisive_win_rate_pct"], 50.0) # 1 / 2
                self.assertEqual(summary["avg_winner_pct"], 60.0) # Undiluted by 0% breakevens!
                self.assertEqual(summary["avg_loser_pct"], -20.0)
                self.assertEqual(summary["profit_factor"], 3.0) # 60 / 20
            finally:
                scanner.DATA_DIR = orig_dir

if __name__ == "__main__":
    unittest.main()
