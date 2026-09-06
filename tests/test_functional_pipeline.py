import os
import sys
import unittest
import json
import pandas as pd
import numpy as np

ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine")
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

sys.path.append(ENGINE_DIR)
import scanner
import universe

class TestFunctionalPipeline(unittest.TestCase):
    def setUp(self):
        # Create a simulated universe dataset for 30 sample tickers across all sectors
        np.random.seed(101)
        dates = pd.date_range("2026-03-01", "2026-09-04", freq="B")
        
        sample_tickers = [
            "SPY", "QQQ", "GDX", "IBB", "XLE", "IGV", "XBI", "XME", "XLV", "XLK", "XLF",
            "AAPL", "NVDA", "MSFT", "AMZN", "GOOGL", "META", "DOCU", "RKT", "MS", "PNC",
            "FISV", "CRCL", "GRAL", "CEG", "XOM", "DVN", "JPM", "DELL", "HSAI"
        ]
        
        tuples = []
        for t in sample_tickers:
            for field in ["Open", "High", "Low", "Close", "Volume"]:
                tuples.append((t, field))
                
        cols = pd.MultiIndex.from_tuples(tuples, names=["Ticker", "Field"])
        
        data_matrix = np.zeros((len(dates), len(tuples)))
        idx = 0
        for t in sample_tickers:
            base_price = 100.0 if not t.startswith("X") and t != "SPY" and t != "QQQ" else 200.0
            ret = np.random.normal(0.0004, 0.018, size=len(dates))
            close = base_price * np.cumprod(1 + ret)
            high = close * 1.01
            low = close * 0.99
            open_p = (high + low) / 2
            vol = np.random.randint(10000, 1000000, size=len(dates))
            
            data_matrix[:, idx] = open_p
            data_matrix[:, idx+1] = high
            data_matrix[:, idx+2] = low
            data_matrix[:, idx+3] = close
            data_matrix[:, idx+4] = vol
            idx += 5
            
        self.raw_data = pd.DataFrame(data_matrix, index=dates, columns=cols)

    def test_end_to_end_process_universe(self):
        payload = scanner.process_universe(self.raw_data, sample_date_str="2026-09-04")
        self.assertIsNotNone(payload)
        
        # 1. Macro breadth validation
        m = payload["macro_breadth"]
        self.assertEqual(m["date"], "2026-09-04")
        self.assertGreater(m["total_alerts"], 0)
        self.assertIn("regime", m)
        self.assertIsInstance(m["macro_ratio"], float)
        
        # 2. Candidates validation
        cands = payload["top_candidates"]
        self.assertLessEqual(len(cands), 5)
        for c in cands:
            self.assertIn("ticker", c)
            self.assertIn("stop", c)
            self.assertIn("tp1", c)
            self.assertIn("tp2", c)
            self.assertLess(c["stop"], c["price"])
            self.assertGreater(c["tp1"], c["price"])
            self.assertTrue(c["overhead_clearance_ok"])
            
        # 3. All 25 ETFs validation
        etfs = payload["all_25_etfs"]
        self.assertGreater(len(etfs), 0)
        for e in etfs:
            self.assertIsInstance(e["pct"], (int, float))
            self.assertIn(e["style"], ["Growth", "Cyclical", "Defensive"])

        # 4. Sector strength validation
        sec_str = payload["sector_strength"]
        self.assertGreater(len(sec_str), 0)
        sectors_seen = set()
        for s in sec_str:
            self.assertNotIn(s["sector"], sectors_seen, "No duplicate sectors in sector strength")
            sectors_seen.add(s["sector"])
            self.assertIn("/10", s["display"])
            
        # 5. Top Sub-Sectors validation
        subs = payload["top_subsectors"]
        self.assertGreater(len(subs), 0)
        for sub in subs:
            self.assertIn("subsector", sub)
            self.assertIn("win", sub)
            self.assertIn("ret", sub)
            self.assertFalse(sub["ret"] == "+0.00%" and sub["win"] == "0%")

        # 6. JSON serializability
        dumped = json.dumps(payload)
        self.assertGreater(len(dumped), 1000)

if __name__ == "__main__":
    unittest.main(verbosity=2)
