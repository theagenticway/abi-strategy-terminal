# ABI Strategy Terminal & Options Alpha Radar

Automated market telemetry, EMA50 reclaim scanner, and asymmetric options trade structuring engine.

Designed to replace TradingView Pine Script alerts and Google Sheets with an automated, zero-cost, and robust pipeline hosted entirely on GitHub.

---

## 🏛️ Architecture Overview

* **Screening Engine**: Python + `yfinance` + `pandas` running via **GitHub Actions** on scheduled market-close and pre-market crons.
* **Storage Layer**: Flat immutable JSON and static HTML in `/data` (zero database dependencies, zero API rate limits).
* **Presentation**: Fast, client-side dashboard with Tailwind CSS (`index.html`) deployed via **GitHub Pages** or Netlify.
* **Agent Integration**: Direct machine-readable endpoints (`/data/latest.json` and `/data/telemetry.html`) engineered specifically for the 06:15 MST **Options Alpha Radar** scheduled Spark task.

---

## 📊 Endpoints & Data Schema

| Resource | Path | Description |
| :--- | :--- | :--- |
| **Visual Dashboard** | `https://<user>.github.io/<repo>/` | Interactive web terminal with date picker & filters |
| **Latest Telemetry API** | `https://<user>.github.io/<repo>/data/latest.json` | Today's macro breadth, top setups, & reclaims |
| **Historical Breadth Index** | `https://<user>.github.io/<repo>/data/summary.json` | 45+ day macro history (alerts, reclaims, regimes) |
| **Daily Archive** | `https://<user>.github.io/<repo>/data/history/YYYY-MM-DD.json` | Granular per-ticker telemetry snapshots |
| **Headless SSR Telemetry** | `https://<user>.github.io/<repo>/data/telemetry.html` | Pre-rendered static HTML table for zero-JS ingestion |

---

## ⚡ 1-Minute GitHub Setup

1. **Create Repository**: Push this directory to your GitHub account as `abi-strategy-terminal`.
2. **Enable Workflow Permissions**:
   * Go to **Settings** > **Actions** > **General** > **Workflow permissions**.
   * Select **"Read and write permissions"** and click **Save** (allows GitHub Actions to commit updated JSON data).
3. **Enable GitHub Pages**:
   * Go to **Settings** > **Pages**.
   * Under **Branch**, select `main` and `/ (root)`.
   * Click **Save**. Your dashboard will be live at `https://<username>.github.io/<repo>/`.
4. **Trigger First Scan**:
   * Go to the **Actions** tab > select **ABI Strategy Scanner & Telemetry Engine** > click **Run workflow**.

---

## 🤖 Spark Task Integration

In your scheduled 06:15 MST task (`Execute pre market options scan`):
* The task reads `https://<username>.github.io/<repo>/data/latest.json` or `telemetry.html`.
* Pre-computed fields (Entry, Invalidation Stop, TP1/TP2, Risk/Reward, 200 MA Clearance, and Velocity D0–D2) map directly into Section 2B of your **Executive Master State Tracker**.
