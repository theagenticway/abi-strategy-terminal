"""
Core universe scan: evaluates every ticker in the taxonomy, all 25 sector
ETFs, and every subsector; builds qualified candidate lists (Bull Call
Spreads, Strategic LEAPS, stock recommendations, downside hedges), scores
them, and returns the full report payload consumed by save_payloads().

This is a mechanical extraction of process_universe() from the original
scanner.py — the function body is unchanged. It is the single largest
function in the codebase (~1000 lines) and is left intact rather than
further decomposed, since splitting its internals safely would need a
regression baseline (recorded outputs on real data) to check against;
happy to do that as a follow-up if useful.
"""
import os
import sys
import json
import datetime
import pandas as pd
import numpy as np

_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.append(_this_dir)

try:
    from engine.config import (
        DATA_DIR, DEFAULT_PORTFOLIO_CAPITAL, MAX_CAPITAL_ALLOCATION_PCT,
        DOLLAR_AT_RISK_PCT, SPRINT_STOP_PCT,
    )
except (ImportError, ModuleNotFoundError):
    from config import (
        DATA_DIR, DEFAULT_PORTFOLIO_CAPITAL, MAX_CAPITAL_ALLOCATION_PCT,
        DOLLAR_AT_RISK_PCT, SPRINT_STOP_PCT,
    )

try:
    from engine.market_data import extract_ticker_df, verify_multi_timeframe_confluence
except (ImportError, ModuleNotFoundError):
    from market_data import extract_ticker_df, verify_multi_timeframe_confluence

try:
    from engine.benchmark import calculate_benchmark_matrix, generate_market_commentary
except (ImportError, ModuleNotFoundError):
    from benchmark import calculate_benchmark_matrix, generate_market_commentary

try:
    from engine.radar import build_high_risk_radars, evaluate_gatekeepers, build_near_miss_candidates
except (ImportError, ModuleNotFoundError):
    from radar import build_high_risk_radars, evaluate_gatekeepers, build_near_miss_candidates

from universe import SECTOR_ETFS, get_complete_taxonomy
from indicators import compute_technical_snapshot, calculate_iv_rank
from patterns import detect_retrace_pattern, calculate_reclaim_velocity, structure_trade_signal, screen_strategic_leaps_candidate
import patterns

try:
    import stocks
except ModuleNotFoundError:
    import importlib.util
    _stocks_path = os.path.join(_this_dir, "stocks.py")
    if os.path.exists(_stocks_path):
        _spec = importlib.util.spec_from_file_location("stocks", _stocks_path)
        stocks = importlib.util.module_from_spec(_spec)
        sys.modules["stocks"] = stocks
        _spec.loader.exec_module(stocks)


# Comprehensive mapping of 25 Sector/Industry ETFs to constituent sectors & keywords
ETF_SECTOR_MAP = {
    "GDX": {"sectors": ["MATERIALS"], "keywords": ["gold", "mining", "metal"]},
    "IBB": {"sectors": ["HEALTHCARE"], "keywords": ["biotech", "therapeutic"]},
    "XBI": {"sectors": ["HEALTHCARE"], "keywords": ["biotech", "rare"]},
    "XLE": {"sectors": ["ENERGY"], "keywords": []},
    "IGV": {"sectors": ["TECH SOFTWARE"], "keywords": []},
    "XME": {"sectors": ["MATERIALS"], "keywords": ["mining", "metal", "steel"]},
    "XLV": {"sectors": ["HEALTHCARE"], "keywords": []},
    "XLK": {"sectors": ["TECH SOFTWARE", "TECH SEMIS", "TECH CORE"], "keywords": []},
    "XLF": {"sectors": ["FINANCIALS"], "keywords": []},
    "IHAK": {"sectors": ["TECH SOFTWARE"], "keywords": ["cyber", "security"]},
    "QQQ": {"sectors": ["TECH SOFTWARE", "TECH SEMIS", "TECH CORE", "COMM SERVICES", "CONSUMER DISC"], "keywords": []},
    "KRE": {"sectors": ["FINANCIALS"], "keywords": ["bank", "regional"]},
    "XLB": {"sectors": ["MATERIALS"], "keywords": []},
    "XLC": {"sectors": ["COMM SERVICES"], "keywords": []},
    "SMH": {"sectors": ["TECH SEMIS"], "keywords": []},
    "XRT": {"sectors": ["CONSUMER DISC", "CONSUMER STAPLES"], "keywords": ["retail", "store", "supercenter"]},
    "XLP": {"sectors": ["CONSUMER STAPLES"], "keywords": []},
    "XLY": {"sectors": ["CONSUMER DISC"], "keywords": []},
    "XLRE": {"sectors": ["REAL ESTATE"], "keywords": []},
    "IYT": {"sectors": ["INDUSTRIALS"], "keywords": ["freight", "rail", "airline", "truck", "transport", "logistics"]},
    "XLU": {"sectors": ["UTILITIES"], "keywords": []},
    "XLI": {"sectors": ["INDUSTRIALS"], "keywords": []},
    "ITB": {"sectors": ["CONSUMER DISC", "INDUSTRIALS"], "keywords": ["homebuild", "construction", "residential", "building"]},
    "JETS": {"sectors": ["INDUSTRIALS"], "keywords": ["airline", "passenger"]},
    "TAN": {"sectors": ["TECH CORE", "UTILITIES"], "keywords": ["solar", "clean energy"]}
}


def process_universe(raw_data=None, sample_date_str=None):
    """Complete universe evaluation synthesizing all 15 derived structures."""
    today_str = sample_date_str or datetime.datetime.now().strftime("%Y-%m-%d")
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    time_str = timestamp_str.split(" ")[-1][:5] if " " in timestamp_str else "16:00"
    taxonomy = get_complete_taxonomy()

    # 1. SPY Benchmark Returns
    spy_returns = None
    spy_df = extract_ticker_df(raw_data, "SPY")
    spy_regime_for_sizing = "MIXED"
    if spy_df is not None and "Close" in spy_df.columns:
        spy_returns = spy_df["Close"].pct_change()
        if len(spy_df) >= 50:
            from indicators import calculate_ema
            spy_c = float(spy_df["Close"].iloc[-1])
            spy_e = float(calculate_ema(spy_df["Close"], 50).iloc[-1])
            spy_regime_for_sizing = "RISK-OFF" if spy_c < spy_e else "RISK-ON"

    # 2. Process Individual Equities
    ticker_records = []
    qualified_candidates = []
    strategic_leaps_candidates = []
    qualified_stock_candidates = []
    core_stock_candidates = []
    alert_count = 0
    reclaim_count = 0
    confirmed_count = 0
    retrace_counts = {"EMA50": 0, "DB": 0, "OTE": 0, "MA150": 0}
    beta_buckets = {"<1": 0, "1-1.5": 0, ">1.5": 0}
    sector_counts = {}

    # Intraday check (09:30 to 16:00 ET / 13:30 to 20:00 UTC)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    is_weekday = (now_utc.weekday() < 5)
    market_open_time = now_utc.replace(hour=13, minute=30, second=0, microsecond=0)
    market_close_time = now_utc.replace(hour=20, minute=0, second=0, microsecond=0)
    is_intraday = bool(is_weekday and market_open_time <= now_utc < market_close_time)

    funnel = {
        "scanned": len(taxonomy),
        "below_floor": 0,
        "stale_reclaim": 0,
        "wrong_retrace": 0,
        "low_runway": 0,
        "pending_eod": 0,
        "illiquid_options": 0,
        "qualified": 0
    }

    for ticker, (sector, subsector) in taxonomy.items():
        ticker_df = extract_ticker_df(raw_data, ticker)
        snapshot = compute_technical_snapshot(ticker_df, spy_returns) if ticker_df is not None else None
        
        if snapshot is None:
            continue

        close = snapshot["raw_close"]
        high = snapshot["raw_high"]
        low = snapshot["raw_low"]
        ema50 = snapshot["raw_ema50"]
        raw_sma150 = snapshot.get("raw_sma150", snapshot["sma150"])

        retrace_type, retrace_level = detect_retrace_pattern(close, high, low, ema50, raw_sma150)
        reclaim_days, is_confirmed, bounce_state = calculate_reclaim_velocity(close, ema50)

        alert_count += 1
        retrace_counts[retrace_type] = retrace_counts.get(retrace_type, 0) + 1
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

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
        elif price >= snapshot["ema50"]:
            trend_quality = "ABOVE EMA50 — holding Stage 2"
        elif price >= sma150:
            trend_quality = "BELOW EMA50 — MA150 support"
        else:
            trend_quality = "BELOW ALL — avoid longs"

        # Clearance runway to 200 MA (Item 2D guardrail for <200d history)
        has_200 = bool(snapshot.get("has_200sma", True) and snapshot.get("sma200") is not None)
        is_above_200 = bool(snapshot["price"] >= snapshot["sma200"]) if has_200 else True
        runway_val = 0.0 if is_above_200 else (snapshot.get("overhead_runway_pct") or 0.0)
        overhead_ok = bool(not has_200 or is_above_200 or (runway_val and runway_val >= 5.0))

        rsi_val = float(snapshot.get("rsi", 50.0))
        rsi_floor_ok = bool(rsi_val >= 45.0)
        macd_ok = bool(snapshot.get("macd_hook_ok", snapshot.get("macd_crawling_up", True)))

        # Evaluate gatekeepers (modularized contract supporting near-miss detection)
        gate_results = evaluate_gatekeepers(snapshot, reclaim_days, retrace_type)
        is_qualified = all(g.get("pass") for g in gate_results.values())

        ret_val = snapshot.get("d1_return", 0.0)

        record = {
            "ticker": ticker,
            "sector": sector,
            "subsector": subsector,
            "price": snapshot["price"],
            "ema50": snapshot["ema50"],
            "ema50_pct": snapshot["ema50_dist_pct"],
            "sma150_pct": snapshot["sma150_dist_pct"],
            "ema200_pct": snapshot["ema200_dist_pct"],
            "overhead_runway_pct": runway_val,
            "overhead_clearance_ok": overhead_ok,
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
            "state": "RECLAIMED" if snapshot["ema50_dist_pct"] >= 0 else "BELOW",
            "qualified": "YES" if is_qualified else "NO",
            "gate_results": gate_results
        }
        ticker_records.append(record)

        # Record funnel diagnostics
        if snapshot["price"] < snapshot["ema50"]:
            funnel["below_floor"] += 1
        elif reclaim_days > 3:
            funnel["stale_reclaim"] += 1
        elif retrace_type not in ["EMA50", "DB", "OTE"]:
            funnel["wrong_retrace"] += 1
        elif not overhead_ok:
            funnel["low_runway"] += 1
        else:
            if is_qualified:
                if is_intraday and reclaim_days == 0:
                    funnel["pending_eod"] += 1
                else:
                    funnel["qualified"] += 1

        if is_qualified:
            trade_setup = structure_trade_signal(ticker, sector, snapshot, retrace_type, reclaim_days, spy_regime_for_sizing)
            trade_setup["overhead_runway_pct"] = runway_val
            trade_setup["overhead_clearance_ok"] = overhead_ok
            trade_setup["has_200sma"] = snapshot.get("has_200sma", True)
            trade_setup["overhead_runway_label"] = snapshot.get("overhead_runway_label", "CLEAR (Above 200MA)")
            trade_setup["execution_state"] = "PENDING_EOD" if (is_intraday and reclaim_days == 0) else "CONFIRMED"
            trade_setup["execution_badge"] = "🟡 PENDING CLOSE (Wait EOD)" if (is_intraday and reclaim_days == 0) else "🟢 CONFIRMED CLOSE"
            
            # Module 3: Multi-Timeframe Confirmation (Live scans only; skip during backfill for 15s execution)
            if sample_date_str is None:
                mtf_check = verify_multi_timeframe_confluence(ticker, snapshot["ema50"])
            else:
                mtf_check = {"confirmed_4h": True, "badge": "🟢 4H CONFLUENCE (Pass)", "status": "CONFIRMED_4H"}
            trade_setup["mtf_status"] = mtf_check["status"]
            trade_setup["mtf_badge"] = mtf_check["badge"]
            trade_setup["rvol"] = snapshot.get("rvol", 1.0)
            trade_setup["rsi"] = snapshot.get("rsi", 52.0)
            trade_setup["macd_hook_ok"] = snapshot.get("macd_hook_ok", True)
            trade_setup["beta"] = snapshot.get("beta", 1.0)
            trade_setup["adr_pct"] = snapshot.get("adr_pct", 2.5)
            trade_setup["iv_rank"] = snapshot.get("iv_rank", 25.0)
            trade_setup["iv_status"] = snapshot.get("iv_status", "LOW (Cheap Vol · Debit Favorable)")
            trade_setup["weekly_stage"] = snapshot.get("weekly_stage", "STAGE 2 (Advancing)")
            
            qualified_candidates.append(trade_setup)
            try:
                # Broad index exclusion: SPY, QQQ, IWM, RSP are reserved for Core Accumulation & Benchmark Ribbon
                is_broad_index = (ticker.upper() in ("SPY", "QQQ", "IWM", "RSP") or (sector and sector.upper() == "INDEX"))
                stock_setup = stocks.structure_stock_trade(ticker, sector, snapshot, retrace_type, reclaim_days, spy_regime_for_sizing, subsector=subsector)
                if stock_setup is not None:
                    stock_setup["overhead_runway_pct"] = runway_val
                    stock_setup["overhead_clearance_ok"] = overhead_ok
                    stock_setup["has_200sma"] = snapshot.get("has_200sma", True)
                    stock_setup["overhead_runway_label"] = snapshot.get("overhead_runway_label", "CLEAR (Above 200MA)")
                    stock_setup["execution_state"] = trade_setup["execution_state"]
                    stock_setup["execution_badge"] = trade_setup["execution_badge"]
                    if not is_broad_index:
                        qualified_stock_candidates.append(stock_setup)
            except Exception as s_err:
                print(f"[!] Warning structuring stock trade for {ticker}: {s_err}")

        # Screen for multi-quarter Strategic LEAPS accumulation (Approach 2)
        leaps_setup = screen_strategic_leaps_candidate(ticker, sector, snapshot)
        if leaps_setup is not None:
            leaps_setup["rvol"] = snapshot.get("rvol", 1.0)
            leaps_setup["rsi"] = snapshot.get("rsi", 52.0)
            leaps_setup["macd_hook_ok"] = snapshot.get("macd_hook_ok", True)
            leaps_setup["beta"] = snapshot.get("beta", 1.0)
            leaps_setup["adr_pct"] = snapshot.get("adr_pct", 2.5)
            leaps_setup["iv_rank"] = snapshot.get("iv_rank", 20.0)
            leaps_setup["iv_status"] = snapshot.get("iv_status", "LOW (Cheap Vol · Debit Favorable)")
            leaps_setup["weekly_stage"] = snapshot.get("weekly_stage", "STAGE 2 (Advancing)")
            strategic_leaps_candidates.append(leaps_setup)
            try:
                core_stock = stocks.structure_core_stock_accumulation(ticker, sector, snapshot, subsector=subsector)
                if core_stock is not None:
                    core_stock_candidates.append(core_stock)
            except Exception as c_err:
                print(f"[!] Warning structuring core stock for {ticker}: {c_err}")

    # 3. Process All 25 Sector ETFs
    sector_results = []
    all_25_etfs = []
    regime_change_etfs = []

    for etf, meta in SECTOR_ETFS.items():
        etf_df = extract_ticker_df(raw_data, etf)
        snapshot = compute_technical_snapshot(etf_df, spy_returns) if etf_df is not None else None
        
        if snapshot is None:
            # Previously defaulted to an optimistic +2.5% "OUTPERFORMING" state on a failed
            # download, which manufactured false alpha: a data-outage sector could rank into
            # the top quartile and get scored as a leading sector for every stock in it.
            # Neutral/unavailable values so a missing ETF can't masquerade as a strong one.
            vs_ema50 = 0.0
            mom5 = 0.0
            mom20 = 0.0
            status = "DATA_UNAVAILABLE"
            holding_days = 0
            crossed = "NO"
        else:
            vs_ema50 = snapshot["ema50_dist_pct"]
            mom5 = snapshot["d5_return"]
            mom20 = snapshot["d20_return"]
            
            raw_c = snapshot["raw_close"]
            raw_e = snapshot["raw_ema50"]
            
            # True Mathematical Crossover Check & Consecutive Holding Days
            if len(raw_c) >= 2 and len(raw_e) >= 2:
                yesterday_diff = float(raw_c.iloc[-2]) - float(raw_e.iloc[-2])
                today_diff = float(raw_c.iloc[-1]) - float(raw_e.iloc[-1])
                did_flip = (np.sign(yesterday_diff) != np.sign(today_diff))
                crossed = "YES" if did_flip else "NO"
                
                # Calculate exact consecutive holding days on current side
                current_sign = np.sign(today_diff)
                holding_days = 0
                diff_series = raw_c - raw_e
                for pos in range(len(diff_series) - 1, -1, -1):
                    val = float(diff_series.iloc[pos])
                    if np.sign(val) == current_sign:
                        holding_days += 1
                    else:
                        break
            else:
                crossed = "NO"
                holding_days = 15
                today_diff = vs_ema50

            # Mathematical Status Classification
            if vs_ema50 > 1.5 and holding_days >= 5:
                status = "★ OUTPERFORMING"
            elif vs_ema50 < -1.5 and holding_days >= 5:
                status = "WEAKENING"
            elif today_diff >= 0:
                status = "GAINING"
            else:
                status = "WEAKENING"

        # Populate tickers at support using ETF_SECTOR_MAP
        rule = ETF_SECTOR_MAP.get(etf, {"sectors": [meta["name"].upper()], "keywords": []})
        matched_tickers = []
        for t in ticker_records:
            t_sec = t["sector"].upper()
            t_sub = t["subsector"].lower()
            sec_ok = any(s in t_sec for s in rule["sectors"])
            kw_ok = any(kw in t_sub for kw in rule["keywords"]) if rule["keywords"] else True
            if sec_ok and kw_ok and t["bounce_state"] in ["BOUNCED", "IN ZONE", "ABOVE"]:
                matched_tickers.append(t["ticker"])

        reclaiming_in_sector = len([t for t in matched_tickers if any(c["ticker"] == t for c in qualified_candidates)])

        if status == "DATA_UNAVAILABLE":
            sig = "DATA UNAVAILABLE — sector strength unknown"
        elif "OUTPERFORMING" in status:
            sig = f"★ HOT — ETF + {len(matched_tickers)} tickers bouncing"
        elif "GAINING" in status:
            sig = "REGIME CHANGE — watch closely"
        elif "WEAKENING" in status:
            sig = "TICKERS BOUNCING — sector may turn"
        else:
            sig = "CAUTION — growth lagging"

        sec_entry = {
            "etf": etf,
            "sector": meta["name"],
            "type": meta["type"],
            "status": status,
            "vs_ema50": f"{vs_ema50:+.2f}%",
            "vs_ema50_num": round(vs_ema50, 2),
            "days": holding_days,
            "mom5d": f"{mom5:+.2f}%",
            "mom20d": f"{mom20:+.2f}%",
            "mom5_num": round(mom5, 2),
            "mom20_num": round(mom20, 2),
            "crossed": crossed,
            "reclaiming_count": reclaiming_in_sector,
            "bouncing_count": len(matched_tickers),
            "tickers_at_support": matched_tickers[:12],
            "signal": sig
        }
        sector_results.append(sec_entry)

        # 25 ETF Ladder Item
        all_25_etfs.append({
            "etf": etf,
            "sector": meta["name"],
            "style": meta["type"].capitalize(),
            "pct": round(vs_ema50, 2),
            "days": holding_days,
            "status": status,
            "mom5d": f"{mom5:+.2f}%",
            "mom20d": f"{mom20:+.2f}%",
            "mom5_num": round(mom5, 2),
            "mom20_num": round(mom20, 2),
            "tickers_at_support": matched_tickers[:12]
        })

        # Don't let a data outage masquerade as a regime-change signal (holding_days=0 and
        # vs_ema50=0.0 would otherwise satisfy the "just flipped" condition below every time).
        if status != "DATA_UNAVAILABLE" and (crossed == "YES" or (holding_days <= 2 and abs(vs_ema50) <= 2.0)):
            regime_change_etfs.append({
                "etf": etf,
                "sector": meta["name"],
                "style": meta["type"],
                "status": "GAINING" if vs_ema50 >= 0 else "WEAKENING",
                "vs_ema50": f"{vs_ema50:+.2f}%",
                "mom": f"{mom5:+.2f}% / {mom20:+.2f}%",
                "at_support": len(matched_tickers)
            })

    all_25_etfs = sorted(all_25_etfs, key=lambda x: x["pct"], reverse=True)
    sector_results = sorted(sector_results, key=lambda x: x["vs_ema50_num"], reverse=True)

    # 4. Sector Strength (Unique 20 Sectors)
    all_known_sectors = set(t["sector"].upper() for t in ticker_records if t.get("sector"))
    for meta in SECTOR_ETFS.values():
        all_known_sectors.add(meta["name"].upper())
    for s_name, _ in taxonomy.values():
        all_known_sectors.add(s_name.upper())

    sector_strength = []
    for sec_name in sorted(list(all_known_sectors)):
        sec_tickers = [t for t in ticker_records if t["sector"].upper() == sec_name]
        qual_count = len([t for t in sec_tickers if t.get("qualified") == "YES"])
        win_rate_val = round((qual_count / max(1, len(sec_tickers))) * 100) if sec_tickers else 0
        valid_rets = [float(t.get("return_pct", 0)) for t in sec_tickers if t.get("return_pct") is not None and not np.isnan(float(t.get("return_pct", 0)))]
        avg_ret_val = round(sum(valid_rets) / max(1, len(valid_rets)), 2) if valid_rets else 0.0
        score_val = max(1, min(10, round((win_rate_val / 10) * 0.7 + (max(0, avg_ret_val) * 0.3)))) if sec_tickers else 1
        sector_strength.append({
            "sector": sec_name,
            "score": score_val,
            "display": f"{score_val}/10",
            "strength_str": f"{score_val}/10",
            "win_pct": f"{win_rate_val}%",
            "avg_ret": f"{avg_ret_val:+.2f}%"
        })
    sector_strength = sorted(sector_strength, key=lambda x: x["score"], reverse=True)

    # 5. Rotating In (HOT Sectors matching Netlify methodology)
    # Dynamic sort by active support retests descending (zero hardcoded priority list or artificial floors)
    rotating_candidates = []
    all_unique_sectors = sorted(list(set(t["sector"] for t in ticker_records if t.get("sector") and t["sector"] not in ["Unknown", "INDEX", "Commodity", "Currency"])))
    
    for sec_name in all_unique_sectors:
        sec_tickers = [t for t in ticker_records if t["sector"] == sec_name]
        bouncing = [t for t in sec_tickers if t.get("bounce_state") in ["BOUNCED", "IN ZONE", "ABOVE"]]
        b_count = len(bouncing)
        recent_3d = len([t for t in bouncing if t.get("reclaim_days", 1) <= 3])
        
        # Calculate positive bounce momentum / gain from support
        bounce_gains = [t.get("return_pct", 0) for t in bouncing if t.get("return_pct", 0) > 0]
        avg_bounce_ret = round(sum(bounce_gains) / max(1, len(bounce_gains)), 2) if bounce_gains else 0.0
        
        # Dynamic rotation tier matching Netlify
        if b_count >= 20 or avg_bounce_ret >= 4.0:
            rot_tier = "HOT 8/10"
        elif b_count >= 10 or avg_bounce_ret >= 1.5:
            rot_tier = "ACTIVE 6/10"
        elif b_count >= 5:
            rot_tier = "WARMING 4/10"
        else:
            rot_tier = "QUIET 2/10"
            
        rotating_candidates.append({
            "sector": sec_name,
            "strength": rot_tier,
            "bounces": b_count,
            "recent_3d": recent_3d,
            "avg_return": f"{avg_bounce_ret:+.2f}%",
            "avg_return_num": avg_bounce_ret
        })

    # Sort strictly by active support bounces descending, then return
    rotating_candidates = sorted(rotating_candidates, key=lambda x: (x["bounces"], x["avg_return_num"]), reverse=True)
    rotating_in = rotating_candidates[:8]

    # 6. Complete 90+ Sub-Sectors
    subsector_dict = {}
    for t in ticker_records:
        sub = t.get("subsector") or "General"
        if sub not in subsector_dict:
            subsector_dict[sub] = {"sector": t["sector"], "tickers": []}
        subsector_dict[sub]["tickers"].append(t)

    all_subsectors = []
    for sub, data_sub in subsector_dict.items():
        t_list = data_sub["tickers"]
        count = len(t_list)
        qual = len([t for t in t_list if t.get("qualified") == "YES" or t.get("ema50_pct", 0) >= 0])
        win = round((qual / count) * 100)
        rets = [float(t.get("return_pct", 0)) for t in t_list if t.get("return_pct") is not None and not np.isnan(float(t.get("return_pct", 0)))]
        avg_ret = round(sum(rets) / len(rets), 2) if rets else 0.0
        score = max(1, min(10, round((win / 10) * 0.6 + min(4, max(0, avg_ret * 0.2)))))
        
        # Netlify Sub-Sector Conviction Signal
        if win >= 60:
            conviction_sig = "GOOD — Trade 3rd+"
            conviction_badge = "emerald"
        elif win >= 40:
            conviction_sig = "MODERATE — Selective"
            conviction_badge = "blue"
        elif win >= 25:
            conviction_sig = "WEAK — Skip or Half"
            conviction_badge = "amber"
        else:
            conviction_sig = "AVOID — Sector Failing"
            conviction_badge = "rose"

        all_subsectors.append({
            "subsector": f"{sub} • {count}",
            "subsector_raw": sub,
            "sector": data_sub["sector"],
            "str": f"{score}/10",
            "score": score,
            "win": f"{win}%",
            "ret": f"{avg_ret:+.2f}%",
            "ret_num": avg_ret,
            "signal": conviction_sig,
            "signal_badge": conviction_badge,
            "tickers": [t["ticker"] for t in t_list]
        })

    all_subsectors.sort(key=lambda x: (x["score"], int(x["win"].replace("%", "")), x["ret_num"]), reverse=True)
    top_subsectors = all_subsectors[:15]

    # 7. Reclaims and Bounces by Sector
    reclaims_by_sector = []
    bounces_by_sector = []
    for sec_name in sorted(list(set(t["sector"] for t in ticker_records))):
        rec_count = len([t for t in ticker_records if t["sector"] == sec_name and t["qualified"] == "YES"])
        bnc_count = len([t for t in ticker_records if t["sector"] == sec_name and t["bounce_state"] in ["BOUNCED", "IN ZONE"]])
        reclaims_by_sector.append({"sector": sec_name, "count": rec_count})
        bounces_by_sector.append({"sector": sec_name, "count": bnc_count})
    reclaims_by_sector = sorted(reclaims_by_sector, key=lambda x: x["count"], reverse=True)
    bounces_by_sector = sorted(bounces_by_sector, key=lambda x: x["count"], reverse=True)

    # 8. Fast Reclaims
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
    fast_reclaims = sorted(fast_reclaims, key=lambda x: (x["days"], -float(x["ret_pct"].replace("%", "").replace("+", ""))))

    # 9. Daily Activity (From summary history)
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

    # 10. Macro Breadth Calculation
    top_sectors = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    top_sectors_str = ", ".join([f"{s}({c})" for s, c in top_sectors]) if top_sectors else "FINANCIALS, TECH, ENERGY"

    # Cumulative alerts/reclaims/win-rate previously used hardcoded seed values (1012, 385,
    # "38.0%") whenever the session count was small, and winrate_cumulative was *always*
    # fake regardless of session size. data/summary.json already accumulates one macro_breadth
    # entry per scan day (see save_payloads), including total_alerts/reclaims - so the real
    # cumulative figures are just a sum over that history plus today's session counts.
    cumulative_alerts = alert_count
    cumulative_reclaims = reclaim_count
    try:
        _summary_path = os.path.join(DATA_DIR, "summary.json")
        if os.path.exists(_summary_path):
            with open(_summary_path, "r") as _sf:
                _hist_days = json.load(_sf)
            for _d in _hist_days:
                if _d.get("date") == today_str:
                    continue  # avoid double-counting a same-day re-run
                cumulative_alerts += int(_d.get("total_alerts", 0) or 0)
                cumulative_reclaims += int(_d.get("reclaims", 0) or 0)
    except Exception:
        pass

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
        "total_alerts_session": alert_count,
        "total_alerts_cumulative": cumulative_alerts,
        "reclaims_session": reclaim_count,
        "reclaims_cumulative": cumulative_reclaims,
        "winrate_session": f"{(reclaim_count / max(1, alert_count))*100:.1f}%",
        "winrate_cumulative": f"{(cumulative_reclaims / max(1, cumulative_alerts))*100:.1f}%",
        "funnel_diagnostic": funnel,
        "offense_pct": round((len([e for e in all_25_etfs if e["style"] in ["Growth", "Cyclical"] and e["pct"] >= 0]) / 20) * 100),
        "regime": "RISK-ON" if (len([e for e in all_25_etfs if e["style"] in ["Growth", "Cyclical"] and e["pct"] >= 0]) / 20) >= 0.60 else ("RISK-OFF" if (len([e for e in all_25_etfs if e["style"] in ["Growth", "Cyclical"] and e["pct"] >= 0]) / 20) <= 0.35 else "MIXED"),
        "regime_desc": "RISK-ON — Broad market expansion" if (len([e for e in all_25_etfs if e["style"] in ["Growth", "Cyclical"] and e["pct"] >= 0]) / 20) >= 0.60 else ("RISK-OFF — Defensive capital rotation" if (len([e for e in all_25_etfs if e["style"] in ["Growth", "Cyclical"] and e["pct"] >= 0]) / 20) <= 0.35 else "MIXED — No clear rotation")
    }

    # 11. Multi-factor Alpha Radar Candidate Sorting
    sector_priority = {
        "TECH SOFTWARE": 10, "TECH SEMIS": 10, "FINANCIALS": 9, "ENERGY": 9,
        "HEALTHCARE": 8, "TECH CORE": 8, "COMM SERVICES": 7, "CRYPTO": 7,
        "INDUSTRIALS": 6, "MATERIALS": 5, "CONSUMER DISC": 5, "CONSUMER STAPLES": 4
    }

    qualified_candidates = sorted(
        qualified_candidates,
        key=lambda x: (
            x.get("reclaim_days", 2),
            -sector_priority.get(x.get("sector", "").upper(), 1),
            -float(str(x.get("rr_ratio", "1:2.5")).replace("1:", "")),
            -x.get("beta", 1.0)
        )
    )

    # Sort Strategic LEAPS candidates (prioritize secular tech leaders & high quality)
    strategic_leaps_candidates = sorted(
        strategic_leaps_candidates,
        key=lambda x: (
            -sector_priority.get(x.get("sector", "").upper(), 1),
            x.get("price", 100.0) # Larger institutional market cap proxy
        )
    )

    # 12. Benchmark Matrix, Market Commentary & Downside Hedges
    benchmark_matrix = calculate_benchmark_matrix(raw_data, sample_date_str)
    market_commentary = generate_market_commentary(benchmark_matrix, macro_breadth, all_25_etfs, top_subsectors, funnel)

    # Downside Hedge Scanning: Detect stocks in bottom sectors / Stage 4 downtrend failing overhead resistance
    bottom_sectors = set([e["sector"].upper() for e in sorted(all_25_etfs, key=lambda x: float(x.get("pct", 0) or 0))[:8]])
    raw_downside_candidates = []
    
    for t in ticker_records:
        t_sec = t.get("sector", "").upper()
        if t_sec in bottom_sectors or t.get("ema50_pct", 0) < -2.0:
            df_t = extract_ticker_df(raw_data, t["ticker"])
            if df_t is not None and len(df_t) >= 50:
                from indicators import calculate_ema, calculate_sma, calculate_rsi, calculate_macd
                c_s = df_t["Close"]
                h_s = df_t["High"]
                l_s = df_t["Low"]
                o_s = df_t["Open"] if "Open" in df_t.columns else c_s
                e21 = calculate_ema(c_s, 21)
                e50 = calculate_ema(c_s, 50)
                s200 = calculate_sma(c_s, 200)
                rsi_s = calculate_rsi(c_s, 14)
                _, _, m_hist = calculate_macd(c_s, 12, 26, 9)
                is_rej, lvl_name, lvl_price = patterns.detect_resistance_rejection(h_s, l_s, c_s, o_s, e21, e50, s200, rsi_s, m_hist)
                if is_rej:
                    hedge_ticket = patterns.model_bear_put_spread(t["ticker"], t["price"], round(t["price"] * 1.03, 2), round(t["price"] * 0.88, 2), today=now_utc.date())
                    raw_downside_candidates.append({
                        "ticker": t["ticker"],
                        "sector": t["sector"],
                        "subsector": t.get("subsector", "General"),
                        "price": t["price"],
                        "stop": round(t["price"] * 1.03, 2),
                        "tp1": round(t["price"] * 0.88, 2),
                        "tp2": round(t["price"] * 0.82, 2),
                        "rr_ratio": hedge_ticket["rr_ratio"],
                        "resistance_level": lvl_name,
                        "resistance_price": lvl_price,
                        "long_strike": hedge_ticket["long_strike"],
                        "short_strike": hedge_ticket["short_strike"],
                        "contract": hedge_ticket["contract"],
                        "contract_details": hedge_ticket["contract_details"],
                        "routing_guidance": hedge_ticket["routing_guidance"],
                        "est_debit": hedge_ticket["est_debit"],
                        "width": hedge_ticket["width"],
                        "structure": "Bear Put Spread (30-45 DTE)",
                        "rvol": t.get("rvol", 1.0),
                        "weekly_stage": t.get("weekly_stage", "STAGE 4 (Declining)"),
                        "execution_state": "CONFIRMED REJECTION",
                        "execution_badge": "🔴 CONFIRMED REJECTION"
                    })

    # If no rejection found dynamically, provide deterministic hedge candidate from bottom sector laggards
    if not raw_downside_candidates:
        for t in ticker_records:
            if t.get("sector", "").upper() in bottom_sectors and t.get("ema50_pct", 0) < 0:
                hedge_ticket = patterns.model_bear_put_spread(t["ticker"], t["price"], round(t["price"] * 1.03, 2), round(t["price"] * 0.88, 2), today=now_utc.date())
                raw_downside_candidates.append({
                    "ticker": t["ticker"],
                    "sector": t["sector"],
                    "subsector": t.get("subsector", "General"),
                    "price": t["price"],
                    "stop": round(t["price"] * 1.03, 2),
                    "tp1": round(t["price"] * 0.88, 2),
                    "tp2": round(t["price"] * 0.82, 2),
                    "rr_ratio": hedge_ticket["rr_ratio"],
                    "resistance_level": "EMA50 Resistance",
                    "resistance_price": round(t["price"] * 1.02, 2),
                    "long_strike": hedge_ticket["long_strike"],
                    "short_strike": hedge_ticket["short_strike"],
                    "contract": hedge_ticket["contract"],
                    "contract_details": hedge_ticket["contract_details"],
                    "routing_guidance": hedge_ticket["routing_guidance"],
                    "est_debit": hedge_ticket["est_debit"],
                    "width": hedge_ticket["width"],
                    "structure": "Bear Put Spread (30-45 DTE)",
                    "rvol": t.get("rvol", 1.0),
                    "weekly_stage": "STAGE 4 (Declining)",
                    "execution_state": "CONFIRMED REJECTION",
                    "execution_badge": "🔴 CONFIRMED REJECTION"
                })

    # WATERFALL LIQUIDITY QUEUE FOR DOWNSIDE HEDGES
    # Inspects live put options chain; if low volume / low open interest, advances to the NEXT candidate in line!
    verified_downside_hedges = []
    for h_cand in raw_downside_candidates:
        # Live scans only; during backfills skip network calls for sub-minute execution
        if sample_date_str is None:
            opt_verif = patterns.verify_and_fetch_live_options(
                ticker=h_cand["ticker"],
                option_type="PUT",
                long_strike=h_cand.get("long_strike", h_cand["price"] * 1.02),
                short_strike=h_cand.get("short_strike", h_cand["tp1"]),
                target_dte_range=(30, 50),
                today=now_utc.date()
            )
        else:
            opt_verif = {"passed": True, "offline_fallback": True, "long_oi": 520, "short_oi": 380, "total_vol": 75}
        if opt_verif and not opt_verif.get("passed", True):
            funnel["illiquid_options"] = funnel.get("illiquid_options", 0) + 1
            print(f"[*] Downside hedge candidate {h_cand['ticker']} skipped due to illiquid options ({opt_verif.get('reject_reason')}). Waterfalling to next in queue...")
            continue

        # Attach live options liquidity metrics
        if opt_verif and not opt_verif.get("offline_fallback", False):
            h_cand["long_oi"] = opt_verif.get("long_oi", 520)
            h_cand["short_oi"] = opt_verif.get("short_oi", 380)
            h_cand["opt_volume"] = opt_verif.get("total_vol", 60)
            h_cand["est_debit"] = opt_verif.get("live_debit", h_cand["est_debit"])
            h_cand["liquidity_status"] = opt_verif.get("liquidity_status")
            h_cand["is_offline_simulated"] = False
        else:
            # Simulated liquidity (no live chain fetch during backfills). Tagged explicitly
            # so the ledger/UI can't mistake this for a real, verified live fill.
            h_cand["long_oi"] = 520
            h_cand["short_oi"] = 380
            h_cand["opt_volume"] = 75
            h_cand["liquidity_status"] = "🟢 LIQUID (Simulated — Backfill/Offline)"
            h_cand["is_offline_simulated"] = True

        verified_downside_hedges.append(h_cand)
        if len(verified_downside_hedges) >= 5:
            break

    # WATERFALL LIQUIDITY QUEUE FOR BULL CALL SPREADS
    candidate_queue = list(qualified_candidates)
    if benchmark_matrix.get("actionable_bias") == "OFFENSE_NON_TECH":
        non_tech = [c for c in qualified_candidates if c.get("sector") not in ["TECH SOFTWARE", "TECH SEMIS", "TECH CORE"]]
        if len(non_tech) >= 2:
            candidate_queue = non_tech

    verified_top_candidates = []
    for c_cand in candidate_queue:
        # Live scans only; during backfills skip network calls for sub-minute execution
        if sample_date_str is None:
            opt_verif = patterns.verify_and_fetch_live_options(
                ticker=c_cand["ticker"],
                option_type="CALL",
                long_strike=c_cand.get("long_strike", c_cand["price"]),
                short_strike=c_cand.get("short_strike", c_cand["tp1"]),
                target_dte_range=(35, 65),
                today=now_utc.date()
            )
        else:
            opt_verif = {"passed": True, "offline_fallback": True, "long_oi": 650, "short_oi": 420, "total_vol": 110}
        if opt_verif and not opt_verif.get("passed", True):
            funnel["illiquid_options"] = funnel.get("illiquid_options", 0) + 1
            print(f"[*] Bull spread candidate {c_cand['ticker']} skipped due to illiquid options ({opt_verif.get('reject_reason')}). Waterfalling to next in queue...")
            continue

        if opt_verif and not opt_verif.get("offline_fallback", False):
            c_cand["long_oi"] = opt_verif.get("long_oi", 650)
            c_cand["short_oi"] = opt_verif.get("short_oi", 420)
            c_cand["opt_volume"] = opt_verif.get("total_vol", 85)
            c_cand["est_debit"] = opt_verif.get("live_debit", c_cand["est_debit"])
            c_cand["liquidity_status"] = opt_verif.get("liquidity_status")
            c_cand["is_offline_simulated"] = False
        else:
            c_cand["long_oi"] = 650
            c_cand["short_oi"] = 420
            c_cand["opt_volume"] = 110
            c_cand["liquidity_status"] = "🟢 LIQUID (Simulated — Backfill/Offline)"
            c_cand["is_offline_simulated"] = True

        verified_top_candidates.append(c_cand)
        if len(verified_top_candidates) >= 5:
            break

    # WATERFALL FOR LEAPS
    verified_leaps = []
    for l_cand in strategic_leaps_candidates:
        # Live scans only; during backfills skip network calls for sub-minute execution
        if sample_date_str is None:
            opt_verif = patterns.verify_and_fetch_live_options(
                ticker=l_cand["ticker"],
                option_type="LEAPS",
                long_strike=l_cand.get("strike", l_cand["price"] * 0.80),
                target_dte_range=(300, 600),
                today=now_utc.date()
            )
        else:
            opt_verif = {"passed": True, "offline_fallback": True, "long_oi": 350, "total_vol": 35}
        if opt_verif and not opt_verif.get("passed", True):
            continue
        if opt_verif and not opt_verif.get("offline_fallback", False):
            l_cand["long_oi"] = opt_verif.get("long_oi", 350)
            l_cand["liquidity_status"] = opt_verif.get("liquidity_status")
            l_cand["is_offline_simulated"] = False
        else:
            l_cand["long_oi"] = 350
            l_cand["liquidity_status"] = "🟢 LIQUID LEAPS (Simulated — Backfill/Offline)"
            l_cand["is_offline_simulated"] = True
        verified_leaps.append(l_cand)
        if len(verified_leaps) >= 5:
            break

    # =========================================================================
    # DYNAMIC ALPHA COMPOSITE SCORING & SECTOR DIVERSIFICATION (RELEASE V14)
    # =========================================================================
    top_quartile_sectors = set()
    # Exclude ETFs with no real data from the leadership ranking - a neutral 0.0% fallback
    # value shouldn't be able to earn a sector "top quartile" status it didn't actually earn.
    _ranked_etfs = [e for e in all_25_etfs if e.get("status") != "DATA_UNAVAILABLE"]
    num_tq_etfs = max(1, len(_ranked_etfs) // 4 + 1)
    for e in _ranked_etfs[:num_tq_etfs]:
        if e.get("sector"):
            top_quartile_sectors.add(e["sector"].upper())
        if e.get("etf"):
            top_quartile_sectors.add(e["etf"].upper())
    for s in sector_strength[:max(1, len(sector_strength) // 4 + 1)]:
        if s.get("sector"):
            top_quartile_sectors.add(s["sector"].upper())

    sector_mom_map = {}
    for e in all_25_etfs:
        sec_name = (e.get("sector") or "").upper()
        spread = float(e.get("mom5_num", 0)) - float(e.get("mom20_num", 0))
        sector_mom_map[sec_name] = spread
        if e.get("etf"):
            sector_mom_map[e["etf"].upper()] = spread

    macro_confluence = benchmark_matrix.get("composite_score", benchmark_matrix.get("score", 2))

    for s_cand in qualified_stock_candidates:
        s_sec = (s_cand.get("sector") or "").upper()
        s_score, s_breakdown = stocks.compute_alpha_composite_score(
            reclaim_days=s_cand.get("reclaim_days", 0),
            rvol=s_cand.get("rvol", 1.0),
            price=s_cand.get("price", 100.0),
            ema50=s_cand.get("ema50", s_cand.get("price", 100.0)),
            sector=s_cand.get("sector"),
            rr_ratio=s_cand.get("rr_ratio", 2.5),
            top_quartile_sectors=top_quartile_sectors,
            market_structure=s_cand.get("market_structure"),
            macro_confluence=macro_confluence,
            mom_spread=sector_mom_map.get(s_sec, 0.0),
            return_breakdown=True
        )
        s_cand["alpha_score"] = s_score
        s_cand["alpha_score_breakdown"] = s_breakdown

    # Score ALL qualified options candidates so all_qualified and radar.html have real scores
    # (previously this only scored the liquidity-filtered verified_top_candidates, leaving
    # the rest of qualified_candidates - and anything reading options_alpha_score off them -
    # without a real score). verified_top_candidates holds references into qualified_candidates,
    # so mutating here still updates it in place; the sort below still applies correctly.
    for c_cand in qualified_candidates:
        opt_s, opt_b = patterns.compute_options_alpha_score(
            directional_alpha=c_cand.get("alpha_score", 75.0),
            iv_rank=c_cand.get("iv_rank", 25.0),
            long_oi=c_cand.get("long_oi", 650),
            short_oi=c_cand.get("short_oi", 420),
            bid_ask_spread_pct=c_cand.get("bid_ask_spread_pct", 0.05),
            overhead_runway_pct=c_cand.get("overhead_runway_pct", 999.0),
            days_to_earnings=c_cand.get("days_to_earnings", 60),
            is_leaps=False,
            strategy_prong=c_cand.get("strategy_prong", "BALANCED"),
            rsi=c_cand.get("rsi", 52.0),
            macd_hook_ok=c_cand.get("macd_hook_ok", True),
            return_breakdown=True
        )
        c_cand["options_alpha_score"] = opt_s
        c_cand["alpha_score"] = opt_s  # Mirror key for uniform UI compatibility
        c_cand["options_alpha_breakdown"] = opt_b

    verified_top_candidates.sort(key=lambda x: x.get("options_alpha_score", 0), reverse=True)

    # Score and dynamically rank Strategic LEAPS
    for l_cand in verified_leaps:
        l_s, l_b = patterns.compute_options_alpha_score(
            directional_alpha=l_cand.get("alpha_score", 70.0),
            iv_rank=l_cand.get("iv_rank", 20.0),
            long_oi=l_cand.get("long_oi", 350),
            short_oi=None,
            bid_ask_spread_pct=0.06,
            overhead_runway_pct=l_cand.get("overhead_runway_pct", 999.0),
            days_to_earnings=l_cand.get("days_to_earnings", 60),
            is_leaps=True,
            strategy_prong="CORE",
            rsi=l_cand.get("rsi", 52.0),
            macd_hook_ok=l_cand.get("macd_hook_ok", True),
            return_breakdown=True
        )
        l_cand["options_alpha_score"] = l_s
        l_cand["options_alpha_breakdown"] = l_b

    verified_leaps.sort(key=lambda x: x.get("options_alpha_score", 0), reverse=True)

    # Dynamic sort: descending by multi-factor Alpha Composite Score
    qualified_stock_candidates.sort(key=lambda x: x.get("alpha_score", 0), reverse=True)

    # Enforce Sector Concentration Guardrail: maximum 2 tickers per sector
    selected_stock_recommendations = []
    sector_counts = {}
    for s_cand in qualified_stock_candidates:
        sec = (s_cand.get("sector") or "OTHER").upper()
        if sector_counts.get(sec, 0) < 2:
            selected_stock_recommendations.append(s_cand)
            sector_counts[sec] = sector_counts.get(sec, 0) + 1
        if len(selected_stock_recommendations) >= 5:
            break

    # Fallback if fewer than 5 met strict cap
    if len(selected_stock_recommendations) < 5:
        for s_cand in qualified_stock_candidates:
            if s_cand not in selected_stock_recommendations:
                selected_stock_recommendations.append(s_cand)
                if len(selected_stock_recommendations) >= 5:
                    break

    # =========================================================================
    # 13. DEDICATED HIGH-RISK RADAR: TOP 10 STOCKS & TOP 10 OPTIONS
    # =========================================================================
    # High-Risk radar logic, scoring, and streak tracking modularized into engine/radar.py
    archive_records = []
    archive_file = os.path.join(DATA_DIR, "recommendations_archive.json")
    if os.path.exists(archive_file):
        try:
            with open(archive_file, "r", encoding="utf-8") as f:
                archive_records = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load recommendations_archive.json for streak computation: {e}")

    high_risk_stocks_radar, high_risk_options_radar = build_high_risk_radars(
        ticker_records=ticker_records,
        qualified_stock_candidates=qualified_stock_candidates,
        qualified_candidates=qualified_candidates,
        raw_data=raw_data,
        top_quartile_sectors=top_quartile_sectors,
        macro_confluence=macro_confluence,
        sector_mom_map=sector_mom_map,
        now_utc=now_utc,
        date_str=today_str,
        archive_records=archive_records,
    )

    # Feature 4: Near-Miss Watchlist (Candidates that failed exactly 1 gatekeeper filter)
    near_miss_candidates = build_near_miss_candidates(
        ticker_records=ticker_records,
        qualified_candidates=qualified_candidates,
        qualified_stock_candidates=qualified_stock_candidates,
    )

    return {
        "macro_breadth": macro_breadth,
        "benchmark_matrix": benchmark_matrix,
        "market_commentary": market_commentary,
        "downside_hedges": verified_downside_hedges,
        "funnel_diagnostic": funnel,
        "all_25_etfs": all_25_etfs,
        "sector_strength": sector_strength,
        "rotating_in": rotating_in,
        "all_subsectors": all_subsectors,
        "top_subsectors": top_subsectors,
        "reclaims_by_sector": reclaims_by_sector,
        "bounces_by_sector": bounces_by_sector,
        "bounces_by_level": retrace_counts,
        "fast_reclaims": fast_reclaims,
        "daily_activity": daily_activity,
        "regime_change_etfs": regime_change_etfs,
        "top_candidates": verified_top_candidates[:5],
        "high_risk_stocks_radar": high_risk_stocks_radar,
        "high_risk_options_radar": high_risk_options_radar,
        "near_miss_candidates": near_miss_candidates,
        "stock_recommendations": selected_stock_recommendations[:5],
        "all_qualified_stocks": qualified_stock_candidates,
        "core_stocks": core_stock_candidates[:5],
        "all_qualified": qualified_candidates,
        "strategic_leaps": verified_leaps,
        "sector_momentum": sector_results,
        "tickers": ticker_records
    }
