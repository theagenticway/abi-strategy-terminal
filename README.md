# ABI Strategy Terminal & Quantitative Execution Engine

Institutional-grade quantitative market telemetry, multi-index benchmark confluence engine, tri-portal execution architecture (**Options Terminal**, **Dedicated Stocks Terminal**, and **365-Day Historical Signal Archive**), scalable multi-horizon portfolio allocator ($100K baseline scaling dynamically to $500K+), 3-pronged strategic execution framework, price-gated runner protection, relative-strength eviction, and automated multi-asset trade lifecycle auditor.

Engineered to replace fragmented TradingView alerts, third-party webhooks, and manual spreadsheets with an autonomous, zero-cost quantitative pipeline hosted entirely on **GitHub Actions** and **GitHub Pages**.

For the complete, granular data dictionary, yfinance field mapping, and mathematical formula breakdowns, see:  
📖 **[`DATA_METRICS_AND_SCORING_ARCHITECTURE.md`](DATA_METRICS_AND_SCORING_ARCHITECTURE.md)**

---

## 🏛️ Capital Architecture & The Decoupled Twin-Engine Model

The engine operates two fully decoupled, independent portfolios to prevent cross-asset competition, avoid liquidity bottlenecks, and allow high-conviction mega-cap leaders and high-beta momentum stocks to be traded without capital distortion:

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
  │ • Capital / Slot: ~$4,500 – $6,000   │                       │ • Capital / Slot: ~$4,500 – $6,000   │
  │ • Dollar-at-Risk: $1,000 max (1.0%)  │                       │ • Dollar-at-Risk: $350 – $500 (0.45%)│
  │ • Vehicles: Spreads & Multi-Yr LEAPS │                       │ • Vehicles: Common Shares (Cash)     │
  │ • Tactical Sprint: 10–12 Slots       │                       │ • Tactical Sprint: 10–12 Slots       │
  │ • Strategic Anchor: 6–8 Slots        │                       │ • Strategic Anchor: 6–8 Slots        │
  │ • Relative-Strength Eviction Enabled │                       │ • Relative-Strength Eviction Enabled │
  └──────────────────────────────────────┘                       └──────────────────────────────────────┘
```

### A. Position Capacity & Heat Management
* **Decoupled Execution Pools**: The Stock Engine and Options Engine scan the 500-constituent universe independently. An equity recommendation does not consume an options slot, and high-dollar mega-caps (e.g., NVDA, MSFT, META, LLY) can be traded via LEAPS or shares without starving other positions.
* **Decoupled Sprint vs. Anchor Books**: Within each portfolio, capacity is split between:
  * **Tactical Sprint Book (10–12 slots)**: 45–90 DTE vertical spreads and 10–22 day stock swings for high capital velocity.
  * **Strategic Anchor Book (6–8 slots)**: January 2028 multi-year LEAPS and Stage 2 secular compounders with 200 SMA trailing stops. Multi-month holdings never freeze tactical trading bandwidth.
* **Scalable Capital**: Starting baseline is **$100,000 per book** ($200,000 terminal total), with position sizing and capital allocation formulas designed to scale seamlessly up to **$500,000 or higher**.

### B. Dollar-at-Risk Position Sizing
Every recommendation is sized strictly on **Dollar-at-Risk (Capital Protection First)**:
* **Options Book ($100K Baseline)**: Max risk per trade is hard-capped at **$1,000 (1.0% account equity)**.
  * *Vertical Spreads*: Buy 4–5 contracts @ $2.00–$2.50 net debit ($800–$1,000 max risk).
  * *Call LEAPS*: 1 contract on secular leaders ($3,500–$5,000 capital deployed), protected by an invalidation stop at the 50 EMA / 200 SMA.
  * *Scaling*: On a $500K account, risk scales proportionally to $5,000 per trade (1.0%).
* **Stock Book ($100K Baseline)**: Max risk per trade is sized to **$350–$500 (0.35%–0.50% account equity)**.
  * Sized via:
    $$\text{Shares} = \min\left(\left\lfloor \frac{\text{Max Risk Dollars}}{\text{Entry Price} - \text{Stop Price}} \right\rfloor, \left\lfloor \frac{\text{Max Capital Ceiling (6\%)}}{\text{Entry Price}} \right\rfloor\right)$$
  * Sizing shares to a 7% technical stop risks only ~$350–$420 on a $5,000–$6,000 position, providing high-beta equities ample breathing room while bounding drawdown.
  * *Scaling*: On a $500K account, risk scales to $2,250 (0.45%) and the 6% capital ceiling scales to $30,000.

---

## 🎯 The 3-Pronged Strategic Allocation Framework

The strategy engine divides all recommendations across three distinct holding horizons, each with tailored volatility metrics, holding targets, and stagnation rules:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       3-PRONGED MULTI-HORIZON FRAMEWORK                                          │
├─────────────────────────┬───────────────────────────────────┬────────────────────────────────────────────────────┤
│ STRATEGY PRONG          │ EQUITIES SPECIFICATION            │ DERIVATIVES SPECIFICATION (INCL. LEAPS)            │
├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤
│ 🚀 HIGH RISK (VELOCITY) │ • Holding Horizon: 10–22 sessions │ • Vehicles: 45–90 DTE Spreads OR 6–9 Mo ITM LEAPS │
│    "Momentum Sprint"    │ • Target: Beta >= 1.8, ADR >= 3.5%│ • Volatility: High IV Rank (60–85+) Rewarded       │
│    Capacity: 7-8 Slots  │ • Entry: D0-D1 Reclaim, RVOL>=1.8x│ • Max Risk: Bounded Stop at -8.0% Max Loss         │
│                         │ • Stop: max(ema50*0.985, p*0.92)  │ • Exit: 70% Max Profit or Day 10 Stagnation Stop   │
├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤
│ ⚖️ BALANCED (TACTICAL)   │ • Holding Horizon: 15–35 sessions │ • Vehicles: 60–120 DTE Spreads OR 9–15 Mo LEAPS    │
│    "Core Swing"         │ • Target: Beta 1.0-1.5, ADR 2-3.2%│ • Volatility: Sweet Spot IV Rank (35–65) Rewarded  │
│    Capacity: 7 Slots    │ • Entry: D0-D2 Reclaim, RVOL>=1.2x│ • Max Risk: Bounded Stop at -9.5% Max Loss         │
│                         │ • Stop: max(ema50*0.98, p*0.905)  │ • Exit: TP1 (+2.5 R:R), Day 14 Stagnation Stop     │
├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤
│ 🛡️ LOW RISK (CORE)       │ • Holding Horizon: 40–120+ sess.  │ • Vehicle: Jan 2028 Call LEAPS (~0.78-0.82 Delta)  │
│    "Compounder"         │ • Target: Beta <= 1.0, Pos. FCF   │ • Volatility: Low IV Rank (< 35) Mandatory         │
│    Capacity: 4-5 Slots  │ • Trend: Stage 2 Stack (50>150>200│ • Holding: 18–24+ Months (~500+ DTE)               │
│                         │ • Stagnation: None (Trend Stop)   │ • Exit: 3% below 200 SMA Macro Invalidation Stop   │
└─────────────────────────┴───────────────────────────────────┴────────────────────────────────────────────────────┘
```

---

## 🏃 Extended Runway & Price-Gated Stagnation Protocol

To eliminate arbitrary calendar selloffs on winning positions, the engine incorporates an institutional price-gated stagnation model:

```text
       ┌─────────────────────────────────────────────────────────────┐
       │             PRICE-GATED RUNNER PROTECTION                   │
       ├─────────────────────────────────────────────────────────────┤
       │ IF Close > Entry Price AND Close ≥ EMA50:                   │
       │   • BYPASS calendar exit (Day 10/14 kill-switch disabled)   │
       │   • TRAIL stop to Breakeven (Tier A: House Money)           │
       │   • EXTEND holding runway:                                  │
       │       - Sprints: Up to 22 trading sessions                  │
       │       - Balanced: Up to 35 trading sessions                 │
       │ ELSE IF Close < Stop OR Close < EMA50:                      │
       │   • Trigger immediate technical / stagnation exit           │
       └─────────────────────────────────────────────────────────────┘
```

* **Legacy Issue Resolved**: Previously, rigid Day 10 and Day 14 timers liquidated momentum leaders after initial +10% to +18% gains during normal pullbacks, truncating winners and hurting win rates.
* **House Money Protection**: Winning trades that cross Day 10 (Sprint) or Day 14 (Balanced) have their stop loss automatically trailed to **Breakeven (entry price)**, guaranteeing zero capital loss while allowing the second half of the position to run toward final targets.

---

## 🛑 Bounded Stop-Loss Limits (-8.0% Max Loss on Sprints)

To prevent high-beta equities from bleeding into severe drawdowns:
* **High-Risk Sprints**: Enforces `stop_price = round(max(ema50 * 0.985, price * 0.92), 2)`. Maximum technical risk is bounded at strictly **8.0% from entry**.
* **Balanced Swings**: Enforces `stop_price = round(max(ema50 * 0.98, price * 0.905), 2)`. Maximum technical risk is bounded at strictly **9.5% from entry**.
* **Immediate Failure Discipline**: If a stock breaks technical support, it is stopped out on Day 2 or 3 at -4% to -8%, rather than drifting down to -20% or -25% waiting for a calendar timer.

---

## 🔄 Dynamic Active Re-Scoring & Relative-Strength Eviction

The engine continuously audits all active holdings on every scan run to ensure capital stays concentrated in top relative-strength leaders:

```text
       ┌─────────────────────────────────────────────────────────────┐
       │             RELATIVE-STRENGTH EVICTION ENGINE               │
       ├─────────────────────────────────────────────────────────────┤
       │ 1. Continuous Re-Scoring: Live Alpha Score on all positions │
       │ 2. Health Tier Classification:                              │
       │    • Tier A: House Money (TP1 scaled, stop at breakeven)    │
       │    • Tier B: On-Track (Score ≥ 60.0, holding above EMA50)   │
       │    • Tier C: Stagnant (Score 50.0–59.9, stalled momentum)   │
       │    • Tier D: Eviction Eligible (Score < 55.0 for ≥ 2 days)  │
       │ 3. Hysteresis & Hurdle Gatekeeper:                          │
       │    • Near-Capacity Trigger: Active positions ≥ 85% (≥ 15/18) │
       │    • Replacement Hurdle: New candidate outscores by Δ ≥ 18  │
       │    • Outcome: Stagnant holding evicted -> capital recycled  │
       └─────────────────────────────────────────────────────────────┘
```

* **Hysteresis Guard**: Prevents premature churn by requiring at least 2 consecutive daily closes below 55.0 score (or prolonged stagnation $\ge 18$ days with score $< 58.0$).
* **Recycling Hurdle ($\Delta \ge 18.0$ pts)**: Existing holdings are only evicted if a verified incoming setup exceeds the incumbent by at least 18.0 Alpha points.
* **Audit Tagging**: Evicted trades are logged with `status = 'CLOSED_EVICTED'` and `exit_reason = 'Relative Strength Eviction'`, separate from technical stop-outs.

---

## 🗄️ 365-Day Historical Signal Archive Module

A dedicated historical signal registry and search portal (`archive.html`) captures and indexes all daily recommendations generated by the platform:

* **Automated Intraday Logging (`engine/archive.py`)**: Runs automatically inside `save_payloads()` on every scan execution and historical backfill.
* **Intraday Upsert Idempotency**: Running at 11:00 AM, 12:30 PM, and 2:00 PM ET updates that day's records in place rather than creating duplicate rows.
* **365-Day Rolling Pruning**: Automatically drops records older than 365 days on every pass, ensuring `data/recommendations_archive.json` stays permanently bounded ($\le 1\text{ MB}$) for high-speed client-side loading.
* **Standalone UI (`archive.html`)**:
  * Full-text search across Ticker, Company Name, Sector, and Strategy Structure.
  * Category filter pills (`All`, `🚀 High-Risk Sprint`, `⚖️ Balanced Swing`, `🛡️ Core Accumulation`, `🛑 Downside Hedge`).
  * Asset type filter (`All`, `Options Only`, `Stocks Only`).
  * Date range limits (`Last 7D`, `14D`, `30D`, `90D`, `365D Full Archive`).
  * Minimum Alpha Score filter (`≥ 70`, `≥ 80`, `≥ 85`, `≥ 90`).
  * One-click **JSON** and **CSV** dataset exports.
  * Linked in top navigation across `index.html`, `stocks.html`, and `archive.html`.

---

## ⚡ Universal Momentum Gating: RSI & MACD Hook

Every candidate recommendation across both the Stock Terminal and Options Terminal must satisfy two non-negotiable universal momentum criteria before qualification:

```text
       ┌─────────────────────────────────────────────────────────────┐
       │             UNIVERSAL MOMENTUM GATEKEEPERS                  │
       ├──────────────────────────────┬──────────────────────────────┤
       │ 1. RSI(14) ≥ 45.0 Floor      │ 2. MACD Histogram Hook       │
       │    • Strict Disqualification │    • Hist_t > Hist_t-1       │
       │    • Weeds out dead pullbacks│    • Confirms momentum curl  │
       └──────────────────────────────┴──────────────────────────────┘
```

1. **RSI(14) Floor ($\ge 45.0$)**: Eliminates exhausted pullbacks where selling pressure remains dominant. A stock below 45 RSI is disqualified regardless of 50 EMA proximity.
2. **MACD Histogram Hook ($\text{Hist}_t > \text{Hist}_{t-1}$)**: Verifies that momentum deceleration has ended and buying pressure is accelerating upward on the 50 EMA bounce.
3. **Qualification Display**: The terminal interface displays explicit visual badges for each qualification criterion (`RSI: 54.2 ≥45 🟢`, `MACD: ↗ Hook`, `β: 1.85`, `ADR: 3.8%`, `RVOL: 2.1x`) so traders can immediately verify why each setup qualified.

---

## 📊 Dual 100-Point Scoring Engines

### A. Cash Equities Alpha Composite Score (0 to 100)
Calculated in `engine/stocks.py` (`compute_alpha_composite_score`):

$$\text{Stock Alpha Score} = S_{\text{Reclaim}} (20) + S_{\text{RVOL}} (20) + S_{\text{Sector RS}} (15) + S_{\text{Beta/Elasticity}} (15) + S_{\text{Momentum}} (15) + S_{\text{Structure}} (15)$$

| Component | Weight | 🚀 High-Risk Sprint | ⚖️ Balanced Swing | 🛡️ Core Compounder |
| :--- | :---: | :--- | :--- | :--- |
| **1. Reclaim Velocity & Freshness** | **20 pts** | Day 0–1 Reclaim (20 pts) | Day 0–2 Reclaim (20 pts) | Stage 2 Stack (20 pts) |
| **2. Institutional RVOL** | **20 pts** | $\text{RVOL} \ge 2.0\times$ (20 pts) | $\text{RVOL} \ge 1.3\times$ (20 pts) | Steady Volume (15 pts) |
| **3. Sector Relative Strength (RS)** | **15 pts** | **Top-Quartile ETF & $\text{mom\_spread} > 0$** | **Top-Half ETF & $\text{mom\_spread} > 0$** | **Defensive/Secular Sector** |
| **4. Beta & Price Elasticity** | **15 pts** | **$\beta \ge 1.8$ & $\text{ADR} \ge 3.5\%$ (15 pts)** | **$\beta \in [1.0, 1.5]$ & $\text{ADR } 2.0 - 3.2\%$** | **$\beta \le 1.0$ (Low Drag, 15 pts)** |
| **5. Universal Momentum (RSI + MACD)**| **15 pts** | $\text{RSI} \ge 50$ + MACD Hist Hook | $\text{RSI} \ge 45$ + MACD Hist Hook | $\text{RSI} \ge 45$ + Bullish Stack |
| **6. Dow Theory Market Structure** | **15 pts** | Confirmed HH/HL (15 pts) | Emerging Base / HH (15 pts) | Multi-Month Base (15 pts) |

### B. Derivatives Options Alpha Radar Score (0 to 100)
Calculated in `engine/patterns.py` (`compute_options_alpha_score`):

$$\text{Options Alpha Score} = (\text{Directional Alpha} \times 0.35) + S_{\text{IV}} (20) + S_{\text{Liquidity}} (20) + S_{\text{Runway}} (15) + S_{\text{Momentum}} (10) + P_{\text{Earnings}}$$

| Component | Weight | High-Risk Sprint (45–90 DTE) | Balanced Swing (60–120 DTE) | Core LEAPS (Jan 2028) |
| :--- | :---: | :--- | :--- | :--- |
| **1. Directional Foundation** | **35 pts** | $0.35 \times \text{Stock Alpha}$ | $0.35 \times \text{Stock Alpha}$ | $0.35 \times \text{Stock Alpha}$ |
| **2. IV Rank Behavior** | **20 pts** | **High IV (60–85+) = 20 pts** | **Sweet Spot (35–65) = 20 pts**| **Low IV (< 35) = 20 pts** |
| **3. Contract Liquidity** | **20 pts** | $\text{OI} \ge 1000$, $\text{Spread} \le 5\%$ | $\text{OI} \ge 500$, $\text{Spread} \le 8\%$ | $\text{OI} \ge 250$, $\text{Spread} \le 10\%$|
| **4. 200 SMA Clearance Runway**| **15 pts** | Runway $\ge 8\%$ or Blue Sky | Runway $\ge 5\%$ or Blue Sky | Above 200 SMA Mandatory |
| **5. Universal MACD/RSI Hook** | **10 pts** | MACD Hist Hook + $\text{RSI} \ge 45$| MACD Hist Hook + $\text{RSI} \ge 45$| Stage 2 Trend Stack |
| **6. Earnings Blackout** | **Penalty** | $-35$ pts if inside trade DTE | $-35$ pts if inside trade DTE | $-35$ pts if inside 60 days |

---

## 🛡️ Risk & Execution Guardrails

1. **Dynamic Sector Capital Allocation (30%–35% Cap)**: Rather than an arbitrary rigid cap of 3 per sector, each 16–21 slot book permits up to **30%–35% total capital per sector** (~5 to 6 positions in the #1 relative strength sector). This fully captures institutional sector momentum while preventing hyper-concentration.
2. **The "Liquid Route" Auto-Switch (Options vs. Stock)**: If an options candidate meets all technical criteria (50 EMA, RSI, MACD, RVOL) but fails options chain liquidity ($\text{OI} < 500$ or spread $> 8\%$), the engine automatically routes the order ticket to the **Stock Portfolio as Common Shares** with a `🔄 AUTO-ROUTED FROM OPTIONS` badge.
3. **The 70% Max-Profit Harvest Rule**: Vertical spreads that achieve $\ge 70\%$ of maximum potential spread width or reach TP1 trigger an automated early harvest, locking in profits and freeing up portfolio slots days ahead of expiration.
4. **Strict Breakeven Accounting**: Closed trades with PnL == 0.00% are cataloged as `CLOSED_BREAKEVEN`, completely decoupled from profitable winners to preserve audit integrity and prevent average-winner dilution.
5. **Anti-Chop Re-Entry Cooldown**: When a position is stopped out, the ticker enters a mandatory **4-to-5 trading day re-entry blackout**, protecting the portfolio from range-bound whipsaw markets.

---

## ⏰ Active Market Hours Workflow (`.github/workflows/scan.yml`)

The scanner operates strictly during active US market trading hours to guarantee liquid, representative bid/ask quotes and eliminate erratic pre-market or post-market pricing artifacts:

```yaml
on:
  schedule:
    # 11:00 AM ET (15:00 UTC) Mon-Fri: Morning Momentum Confirmation
    - cron: '0 15 * * 1-5'
    # 12:30 PM ET (16:30 UTC) Mon-Fri: Midday Trend Follow-Through
    - cron: '30 16 * * 1-5'
    # 2:00 PM ET (18:00 UTC) Mon-Fri: Afternoon Institutional Setup Finalization
    - cron: '0 18 * * 1-5'
```

* **Concurrency Protection**: Uses `concurrency.group = abi-telemetry-scanner` with `cancel-in-progress: false` to prevent overlapping runs or git push collisions.
* **Auto-Pruned Artifacts**: Automatically commits telemetry, ledger logs, and the rolling 365-day recommendation archive in a single atomic git commit.

---

## 🧪 Comprehensive Testing & Verification Suite

A complete verification suite of **112 automated tests** across Python and Node.js guarantees structural, mathematical, and DOM integrity:

```bash
# 1. Run all Python unit & functional test suites (81 tests)
cd abi-strategy-terminal
for f in tests/test_*.py; do python3 "$f"; done

# 2. Run Node.js end-to-end simulation suites (31 tests)
node tests/test_allocator_node.js
node tests/test_stocks_page_node.js
node tests/test_archive_html.js
```

### Verified Test Matrix:
* **Active Re-Scoring & Health Tiers (`test_active_rescoring.py`)**: Validates continuous scoring and Tier A–D classification.
* **Relative-Strength Eviction (`test_eviction_and_decoupled_books.py`)**: Validates the 18-point hurdle, 85% capacity threshold, and sprint vs. anchor slot decoupling.
* **Regime Gating & Breakeven Accounting (`test_regime_and_breakeven.py`)**: Validates 4-index macro gating and zero-dilution breakeven logging.
* **365-Day Archive Module (`test_archive_module.py` & `test_archive_html.js`)**: Validates signal normalization, same-day upsert idempotency, 365-day boundary pruning, and DOM rendering.
* **Scalable Capital Sizing & Guardrails (`test_stock_engine.py`)**: Verifies $100K to $500K dynamic scaling, 1.0% dollar-at-risk options limits, and 6.0% stock capital ceilings.
* **Allocator & UI Simulations (`test_allocator_node.js` & `test_stocks_page_node.js`)**: Verifies multi-portfolio localStorage management, cross-terminal navigation, and execution ticket generation.
