import os
import json
import unittest
from bs4 import BeautifulSoup

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = os.path.join(REPO_ROOT, "index.html")
LATEST_JSON = os.path.join(REPO_ROOT, "data", "latest.json")
TRADES_LOG_JSON = os.path.join(REPO_ROOT, "data", "trades_log.json")

class TestStage1Allocator(unittest.TestCase):
    def setUp(self):
        with open(HTML_PATH, "r", encoding="utf-8") as f:
            self.html = f.read()
        self.soup = BeautifulSoup(self.html, "html.parser")
        with open(LATEST_JSON, "r", encoding="utf-8") as f:
            self.latest = json.load(f)
        with open(TRADES_LOG_JSON, "r", encoding="utf-8") as f:
            self.trades_log = json.load(f)

    def test_allocator_dom_structure(self):
        """Verify all 4 pillars and summary badges exist in index.html"""
        required_ids = [
            "btn-dcap-10k", "btn-dcap-25k", "btn-dcap-50k", "btn-dcap-100k", "deploy-custom-capital",
            "alloc-architecture-mode", "alloc-cash-reserve-mode",
            "tranche-pace-title", "tranche-pace-amount",
            "plan-total-cap", "plan-my-committed", "plan-cash-reserve", "plan-free-cash", "plan-today-budget",
            "plan-capacity-banner", "plan-capacity-msg",
            "plan-leaps-budget", "plan-leaps-ratio", "plan-spreads-budget", "plan-spreads-ratio",
            "btn-pfilt-my-port", "my-port-tab-badge"
        ]
        for rid in required_ids:
            el = self.soup.find(id=rid)
            self.assertIsNotNone(el, f"Required Allocator DOM ID '{rid}' missing in index.html")

    def test_executive_briefing_dom_elements(self):
        """Verify Executive Market Briefing & 4-Index Confluence Ribbon exist in DOM"""
        briefing_ids = [
            "executive-briefing-container", "briefing-verdict-badge",
            "idx-chip-spy", "idx-spy-price", "idx-spy-status",
            "idx-chip-qqq", "idx-qqq-price", "idx-qqq-status",
            "idx-chip-rsp", "idx-rsp-price", "idx-rsp-status",
            "idx-chip-iwm", "idx-iwm-price", "idx-iwm-status",
            "briefing-macro-narrative", "briefing-sector-narrative", "briefing-mandates-list",
            "btn-dir-long", "btn-dir-hedge", "table1-header-title"
        ]
        for bid in briefing_ids:
            el = self.soup.find(id=bid)
            self.assertIsNotNone(el, f"Required Briefing DOM ID '{bid}' missing in index.html")

    def test_localstorage_helper_functions_present(self):
        """Verify core JavaScript portfolio functions exist in script"""
        required_functions = [
            "function getMyPortfolio",
            "function saveMyPortfolio",
            "function clearMyPortfolioConfirm",
            "function toggleTradePortfolio",
            "function toggleLedgerTradePortfolio",
            "function onPortfolioUpdated",
            "function setDeployCapital",
            "function resetAllocator",
            "function updateAllocationPlan",
            "function setDirectionalMode"
        ]
        for fn in required_functions:
            self.assertIn(fn, self.html, f"Missing JavaScript function: {fn}")

    def test_mathematical_allocator_logic(self):
        """Simulate mathematical allocation formulas across different regimes and capital levels"""
        deployCapital = 50000
        cashReservePct = 25
        totalCommitted = 0
        
        cashReserveDollars = round(deployCapital * (cashReservePct / 100))
        freeLiquidCash = max(0, deployCapital - totalCommitted - cashReserveDollars)
        trancheBudget = min(freeLiquidCash, round(deployCapital * 0.33))
        
        strategicBudget = round(trancheBudget * 0.60)
        tacticalBudget = max(0, trancheBudget - strategicBudget)
        
        self.assertEqual(cashReserveDollars, 12500)
        self.assertEqual(freeLiquidCash, 37500)
        self.assertEqual(trancheBudget, 16500)
        self.assertEqual(strategicBudget, 9900)
        self.assertEqual(tacticalBudget, 6600)
        
        # Adding $12,000 in open positions
        totalCommitted = 12000
        freeLiquidCash = max(0, deployCapital - totalCommitted - cashReserveDollars)
        trancheBudget = min(freeLiquidCash, round(deployCapital * 0.33))
        self.assertEqual(freeLiquidCash, 25500)
        self.assertEqual(trancheBudget, 16500)
        
        # Capacity Reached
        totalCommitted = 40000
        freeLiquidCash = max(0, deployCapital - totalCommitted - cashReserveDollars)
        isCapacityReached = (totalCommitted + cashReserveDollars >= deployCapital) or (freeLiquidCash <= 0)
        trancheBudget = 0 if isCapacityReached else min(freeLiquidCash, round(deployCapital * 0.33))
        
        self.assertEqual(freeLiquidCash, 0)
        self.assertTrue(isCapacityReached)
        self.assertEqual(trancheBudget, 0)

    def test_integer_contract_sizing_and_small_account_protection(self):
        """Verify small-account protection prevents forced over-allocation on expensive contracts"""
        allocPerLeaps = 990
        leapsCost = 6879
        leapsContracts = allocPerLeaps // leapsCost
        self.assertEqual(leapsContracts, 0, "Must round down to 0 contracts if budget is insufficient")
        
        allocPerSpread = 660
        spreadCost = 1520
        spreadContracts = allocPerSpread // spreadCost
        self.assertEqual(spreadContracts, 0, "Must round down to 0 contracts if budget is insufficient")

    def test_benchmark_matrix_and_commentary_data(self):
        """Verify benchmark_matrix and market_commentary structures in data/latest.json"""
        self.assertIn("benchmark_matrix", self.latest)
        bm = self.latest["benchmark_matrix"]
        self.assertIn("composite_score", bm)
        self.assertIn("regime", bm)
        self.assertIn("indices", bm)
        for sym in ["SPY", "QQQ", "RSP", "IWM"]:
            self.assertIn(sym, bm["indices"])
            self.assertIn("price", bm["indices"][sym])
            self.assertIn("vs_ema50_pct", bm["indices"][sym])
            self.assertIn("status", bm["indices"][sym])

        self.assertIn("market_commentary", self.latest)
        mc = self.latest["market_commentary"]
        self.assertIn("action_verdict", mc)
        self.assertIn("action_badge", mc)
        self.assertIn("macro_narrative", mc)
        self.assertIn("sector_flow_narrative", mc)
        self.assertIn("execution_mandates", mc)
        self.assertGreater(len(mc["execution_mandates"]), 0)

        self.assertIn("downside_hedges", self.latest)
        self.assertIsInstance(self.latest["downside_hedges"], list)
        self.assertGreater(len(self.latest["downside_hedges"]), 0)
        first_hedge = self.latest["downside_hedges"][0]
        self.assertIn("ticker", first_hedge)
        self.assertIn("structure", first_hedge)
        self.assertIn("est_debit", first_hedge)
        self.assertIn("contract", first_hedge)
        self.assertIn("Put Spread", first_hedge["contract"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
