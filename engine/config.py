"""
Shared configuration: portfolio sizing constants and on-disk data paths.
Extracted from the top of the original scanner.py so every engine module
can import these without pulling in scanner.py itself (which would create
circular imports once scanner.py becomes the orchestrator).
"""
import os

# --- Portfolio / Risk Constants -------------------------------------------
MAX_OPTIONS_SLOTS = 18
MAX_OPTIONS_SPRINT_SLOTS = 12   # Tactical Spreads (45-60 DTE)
MAX_OPTIONS_ANCHOR_SLOTS = 6    # Strategic LEAPS (Jan 2028)
REPLACEMENT_HURDLE_DELTA = 18.0 # Alpha score advantage required to trigger eviction
MIN_EVICTION_AGING_DAYS = 5     # Minimum sessions held before eviction eligibility

# --- High-Risk Sprint / Model Heuristics ------------------------------------
# These are deliberate risk/money-management rules (not bugs) that were previously
# scattered as magic numbers across universe_scan.py. Named here so the actual
# trading rules are visible and adjustable in one place. NOTE: these constants
# are not yet wired into universe_scan.py's call sites - that's a follow-up,
# since swapping every occurrence carries its own risk and should be verified
# against the test suite one call site at a time rather than all at once.
DEFAULT_PORTFOLIO_CAPITAL = 100000.0
MAX_CAPITAL_ALLOCATION_PCT = 0.06        # $6,000 max capital per High-Risk Sprint on $100K
DOLLAR_AT_RISK_PCT = 0.0045              # $450 max dollar-risk per High-Risk Sprint trade
HIGH_RISK_MIN_BETA = 1.5
HIGH_RISK_MIN_ADR_PCT = 3.0
SPRINT_STOP_PCT = 0.075                  # -7.5% technical stop for High-Risk Sprints
ESTIMATED_DEBIT_SPREAD_WIDTH_RATIO = 0.38  # Midpoint debit estimate for a 1-strike OTM spread

# --- Data Paths -------------------------------------------------------------
# NOTE: this mirrors the original layout: <project_root>/data, where
# <project_root> is the parent of the directory this file lives in
# (i.e. the parent of engine/).
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")

RETENTION_DAYS = 365  # 1-Year historical retention prune
