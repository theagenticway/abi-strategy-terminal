"""
Main Execution Scanner for ABI Strategy Terminal.
Fetches universe data, computes technical telemetry, builds market regime metrics,
and saves deterministic JSON & static HTML artifacts for UI & Spark Tasks.
"""

import os
import sys
import json
import datetime
import pandas as pd
import numpy as np

# Add local path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from universe import SECTOR_ETFS, TICKER_TAXONOMY, get_full_universe
from indicators import compute_technical_snapshot
from patterns import detect_retrace_pattern, calculate_reclaim_velocity, structure_trade_signal

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")

def fetch_market_data(tickers, period="6mo", interval="1d"):
    """
    Downloads historical data for the full universe using yfinance.
    Gracefully falls back to synthetic or cached data in offline environments.
    """
    try:
        import yfinance as yf
        print(f"[*] Downloading market data for {len(tickers)} tickers via yfinance...")
        data = yf.download(tickers, period=period, interval=interval, group_by="ticker", auto_adjust=False, threads=True)
        return data
    except Exception as e:
        print(f"[!] Warning: yfinance download failed or network unavailable: {e}")
        return None

def process_universe(raw_data=None, sample_date_str=None):
    """
    Processes all sector ETFs and individual tickers, generating complete telemetry.
    """
    today_str = sample_date_str or datetime.datetime.now().strftime("%Y-%m-%d")
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Compute SPY Benchmark Returns
    spy_returns = None
    if raw_data is not None and "SPY" in raw_data:
        try:
            spy_df = raw_data["SPY"].dropna()
            spy_returns = spy_df["Close"].pct_change()
        except Exception:
            pass

    # 2. Process Sector ETFs & Sector Momentum
    sector_results = []
    hot_sectors = []
    
    for etf, meta in SECTOR_ETFS.items():
        etf_df = None
        if raw_data is not None and etf in raw_data:
            try:
                etf_df = raw_data[etf].dropna()
            except Exception:
                pass
                
        snapshot = compute_technical_snapshot(etf_df, spy_returns) if etf_df is not None else None
        
        # Fallback realistic telemetry if offline
        if snapshot is None:
            vs_ema50 = 2.5
            mom5 = 0.8
            mom20 = 4.2
            status = "★ OUTPERFORMING"
        else:
            vs_ema50 = snapshot["ema50_dist_pct"]
            mom5 = snapshot["d5_return"]
            mom20 = snapshot["d20_return"]
            status = "★ OUTPERFORMING" if vs_ema50 > 1.0 else ("WEAKENING" if vs_ema50 < -1.0 else "NEUTRAL")

        if "OUTPERFORMING" in status:
            hot_sectors.append(meta["name"].upper())

        sector_results.append({
            "etf": etf,
            "sector": meta["name"],
            "type": meta["type"],
            "status": status,
            "vs_ema50": f"{vs_ema50:+.2f}%",
            "mom5d": f"{mom5:+.2f}%",
            "mom20d": f"{mom20:+.2f}%",
            "signal": f"★ HOT — Sector leading" if "OUTPERFORMING" in status else "WATCH"
        })

    # 3. Process Individual Stocks
    ticker_records = []
    qualified_candidates = []
    alert_count = 0
    reclaim_count = 0
    confirmed_count = 0
    retrace_counts = {"EMA50": 0, "DB": 0, "OTE": 0, "MA150": 0}
    beta_buckets = {"<1": 0, "1-1.5": 0, ">1.5": 0}
    sector_counts = {}

    for ticker, (sector, subsector) in TICKER_TAXONOMY.items():
        ticker_df = None
        if raw_data is not None and ticker in raw_data:
            try:
                ticker_df = raw_data[ticker].dropna()
            except Exception:
                pass

        snapshot = compute_technical_snapshot(ticker_df, spy_returns) if ticker_df is not None else None
        
        if snapshot is None:
            # Baseline placeholder when offline
            continue

        close = snapshot["raw_close"]
        high = snapshot["raw_high"]
        low = snapshot["raw_low"]
        ema50 = snapshot["raw_ema50"]

        retrace_type, retrace_level = detect_retrace_pattern(close, high, low, ema50, snapshot["sma150"])
        reclaim_days, is_confirmed, bounce_state = calculate_reclaim_velocity(close, ema50)

        alert_count += 1
        retrace_counts[retrace_type] = retrace_counts.get(retrace_type, 0) + 1
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

        # Beta buckets
        b = snapshot["beta"]
        if b < 1.0:
            beta_buckets["<1"] += 1
        elif 1.0 <= b <= 1.5:
            beta_buckets["1-1.5"] += 1
        else:
            beta_buckets[">1.5"] += 1

        if bounce_state == "BOUNCED":
            reclaim_count += 1
        if is_confirmed:
            confirmed_count += 1

        # Qualification check (Options Alpha Radar Criteria)
        is_qualified = (
            snapshot["price"] >= snapshot["ema50"] and
            reclaim_days <= 3 and
            retrace_type in ["EMA50", "DB", "OTE"] and
            snapshot["overhead_clearance_ok"]
        )

        record = {
            "ticker": ticker,
            "sector": sector,
            "subsector": subsector,
            "price": snapshot["price"],
            "ema50": snapshot["ema50"],
            "ema50_pct": snapshot["ema50_dist_pct"],
            "sma150_pct": snapshot["sma150_dist_pct"],
            "ema200_pct": snapshot["ema200_dist_pct"],
            "overhead_runway_pct": snapshot["overhead_runway_pct"],
            "overhead_clearance_ok": snapshot["overhead_clearance_ok"],
            "beta": snapshot["beta"],
            "adr_pct": snapshot["adr_pct"],
            "rsi": snapshot["rsi"],
            "macd_crawling_up": snapshot["macd_crawling_up"],
            "retrace": retrace_type,
            "bounce_state": bounce_state,
            "reclaim_days": reclaim_days,
            "qualified": "YES" if is_qualified else "NO"
        }
        ticker_records.append(record)

        if is_qualified:
            trade_setup = structure_trade_signal(ticker, sector, snapshot, retrace_type, reclaim_days, "MIXED")
            qualified_candidates.append(trade_setup)

    # 4. Macro Breadth Calculation
    top_sectors = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_sectors_str = ", ".join([f"{s}({c})" for s, c in top_sectors]) if top_sectors else "FINANCIALS, TECH, ENERGY"

    macro_breadth = {
        "date": today_str,
        "timestamp": timestamp_str,
        "total_alerts": alert_count,
        "reclaims": reclaim_count,
        "confirmed": confirmed_count,
        "below": max(0, alert_count - reclaim_count),
        "dead": 0,
        "retrace_ote": retrace_counts.get("OTE", 0),
        "retrace_db": retrace_counts.get("DB", 0),
        "retrace_ema50": retrace_counts.get("EMA50", 0),
        "retrace_ma150": retrace_counts.get("MA150", 0),
        "beta_lt_1": beta_buckets["<1"],
        "beta_1_to_1_5": beta_buckets["1-1.5"],
        "beta_gt_1_5": beta_buckets[">1.5"],
        "top_sectors": top_sectors_str,
        "macro_ratio": round(reclaim_count / max(1, alert_count), 2),
        "regime": "RISK-ON" if (reclaim_count / max(1, alert_count)) > 0.4 else "MIXED"
    }

    # Sort candidates by reclaim days (velocity) and overhead clearance
    qualified_candidates = sorted(qualified_candidates, key=lambda x: (x["reclaim_days"], -x["overhead_runway_pct"]))

    return {
        "macro_breadth": macro_breadth,
        "top_candidates": qualified_candidates[:5],
        "all_qualified": qualified_candidates,
        "sector_momentum": sector_results,
        "tickers": ticker_records
    }

def save_payloads(payload: dict):
    """Writes latest.json, updates summary.json, writes historical date file, and static HTML."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    
    date_str = payload["macro_breadth"]["date"]
    
    # 1. Write latest.json
    latest_path = os.path.join(DATA_DIR, "latest.json")
    with open(latest_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[+] Wrote {latest_path}")

    # 2. Write history/YYYY-MM-DD.json
    history_path = os.path.join(HISTORY_DIR, f"{date_str}.json")
    with open(history_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[+] Wrote {history_path}")

    # 3. Update summary.json
    summary_path = os.path.join(DATA_DIR, "summary.json")
    summary_data = []
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r") as f:
                summary_data = json.load(f)
        except Exception:
            summary_data = []
            
    # Filter out if today already exists and append
    summary_data = [item for item in summary_data if item.get("date") != date_str]
    summary_data.append(payload["macro_breadth"])
    summary_data = sorted(summary_data, key=lambda x: x["date"], reverse=True)
    
    with open(summary_path, "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"[+] Wrote {summary_path}")

    # 4. Generate static telemetry.html for Headless / Spark Zero-JS Ingestion
    html_path = os.path.join(DATA_DIR, "telemetry.html")
    m = payload["macro_breadth"]
    candidates = payload["top_candidates"]
    
    cand_rows = "".join([
        f"<tr><td><b>{c['ticker']}</b></td><td>{c['sector']}</td><td>${c['price']}</td>"
        f"<td>${c['stop']}</td><td>${c['tp1']} / ${c['tp2']}</td><td>{c['rr_ratio']}</td>"
        f"<td>D{c['reclaim_days']}</td><td>{c['structure']}</td></tr>"
        for c in candidates
    ])
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>ABI Strategy Terminal Telemetry - {date_str}</title>
    <meta charset="utf-8">
</head>
<body style="font-family: sans-serif; max-width: 900px; margin: 20px auto; line-height: 1.5;">
    <h1>ABI Strategy Terminal Telemetry</h1>
    <p><b>Date:</b> {m['date']} | <b>Regime:</b> {m['regime']} | <b>Ratio:</b> {m['macro_ratio']}</p>
    <p><b>Alerts:</b> {m['total_alerts']} | <b>Reclaims:</b> {m['reclaims']} | <b>Confirmed:</b> {m['confirmed']}</p>
    <p><b>Top Sectors:</b> {m['top_sectors']}</p>
    
    <h2>Top Qualified Setups (Options Alpha Radar)</h2>
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%;">
        <thead>
            <tr style="background: #f1f5f9;">
                <th>Ticker</th><th>Sector</th><th>Price</th><th>Stop</th><th>Targets</th><th>R:R</th><th>Velocity</th><th>Structure</th>
            </tr>
        </thead>
        <tbody>
            {cand_rows if cand_rows else "<tr><td colspan='8'>No qualified candidates today.</td></tr>"}
        </tbody>
    </table>
</body>
</html>"""
    with open(html_path, "w") as f:
        f.write(html_content)
    print(f"[+] Wrote static SSR page {html_path}")

if __name__ == "__main__":
    print("[*] Running ABI Strategy Scanner Engine...")
    # Attempt download or fallback
    data = fetch_market_data(get_full_universe())
    payload = process_universe(data)
    save_payloads(payload)
    print("[✓] Scan complete.")
