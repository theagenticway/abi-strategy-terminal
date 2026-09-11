# ABI Strategy Terminal & Quantitative Execution Engine

Institutional-grade quantitative market telemetry, multi-index benchmark confluence engine, dual-book execution radar (**Options Spreads/LEAPS** and **Cash Equities**), dynamic portfolio allocator, and automated multi-asset trade auditor.

Engineered to replace fragmented TradingView alerts, third-party webhooks, and manual spreadsheets with an autonomous, zero-cost quantitative pipeline hosted entirely on **GitHub Actions** and **GitHub Pages**.

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
         │  • Weekly Stan Weinstein Stage 2 Alignment   │
         │  • 1-Year Implied Volatility Rank (IV Rank)  │
         │  • Multi-Timeframe 4H Candle Confluence      │
         │  • 45-Day Corporate Earnings Blackout Filter │
         └──────────────────────┬───────────────────────┘
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
┌──────────────────────────────┐        ┌──────────────────────────────┐
│    DERIVATIVES BOOK ENGINE   │        │     EQUITIES BOOK ENGINE     │
│     (engine/patterns.py)     │        │      (engine/stocks.py)      │
├──────────────────────────────┤        ├──────────────────────────────┤
│ • Bull Call Spreads (45-60d) │        │ • Tactical Equity Swings     │
│ • Core Call LEAPS (Jan 2028) │        │ • Core Secular Accumulation  │
│ • Downside Hedges (Bear Puts)│        │ • Dollar-at-Risk Sizing (1%) │
│ • Waterfall Liquidity Queue  │        │ • 20% Single-Stock Cap       │
│   (OI ≥ 250, Spread ≤ 15%)   │        │ • Two-Tranche Scale & Trail  │
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

### 3. 🌊 Waterfall Liquidity Queue (`engine/patterns.py` & `engine/scanner.py`)
Solves the illiquid options trap on single stocks (e.g., mid-cap put spreads):
* **Real-Time Options Chain Inspection**: Calls `t.option_chain()` via `yfinance` across both `chain.calls` and `chain.puts`.
* **Institutional Liquidity Gates**:
  * **Minimum Open Interest**: $\text{OI} \ge 250$ contracts on both the Long strike and Short strike (or daily volume $\ge 10$). For LEAPS, $\text{OI} \ge 100$.
  * **Bid-Ask Spread Slippage Gate**: $\frac{\text{Ask} - \text{Bid}}{\text{Mid}} \le 15\%$.
* **Automatic Next-in-Line Progression**: If Candidate #1 has low open interest or wide spreads, **the engine logs the rejection (`➔ [N Illiquid Opts Skipped]`), bypasses the ticker, and immediately tests Candidate #2 in the priority queue**.
* **Verified Contract Badging**: Surfaces live strike depth directly on each trade card: `OI: 720/480 · Vol: 115`.

### 4. 📈 Modular Equity / Common Stock Strategy Engine (`engine/stocks.py`)
A dedicated, modular cash-equities engine running in parallel with the options radar:
* **Fixed Fractional Risk Sizing**:
  * Sized on **Dollar-at-Risk** (1.0% to 1.5% portfolio equity risk) rather than cash cost:
    $$\text{Shares to Buy} = \lfloor \frac{\text{Risk Budget}}{\text{Entry Price} - \text{Stop Price}} \rfloor$$
* **20% Capital Allocation Ceiling Safeguard**:
  * Automatically caps single-position value to **maximum 20% of account capital**. If a stop is ultra-tight (e.g. $\$100$ price, $\$99$ stop), it prevents over-allocating account equity while preserving risk limits.
* **Two-Tranche "Scale & Trail" Exit Engine**:
  * **Tranche 1 (50% Shares)**: Automatically scaled out at **TP1 (+2.5 R:R)**, locking in cash gains.
  * **Tranche 2 (Remaining 50% Shares)**: Stop price automatically moves to **Breakeven (Entry Price)** and trails along the **rising 50-day EMA** to capture multi-month trend runners.
* **Gap-Down Slippage Modeling**:
  * In the audit engine, if the day's Open is below the technical stop, the exit fill is recorded at the **Open price** rather than assuming a perfect stop exit.
* **Independent Audit Ledger (`data/stock_trades_log.json`)**:
  * Maintains state for equity paper trades separately from options. Computes independent **Equity Win Rate %**, **Profit Factor**, and **Gross Realized Gains**.

### 5. 💰 Stage 1 Macro-Adaptive Portfolio Allocator & Cash Buffering
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
* **Integer Sizing & Small-Account Fallback**:
  * Enforces strict integer contract floors ($\lfloor \text{Budget} / \text{Cost} \rfloor$) and share counts.
  * If budget is insufficient, safely rolls cash to dry powder without over-allocating.
* **Portfolio Capacity Reached Guardrail**:
  * When open commitments + cash floor reach 100%, today's tranche is throttled to `$0` and the terminal displays a prominent warning banner.

### 6. 🗄️ LocalStorage Personal Portfolio Engine (`abi_my_portfolio`)
Zero-cost, serverless client-side state persistence:
* **Interactive UI Toggles**: Click `[+ Mark as Taken]` on any recommendation in Table 1 or Table 2 to log it directly into your portfolio. The button dynamically updates to `[✓ In My Portfolio · N ct / sh]`.
* **Table 3 Ledger Integration**: Click `[+ Track]` on any historical trade in the ledger. Filter the entire ledger using the `[★ My Portfolio]` button to inspect only your active holdings.
* **Instant Reactivity**: Toggling a trade immediately recalculates your committed capital, free liquid cash, and today's deployable tranche in real time.

---

## 🖥️ Terminal Interface & Core Modules

### Tab 1: 🎯 Key Trading Recommendations & Portfolio Management
* **Executive Market Briefing**: Real-time Action Verdict badge, 4-index chips (`SPY`, `QQQ`, `RSP`, `IWM`), macro narrative, sector capital flows, and execution mandates.
* **Strategy Asset Class Switcher**:
  `[● 🎯 Options Alpha Radar (Spreads & LEAPS)]` | `[📈 Equity / Stock Radar (Shares & Trailing)]`
  * Switches Table 1 between **Bull Call Spreads (or Bear Put Hedges)** and **Tactical Equity Swings**.
  * Switches Table 2 between **Call LEAPS (Jan 2028)** and **Core Secular Stock Accumulation**.
* **Quant Rejection Funnel Ribbon**: Real-time diagnostic ribbon detailing why tickers were excluded:  
  `[Scanned]` $\rightarrow$ `[Below Floor]` $\rightarrow$ `[Stale Reclaim]` $\rightarrow$ `[Low Runway]` $\rightarrow$ `[Pending EOD]` $\rightarrow$ `[N Illiquid Opts Skipped]` $\rightarrow$ `[Qualified Fills]`.
* **Stage 1 Allocator Bar**: 4-pillar capital sizing, architecture modes, dynamic dry powder buffer, tranche pacing, and capacity alerts.
* **Table 1: Directional Swings**: Ticker, Sector, Price, Stop, Targets, R:R, Velocity, RVOL, IV Rank, Verified Options Liquidity (`OI: 720/480 · Vol: 115`), Sizing, and Limit Order Tickets.
* **Table 2: Strategic Core Accumulation**: Multi-quarter compounders with 200 SMA macro stops, Stage 2 trend badges, IV Rank, and exact execution tickets.
* **Table 3: Universe Telemetry Monitor**: Full searchable database of 493+ constituents with live filters for qualified setups, moving average distances (`vs EMA50`, `vs MA150`, `vs 200MA`), Beta, and ADR%.

### Tab 2: 🌐 Macroeconomic Board (Institutional Market Telemetry)
* **2D Momentum Quadrant**: Interactive scatter plot of 5-Day vs. 20-Day momentum across 25 ETFs with color-coded style buckets (Growth, Cyclical, Defensive) and labeled quadrants (*Strong & Holding*, *Turning Up*, *Fading*, *Weak*).
* **Dual-Horizon Breadth Switcher**: Seamless toggle between `[LIVE SESSION]` (intraday retests) and `[CUMULATIVE (ALL-TIME)]` (historical database).
* **ETF Ladder — VS EMA50**: Diverging bar chart tracking all 25 sector ETFs centered on the 0% baseline.
* **Sector Strength Score**: 10-point scoring model with sort toggles for `Strength`, `Win %`, and `Avg Ret`.
* **★ Rotating In**: 8 hot sector cards dynamically sorted by active bounce concentration and average support return.
* **Sub-Industry Performance Matrix**: Drilldown across 90 sub-sectors with **Conviction Badges** (`GOOD — Trade 3rd+`, `MODERATE — Selective`, `WEAK — Skip or Half`, `AVOID — Sector Failing`).
* **Support Retest Distribution**: Breakdown across EMA50, Double Bottoms (DB), Optimal Trade Entry (OTE Fib 0.618–0.786), and MA150.
* **Daily Activity Stacked Bars**: Color-coded daily support retests over 7, 14, 30, or all sessions.
* **Global Click-to-Filter Engine**: Clicking any sector pill, card, ladder bar, or table row instantly filters all tables, charts, and metrics simultaneously.

### Tab 3: 📈 Performance & Audit Log
* **Strategy Alpha Comparison Ribbon**: Side-by-side performance benchmarking between the **Options Book** and the **Equity Book**:
  * Options Book: `Win Rate: 60.0% │ Profit Factor: 1.99x │ Realized ROI: +29.7%`
  * Equity Book: `Win Rate: 62.5% │ Profit Factor: 2.15x │ Realized ROI: +17.8%`
  * Net Alpha Spread: `+11.9% Options Excess Return over Equities`
* **Ledger Book Switcher**: Toggle between `[🎯 Options Ledger]` (`data/trades_log.json`) and `[📈 Stock Ledger]` (`data/stock_trades_log.json`).
* **Interactive Portfolio Capital & Timeframe Simulator**: Configurable capital ($10k to $100k), inception dates (All-Time, July 1+, Aug 1+), and position sizing models (2% Risk, 10% Cash, $1,000 Flat).
* **Automated Trade Ledger**: Tracks paper trades against live High, Low, and Close market prices with automated breakeven trailing (+2.5 R:R) and 50 EMA trend trailing.
* **`[★ My Portfolio]` Status Filter**: Isolates only the trades you have marked as taken.
* **Root-Cause Loss Attribution Engine**: Automatically diagnoses why a stopped-out trade failed (`[MACRO CONTAGION]`, `[SECTOR ROTATION]`, `[EARNINGS GAP]`, `[STAGNATION]`, `[IDIOSYNCRATIC]`).

---

## 📊 Endpoints & Data Schema

| Resource | Path | Description |
| :--- | :--- | :--- |
| **Visual Dashboard** | `https://<user>.github.io/<repo>/` | Interactive 3-tab web terminal |
| **Latest Telemetry API** | `https://<user>.github.io/<repo>/data/latest.json` | Master payload (options & stock recs, macro, benchmark matrix) |
| **Options Audit Ledger** | `https://<user>.github.io/<repo>/data/trades_log.json` | Persistent stateful options paper-trade ledger & metrics |
| **Equities Audit Ledger** | `https://<user>.github.io/<repo>/data/stock_trades_log.json` | Persistent stateful equity paper-trade ledger & metrics |
| **Historical Breadth Index** | `https://<user>.github.io/<repo>/data/summary.json` | Rolling daily macro breadth and regime history |
| **Daily Snapshots** | `https://<user>.github.io/<repo>/data/history/YYYY-MM-DD.json` | Full granular historical daily archives |

---

## ⚙️ Automated GitHub Actions Workflow

Configured in `.github/workflows/scan.yml` running on Ubuntu runners with `contents: write` permissions:

* **05:45 MST (12:45 UTC) Mon–Fri**: Pre-market refresh ahead of the 06:15 MST Spark options scan.
* **Hourly (13:30 – 20:30 UTC Mon–Fri)**: Real-time scan during US market hours (06:30 AM – 01:30 PM MST) logging live price reclaims.
* **14:00 MST / 17:00 EDT (21:00 UTC) Mon–Fri**: Official market close, retention pruning, and final audit ledger update.
* **Historical Backfill Engine**: Supports in-memory backfilling via `workflow_dispatch` input (`backfill_days: 90`).
* **1-Year Retention Auto-Flush**: Automatically purges historical snapshots older than 365 days, capping repository growth at ~15MB–20MB.
* **Circuit Breaker**: Prevents overwriting valid telemetry if an upstream data feed provider glitch returns 0 tickers.

---

## 🧪 Comprehensive Testing & Verification Suite

A rigorous automated testing suite of **57 automated tests** (39 Python unit/functional tests + 18 Node.js end-to-end DOM simulation tests) is located in `/tests`:

```bash
# 1. Run full Python test suite (Technical, Options, Scanner, Allocator, Equity Engine)
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 tests/test_stock_engine.py -v

# 2. Run Node.js end-to-end DOM simulation & localStorage test suite
node tests/test_allocator_node.js
```

### Test Coverage:
1. **Mathematical & Indicator Integrity**: Validates `EMA 10/21/50/200`, `SMA 150/200`, `RSI(14)`, `MACD(12,26,9)`, `ADR%`, 60-day rolling `Beta` vs. `SPY`, 20-day `RVOL`, 1-year `IV Rank`, and 30-week `Weekly Stage` slope.
2. **Benchmark Confluence & Market Commentary**: Validates 4-index confluence matrix across all 16 permutation states ($2^4$) and checks dynamic narrative generation across all four action verdict regimes.
3. **Options Liquidity & Waterfall Queue**: Validates `verify_and_fetch_live_options()` across calls, puts, and LEAPS ($\ge 250\text{ OI}$, $\le 15\%$ spread width), and tests automatic next-in-line skipping on illiquid strikes.
4. **Equity Strategy Engine (`engine/stocks.py`)**: Validates fixed fractional dollar-at-risk share sizing, 20% capital ceiling safeguard, Two-Tranche Scale & Trail exits (50% TP1 / 50% 50 EMA trail), gap-down slippage modeling, and JSON persistence.
5. **Portfolio Allocator & LocalStorage State**: Validates capital sizing across tiers ($10k to $100k), dynamic dry powder adjustments, 33% session tranche pacing, integer contract rounding, small-account budget protection, position toggling, and the capacity ceiling guardrail.
6. **Strategy Alpha Comparison & UI Switches**: Validates Tab 1 Asset Class Switcher (`[Options]` $\leftrightarrow$ `[Stocks]`), Tab 3 Alpha Comparison Ribbon, and Tab 3 Ledger Switcher.
