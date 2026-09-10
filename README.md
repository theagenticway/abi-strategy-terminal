# ABI Strategy Terminal & Options Alpha Radar

Institutional-grade quantitative market telemetry, multi-index benchmark confluence engine, asymmetric options trade structuring radar, dynamic portfolio allocator, and automated trade performance auditor.

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
│  BULLISH ALPHA MODULE (LONG) │        │  DOWNSIDE HEDGE MODULE (PUT) │
├──────────────────────────────┤        ├──────────────────────────────┤
│ • 45–60 DTE Bull Call Spreads│        │ • 30–45 DTE Bear Put Spreads │
│ • Jan 2028 Core LEAPS        │        │ • Overhead Resistance Retest │
│ • 21-Day Theta Cliff Date    │        │ • Structural Stage 4 Filters │
│ • Natural Mid-Price Routing  │        │ • Asymmetric Downside R:R    │
└──────────────────────────────┘        └──────────────────────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │   STAGE 1 MACRO-ADAPTIVE PORTFOLIO ALLOCATOR │
         │  • Total Capital Sizing ($10k to $100k+)     │
         │  • Core (LEAPS) vs. Satellite (Spread) Ratio │
         │  • Dynamic Dry Powder Floor (15% to 50%+)    │
         │  • 33% Session Tranche Pacing Limit          │
         │  • Integer Contract Sizing (Small Account OK)│
         │  • Browser-Persistent LocalStorage Tracking  │
         │  • Portfolio Capacity Reached Guardrail      │
         └──────────────────────┬───────────────────────┘
                                │
                                ▼
         ┌──────────────────────────────────────────────┐
         │       AUTOMATED PERFORMANCE AUDIT LEDGER     │
         │  • State Tracking in data/trades_log.json    │
         │  • Automated Breakeven Trailing (+2.5 R:R)   │
         │  • Root-Cause Loss Attribution Engine        │
         │  • Multi-Tier Interactive Growth Simulator   │
         └──────────────────────────────────────────────┘
```

---

## ⚡ Core Quantitative Intelligence Engines

### 1. 🏛️ Executive Market Briefing & 4-Tier Action Verdict
Synthesizes all ingested quantitative telemetry into an executive daily briefing at the top of the terminal with **zero hardcoding**:

* **4-Tier Action Verdict Matrix**:
  * 🟢 **AGGRESSIVE BUY (Risk-On Expansion)**: 4 of 4 benchmark indices $> 50$ EMA, Breadth $\ge 0.55$. Full 33% daily tranche deployment across high-velocity Bull Spreads and Core LEAPS. Baseline 15% cash reserve.
  * 🟡 **CAUTIOUS BUY (Selective Cyclical Rotation)**: QQQ $< 50$ EMA, but SPY or RSP $> 50$ EMA. Tech under distribution, cyclicals holding. Longs permitted **only** in leading non-tech sectors. 25% cash reserve.
  * 🟠 **HOLD / PRESERVE (Chop & Retest)**: Broad market breadth $< 0.35$ or narrow mega-cap masking. Zero new long commitments. Trail stops on open winners; 35% cash buffer.
  * 🔴 **DEFENSIVE / HEDGE (Systemic Breakdown)**: SPY & RSP $< 50$ EMA. 100% freeze on long calls; deploy tactical Bear Put Spreads or sit in 50%–70% cash.
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

### 3. 💰 Stage 1 Macro-Adaptive Portfolio Allocator & Cash Buffering
Transforms the terminal from an isolated screener into an active portfolio construction system:
* **Pillar 1: Total Portfolio Capital**: Configurable account sizing ($10k, $25k, $50k, $100k, and custom numeric input).
* **Pillar 2: Allocation Architecture**:
  * *Balanced Core/Satellite* (60% LEAPS / 40% Spreads).
  * *Tactical Momentum* (80% Spreads / 20% LEAPS).
  * *Secular Compounding* (80% LEAPS / 20% Spreads).
  * *Macro-Adaptive Auto-Tilt* (Risk-On: 35/65, Mixed: 50/50, Risk-Off: 80/20).
* **Pillar 3: Dynamic Dry Powder (Cash Buffer)**:
  * *Automated Macro Buffer*: 15% (Risk-On), 25% (Mixed), 50%–70% (Risk-Off).
  * *Manual Overrides*: Fixed 20%, Fixed 30%, Fully Deployed (0%).
* **Pillar 4: Tranche Pacing & Capital Protection**:
  * Real open risk deduction: $\text{Free Liquid Cash} = \max(0, \text{Total Capital} - \text{Committed Risk} - \text{Cash Floor})$.
  * Single-session ceiling: $\text{Today's Tranche} = \min(\text{Free Liquid Cash}, \text{Total Capital} \times 0.33)$.
* **Integer Contract Rounding & Small-Account Fallback**:
  * Enforces $\text{Contracts} = \lfloor \text{Budget} / \text{Cost} \rfloor$.
  * If contract cost exceeds allocated budget (e.g. $6,800 NVDA LEAPS on a $10k account), safely displays: `🟡 0 Contracts (Budget Below 1ct) — Rolled to Dry Powder`.
* **Portfolio Capacity Reached Guardrail**:
  * When open commitments + cash floor reach 100%, today's tranche is throttled to `$0` and the terminal displays a prominent warning banner.

### 4. 🗄️ LocalStorage Personal Portfolio Engine (`abi_my_portfolio`)
Zero-cost, serverless client-side state persistence:
* **Interactive UI Toggles**: Click `[+ Mark as Taken]` on any recommendation in Table 1 or Table 2 to log it directly into your portfolio. The button dynamically updates to `[✓ In My Portfolio · N ct ($X)]`.
* **Table 3 Ledger Integration**: Click `[+ Track]` on any historical trade in the ledger. Filter the entire ledger using the `[★ My Portfolio]` button to inspect only your active holdings.
* **Instant Reactivity**: Toggling a trade immediately recalculates your committed capital, free liquid cash, and today's deployable tranche in real time.

### 5. 🛡️ Multi-Directional Asymmetric Options Radar (Spreads & LEAPS)
* **Tactical Bull Call Spreads (45–60 DTE)**:
  * High-velocity momentum setups: D0–D2 reclaims, $\ge 5\%$ overhead runway to 200 MA, and tight invalidation stops below the 50 EMA.
  * Long Call ($\approx 0.55–0.60$ Delta), Short Call ($\approx 0.30–0.35$ Delta at TP1), 21-day theta cliff, and natural mid-price routing tickets.
* **Strategic Core Accumulation LEAPS (Jan 2028, ~500 DTE)**:
  * Deep-ITM call options ($\approx 0.75–0.80$ Delta, ~80% of stock price) on secular institutional leaders. Minimal theta decay (~$0.01/day).
  * Requires full Stage 2 trend stack ($\text{Price} \ge \text{EMA 50} \ge \text{SMA 150} \ge \text{SMA 200}$), rising 200 MA, low beta ($\le 2.2$), and positive free cash flow.
* **Tactical Downside Hedges (Bear Put Spreads 30–45 DTE)**:
  * Directional Mode Switcher on Table 1: `[⚡ Bull Spreads]` $\leftrightarrow$ `[🛡️ Bear Put Hedges]`.
  * Screens Stage 4 downtrend stocks in bottom ETF sectors failing overhead resistance (EMA21 or EMA50) with bearish rejection candles, RSI $< 52$, and negative MACD.
  * Long Put ($\approx 0.55$ Delta ITM), Short Put ($\approx 0.30$ Delta OTM near target support).

### 6. 🔬 Institutional Microstructure & Indicator Architecture
* **RVOL (Relative Volume)**: Compares current volume to trailing 20-day Average Daily Volume. Flags low-volume fakeouts ($< 0.8\times$) and confirms institutional accumulation ($\ge 1.0\times$ to $1.5\times+$).
* **Implied Volatility Rank (IV Rank)**: 52-week volatility range ($0–100$). Categorizes cheap volatility ($< 35\%$, debit spreads favorable) vs. elevated volatility ($> 65\%$, credit spreads favorable).
* **Stan Weinstein Weekly Stage Filter**: Checks 30-week (150-day) structural moving average slope to verify Stage 2 expansion vs. Stage 4 distribution.
* **Multi-Timeframe 4H Confluence**: Verifies 4-hour candle progression before confirming daily reclaims.
* **45-Day Corporate Earnings Blackout**: Prevents entering long gamma setups within 45 days of earnings reports to avoid binary IV crush.

---

## 🖥️ Terminal Interface & Core Modules

### Tab 1: 🎯 Key Trading Recommendations & Portfolio Management
* **Executive Market Briefing**: Real-time Action Verdict badge, 4-index chips (`SPY`, `QQQ`, `RSP`, `IWM`), macro narrative, sector capital flows, and execution mandates.
* **Quant Rejection Funnel**: Real-time diagnostic ribbon detailing why tickers were excluded (`Scanned` $\rightarrow$ `Below Floor` $\rightarrow$ `Stale Reclaim` $\rightarrow$ `Low Runway` $\rightarrow$ `Pending EOD` $\rightarrow$ `Qualified`).
* **Stage 1 Allocator Bar**: 4-pillar capital sizing, architecture modes, dynamic dry powder buffer, tranche pacing, and capacity alerts.
* **Table 1: Directional Swings (Bull Call Spreads & Bear Put Spreads)**: Filterable setups with ticker, sector, price, stop, targets, R:R, velocity, RVOL, IV Rank, execution badges (`🟢 CONFIRMED` vs. `🟡 PENDING EOD`), integer contract sizing, and limit order tickets.
* **Table 2: Strategic Core Accumulation (Call LEAPS — Jan 2028)**: Secular compounders with macro stops (3% below 200 MA), Stage 2 trend badges, IV Rank, and exact LEAPS contract tickets.
* **Table 3: Universe Telemetry Monitor**: Full searchable database of 493+ constituents with live filters for qualified setups, moving average distances (`vs EMA50`, `vs MA150`, `vs 200MA`), Beta, and ADR%.

### Tab 2: 🌐 Macroeconomic Board (Institutional Market Telemetry)
* **2D Momentum Quadrant**: Interactive scatter plot of 5-Day vs. 20-Day momentum across 25 ETFs with color-coded style buckets (Growth, Cyclical, Defensive) and labeled quadrants (*Strong & Holding*, *Turning Up*, *Fading*, *Weak*).
* **Dual-Horizon Breadth Switcher**: Seamless toggle between `[LIVE SESSION]` (intraday retests) and `[CUMULATIVE (ALL-TIME)]` (historical database).
* **ETF Ladder — VS EMA50**: Diverging bar chart tracking all 25 sector ETFs centered on the 0% baseline.
* **Sector Strength Score**: 10-point scoring model with sort toggles for `Strength`, `Win %`, and `Avg Ret`.
* **★ Rotating In**: 8 hot sector cards tracking bounce concentration, 3-day recency, and average support return.
* **Sub-Industry Performance Matrix**: Drilldown across 90 sub-sectors with **Conviction Badges** (`GOOD — Trade 3rd+`, `MODERATE — Selective`, `WEAK — Skip or Half`, `AVOID — Sector Failing`).
* **Support Retest Distribution**: Breakdown across EMA50, Double Bottoms (DB), Optimal Trade Entry (OTE Fib 0.618–0.786), and MA150.
* **Daily Activity Stacked Bars**: Color-coded daily support retests over 7, 14, 30, or all sessions.
* **Global Click-to-Filter Engine**: Clicking any sector pill, card, ladder bar, or table row instantly filters all tables, charts, and metrics simultaneously.

### Tab 3: 📈 Performance & Audit Log
* **Performance KPI Ribbon**: Live Cumulative Win Rate %, Profit Factor, Total Recommendations, Active Open Positions, and Average Holding Days.
* **Interactive Portfolio Capital & Timeframe Simulator**:
  * Configurable starting capital ($10k, $25k, $50k, $100k, or custom).
  * Inception date selector (All-Time, July 1+, August 1+).
  * Dynamic sizing models (2% Risk, 10% Cash, $1,000 Flat).
  * Real-time tracking of simulated portfolio equity, realized gains, peak deployed capital, and cash left.
* **Automated Trade Ledger**: Tracks paper trades against live High, Low, and Close market prices with automated breakeven trailing (+2.5 R:R).
* **`[★ My Portfolio]` Status Filter**: Isolates only the trades you have marked as taken, displaying your personalized open risk and return.
* **Root-Cause Loss Attribution Engine**: Automatically diagnoses why a stopped-out trade failed:
  * `[MACRO CONTAGION]`: Broad index selloff (SPY/QQQ dropped $>1.2\%$ or broke 50 EMA).
  * `[SECTOR ROTATION]`: Institutional outflows broke sector ETF support ($>1.2\%$ drop).
  * `[EARNINGS GAP]`: Binary earnings gap-down.
  * `[STAGNATION EXIT]`: Position stalled past 7–10 day velocity window.
  * `[IDIOSYNCRATIC]`: Stock broke down on volume despite healthy sector backdrop.

---

## 📊 Endpoints & Data Schema

| Resource | Path | Description |
| :--- | :--- | :--- |
| **Visual Dashboard** | `https://<user>.github.io/<repo>/` | Interactive 3-tab web terminal |
| **Latest Telemetry API** | `https://<user>.github.io/<repo>/data/latest.json` | Complete self-contained master payload |
| **Trade Audit Ledger** | `https://<user>.github.io/<repo>/data/trades_log.json` | Persistent stateful paper-trade ledger & metrics |
| **Historical Breadth Index** | `https://<user>.github.io/<repo>/data/summary.json` | Rolling daily macro breadth and regime history |
| **Daily Snapshots** | `https://<user>.github.io/<repo>/data/history/YYYY-MM-DD.json` | Full granular historical daily archives |

---

## ⚙️ Automated GitHub Actions Workflow

Configured in `.github/workflows/scan.yml` running on Ubuntu runners with `contents: write` permissions:

* **05:45 MST (12:45 UTC) Mon–Fri**: Pre-market refresh ahead of the 06:15 MST Spark options scan.
* **Hourly (13:30 – 20:30 UTC Mon–Fri)**: Real-time scan during US market hours (06:30 AM – 01:30 PM MST) logging live price reclaims.
* **14:00 MST / 17:00 EDT (21:00 UTC) Mon–Fri**: Official market close, retention pruning, and final audit ledger update.
* **Historical Backfill Engine**: Supports in-memory backfilling via `workflow_dispatch` input (`backfill_days: 30`).
* **1-Year Retention Auto-Flush**: Automatically purges historical snapshots older than 365 days, capping repository growth at ~15MB–20MB.
* **Circuit Breaker**: Prevents overwriting valid telemetry if an upstream data feed provider glitch returns 0 tickers.

---

## 🧪 Comprehensive Testing & Verification Suite

A rigorous automated testing suite of **47 automated tests** (33 Python unit/functional tests + 14 Node.js end-to-end DOM simulation tests) is located in `/tests`:

```bash
# 1. Run full Python unit, functional, and indicator test suite
python3 -m unittest discover -s tests -p "test_*.py" -v

# 2. Run Node.js end-to-end DOM simulation & localStorage test suite
node tests/test_allocator_node.js
```

### Test Coverage:
1. **Mathematical & Indicator Integrity**: Validates `EMA 10/21/50/200`, `SMA 150/200`, `RSI(14)`, `MACD(12,26,9)`, `ADR%`, 60-day rolling `Beta` vs. `SPY`, 20-day `RVOL`, 1-year `IV Rank`, and 30-week `Weekly Stage` slope.
2. **Benchmark Confluence & Market Commentary**: Validates 4-index confluence matrix across all 16 permutation states ($2^4$) and checks dynamic narrative generation across all four action verdict regimes (`AGGRESSIVE BUY`, `CAUTIOUS BUY`, `HOLD / PRESERVE`, `DEFENSIVE / HEDGE`).
3. **Pattern Recognition & Downside Hedges**: Verifies `detect_retrace_pattern`, `calculate_reclaim_velocity`, `detect_resistance_rejection`, and `model_bear_put_spread` strike geometry and DTE boundaries.
4. **Options Structuring & Blackouts**: Validates vertical strike intervals, 21-day theta cliff, 45-day earnings blackout window, 200 MA clearance badges, and natural mid-price order routing.
5. **Portfolio Allocator & LocalStorage State**: Validates capital sizing across tiers ($10k to $100k), dynamic dry powder adjustments, 33% session tranche pacing, integer contract rounding, small-account budget protection, position toggling, and the capacity ceiling guardrail.
6. **Data Schemas & DOM Integrity**: Asserts non-null labels, `.nojekyll` static file serving, and 50+ essential interactive DOM elements.
