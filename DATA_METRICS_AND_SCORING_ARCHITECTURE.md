# Quantitative Data Pipeline, Derived Metrics & Dual Scoring Architecture

This document provides the definitive, production-grade technical specification for the **ABI Strategy Terminal & Quantitative Execution Engine**.

It details:

1.  **The Twin-Engine Architecture**: Independent $100,000 Common Stock and $100,000 Options portfolios ($200,000 total capital base) operating with dedicated 16–21 position holding capacity.
2.  **The 3-Pronged Strategy Framework**: Low Risk (Core Compounders), Balanced (Tactical Swings & LEAPS), and High Risk (High-Velocity Momentum Sprints) across cash equities and derivatives.
3.  **Universal Indicator Telemetry**: Complete mathematical definitions for all raw inputs, derived moving averages, RVOL, Wilder's RSI(14) pullback floors, and MACD(12, 26, 9) histogram momentum hooks.
4.  **Bi-Directional Execution & Natural Macro Steering**: Dynamic allocation between Call and Put spreads driven by the 4-Index Benchmark Matrix.
5.  **Execution Guardrails**: Dynamic sector capital caps (30%–35%), the "Liquid Route" options-to-stock auto-switch, 70% max-profit spread harvesting, and anti-chop re-entry cooldowns.
6.  **Persistence Lifecycle**: Complete left-to-right mapping and daily JSON storage vs. ephemeral memory boundaries.

-----

## 1\. Capital Architecture & The Twin-Engine Model

The engine operates two fully decoupled, independent portfolios to prevent cross-asset competition, avoid liquidity bottlenecks, and allow high-conviction mega-cap leaders to be traded without capital distortion:

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

  │ • Capital / Slot: \~$4,500 – $6,000   │                       │ • Capital / Slot: \~$4,500 – $6,000   │

  │ • Dollar-at-Risk: $1,000 max (1.0%)  │                       │ • Dollar-at-Risk: $350 – $500 (0.4%) │

  │ • Vehicles: Spreads & Deep LEAPS     │                       │ • Vehicles: Common Shares (Cash)     │

  └──────────────────────────────────────┘                       └──────────────────────────────────────┘

### A. Position Capacity & Heat Management

  - **Legacy Bottleneck Solved**: The legacy terminal enforced a flat ceiling of 7 concurrent open trades. A single slow-moving stock holding for 40 days throttled the entire system.
  - **Expanded Capacity**: Active holding capacity is expanded to **16 to 21 concurrent positions per portfolio** (32 to 42 active holdings across the entire terminal).
  - **Dedicated Execution Pools**: The Stock Engine and Options Engine scan the 500-constituent universe independently. An equity recommendation does not consume an options slot, and high-dollar mega-caps (e.g., NVDA, MSFT, META, LLY) can be traded via LEAPS or shares without starving other positions.

### B. Dollar-at-Risk Position Sizing

Every recommendation is sized strictly on **Dollar-at-Risk (Capital Protection First)**:

  - **Options Book ($100K)**: Max risk per trade is hard-capped at **$1,000 (1.0% account equity)**.
      
      - *Vertical Spreads*: Buy 4–5 contracts @ $2.00–$2.50 net debit ($800–$1,000 max risk).
      - *Call LEAPS*: 1 contract on secular leaders ($3,500–$5,000 capital deployed), protected by an invalidation stop at the 50 EMA / 200 SMA.
  - **Stock Book ($100K)**: Max risk per trade is sized to **$350–$500 (0.35%–0.50% account equity)**.
      
      - Sized via: $$\text{Shares} = \min\left(\left\lfloor \frac{\text{Max Risk Dollars}}{\text{Entry Price} - \text{Stop Price}} \right\rfloor, \left\lfloor \frac{\text{Max Capital Ceiling (6%)}}{\text{Entry Price}} \right\rfloor\right)$$
      - Sizing shares to a 7% technical stop risks only \~$350–$420 on a $5,000–$6,000 position, providing high-beta equities ample breathing room while bounding drawdown.

-----

## 2\. Raw Market Data Ingestion Pipeline

Data ingestion is orchestrated in engine/market_data.py (fetching) and engine/universe_scan.py (structuring via engine/stocks.py and engine/patterns.py) via yfinance.

### A. Universe Definition

  - **S\&P 500 & Key NASDAQ-100 Constituents**: 493+ liquid US large-cap equities dynamically fetched and mapped to the master sector/sub-industry taxonomy in engine/universe.py.
  - **25 Sector & Industry Benchmark ETFs**: XLK, SMH, IGV, IHAK, XLC, XLF, KRE, XLE, XLV, IBB, XBI, XLI, IYT, JETS, XLY, XRT, ITB, XLP, XLU, XLB, XME, GDX, XLRE, TAN, QQQ.
  - **4-Index Macro Benchmark Ribbon**: SPY (S\&P 500), QQQ (Nasdaq 100), RSP (Equal-Weight S\&P), and IWM (Russell 2000).

### B. Batching Mechanics & Rate-Limit Shielding

  - Raw OHLCV market history is downloaded in **batches of 75 tickers** (batch_size = 75) using multi-threaded batch calls (yf.download(batch, period="1y", interval="1d", group_by="ticker", auto_adjust=False, threads=True)).
  - For the full 500-constituent universe, this requires only **\~7 bulk HTTP queries per scan session**, entirely bypassing Yahoo Finance IP rate limiters (which trigger on thousands of individual single-ticker REST calls).

-----

## 3\. Universal Technical Telemetry & Indicator Engine

Every raw OHLCV bar and options quote is processed through engine/indicators.py to extract structural, volatility, and trend metrics.

### 1\. Moving Average Confluence & Structural Baselines

  - **EMA 10** **&** **EMA 21**: Fast trend velocity and short-term trailing baselines.
  - **EMA 50**: The primary institutional accumulation/distribution floor: $$\text{EMA}_t = \text{Price}_t \times \left(\frac{2}{N+1}\right) + \text{EMA}_{t-1} \times \left(1 - \frac{2}{N+1}\right), \quad N=50$$
  - **SMA 150**: Intermediate cyclical support.
  - **SMA 200**: Secular institutional macro boundary.
  - **Overhead 200 SMA Runway %**:
      
      - If $\text{Price} \ge \text{SMA}_{200}$: Tagged as CLEAR (Above 200MA) (runway = 999.0 or 0.0).
      - If $\text{Price} < \text{SMA}_{200}$: Measured as $\frac{\text{SMA}_{200} - \text{Price}}{\text{Price}} \times 100$. Minimum **$5.0%$ clearance runway required** to ensure take-profit targets are not capped directly below major institutional supply.
      - If History $< 200$ bars (Recent IPOs/Spinoffs): Tagged as has_200sma = False, labeled N/A (<200d History), and granted a neutral pass.

### 2\. Universal Oscillators: RSI & MACD Long Integration

Previously used only in downside resistance rejection detection, **RSI and MACD are now mandatory across all long equity and options scans**:

  - **RSI(14)** **Pullback Floor (Wilder's Smoothing)**: $$\text{RSI} = 100 - \left(\frac{100}{1 + \frac{\text{EMA}_{14}(\text{Gains})}{\text{EMA}_{14}(\text{Losses})}}\right)$$
      
      - **Mandatory Floor**: $\text{RSI}(14) \ge 45.0$.
      - *Institutional Rationale*: In a healthy Stage 2 uptrend, pullbacks to the 50-day EMA find support with RSI in the 45–55 zone. An RSI $< 40$ indicates aggressive institutional distribution or a falling knife rather than an orderly support retest.
  - **MACD(12, 26, 9)** **Histogram Momentum Hook**: $$\text{MACD Line} = \text{EMA}_{12}(\text{Close}) - \text{EMA}_{26}(\text{Close})$$ $$\text{Signal Line} = \text{EMA}_9(\text{MACD Line})$$ $$\text{Histogram} = \text{MACD Line} - \text{Signal Line}$$
      
      - **Mandatory Leading Hook**: $\text{Histogram}_t > \text{Histogram}_{t-1}$.
      - *Institutional Rationale*: Waiting for a full MACD signal line crossover introduces 3 to 7 days of lag, ruining favorable risk-to-reward entries. The Histogram Slope Hook confirms that downward selling momentum has decelerated and is curling upward at support on Day 0/Day 1 without lag.

### 3\. Institutional Relative Volume (RVOL)

Measures capital commitment on support reclaims and breakouts: $$\text{RVOL} = \frac{\text{Volume}_0}{\frac{1}{20}\sum*{i=1}^{20} \text{Volume}_{-i}}$$

  - $\text{RVOL} \ge 1.0\times$: Baseline institutional interest.
  - $\text{RVOL} \ge 1.5\times$: Strong accumulation.
  - $\text{RVOL} \ge 2.0\times$: High-velocity volume surge (mandatory for High-Risk Sprint setups).

### 4\. Volatility, Range & Beta Analytics

  - **Average Daily Range (****ADR%****)**: $$\text{ADR%} = \frac{\frac{1}{20}\sum_{i=0}^{19} (\text{High}_{-i} - \text{Low}_{-i})}{\text{Close}_0} \times 100$$
      
      - High Risk: $\text{ADR} \ge 3.2%$ (guarantees price elasticity).
      - Balanced: $\text{ADR } 2.0% - 3.2%$.
      - Core: $\text{ADR } < 2.5%$.
  - **60-Day Rolling** **Beta** **vs.** **SPY**: $$\beta = \frac{\text{Cov}(R_{\text{Stock}}, R_{\text{SPY}})}{\text{Var}(R_{\text{SPY}})}$$
      
      - High Risk: $\beta \ge 1.5$ (accelerates move toward target).
      - Balanced: $\beta \in [1.0, 1.5]$.
      - Core: $\beta \le 1.2$ (low beta drag for secular compounders).
  - **1-Year Implied Volatility Rank (****IV Rank****)**: $$\text{IV Rank} = \frac{\text{IV}_{\text{Current}} - \text{IV}_{\text{Min}, 252\text{d}}}{\text{IV}_{\text{Max}, 252\text{d}} - \text{IV}_{\text{Min}, 252\text{d}}} \times 100$$
      
      - *High-Risk Spreads*: High IV Rank (60–85+) awarded maximum score (volatility expansion & momentum).
      - *Balanced Spreads*: Sweet Spot IV Rank (35–65) awarded maximum score.
      - *Core LEAPS*: Low IV Rank ($< 35$) awarded maximum score (minimizes multi-month extrinsic decay).

### 5\. Retrace Taxonomy & Reclaim Velocity

  - **Retrace Types**:
      
      - EMA50: Clean touch and bounce within $1.5%$ of the 50-day EMA.
      - DB: Double Bottom test within $1.5%$ of prior 20-day swing low.
      - OTE: Optimal Trade Entry (Fibonacci $61.8% - 78.6%$ retracement).
      - MA150: Deep cyclical retest of the 150-day moving average.
  - **reclaim_days** **Velocity ("Sooner Metric")**:
      
      - Day 0: Intraday breakout (marked ð¡ PENDING CLOSE until official 4:00 PM ET close).
      - Day 1: Confirmed daily close above 50 EMA with follow-through (Prime velocity entry).
      - Day 2: Secondary confirmation test.
      - Day > 2: Stale reclaim; penalized or excluded.

### 6\. Dow Theory Market Structure Engine & Hard Disqualification Gate

Derived via engine/indicators.py::detect_market_structure() by evaluating 5-day rolling swing highs and swing lows across price history:

  - **Regime Classifications**:
      
      - BULLISH_HH_HL: Series of Higher Highs and Higher Lows. Confirms an active Stage 2 institutional mark-up trend.
      - CONSOLIDATION_BASE: Forming higher lows above multi-week accumulation baselines or horizontal range support.
      - BEARISH_LH_LL: Series of Lower Highs and Lower Lows. Confirms an active Stage 4 institutional distribution trend.
  - **Universal Hard Qualification Filter for Long Plays (****dow_structure_ok****)**:
      
      - $$\text{Market Structure Regime} \neq \text{"BEARISH_LH_LL"}$$
      - **Eliminating the "Bear Trap" Relief Bounce**: When an equity is in a confirmed BEARISH_LH_LL downtrend, any bounce into the 50-day EMA represents a dead-cat relief rally into falling overhead supply, NOT a trend continuation.
      - **Application to Derivatives & Equities**:
          
        1.  **Bull Call Spreads & Deep-ITM Call LEAPS**: In options, buying into a BEARISH_LH_LL relief bounce almost always results in a 100% loss of net debit as the stock rolls over to make a new lower low while theta accelerates. Hard disqualification shields premium buyers from bear traps.
        2.  **Cash Equities**: Prevents premature accumulation in broken structural downtrends.
      - **Downside Hedge Requirement**: For Bear Put Spreads (downside_hedges), BEARISH_LH_LL is actively required or rewarded as structural confirmation of continuing institutional distribution.

-----

## 4\. The 3-Pronged Strategy Engine Specification

┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐

│                                       3-PRONGED MULTI-HORIZON FRAMEWORK                                          │

├─────────────────────────┬───────────────────────────────────┬────────────────────────────────────────────────────┤

│ STRATEGY PRONG          │ EQUITIES SPECIFICATION            │ DERIVATIVES SPECIFICATION                          │

├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤

│ ð HIGH RISK (VELOCITY) │ • Holding Horizon: 10–14 sessions │ • Vehicle: 45–90 DTE Bull/Bear Call/Put Spreads    │

│    "Momentum Sprint"    │ • Target: Beta >= 1.5, ADR >= 3.2%│ • Volatility: High IV Rank (60–85+) Rewarded       │

│    Capacity: 7-8 Slots  │ • Entry: D0-D1 Reclaim, RVOL>=1.8x│ • Exit: 70% Max Profit or Day 10 Stagnation Stop   │

├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤

│ ⚖️ BALANCED (TACTICAL)   │ • Holding Horizon: 15–25 sessions │ • Vehicle: 60–120 DTE Spreads & Deep-ITM LEAPS     │

│    "Core Swing"         │ • Target: Beta 1.0-1.5, ADR 2-3.2%│ • Volatility: Sweet Spot IV Rank (35–65) Rewarded  │

│    Capacity: 7 Slots    │ • Entry: D0-D2 Reclaim, RVOL>=1.2x│ • Exit: TP1 (+2.5 R:R), Day 14 Stagnation Stop     │

├─────────────────────────┼───────────────────────────────────┼────────────────────────────────────────────────────┤

│ ð¡️ LOW RISK (CORE)       │ • Holding Horizon: 40–120+ sess.  │ • Vehicle: Jan 2028 Call LEAPS (Delta >= 0.75)     │

│    "Compounder"         │ • Target: Beta <= 1.2, Pos. FCF   │ • Volatility: Low IV Rank (< 35) Mandatory         │

│    Capacity: 4-5 Slots  │ • Trend: Stage 2 Stack (50>150>200│ • Exit: 3% below 200 SMA Macro Invalidation Stop   │

└─────────────────────────┴───────────────────────────────────┴────────────────────────────────────────────────────┘

### Stagnation Stop Rules (Recycling Portfolio Heat)

  - **High-Risk Prong**: If a position fails to reach at least $+1.0\text{R}$ of profit within **10 trading sessions**, exit immediately at market or close the spread. Capital is recycled into fresh setups.
  - **Balanced Prong**: If a position fails to achieve $>50%$ of the distance to TP1 within **14 trading sessions**, tighten stop to breakeven or close to prevent theta decay.
  - **Core Prong**: No time-based stagnation stop. Governed strictly by trend stack integrity and macro moving averages.

-----

## 5\. Bi-Directional Directional Guidance: Macro Steering

Rather than imposing an arbitrary 50/50 ratio between Call Spreads and Put Spreads, the distribution of bullish vs. bearish setups is guided organically by the **4-Index Macro Benchmark Matrix** (SPY, QQQ, RSP, IWM vs. 50 EMA):

$$\text{Macro Confluence Score} = \sum_{i=1}^4 \mathbf{1}[ \text{Index}_i \ge \text{EMA}_{50} ]$$

|  |  |  |  |  |
| :-: | :-: | :-: | :-: | :-: |
| **Macro Regime** | **Confluence Score** | **Market Breadth Ratio** | **Strategy Directive** | **Portfolio Bias** |
| **RISK-ON** | **4 / 4** | $> 0.55$ | **Aggressive Expansion**: Full offense across High-Risk and Balanced tiers. Puts restricted to extreme overbought blow-offs. | **85% – 100% Long** |
| **CAUTIOUS RISK-ON** | **3 / 4** | $0.45 - 0.55$ | **Selective Trend Longs**: Target top-quartile relative strength sectors. Long calls favored. | **70% Long / 30% Short** |
| **MIXED / ROTATION** | **2 / 4** | $0.35 - 0.45$ | **Hedged Pairs Trading**: Long relative strength leaders (e.g., Energy, Biotech); Bear Put Spreads on breakdown sectors (e.g., Solar, Airlines). | **50% Long / 50% Short** |
| **DEFENSIVE / CHOP** | **1 / 4** | $0.25 - 0.35$ | **Capital Preservation**: 100% freeze on new long calls/LEAPS. Tactical Bear Put Spreads on resistance rejections. | **20% Long / 80% Short** |
| **SYSTEMIC LIQUIDATION** | **0 / 4** | $< 0.25$ | **Regime Lockdown**: Strict freeze on all long positions. 50%–70% cash reserves; downside put hedges dominate. | **0% Long / 100% Short** |

-----

## 6\. Execution & Risk Guardrails

### A. Dynamic Sector Capital Allocation (30%–35% Cap)

  - **The Principle**: When institutional capital concentrates aggressively into a dominant theme (e.g., Semiconductors or Energy), a rigid "max 3 per sector" cap arbitrarily rejects top-tier setups.
  - **The Rule**: Enforce a **maximum 30%–35% capital allocation per sector** across each 16–21 position book.
      
      - In a 18-position portfolio, this permits up to **5 to 6 positions in the \#1 leading relative strength sector**.
      - Prevents catastrophic 70%+ hyper-concentration while fully capitalizing on institutional sector momentum.

### B. The "Liquid Route" Auto-Switch (Options vs. Stock)

  - Before executing an options structure, the engine screens options chain market quality:
      
      - Minimum Open Interest: $\text{OI} \ge 500$ on target strikes.
      - Maximum Bid-Ask Spread: $\text{Spread Width} \le 8.0%$ of mid-price.
  - **Auto-Routing Protocol**: If a setup meets all technical criteria (50 EMA, RSI, MACD, RVOL) but fails the liquidity test, the engine automatically routes the order ticket to the **Stock Portfolio as Common Shares**, preventing execution slippage while preserving the technical idea.

### C. The 70% Max-Profit Harvest Rule

  - For vertical spreads (Bull Call or Bear Put Spreads), as the underlying reaches the short strike, the spread achieves 70%–80% of max profit. Squeezing out the remaining 20% requires holding until expiration while bearing 100% reversal risk.
  - **Harvest Mandate**: Close vertical spreads when they reach **70%–75% of maximum potential spread width** (or at TP1). Recycles portfolio heat and frees up capital days ahead of expiration.

### D. Anti-Chop Re-Entry Cooldown

  - If an equity or option position hits its invalidation stop, the ticker enters a mandatory **3-to-5 trading day Re-Entry Cooldown**.
  - Even if the stock closes back above the 50 EMA the following day, re-entry is blocked until the cooldown elapses, shielding the portfolio from choppy, range-bound whip patterns.

### E. News Cycle Telemetry Synthesis

  - Real-time news events are incorporated directly through quantitative footprint indicators rather than noisy, lagging news headline scrapers:
      
      - **RVOL $\ge 1.8\times - 2.5\times$**: The institutional footprint of breaking news and catalyst accumulation.
      - **Expanding IV Rank**: Captures market anticipation and volatility expansion.
      - **Price Action Confirmation**: A confirmed close above the 50 EMA confirms the market has absorbed the news constructively.
      - **Corporate Earnings Calendar Blackout**: The only hard calendar gatekeeper, requiring $\ge 21$ days clearance before upcoming earnings reports to prevent binary gap-down stop-outs.

### F. Universal Hard Qualification Gatekeeper Matrix

Before any ticker is submitted to the mathematical scoring engines (Composite Alpha Score or Options Quality Index), it must pass **100% of the six universal gatekeeper filters**:

|  |  |  |  |
| :-: | :-: | :-: | :-: |
| **Gatekeeper Filter** | **Parameter / Condition** | **Institutional Rationale** | **Enforcement Target** |
| **1. 50 EMA Velocity** | Price >= EMA50 & reclaim_days <= 3 | Captures fresh momentum; rejects stale, extended moves. | Long Options & Stocks |
| **2. Retrace Taxonomy** | retrace_type in ["EMA50", "DB", "OTE"] | Requires high-probability institutional pullback structures. | Long Options & Stocks |
| **3. Overhead Runway** | runway >= 5.0% or CLEAR (Above 200 SMA) | Prevents entering directly below major 200 SMA supply walls. | Long Options & Stocks |
| **4. RSI Floor** | RSI(14) >= 45.0 | Filters out severe institutional distribution and falling knives. | Long Options & Stocks |
| **5. MACD Momentum** | Histogram[t] > Histogram[t-1] | Confirms selling deceleration and upward curl without lag. | Long Options & Stocks |
| **6. Dow Market Structure** | Market Structure != "BEARISH_LH_LL" | Rejects dead-cat bounces and bear traps in structural downtrends. | Long Options & Stocks |

-----

## 7\. Mathematical Scoring Engines

### A. Cash Equities Alpha Composite Score (0 to 100)

Calculated in engine/stocks.py (compute_alpha_composite_score).

$$\text{Stock Alpha Score} = S_{\text{Reclaim}} + S_{\text{RVOL}} + S_{\text{SectorRS}} + S_{\text{BetaElasticity}} + S_{\text{Momentum}} + S_{\text{Structure}}$$

| Component | Weight | High-Risk Sprint Metric | Balanced Swing Metric | Core Compounder Metric |
| :--- | :---: | :--- | :--- | :--- |
| **1. Reclaim Freshness** | **20 pts** | Day 0–1 Reclaim (20 pts), Day 2 (12 pts) | Day 0–2 Reclaim (20 pts), Day 3 (10 pts) | Stage 2 Alignment (20 pts) |
| **2. Institutional RVOL** | **20 pts** | $\text{RVOL} \ge 2.0\times$ (20 pts), $\ge 1.5\times$ (16 pts) | $\text{RVOL} \ge 1.8\times$ (20 pts), $\ge 1.3\times$ (16 pts) | $\text{RVOL} \ge 0.9\times$ (15 pts) |
| **3. Sector Relative Strength** | **15 pts** | Top-Quartile Sector + Mom Pos (15 pts) | Top-Quartile Sector + Mom Pos (15 pts) | Top-Quartile Sector + Mom Pos (15 pts) |
| **4. Beta & Price Elasticity** | **15 pts** | $\text{Beta} \ge 1.8, \text{ADR} \ge 3.5\%$ (15 pts) | $1.0 \le \text{Beta} \le 1.6, 2.0 \le \text{ADR} \le 3.6\%$ (15 pts) | $\text{Beta} \le 1.0$ Low-Vol Stability (15 pts) |
| **5. Universal Momentum** | **15 pts** | $\text{RSI} \ge 50$ + MACD Hist Hook (15 pts) | $\text{RSI} \ge 50$ + MACD Hist Hook (15 pts) | $\text{RSI} \ge 45$ Floor + Hook (13 pts) |
| **6. Market Structure** | **15 pts** | Confirmed BULLISH_HH_HL (15 pts) | Confirmed BULLISH_HH_HL (15 pts) | Multi-Month Base Consolidation (11–15 pts) |

-----

### B. Derivatives Options Alpha Radar Score (0 to 100)

Calculated in `engine/patterns.py` (`compute_options_alpha_score`).

$$\text{Options Alpha Score} = (\text{Directional Alpha} \times 0.35) + S_{\text{IV}} + S_{\text{Liquidity}} + S_{\text{Runway}} + S_{\text{Momentum}} + P_{\text{Earnings}}$$

| Component | Weight | High-Risk Sprint (45–90 DTE) | Balanced Swing (60–120 DTE) | Core LEAPS (Jan 2028) |
| :--- | :---: | :--- | :--- | :--- |
| **1. Directional Foundation** | **35 pts** | $0.35 \times \text{Stock Alpha}$ | $0.35 \times \text{Stock Alpha}$ | $0.35 \times \text{Stock Alpha}$ |
| **2. IV Rank Behavior** | **20 pts** | $\text{IV} \ge 60$ (20 pts), $\ge 45$ (15 pts), $\ge 30$ (8 pts) | $35 \le \text{IV} \le 65$ (20 pts), $25 \le \text{IV} < 35$ or $65 < \text{IV} \le 75$ (14 pts) | $\text{IV} < 35$ (20 pts), $< 50$ (12 pts), else 4 pts |
| **3. Contract Liquidity** | **20 pts** | $\text{OI} \ge 500 \text{ \& Spread} \le 8\%$ (20 pts), $\text{OI} \ge 250 \text{ \& Spread} \le 15\%$ (14 pts), $\text{OI} \ge 100$ (8 pts), else 3 pts | Same universal liquidity tiers | Same universal liquidity tiers |
| **4. 200 SMA Clearance Runway** | **15 pts** | Runway $\ge 900\%$ or Blue Sky (15 pts), $\ge 8\%$ (12 pts), $\ge 5\%$ (8 pts), else 2 pts | Same universal clearance tiers | Same universal clearance tiers |
| **5. Universal MACD/RSI Hook** | **10 pts** | $\text{RSI} \ge 50 \text{ + Hook}$ (10 pts), $\text{RSI} \ge 45 \text{ + Hook}$ (8 pts), $\text{RSI} \ge 45$ (5 pts) | Same universal momentum tiers | Same universal momentum tiers |
| **6. Earnings Blackout** | **Penalty** | $-35$ pts if $0 \le \text{DTE}_{\text{earnings}} \le 45$ | $-35$ pts if $0 \le \text{DTE}_{\text{earnings}} \le 45$ | LEAPS exempt ($0$ pts penalty) |

#### Dow Theory Market Structure in Options Logic:

1.  **Mandatory Hard Gatekeeper (****dow_structure_ok****)**:
      
      - Before any options contract is modeled or fetched, the underlying equity must pass the universal market structure filter: $$\text{Market Structure Regime} \neq \text{"BEARISH_LH_LL"}$$
      - If a ticker is printing Lower Highs and Lower Lows, it is **100% hard-disqualified from Bull Call Spreads and Call LEAPS**, preventing net debit burn on dead-cat bounces.
2.  **Mathematical Score Transmission**:
      
      - Component 1 (Directional Foundation, 35 pts) directly incorporates the **15-point Dow Theory Market Structure score** from the underlying stock: $$\text{Options Dow Component} = 0.35 \times \text{Stock Dow Score (up to 15 pts)} = \mathbf{+5.25\text{ pts}}$$
      - Confirmed Higher Highs and Higher Lows (BULLISH_HH_HL) directly contribute $+5.25$ points toward the final Options Quality ranking.
3.  **Downside Hedges (Bear Put Spreads)**:
      
      - For downside hedge recommendations, the engine reverses this logic: setups actively *require* BEARISH_LH_LL or overhead resistance rejections to qualify.

-----

## 8\. Complete Left-to-Right Architecture Mapping

|  |  |  |  |  |  |
| :-: | :-: | :-: | :-: | :-: | :-: |
| **Raw Ingestion Input** | **Derived Metric** | **Engine Function** | **Cash Equities Role** | **Options Derivatives Role** | **Storage Lifecycle** |
| **Close** **(504 daily bars)** | EMA 10, 21, 50, 200SMA 150, 200 | indicators.py :: compute_technical_snapshot() | Primary support floors; sets stop-loss anchor | Primary support floors; sets vertical spread strikes | **Stored Daily** (latest.json & history/*.json) |
| **High**, **Low**, **Close** | RSI(14) | indicators.py :: calculate_rsi() | **Universal Floor**: Disqualifies any setup with $\text{RSI} < 45.0$ | **Universal Floor**: Disqualifies any setup with $\text{RSI} < 45.0$ | **Stored Daily** (latest.json) |
| **Close** **(12, 26, 9)** | MACD Histogram | indicators.py :: calculate_macd() | **Momentum Hook**: Requires $\text{Hist}_t > \text{Hist}_{t-1}$ at 50 EMA | **Momentum Hook**: Requires $\text{Hist}_t > \text{Hist}_{t-1}$ at 50 EMA | **Stored Daily** (latest.json) |
| **Volume** **(20-day window)** | RVOL | indicators.py :: compute_technical_snapshot() | Confirms institutional accumulation ($\ge 1.8\times$ for High-Risk) | Validates breakout volume on options entry | **Stored Daily** (latest.json) |
| **Close** **+** **Low** **(20d)** | retrace_type, reclaim_days | patterns.py :: detect_retrace_pattern() | Classifies EMA50, DB, OTE, MA150 retests; D0–D2 velocity | Determines spread vehicle vs. LEAPS structure | **Stored Daily** (latest.json) |
| **Close** **vs** **SPY** **(60d)** | Beta | indicators.py :: calculate_beta() | Allocates to High Risk ($\ge 1.5$) vs Balanced vs Core ($\le 1.2$) | Calibrates strike widths and delta expansion targets | **Stored Daily** (latest.json) |
| **Close** **(252-day window)** | IV Rank | indicators.py :: compute_technical_snapshot() | Contextual range metric for share elasticity | **Key Divergence**: High-Risk rewards High IV; Core rewards Low IV | **Stored Daily** (latest.json) |
| **option_chain(exp)** | bid, ask, openInterest, volume | patterns.py :: verify_and_fetch_live_options() | Liquid Route Switch: If illiquid, routes setup to Stock Portfolio | Guarantees $\text{OI} \ge 500$ and spread $\le 8%$ | **Stored Daily** (latest.json) |
| **4 Benchmark Indices** | Macro Confluence(0 to 4 score) | benchmark.py :: calculate_benchmark_matrix() | Governs long share allocation vs cash defense | Dictates Call Spread vs. Bear Put Spread portfolio ratio | **Stored Daily** (latest.json & summary.json) |
| **Calendar / Earnings** | days_to_earnings | patterns.py :: evaluate_earnings_blackout() | Informational risk flag | **Hard Gate**: $-35$ pts penalty if earnings inside 21–45 DTE | **Stored Daily** (latest.json) |

-----

## 9\. Storage & Persistence Lifecycle

To maintain complete auditability while keeping repository storage within GitHub Pages static serving limits (\~15MB–20MB), the system enforces strict state separation:

### What Is Stored Daily in data/latest.json and data/history/YYYY-MM-DD.json

1.  **stock_recommendations** **&** **all_qualified_stocks**: Active common share setups partitioned across High-Risk, Balanced, and Core prongs with exact dollar-at-risk share counts, stops, TP1, and TP2 targets.
2.  **top_candidates****,** **strategic_leaps****, and** **downside_hedges**: Complete derivatives execution tickets specifying contract month, strike intervals, mid-price limit debits, max profit, delta, and verified Open Interest.
3.  **macro_breadth** **&** **benchmark_matrix**: 4-index confluence metrics, market breadth ratios, regime status, and narrative execution directives.
4.  **sector_strength** **&** **subsector_matrix**: 25 Sector ETF momentum rankings, 90 sub-industry metrics, and sector rotation cards.
5.  **trades_log.json** **&** **stock_trades_log.json**: Permanent stateful trade ledgers tracking active entries, scale-outs, trailing stops, realized P\&L, hold times, and root-cause loss attribution.

### What Is Ephemeral and NEVER Stored in JSON

1.  **Raw Historical 2-Year OHLCV Data**: The \~1.5 million historical data points ingested across the 520+ symbols are computed entirely in volatile RAM and discarded.
2.  **Exhaustive Multi-Strike Option Chains**: Thousands of strike/bid/ask combinations are evaluated in memory; only the selected long and short contract pair is retained.
3.  **Rolling Array Buffers**: Intermediate NumPy matrix calculations for rolling covariance, ATR, and Wilder's smoothing are garbage-collected immediately after computing the scalar indicators.

  

-----

## 10\. Continuous Daily Re-Scoring, Active Ledger Scoring & Relative-Strength Eviction

The engine maintains constant surveillance of existing positions through a recursive scoring loop that ensures capital is always allocated to the highest-velocity relative strength leaders.

### A. Active Ledger Scoring

  - Every open trade in data/trades_log.json and data/stock_trades_log.json is re-scored daily against live market closes, RVOL, and sector momentum.
  - **JSON Schema Fields** added to active trade objects:
      
      - current_alpha_score: 0-100 float.
      - score_breakdown: dictionary of component scores.
      - active_health_tier: TIER_A (De-risked), TIER_B (On-Track), TIER_C (Stagnant), TIER_D (Eviction Candidate).
      - consecutive_low_score_days: integer count.
      - eviction_eligible: boolean flag.

### B. Hysteresis & Hurdle Eviction Protocol

  - **3-session degradation persistence**: score < 40/100 or sector in bottom 30% for >= 3 consecutive closes, with days_active >= 5.
  - **Replacement hurdle**: newly qualified incoming candidate must outscore the lowest eviction-eligible incumbent by Delta >= 18.0 points (`REPLACEMENT_HURDLE_DELTA` in `engine/config.py`).
  - **Minimum aging buffer**: 5 trading days minimum holding before an eviction can be triggered (`MIN_EVICTION_AGING_DAYS` in `engine/config.py`).
  - **Exit classification**: status = 'CLOSED_EVICTED', exit_reason = 'Relative Strength Eviction'.

### C. Decoupled Sprint vs Anchor Book Heat Management

  - **Tactical Sprint Book**: Max 10-12 active slots (45-60 DTE Spreads and 10-14d Stock Swings).
  - **Strategic Anchor Book**: Max 6-8 active slots (Jan 2028 LEAPS and Core Compounders).
  - **Prevention of Throttling**: This separation prevents multi-month LEAPS holdings from freezing tactical turnover.

### D. Regime-Gated 3-Tier Risk Architecture

  - **Dynamic Capacity Caps**: 0 to 5 per tier (Core, Balanced, High-Risk) governed by the 4-Index Confluence Score (0 to 4).

### E. Strict Breakeven Accounting

  - **Separation of Outcomes**: Separation of CLOSED_BREAKEVEN (PnL == 0.00%) from strictly profitable trades (PnL > 0.00%) to prevent average winner dilution.

## 11\. Optimized Runway Architecture, Price-Gated Stagnation, Bounded Stop Limits & Calibrated Eviction

This section formalizes the empirical calibration and institutional risk optimizations implemented in Engine Release v2.2.

### A. The Price-Gated Stagnation Protocol (Protecting Compounders)

  - **The Core Rule**: Never liquidate a trade on a calendar timer if it is profitable (PnL > 0.0%) and holding above its 50-day EMA.
  - **Legacy Bottleneck Solved**: Previously, rigid Day 10 and Day 14 timers liquidated winning momentum runners (such as MU, VSAT, ON, FCX, KLAC) after early +10% to +20% gains during normal pullbacks, capping average winners at +18.7% and causing a 6.9% win rate on Balanced swings.
  - **The Refined Algorithm**:
      
      - If a position reaches its nominal horizon (Day 10 for Sprint, Day 14 for Balanced) while trading above its 50-day EMA with positive PnL (current_r >= 0.5R), the calendar kill-switch is bypassed.
      - The stop-loss is automatically moved to Breakeven (entry_price), converting the position into Tier A (House Money) and granting an extended runway (up to Day 22 for Sprints and Day 35 for Balanced) to reach final TP2 targets.
      - Stagnation exits trigger strictly if the trade is in negative territory or has broken below its 50-day EMA support.

### B. Bounded Stop-Loss Limits (Eliminating -20%+ High-Beta Bleed)

  - **Legacy Bottleneck Solved**: Previously, using min(ema50 * 0.985, price * 0.94) on extended large caps pushed stop losses up to 35% below entry, causing +1.0R targets to require unreachable +35% to +50% rallies, while allowing losing sprints (such as WULF, AMAT, LRCX) to drift down -20% to -24% before Day 10.
  - **The Bounded Stop Mandate**:
      
      - High-Risk Sprints: stop_price = round(max(ema50 * 0.985, price * 0.92), 2), capping maximum technical risk at strictly 8.0% from entry.
      - Balanced Swings: stop_price = round(max(ema50 * 0.98, price * 0.905), 2), capping maximum technical risk at strictly 9.5% from entry.
      - If an equity breaks its technical stop, it is liquidated immediately on Day 1, 2, or 3, bounding average losses to -4.5% to -5.0%.

### C. Realistic Two-Tranche Harvest Geometry

  - **Tranche 1 (Velocity Scale)**: 50% shares closed at TP1 (+1.5R to +2.5R, or +8% to +15% gain), banking the early momentum burst identified by RVOL and 50 EMA reclaims.
  - **Stop Trailing to Breakeven**: Once TP1 is scaled, stop moves to entry price.
  - **Tranche 2 (Trend Runner)**: Remaining 50% shares trailed along the rising 50 EMA / 21 EMA toward TP2 (+2.8R to +3.5R).

### D. Equity Anchor Book Activation (Stage 2 Secular Compounders)

  - To prevent 100% equity exposure to high-beta tactical swings, core_stock_candidates are merged into stock_recommendations in save_payloads().
  - Actively populates 4 to 6 slots in data/stock_trades_log.json under anchor_open, providing low-beta (beta <= 1.1), high-FCF stability with 200 SMA macro trailing stops.

### E. Calibrated Relative-Strength Eviction Gatekeepers

  - **Degradation Floor**: Lowered from score < 40.0 to score < 55.0 (Tier C Stagnant) for >= 2 consecutive closes, or prolonged stagnation (days_active >= 18) with score < 58.0.
  - **Replacement Hurdle**: Lowered from Delta >= 25.0 to Delta >= 18.0 points.
  - **Near-Capacity Threshold**: Eviction triggers when active open positions reach >= 85% capacity (>= 15 slots in an 18-slot book), actively recycling sluggish capital before total

-----

## 12\. Dedicated Cash Equities Portfolio Management & Execution Engine

This section provides the comprehensive, production-grade technical specification for the **Common Stock Portfolio Management Engine** (`engine/stocks.py`), detailing mathematical share sizing, multi-horizon trade structuring, dynamic macro gating, continuous health auditing, two-tranche execution, and relative-strength eviction.

### A. Mathematical Share Sizing & Capital Allocation Architecture

To ensure strict risk parity across high-beta growth stocks, large-cap compounders, and turnaround plays, positions are sized via **fixed-fractional Dollar-at-Risk** rather than flat dollar amounts or arbitrary share counts:

$$\text{Shares} = \max\left(1, \min\left(\left\lfloor \frac{\text{Max Risk Dollars}}{\text{Risk Per Share}} \right\rfloor, \left\lfloor \frac{\text{Max Capital Allocation}}{\text{Entry Price}} \right\rfloor\right)\right)$$

#### 1. Sizing Parameter Definitions:
* **Account Baseline**: Starting capital base $C = \$100,000$, designed to scale dynamically to $\$500,000+$ without changing algorithmic logic.
* **Effective Risk Percentage ($R_{\%}$)**: Default is $0.45\%$ ($0.0045$), bounding maximum loss to $\$350 - \$500$ per setup on a $\$100,000$ base:
  $$\text{Max Risk Dollars} = C \times R_{\%} = \$100,000 \times 0.0045 = \$450.00$$
  *(On a $\$500,000$ account, $\text{Max Risk Dollars} = \$2,250.00$)*.
* **Risk Per Share ($\Delta P_{\text{risk}}$)**: Calculated as the distance from entry price to the technical invalidation stop, enforced with a minimum $2.0\%$ floor:
  $$\Delta P_{\text{risk}} = \max\left(\text{Entry Price} \times 0.02, \; \text{Entry Price} - \text{Stop Price}\right)$$
* **Capital Ceiling Safeguard ($C_{\text{max}}$)**: Hard-capped at **$6.0\%$ of total portfolio capital** ($0.06$):
  $$\text{Max Capital Allocation} = C \times 0.06 = \$100,000 \times 0.06 = \$6,000.00$$
  *(On a $\$500,000$ account, $\text{Max Capital Allocation} = \$30,000.00$)*.
* **Capital Ceiling Safeguard Rationale**: If a high-dollar stock has an ultra-tight technical stop (e.g., a $1.2\%$ stop on a $\$200$ stock = $\$2.40$ risk), pure risk-based sizing would allocate $\lfloor \$450 / \$2.40 \rfloor = 187$ shares ($37,400 deployed, or $37.4\%$ of the account). The $6.0\%$ capital ceiling strictly caps deployment to $\lfloor \$6,000 / \$200 \rfloor = 30$ shares, eliminating catastrophic single-stock gap-down risk.

#### 2. Scalable Capital Sizing Reference Matrix:
| Stock Ticker | Entry Price | Technical Stop | Risk / Share | Risk-Based Shares | 6% Capital Cap | Final Shares | Capital Deployed | Actual $ at Risk | Effective Risk % |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **NVDA** (Balanced) | $92.89 | $85.46 (-8.0%) | $7.43 | 60 sh | 64 sh ($6,000) | **60 sh** | $5,573.40 | $445.80 | **0.45%** |
| **DOCU** (High-Risk) | $143.55 | $132.07 (-8.0%) | $11.48 | 39 sh | 41 sh ($6,000) | **39 sh** | $5,598.45 | $447.72 | **0.45%** |
| **MS** (Balanced) | $112.24 | $103.26 (-8.0%) | $8.98 | 50 sh | 53 sh ($6,000) | **50 sh** | $5,612.00 | $449.00 | **0.45%** |
| **SPY** (Core Anchor)| $764.29 | $692.80 (-9.4%) | $71.49 | 6 sh | 7 sh ($6,000) | **6 sh** | $4,585.74 | $428.94 | **0.43%** |
| **Tight-Stop Play** | $50.00 | $49.25 (-1.5%) | $1.00 (min 2%)| 450 sh | 120 sh ($6,000)| **120 sh (Capped)**| $6,000.00 | $120.00 | **0.12%** |

---

### B. Decoupled Sub-Books & Capacity Allocation

The cash equity portfolio enforces a hard capacity target of **18 active positions** (`MAX_STOCK_PORTFOLIO_SLOTS = 18`), dynamically managed between 16 and 21 slots. To prevent slow-moving compounders from choking high-velocity trading, capital is partitioned across two decoupled books:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             COMMON STOCK CAPACITY ARCHITECTURE (18 SLOTS)                        │
├────────────────────────────────────────────────────┬─────────────────────────────────────────────┤
│ TACTICAL SPRINT BOOK (Max 12 Slots)                │ STRATEGIC ANCHOR BOOK (Max 6 Slots)         │
├────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ • Prongs: High-Risk Sprint & Balanced Swing        │ • Prong: Low-Risk Core Secular Compounders   │
│ • Holding Horizon: 10 – 35 sessions                │ • Holding Horizon: 40 – 120+ sessions        │
│ • Technical Basis: 50 EMA Reclaim + RVOL + MACD    │ • Technical Basis: Stage 2 Stack (50>150>200)│
│ • Exit Mechanism: TP1 Scale (50%) + Trailing EMA   │ • Exit Mechanism: 200 SMA Macro Stop (-3.0%) │
│ • Stagnation: Price-Gated 22d / 35d Extended Runway│ • Stagnation: None (Trend Following)        │
│ • Eviction: Eligible for Relative-Strength Eviction │ • Eviction: Independent Anchor Eviction Pool│
└────────────────────────────────────────────────────┴─────────────────────────────────────────────┘
```

---

### C. Macro Regime Steering & Sector Contagion Shields

Equity execution is organically modulated by the **4-Index Macro Benchmark Matrix** ($M \in [0, 4]$ across SPY, QQQ, RSP, IWM vs. 50 EMA):

$$\text{Macro Confluence Score } M = \sum_{i=1}^4 \mathbf{1}[ \text{Index}_i \ge \text{EMA}_{50} ]$$

#### 1. Dynamic Risk-Tier Capacities:
Derived via `engine/indicators.py::get_regime_tier_capacities(M)`:
* **Risk-On ($M=4$)**: Full offense. High-Risk: **5**, Balanced: **5**, Core: **5** slots permitted.
* **Cautious Risk-On ($M=3$)**: High-Risk throttled to **3**, Balanced: **5**, Core: **5** slots.
* **Mixed / Rotation ($M=2$)**: High-Risk throttled to **1**, Balanced: **3**, Core: **4** slots.
* **Defensive / Chop ($M=1$)**: High-Risk: **0 (Strict Freeze)**, Balanced: **1**, Core: **3** slots.
* **Systemic Breakdown ($M=0$)**: High-Risk: **0**, Balanced: **0**, Core: **1 (Max Capital Preservation)**.

#### 2. Sector Contagion Shield (Tech & Growth Freeze):
* When macro confluence deteriorates to **$M \le 2$ (Mixed or Hostile Regimes)**, institutional distribution disproportionately impacts high-multiple tech, software, and semiconductor names.
* **Automated Shield**: In `update_stock_trades_log`, when $M \le 2$, any new candidate in the High-Risk or Balanced prongs belonging to Technology, Semiconductors, or Software is automatically disqualified:
  ```python
  if confluence_score <= 2 and cand_prong in ["HIGH_RISK", "BALANCED"]:
      sec_upper = (s_rec.get("sector") or "").upper()
      if any(kw in sec_upper for kw in ["TECH", "SEMIS", "SOFTWARE"]):
          continue  # Protect against Nasdaq/tech distribution contagion
  ```
* This isolates the portfolio from growth stock liquidation cascades while permitting defensive rotation entries (e.g., Energy, Utilities, Healthcare, Staples).

---

### D. Dynamic Sector Concentration Limits (30%–35% Cap)

* **Sector Capital Cap**: A single sector may consume at most **30%–35% of total portfolio capital** (~5 to 6 positions in an 18-slot portfolio).
* **Sub-Industry Capital Cap**: A single sub-industry may consume at most **20% of total portfolio capital** (~3 to 4 positions).
* **Institutional Benefit**: Rather than arbitrary limits (e.g., 3 stocks per sector), this allows the platform to capture powerful institutional sector rotations without creating vulnerable hyper-concentration.

---

### E. Two-Tranche Scale & Trail Execution Engine

Every equity trade executes under an automated **Two-Tranche Scale & Trail Model**:

```text
       ┌─────────────────────────────────────────────────────────────┐
       │             TWO-TRANCHE SCALE & TRAIL MECHANICS             │
       ├─────────────────────────────────────────────────────────────┤
       │ 1. Tranche 1 (50% of Shares) — Target: TP1 (+2.0R to +2.5R) │
       │    • Lock in initial gains (+12% to +18%)                   │
       │    • Move Stop Loss on Tranche 2 to BREAKEVEN (Entry Price) │
       │    • Transition Health Tier to Tier A: House Money          │
       │ 2. Tranche 2 (50% of Shares) — Target: Trailing Runner      │
       │    • Sprint: Trail 21 EMA until daily close below           │
       │    • Balanced: Trail 50 EMA until daily close below         │
       │    • Core: Macro Invalidation Stop at 200 SMA -3.0%         │
       └─────────────────────────────────────────────────────────────┘
```

#### Blended Realized P&L Formula:
$$\text{Blended PnL } (\%) = 0.50 \times \left(\frac{\text{TP1 Price} - \text{Entry Price}}{\text{Entry Price}}\right) + 0.50 \times \left(\frac{\text{Exit Price}_{\text{Tranche 2}} - \text{Entry Price}}{\text{Entry Price}}\right)$$

Once Tranche 1 hits TP1:
1. Trade status transitions from `OPEN` to `TP1_SCALED`.
2. Stop loss on Tranche 2 is automatically moved to **Breakeven (Entry Price)**.
3. Health Tier transitions to **Tier A: House Money**, making the trade permanently immune to eviction.
4. Capital risk on the position drops to exactly **$0.00**, allowing the trader to hold the runner for multi-month trend expansions with zero psychological friction.

---

### F. Continuous Health Tier Auditing Protocol

On every market-hours scan run, `engine/stocks.py::audit_stock_positions()` audits all open positions against live market bars and re-computes an **Active Health Tier**:

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              ACTIVE HEALTH TIER TAXONOMY (TIERS A–D)                             │
├────────┬─────────────────┬───────────────────────────────────┬───────────────────────────────────┤
│ Tier   │ Badge / Label   │ Technical Criteria                │ Portfolio Action / State          │
├────────┼─────────────────┼───────────────────────────────────┼───────────────────────────────────┤
│ Tier A │ 🟢 HOUSE MONEY  │ TP1 Hit OR Stop ≥ Entry Price     │ De-risked; Eviction-Exempt        │
│ Tier B │ 🔵 ON-TRACK     │ Score ≥ 60.0 & Close ≥ EMA50      │ Healthy Winner; Normal Trailing   │
│ Tier C │ 🟡 STAGNANT     │ Score 50.0–59.9 OR Approaching Timers│ Momentum Slowing; Stop Tightened │
│ Tier D │ 🔴 EVICTION ELIG│ Score < 55.0 for ≥ 2 days OR Stalled│ Marked for Active Replacement     │
└────────┴─────────────────┴───────────────────────────────────┴───────────────────────────────────┘
```

#### Eviction Eligibility Criteria (`compute_active_health_tier`):
A position is flagged as `eviction_eligible = True` if:
1. **Low Alpha Score Persistence**: `current_alpha_score < 55.0` for at least **2 consecutive trading sessions** (`consecutive_low_score_days >= 2`), AND `days_active >= 5`.
2. **Prolonged Stagnation**: Position has been held for $\ge 18$ trading sessions with `current_alpha_score < 58.0` and price below the 21 EMA.
3. **Severe Structural Breakdown**: Stock breaks below its 50-day EMA and prints a BEARISH_LH_LL market structure with declining RVOL.

---

### G. Relative-Strength Eviction Algorithm

When a new high-conviction setup qualifies during market hours, the engine checks whether the stock book has reached capacity:

```text
       ┌─────────────────────────────────────────────────────────────┐
       │             RELATIVE-STRENGTH EVICTION ENGINE               │
       ├─────────────────────────────────────────────────────────────┤
       │ 1. Capacity Trigger: Total Open ≥ 18 OR Book ≥ 85% Capacity │
       │    OR any active incumbent is flagged Tier D                │
       │ 2. Candidate Sub-Book Routing:                              │
       │    • If candidate is Core -> target Anchor Eviction Pool    │
       │    • If candidate is Tactical -> target Sprint Eviction Pool│
       │ 3. Aging Gatekeeper:                                        │
       │    • Incumbent must have days_active ≥ 5 sessions            │
       │ 4. Hurdle Advantage Gatekeeper:                             │
       │    • Score_Candidate - Score_Incumbent ≥ 18.0 points        │
       │ 5. Execution:                                               │
       │    • Incumbent closed as CLOSED_EVICTED                     │
       │    • Realized P&L booked at current price                   │
       │    • New candidate allocated to vacated slot                │
       └─────────────────────────────────────────────────────────────┘
```

#### Eviction Hurdle Formula:
$$\Delta_{\text{Alpha}} = \text{Score}_{\text{Candidate}} - \text{Score}_{\text{Incumbent}} \ge 18.0 \text{ pts}$$

* **Hysteresis Rationale**: Requiring an 18-point score differential prevents portfolio "churn" caused by minor day-to-day score fluctuations (e.g., replacing a 72-point stock with a 74-point stock).
* **Aging Safeguard**: `MIN_EVICTION_AGING_DAYS = 5` ensures every newly entered trade has at least one full trading week to develop before being subject to eviction.

---

### H. Persistent Stock Trade Ledger Schema (`data/stock_trades_log.json`)

The common stock portfolio maintains its own audit log independent of options trades:

```json
{
  "summary": {
    "total_trades": 45,
    "open_trades": 18,
    "closed_trades": 27,
    "winning_trades": 19,
    "losing_trades": 8,
    "win_rate_pct": 70.37,
    "profit_factor": 2.45,
    "total_realized_pnl_dollars": 6845.20,
    "total_realized_pnl_pct": 68.45,
    "avg_win_pct": 14.82,
    "avg_loss_pct": -5.12,
    "avg_holding_days": 16.4,
    "evicted_trades": 3
  },
  "trades": [
    {
      "id": "STOCK_2026-09-12_NVDA",
      "ticker": "NVDA",
      "company_name": "NVIDIA Corporation",
      "sector": "Information Technology",
      "sub_industry": "Semiconductors",
      "entry_date": "2026-09-12",
      "entry_price": 92.89,
      "shares": 60,
      "capital_deployed": 5573.40,
      "actual_risk_dollars": 445.80,
      "risk_pct_actual": 0.45,
      "strategy_prong": "BALANCED",
      "horizon_tier": "BALANCED_SWING",
      "stop_price": 85.46,
      "tp1": 111.47,
      "tp2": 118.89,
      "status": "OPEN",
      "active_health_tier": "TIER_B_HEALTHY",
      "health_badge": "🔵 ON-TRACK",
      "eviction_eligible": false,
      "days_active": 1,
      "current_alpha_score": 82.5
    }
  ]
}
```
