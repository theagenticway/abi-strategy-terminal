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

# --- Data Paths -------------------------------------------------------------
# NOTE: this mirrors the original layout: <project_root>/data, where
# <project_root> is the parent of the directory this file lives in
# (i.e. the parent of engine/).
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")

RETENTION_DAYS = 365  # 1-Year historical retention prune
