"""
Unit tests for engine/radar.py streak computation and radar candidate building.
"""

from datetime import datetime
import unittest

from engine.radar import build_high_risk_radars, compute_radar_streak


class TestRadarModule(unittest.TestCase):

    def test_compute_radar_streak_no_archive(self):
        streak = compute_radar_streak("NVDA", "EQUITY", [], "2026-04-10")
        self.assertEqual(streak, 0)

    def test_compute_radar_streak_consecutive_days(self):
        archive = [
            {
                "date": "2026-04-09",
                "ticker": "NVDA",
                "is_radar": True,
                "asset_type": "EQUITY",
            },
            {
                "date": "2026-04-08",
                "ticker": "NVDA",
                "is_radar": True,
                "asset_type": "EQUITY",
            },
            {
                "date": "2026-04-07",
                "ticker": "NVDA",
                "is_radar": True,
                "asset_type": "EQUITY",
            },
            # Gap on 2026-04-06 (Scan occurred, but NVDA was not on radar)
            {
                "date": "2026-04-06",
                "ticker": "AAPL",
                "is_radar": True,
                "asset_type": "EQUITY",
            },
            {
                "date": "2026-04-05",
                "ticker": "NVDA",
                "is_radar": True,
                "asset_type": "EQUITY",
            },
        ]
        # Scans on 04-09, 04-08, 04-07 -> streak 3
        streak = compute_radar_streak("NVDA", "EQUITY", archive, "2026-04-10")
        self.assertEqual(streak, 3)

    def test_compute_radar_streak_gap_stops_walk(self):
        archive = [
            # Ticker missing on 04-09 (prior scan day had other tickers)
            {
                "date": "2026-04-09",
                "ticker": "AAPL",
                "is_radar": True,
                "asset_type": "EQUITY",
            },
            {
                "date": "2026-04-08",
                "ticker": "NVDA",
                "is_radar": True,
                "asset_type": "EQUITY",
            },
        ]
        streak = compute_radar_streak("NVDA", "EQUITY", archive, "2026-04-10")
        self.assertEqual(streak, 0)

    def test_compute_radar_streak_asset_isolation(self):
        archive = [
            {
                "date": "2026-04-09",
                "ticker": "NVDA",
                "is_radar": True,
                "asset_type": "OPTION",
            },
        ]
        # Option appearance does not count for EQUITY streak
        streak_eq = compute_radar_streak("NVDA", "EQUITY", archive, "2026-04-10")
        self.assertEqual(streak_eq, 0)

        # But counts for OPTION streak
        streak_opt = compute_radar_streak(
            "NVDA", "OPTION", archive, "2026-04-10"
        )
        self.assertEqual(streak_opt, 1)

    def test_build_high_risk_radars_returns_ranked_lists(self):
        ticker_records = [
            {
                "ticker": "MSTR",
                "beta": 2.2,
                "adr_pct": 4.5,
                "price": 150.0,
                "sector": "TECHNOLOGY",
                "subsector": "Crypto/SaaS",
            },
            {
                "ticker": "PLTR",
                "beta": 1.8,
                "adr_pct": 3.6,
                "price": 30.0,
                "sector": "TECHNOLOGY",
                "subsector": "AI Software",
            },
            {
                "ticker": "LOWBETA",
                "beta": 0.8,
                "adr_pct": 1.5,
                "price": 100.0,
                "sector": "UTILITIES",
            },
        ]
        qualified_stocks = [
            {
                "ticker": "MSTR",
                "alpha_score": 92.0,
                "alpha_score_breakdown": {"reclaim_freshness": 20},
            },
            {
                "ticker": "PLTR",
                "alpha_score": 85.0,
                "alpha_score_breakdown": {"reclaim_freshness": 18},
            },
        ]
        qualified_options = [
            {
                "ticker": "MSTR",
                "options_alpha_score": 88.0,
                "iv_rank": 55.0,
                "options_alpha_breakdown": {"directional_foundation": 32},
            },
            {
                "ticker": "PLTR",
                "options_alpha_score": 82.0,
                "iv_rank": 40.0,
                "options_alpha_breakdown": {"directional_foundation": 29},
            },
        ]

        stocks_radar, options_radar = build_high_risk_radars(
            ticker_records=ticker_records,
            qualified_stock_candidates=qualified_stocks,
            qualified_candidates=qualified_options,
            raw_data=None,
            top_quartile_sectors=["TECHNOLOGY"],
            macro_confluence=4,
            sector_mom_map={"TECHNOLOGY": 2.5},
            now_utc=datetime(2026, 4, 10, 16, 0),
            date_str="2026-04-10",
            archive_records=[],
        )

        # LOWBETA must be filtered out
        self.assertEqual(len(stocks_radar), 2)
        self.assertEqual(stocks_radar[0]["ticker"], "MSTR")
        self.assertEqual(stocks_radar[0]["rank"], 1)
        self.assertEqual(stocks_radar[0]["radar_streak_days"], 1)
        self.assertIn("alpha_score_breakdown", stocks_radar[0])

        self.assertEqual(len(options_radar), 2)
        self.assertEqual(options_radar[0]["ticker"], "MSTR")
        self.assertEqual(options_radar[0]["rank"], 1)
        self.assertEqual(options_radar[0]["radar_streak_days"], 1)
        self.assertIn("options_alpha_breakdown", options_radar[0])


if __name__ == "__main__":
    unittest.main()
