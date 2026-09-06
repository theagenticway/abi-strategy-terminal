import os
import sys
import unittest
import json
import re
import pandas as pd
import numpy as np

# Add engine to path
ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.append(ENGINE_DIR)
import indicators
import patterns
import universe
import scanner

class TestIndicators(unittest.TestCase):
    def setUp(self):
        # Generate synthetic price series (250 bars)
        np.random.seed(42)
        dates = pd.date_range("2026-01-01", periods=250, freq="B")
        returns = np.random.normal(0.0005, 0.015, size=250)
        close = 100 * np.cumprod(1 + returns)
        high = close * (1 + np.abs(np.random.normal(0, 0.008, size=250)))
        low = close * (1 - np.abs(np.random.normal(0, 0.008, size=250)))
        open_p = (high + low) / 2
        volume = np.random.randint(100000, 5000000, size=250)
        
        self.df = pd.DataFrame({
            "Open": open_p, "High": high, "Low": low, "Close": close, "Volume": volume
        }, index=dates)
        
        # Benchmark SPY returns
        spy_ret = np.random.normal(0.0003, 0.010, size=250)
        self.spy_returns = pd.Series(spy_ret, index=dates)

    def test_ema_calculation(self):
        ema50 = indicators.calculate_ema(self.df["Close"], 50)
        self.assertEqual(len(ema50), len(self.df))
        self.assertFalse(np.isnan(ema50.iloc[-1]))
        self.assertGreater(ema50.iloc[-1], 0)

    def test_sma_calculation(self):
        sma150 = indicators.calculate_sma(self.df["Close"], 150)
        self.assertEqual(len(sma150), len(self.df))
        self.assertTrue(np.isnan(sma150.iloc[50]))
        self.assertFalse(np.isnan(sma150.iloc[-1]))

    def test_rsi_calculation(self):
        rsi = indicators.calculate_rsi(self.df["Close"], 14)
        self.assertEqual(len(rsi), len(self.df))
        last_rsi = rsi.iloc[-1]
        self.assertGreaterEqual(last_rsi, 0.0)
        self.assertLessEqual(last_rsi, 100.0)

    def test_macd_calculation(self):
        line, signal, hist = indicators.calculate_macd(self.df["Close"], 12, 26, 9)
        self.assertEqual(len(hist), len(self.df))
        self.assertFalse(np.isnan(hist.iloc[-1]))

    def test_adr_and_beta(self):
        adr = indicators.calculate_adr_pct(self.df["High"], self.df["Low"], self.df["Close"], 20)
        self.assertGreater(adr, 0.0)
        
        ret = self.df["Close"].pct_change()
        beta = indicators.calculate_beta(ret, self.spy_returns)
        self.assertIsInstance(beta, float)

    def test_technical_snapshot(self):
        snap = indicators.compute_technical_snapshot(self.df, self.spy_returns)
        self.assertIsNotNone(snap)
        self.assertIn("price", snap)
        self.assertIn("ema50", snap)
        self.assertIn("sma150", snap)
        self.assertIn("ema200", snap)
        self.assertIn("overhead_runway_pct", snap)
        self.assertIn("overhead_clearance_ok", snap)
        self.assertIn("raw_sma150", snap)
        self.assertIsInstance(snap["overhead_clearance_ok"], bool)

class TestPatterns(unittest.TestCase):
    def setUp(self):
        self.close = pd.Series([100.0, 101.0, 102.0, 103.0, 105.0])
        self.high = pd.Series([101.0, 102.0, 103.0, 104.0, 106.0])
        self.low = pd.Series([99.0, 100.0, 101.0, 102.0, 104.0])
        self.ema50 = pd.Series([98.0, 99.0, 100.0, 101.0, 103.0])
        self.sma150_float = 95.0
        self.sma150_series = pd.Series([93.0, 93.5, 94.0, 94.5, 95.0])

    def test_retrace_detection_with_float_sma(self):
        # Must not raise AttributeError: 'float' object has no attribute 'iloc'
        retrace, lvl = patterns.detect_retrace_pattern(
            self.close, self.high, self.low, self.ema50, self.sma150_float
        )
        self.assertIn(retrace, ["EMA50", "DB", "OTE", "MA150"])
        self.assertGreater(lvl, 0.0)

    def test_retrace_detection_with_series_sma(self):
        retrace, lvl = patterns.detect_retrace_pattern(
            self.close, self.high, self.low, self.ema50, self.sma150_series
        )
        self.assertIn(retrace, ["EMA50", "DB", "OTE", "MA150"])

    def test_reclaim_velocity(self):
        days, is_confirmed, state = patterns.calculate_reclaim_velocity(self.close, self.ema50)
        self.assertIsInstance(days, int)
        self.assertIsInstance(is_confirmed, bool)
        self.assertIn(state, ["BOUNCED", "ABOVE", "BELOW"])

    def test_trade_signal_structuring(self):
        snap = {
            "price": 100.0, "ema50": 98.0, "beta": 1.2,
            "ema50_dist_pct": 2.04, "overhead_runway_pct": 8.5,
            "overhead_clearance_ok": True
        }
        sig = patterns.structure_trade_signal("AAPL", "TECH CORE", snap, "EMA50", 1, "MIXED")
        self.assertEqual(sig["action"], "BUY")
        self.assertEqual(sig["ticker"], "AAPL")
        self.assertLess(sig["stop"], sig["price"])
        self.assertGreater(sig["tp1"], sig["price"])
        self.assertGreater(sig["tp2"], sig["tp1"])
        self.assertTrue(sig["rr_ratio"].startswith("1:"))
        self.assertEqual(sig["structure"], "Bull Call Spread (45-60 DTE)")

class TestUniverse(unittest.TestCase):
    def test_all_25_etfs_present(self):
        expected_25 = [
            "GDX", "IBB", "XLE", "IGV", "XBI", "XME", "XLV", "XLK", "XLF", "IHAK",
            "QQQ", "KRE", "XLB", "XLC", "SMH", "XRT", "XLP", "XLY", "XLRE", "IYT",
            "XLU", "XLI", "ITB", "JETS", "TAN"
        ]
        for etf in expected_25:
            self.assertIn(etf, universe.SECTOR_ETFS, f"Missing ETF {etf}")
        self.assertEqual(len(universe.SECTOR_ETFS), 25)

    def test_universe_ticker_count(self):
        all_u = universe.get_full_universe()
        self.assertGreaterEqual(len(all_u), 450, "Universe must cover 450+ stocks")

class TestDataIntegrity(unittest.TestCase):
    def setUp(self):
        latest_path = os.path.join(DATA_DIR, "latest.json")
        self.assertTrue(os.path.exists(latest_path), "data/latest.json must exist")
        with open(latest_path, "r") as f:
            self.data = json.load(f)

    def test_all_15_required_keys_present(self):
        required_keys = [
            "macro_breadth", "top_candidates", "all_qualified", "sector_momentum",
            "tickers", "all_25_etfs", "sector_strength", "rotating_in", "top_subsectors",
            "all_subsectors", "reclaims_by_sector", "bounces_by_sector", "bounces_by_level",
            "fast_reclaims", "daily_activity"
        ]
        for k in required_keys:
            self.assertIn(k, self.data, f"Missing required payload key: {k}")

    def test_sector_strength_cleanliness(self):
        strength_list = self.data.get("sector_strength", [])
        self.assertGreater(len(strength_list), 15, "Sector strength must have 15+ sectors")
        sectors_seen = set()
        for item in strength_list:
            # Check for no duplicates
            sec = item["sector"]
            self.assertNotIn(sec, sectors_seen, f"Duplicate sector found: {sec}")
            sectors_seen.add(sec)
            # Check display field
            disp = item.get("display") or item.get("strength_str")
            self.assertIsNotNone(disp)
            self.assertFalse(disp == "undefined", f"Sector {sec} has 'undefined' display")

    def test_all_25_etfs_data(self):
        etfs = self.data.get("all_25_etfs", [])
        self.assertEqual(len(etfs), 25, "all_25_etfs must have exactly 25 items")
        for e in etfs:
            self.assertIn(e["style"], ["Growth", "Cyclical", "Defensive"])
            self.assertIsInstance(e["pct"], (int, float))

    def test_top_candidates_runway_and_clearance(self):
        cands = self.data.get("top_candidates", [])
        self.assertLessEqual(len(cands), 5)
        for c in cands:
            runway = c.get("overhead_runway_pct")
            # Runway must not be a buggy 0% or negative below 200MA
            self.assertIsNotNone(runway)
            self.assertNotEqual(str(runway), "0%")

    def test_nojekyll_file_exists(self):
        nojekyll_path = os.path.join(ROOT_DIR, ".nojekyll")
        self.assertTrue(os.path.exists(nojekyll_path), ".nojekyll file must exist in repo root to prevent 404s on GitHub Pages")

class TestFrontendLogic(unittest.TestCase):
    def setUp(self):
        index_path = os.path.join(ROOT_DIR, "index.html")
        self.assertTrue(os.path.exists(index_path))
        with open(index_path, "r") as f:
            self.html = f.read()

    def test_parse_pct_logic(self):
        # Simulate the JavaScript parsePct regex
        def parse_pct_py(s):
            if isinstance(s, (int, float)):
                return float(s)
            if not s:
                return 0.0
            clean = re.sub(r'[\\%+\s]', '', str(s)).replace('−', '-')
            try:
                val = float(clean)
                return 0.0 if np.isnan(val) else val
            except:
                return 0.0

        self.assertEqual(parse_pct_py(r"\-0.50%"), -0.50)
        self.assertEqual(parse_pct_py("+10.86%"), 10.86)
        self.assertEqual(parse_pct_py(r"\-4.61%"), -4.61)
        self.assertEqual(parse_pct_py("−3.73%"), -3.73)
        self.assertEqual(parse_pct_py(None), 0.0)
        self.assertEqual(parse_pct_py(""), 0.0)

    def test_essential_dom_elements_present(self):
        expected_ids = [
            "tab-recs-btn", "tab-macro-btn", "tab-recs", "tab-macro",
            "macro-sectors-count", "macro-hot-count", "macro-alerts-count", "macro-winrate",
            "macro-reclaims-count", "macro-bounces-count",
            "macro-regime-title", "macro-regime-counts", "offense-label", "defense-slider-bar", "offense-subtext",
            "seg-outperforming", "seg-gaining", "seg-weakening", "seg-underperforming",
            "macro-growth-breadth", "macro-growth-avg", "macro-cyclical-breadth", "macro-cyclical-avg",
            "macro-defensive-breadth", "macro-defensive-avg",
            "quadrantCanvas", "regime-change-cards-container", "regime-detail-body",
            "ladder-container", "sector-strength-container", "rotating-in-cards",
            "top-subsectors-body", "reclaims-by-sector-container",
            "reclaim-detail-body", "bounces-by-level-container", "bounces-by-sector-container",
            "bounce-alerts-body", "fast-reclaims-body", "daily-activity-rows",
            "candidates-body", "tickers-body", "active-filter-banner"
        ]
        for dom_id in expected_ids:
            self.assertIn(f'id="{dom_id}"', self.html, f"Missing essential DOM ID in index.html: {dom_id}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
