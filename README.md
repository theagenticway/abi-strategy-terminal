# ABI Strategy Terminal & Quantitative Execution Engine

Institutional-grade quantitative market telemetry, multi-index benchmark confluence engine, dual-portal execution architecture (**Options Terminal** and **Dedicated Stocks Terminal**), scalable multi-horizon portfolio allocator ($100K baseline scaling dynamically to $500K+), 3-pronged strategic execution framework, and automated multi-asset trade lifecycle auditor.

Engineered to replace fragmented TradingView alerts, third-party webhooks, and manual spreadsheets with an autonomous, zero-cost quantitative pipeline hosted entirely on **GitHub Actions** and **GitHub Pages**.

For the complete, granular data dictionary, yfinance field mapping, and mathematical formula breakdowns, see:  
📖 **[`DATA_METRICS_AND_SCORING_ARCHITECTURE.md`](DATA_METRICS_AND_SCORING_ARCHITECTURE.md)**

---

## 🏛️ Capital Architecture & The Twin-Engine Model

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
  │ • Stagnation Stops: Day 10 / Day 14  │                       │ • Stagnation Stops: Day 10 / Day 14  │
  └──────────────────────────────────────┘                       └──────────────────────────────────────┘
```

### A. Position Capacity & Heat Management
* **Legacy Bottleneck Solved**: The legacy terminal enforced a flat ceiling of 7 concurrent open trades. A single slow-moving stock holding for 30+ sessions throttled the entire system.
* **Expanded Capacity**: Active holding capacity is expanded to **16 to 21 concurrent positions per portfolio** (32 to 42 active holdings across the entire terminal).
* **Dedicated Execution Pools**: The Stock Engine and Options Engine scan the 500-constituent universe independently. An equity recommendation does not consume an options slot, and high-dollar mega-caps (e.g., NVDA, MSFT, META, LLY) can be traded via LEAPS or shares without starving other positions.
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
│ 🚀 HIGH RISK (VELOCITY) │ • Holding Horizon: 10–14 sessions │ • Vehicles: 45–90 DTE Spreads OR 6–9 Mo ITM LEAPS │
│    "Momentum Sprint"    │ • Target: Beta >= 1.8, ADR >= 3.5%│ • Volatility: High IV Rank (60–85+) Rewarded       │
│    Capacity: 7-8 Slots  │ • Entry: D0-D1 Reclaim, RVOL>=1.8x│ • LEAPS: ~0.70-0.75 Delta, Uncapped High-Beta Run  │
│                         │ • Stagnation: Day 10 if < +1.0R   │ • Exit: 70% Max Profit or Day 10 Stagnation Stop   │
├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤
│ ⚖️ BALANCED (TACTICAL)   │ • Holding Horizon: 15–25 sessions │ • Vehicles: 60–120 DTE Spreads OR 9–15 Mo LEAPS    │
│    "Core Swing"         │ • Target: Beta 1.0-1.5, ADR 2-3.2%│ • Volatility: Sweet Spot IV Rank (35–65) Rewarded  │
│    Capacity: 7 Slots    │ • Entry: D0-D2 Reclaim, RVOL>=1.2x│ • LEAPS: ~0.75-0.80 Delta, High Sector RS Leaders  │
│                         │ • Stagnation: Day 14 if < 50% TP1 │ • Exit: TP1 (+2.5 R:R), Day 14 Stagnation Stop     │
├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤
│ 🛡️ LOW RISK (CORE)       │ • Holding Horizon: 40–120+ sess.  │ • Vehicle: Jan 2028 Call LEAPS (~0.78-0.82 Delta)  │
│    "Compounder"         │ • Target: Beta <= 1.0, Pos. FCF   │ • Volatility: Low IV Rank (< 35) Mandatory         │
│    Capacity: 4-5 Slots  │ • Trend: Stage 2 Stack (50>150>200│ • Holding: 18–24+ Months (~500+ DTE)               │
│                         │ • Stagnation: None (Trend Stop)   │ • Exit: 3% below 200 SMA Macro Invalidation Stop   │
└─────────────────────────┴───────────────────────────────────┴────────────────────────────────────────────────────┘
```

### Are LEAPS Included in All Three Strategies?
**YES.** LEAPS are tailored and available across all three strategy prongs:
1. **🚀 High-Risk Sprint LEAPS**: 6 to 9 months to expiration (~210 DTE), aggressive ~0.70–0.75 Delta strikes. Designed for explosive high-beta stocks ($\beta \ge 1.8$) to participate in rapid momentum runs with **uncapped upside** while avoiding the severe 30-day theta cliff.
2. **⚖️ Balanced Tactical LEAPS**: 9 to 15 months to expiration (~360 DTE), Deep-ITM ~0.75–0.80 Delta strikes on top-half sector relative strength leaders. Combines high directional sensitivity with minimal theta drag over a 15–25+ session holding horizon.
3. **🛡️ Core Secular LEAPS**: January 2028 multi-year contracts (18–24+ months, ~500+ DTE), Deep-ITM ~0.78–0.82 Delta strikes on institutional mega-cap compounders with low IV Rank ($< 35\%$). Governed strictly by the 200-day moving average macro stop with zero time-based stagnation pressure.

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
4. **Stagnation Exits (Recycling Portfolio Heat)**:
   * *High-Risk*: Position exits at Day 10 if profit $< +1.0\text{R}$.
   * *Balanced*: Position exits or stop tightens to breakeven at Day 14 if gain $< 50\%$ of distance to TP1.
   * *Core*: Governed strictly by trend stack integrity and the 200 SMA macro stop.
5. **Anti-Chop Re-Entry Cooldown**: When a position is stopped out, the ticker enters a mandatory **4-to-5 trading day re-entry blackout**, protecting the portfolio from range-bound whipsaw markets.

---

## 🖥️ Terminal Interface & Display Controls

### 3-Prong Strategic Allocation Filter Bars
Both portals feature interactive strategy prong filter buttons directly above the primary recommendation tables:
* **Options Terminal (`index.html`)**: `[ALL SETUPS]`, `[🚀 HIGH RISK (45–90d SPRINT)]`, `[⚖️ BALANCED (60–120d SWING)]`. Table 2 displays `[🛡️ CORE SECULAR COMPOUNDER]` Jan 2028 Call LEAPS.
* **Stocks Terminal (`stocks.html`)**: `[ALL SWINGS]`, `[🚀 HIGH RISK (10d SPRINT)]`, `[⚖️ BALANCED (15–25d SWING)]`. Table 2 displays `[🛡️ STRATEGIC CORE ACCUMULATION]` Common Shares.

### Real-Time Qualification Badges
Every row in both terminals renders granular indicator telemetry:
* **Prong Badge**: `🚀 HIGH RISK (SPRINT)`, `⚖️ BALANCED (SWING)`, or `🛡️ CORE (COMPOUNDER)`.
* **Oscillators**: `RSI: 54.2 (≥45 Floor 🟢)` and `MACD: ↗ Hook (Hist+ 🟢)`.
* **Elasticity**: `β: 1.85` and `ADR: 3.8%`.
* **Volume**: `RVOL: 2.1x Institutional`.
* **Velocity**: `D0 Reclaimed Today` / `D1 Confirmed`.
* **Runway**: `CLEAR (Above 200MA)` or exact `% Runway` to overhead resistance.
* **Options Liquidity**: `OI: 850/620 · Vol: 110` with live mid-price debits.

---

## 🧪 Automated Testing & Verification Suite

A comprehensive automated testing suite of **73 automated tests** (53 Python unit/functional tests + 20 Node.js DOM simulation tests) verifies mathematical, architectural, and visual integrity:

```bash
# 1. Run all Python unit & functional test suites
cd terminal/abi-strategy-terminal
python3 -m unittest discover -s tests -p "test_*.py"

# 2. Run Node.js end-to-end simulation suites
node tests/test_allocator_node.js
node tests/test_stocks_page_node.js
```

### Verified Test Matrix:
* **Scalable Capital Sizing**: Verifies $100K baseline scaling dynamically to $500K+ with dollar-at-risk share limits.
* **3-Prong Generators**: Verifies High-Risk Sprint (10d), Balanced Swing (15–25d), and Core Compounder (40–120d).
* **Stagnation Exits**: Verifies Day 10 ($<1.0\text{R}$) and Day 14 ($<50\%$ TP1) capital recycling stops.
* **Bifurcated IV Scoring**: Verifies High-Risk rewards high IV (60–85+), Balanced rewards sweet spot (35–65), and Core rewards low IV ($<35$).
* **Liquid Route Auto-Switch**: Verifies automatic re-routing of illiquid options to the common stock book.
* **Universal Momentum Hooks**: Verifies RSI $\ge 45$ floor and MACD histogram slope gating.
* **Capacity & Dynamic Sector Allocation**: Verifies 16–21 slot capacity per ledger and dynamic 30%–35% sector caps.
