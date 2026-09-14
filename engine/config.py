"""
engine/config.py
Quantitative Configuration, Portfolio Sizing Guardrails, and On-Disk Paths.
Centralizes execution limits, options heuristics, and risk controls for the ABI Strategy Terminal.
"""

import os

# =============================================================================
# 1. FILE & DIRECTORY PATHS
# =============================================================================
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")
RETENTION_DAYS = 365  # 1-Year historical retention prune

# =============================================================================
# 2. PORTFOLIO HEAT & DECOUPLED BOOKS CAPACITY
# =============================================================================
MAX_OPTIONS_SLOTS = 18
MAX_OPTIONS_SPRINT_SLOTS = 12   # Tactical Spreads (35-65 DTE)
MAX_OPTIONS_ANCHOR_SLOTS = 6    # Strategic LEAPS (Jan 2028)
REPLACEMENT_HURDLE_DELTA = 18.0 # Alpha score advantage required to trigger eviction
MIN_EVICTION_AGING_DAYS = 5     # Minimum sessions held before eviction eligibility

# =============================================================================
# 3. POSITION SIZING & CAPITAL GUARDRAILS
# =============================================================================
DEFAULT_PORTFOLIO_CAPITAL: float = 100000.0   # Baseline portfolio size ($100k account)
MAX_CAPITAL_ALLOCATION_PCT: float = 0.06     # 6.0% max capital per slot ($6,000 on $100k)
DOLLAR_AT_RISK_PCT: float = 0.0045           # 0.45% risk per trade ($450 on $100k)

MAX_POSITION_CAPITAL: float = round(DEFAULT_PORTFOLIO_CAPITAL * MAX_CAPITAL_ALLOCATION_PCT, 2)
MAX_DOLLAR_RISK: float = round(DEFAULT_PORTFOLIO_CAPITAL * DOLLAR_AT_RISK_PCT, 2)

# =============================================================================
# 4. HIGH-RISK SPRINT & SWING SCREENING CRITERIA
# =============================================================================
HIGH_RISK_MIN_BETA: float = 1.5
HIGH_RISK_MIN_ADR_PCT: float = 3.0

# SPRINT TECHNICAL STOP & TARGET RATIOS
SPRINT_STOP_PCT: float = 0.075               # -7.5% technical stop limit (0.925)
SPRINT_TP05_R_MULTIPLE: float = 1.0          # +1.0R (Half take-profit / breakeven trail)
SPRINT_TP1_R_MULTIPLE: float = 2.2           # +2.2R primary target
SPRINT_TP2_R_MULTIPLE: float = 3.5           # +3.5R runner target

# =============================================================================
# 5. OPTIONS PRICING, EXPIRY & THETA CLIFF HEURISTICS
# =============================================================================
ESTIMATED_DEBIT_SPREAD_WIDTH_RATIO: float = 0.38  # Modeling debit spread purchase at 38% of width
TARGET_OPTIONS_MIN_DTE: int = 30                  # Min DTE for Bull Call Spread selection
TARGET_OPTIONS_MAX_DTE: int = 65                  # Max DTE for Bull Call Spread selection
TARGET_OPTIONS_NOMINAL_DTE: int = 45              # Nominal target DTE
THETA_CLIFF_DTE: int = 21                         # 21 DTE theta decay cliff threshold for planned exits

# =============================================================================
# 6. OFFLINE / BACKTEST SIMULATED OPTIONS LIQUIDITY FALLBACKS
# =============================================================================
OFFLINE_MOCK_LIQUIDITY_BULL_CALL = {
    "passed": True,
    "offline_fallback": True,
    "long_oi": 650,
    "short_oi": 420,
    "total_vol": 110
}

OFFLINE_MOCK_LIQUIDITY_BEAR_PUT = {
    "passed": True,
    "offline_fallback": True,
    "long_oi": 520,
    "short_oi": 380,
    "total_vol": 75
}

OFFLINE_MOCK_LIQUIDITY_LEAPS = {
    "passed": True,
    "offline_fallback": True,
    "long_oi": 350,
    "total_vol": 35
}
