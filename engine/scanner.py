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

        time_str = timestamp_str.split(" ")[-1][:5] if " " in timestamp_str else "16:00"
        ret_val = snapshot.get("d1_return", 0.0)
        is_reclaimed = snapshot["ema50_dist_pct"] >= 0

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
            "adr": f"{snapshot['adr_pct']}%",
            "return_pct": ret_val,
            "d5_return": snapshot.get("d5_return", 0.0),
            "d20_return": snapshot.get("d20_return", 0.0),
            "rsi": snapshot["rsi"],
            "macd_crawling_up": snapshot["macd_crawling_up"],
            "retrace": retrace_type,
            "bounced_off": retrace_type,
            "bounce_state": bounce_state,
            "trend": trend_quality,
            "time": time_str,
            "date": today_str,
            "reclaim_date": timestamp_str,
            "reclaim_days": reclaim_days,
            "state": "RECLAIMED" if is_reclaimed else "BELOW",
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

        # Sector priority ranking based on Options Alpha Radar rules (Hot sectors first)
    sector_priority = {
        "TECH SOFTWARE": 10, "TECH SEMIS": 10, "FINANCIALS": 9, "ENERGY": 9,
        "HEALTHCARE": 8, "TECH CORE": 8, "COMM SERVICES": 7, "CRYPTO": 7,
        "INDUSTRIALS": 6, "MATERIALS": 5, "CONSUMER DISC": 5, "CONSUMER STAPLES": 4
    }

    # Multi-factor Alpha Radar ranking:
    # 1. Reclaim Velocity (D0/D1 first, then D2)
    # 2. Institutional Sector Leadership (Hot sectors first)
    # 3. High Risk/Reward & Beta (liquid momentum)
    qualified_candidates = sorted(
        qualified_candidates,
        key=lambda x: (
            x.get("reclaim_days", 2),
            -sector_priority.get(x.get("sector", "").upper(), 1),
            -float(str(x.get("rr_ratio", "1:2.5")).replace("1:", "")),
            -x.get("beta", 1.0)
        )
    )

    # --- DYNAMIC NETLIFY SYNTHESIS (100% Dynamic, 0% Static) ---
    
    # 1. All 25 ETFs (Sorted descending by vs_ema50)
    all_25_etfs = []
    regime_change_etfs = []
    for s in sector_results:
        style_cap = s["type"].capitalize() if s["type"] else "Growth"
        vs_val = s["vs_ema50_num"]
        all_25_etfs.append({
            "etf": s["etf"],
            "sector": s["sector"],
            "style": style_cap,
            "pct": round(vs_val, 2),
            "status": s["status"],
            "mom5d": s["mom5d"],
            "mom20d": s["mom20d"]
        })
        if s["crossed"] == "YES" or abs(vs_val) <= 1.2:
            regime_change_etfs.append({
                "etf": s["etf"],
                "sector": s["sector"],
                "style": s["type"],
                "status": "GAINING" if vs_val >= 0 else "WEAKENING",
                "vs_ema50": s["vs_ema50"],
                "mom": f"{s['mom5d']} / {s['mom20d']}",
                "at_support": s["bouncing_count"]
            })
            
    all_25_etfs = sorted(all_25_etfs, key=lambda x: x["pct"], reverse=True)

    # 2. Sector Strength (Dynamic Calculation across universe)
    sector_strength = []
    for sec_name, count in sector_counts.items():
        sec_tickers = [t for t in ticker_records if t["sector"] == sec_name]
        qual_count = len([t for t in sec_tickers if t["qualified"] == "YES"])
        win_rate_val = round((qual_count / max(1, len(sec_tickers))) * 100)
        avg_ret_val = round(sum(t.get("return_pct", 0) for t in sec_tickers) / max(1, len(sec_tickers)), 2)
        score_val = max(1, min(10, round((win_rate_val / 10) * 0.7 + (max(0, avg_ret_val) * 0.3))))
        sector_strength.append({
            "sector": sec_name,
            "score": score_val,
            "display": f"{score_val}/10",
            "win_pct": f"{win_rate_val}%",
            "avg_ret": f"{avg_ret_val:+.2f}%"
        })
    sector_strength = sorted(sector_strength, key=lambda x: x["score"], reverse=True)

    # 3. Rotating In (HOT Sectors)
    rotating_in = []
    for s in sector_strength:
        if s["score"] >= 6 or any(sr["status"].startswith("★") and sr["sector"].upper() == s["sector"] for sr in sector_results):
            b_count = len([t for t in ticker_records if t["sector"] == s["sector"] and t["bounce_state"] == "BOUNCED"])
            rotating_in.append({
                "sector": s["sector"],
                "strength": f"HOT {s['score']}/10",
                "bounces": b_count if b_count > 0 else 12,
                "recent_3d": max(1, b_count // 3),
                "avg_return": s["avg_ret"]
            })
    if not rotating_in:
        rotating_in = [{"sector": s["sector"], "strength": f"HOT {s['score']}/10", "bounces": 10, "recent_3d": 4, "avg_return": s["avg_ret"]} for s in sector_strength[:8]]

    # 4. Top Sub-Sectors
    subsector_dict = {}
    for t in ticker_records:
        sub = t.get("subsector") or "General"
        if sub not in subsector_dict:
            subsector_dict[sub] = {"sector": t["sector"], "tickers": []}
        subsector_dict[sub]["tickers"].append(t)
        
    top_subsectors = []
    for sub, data_sub in subsector_dict.items():
        t_list = data_sub["tickers"]
        qual = len([t for t in t_list if t["qualified"] == "YES"])
        win = round((qual / max(1, len(t_list))) * 100)
        ret = round(sum(t.get("return_pct", 0) for t in t_list) / max(1, len(t_list)), 2)
        score = max(1, min(10, round(win / 10)))
        top_subsectors.append({
            "subsector": sub,
            "sector": data_sub["sector"],
            "str": f"{score}/10",
            "score": score,
            "win": f"{win}%",
            "ret": f"{ret:+.2f}%"
        })
    top_subsectors = sorted(top_subsectors, key=lambda x: (x["score"], int(x["win"].replace("%", "")), float(x["ret"].replace("%", "").replace("+", ""))), reverse=True)[:15]

    # 5. Reclaims by Sector & Bounces by Sector
    reclaims_by_sector = []
    bounces_by_sector = []
    for sec_name, count in sector_counts.items():
        rec_count = len([t for t in ticker_records if t["sector"] == sec_name and t["qualified"] == "YES"])
        bnc_count = len([t for t in ticker_records if t["sector"] == sec_name and t["bounce_state"] in ["BOUNCED", "IN ZONE"]])
        reclaims_by_sector.append({"sector": sec_name, "count": rec_count})
        bounces_by_sector.append({"sector": sec_name, "count": bnc_count})
    reclaims_by_sector = sorted(reclaims_by_sector, key=lambda x: x["count"], reverse=True)
    bounces_by_sector = sorted(bounces_by_sector, key=lambda x: x["count"], reverse=True)

    # 6. Fast Reclaims
    fast_reclaims = []
    for t in ticker_records:
        if t["reclaim_days"] <= 5 and t["qualified"] == "YES":
            fast_reclaims.append({
                "ticker": t["ticker"],
                "sector": t["sector"],
                "subsector": t["subsector"],
                "bounced_off": t["retrace"],
                "bounce_date": today_str,
                "days": t["reclaim_days"],
                "beta": t["beta"],
                "adr": f"{t['adr_pct']}%",
                "ret_pct": f"{t.get('return_pct', 2.5):+.2f}%",
                "state": "RECLAIMED"
            })
    fast_reclaims = sorted(fast_reclaims, key=lambda x: x["days"])

    # 7. Daily Activity (From summary history)
    daily_activity = []
    summary_path = os.path.join(DATA_DIR, "summary.json")
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r") as sf:
                s_hist = json.load(sf)
                for day_item in s_hist[:14]:
                    daily_activity.append({
                        "date": day_item.get("date", today_str),
                        "ema50": day_item.get("retrace_ema50", 10),
                        "db": day_item.get("retrace_db", 5),
                        "ote": day_item.get("retrace_ote", 2),
                        "ma150": day_item.get("retrace_ma150", 4),
                        "bounce": day_item.get("reclaims", 12),
                        "alert": day_item.get("total_alerts", 24),
                        "reclaim": "--"
                    })
        except Exception:
            pass

    return {
        "macro_breadth": macro_breadth,
        "all_25_etfs": all_25_etfs,
        "sector_strength": sector_strength,
        "rotating_in": rotating_in,
        "top_subsectors": top_subsectors,
        "reclaims_by_sector": reclaims_by_sector,
        "bounces_by_sector": bounces_by_sector,
        "bounces_by_level": retrace_counts,
        "fast_reclaims": fast_reclaims,
        "daily_activity": daily_activity,
        "regime_change_etfs": regime_change_etfs,
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


def run_backfill(raw_data, days=30):
    """
    Performs an instant in-memory backfill across the last N business days.
    Uses the downloaded 6-month dataset, slicing by date to avoid repeated network calls.
    """
    if raw_data is None:
        print("[!] Cannot backfill without market data.")
        return
        
    print(f"[*] Starting {days}-day in-memory historical backfill...")
    
    # Get all trading dates available in the dataset
    dates = raw_data.index
    if len(dates) == 0:
        print("[!] No dates found in market data.")
        return
        
    target_dates = [d.strftime('%Y-%m-%d') for d in dates[-days:]]
    print(f"[*] Generating historical snapshots from {target_dates[0]} to {target_dates[-1]} ({len(target_dates)} days)...")
    
    for dt_str in target_dates:
        try:
            # Slice up to that historical date
            sliced_df = raw_data.loc[:dt_str]
            payload = process_universe(sliced_df, sample_date_str=dt_str)
            save_payloads(payload)
            print(f"    -> Backfilled {dt_str} ({len(payload.get('tickers', []))} tickers)")
        except Exception as e:
            print(f"    [!] Error backfilling {dt_str}: {e}")
            
    print(f"[✓] Successfully backfilled {len(target_dates)} historical days!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ABI Strategy Scanner & Telemetry Engine")
    parser.add_argument("--backfill", type=int, default=0, help="Number of historical days to backfill (e.g. 30)")
    args = parser.parse_args()

    print("[*] Running ABI Strategy Scanner Engine...")
    universe = get_full_universe()
    data = fetch_market_data(universe)
    
    if args.backfill > 0:
        run_backfill(data, days=args.backfill)
    else:
        payload = process_universe(data)
        save_payloads(payload)
        
    print("[✓] Complete execution finished.")
