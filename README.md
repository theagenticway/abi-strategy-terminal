# ABI Strategy Terminal & Options Alpha Radar

Institutional-grade market telemetry, EMA50 reclaim scanner, asymmetric options trade structuring engine, and automated performance auditor.

Engineered to replace fragmented TradingView alerts, third-party webhooks, and manual spreadsheets with an autonomous, zero-cost pipeline hosted entirely on GitHub Actions and GitHub Pages.

---

## 🏛️ Architecture & System Blueprint

```
                     [Live Market Ingestion]
      493+ S&P 500 / NASDAQ-100 Constituents + 25 Sector ETFs
                     (yfinance batch OHLCV)
                                │
                                ▼
                   [Quantitative Math Engine]
   • EMAs (10, 21, 50, 200) & SMAs (150, 200 Overhead Clearance)
   • Wilder's RSI(14) & MACD(12, 26, 9) Histogram Progression
   • 60-day Rolling Beta vs. SPY & 20-day Average Daily Range (ADR%)
   • Multi-Factor Patterns: EMA50, Double Bottom (DB), OTE Fib 0.618–0.786
   • True Mathematical Sign-Flip Crossover & Consecutive Holding Days
                                │
                                ▼
                 [Options Structuring & Risk Filters]
   • 45-Day Corporate Earnings Blackout Filter (Avoids IV Crush)
   • 21-Day Theta Cliff Date & 8-Day Velocity Invalidation Stop
   • Modeled Exact Strike Pairs (At/ITM Long Call + Short Call at TP1)
   • Natural Mid-Price Limit Order Routing (Slippage Prevention)
   • Dynamic Macro Sizing Throttler ($1,000 / $750 / $500 based on SPY)
                                │
                                ▼
            [Automated Trade Auditor & Loss Attribution]
   • Logs & Audits Positions in `data/trades_log.json`
   • Automated Trailing Stops to Breakeven upon reaching TP1 (+2.5 R:R)
   • Root-Cause Loss Attribution (Macro Contagion vs. Sector Rotation vs. Idiosyncratic)
                                │
                                ▼
                      [Interactive Frontend]
          Tab 1: 🎯 Key Trading Recommendations (Spreads & LEAPS)
          Tab 2: 🌐 Macroeconomic Board (Full Netlify Parity)
          Tab 3: 📈 Performance & Audit Log (Historical Ledger)
```

---

## 🖥️ Terminal Interface & Core Modules

### Tab 1: 🎯 Key Trading Recommendations
* **Table 1: ⚡ Tactical Swings (Bull Call Spreads — 45–60 DTE)**:
  * High-velocity momentum setups: Confirmed D0–D2 reclaims, $\ge 5\%$ runway to 200 MA, and tight stops below 50 EMA.
  * Auto-models exact strikes: Long Strike ($\approx 0.55 - 0.60$ Delta), Short Strike ($\approx 0.30 - 0.35$ Delta at TP1), Width, Est. Debit, Max Profit.
  * Real-time 45-day earnings blackout status (`● SAFE (62d)` vs. `● BLACKOUT (18d)`).
  * Explicit order execution ticket: `LIMIT ORDER @ $X.XX MID-PRICE (Do not cross spread)`.
  * Dynamic macro allocation: Scales position risk ($1,000 / $750 / $500) based on broader index health.
* **Table 2: 🏛️ Strategic Core Accumulation (Deep-ITM Call LEAPS — Jan 2028 Expiry)**:
  * Multi-quarter secular compounders: Requires complete Stage 2 trend stack ($\text{Price} \ge \text{EMA 50} \ge \text{SMA 150} \ge \text{SMA 200}$) with a rising 200 MA.
  * Quality filter: Low beta drag ($\le 2.2$), moderate ADR ($\le 4.5\%$), and positive free cash flow.
  * Models deep-ITM strike at $\approx 80\%$ of price ($\approx 0.75 - 0.80$ Delta) with minimal theta decay (~500 DTE).
  * Macro Invalidation Stop: Anchored 3% below the structural 200-day moving average.
* **Table 3: Universe Telemetry & Active Reclaims**:
  * Complete, filterable monitor across all S&P 500 and NASDAQ constituents with live search.

### Tab 2: 🌐 Macroeconomic Board (1:1 Netlify Parity)
* **2D Momentum Quadrant**: Interactive scatter plot of 5-Day (short-term) vs. 20-Day (trend) momentum across 25 ETFs with color-coded style buckets (Growth, Cyclical, Defensive) and labeled quadrants (*Strong & Holding*, *Turning Up*, *Fading*, *Weak*).
* **ETF Ladder — VS EMA50**: Diverging bar chart centered on the 0% axis tracking all 25 sector ETFs.
* **Sector Strength**: 10-point scoring model with dynamic sort buttons (`Strength`, `Win %`, `Avg Ret`) that toggle right-hand badges to match.
* **★ Rotating In**: 8 HOT sector cards tracking bounce concentration, 3-day recency, and average return from support.
* **Top Sub-Sectors & Reclaims by Sector**: Performance drill-down across 90 granular sub-industries with click-to-filter capability.
* **Reclaim Detail & Fast Reclaims**: Multi-session filterable tables (`Latest`, `≤1d`, `≤3d`, `≤7d`, `≤30d`) with beta toggles.
* **Bounce Alerts**: Level distribution across EMA50, Double Bottoms (DB), Optimal Trade Entry (OTE Fib 0.618–0.786), and MA150.
* **Daily Activity Chart**: Multi-colored stacked horizontal bars split by bounce level across the last 14 to 30 market sessions.
* **Global Click-to-Filter Engine**: Clicking any sector pill, card, ladder bar, or table row instantly filters all tables, charts, and counts simultaneously with an active filter banner and clear button.

### Tab 3: 📈 Performance & Audit Log
* **Performance KPI Ribbon**: Live Cumulative Win Rate %, Profit Factor (Gross Gain / Loss), Total Logged Recommendations, Active Open Positions, and Average Holding Days.
* **Automated Trade Ledger**: Real-time tracking of active and historical paper trades against live High, Low, and Close market prices.
* **Automated Breakeven Trailing**: Trails stop to entry price when underlying reaches TP1 (+2.5 R:R).
* **Post-Mortem Loss Attribution Engine**: Automatically diagnoses why a stopped-out trade failed:
  * `[MACRO CONTAGION]`: Broad index selloff (SPY dropped $>1.2\%$ or broke 50 EMA).
  * `[SECTOR ROTATION]`: Institutional outflows broke sector ETF support ($>1.2\%$ drop).
  * `[EARNINGS VOLATILITY]`: Binary earnings event gap-down.
  * `[STAGNATION EXIT]`: Position stalled past 7–10 day velocity window.
  * `[IDIOSYNCRATIC BREAKDOWN]`: Stock broke down on volume despite healthy sector backdrop.

---

## 📊 Endpoints & Data Schema

| Resource | Path | Description |
| :--- | :--- | :--- |
| **Visual Dashboard** | `https://<user>.github.io/<repo>/` | Interactive 3-tab web terminal |
| **Latest Telemetry API** | `https://<user>.github.io/<repo>/data/latest.json` | Complete self-contained payload (all 15 structures) |
| **Trade Audit Ledger** | `https://<user>.github.io/<repo>/data/trades_log.json` | Persistent stateful paper-trade ledger & metrics |
| **Historical Breadth Index** | `https://<user>.github.io/<repo>/data/summary.json` | Rolling daily macro breadth and regime history |
| **Daily Snapshots** | `https://<user>.github.io/<repo>/data/history/YYYY-MM-DD.json` | Full granular historical daily archives |

---

## ⚙️ Automated GitHub Actions Workflow

Configured in `.github/workflows/scan.yml` running on Ubuntu runners with `contents: write` permissions:

* **05:45 MST (12:45 UTC) Mon–Fri**: Pre-market refresh ahead of the 06:15 MST Spark options scan.
* **Hourly (13:30 – 20:30 UTC Mon–Fri)**: Real-time scan during US market hours (06:30 AM – 01:30 PM MST) logging live price reclaims.
* **14:00 MST / 17:00 EDT (21:00 UTC) Mon–Fri**: Official market close, retention pruning, and final audit ledger update.
* **1-Year Retention Auto-Flush**: Automatically purges historical snapshots older than 365 days, capping repository growth at ~15MB–20MB.
* **Circuit Breaker**: Prevents overwriting valid telemetry if an upstream data feed provider glitch returns 0 tickers.

---

## 🧪 Automated Testing & Verification Suite

A comprehensive test suite of **25 unit, functional, and regression tests** is located in `/tests`:

```bash
# Run complete test suite locally
python3 -m unittest discover -s tests -p "test_*.py" -v
```

### Coverage:
1. **Mathematical & Indicator Integrity**: Validates `EMA 10/21/50/200`, `SMA 150/200`, `RSI(14)`, `MACD(12,26,9)`, `ADR%`, and rolling 60-day `Beta` against `SPY`.
2. **Pattern Recognition**: Verifies `detect_retrace_pattern` against float and Series inputs without `.iloc` errors; verifies velocity `calculate_reclaim_velocity`.
3. **Options Structuring**: Validates strike interval math, DTE calculation, 21-day theta cliff, 45-day earnings blackout window, and 200 MA clearance badges.
4. **Data Schemas**: Validates all 15 JSON structures, clean non-null labels, `.nojekyll` static file serving, and non-destructive `trades_log.json` state transitions.
5. **Loss Attribution**: Tests all 5 post-mortem failure classifications (macro, sector, earnings, stagnation, idiosyncratic).
