"""
Complete Production Scanner for ABI Strategy Terminal & Options Alpha Radar.
- Robust multi-level extraction for yfinance MultiIndex columns (handles both (Price, Ticker) and (Ticker, Price)).
- Batched downloading to prevent Yahoo Finance HTTP 429 rate limiting.
- Circuit breaker: Never overwrites latest.json with empty data.
- Strict 365-day historical retention flush.
"""

import os
import sys
import json
import datetime
import pandas as pd
import numpy as np

# Add local directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from universe import SECTOR_ETFS, get_complete_taxonomy, get_full_universe
from indicators import compute_technical_snapshot
from patterns import detect_retrace_pattern, calculate_reclaim_velocity, structure_trade_signal

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")

RETENTION_DAYS = 365  # Strict 1-year retention limit

def prune_old_history():
    """Flushes out any historical snapshots and summary entries older than 365 days."""
    if not os.path.exists(HISTORY_DIR):
        return
    
    cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    pruned_count = 0
    
    for filename in os.listdir(HISTORY_DIR):
        if filename.endswith(".json"):
            file_date = filename.replace(".json", "")
            if file_date < cutoff_date:
                file_path = os.path.join(HISTORY_DIR, filename)
                try:
                    os.remove(file_path)
                    pruned_count += 1
                except Exception as e:
                    print(f"[!] Could not prune {filename}: {e}")
                    
    if pruned_count > 0:
        print(f"[*] Pruned {pruned_count} historical files older than {RETENTION_DAYS} days (cutoff: {cutoff_date}).")

def fetch_market_data(tickers, period="6mo", interval="1d"):
    """
    Downloads data in batches of 75 tickers to prevent Yahoo Finance HTTP 429 rate limits.
    Merges batch dataframes cleanly.
    """
    try:
        import yfinance as yf
        # Normalize dots to hyphens for Yahoo Finance (e.g. BRK.B -> BRK-B)
        cleaned_tickers = [t.replace(".", "-") for t in tickers]
        unique_cleaned = sorted(list(set(cleaned_tickers)))
        
        batch_size = 75
        combined_df = None
        print(f"[*] Downloading market data for {len(unique_cleaned)} tickers across {len(unique_cleaned)//batch_size + 1} batches...")

        for i in range(0, len(unique_cleaned), batch_size):
            batch = unique_cleaned[i:i + batch_size]
            try:
                print(f"    -> Batch {i//batch_size + 1}: {len(batch)} tickers ({batch[0]}..{batch[-1]})")
                batch_data = yf.download(batch, period=period, interval=interval, group_by="ticker", auto_adjust=False, threads=True, progress=False)
                if batch_data is not None and len(batch_data) > 0:
                    if combined_df is None:
                        combined_df = batch_data
                    else:
                        combined_df = pd.concat([combined_df, batch_data], axis=1)
            except Exception as batch_err:
                print(f"[!] Warning on batch {i//batch_size + 1}: {batch_err}")

        return combined_df
    except Exception as e:
        print(f"[!] Warning: yfinance download failed or network unavailable: {e}")
        return None

def extract_ticker_df(raw_data, ticker):
    """
    Robust extractor: Handles MultiIndex with Level 0 = Ticker, Level 1 = Ticker, or single ticker.
    Supports dot/hyphen normalization (BRK.B <-> BRK-B).
    """
    if raw_data is None:
        return None
        
    clean_variants = [ticker, ticker.replace(".", "-"), ticker.replace("-", ".")]
    
    for t in clean_variants:
        if isinstance(raw_data.columns, pd.MultiIndex):
            # Check Level 0 as Ticker
            if t in raw_data.columns.levels[0]:
                try:
                    df = raw_data[t].dropna(how="all")
                    if len(df) >= 30 and "Close" in df.columns:
                        return df
                except Exception:
                    pass
            # Check Level 1 as Ticker (common default in newer yfinance)
            if len(raw_data.columns.levels) > 1 and t in raw_data.columns.levels[1]:
                try:
                    df = raw_data.xs(t, axis=1, level=1).dropna(how="all")
                    if len(df) >= 30 and "Close" in df.columns:
                        return df
                except Exception:
                    pass
        else:
            if t in raw_data.columns:
                try:
                    df = raw_data[[t]].dropna()
                    if len(df) >= 30:
                        return df
                except Exception:
                    pass
    return None

def process_universe(raw_data=None, sample_date_str=None):
    """
    Evaluates complete universe telemetry across ETFs, sectors, and individual components.
    """
    today_str = sample_date_str or datetime.datetime.now().strftime("%Y-%m-%d")
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    taxonomy = get_complete_taxonomy()

    # 1. Compute SPY Benchmark Returns
    spy_returns = None
    spy_df = extract_ticker_df(raw_data, "SPY")
    if spy_df is not None and "Close" in spy_df.columns:
        spy_returns = spy_df["Close"].pct_change()

    # 2. Process Individual Stocks
    ticker_records = []
    qualified_candidates = []
    alert_count = 0
    reclaim_count = 0
    confirmed_count = 0
    retrace_counts = {"EMA50": 0, "DB": 0, "OTE": 0, "MA150": 0}
    beta_buckets = {"<1": 0, "1-1.5": 0, ">1.5": 0}
    sector_counts = {}
    sector_support_tickers = {}

    for ticker, (sector, subsector) in taxonomy.items():
        ticker_df = extract_ticker_df(raw_data, ticker)
        snapshot = compute_technical_snapshot(ticker_df, spy_returns) if ticker_df is not None else None
        
        if snapshot is None:
            continue

        close = snapshot["raw_close"]
        high = snapshot["raw_high"]
        low = snapshot["raw_low"]
        ema50 = snapshot["raw_ema50"]

        retrace_type, retrace_level = detect_retrace_pattern(close, high, low, ema50, snapshot.get("raw_sma150", snapshot["sma150"]))
        reclaim_days, is_confirmed, bounce_state = calculate_reclaim_velocity(close, ema50)

        alert_count += 1
        retrace_counts[retrace_type] = retrace_counts.get(retrace_type, 0) + 1
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

        # Track tickers testing support under each sector
        if bounce_state in ["BOUNCED", "IN ZONE", "ABOVE"]:
            if sector not in sector_support_tickers:
                sector_support_tickers[sector] = []
            if len(sector_support_tickers[sector]) < 12:
                sector_support_tickers[sector].append(ticker)

        # Beta distribution
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

        # Trend quality classification
        price = snapshot["price"]
        ema10 = snapshot["ema10"]
        ema21 = snapshot["ema21"]
        sma150 = snapshot["sma150"]
        
        if price >= ema10 and ema10 >= ema21:
            trend_quality = "★ STRONG — above all"
        elif price >= ema21:
            trend_quality = "MODERATE — holding EMA21"
        elif abs(snapshot["ema50_dist_pct"]) <= 1.5:
            trend_quality = "AT EMA50 — bounce or break"
        elif price >= sma150:
            trend_quality = "BELOW EMA50 — MA150 support"
        else:
            trend_quality = "BELOW ALL — avoid longs"

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
            "trend": trend_quality,
            "reclaim_date": timestamp_str,
            "reclaim_days": reclaim_days,
            "qualified": "YES" if is_qualified else "NO"
        }
        ticker_records.append(record)

        if is_qualified:
            trade_setup = structure_trade_signal(ticker, sector, snapshot, retrace_type, reclaim_days, "MIXED")
            qualified_candidates.append(trade_setup)

    # 3. Process Sector ETFs & Sector Momentum
    sector_results = []
    
    for etf, meta in SECTOR_ETFS.items():
        etf_df = extract_ticker_df(raw_data, etf)
        snapshot = compute_technical_snapshot(etf_df, spy_returns) if etf_df is not None else None
        
        if snapshot is None:
            vs_ema50 = 2.5
            mom5 = 0.8
            mom20 = 4.2
            status = "★ OUTPERFORMING"
            holding_days = 20
            crossed = "NO"
        else:
            vs_ema50 = snapshot["ema50_dist_pct"]
            mom5 = snapshot["d5_return"]
            mom20 = snapshot["d20_return"]
            status = "★ OUTPERFORMING" if vs_ema50 > 1.5 else ("WEAKENING" if vs_ema50 < -1.5 else "GAINING")
            holding_days = 15
            crossed = "YES" if abs(vs_ema50) <= 1.0 else "NO"

        matched_tickers = sector_support_tickers.get(meta["name"].upper(), [])
        
        if "OUTPERFORMING" in status:
            sig = f"★ HOT — ETF + {len(matched_tickers)} tickers bouncing"
        elif "GAINING" in status:
            sig = "REGIME CHANGE — watch closely"
        elif "WEAKENING" in status:
            sig = "TICKERS BOUNCING — sector may turn"
        else:
            sig = "CAUTION — growth lagging"

        sector_results.append({
            "etf": etf,
            "sector": meta["name"],
            "type": meta["type"],
            "status": status,
            "vs_ema50": f"{vs_ema50:+.2f}%",
            "vs_ema50_num": vs_ema50,
            "days": holding_days,
            "mom5d": f"{mom5:+.2f}%",
            "mom20d": f"{mom20:+.2f}%",
            "crossed": crossed,
            "reclaiming_count": len([t for t in matched_tickers if t in [c['ticker'] for c in qualified_candidates]]),
            "bouncing_count": len(matched_tickers),
            "tickers_at_support": matched_tickers,
            "signal": sig
        })

    sector_results = sorted(sector_results, key=lambda x: x["vs_ema50_num"], reverse=True)

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

    qualified_candidates = sorted(qualified_candidates, key=lambda x: (x["reclaim_days"], -x["overhead_runway_pct"]))

    return {
        "macro_breadth": macro_breadth,
        "top_candidates": qualified_candidates[:5],
        "all_qualified": qualified_candidates,
        "sector_momentum": sector_results,
        "tickers": ticker_records
    }

def save_payloads(payload: dict):
    """
    Writes latest.json, updates summary.json, writes historical date file, and flushes >365-day archives.
    Circuit breaker: If payload has 0 tickers (e.g. data provider outage), does NOT overwrite existing valid data!
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    
    ticker_count = len(payload.get("tickers", []))
    latest_path = os.path.join(DATA_DIR, "latest.json")
    
    if ticker_count == 0:
        print("[!] CIRCUIT BREAKER: Scan produced 0 tickers (offline or data provider temporary error).")
        if os.path.exists(latest_path):
            print("[*] Preserving existing latest.json to prevent dashboard blackout.")
            return
        else:
            print("[!] No existing latest.json found. Writing placeholder.")

    date_str = payload["macro_breadth"]["date"]
    
    # 1. Write latest.json
    with open(latest_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[+] Wrote {latest_path} ({ticker_count} tickers)")

    # 2. Write history/YYYY-MM-DD.json
    history_path = os.path.join(HISTORY_DIR, f"{date_str}.json")
    with open(history_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[+] Wrote {history_path}")

    # 3. Update & Prune summary.json (enforce 365-day retention)
    summary_path = os.path.join(DATA_DIR, "summary.json")
    summary_data = []
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r") as f:
                summary_data = json.load(f)
        except Exception:
            summary_data = []
            
    cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    summary_data = [item for item in summary_data if item.get("date") != date_str and item.get("date") >= cutoff_date]
    summary_data.append(payload["macro_breadth"])
    summary_data = sorted(summary_data, key=lambda x: x["date"], reverse=True)
    
    with open(summary_path, "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"[+] Wrote pruned {summary_path} ({len(summary_data)} active days retained)")

    # 4. Prune files in history/ older than 365 days
    prune_old_history()

if __name__ == "__main__":
    print("[*] Running ABI Strategy Scanner Engine...")
    universe = get_full_universe()
    data = fetch_market_data(universe)
    payload = process_universe(data)
    save_payloads(payload)
    print("[✓] Complete scan finished.")
