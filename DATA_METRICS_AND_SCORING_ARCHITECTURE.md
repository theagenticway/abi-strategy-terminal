# Quantitative Data Pipeline, Derived Metrics & Dual Scoring Architecture

This document provides the definitive, production-grade technical specification for the **ABI Strategy Terminal & Quantitative Execution Engine**.

It details:
1. **The Twin-Engine Architecture**: Independent $100,000 Common Stock and $100,000 Options portfolios ($200,000 total capital base) operating with dedicated 16–21 position holding capacity.
2. **The 3-Pronged Strategy Framework**: Low Risk (Core Compounders), Balanced (Tactical Swings & LEAPS), and High Risk (High-Velocity Momentum Sprints) across cash equities and derivatives.
3. **Two-Level Macro vs. Sector Separation**: Macro Confluence as the Level 1 Top-Level Portfolio Governor vs. Sector Relative Strength as an active Level 2 scoring factor.
4. **Direct Beta & Elasticity Scoring**: Active incorporation of 60-day rolling Beta and ADR% into equity scoring (rewarding high beta in High-Risk; rewarding low beta in Core).
5. **Universal Indicator Telemetry**: Complete mathematical definitions for all raw inputs, derived moving averages, RVOL, Wilder's RSI(14) pullback floors, and MACD(12, 26, 9) histogram momentum hooks.
6. **Bi-Directional Execution & Natural Macro Steering**: Dynamic allocation between Call and Put spreads driven by the 4-Index Benchmark Matrix.
7. **Execution Guardrails**: Dynamic sector capital caps (30%–35%), the "Liquid Route" options-to-stock auto-switch, 70% max-profit spread harvesting, and anti-chop re-entry cooldowns.
8. **Persistence Lifecycle**: Complete left-to-right mapping and daily JSON storage vs. ephemeral memory boundaries.

---

## 1. Capital Architecture & The Twin-Engine Model

The engine operates two fully decoupled, independent portfolios to prevent cross-asset competition, avoid liquidity bottlenecks, and allow high-conviction mega-cap leaders to be traded without capital distortion:

```
                          ┌────────────────────────────────────────────────────────┐
                          │         ABI QUANTITATIVE EXECUTION ENGINE              │
                          │             Total Capital: $200,000                    │
                          └──────────────────────────┬─────────────────────────────┘
                                                     │
                     ┌───────────────────────────────┴───────────────────────────────┐
                     ▼                                                               ▼
  ┌──────────────────────────────────────┐                       ┌──────────────────────────────────────┐
  │      OPTIONS PORTFOLIO ($100,000)    │                       │       STOCK PORTFOLIO ($100,000)     │
  ├──────────────────────────────────────┤                       ├──────────────────────────────────────┤
  │ • Capacity: 16 – 21 Active Positions │                       │ • Capacity: 16 – 21 Active Positions │
  │ • Capital / Slot: ~$4,500 – $6,000   │                       │ • Capital / Slot: ~$4,500 – $6,000   │
  │ • Dollar-at-Risk: $1,000 max (1.0%)  │                       │ • Dollar-at-Risk: $350 – $500 (0.4%) │
  │ • Vehicles: Spreads & Deep LEAPS     │                       │ • Vehicles: Common Shares (Cash)     │
  └──────────────────────────────────────┘                       └──────────────────────────────────────┘
```

### A. Position Capacity & Heat Management
* **Legacy Bottleneck Solved**: The legacy terminal enforced a flat ceiling of 7 concurrent open trades. A single slow-moving stock holding for 40 days throttled the entire system.
* **Expanded Capacity**: Active holding capacity is expanded to **16 to 21 concurrent positions per portfolio** (32 to 42 active holdings across the entire terminal).
* **Dedicated Execution Pools**: The Stock Engine and Options Engine scan the 500-constituent universe independently. An equity recommendation does not consume an options slot, and high-dollar mega-caps (e.g., NVDA, MSFT, META, LLY) can be traded via LEAPS or shares without starving other positions.

### B. Dollar-at-Risk Position Sizing
Every recommendation is sized strictly on **Dollar-at-Risk (Capital Protection First)**:
* **Options Book ($100K)**: Max risk per trade is hard-capped at **$1,000 (1.0% account equity)**.
  * *Vertical Spreads*: Buy 4–5 contracts @ $2.00–$2.50 net debit ($800–$1,000 max risk).
  * *Call LEAPS*: 1 contract on secular leaders ($3,500–$5,000 capital deployed), protected by an invalidation stop at the 50 EMA / 200 SMA.
* **Stock Book ($100K)**: Max risk per trade is sized to **$350–$500 (0.35%–0.50% account equity)**.
  * Sized via:
    $$\text{Shares} = \min\left(\left\lfloor \frac{\text{Max Risk Dollars}}{\text{Entry Price} - \text{Stop Price}} \right\rfloor, \left\lfloor \frac{\text{Max Capital Ceiling (6\%)}}{\text{Entry Price}} \right\rfloor\right)$$
  * Sizing shares to a 7% technical stop risks only ~$350–$420 on a $5,000–$6,000 position, providing high-beta equities ample breathing room while bounding drawdown.

---

## 2. Raw Market Data Ingestion Pipeline

Data ingestion is orchestrated in `engine/scanner.py`, `engine/stocks.py`, and `engine/patterns.py` via `yfinance`.

### A. Universe Definition
* **S&P 500 & Key NASDAQ-100 Constituents**: 493+ liquid US large-cap equities dynamically fetched and mapped to the master sector/sub-industry taxonomy in `engine/universe.py`.
* **25 Sector & Industry Benchmark ETFs**: `XLK`, `SMH`, `IGV`, `IHAK`, `XLC`, `XLF`, `KRE`, `XLE`, `XLV`, `IBB`, `XBI`, `XLI`, `IYT`, `JETS`, `XLY`, `XRT`, `ITB`, `XLP`, `XLU`, `XLB`, `XME`, `GDX`, `XLRE`, `TAN`, `QQQ`.
* **4-Index Macro Benchmark Ribbon**: `SPY` (S&P 500), `QQQ` (Nasdaq 100), `RSP` (Equal-Weight S&P), and `IWM` (Russell 2000).

### B. Batching Mechanics & Rate-Limit Shielding
* Raw OHLCV market history is downloaded in **batches of 75 tickers** (`batch_size = 75`) using multi-threaded batch calls (`yf.download(batch, period="1y", interval="1d", group_by="ticker", auto_adjust=False, threads=True)`).
* For the full 500-constituent universe, this requires only **~7 bulk HTTP queries per scan session**, entirely bypassing Yahoo Finance IP rate limiters (which trigger on thousands of individual single-ticker REST calls).

---

## 3. Universal Technical Telemetry & Indicator Engine

Every raw OHLCV bar and options quote is processed through `engine/indicators.py` to extract structural, volatility, and trend metrics.

### 1. Moving Average Confluence & Structural Baselines
* **`EMA 10` & `EMA 21`**: Fast trend velocity and short-term trailing baselines.
* **`EMA 50`**: The primary institutional accumulation/distribution floor:
  $$\text{EMA}_t = \text{Price}_t \times \left(\frac{2}{N+1}\right) + \text{EMA}_{t-1} \times \left(1 - \frac{2}{N+1}\right), \quad N=50$$
* **`SMA 150`**: Intermediate cyclical support.
* **`SMA 200`**: Secular institutional macro boundary.
* **`Overhead 200 SMA Runway %`**:
  * If $\text{Price} \ge \text{SMA}_{200}$: Tagged as `CLEAR (Above 200MA)` (`runway = 999.0` or `0.0`).
  * If $\text{Price} < \text{SMA}_{200}$: Measured as $\frac{\text{SMA}_{200} - \text{Price}}{\text{Price}} \times 100$. Minimum **$5.0\%$ clearance runway required** to ensure take-profit targets are not capped directly below major institutional supply.
  * If History $< 200$ bars (Recent IPOs/Spinoffs): Tagged as `has_200sma = False`, labeled `N/A (<200d History)`, and granted a neutral pass.

### 2. Universal Oscillators: RSI & MACD Long Integration
Previously used only in downside resistance rejection detection, **RSI and MACD are now mandatory across all long equity and options scans**:
* **`RSI(14)` Pullback Floor (Wilder's Smoothing)**:
  $$\text{RSI} = 100 - \left(\frac{100}{1 + \frac{\text{EMA}_{14}(\text{Gains})}{\text{EMA}_{14}(\text{Losses})}}\right)$$
  * **Mandatory Floor**: $\text{RSI}(14) \ge 45.0$.
  * *Institutional Rationale*: In a healthy Stage 2 uptrend, pullbacks to the 50-day EMA find support with RSI in the 45–55 zone. An RSI $< 40$ indicates aggressive institutional distribution or a falling knife rather than an orderly support retest.
* **`MACD(12, 26, 9)` Histogram Momentum Hook**:
  $$\text{MACD Line} = \text{EMA}_{12}(\text{Close}) - \text{EMA}_{26}(\text{Close})$$
  $$\text{Signal Line} = \text{EMA}_9(\text{MACD Line})$$
  $$\text{Histogram} = \text{MACD Line} - \text{Signal Line}$$
  * **Mandatory Leading Hook**: $\text{Histogram}_t > \text{Histogram}_{t-1}$.
  * *Institutional Rationale*: Waiting for a full MACD signal line crossover introduces 3 to 7 days of lag, ruining favorable risk-to-reward entries. The Histogram Slope Hook confirms that downward selling momentum has decelerated and is curling upward at support on Day 0/Day 1 without lag.

### 3. Institutional Relative Volume (RVOL)
Measures capital commitment on support reclaims and breakouts:
$$\text{RVOL} = \frac{\text{Volume}_0}{\frac{1}{20}\sum_{i=1}^{20} \text{Volume}_{-i}}$$
* $\text{RVOL} \ge 1.0\times$: Baseline institutional interest.
* $\text{RVOL} \ge 1.5\times$: Strong accumulation.
* $\text{RVOL} \ge 2.0\times$: High-velocity volume surge (mandatory for High-Risk Sprint setups).

### 4. Volatility, Range & Beta Analytics
* **Average Daily Range (`ADR%`)**:
  $$\text{ADR\%} = \frac{\frac{1}{20}\sum_{i=0}^{19} (\text{High}_{-i} - \text{Low}_{-i})}{\text{Close}_0} \times 100$$
  * High Risk: $\text{ADR} \ge 3.2\%$ (guarantees price elasticity).
  * Balanced: $\text{ADR } 2.0\% - 3.2\%$.
  * Core: $\text{ADR } < 2.5\%$.
* **60-Day Rolling `Beta` vs. `SPY`**:
  $$\beta = \frac{\text{Cov}(R_{\text{Stock}}, R_{\text{SPY}})}{\text{Var}(R_{\text{SPY}})}$$
  * High Risk: $\beta \ge 1.8$ heavily rewarded (accelerates move toward target).
  * Balanced: $\beta \in [1.0, 1.5]$.
  * Core: $\beta \le 1.0$ heavily rewarded (low volatility drag for compounders).
* **1-Year Implied Volatility Rank (`IV Rank`)**:
  $$\text{IV Rank} = \frac{\text{IV}_{\text{Current}} - \text{IV}_{\text{Min}, 252\text{d}}}{\text{IV}_{\text{Max}, 252\text{d}} - \text{IV}_{\text{Min}, 252\text{d}}} \times 100$$
  * *High-Risk Spreads*: High IV Rank (60–85+) awarded maximum score (volatility expansion & momentum).
  * *Balanced Spreads*: Sweet Spot IV Rank (35–65) awarded maximum score.
  * *Core LEAPS*: Low IV Rank ($< 35$) awarded maximum score (minimizes multi-month extrinsic decay).

### 5. Retrace Taxonomy & Reclaim Velocity
* **Retrace Types**:
  * `EMA50`: Clean touch and bounce within $1.5\%$ of the 50-day EMA.
  * `DB`: Double Bottom test within $1.5\%$ of prior 20-day swing low.
  * `OTE`: Optimal Trade Entry (Fibonacci $61.8\% - 78.6\%$ retracement).
  * `MA150`: Deep cyclical retest of the 150-day moving average.
* **`reclaim_days` Velocity ("Sooner Metric")**:
  * `Day 0`: Intraday breakout (marked `🟡 PENDING CLOSE` until official 4:00 PM ET close).
  * `Day 1`: Confirmed daily close above 50 EMA with follow-through (Prime velocity entry).
  * `Day 2`: Secondary confirmation test.
  * `Day > 2`: Stale reclaim; penalized or excluded.

### 6. Dow Theory Market Structure Engine & Hard Disqualification Gate
Derived via `engine/indicators.py::detect_market_structure()` by evaluating 5-day rolling swing highs and swing lows across price history:
* **Regime Classifications**:
  1. `BULLISH_HH_HL`: Series of Higher Highs and Higher Lows. Confirms an active Stage 2 institutional mark-up trend.
  2. `CONSOLIDATION_BASE`: Forming higher lows above multi-week accumulation baselines or horizontal range support.
  3. `BEARISH_LH_LL`: Series of Lower Highs and Lower Lows. Confirms an active Stage 4 institutional distribution trend.
* **Universal Hard Qualification Filter for Long Plays (`dow_structure_ok`)**:
  $$\text{Market Structure Regime} \neq \text{"BEARISH\_LH\_LL"}$$
  * **Eliminating the "Bear Trap" Relief Bounce**: When an equity is in a confirmed `BEARISH_LH_LL` downtrend, any bounce into the 50-day EMA represents a dead-cat relief rally into falling overhead supply, NOT a trend continuation.
  * **Application to Derivatives & Equities**:
    * **Bull Call Spreads & Deep-ITM Call LEAPS**: In options, buying into a `BEARISH_LH_LL` relief bounce almost always results in a 100% loss of net debit as the stock rolls over to make a new lower low while theta accelerates. Hard disqualification shields premium buyers from bear traps.
    * **Cash Equities**: Prevents premature accumulation in broken structural downtrends.
  * **Downside Hedge Requirement**: For Bear Put Spreads (`downside_hedges`), `BEARISH_LH_LL` is actively required or rewarded as structural confirmation of continuing institutional distribution.

---

## 4. The 3-Pronged Strategy Engine Specification

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                       3-PRONGED MULTI-HORIZON FRAMEWORK                                          │
├─────────────────────────┬───────────────────────────────────┬────────────────────────────────────────────────────┤
│ STRATEGY PRONG          │ EQUITIES SPECIFICATION            │ DERIVATIVES SPECIFICATION                          │
├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤
│ 🚀 HIGH RISK (VELOCITY) │ • Holding Horizon: 10–14 sessions │ • Vehicle: 45–90 DTE Bull/Bear Call/Put Spreads    │
│    "Momentum Sprint"    │ • Target: Beta >= 1.8, ADR >= 3.5%│ • Volatility: High IV Rank (60–85+) Rewarded       │
│    Capacity: 7-8 Slots  │ • Entry: D0-D1 Reclaim, RVOL>=1.8x│ • Exit: 70% Max Profit or Day 10 Stagnation Stop   │
├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤
│ ⚖️ BALANCED (TACTICAL)   │ • Holding Horizon: 15–25 sessions │ • Vehicle: 60–120 DTE Spreads & Deep-ITM LEAPS     │
│    "Core Swing"         │ • Target: Beta 1.0-1.5, ADR 2-3.2%│ • Volatility: Sweet Spot IV Rank (35–65) Rewarded  │
│    Capacity: 7 Slots    │ • Entry: D0-D2 Reclaim, RVOL>=1.2x│ • Exit: TP1 (+2.5 R:R), Day 14 Stagnation Stop     │
├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤
│ 🛡️ LOW RISK (CORE)       │ • Holding Horizon: 40–120+ sess.  │ • Vehicle: Jan 2028 Call LEAPS (Delta >= 0.75)     │
│    "Compounder"         │ • Target: Beta <= 1.0, Pos. FCF   │ • Volatility: Low IV Rank (< 35) Mandatory         │
│    Capacity: 4-5 Slots  │ • Trend: Stage 2 Stack (50>150>200│ • Exit: 3% below 200 SMA Macro Invalidation Stop   │
└─────────────────────────┴───────────────────────────────────┴────────────────────────────────────────────────────┘
```

### Stagnation Stop Rules (Recycling Portfolio Heat)
* **High-Risk Prong**: If a position fails to reach at least $+1.0\text{R}$ of profit within **10 trading sessions**, exit immediately at market or close the spread. Capital is recycled into fresh setups.
* **Balanced Prong**: If a position fails to achieve $>50\%$ of the distance to TP1 within **14 trading sessions**, tighten stop to breakeven or close to prevent theta decay.
* **Core Prong**: No time-based stagnation stop. Governed strictly by trend stack integrity and macro moving averages.

---

## 5. Two-Level Architecture: Macro Governor vs. Sector Scoring

A key architectural principle separates macro-level controls from micro-level ticker ranking:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   LEVEL 1: MACRO GOVERNOR (PORTFOLIO LEVEL)                      │
│   • 4-Index Benchmark Matrix (SPY, QQQ, RSP, IWM vs. 50 EMA)                     │
│   • Controls: Bullish/Bearish Directional Bias (Calls vs. Puts)                  │
│   • Controls: Global Cash Allocation (10% to 70% cash reserves)                  │
│   • Controls: Emergency Regime Freezes (e.g. 100% Freeze on Long Calls)          │
│   * Does NOT score individual tickers (Macro is uniform across all 500 stocks)   │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │ Governs Portfolio Bias & Constraints
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   LEVEL 2: TICKER ALPHA SCORING (MICRO LEVEL)                    │
│   • Sector Relative Strength (15 pts): Top-Quartile ETF + mom_spread > 0        │
│   • Beta & Price Elasticity (15 pts): Beta >= 1.8 & ADR >= 3.5% (High Risk)      │
│   • Retrace Reclaim Velocity (20 pts) + Institutional RVOL (20 pts)              │
│   • Universal Momentum (15 pts): RSI >= 45 floor + MACD Histogram Curl Hook      │
│   • Dow Theory Market Structure (15 pts): Confirmed HH/HL vs Consolidation Base  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Macro Benchmark Steering Matrix
$$\text{Macro Confluence Score} = \sum_{i=1}^4 \mathbf{1}_{\{\text{Index}_i \ge \text{EMA}_{50}\}}$$

| Macro Regime | Confluence Score | Market Breadth Ratio | Strategy Directive | Portfolio Bias |
| :--- | :---: | :---: | :--- | :--- |
| **RISK-ON** | **4 / 4** | $> 0.55$ | **Aggressive Expansion**: Full offense across High-Risk and Balanced tiers. Puts restricted to extreme overbought blow-offs. | **85% – 100% Long** |
| **CAUTIOUS RISK-ON** | **3 / 4** | $0.45 - 0.55$ | **Selective Trend Longs**: Target top-quartile relative strength sectors. Long calls favored. | **70% Long / 30% Short** |
| **MIXED / ROTATION** | **2 / 4** | $0.35 - 0.45$ | **Hedged Pairs Trading**: Long relative strength leaders (e.g., Energy, Biotech); Bear Put Spreads on breakdown sectors (e.g., Solar, Airlines). | **50% Long / 50% Short** |
| **DEFENSIVE / CHOP** | **1 / 4** | $0.25 - 0.35$ | **Capital Preservation**: 100% freeze on new long calls/LEAPS. Tactical Bear Put Spreads on resistance rejections. | **20% Long / 80% Short** |
| **SYSTEMIC LIQUIDATION**| **0 / 4** | $< 0.25$ | **Regime Lockdown**: Strict freeze on all long positions. 50%–70% cash reserves; downside put hedges dominate. | **0% Long / 100% Short** |

---

## 6. Execution & Risk Guardrails

### A. Dynamic Sector Capital Allocation (30%–35% Cap)
* **The Principle**: When institutional capital concentrates aggressively into a dominant theme (e.g., Semiconductors or Energy), a rigid "max 3 per sector" cap arbitrarily rejects top-tier setups.
* **The Rule**: Enforce a **maximum 30%–35% capital allocation per sector** across each 16–21 position book.
  * In an 18-position portfolio, this permits up to **5 to 6 positions in the #1 leading relative strength sector**.
  * Prevents catastrophic 70%+ hyper-concentration while fully capitalizing on institutional sector momentum.

### B. The "Liquid Route" Auto-Switch (Options vs. Stock)
* Before executing an options structure, the engine screens options chain market quality:
  * Minimum Open Interest: $\text{OI} \ge 500$ on target strikes.
  * Maximum Bid-Ask Spread: $\text{Spread Width} \le 8.0\%$ of mid-price.
* **Auto-Routing Protocol**: If a setup meets all technical criteria (50 EMA, RSI, MACD, RVOL) but fails the liquidity test, the engine automatically routes the order ticket to the **Stock Portfolio as Common Shares**, preventing execution slippage while preserving the technical idea.

### C. The 70% Max-Profit Harvest Rule
* For vertical spreads (Bull Call or Bear Put Spreads), as the underlying reaches the short strike, the spread achieves 70%–80% of max profit. Squeezing out the remaining 20% requires holding until expiration while bearing 100% reversal risk.
* **Harvest Mandate**: Close vertical spreads when they reach **70%–75% of maximum potential spread width** (or at TP1). Recycles portfolio heat and frees up capital days ahead of expiration.

### D. Anti-Chop Re-Entry Cooldown
* If an equity or option position hits its invalidation stop, the ticker enters a mandatory **3-to-5 trading day Re-Entry Cooldown**.
* Even if the stock closes back above the 50 EMA the following day, re-entry is blocked until the cooldown elapses, shielding the portfolio from choppy, range-bound whip patterns.

### E. News Cycle Telemetry Synthesis
* Real-time news events are incorporated directly through quantitative footprint indicators rather than noisy, lagging news headline scrapers:
  * **RVOL $\ge 1.8\times - 2.5\times$**: The institutional footprint of breaking news and catalyst accumulation.
  * **Expanding IV Rank**: Captures market anticipation and volatility expansion.
  * **Price Action Confirmation**: A confirmed close above the 50 EMA confirms the market has absorbed the news constructively.
  * **Corporate Earnings Calendar Blackout**: The only hard calendar gatekeeper, requiring $\ge 21$ days clearance before upcoming earnings reports to prevent binary gap-down stop-outs.

### F. Universal Hard Qualification Gatekeeper Matrix
Before any ticker is submitted to the mathematical scoring engines (Composite Alpha Score or Options Quality Index), it must pass **100% of the six universal gatekeeper filters**:

| Gatekeeper Filter | Parameter / Condition | Institutional Rationale | Enforcement Target |
| :--- | :--- | :--- | :--- |
| **1. 50 EMA Velocity** | `Price >= EMA50` & `reclaim_days <= 3` | Captures fresh momentum; rejects stale, extended moves. | Long Options & Stocks |
| **2. Retrace Taxonomy** | `retrace_type in ["EMA50", "DB", "OTE"]` | Requires high-probability institutional pullback structures. | Long Options & Stocks |
| **3. Overhead Runway** | `runway >= 5.0%` or `CLEAR (Above 200 SMA)` | Prevents entering directly below major 200 SMA supply walls. | Long Options & Stocks |
| **4. RSI Floor** | `RSI(14) >= 45.0` | Filters out severe institutional distribution and falling knives. | Long Options & Stocks |
| **5. MACD Momentum** | `Histogram[t] > Histogram[t-1]` | Confirms selling deceleration and upward curl without lag. | Long Options & Stocks |
| **6. Dow Market Structure**| `Market Structure != "BEARISH_LH_LL"` | Rejects dead-cat bounces and bear traps in structural downtrends. | Long Options & Stocks |

---

## 7. Mathematical Scoring Engines

### A. Cash Equities Alpha Composite Score (0 to 100)
Calculated in `engine/stocks.py` (`compute_alpha_composite_score`).

$$\text{Stock Alpha Score} = S_{\text{Reclaim}} + S_{\text{RVOL}} + S_{\text{Sector RS}} + S_{\text{Beta/Elasticity}} + S_{\text{Momentum}} + S_{\text{Structure}}$$

| Component | Weight | 🚀 High-Risk Sprint | ⚖️ Balanced Swing | 🛡️ Core Compounder |
| :--- | :---: | :--- | :--- | :--- |
| **1. Reclaim Velocity & Freshness** | **20 pts** | Day 0–1 Reclaim (20 pts) | Day 0–2 Reclaim (20 pts) | Stage 2 Stack (20 pts) |
| **2. Institutional RVOL** | **20 pts** | $\text{RVOL} \ge 2.0\times$ (20 pts) | $\text{RVOL} \ge 1.3\times$ (20 pts) | Steady Volume (15 pts) |
| **3. Sector Relative Strength (RS)** | **15 pts** | **Top-Quartile ETF & $\text{mom\_spread} > 0$** | **Top-Half ETF & $\text{mom\_spread} > 0$** | **Defensive/Secular Sector** |
| **4. Beta & Price Elasticity** | **15 pts** | **$\beta \ge 1.8$ & $\text{ADR} \ge 3.5\%$ (15 pts)** | **$\beta \in [1.0, 1.5]$ & $\text{ADR } 2.2 - 3.2\%$** | **$\beta \le 1.0$ (Low Drag, 15 pts)** |
| **5. Universal Momentum (RSI + MACD)**| **15 pts** | $\text{RSI} \ge 50$ + MACD Hist Hook | $\text{RSI} \ge 45$ + MACD Hist Hook | $\text{RSI} \ge 45$ + Bullish Stack |
| **6. Dow Theory Market Structure** | **15 pts** | Confirmed HH/HL (15 pts) | Emerging Base / HH (15 pts) | Multi-Month Base (15 pts) |

---

### B. Derivatives Options Alpha Radar Score (0 to 100)
Calculated in `engine/patterns.py` (`compute_options_alpha_score`).

$$\text{Options Alpha Score} = (\text{Directional Alpha} \times 0.35) + S_{\text{IV}} + S_{\text{Liquidity}} + S_{\text{Runway}} + S_{\text{Momentum}} + P_{\text{Earnings}}$$

| Component | Weight | High-Risk Sprint (45–90 DTE) | Balanced Swing (60–120 DTE) | Core LEAPS (Jan 2028) |
| :--- | :---: | :--- | :--- | :--- |
| **1. Directional Foundation** | **35 pts** | $0.35 \times \text{Stock Alpha}$ | $0.35 \times \text{Stock Alpha}$ | $0.35 \times \text{Stock Alpha}$ |
| **2. IV Rank Behavior** | **20 pts** | **High IV (60–85+) = 20 pts** | **Sweet Spot (35–65) = 20 pts**| **Low IV (< 35) = 20 pts** |
| **3. Contract Liquidity** | **20 pts** | $\text{OI} \ge 1000$, $\text{Spread} \le 5\%$ | $\text{OI} \ge 500$, $\text{Spread} \le 8\%$ | $\text{OI} \ge 250$, $\text{Spread} \le 10\%$|
| **4. 200 SMA Clearance Runway**| **15 pts** | Runway $\ge 8\%$ or Blue Sky | Runway $\ge 5\%$ or Blue Sky | Above 200 SMA Mandatory |
| **5. Universal MACD/RSI Hook** | **10 pts** | MACD Hist Hook + $\text{RSI} \ge 45$| MACD Hist Hook + $\text{RSI} \ge 45$| Stage 2 Trend Stack |
| **6. Earnings Blackout** | **Penalty** | $-35$ pts if inside trade DTE | $-35$ pts if inside trade DTE | $-35$ pts if inside 60 days |

---

## 8. Complete Left-to-Right Architecture Mapping

| Raw Ingestion Input | Derived Metric | Engine Function | Cash Equities Role | Options Derivatives Role | Storage Lifecycle |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`Close` (504 daily bars)** | `EMA 10, 21, 50, 200`<br>`SMA 150, 200` | `indicators.py`<br>`compute_technical_snapshot()` | Primary support floors; sets stop-loss anchor | Primary support floors; sets vertical spread strikes | **Stored Daily** (`latest.json` & `history/*.json`) |
| **`Close` (Sector ETF vs SPY 20d)**| `mom_spread` + Top Quartile | `scanner.py`<br>`compute_relative_strength_matrix()` | **Level 2 Scoring Factor (15 pts)**: Rewards parent ETF momentum tailwind | Feeds into Directional Alpha base score | **Stored Daily** (`sector_strength` & `latest.json`) |
| **`Close` vs `SPY` (60d)** | `Beta` + `ADR%` | `indicators.py`<br>`compute_beta()` & `compute_adr()` | **Level 2 Scoring Factor (15 pts)**: Rewards $\beta \ge 1.8$ in High Risk; $\le 1.0$ in Core | Calibrates strike widths and delta expansion targets | **Stored Daily** (`latest.json`) |
| **`High`, `Low`, `Close`** | `RSI(14)` | `indicators.py`<br>`calculate_rsi()` | **Universal Floor**: Disqualifies any setup with $\text{RSI} < 45.0$ | **Universal Floor**: Disqualifies any setup with $\text{RSI} < 45.0$ | **Stored Daily** (`latest.json`) |
| **`Close` (12, 26, 9)** | `MACD Histogram` | `indicators.py`<br>`calculate_macd()` | **Momentum Hook**: Requires $\text{Hist}_t > \text{Hist}_{t-1}$ at 50 EMA | **Momentum Hook**: Requires $\text{Hist}_t > \text{Hist}_{t-1}$ at 50 EMA | **Stored Daily** (`latest.json`) |
| **`Volume` (20-day window)** | `RVOL` | `indicators.py`<br>`compute_technical_snapshot()` | Confirms institutional accumulation ($\ge 1.8\times$ for High-Risk) | Validates breakout volume on options entry | **Stored Daily** (`latest.json`) |
| **`Close` + `Low` (20d)** | `retrace_type`<br>`reclaim_days` | `patterns.py`<br>`detect_support_retrace()` | Classifies EMA50, DB, OTE, MA150 retests; D0–D2 velocity | Determines spread vehicle vs. LEAPS structure | **Stored Daily** (`latest.json`) |
| **`Close` (252-day window)** | `IV Rank` | `indicators.py`<br>`compute_technical_snapshot()` | Contextual range metric for share elasticity | **Key Divergence**: High-Risk rewards High IV; Core rewards Low IV | **Stored Daily** (`latest.json`) |
| **`option_chain(exp)`** | `bid`, `ask`, `openInterest`, `volume` | `patterns.py`<br>`verify_and_fetch_live_options()` | Liquid Route Switch: If illiquid, routes setup to Stock Portfolio | Guarantees $\text{OI} \ge 500$ and spread $\le 8\%$ | **Stored Daily** (`latest.json`) |
| **4 Benchmark Indices** | `Macro Confluence`<br>(0 to 4 score) | `scanner.py`<br>`compute_benchmark_confluence()` | **Level 1 Governor**: Controls overall equity vs cash allocation | Dictates Call Spread vs. Bear Put Spread portfolio ratio | **Stored Daily** (`latest.json` & `summary.json`) |
| **Calendar / Earnings** | `days_to_earnings` | `patterns.py`<br>`evaluate_earnings_blackout()` | Informational risk flag | **Hard Gate**: $-35$ pts penalty if earnings inside 21–45 DTE | **Stored Daily** (`latest.json`) |

---

## 9. Storage & Persistence Lifecycle

To maintain complete auditability while keeping repository storage within GitHub Pages static serving limits (~15MB–20MB), the system enforces strict state separation:

### What Is Stored Daily in `data/latest.json` and `data/history/YYYY-MM-DD.json`
1. **`stock_recommendations` & `all_qualified_stocks`**: Active common share setups partitioned across High-Risk, Balanced, and Core prongs with exact dollar-at-risk share counts, stops, TP1, and TP2 targets.
2. **`top_candidates`, `strategic_leaps`, and `downside_hedges`**: Complete derivatives execution tickets specifying contract month, strike intervals, mid-price limit debits, max profit, delta, and verified Open Interest.
3. **`macro_breadth` & `benchmark_matrix`**: 4-index confluence metrics, market breadth ratios, regime status, and narrative execution directives.
4. **`sector_strength` & `subsector_matrix`**: 25 Sector ETF momentum rankings, 90 sub-industry metrics, and sector rotation cards.
5. **`trades_log.json` & `stock_trades_log.json`**: Permanent stateful trade ledgers tracking active entries, scale-outs, trailing stops, realized P&L, hold times, and root-cause loss attribution.

### What Is Ephemeral and NEVER Stored in JSON
1. **Raw Historical 2-Year OHLCV Data**: The ~1.5 million historical data points ingested across the 520+ symbols are computed entirely in volatile RAM and discarded.
2. **Exhaustive Multi-Strike Option Chains**: Thousands of strike/bid/ask combinations are evaluated in memory; only the selected long and short contract pair is retained.
3. **Rolling Array Buffers**: Intermediate NumPy matrix calculations for rolling covariance, ATR, and Wilder's smoothing are garbage-collected immediately after computing the scalar indicators.
