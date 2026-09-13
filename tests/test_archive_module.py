import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
#!/usr/bin/env python3
"""
Unit test suite for engine/archive.py
Validates signal extraction, same-day upsert idempotency, and 365-day rolling pruning.
"""

import unittest
import os
import json
import tempfile
import datetime
from engine import archive

class TestArchiveModule(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.archive_path = os.path.join(self.temp_dir.name, "recommendations_archive.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_and_save_signals(self):
        payload = {
            "top_candidates": [
                {
                    "ticker": "NVDA",
                    "company_name": "NVIDIA Corporation",
                    "sector": "Semiconductors",
                    "horizon_tier": "HIGH_RISK_SPRINT",
                    "current_price": 128.50,
                    "options_alpha_score": 88.5,
                    "ema50": 124.20,
                    "rsi": 54.2,
                    "macd_hist": 0.45,
                    "rvol": 2.1,
                    "retrace_type": "EMA50",
                    "reclaim_days": 1,
                    "market_structure": "BULLISH_HH_HL",
                    "expiry": "2026-11-20",
                    "dte": 69,
                    "long_strike": 125.0,
                    "short_strike": 135.0,
                    "net_debit": 3.80,
                    "stop_loss": 118.20,
                    "tp1": 138.00,
                    "tp2": 145.00
                }
            ],
            "strategic_leaps": [
                {
                    "ticker": "MSFT",
                    "company_name": "Microsoft Corporation",
                    "sector": "Software",
                    "current_price": 450.00,
                    "options_alpha_score": 92.0,
                    "ema50": 435.0,
                    "expiry": "2028-01-21",
                    "dte": 490,
                    "strike": 400.0,
                    "ask": 85.0
                }
            ],
            "downside_hedges": [
                {
                    "ticker": "XOM",
                    "company_name": "Exxon Mobil Corp",
                    "sector": "Energy",
                    "current_price": 110.0,
                    "options_alpha_score": 75.0,
                    "market_structure": "BEARISH_LH_LL",
                    "expiry": "2026-10-16",
                    "long_strike": 112.0,
                    "short_strike": 105.0,
                    "net_debit": 2.50
                }
            ],
            "stock_recommendations": [
                {
                    "ticker": "AAPL",
                    "company_name": "Apple Inc.",
                    "sector": "Technology",
                    "horizon_tier": "BALANCED_SWING",
                    "entry_price": 220.0,
                    "alpha_composite_score": 86.0,
                    "stop_price": 208.0,
                    "tp1": 235.0,
                    "tp2": 245.0,
                    "shares_recommended": 40
                }
            ],
            "core_stocks": [
                {
                    "ticker": "GOOGL",
                    "company_name": "Alphabet Inc.",
                    "sector": "Communication Services",
                    "horizon_tier": "CORE_ACCUMULATION",
                    "entry_price": 175.0,
                    "alpha_composite_score": 84.0,
                    "stop_price": 160.0,
                    "tp1": 195.0,
                    "tp2": 210.0,
                    "shares_recommended": 50
                }
            ]
        }
        
        signals = archive.extract_signal_records(payload, "2026-09-12")
        self.assertEqual(len(signals), 5)
        
        # Verify NVDA Sprint mapped properly
        nvda = next(s for s in signals if s["ticker"] == "NVDA")
        self.assertEqual(nvda["category"], "HIGH_RISK_SPRINT")
        self.assertEqual(nvda["asset_type"], "OPTION")
        self.assertEqual(nvda["structure"]["strategy"], "Bull Call Spread")
        self.assertEqual(nvda["structure"]["long_strike"], 125.0)

        # Verify MSFT Core LEAPS mapped properly
        msft = next(s for s in signals if s["ticker"] == "MSFT")
        self.assertEqual(msft["category"], "CORE_ACCUMULATION")
        self.assertEqual(msft["structure"]["strategy"], "Deep-ITM Call LEAPS")

        # Verify XOM Hedge mapped properly
        xom = next(s for s in signals if s["ticker"] == "XOM")
        self.assertEqual(xom["category"], "DOWNSIDE_HEDGE")
        self.assertEqual(xom["structure"]["strategy"], "Bear Put Spread")

        # Verify AAPL Equity mapped properly
        aapl = next(s for s in signals if s["ticker"] == "AAPL")
        self.assertEqual(aapl["asset_type"], "EQUITY")
        self.assertEqual(aapl["category"], "BALANCED_SWING")
        self.assertEqual(aapl["structure"]["shares"], 40)

        # Write to archive
        upserted, total = archive.update_recommendations_archive(payload, "2026-09-12", archive_path=self.archive_path)
        self.assertEqual(upserted, 5)
        self.assertEqual(total, 5)
        self.assertTrue(os.path.exists(self.archive_path))

    def test_idempotent_intraday_upsert(self):
        """Simulate cron running at 11:00 AM and 2:00 PM on same day."""
        payload_11am = {
            "top_candidates": [{
                "ticker": "NVDA",
                "current_price": 128.0,
                "options_alpha_score": 87.0
            }]
        }
        archive.update_recommendations_archive(payload_11am, "2026-09-12", archive_path=self.archive_path)
        
        with open(self.archive_path) as f:
            records = json.load(f)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["entry_price"], 128.0)

        # 2:00 PM update with newer price
        payload_2pm = {
            "top_candidates": [{
                "ticker": "NVDA",
                "current_price": 129.5,
                "options_alpha_score": 89.0
            }]
        }
        archive.update_recommendations_archive(payload_2pm, "2026-09-12", archive_path=self.archive_path)

        with open(self.archive_path) as f:
            records = json.load(f)
        # Should still have exactly 1 record, updated in place
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["entry_price"], 129.5)
        self.assertEqual(records[0]["alpha_score"], 89.0)

    def test_auto_prune_beyond_365_days(self):
        """Pre-populate archive with old records and verify >365d records are pruned."""
        today = datetime.datetime.strptime("2026-09-12", "%Y-%m-%d")
        day_100_ago = (today - datetime.timedelta(days=100)).strftime("%Y-%m-%d")
        day_360_ago = (today - datetime.timedelta(days=360)).strftime("%Y-%m-%d")
        day_366_ago = (today - datetime.timedelta(days=366)).strftime("%Y-%m-%d")
        day_400_ago = (today - datetime.timedelta(days=400)).strftime("%Y-%m-%d")

        seed_data = [
            {"id": f"{day_100_ago}_AAPL_BALANCED_BCS", "date": day_100_ago, "ticker": "AAPL", "alpha_score": 80.0},
            {"id": f"{day_360_ago}_MSFT_BALANCED_BCS", "date": day_360_ago, "ticker": "MSFT", "alpha_score": 78.0},
            {"id": f"{day_366_ago}_GOOG_BALANCED_BCS", "date": day_366_ago, "ticker": "GOOG", "alpha_score": 75.0},
            {"id": f"{day_400_ago}_AMZN_BALANCED_BCS", "date": day_400_ago, "ticker": "AMZN", "alpha_score": 72.0},
        ]
        with open(self.archive_path, "w") as f:
            json.dump(seed_data, f)

        # Run archive update for today
        new_payload = {
            "top_candidates": [{
                "ticker": "NVDA",
                "current_price": 130.0,
                "options_alpha_score": 90.0
            }]
        }
        archive.update_recommendations_archive(new_payload, "2026-09-12", archive_path=self.archive_path, retention_days=365)

        with open(self.archive_path) as f:
            final_records = json.load(f)

        dates = [r["date"] for r in final_records]
        self.assertIn("2026-09-12", dates)
        self.assertIn(day_100_ago, dates)
        self.assertIn(day_360_ago, dates)
        # Verify 366d and 400d were pruned!
        self.assertNotIn(day_366_ago, dates)
        self.assertNotIn(day_400_ago, dates)
        self.assertEqual(len(final_records), 3)

if __name__ == "__main__":
    unittest.main()
