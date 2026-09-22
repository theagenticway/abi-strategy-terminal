#!/usr/bin/env python3
"""
ABI Strategy Terminal - Historical Recommendations Archive Logger
Stores and indexes daily recommendations across Options and Equities.
Automatically prunes entries older than 365 days on every scan.
"""

import os
import json
import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
ARCHIVE_PATH = os.path.join(DATA_DIR, "recommendations_archive.json")
RETENTION_DAYS = 365

def _safe_float(val, default=0.0):
    try:
        if val is None or val == "" or val == "N/A":
            return default
        return float(val)
    except Exception:
        return default

def _safe_int(val, default=0):
    try:
        if val is None or val == "" or val == "N/A":
            return default
        return int(val)
    except Exception:
        return default

def _normalize_ms(val, default="BULLISH_HH_HL") -> str:
    if isinstance(val, dict):
        return str(val.get("regime") or default)
    if not val:
        return default
    s = str(val)
    if s.startswith("{") and "'regime':" in s:
        try:
            import ast
            d = ast.literal_eval(s)
            if isinstance(d, dict) and "regime" in d:
                return str(d["regime"])
        except Exception:
            pass
    return s

def extract_signal_records(payload, date_str):
    """
    Extracts structured signal records from latest scanner payload.
    Maps options and stock candidates to a unified, lightweight schema.
    """
    signals = []
    
    # 1. Bull Call Spreads (Top Candidates: High-Risk Sprint or Balanced)
    for c in payload.get("top_candidates", []):
        ticker = c.get("ticker", "")
        if not ticker:
            continue
        tier = c.get("horizon_tier", "BALANCED_SWING")
        if "HIGH" in str(tier).upper() or "SPRINT" in str(tier).upper():
            category = "HIGH_RISK_SPRINT"
        else:
            category = "BALANCED_SWING"
            
        strat = c.get("structure", "Bull Call Spread")
        rec_id = f"{date_str}_{ticker}_{category}_BCS"
        
        signals.append({
            "id": rec_id,
            "date": date_str,
            "asset_type": "OPTION",
            "category": category,
            "ticker": ticker,
            "company_name": c.get("company_name", c.get("name", ticker)),
            "sector": c.get("sector", "Unknown"),
            "sub_industry": c.get("sub_industry", c.get("industry", "Unknown")),
            "entry_price": _safe_float(c.get("price", c.get("current_price", c.get("entry_price")))),
            "alpha_score": _safe_float(c.get("options_alpha_score", c.get("alpha_score", c.get("score")))),
            "technical_snapshot": {
                "ema50": _safe_float(c.get("ema50")),
                "rsi": _safe_float(c.get("rsi")),
                "macd_hist": _safe_float(c.get("macd_hist")),
                "rvol": _safe_float(c.get("rvol", 1.0)),
                "retrace_type": str(c.get("retrace") or c.get("retrace_type", "EMA50")),
                "reclaim_days": _safe_int(c.get("reclaim_days", 1)),
                "market_structure": _normalize_ms(c.get("market_structure"), "BULLISH_HH_HL"),
                "beta": _safe_float(c.get("beta", 1.0)),
                "adr_pct": _safe_float(c.get("adr_pct", 2.0)),
                "iv_rank": _safe_float(c.get("iv_rank", 50.0))
            },
            "structure": {
                "strategy": strat,
                "expiration": c.get("expiry", c.get("expiration", "N/A")),
                "dte": _safe_int(c.get("dte", 60)),
                "long_strike": _safe_float(c.get("long_strike", c.get("strike_long"))),
                "short_strike": _safe_float(c.get("short_strike", c.get("strike_short"))),
                "net_debit": _safe_float(c.get("est_debit", c.get("net_debit", c.get("mid_debit")))),
                "stop_price": _safe_float(c.get("stop", c.get("stop_loss", c.get("stop_price")))),
                "tp1": _safe_float(c.get("tp1", c.get("target_1"))),
                "tp2": _safe_float(c.get("tp2", c.get("target_2"))),
                "shares": None
            }
        })

    # 2. Strategic Call LEAPS (Core Accumulation)
    for c in payload.get("strategic_leaps", []):
        ticker = c.get("ticker", "")
        if not ticker:
            continue
        rec_id = f"{date_str}_{ticker}_CORE_ACCUMULATION_LEAPS"
        signals.append({
            "id": rec_id,
            "date": date_str,
            "asset_type": "OPTION",
            "category": "CORE_ACCUMULATION",
            "ticker": ticker,
            "company_name": c.get("company_name", c.get("name", ticker)),
            "sector": c.get("sector", "Unknown"),
            "sub_industry": c.get("sub_industry", c.get("industry", "Unknown")),
            "entry_price": _safe_float(c.get("price", c.get("current_price", c.get("entry_price")))),
            "alpha_score": _safe_float(c.get("options_alpha_score", c.get("alpha_score", c.get("score")))),
            "technical_snapshot": {
                "ema50": _safe_float(c.get("ema50")),
                "rsi": _safe_float(c.get("rsi")),
                "macd_hist": _safe_float(c.get("macd_hist")),
                "rvol": _safe_float(c.get("rvol", 1.0)),
                "retrace_type": str(c.get("retrace") or c.get("retrace_type", "Stage2_Stack")),
                "reclaim_days": _safe_int(c.get("reclaim_days", 1)),
                "market_structure": _normalize_ms(c.get("market_structure"), "BULLISH_HH_HL"),
                "beta": _safe_float(c.get("beta", 1.0)),
                "adr_pct": _safe_float(c.get("adr_pct", 2.0)),
                "iv_rank": _safe_float(c.get("iv_rank", 25.0))
            },
            "structure": {
                "strategy": "Deep-ITM Call LEAPS",
                "expiration": c.get("expiry", c.get("expiration", "N/A")),
                "dte": _safe_int(c.get("dte", 300)),
                "long_strike": _safe_float(c.get("strike", c.get("long_strike"))),
                "short_strike": None,
                "net_debit": _safe_float(c.get("est_premium", c.get("ask", c.get("mid_debit", c.get("net_debit"))))),
                "stop_price": _safe_float(c.get("macro_stop", c.get("stop", c.get("stop_loss", c.get("stop_price"))))),
                "tp1": _safe_float(c.get("tp1", c.get("target_1"))),
                "tp2": _safe_float(c.get("tp2", c.get("target_2"))),
                "shares": None
            }
        })

    # 3. Downside Hedges (Bear Put Spreads)
    for c in payload.get("downside_hedges", []):
        ticker = c.get("ticker", "")
        if not ticker:
            continue
        rec_id = f"{date_str}_{ticker}_DOWNSIDE_HEDGE_BPS"
        signals.append({
            "id": rec_id,
            "date": date_str,
            "asset_type": "OPTION",
            "category": "DOWNSIDE_HEDGE",
            "ticker": ticker,
            "company_name": c.get("company_name", c.get("name", ticker)),
            "sector": c.get("sector", "Unknown"),
            "sub_industry": c.get("sub_industry", c.get("industry", "Unknown")),
            "entry_price": _safe_float(c.get("price", c.get("current_price", c.get("entry_price")))),
            "alpha_score": _safe_float(c.get("options_alpha_score", c.get("alpha_score", c.get("score")))),
            "technical_snapshot": {
                "ema50": _safe_float(c.get("ema50")),
                "rsi": _safe_float(c.get("rsi")),
                "macd_hist": _safe_float(c.get("macd_hist")),
                "rvol": _safe_float(c.get("rvol", 1.0)),
                "retrace_type": str(c.get("retrace") or c.get("retrace_type", "Resistance_Rejection")),
                "reclaim_days": _safe_int(c.get("reclaim_days", 0)),
                "market_structure": _normalize_ms(c.get("market_structure"), "BEARISH_LH_LL"),
                "beta": _safe_float(c.get("beta", 1.0)),
                "adr_pct": _safe_float(c.get("adr_pct", 2.0)),
                "iv_rank": _safe_float(c.get("iv_rank", 60.0))
            },
            "structure": {
                "strategy": "Bear Put Spread",
                "expiration": c.get("expiry", c.get("expiration", "N/A")),
                "dte": _safe_int(c.get("dte", 45)),
                "long_strike": _safe_float(c.get("long_strike", c.get("strike_long"))),
                "short_strike": _safe_float(c.get("short_strike", c.get("strike_short"))),
                "net_debit": _safe_float(c.get("est_debit", c.get("net_debit", c.get("mid_debit")))),
                "stop_price": _safe_float(c.get("stop", c.get("stop_loss", c.get("stop_price")))),
                "tp1": _safe_float(c.get("tp1", c.get("target_1"))),
                "tp2": _safe_float(c.get("tp2", c.get("target_2"))),
                "shares": None
            }
        })

    # 4. Stock Recommendations (Tactical Swings & Core Equities)
    core_list = payload.get("core_stocks", [])
    all_stocks = payload.get("stock_recommendations", []) + core_list
    seen_stock_ids = set()
    for s in all_stocks:
        ticker = s.get("ticker", "")
        if not ticker:
            continue
        tier = s.get("horizon_tier") or s.get("strategy_prong") or ("CORE" if s in core_list else "BALANCED_SWING")
        if "HIGH" in str(tier).upper() or "SPRINT" in str(tier).upper():
            category = "HIGH_RISK_SPRINT"
        elif "CORE" in str(tier).upper():
            category = "CORE_ACCUMULATION"
        else:
            category = "BALANCED_SWING"
            
        rec_id = f"{date_str}_{ticker}_{category}_EQUITY"
        if rec_id in seen_stock_ids:
            continue
        seen_stock_ids.add(rec_id)
        
        signals.append({
            "id": rec_id,
            "date": date_str,
            "asset_type": "EQUITY",
            "category": category,
            "ticker": ticker,
            "company_name": s.get("company_name", s.get("name", ticker)),
            "sector": s.get("sector", "Unknown"),
            "sub_industry": s.get("sub_industry", s.get("industry", "Unknown")),
            "entry_price": _safe_float(s.get("price", s.get("entry_price", s.get("current_price")))),
            "alpha_score": _safe_float(s.get("alpha_composite_score") or s.get("alpha_score") or s.get("score") or (80.0 if category == "CORE_ACCUMULATION" else 0.0)),
            "technical_snapshot": {
                "ema50": _safe_float(s.get("ema50")),
                "rsi": _safe_float(s.get("rsi")),
                "macd_hist": _safe_float(s.get("macd_hist")),
                "rvol": _safe_float(s.get("rvol", 1.0)),
                "retrace_type": str(s.get("retrace") or s.get("retrace_type", "EMA50")),
                "reclaim_days": _safe_int(s.get("reclaim_days", 1)),
                "market_structure": _normalize_ms(s.get("market_structure"), "BULLISH_HH_HL"),
                "beta": _safe_float(s.get("beta", 1.0)),
                "adr_pct": _safe_float(s.get("adr_pct", 2.0)),
                "iv_rank": _safe_float(s.get("iv_rank", 40.0))
            },
            "structure": {
                "strategy": "Common Shares",
                "expiration": "N/A",
                "dte": 0,
                "long_strike": None,
                "short_strike": None,
                "net_debit": None,
                "stop_price": _safe_float(s.get("stop", s.get("macro_stop", s.get("stop_loss", s.get("stop_price"))))),
                "tp1": _safe_float(s.get("tp1", s.get("take_profit_1"))),
                "tp2": _safe_float(s.get("tp2", s.get("take_profit_2"))),
                "shares": _safe_int(s.get("shares_recommended", s.get("shares", 0)))
            }
        })

    # 5. Dedicated Daily High-Risk Radar: Options
    for c in payload.get("high_risk_options_radar", []):
        ticker = c.get("ticker", "")
        if not ticker:
            continue
        rec_id = f"{date_str}_{ticker}_HIGH_RISK_RADAR_OPTION"
        signals.append({
            "id": rec_id,
            "date": date_str,
            "asset_type": "OPTION",
            "category": "HIGH_RISK_SPRINT",
            "is_radar": True,
            "execution_intent": "RADAR_SURVEILLANCE",
            "ticker": ticker,
            "company_name": c.get("company_name", c.get("name", ticker)),
            "sector": c.get("sector", "Unknown"),
            "sub_industry": c.get("sub_industry", c.get("industry", "Unknown")),
            "entry_price": _safe_float(c.get("price", c.get("entry_price"))),
            "alpha_score": _safe_float(c.get("options_alpha_score", c.get("alpha_score", 60.0))),
            "technical_snapshot": {
                "ema50": _safe_float(c.get("ema50")),
                "rsi": _safe_float(c.get("rsi", 50.0)),
                "macd_hist": _safe_float(c.get("macd_hist")),
                "rvol": _safe_float(c.get("rvol", 1.2)),
                "retrace_type": str(c.get("retrace") or c.get("retrace_type", "EMA50")),
                "reclaim_days": _safe_int(c.get("reclaim_days", 1)),
                "market_structure": _normalize_ms(c.get("market_structure"), "BULLISH_HH_HL"),
                "beta": _safe_float(c.get("beta", 1.5)),
                "adr_pct": _safe_float(c.get("adr_pct", 3.0)),
                "iv_rank": _safe_float(c.get("iv_rank", 50.0))
            },
            "structure": {
                "strategy": c.get("structure", "High-Risk Bull Call Spread"),
                "contract": c.get("contract"),
                "expiration": c.get("expiry", "N/A"),
                "dte": _safe_int(c.get("dte", 45)),
                "long_strike": _safe_float(c.get("long_strike")),
                "short_strike": _safe_float(c.get("short_strike")),
                "net_debit": _safe_float(c.get("est_debit")),
                "stop_price": _safe_float(c.get("stop", c.get("stop_price"))),
                "tp1": _safe_float(c.get("tp1")),
                "tp2": _safe_float(c.get("tp2")),
                "shares": None
            }
        })

    # 6. Dedicated Daily High-Risk Radar: Stocks
    for s in payload.get("high_risk_stocks_radar", []):
        ticker = s.get("ticker", "")
        if not ticker:
            continue
        rec_id = f"{date_str}_{ticker}_HIGH_RISK_RADAR_STOCK"
        signals.append({
            "id": rec_id,
            "date": date_str,
            "asset_type": "EQUITY",
            "category": "HIGH_RISK_SPRINT",
            "is_radar": True,
            "execution_intent": "RADAR_SURVEILLANCE",
            "ticker": ticker,
            "company_name": s.get("company_name", s.get("name", ticker)),
            "sector": s.get("sector", "Unknown"),
            "sub_industry": s.get("sub_industry", s.get("industry", "Unknown")),
            "entry_price": _safe_float(s.get("price", s.get("entry_price"))),
            "alpha_score": _safe_float(s.get("alpha_score", 60.0)),
            "technical_snapshot": {
                "ema50": _safe_float(s.get("ema50")),
                "rsi": _safe_float(s.get("rsi", 50.0)),
                "macd_hist": _safe_float(s.get("macd_hist")),
                "rvol": _safe_float(s.get("rvol", 1.2)),
                "retrace_type": str(s.get("retrace") or s.get("retrace_type", "EMA50")),
                "reclaim_days": _safe_int(s.get("reclaim_days", 1)),
                "market_structure": _normalize_ms(s.get("market_structure"), "BULLISH_HH_HL"),
                "beta": _safe_float(s.get("beta", 1.5)),
                "adr_pct": _safe_float(s.get("adr_pct", 3.0)),
                "iv_rank": _safe_float(s.get("iv_rank", 50.0))
            },
            "structure": {
                "strategy": s.get("structure", "High-Risk Sprint (Common Shares)"),
                "expiration": "N/A",
                "dte": 0,
                "long_strike": None,
                "short_strike": None,
                "net_debit": None,
                "stop_price": _safe_float(s.get("stop", s.get("stop_price"))),
                "tp0_5": _safe_float(s.get("tp0_5")),
                "tp1": _safe_float(s.get("tp1")),
                "tp2": _safe_float(s.get("tp2")),
                "shares": _safe_int(s.get("shares", 50))
            }
        })

    return signals

def update_recommendations_archive(payload, date_str, archive_path=ARCHIVE_PATH, retention_days=RETENTION_DAYS):
    """
    Appends or updates today's signals in recommendations_archive.json and prunes records older than retention_days.
    Safe for repeated intraday cron runs (upserts on unique ID).
    """
    try:
        new_signals = extract_signal_records(payload, date_str)
        if not new_signals:
            return 0, 0

        # Load existing archive
        existing_records = []
        if os.path.exists(archive_path):
            try:
                with open(archive_path, "r") as f:
                    existing_records = json.load(f)
                    if not isinstance(existing_records, list):
                        existing_records = []
            except Exception as read_err:
                print(f"[!] Warning reading existing archive: {read_err}. Starting fresh.")
                existing_records = []

        # Index existing records by ID for upsert
        record_map = {r.get("id"): r for r in existing_records if "id" in r}

        # Upsert today's signals
        upserted_count = 0
        for sig in new_signals:
            record_map[sig["id"]] = sig
            upserted_count += 1

        # Calculate cutoff date for 365-day rolling window
        try:
            curr_dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            curr_dt = datetime.datetime.now()
        
        cutoff_dt = curr_dt - datetime.timedelta(days=retention_days)
        cutoff_str = cutoff_dt.strftime("%Y-%m-%d")

        # Filter out entries older than retention_days
        pruned_records = [
            r for r in record_map.values()
            if r.get("date", "") >= cutoff_str
        ]

        # Sort descending by date, then alpha score
        pruned_records.sort(
            key=lambda x: (x.get("date", ""), x.get("alpha_score", 0.0)),
            reverse=True
        )

        # Write updated archive atomically
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
        tmp_path = archive_path + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(pruned_records, f, indent=2)
        os.replace(tmp_path, archive_path)

        print(f"[+] recommendations_archive.json updated: {upserted_count} signals logged for {date_str} ({len(pruned_records)} total across {retention_days}d rolling window, pruned < {cutoff_str})")
        return upserted_count, len(pruned_records)
    except Exception as e:
        print(f"[!] Error updating recommendations archive: {e}")
        return 0, 0

if __name__ == "__main__":
    latest_file = os.path.join(DATA_DIR, "latest.json")
    if os.path.exists(latest_file):
        with open(latest_file, "r") as f:
            p = json.load(f)
        d_str = p.get("date", datetime.date.today().strftime("%Y-%m-%d"))
        update_recommendations_archive(p, d_str)
    else:
        print(f"[!] {latest_file} not found.")
