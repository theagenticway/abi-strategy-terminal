# AI Agent Context & Platform Onboarding Guide: ABI Strategy Terminal

Welcome! This document provides the definitive, end-to-end technical context for the **ABI Strategy Terminal & Quantitative Execution Engine**. Whenever starting a new task, read this document first to understand the architecture, data pipeline, quantitative logic, file locations, and operational guidelines.

---

## 1. System Overview & Mission

The **ABI Strategy Terminal** is an institutional-grade, fully autonomous quantitative trading platform designed to eliminate manual spreadsheet tracking, fragmented alerts, and emotional execution. 

* **Core Mission**: Execute daily quantitative scans during US market hours, score equities and derivatives on multi-factor alpha models, manage risk via fixed-fractional Dollar-at-Risk position sizing, audit open positions with active health tier tracking, and dynamically recycle capital through relative-strength eviction.
* **Hosting & Runtime**: Zero infrastructure cost. Operates entirely via **GitHub Actions** (`.github/workflows/scan.yml`) on market-hours crons and serves its frontend portals via **GitHub Pages**.
* **Frontend Philosophy**: 100% Vanilla HTML5, CSS3, and JavaScript (ES6+). Zero build steps, zero bundlers (no Vite/Webpack), and zero external framework dependencies (no React/Vue). Pages load instantly from static JSON payloads in `data/`.

---

## 2. Capital Architecture & The Decoupled Twin-Engine Model

The terminal manages a total capital baseline of **$200,000**, completely partitioned across two decoupled portfolios to eliminate capital competition between cash equities and leveraged options:

```text
                          ┌────────────────────────────────────────────────────────┐
                          │         ABI QUANTITATIVE EXECUTION ENGINE              │
                          │        Starting Capital: $200,000 ($100K x 2)          │
                          │            (Scalable to $500K – $1.0M+)                │
                          └──────────────────────────┬─────────────────────────────┘
                                                     │
                     ┌───────────────────────────────┴───────────────────────────────┐
                     ▼                                                               ▼
  ┌──────────────────────────────────────┐                       ┌──────────────────────────────────────┐
  │      OPTIONS PORTFOLIO ($100,000)    │                       │       STOCK PORTFOLIO ($100,000)     │
  ├──────────────────────────────────────┤                       ├──────────────────────────────────────┤
  │ • Capacity: 16 – 21 Active Positions │                       │ • Capacity: 16 – 21 Active Positions │
  │ • Target Capacity: 18 Active Slots   │                       │ • Target Capacity: 18 Active Slots   │
  │ • Max Risk / Trade: $1,000 (1.0%)    │                       │ • Max Risk / Trade: $350–$500 (0.45%)│
  │ • Capital Ceiling: Controlled Debit  │                       │ • Capital Ceiling: 6.0% ($6,000 max) │
  │ • Tactical Sprint: 10–12 Slots       │                       │ • Tactical Sprint: 10–12 Slots       │
  │ • Strategic Anchor: 6–8 Slots        │                       │ • Strategic Anchor: 6–8 Slots        │
  │ • Vehicles: Spreads & Call LEAPS     │                       │ • Vehicles: Common Shares (Cash)     │
  │ • Portal UI: index.html              │                       │ • Portal UI: stocks.html             │
  │ • Persistent Log: trades_log.json    │                       │ • Persistent Log: stock_trades_log   │
  └──────────────────────────────────────┘                       └──────────────────────────────────────┘
```

* **Scalability**: Designed to scale from $100K to $500K+ without changing logic. Sizing is governed by formulas, not hardcoded dollar amounts.
* **Sub-Book Partitioning**: Both portfolios split capacity into:
  * **Tactical Sprint Book (12 slots)**: High-Risk Sprints & Balanced Swings (10–35 day horizon).
  * **Strategic Anchor Book (6 slots)**: Core Secular Compounders & Jan 2028 LEAPS (40–120+ day horizon).

---

## 3. Directory & File Reference Map

```text
abi-strategy-terminal/
├── .github/
│   └── workflows/
│       └── scan.yml            # GitHub Actions cron workflow (11:00 AM, 12:30 PM, 2:00 PM ET)
├── data/
│   ├── latest.json             # Master daily market telemetry & recommendations payload
│   ├── summary.json            # Rolling per-day macro_breadth history (source of true cumulative stats)
│   ├── recommendations_archive.json # 365-day rolling archive of all generated signals
│   ├── stock_trades_log.json   # Persistent audit ledger for common stock trades
│   ├── trades_log.json         # Persistent audit ledger for options trades
│   └── history/
│       └── YYYY-MM-DD.json     # Historical daily raw snapshots
├── engine/
│   ├── scanner.py              # THIN ORCHESTRATOR ONLY: CLI args (--backfill), run_backfill(),
│   │                           # __main__ entry point. Re-exports every public name the modules
│   │                           # below own (process_universe, audit_and_update_trades,
│   │                           # determine_invalidation_driver, ETF_SECTOR_MAP, etc.) so
│   │                           # `scanner.<name>` keeps working for any external caller/test.
│   │                           # As of the engine split, scanner.py no longer CONTAINS the
│   │                           # scan/audit/persistence logic itself - see the 6 files below.
│   ├── config.py               # Shared constants: MAX_OPTIONS_SLOTS/SPRINT/ANCHOR_SLOTS,
│   │                           # REPLACEMENT_HURDLE_DELTA, MIN_EVICTION_AGING_DAYS,
│   │                           # DEFAULT_PORTFOLIO_CAPITAL, MAX_CAPITAL_ALLOCATION_PCT,
│   │                           # DOLLAR_AT_RISK_PCT, HIGH_RISK_MIN_BETA/ADR_PCT,
│   │                           # SPRINT_STOP_PCT, and data paths (DATA_DIR/HISTORY_DIR/
│   │                           # RETENTION_DAYS). SINGLE SOURCE OF TRUTH for portfolio capital -
│   │                           # stocks.py and patterns.py both import DEFAULT_PORTFOLIO_CAPITAL
│   │                           # from here rather than defining their own copy. If you ever see
│   │                           # a hardcoded $100,000 / 100000.0 anywhere else in engine/, that's
│   │                           # a bug - it should be reading this constant instead.
│   ├── market_data.py          # fetch_market_data() (batches yfinance downloads in groups of 75),
│   │                           # extract_ticker_df(), prune_old_history(),
│   │                           # verify_multi_timeframe_confluence() (1h/4h check).
│   ├── benchmark.py            # calculate_benchmark_matrix() (4-index macro confluence) and
│   │                           # generate_market_commentary() (executive summary narrative).
│   ├── universe_scan.py        # process_universe(): the full per-ticker/per-ETF/per-subsector
│   │                           # scan. ~1,200 lines, the largest module in the engine - see
│   │                           # Gotcha 4 below before touching this file.
│   ├── trade_audit.py          # audit_and_update_trades(), determine_invalidation_driver()
│   │                           # (post-mortem stop-out attribution), daily re-scoring, eviction.
│   ├── persistence.py          # ensure_ledgers_exist(), save_payloads() (writes latest.json,
│   │                           # dated history/, summary.json; triggers archive.py + stocks.py
│   │                           # ledger updates on every scan).
│   ├── stocks.py               # Common stock engine: sizing, 3-prong structuring, stock alpha score, equity audit
│   ├── patterns.py             # Options engine: options chains, spreads, LEAPS, options alpha score, liquid route
│   ├── indicators.py           # Technical telemetry: MAs, RSI, MACD hook, RVOL, Beta, Dow structure, Health Tiers
│   ├── universe.py             # 500+ S&P/Nasdaq constituents, 25 benchmark ETFs, 4 macro indices
│   ├── archive.py              # 365-day signal archiver: uniform extraction, upsert idempotency, auto-pruning
│   └── requirements.txt        # Python RUNTIME dependencies only (yfinance, numpy, pandas, requests).
│                               # Running the test suite additionally requires `pytest` and
│                               # `beautifulsoup4`, which are NOT listed here - install them
│                               # separately before running tests/.
├── tests/
│   ├── test_stock_engine.py    # 23 tests: equity sizing, 6% cap, macro gating, eviction, 2-tranche model
│   ├── test_archive_module.py  # Tests: signal extraction, idempotency, 365-day pruning
│   ├── test_multi_horizon.py   # Tests: 3-prong multi-horizon trade structuring
│   ├── test_suite.py           # Core indicator & options math tests
│   ├── test_allocator_node.js  # Node.js simulation for options allocation & UI state
│   ├── test_stocks_page_node.js# Node.js simulation for stocks.html DOM rendering & filters
│   └── test_archive_html.js    # Node.js simulation for archive.html search & filters
├── index.html                  # Primary Options Terminal & Active Trades Dashboard. Also hosts
│                               # the "Macro-Adaptive Portfolio Allocator" - a purely client-side,
│                               # localStorage-backed capital calculator (key: abi_my_portfolio).
│                               # NOTE: this has NO connection to engine/config.py's
│                               # DEFAULT_PORTFOLIO_CAPITAL - they are two independent capital
│                               # concepts. Changing one does not affect the other. See Gotcha 5.
├── stocks.html                 # Dedicated Common Stock Terminal & Portfolio Audit Ledger
├── archive.html                # 365-Day Historical Signal Search Engine & Export Portal
├── radar.html                  # High-Risk Momentum Sprint Surveillance Radar (renders
│                               # high_risk_stocks_radar / high_risk_options_radar from
│                               # universe_scan.py). Has no capital-input UI of its own; sizing
│                               # shown here reflects config.py's DEFAULT_PORTFOLIO_CAPITAL at
│                               # scan time for whoever ran the scan, not the viewer's own capital.
├── macro.html                  # 4-Index Macro Benchmark Matrix & Sector Momentum Map
├── advanced.html                # Advanced Analytics, Technical Telemetry & Deep-Dive Diagnostics
├── README.md                   # High-level product overview, features, and setup documentation
├── DATA_METRICS_AND_SCORING_ARCHITECTURE.md # Definitive quantitative & mathematical specification
└── context.md                  # THIS FILE: Developer & AI Agent Onboarding Manual
```

---

## 4. Key Quantitative Rules & Non-Negotiable Logic

### A. Universal Hard Gatekeeper Filters
Before any stock or option can qualify for recommendation, it must pass **100% of the 6 Hard Gates**:
1. **50 EMA Velocity**: Price $\ge$ EMA50 and `reclaim_days <= 3` (fresh momentum; rejects stale, extended moves).
2. **Retrace Taxonomy**: `retrace_type` in `["EMA50", "DB", "OTE"]` (requires institutional pullback structure).
3. **Overhead 200 SMA Runway**: Runway $\ge 5.0\%$ or `CLEAR` (Price $\ge$ SMA200). Never buy into overhead institutional resistance walls.
4. **RSI(14) Floor**: $\text{RSI}(14) \ge 45.0$ (Wilder's smoothing). Rejects severe institutional distribution and falling knives.
5. **MACD Histogram Hook**: $\text{Hist}_t > \text{Hist}_{t-1}$. Confirms selling deceleration and upward curl on Day 0/1 without lag.
6. **Dow Theory Market Structure**: Regime $
e$ `"BEARISH_LH_LL"`. Rejects dead-cat bounces in structural downtrends.
7. **Earnings Calendar Blackout**: Minimum 21 days clearance before corporate earnings to eliminate binary gap-down risk.

### B. Fixed-Fractional Dollar-at-Risk Position Sizing
* **Options Book**: Max risk hard-capped at **$1,000 (1.0% of $100K)**. Sized to debit paid on vertical spreads or technical stop on LEAPS.
* **Common Stock Book**: Max risk sized to **$350–$500 (0.45% baseline)**:
  $$\text{Shares} = \max\left(1, \min\left(\left\lfloor \frac{\text{Max Risk Dollars}}{\max(\text{Entry} \times 0.02, \text{Entry} - \text{Stop})} \right\rfloor, \left\lfloor \frac{\text{Max Capital Ceiling (6\%)}}{\text{Entry Price}} \right\rfloor\right)\right)$$
* **6.0% Capital Ceiling Safeguard**: Maximum capital deployed per stock position is **$6,000 on $100K** ($30,000 on $500K). Prevents disproportionate position sizes on ultra-tight stops.

### C. Macro Regime Steering & Sector Contagion Shields
* **4-Index Macro Benchmark Matrix**: Measures SPY, QQQ, RSP, IWM vs. 50 EMA ($M \in [0, 4]$).
* **Sector Contagion Shield**: In hostile or rotation regimes ($M \le 2$), new common stock swings in Technology, Semiconductors, and Software (`["TECH", "SEMIS", "SOFTWARE"]`) are automatically blocked to prevent Nasdaq distribution contagion.
* **Dynamic Tier Capacities**: Hard limits (0 to 5 per tier) based on macro environment ($M=4 \rightarrow 5/5/5$; $M=1 \rightarrow 0/1/3$; $M=0 \rightarrow 0/0/1$).

### D. Sector Capital Allocation Caps
* **Sector Cap**: Max **30%–35% total portfolio capital** per GICS sector (~5–6 positions in an 18-slot book).
* **Sub-Industry Cap**: Max **20% total portfolio capital** per sub-industry (~3–4 positions).

### E. Two-Tranche Scale & Trail Model (Equities)
* **Tranche 1 (50% shares)**: Scale at TP1 (+2.0R to +2.5R, +12% to +18%). Move Stop Loss on Tranche 2 to **Breakeven (Entry Price)**. Trade transitions to `TP1_SCALED` and **Tier A: House Money** (eviction-exempt).
* **Tranche 2 (50% shares)**: Trailing runner managed on 21 EMA (Sprint) or 50 EMA (Balanced) until confirmed daily close below.

### F. Price-Gated Stagnation Protocol
* Bypasses rigid calendar exits (Day 10/14 kill-switch) if `Close > Entry` and `Close ≥ EMA50`.
* Sprints extended up to **22 trading sessions**; Balanced swings extended up to **35 trading sessions**. Stops trailed to breakeven.

### G. Active Health Tiers & Relative-Strength Eviction
* **Health Tiers**:
  * `Tier A (House Money)`: De-risked (TP1 hit, stop $\ge$ entry). Eviction-exempt.
  * `Tier B (On-Track)`: Score $\ge 60.0$, holding above 50 EMA. Eviction-exempt.
  * `Tier C (Stagnant)`: Score 50.0–59.9, momentum slowing.
  * `Tier D (Eviction Eligible)`: Score $< 55.0$ for $\ge 2$ consecutive days or $\ge 18$ days stalled with score $< 58.0$.
* **Relative-Strength Eviction Hurdle**:
  * Trigger: Total Open $\ge 18$ slots OR Sub-Book $\ge 85\%$ full OR incumbent flagged Tier D.
  * Aging Rule: Incumbent must have `days_active >= 5` sessions (`MIN_EVICTION_AGING_DAYS = 5`).
  * Hurdle Delta: $\Delta = \text{Score}_{\text{Candidate}} - \text{Score}_{\text{Incumbent}} \ge 18.0$ points.
  * Closes incumbent as `CLOSED_EVICTED`, books P&L, logs delta, and allocates slot to incoming candidate.

### H. The "Liquid Route" Options-to-Stock Auto-Switch
* If an options candidate meets technical gates but fails options chain liquidity ($\text{OI} < 500$ or bid-ask spread $> 8\%$), it is automatically converted into a **Common Stock Order Ticket** with a `🔄 AUTO-ROUTED FROM OPTIONS` badge.

### I. 70% Max-Profit Spread Harvesting
* Vertical spreads reaching $\ge 70\%$ of max spread width or TP1 are automatically harvested, recycling portfolio slots days ahead of expiration.

---

## 5. Critical Engineering Guidelines & Past Pitfalls

### ⚠️ Gotcha 1: Dictionary Key Synchronization Across Modules
* When `universe_scan.py`, `stocks.py`, or `patterns.py` generate records, their dictionary keys MUST be cleanly aligned with `engine/archive.py` (`extract_signal_records`) and the frontend JS renderers.
* **Past Bug**: `archive.py` was looking for `c.get("entry_price")` instead of `c.get("price")` and `s.get("stop_loss")` instead of `s.get("stop")` / `s.get("macro_stop")`, causing `0.0` prices in the archive.
* **Rule**: Always verify key fallbacks (e.g., `s.get("price", s.get("entry_price", s.get("current_price")))`).

### ⚠️ Gotcha 2: Zero-Build Frontend Compatibility
* The entire frontend (`index.html`, `stocks.html`, `archive.html`, `macro.html`, `radar.html`) runs directly in standard browsers without Babel, Webpack, or npm.
* **Rule**: Use standard ES6+ JavaScript. Never use JSX, TypeScript, SCSS, or require Node runtime dependencies in web pages.
* Always validate syntax using `node test_syntax.js` or browser simulation scripts.

### ⚠️ Gotcha 3: Testing Before Committing
* The repo contains an extensive verification suite. Before declaring any feature complete or submitting changes, execute:
  ```bash
  # 1. Run all Python unit and functional tests
  python3 -m unittest discover -s tests -p "test_*.py"
  # (equivalently: pip install pytest beautifulsoup4 && python3 -m pytest tests/ -q
  #  --ignore=tests/test_allocator_node.js --ignore=tests/test_archive_html.js
  #  --ignore=tests/test_stocks_page_node.js)

  # 2. Run dedicated stock engine tests
  python3 tests/test_stock_engine.py

  # 3. Run archive engine tests
  python3 tests/test_archive_module.py

  # 4. Run Node.js simulation and syntax tests
  node tests/test_allocator_node.js
  node tests/test_stocks_page_node.js
  node tests/test_archive_html.js
  node test_syntax.js
  ```
* **Important limitation**: this suite checks structure (keys exist, types are correct, math is internally consistent) far more than it checks plausibility of values. It has passed with candidates that all silently shared one hardcoded score, an expiry date that had already passed, and an ETF fallback that lied about outperforming. When adding logic that produces a per-ticker or per-day *value* (a score, a date, a rank), also assert that the value varies sensibly across tickers/days and stays within a sane range - not just that the key exists.

### ⚠️ Gotcha 4: `ticker_records` and `qualified_candidates`/`qualified_stock_candidates` Are Different Dicts
* Inside `universe_scan.py::process_universe()`, the per-ticker loop builds one `record` dict per ticker into `ticker_records` (price, beta, ADR, sector, etc. - the raw scan telemetry for *every* ticker, qualified or not). Separately, `structure_trade_signal()` (patterns.py) and `structure_stock_trade()` (stocks.py) build their own, differently-shaped dicts (`trade_setup`/`stock_setup`) that get appended to `qualified_candidates`/`qualified_stock_candidates` - but only for tickers that passed the hard gates.
* **These are not the same object and do not share keys.** `ticker_records` entries never have `alpha_score`, `options_alpha_score`, or `iv_rank` - those only exist on the qualified-candidate dicts.
* **Past Bug (found and fixed 2026-09)**: `high_risk_stocks_radar` and `high_risk_options_radar` (Section 13 of `process_universe`) were built by iterating `ticker_records` and calling `t.get("alpha_score", 55.0)` / `t.get("iv_rank", 45.0)`. Since those keys never exist on `ticker_records`, every single row silently fell back to the same hardcoded default (55.0 / 45.0) for every ticker, and with no beta/ADR filter, every ticker in the universe was included regardless of actual risk profile - defeating the purpose of a "high-risk radar."
* **The fix, and the pattern to follow**: build a `{ticker: candidate_dict}` lookup map from `qualified_candidates`/`qualified_stock_candidates` first (`options_score_map`, `stock_score_map`), look up the real value from there when the ticker qualified, and only compute a fresh value directly (e.g. via `indicators.calculate_iv_rank()` or `stocks.compute_alpha_composite_score()`) when there's no match - never default to a flat placeholder for a per-ticker metric that's supposed to vary.
* **Rule**: before reading a "score-like" key off a variable in `process_universe`, check which dict it actually came from (`ticker_records` vs. a `qualified_*` list) - don't assume a key is present just because it's present on some dict with a similar name nearby in the function.

### ⚠️ Gotcha 5: "Optimistic Fallback" Anti-Pattern on Data Outages
* Several places in `universe_scan.py` used to respond to missing/failed data (a failed ETF download, a small sample size, unavailable options liquidity) by substituting an optimistic-looking placeholder rather than a neutral one - e.g. a failed ETF snapshot defaulted to `+2.5% "★ OUTPERFORMING"` rather than "no data," and a thin scan session's cumulative stats were seeded with fixed numbers (`1012`, `385`, `"38.0%"`) instead of being read from `data/summary.json`'s real history.
* **Why this matters more than it looks**: these placeholders don't just render oddly - they can flow into real scoring. A fake "outperforming" ETF could land in `top_quartile_sectors` and inflate every stock in that sector's alpha score via the `mom_spread` bonus.
* **Rule**: when a value can't be computed, default to neutral/zero/`"DATA_UNAVAILABLE"`, not a plausible-looking positive number, and make sure downstream ranking/gating logic explicitly excludes or down-weights `DATA_UNAVAILABLE` entries rather than letting them sort in based on their neutral value alone.
* **Also**: most `except Exception:` fallbacks in `universe_scan.py` are silent (no log line). This keeps a scheduled scan alive when one ticker misbehaves, but means degraded-mode operation is currently invisible in GitHub Actions logs. When adding a new fallback path, consider at least a `print()` noting it was hit.

### ⚠️ Gotcha 6: Two Independent "Portfolio Capital" Concepts - Don't Conflate Them
* `engine/config.py::DEFAULT_PORTFOLIO_CAPITAL` (imported by `stocks.py` and `patterns.py` as the single source of truth) drives the actual dollar sizing math baked into every scan's output - stock share counts, options contract counts, `capital_deployed`, `actual_risk_dollars`. Changing it and re-running the scanner rescales every future recommendation for whoever ran that scan.
* The **"Macro-Adaptive Portfolio Allocator"** on `index.html` is a completely separate, purely client-side calculator that stores its own state in the browser's `localStorage` (key `abi_my_portfolio`). It has no code path back into the Python engine at all.
* **These do not talk to each other.** Editing one has zero effect on the other. If you're asked to make High-Risk Radar (or any other) sizing "dynamic based on the portfolio," check first whether the ask is (a) server-side/single-account ("I run this for my own account, just use my real numbers" - edit `config.py`), or (b) genuinely per-viewer ("different people should see different sizing on the same published page" - requires new frontend UI + a schema change to stop baking absolute dollar amounts into the JSON; not a small change).

---

## 6. Daily Ingestion Workflow (`scan.yml`)

The scanner runs three times daily during active trading hours:
1. **11:00 AM ET (15:00 UTC)**: Morning Momentum Confirmation.
2. **12:30 PM ET (16:30 UTC)**: Midday Trend Follow-Through.
3. **2:00 PM ET (18:00 UTC)**: Afternoon Institutional Setup Finalization.

### Scan Sequence:
1. `engine/universe.py` supplies 500+ tickers and benchmark ETFs.
2. `engine/market_data.py::fetch_market_data()` batches downloads in groups of 75 (`batch_size=75`) to prevent rate-limiting.
3. `engine/universe_scan.py::process_universe()` orchestrates the full scan: indicators/Dow structure from `engine/indicators.py`, macro regime from `engine/benchmark.py`, equities structured via `engine/stocks.py`, options modeled via `engine/patterns.py`.
4. `engine/trade_audit.py::audit_and_update_trades()` re-scores and audits all open positions (stop-outs, TP hits, eviction).
5. Signals archived idempotently via `engine/archive.py`.
6. `engine/persistence.py::save_payloads()` writes `data/latest.json`, `data/stock_trades_log.json`, `data/trades_log.json`, `data/summary.json`, and `data/recommendations_archive.json`.
7. `engine/scanner.py` is the entry point that wires steps 1-6 together (`python engine/scanner.py` or `--backfill N`); it doesn't contain this logic itself, see Section 3.
8. GitHub Action commits updated JSON files to `main`, auto-deploying to GitHub Pages.
