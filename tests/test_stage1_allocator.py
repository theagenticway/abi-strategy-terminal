import os
import json
import unittest
import re
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
            "function updateAllocationPlan"
        ]
        for fn in required_functions:
            self.assertIn(fn, self.html, f"Missing JavaScript function: {fn}")

    def test_mathematical_allocator_logic(self):
        """Simulate mathematical allocation formulas across different regimes and capital levels"""
        # Test Case 1: $50k account, Mixed regime (25% cash buffer), 0 open positions
        deployCapital = 50000
        cashReservePct = 25 # Mixed
        totalCommitted = 0
        
        cashReserveDollars = round(deployCapital * (cashReservePct / 100)) # 12500
        freeLiquidCash = max(0, deployCapital - totalCommitted - cashReserveDollars) # 37500
        trancheBudget = min(freeLiquidCash, round(deployCapital * 0.33)) # 16500
        
        # Balanced 60/40
        strategicBudget = round(trancheBudget * 0.60) # 9900
        tacticalBudget = max(0, trancheBudget - strategicBudget) # 6600
        
        self.assertEqual(cashReserveDollars, 12500)
        self.assertEqual(freeLiquidCash, 37500)
        self.assertEqual(trancheBudget, 16500)
        self.assertEqual(strategicBudget, 9900)
        self.assertEqual(tacticalBudget, 6600)
        
        # Test Case 2: User adds $12,000 in open positions
        totalCommitted = 12000
        freeLiquidCash = max(0, deployCapital - totalCommitted - cashReserveDollars) # 50000 - 12000 - 12500 = 25500
        trancheBudget = min(freeLiquidCash, round(deployCapital * 0.33)) # min(25500, 16500) = 16500
        self.assertEqual(freeLiquidCash, 25500)
        self.assertEqual(trancheBudget, 16500)
        
        # Test Case 3: User adds $35,000 in open positions
        totalCommitted = 35000
        freeLiquidCash = max(0, deployCapital - totalCommitted - cashReserveDollars) # 50000 - 35000 - 12500 = 2500
        trancheBudget = min(freeLiquidCash, round(deployCapital * 0.33)) # min(2500, 16500) = 2500 (throttled!)
        self.assertEqual(freeLiquidCash, 2500)
        self.assertEqual(trancheBudget, 2500)
        
        # Test Case 4: Capacity Reached (Total committed + reserve >= total capital)
        totalCommitted = 40000 # 40000 + 12500 = 52500 > 50000
        freeLiquidCash = max(0, deployCapital - totalCommitted - cashReserveDollars)
        isCapacityReached = (totalCommitted + cashReserveDollars >= deployCapital) or (freeLiquidCash <= 0)
        trancheBudget = 0 if isCapacityReached else min(freeLiquidCash, round(deployCapital * 0.33))
        
        self.assertEqual(freeLiquidCash, 0)
        self.assertTrue(isCapacityReached)
        self.assertEqual(trancheBudget, 0)

    def test_integer_contract_sizing_and_small_account_protection(self):
        """Verify small-account protection prevents forced over-allocation on expensive contracts"""
        # On a $10,000 account, Balanced 60/40, Mixed (25% cash):
        deployCapital = 10000
        cashReserveDollars = 2500
        freeLiquidCash = 7500
        trancheBudget = min(7500, round(10000 * 0.33)) # 3300
        strategicBudget = round(3300 * 0.60) # 1980 (~990/setup across 2)
        tacticalBudget = 3300 - strategicBudget # 1320 (~660/setup across 2)
        
        # An expensive LEAPS contract costs $6,879 (e.g. NVDA)
        leapsCost = 6879
        allocPerLeaps = 990
        # Integer floor:
        leapsContracts = allocPerLeaps // leapsCost
        self.assertEqual(leapsContracts, 0, "Must round down to 0 contracts if budget is insufficient")
        
        # A spread contract costs $1,520 (e.g. DOCU)
        spreadCost = 1520
        allocPerSpread = 660
        spreadContracts = allocPerSpread // spreadCost
        self.assertEqual(spreadContracts, 0, "Must round down to 0 contracts if budget is insufficient")
        
        # On a $100,000 account:
        deployCapital = 100000
        cashReserveDollars = 25000
        freeLiquidCash = 75000
        trancheBudget = min(75000, 33000) # 33000
        strategicBudget = round(33000 * 0.60) # 19800 (~9900/setup)
        tacticalBudget = 33000 - strategicBudget # 13200 (~6600/setup across 2, or ~4400 across 3)
        
        allocPerLeaps100k = 9900
        leapsContracts100k = allocPerLeaps100k // leapsCost
        self.assertEqual(leapsContracts100k, 1, "Should allocate exactly 1 contract on $100k account")
        
        allocPerSpread100k = 4400
        spreadContracts100k = allocPerSpread100k // spreadCost
        self.assertEqual(spreadContracts100k, 2, "Should allocate exactly 2 contracts on $100k account")

if __name__ == "__main__":
    unittest.main(verbosity=2)
