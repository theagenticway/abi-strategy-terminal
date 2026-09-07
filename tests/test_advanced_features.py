import os
import sys
import unittest
import datetime

ENGINE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine")
sys.path.append(ENGINE_DIR)

import patterns
import scanner

class TestAdvancedAlphaRadarFeatures(unittest.TestCase):
    def setUp(self):
        self.today = datetime.date(2026, 9, 6)

    def test_options_strike_modeling_vertical(self):
        # Stock at $174.33, TP1 at $222.38, D2 velocity
        ticket = patterns.model_options_contract("PLTR", 174.33, 222.38, reclaim_days=2, today=self.today)
        self.assertEqual(ticket["vehicle"], "Bull Call Spread")
        self.assertLessEqual(ticket["long_strike"], 174.33, "Long strike must be at or below share price")
        self.assertGreaterEqual(ticket["short_strike"], 222.38, "Short strike must be at or above TP1")
        self.assertGreater(ticket["width"], 0)
        self.assertGreater(ticket["est_debit"], 0)
        self.assertGreater(ticket["max_profit"], 0)
        self.assertEqual(ticket["width"], round(ticket["est_debit"] + ticket["max_profit"], 2))
        self.assertTrue(45 <= ticket["dte"] <= 65, f"DTE must be in 45-65 range, got {ticket['dte']}")
        self.assertIn("Call Spread", ticket["contract"])

    def test_options_strike_modeling_leaps(self):
        # Stock at $499.70, D4 velocity -> LEAPS
        ticket = patterns.model_options_contract("MSFT", 499.70, 620.55, reclaim_days=4, today=self.today)
        self.assertEqual(ticket["vehicle"], "Call LEAPS")
        self.assertLess(ticket["long_strike"], 499.70 * 0.85, "LEAPS strike must be deep in the money (~80% price)")
        self.assertIsNone(ticket["short_strike"])
        self.assertGreater(ticket["dte"], 300, "LEAPS DTE must be over 300 days")
        self.assertIn("Call LEAPS", ticket["contract"])

    def test_earnings_blackout_filter(self):
        # 1. Inside 45-day blackout window
        earning_in_18d = self.today + datetime.timedelta(days=18)
        res_blackout = patterns.evaluate_earnings_blackout("DOCU", earning_in_18d, today=self.today)
        self.assertFalse(res_blackout["safe"])
        self.assertIn("BLACKOUT", res_blackout["status"])
        self.assertEqual(res_blackout["badge"], "amber")

        # 2. Outside 45-day window (Safe)
        earning_in_62d = self.today + datetime.timedelta(days=62)
        res_safe = patterns.evaluate_earnings_blackout("MS", earning_in_62d, today=self.today)
        self.assertTrue(res_safe["safe"])
        self.assertIn("SAFE", res_safe["status"])
        self.assertEqual(res_safe["badge"], "emerald")

        # 3. Already passed
        earning_past = self.today - datetime.timedelta(days=12)
        res_past = patterns.evaluate_earnings_blackout("NVDA", earning_past, today=self.today)
        self.assertTrue(res_past["safe"])
        self.assertIn("Passed", res_past["status"])

    def test_loss_attribution_engine(self):
        # 1. Macro contagion test (SPY drops > 1.2%)
        driver_macro = scanner.determine_invalidation_driver("AEHR", "TECH SEMIS", 3, spy_ret=-0.018, sector_ret=-0.010)
        self.assertEqual(driver_macro["driver"], "MACRO CONTAGION")
        self.assertEqual(driver_macro["badge"], "orange")
        self.assertIn("SPY -1.80%", driver_macro["note"])

        # 2. Sector rotation test (Sector ETF drops > 1.2% while SPY is flat)
        driver_sector = scanner.determine_invalidation_driver("INTT", "TECH SOFTWARE", 4, spy_ret=-0.002, sector_ret=-0.021)
        self.assertEqual(driver_sector["driver"], "SECTOR ROTATION")
        self.assertEqual(driver_sector["badge"], "amber")
        self.assertIn("TECH SOFTWARE (-2.10%)", driver_sector["note"])

        # 3. Earnings gap test
        driver_earnings = scanner.determine_invalidation_driver("XYZ", "FINANCIALS", 2, is_earnings_gap=True)
        self.assertEqual(driver_earnings["driver"], "EARNINGS GAP")
        self.assertEqual(driver_earnings["badge"], "rose")

        # 4. Stagnation test (past 7 days)
        driver_stagnation = scanner.determine_invalidation_driver("ABC", "HEALTHCARE", 8, spy_ret=0.005, sector_ret=0.004)
        self.assertEqual(driver_stagnation["driver"], "STAGNATION EXIT")
        self.assertEqual(driver_stagnation["badge"], "slate")

        # 5. Idiosyncratic test (Healthy market and sector, but individual stock fails)
        driver_idiosyncratic = scanner.determine_invalidation_driver("MKTX", "FINANCIALS", 3, spy_ret=0.008, sector_ret=0.015)
        self.assertEqual(driver_idiosyncratic["driver"], "IDIOSYNCRATIC")
        self.assertEqual(driver_idiosyncratic["badge"], "rose")
        self.assertIn("healthy sector", driver_idiosyncratic["note"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
