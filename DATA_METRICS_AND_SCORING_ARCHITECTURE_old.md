# Quantitative Data Pipeline, Derived Metrics & Dual Scoring Architecture

This document provides a comprehensive technical reference for the **ABI Strategy Terminal & Quantitative Execution Engine**. It details:
1. Exactly which market data points are ingested from `yfinance`.
2. All mathematical and algorithmic derived metrics generated across the ingestion pipeline.
3. How these metrics are synthesized into the multi-factor scoring engines for **Cash Equities** (`Alpha Composite Score`) and **Derivatives** (`Options Alpha Radar Score`).
4. A complete left-to-right tabular mapping tracing raw inputs to execution logic.
5. The persistence lifecycle: which metrics are permanently archived daily in `data/latest.json` versus which exist ephemerally during runtime.

---

## 1. Raw Market Data Ingestion (`yfinance`)

Data ingestion is orchestrated in `engine/data_loader.py`, `engine/scanner.py`, and `engine/patterns.py` via `yfinance`.

### A. Universe Definition
* **Equities Universe**: 493+ S&P 500 and NASDAQ-100 constituents dynamically fetched from Wikipedia/SEC or backed by `engine/universe.py` master taxonomy.
* **Sector Benchmark Universe**: 25 Sector & Thematic ETFs (`XLK`, `XLC`, `XLF`, `XLE`, `XLV`, `XLI`, `XLY`, `XLP`, `XLU`, `XLB`, `XLRE`, `SMH`, `IGV`, `XBI`, `KRE`, `XHB`, `XRT`, `ITB`, `GDX`, `TAN`, `JETS`, `IYT`, `VNQ`, `COPX`, `URA`).
* **Macro Benchmark Ribbon**: 4 broad-market index ETFs (`SPY`, `QQQ`, `RSP`, `IWM`).

### B. Raw Ingestion Endpoints & Fields
| Source Function | Call Pattern | Raw Ingested Fields | Update Frequency |
| :--- | :--- | :--- | :--- |
| **Daily OHLCV Batch** | `yf.download(tickers, period="2y", interval="1d", group_by="ticker", auto_adjust=False)` | `Open`, `High`, `Low`, `Close`, `Adj Close`, `Volume` (504 daily bars per symbol) | EOD (4:30 PM EDT) & Intraday |
| **Options Chain Inspection** | `yf.Ticker(ticker).option_chain(expiration_date)` | `strike`, `bid`, `ask`, `lastPrice`, `openInterest`, `volume`, `impliedVolatility`, `contractSymbol` | Real-time / Post-Close Scan |
| **Corporate Earnings Calendar** | `yf.Ticker(ticker).calendar` or `.get_earnings_dates()` | `Earnings Date` (timestamp / date) | Daily Scan |
| **Intraday 4H Verification** | `yf.download(ticker, period="1mo", interval="1h")` (aggregated to 4H) | 4-Hour `Open`, `High`, `Low`, `Close`, `Volume` | Live Intraday Scans Only |

---

## 2. Derived Quantitative Metrics

Every raw OHLCV bar and options quote is processed through `engine/indicators.py`, `engine/patterns.py`, and `engine/stocks.py` to extract structural, volatility, and trend metrics.

### 1. Exponential & Simple Moving Averages
* **`EMA 10` & `EMA 21`**: Fast momentum and short-term mean reversion baselines.
* **`EMA 50`**: The core structural institutional support/resistance anchor:
  $$\text{EMA}_t = \text{Price}_t \times \left(\frac{2}{N+1}\right) + \text{EMA}_{t-1} \times \left(1 - \frac{2}{N+1}\right), \quad N=50$$
* **`SMA 150`**: Intermediate cyclical support.
* **`SMA 200`**: Institutional macro trend divider.
* **`EMA 50 Distance %`**: $\frac{\text{Price} - \text{EMA}_{50}}{\text{EMA}_{50}} \times 100$.
* **`EMA 50 Slope`**: Normalized 5-day slope of the 50 EMA: $\frac{\text{EMA}_{50, t} - \text{EMA}_{50, t-5}}{\text{EMA}_{50, t-5}} \times 100$.
* **`SMA 200 Clearance / Overhead Runway %`**:
  * If $\text{Price} \ge \text{SMA}_{200}$: Tagged as `CLEAR (Above 200MA)` (`runway = 999.0` or `0.0`).
  * If $\text{Price} < \text{SMA}_{200}$: Measured as $\frac{\text{SMA}_{200} - \text{Price}}{\text{Price}} \times 100$. Must be $\ge 5.0\%$ to qualify.
  * If History $< 200$ bars (Recent IPOs/Spinoffs): Tagged as `has_200sma = False`, labeled `N/A (<200d History)`, and receives neutral baseline.

### 2. Relative Volume (RVOL)
Measures institutional participation on breakout and support reclaims:
$$\text{RVOL} = \frac{\text{Volume}_0}{\frac{1}{20}\sum_{i=1}^{20} \text{Volume}_{-i}}$$
* $\text{RVOL} \ge 1.0\times$: Institutional accumulation confirmed.
* $\text{RVOL} \ge 2.0\times$: Heavy institutional volume surge (maximum alpha points).

### 3. Momentum & Relative Strength Spread
* **`RSI(14)`**: Wilder\x27s 14-day Relative Strength Index. Enforces $\text{RSI} > 48.0$ (bullish regime).
* **`MACD(12, 26, 9)`**: MACD line, 9-day signal line, and MACD Histogram. Enforces Histogram $\ge -0.05$ and crawling upward.
* **`Sector Momentum Spread` (`mom_spread`)**:
  $$\text{mom\_spread} = \text{Return}_{20\text{d}}(\text{Sector ETF}) - \text{Return}_{20\text{d}}(\text{SPY})$$
  Quantifies whether the ticker\x27s parent sector has an active macro tailwind ($>0\%$) or headwind ($<0\%$).

### 4. Volatility, Range & Risk Metrics
* **`ADR%` (Average Daily Range %)**:
  $$\text{ADR\%} = \frac{\frac{1}{20}\sum_{i=0}^{19} (\text{High}_{-i} - \text{Low}_{-i})}{\text{Close}_0} \times 100$$
  Filters out dormant stocks ($\text{ADR} \ge 1.5\%$).
* **60-Day Rolling `Beta` vs. `SPY`**:
  $$\beta = \frac{\text{Cov}(R_{\text{Stock}}, R_{\text{SPY}})}{\text{Var}(R_{\text{SPY}})}$$
  Ensures controlled beta drag ($\beta \le 2.2$) for secular core investments.
* **1-Year Implied Volatility Rank (`IV Rank`)**:
  Calculates the percentile rank of current 30-day implied volatility (or 20-day historical realized volatility proxy) across its 252-day range:
  $$\text{IV Rank} = \frac{\text{IV}_{\text{Current}} - \text{IV}_{\text{Min}, 252\text{d}}}{\text{IV}_{\text{Max}, 252\text{d}} - \text{IV}_{\text{Min}, 252\text{d}}} \times 100$$
  * $\text{IV Rank} < 20\%$: Optimal for net debit options (cheap volatility).
  * $\text{IV Rank} > 60\%$: Volatility too expensive for debit spreads.

### 5. Market Structure & Dow Theory Regime (`engine/indicators.py`)
Analyzes 5-bar fractal swing pivots across high and low series, combined with leading-edge $T_0/T_{-1}$ price velocity:
* **`🟢 HH/HL (CONFIRMED)`**: Validated multi-bar higher-high and higher-low sequence with structural breakout.
* **`🟢 HH/HL (EMERGING)`**: Leading-edge Day 0 or Day 1 velocity where current price pierces the recent swing high before fractal completion.
* **`🟡 BASE (EMERGING HH)`**: Multi-week consolidation base testing upper resistance.
* **`🔴 LH/LL BEARISH`**: Lower-high and lower-low sequence (flags bull traps).

### 6. Support Retest & Reclaim Velocity (`engine/patterns.py`)
* **Retrace Types**:
  * `EMA50`: Clean bounce within $1.5\%$ of the rising 50-day EMA.
  * `DB`: Double bottom within $1.5\%$ of prior 20-day swing low.
  * `OTE`: Optimal Trade Entry (Fibonacci $61.8\% - 78.6\%$ retracement).
  * `MA150`: Deep cyclical retest of the 150-day simple moving average.
* **`reclaim_days`**:
  * `0`: Day 0 intraday cross (marked `🟡 PENDING CLOSE` until 4:00 PM ET).
  * `1`: Day 1 confirmed close above EMA50 with follow-through (Prime entry).
  * `2-3`: Pullback retest holding above EMA50.
  * `>3`: Stale reclaim (rejected by funnel).

---

## 3. Dual Scoring Engines: Full Mathematical Breakdown

### A. Cash Equities: `Alpha Composite Score` (0 to 100)
Calculated in `engine/stocks.py` (`compute_alpha_composite_score`). Designed for directional equity swings and share accumulation.

$$\text{Alpha Composite Score} = S_{\text{Retrace}} + S_{\text{Structure}} + S_{\text{Macro}} + S_{\text{RVOL}} + S_{\text{RR}}$$

| Factor | Weight | Evaluation Criteria | Points Awarded |
| :--- | :---: | :--- | :---: |
| **1. Retrace & Reclaim Momentum** | **25 pts** | • Day 0 Reclaim (`reclaim_days = 0`)<br>• Day 1 Reclaim (`reclaim_days = 1`)<br>• Day 2 Reclaim (`reclaim_days = 2`)<br>• Day 3 Reclaim (`reclaim_days = 3`)<br>• Stale Reclaim (`> 3`) | **25 pts**<br>**22 pts**<br>**18 pts**<br>**12 pts**<br>0 pts |
| **2. Dow Theory Market Structure** | **20 pts** | • Confirmed HH/HL (`BULLISH_HH_HL` + Confirmed)<br>• Emerging HH/HL (`BULLISH_HH_HL` + Emerging)<br>• Consolidation Base (`CONSOLIDATION_BASE`)<br>• Bearish LH/LL (`BEARISH_LH_LL`) | **20 pts**<br>**18 pts**<br>**12 pts**<br>**$-15$ pts penalty** |
| **3. Macro & Sector Confluence** | **20 pts** | • 4/4 Indices $> 50$ EMA + $\text{mom\_spread} \ge +2.0\%$<br>• 4/4 Indices $> 50$ EMA + $\text{mom\_spread} \ge 0\%$<br>• 3/4 Indices $> 50$ EMA + Positive Sector Flow<br>• Mixed Breadth (2/4 Indices) + Flat Sector<br>• Systemic Breakdown (0-1 Indices) or Negative Spread | **20 pts**<br>**16 pts**<br>**12 pts**<br>**6 pts**<br>**$-10$ pts penalty** |
| **4. Institutional RVOL** | **20 pts** | • $\text{RVOL} \ge 2.0\times$ (Volume surge)<br>• $\text{RVOL} \ge 1.5\times$ (Strong accumulation)<br>• $\text{RVOL} \ge 1.2\times$ (Above-average participation)<br>• $\text{RVOL} \ge 1.0\times$ (Baseline institutional interest)<br>• $\text{RVOL} < 1.0\times$ (Sub-par volume) | **20 pts**<br>**16 pts**<br>**12 pts**<br>**8 pts**<br>2 pts |
| **5. Risk-to-Reward Geometry** | **15 pts** | • $\text{R:R} \ge 3.5:1$<br>• $\text{R:R} \ge 3.0:1$<br>• $\text{R:R} \ge 2.5:1$<br>• $\text{R:R} < 2.5:1$ | **15 pts**<br>**12 pts**<br>**8 pts**<br>0 pts (Disqualified) |

* **Sector Diversity Guardrail**: After scoring, the top 5 selection enforces a hard cap of **maximum 2 tickers per sector** to prevent correlated risk cluster blowups.

---

### B. Derivatives: `Options Alpha Radar Score` (0 to 100)
Calculated in `engine/patterns.py` (`compute_options_alpha_score`). Specifically models asymmetric leverage, option Greeks, and expiration mechanics.

$$\text{Options Alpha Score} = (\text{Directional Alpha} \times 0.40) + S_{\text{IV}} + S_{\text{Liquidity}} + S_{\text{Runway}} + P_{\text{Earnings}}$$

| Factor | Weight | Evaluation Criteria | Points Awarded |
| :--- | :---: | :--- | :---: |
| **1. Directional Alpha Foundation** | **40 pts** | Base directional setup quality scaled to 40% | $0.40 \times \text{Base Alpha}$ (0 to 40 pts) |
| **2. IV Rank Efficiency** | **25 pts** | • $\text{IV Rank} < 20\%$ (Extremely cheap volatility)<br>• $\text{IV Rank} < 35\%$ (Favorable debit cost)<br>• $\text{IV Rank} < 50\%$ (Moderate volatility)<br>• $\text{IV Rank} \ge 50\%$ (Elevated volatility) | **25 pts**<br>**20 pts**<br>**12 pts**<br>4 pts |
| **3. Institutional Options Liquidity** | **20 pts** | • $\text{Min OI} \ge 1000$ and $\text{Spread} \le 5\%$<br>• $\text{Min OI} \ge 500$ and $\text{Spread} \le 10\%$<br>• $\text{Min OI} \ge 250$ and $\text{Spread} \le 15\%$<br>• Off-hours quote blowout with $\text{Min OI} \ge 250$<br>• $\text{Min OI} < 250$ | **20 pts**<br>**15 pts**<br>**10 pts**<br>**10 pts** (OI-verified)<br>0 pts (Disqualified) |
| **4. Overhead 200 SMA Runway** | **15 pts** | • $\text{Price} \ge \text{SMA}_{200}$ (Blue Sky / All-Time Highs)<br>• Runway to 200 SMA $\ge 8.0\%$<br>• Runway to 200 SMA $\ge 5.0\%$<br>• History $< 200$ bars (Spinoff/IPO neutral baseline)<br>• Runway to 200 SMA $< 5.0\%$ | **15 pts**<br>**12 pts**<br>**8 pts**<br>**8 pts** (Item 2D)<br>2 pts (Disqualified) |
| **5. Earnings Blackout Guardrail** | **Penalty** | • **Confirmed Earnings within 45 DTE**<br>• **Unverified Earnings Date** (Item 1A)<br>• **Confirmed Earnings Outside 45 DTE** | **$-35$ pts penalty** (Blackout)<br>**$-2$ pts haircut** (Retains high rank)<br>0 pts (Safe) |

---

## 4. Complete Left-to-Right Architecture Table

| Raw Data Ingestion (`yfinance`) | Derived Quantitative Metric | Strategy Function & Module | Stock Scoring Usage | Options Scoring Usage | Persistence Lifecycle |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`Close` (504 daily bars)** | `EMA 10, 21, 50, 200`<br>`SMA 150, 200` | `indicators.py`<br>`compute_technical_snapshot()` | Trend filter (Price $\ge$ EMA50). Sets trailing stop baseline. | Trend filter (Price $\ge$ EMA50). Sets structural risk floor. | **Stored Daily** (`data/latest.json` & `history/*.json`) |
| **`Close` + `SMA 200`** | `overhead_runway_pct`<br>`overhead_runway_label`<br>`has_200sma` | `indicators.py`<br>`compute_technical_snapshot()` | Prevents longing directly into macro resistance. Sets TP ceiling. | Awarded 15 pts for Blue Sky; 8 pts for $<200$d; disqualified if $<5\%$. | **Stored Daily** (`data/latest.json` & `history/*.json`) |
| **`Close` (5-day window)** | `ema50_slope` | `indicators.py`<br>`compute_technical_snapshot()` | Confirms trend acceleration ($\text{slope} > 0$). | Required for Stage 2 Trend confirmation. | **Stored Daily** (`data/latest.json`) |
| **`Close` + `Low` (20-day window)** | `retrace_type`<br>`reclaim_days` | `patterns.py`<br>`detect_support_retrace()`<br>`calculate_reclaim_days()` | Retrace factor: 25 pts for Day 0, 22 pts for Day 1, down to 12 pts for Day 3. | Directional Alpha input; determines vertical spread vs LEAPS. | **Stored Daily** (`data/latest.json` & `history/*.json`) |
| **`High`, `Low`, `Close` (40-day window)** | `Market Structure`<br>(HH/HL vs LH/LL) | `indicators.py`<br>`analyze_market_structure()` | 20 pts for confirmed HH/HL, 18 pts for emerging; $-15$ pts penalty for LH/LL. | Input to Directional Alpha; filters out bear traps. | **Stored Daily** (`data/latest.json`) |
| **`Volume` (20-day window)** | `RVOL` (Relative Volume) | `indicators.py`<br>`compute_technical_snapshot()` | Institutional participation: up to 20 pts for $\text{RVOL} \ge 2.0\times$. | Confirms institutional interest on options entry candle. | **Stored Daily** (`data/latest.json`) |
| **`High`, `Low` (20-day window)** | `ADR%` (Avg Daily Range) | `indicators.py`<br>`compute_adr()` | Filters out dead stocks ($\text{ADR} \ge 1.5\%$). Validates volatility. | Confirms stock has sufficient range to reach short strike. | **Stored Daily** (`data/latest.json`) |
| **`Close` (Stock vs `SPY` 60-day)** | `Beta` | `indicators.py`<br>`compute_beta()` | Caps beta risk ($\beta \le 2.2$) on Core Secular Stock Accumulation. | Used in macro stress testing and portfolio risk budgeting. | **Stored Daily** (`data/latest.json`) |
| **`Close` (Sector ETF vs `SPY` 20d)** | `mom_spread` | `scanner.py`<br>`compute_relative_strength_matrix()` | Up to 20 pts for positive sector flow; $-10$ pts penalty for fading sector. | Feeds into Directional Alpha base score. | **Stored Daily** (`sector_strength` & `stock_recommendations`) |
| **`Close` (SPY, QQQ, RSP, IWM)** | `Benchmark Confluence`<br>(0 to 4 score) | `scanner.py`<br>`compute_benchmark_confluence()` | 4-Tier Action Verdict: Aggressive Buy (4), Cautious (3), Hold (2), Hedge (0-1). | Controls Long calls vs Tactical Bear Put Spread activation. | **Stored Daily** (`data/latest.json` & `history/*.json`) |
| **`Close` (252-day window)** | `IV Rank` | `indicators.py`<br>`compute_technical_snapshot()` | Background metric for volatility classification. | **Key Options Factor**: Up to 25 pts for cheap IV ($<20\%$). | **Stored Daily** (`data/latest.json`) |
| **`option_chain(exp)` (Calls/Puts)** | `long_oi`, `short_oi`, `total_vol`, `bid_ask_spread_pct` | `patterns.py`<br>`verify_and_fetch_live_options()` | Not used (Stock execution uses direct share limit orders). | **Key Options Factor**: 20 pts for high OI/tight spread; auto-skips if illiquid. | **Stored Daily** (`data/latest.json`) |
| **`option_chain(exp)` (Strikes/Bids/Asks)** | `long_strike`, `short_strike`, `est_debit`, `max_profit` | `patterns.py`<br>`model_bull_call_spread()` | Not used. | Constructs exact trade ticket, width, breakeven, and limit pricing. | **Stored Daily** (`data/latest.json` & `history/*.json`) |
| **`calendar` / `earnings_dates`** | `days_to_earnings`, `earnings_safe`, `earnings_status` | `patterns.py`<br>`evaluate_earnings_blackout()` | Informational display for swing holds. | **Key Guardrail**: $-35$ pts if confirmed inside 45 DTE; $-2$ pts if unverified. | **Stored Daily** (`data/latest.json`) |
| **`High`, `Low`, `Close` (Paper trades)** | `realized_pnl`, `exit_reason`, `loss_attribution` | `scanner.py` & `stocks.py`<br>`audit_open_trades()` | Tracks 50% TP1 (+2.5 R:R) and 50% 50 EMA trailing stop. | Tracks 50% TP1 (+100% ROI) and stop trailing. Diagnoses loss reasons. | **Stored Daily** (`data/trades_log.json` & `stock_trades_log.json`) |
| **2-Year Full OHLCV Matrix** | Raw Price & Volume series | Ingested in memory | Ephemeral computation only. | Ephemeral computation only. | **NEVER Stored** (Calculated during runtime only) |
| **Full Option Chains (All Strikes)** | Out-of-the-money chain arrays | Ingested in memory | Ephemeral computation only. | Ephemeral computation only. | **NEVER Stored** (Only matched strikes are saved) |
| **Rolling Covariance Arrays** | 60-day covariance series | Ingested in memory | Ephemeral computation only. | Ephemeral computation only. | **NEVER Stored** (Only final $\beta$ is saved) |
| **Intraday 1-Hour Sub-Bars** | 1-Hour OHLCV bars | `verify_multi_timeframe_confluence()` | Ephemeral verification only. | Ephemeral verification only. | **NEVER Stored** (Only confirmation badge is saved) |

---

## 5. Storage Lifecycle: Daily Persistent vs. Ephemeral Data

To keep the repository lightweight, fast, and within GitHub Pages static hosting limits (~15MB–20MB total footprint), the architecture strictly partitions persistent state from ephemeral computation:

### What Is Stored Daily in `data/latest.json` and `data/history/*.json`
1. **`top_candidates` (Options Spreads & Hedges)**: Final matched strikes, limit debits, max profit, R:R, expiration dates, verified Open Interest, volume, bid-ask spread %, options alpha score, and earnings status.
2. **`stock_recommendations` (Cash Equities)**: Entry prices, technical stops, TP1 (+2.5 R:R), TP2 (+3.5 R:R), dollar-at-risk share sizing, capital allocation %, alpha composite score, and Dow Theory structure badges.
3. **`strategic_leaps` & `core_stock_recommendations`**: Deep-ITM 2028 LEAPS and secular common share compounders with 200 SMA macro invalidation stops.
4. **`benchmark_matrix` & `market_commentary`**: 4-index confluence metrics (`SPY`, `QQQ`, `RSP`, `IWM`), regime verdicts, dynamic narrative, and execution mandates.
5. **`sector_strength` & `subsector_matrix`**: 25 Sector ETF momentum rankings, win rates, style classifications, and 90 sub-industry conviction tiers.
6. **`all_telemetry`**: Compact technical summary for 493+ constituents (price, distance to 50 EMA, 150 SMA, 200 SMA, Beta, ADR%, and qualified status).
7. **`trades_log.json` & `stock_trades_log.json`**: Persistent audit ledgers tracking trade entries, scale-outs, trailing stops, realized P&L, and root-cause loss attribution.

### What Is Ephemeral and NEVER Stored in JSON
1. **Raw Historical OHLCV DataFrames**: The massive two-year time-series tables for 520+ tickers (504 rows $\times$ 6 columns $\times$ 520 symbols = $\sim 1.57$ million data points) are processed purely in RAM and discarded.
2. **Exhaustive Options Chains**: The hundreds of strike rows across every available expiration cycle are filtered on the fly in RAM. Only the single optimal long and short strike pair is extracted.
3. **Rolling Covariance & Volatility Series**: Temporary NumPy arrays and Pandas rolling windows for Beta, HV, and ATR are garbage-collected immediately after computing the scalar metrics.
4. **Intraday Hourly Sub-Bars**: Ingested strictly to verify 4-Hour trend alignment and discarded after outputting the boolean confluence flag.
