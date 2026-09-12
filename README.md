# ABI Strategy Terminal & Quantitative Execution Engine

Institutional-grade quantitative market telemetry, multi-index benchmark confluence engine, dual-portal execution architecture (**Options Terminal** and **Dedicated Stocks Terminal**), dynamic multi-factor Alpha scoring, macro-adaptive portfolio allocator, and automated multi-asset trade auditor.

Engineered to replace fragmented TradingView alerts, third-party webhooks, and manual spreadsheets with an autonomous, zero-cost quantitative pipeline hosted entirely on **GitHub Actions** and **GitHub Pages**.

For the complete, granular data dictionary, yfinance field mapping, and mathematical formula breakdowns, see:  
📖 **[`DATA_METRICS_AND_SCORING_ARCHITECTURE.md`](DATA_METRICS_AND_SCORING_ARCHITECTURE.md)**

---

## 🏛️ Architecture & System Blueprint

```text
                     [Live Market Data Ingestion]
        493+ S&P 500 / NASDAQ-100 Constituents + 25 Sector ETFs
            + 4 Benchmark Indices (SPY, QQQ, RSP, IWM)
                     (yfinance batch OHLCV)
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │   MULTI-INDEX BENCHMARK CONFLUENCE MATRIX    │
         │  • SPY, QQQ, RSP, IWM Distance vs. 50 EMA    │
         │  • 5-day EMA Slopes & Confluence Score (0–4) │
         │  • Dynamic Regime: Expansion vs. Rotation    │
         │    vs. Thin Masking vs. Systemic Breakdown   │
         └──────────────────────┬───────────────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │     EXECUTIVE MARKET BRIEFING ENGINE         │
         │  • 4-Tier Action Verdict: Buy / Caution /    │
         │    Hold / Hedge                              │
         │  • Dynamic Macro & Sector Inflow/Outflow     │
         │  • Concrete Capital Execution Mandates       │
         └──────────────────────┬───────────────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │        QUANTITATIVE SCREENING FUNNEL         │
         │  • EMAs (10, 21, 50, 200) & SMAs (150, 200) │
         │  • Relative Volume: RVOL ≥ 1.0x Institutional│
         │  • Dow Theory Market Structure (HH/HL)       │
         │  • 1-Year Implied Volatility Rank (IV Rank)  │
         │  • Multi-Timeframe 4H Candle Confluence      │
         │  • 45-Day Corporate Earnings Blackout Filter │
         └──────────────────────┬───────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
┌──────────────────────────────┐        ┌──────────────────────────────┐
│   OPTIONS RADAR (index.html) │        │   STOCKS TERMINAL (stocks)   │
│     (engine/patterns.py)     │        │      (engine/stocks.py)      │
├──────────────────────────────┤        ├──────────────────────────────┤
│ • Bull Call Spreads (45-60d) │        │ • Tactical Equity Swings     │
│ • Core Call LEAPS (Jan 2028) │        │ • Core Common Accumulation   │
│ • Downside Hedges (Bear Puts)│        │ • Dollar-at-Risk Sizing (1%) │
│ • Options Alpha Radar Score  │        │ • Stock Alpha Composite Score│
│ • Waterfall Liquidity Queue  │        │ • 2-Tranche Scale & Trail    │
│   (OI ≥ 250, Spread ≤ 15%)   │        │ • 20% Single-Stock Cap       │
│ • Unverified Earnings Badge  │        │ • Sector Diversity Guardrail │
│ • Audits: trades_log.json    │        │ • Audits: stock_trades_log   │
└──────────────────────────────┘        └──────────────────────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │   STAGE 1 MACRO-ADAPTIVE PORTFOLIO ALLOCATOR │
         │  • Total Capital Sizing ($10k to $100k+)     │
         │  • Core vs. Satellite Asset Ratios           │
         │  • Dynamic Dry Powder Floor (15% to 50%+)    │
         │  • 33% Session Tranche Pacing Limit          │
         │  • Integer Contract & Share Sizing           │
         │  • Browser-Persistent LocalStorage Tracking  │
         │  • JSON Export & Import (Backup / Restore)   │
         │  • Portfolio Capacity Reached Guardrail      │
         └──────────────────────┬───────────────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │       AUTOMATED PERFORMANCE AUDIT LEDGER     │
         │  • Strategy Alpha Comparison Ribbon (Tab 3)  │
         │  • Side-by-Side: Options Book vs. Equity Book│
         │  • Automated Breakeven Trailing (+2.5 R:R)   │
         │  • 50 EMA Trend Trailing for Common Stocks   │
         │  • Root-Cause Loss Attribution Engine        │
         └──────────────────────────────────────────────┘
```

---

## ⚡ Core Quantitative Intelligence Engines

### 1. 🏛️ Executive Market Briefing & 4-Tier Action Verdict
Synthesizes all ingested quantitative telemetry into an executive daily briefing at the top of the terminal with **zero hardcoding**:

* **4-Tier Action Verdict Matrix**:
  * 🟢 **AGGRESSIVE BUY (Risk-On Expansion)**: 4 of 4 benchmark indices $> 50$ EMA, Breadth $\ge 0.55$. Full 33% daily tranche deployment across high-velocity Bull Spreads, Shares, and Core LEAPS. Baseline 15% cash reserve.
  * 🟡 **CAUTIOUS BUY (Selective Cyclical Rotation)**: QQQ $< 50$ EMA, but SPY or RSP $> 50$ EMA. Tech under distribution, cyclicals holding. Long deployment permitted **only** in leading non-tech sectors with RVOL $\ge 1.0\times$. 25% cash reserve.
  * 🟠 **HOLD / PRESERVE (Chop & Retest)**: Broad market breadth $< 0.35$ or narrow mega-cap masking. Zero new long commitments. Trail stops on open winners; 35% cash buffer.
  * 🔴 **DEFENSIVE / HEDGE (Systemic Breakdown)**: SPY & RSP $< 50$ EMA. 100% freeze on long calls and long stock; deploy tactical Bear Put Spreads or sit in 50%–70% cash.
* **3-Tier Algorithmic Synthesis**:
  * **Macro Regime Narrative**: Synthesizes the 4 indices, distance vs. 50 EMA, slope, and advance/decline breadth ratio.
  * **Sector Flow Divergence**: Compares top 3 vs. bottom 3 sectors on the 25-ETF Ladder (e.g., rotation out of Solar/Airlines into Gold/Energy).
  * **Capital Execution Mandates**: Concrete bullet points specifying permitted sectors, restricted sectors, and cash preservation targets.

### 2. 🌐 Multi-Index Benchmark Confluence Matrix (`SPY`, `QQQ`, `RSP`, `IWM`)
Eliminates **Index Masking (Mega-Cap Distortion)** where a handful of mega-caps prop up `QQQ` while the broader market breaks down:
* **`SPY` (S&P 500)**: Macro institutional benchmark across all 11 GICS sectors.
* **`QQQ` (Nasdaq 100)**: High-beta tech, AI, and growth momentum.
* **`RSP` (S&P 500 Equal-Weight)**: **The True Breadth Truth-Teller** (each stock weighted at 0.2%). The spread between SPY and RSP reveals whether rallies are broad or fragile illusions.
* **`IWM` (Russell 2000 Small-Caps)**: Domestic economic liquidity and speculative credit appetite barometer.
* **Composite Confluence Score (0 to 4)**: Calculates moving average distance and slope dynamically to classify market health into `BROAD_EXPANSION`, `SECTOR_ROTATION`, `THIN_MASKING`, or `SYSTEMIC_LIQUIDATION`.

### 3. 🎯 Dedicated Dual-Portal Architecture: Options vs. Stocks
The execution engine is cleanly decoupled into two dedicated, specialized trading terminals:
* **Options Alpha Radar (`index.html`)**: Exclusively focused on asymmetric options structures (30–60 DTE Bull Call Spreads, Jan 2028 Deep-ITM Call LEAPS, and Downside Bear Put Spread Hedges) with contract Greeks, Open Interest depth, limit debit order tickets, and implied volatility analysis.
* **Dedicated Cash Equities Terminal (`stocks.html`)**: Complete standalone stock portal with **zero options terminology or Greeks**. Features fixed fractional share sizing, technical stop placement, Two-Tranche scale and trail execution, and dedicated stock performance tracking.
* **Seamless Cross-Navigation**: Top-bar navigation chips dynamically route between portals (`[● 🎯 Options Alpha Radar]` $\leftrightarrow$ `[● 📈 Dedicated Stocks Terminal]`) with URL parameter synchronization.

### 4. 📊 Multi-Factor Dynamic Alpha Scoring Engines
Replaces static sorting with comprehensive 100-point multi-factor quantitative ranking models:

#### A. Stock Alpha Composite Score (`engine/stocks.py`)
Dynamically ranks cash equity candidates across 5 core institutional factors:
1. **Retrace & Reclaim Momentum (25 pts)**: Day 0 reclaims (25 pts), Day 1 follow-through (22 pts), Day 2 (18 pts), Day 3 (12 pts).
2. **Dow Theory Market Structure (20 pts)**: Validates higher-high / higher-low structure (`🟢 HH/HL (CONFIRMED)` = 20 pts, `🟢 HH/HL (EMERGING)` = 18 pts, `🟡 BASE` = 12 pts, `🔴 LH/LL BEARISH` = $-15$ pt penalty).
3. **Macro & Sector Confluence (20 pts)**: 4/4 Index Confluence + positive sector momentum spread (`mom_spread` $\ge 0$) awards up to 20 pts; negative spread receives a $-10$ pt penalty.
4. **Institutional RVOL Participation (20 pts)**: Volume surges $\ge 2.0\times$ award 20 pts; $\ge 1.5\times$ award 16 pts; $\ge 1.2\times$ award 12 pts; $\ge 1.0\times$ award 8 pts.
5. **Risk-to-Reward Geometry (15 pts)**: $\text{R:R} \ge 3.5:1$ awards 15 pts; $\ge 3.0:1$ awards 12 pts; $\ge 2.5:1$ awards 8 pts.

#### B. Options Alpha Radar Score (`engine/patterns.py`)
Ranks options candidates by contract edge, liquidity, and asymmetric payoff:
1. **Directional Alpha Foundation (40 pts)**: Scaled from underlying directional setup quality.
2. **IV Rank Efficiency (25 pts)**: Awards maximum points for underpriced implied volatility ($\text{IV Rank} < 20\%$ = 25 pts; $<35\%$ = 20 pts).
3. **Institutional Options Liquidity (20 pts)**: High Open Interest and tight bid-ask spreads ($\text{OI} \ge 1000$ and spread $\le 5\%$ = 20 pts).
4. **Overhead 200 SMA Runway (15 pts)**: Blue Sky above 200 SMA awards 15 pts; $<200$d history receives neutral 8 pts.
5. **Earnings Blackout Penalty**: Confirmed earnings within 45 DTE trigger a $-35$ pt blackout penalty.

### 5. 🛡️ Institutional Risk & Integrity Guardrails

* **Sector Diversity Concentration Cap**: The top candidate selector enforces a strict limit of **maximum 2 tickers per sector** in the top 5, preventing portfolio over-concentration in correlated industry groups.
* **Transparent Unverified Earnings Handling (Item 1A)**: If a corporate earnings date is unverified by API providers, the setup is labeled with an amber `⚠️ UNVERIFIED EARNINGS` badge and assessed a minimal $-2$ pt uncertainty haircut rather than an aggressive $-35$ pt blackout penalty. This allows high-scoring candidates to remain visible while alerting the trader to verify the date before execution.
* **Robust Off-Hours Options Liquidity Verification (Item 1B)**: Prevents false rejections when scanning after market close (when market makers pull quotes and spreads artificially blow out $>20\%$). The engine automatically evaluates **settled Open Interest ($\ge 200$) and daily volume ($\ge 5$)** during off-hours to certify institutional contract depth.
* **Spinoff & Recent IPO Data Integrity (Item 2D)**: Tickers with $<200$ trading days are explicitly flagged with `has_200sma = False`, labeled as `N/A (<200d History)`, and receive a neutral 8-point baseline rather than falsely claiming 15-point blue-sky clearance.
* **Leading-Edge Dow Theory Market Structure (Item 2E)**: In addition to 5-bar fractal swing pivots, the engine inspects real-time $T_0/T_{-1}$ breakout velocity to distinguish between `🟢 HH/HL (CONFIRMED)` and `🟢 HH/HL (EMERGING)`.
* **20% Capital Allocation Ceiling Safeguard**: Sizing on Dollar-at-Risk prevents account blowups from ultra-tight stops by capping single-position capital at **20% of total portfolio equity**.
* **Two-Tranche Scale & Trail Exit Engine**: Tranche 1 (50% shares) scales out at **TP1 (+2.5 R:R)**; Tranche 2 moves the technical stop to **Breakeven** and trails along the **rising 50-day EMA**.

### 6. 💰 Stage 1 Macro-Adaptive Portfolio Allocator & Cash Buffering
Transforms the terminal from an isolated screener into an active portfolio construction system:
* **Pillar 1: Total Portfolio Capital**: Configurable account sizing ($10k, $25k, $50k, $100k, and custom numeric input).
* **Pillar 2: Allocation Architecture**:
  * *Balanced Core/Satellite* (60% Core / 40% Tactical).
  * *Tactical Momentum* (80% Tactical / 20% Core).
  * *Secular Compounding* (80% Core / 20% Tactical).
  * *Macro-Adaptive Auto-Tilt* (Risk-On: 35/65, Mixed: 50/50, Risk-Off: 80/20).
* **Pillar 3: Dynamic Dry Powder (Cash Buffer)**:
  * *Automated Macro Buffer*: 15% (Risk-On), 25% (Mixed), 50%–70% (Risk-Off).
  * *Manual Overrides*: Fixed 20%, Fixed 30%, Fully Deployed (0%).
* **Pillar 4: Tranche Pacing & Capital Protection**:
  * Real open risk deduction: $\text{Free Liquid Cash} = \max(0, \text{Total Capital} - \text{Committed Risk} - \text{Cash Floor})$.
  * Single-session ceiling: $\text{Today's Tranche} = \min(\text{Free Liquid Cash}, \text{Total Capital} \times 0.33)$.
* **Integer Sizing & Small-Account Fallback**: Enforces integer contract and share floors, rolling unallocated budget into cash reserves.
* **Portfolio Capacity Reached Guardrail**: Throttles today's deployable tranche to `$0` and renders a warning banner when open risk + cash floor reach 100%.

### 7. 🗄️ LocalStorage Portfolio State & JSON Portability Engine
* **Interactive UI Toggles**: Click `[+ Mark as Taken]` on any recommendation card to log it directly into your portfolio.
* **Table 3 Ledger Tracking**: Tag and monitor trades directly from the historical performance ledger using the `[★ My Portfolio]` filter.
* **Interactive Portfolio JSON Export / Backup**: Generates a clean, timestamped JSON export of your active commitments, account settings, and allocation preferences (`abi_portfolio_backup_YYYY-MM-DD.json`).
* **Portfolio JSON Import with Schema Validation**: Restores or synchronizes portfolio state across devices with support for **Merge** (union existing and imported trades) or **Replace** modes.

---

## 🖥️ Terminal Interface & Core Modules

### Options Terminal (`index.html`)
* **Executive Market Briefing**: Real-time Action Verdict, 4-index chips (`SPY`, `QQQ`, `RSP`, `IWM`), macro narrative, sector flow divergence, and execution mandates.
* **Directional Mode Switcher**: `[● LONG (Bull Call Spreads)]` | `[🔴 HEDGE (Bear Put Spreads)]`.
* **Stage 1 Allocator Bar**: 4-pillar capital sizing, architecture modes, dynamic dry powder buffer, tranche pacing, and capacity alerts.
* **Table 1: Directional Options Swings**: Bull Call Spreads or Bear Put Spreads with strike depth, verified Open Interest (`OI: 720/480 · Vol: 115`), limit debit tickets, options alpha scores, and earnings status.
* **Table 2: Strategic Call LEAPS**: Multi-quarter compounders with Jan 2028 Deep-ITM options, Stage 2 trend badges, and IV Rank efficiency.
* **Tab 2: Macroeconomic Board**: 2D Momentum Quadrant, 25-ETF Ladder vs. 50 EMA, Sector Strength Score, and Sub-Industry Conviction Matrix.
* **Tab 3: Performance & Audit Log**: Side-by-side Strategy Alpha Comparison Ribbon, Options Ledger (`trades_log.json`), Stock Ledger (`stock_trades_log.json`), and Root-Cause Loss Attribution.

### Dedicated Stocks Terminal (`stocks.html`)
* **Executive Market Briefing**: 4-tier Action Verdict, macro narrative, and sector capital flows tailored for cash equity allocation.
* **Stage 1 Allocator Bar (Equities)**: Sized specifically for cash share tranches and dollar-at-risk budgets.
* **Table 1: Tactical Stock Swings**: Stock price, technical stop, TP1 (+2.5 R:R), TP2 (+3.5 R:R), share sizing, capital deployed, Dow Theory market structure badge (`🟢 HH/HL (CONFIRMED)`), and exact limit order tickets.
* **Table 2: Strategic Core Common Stock Accumulation**: Secular Stage 2 compounders with 200 SMA macro invalidation stops, low beta drag ($\le 2.2$), and quarterly rebalancing guidelines.
* **Table 3: Common Stock Performance Ledger**: Dedicated ledger tracking equity paper trades, 50% scale-outs at TP1, breakeven stop trails, and 50 EMA trend trailing.
* **Portfolio Backup / Import Modal**: Full JSON export and import for equity holdings.

---

## 📊 Endpoints & Data Schema

| Resource | Path | Description |
| :--- | :--- | :--- |
| **Options Terminal** | `https://<user>.github.io/<repo>/` | Master options trading terminal (`index.html`) |
| **Stocks Terminal** | `https://<user>.github.io/<repo>/stocks.html` | Dedicated cash equities trading terminal (`stocks.html`) |
| **Latest Telemetry API** | `https://<user>.github.io/<repo>/data/latest.json` | Master payload (options, stocks, macro, benchmark matrix) |
| **Options Audit Ledger** | `https://<user>.github.io/<repo>/data/trades_log.json` | Persistent stateful options paper-trade ledger & metrics |
| **Equities Audit Ledger** | `https://<user>.github.io/<repo>/data/stock_trades_log.json` | Persistent stateful equity paper-trade ledger & metrics |
| **Historical Breadth Index** | `https://<user>.github.io/<repo>/data/summary.json` | Rolling daily macro breadth and regime history |
| **Daily Snapshots** | `https://<user>.github.io/<repo>/data/history/YYYY-MM-DD.json` | Granular historical daily telemetry archives |
| **Architecture Guide** | `DATA_METRICS_AND_SCORING_ARCHITECTURE.md` | Exhaustive data dictionary, formula breakdown & left-to-right matrix |

---

## ⚙️ Automated GitHub Actions Workflow

Configured in `.github/workflows/scan.yml` running on Ubuntu runners with `contents: write` permissions:

* **05:45 MST (12:45 UTC) Mon–Fri**: Pre-market refresh ahead of market open.
* **Hourly (13:30 – 20:30 UTC Mon–Fri)**: Real-time scan during US market hours (06:30 AM – 01:30 PM MST) logging live price reclaims.
* **14:00 MST / 17:00 EDT (21:00 UTC) Mon–Fri**: Official market close, finalized volume ingestion, retention pruning, and audit ledger update.
* **1-Year Retention Auto-Flush**: Automatically purges historical daily archives older than 365 days, capping repository footprint at ~15MB–20MB.
* **Circuit Breaker**: Prevents overwriting valid telemetry if an upstream data feed provider glitch returns 0 tickers.

---

## 🧪 Comprehensive Testing & Verification Suite

A rigorous automated testing suite of **77 automated tests** (57 Python unit/functional tests + 20 Node.js end-to-end DOM simulation tests) is located in `/tests`:

```bash
# 1. Run all Python test suites
python3 tests/test_suite.py
python3 tests/test_stock_engine.py
python3 tests/test_stage1_allocator.py
python3 tests/test_advanced_features.py
python3 tests/test_functional_pipeline.py

# 2. Run Node.js end-to-end simulation suites
node tests/test_allocator_node.js
node tests/test_stocks_page_node.js
```

### Verified Test Coverage:
1. **Mathematical & Indicator Integrity**: Validates `EMA 10/21/50/200`, `SMA 150/200`, `RSI(14)`, `MACD(12,26,9)`, `ADR%`, 60-day rolling `Beta` vs. `SPY`, 20-day `RVOL`, 1-year `IV Rank`, and 30-week `Weekly Stage` slope.
2. **Benchmark Confluence & Market Commentary**: Validates 4-index confluence matrix across all 16 permutation states ($2^4$) and checks dynamic narrative generation across all four action verdict regimes.
3. **Options Liquidity & Waterfall Queue**: Validates `verify_and_fetch_live_options()` across calls, puts, and LEAPS ($\ge 250\text{ OI}$, $\le 15\%$ spread width), off-hours spread blowout handling, and automatic next-in-line skipping on illiquid strikes.
4. **Earnings Blackout & Data Integrity**: Validates confirmed earnings blackout penalty ($-35$ pts) and transparent unverified earnings handling ($-2$ pt haircut with `⚠️ UNVERIFIED EARNINGS` badge).
5. **Market Structure & Dow Theory**: Validates 5-bar fractal swing pivots, emerging vs. confirmed HH/HL, and bearish LH/LL trap penalties.
6. **Equity Strategy Engine (`engine/stocks.py`)**: Validates fixed fractional dollar-at-risk share sizing, 20% capital ceiling safeguard, Two-Tranche Scale & Trail exits (50% TP1 / 50% 50 EMA trail), gap-down slippage modeling, and JSON persistence.
7. **Portfolio Allocator & LocalStorage State**: Validates capital sizing across tiers ($10k to $100k), dynamic dry powder adjustments, 33% session tranche pacing, integer contract rounding, small-account budget protection, position toggling, and the capacity ceiling guardrail.
8. **Dual-Portal UI & Portability**: Validates independent `stocks.html` and `index.html` navigation, absence of leftover widgets, JSON Export schema validation, and JSON Import merge/replace behavior.
