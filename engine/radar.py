"""
High-Risk Sprint Radar Module

Encapsulates candidate filtering, composite scoring, ranking, streak
computation, and payload assembly for the High-Risk Stocks and Options Radars.
"""

from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional, Tuple

try:
    from engine.config import (
        DEFAULT_PORTFOLIO_CAPITAL,
        DOLLAR_AT_RISK_PCT,
        MAX_CAPITAL_ALLOCATION_PCT,
        SPRINT_STOP_PCT,
    )
except (ImportError, ModuleNotFoundError):
    from config import (
        DEFAULT_PORTFOLIO_CAPITAL,
        DOLLAR_AT_RISK_PCT,
        MAX_CAPITAL_ALLOCATION_PCT,
        SPRINT_STOP_PCT,
    )

logger = logging.getLogger("radar")


def compute_radar_streak(
    ticker: str,
    asset_type: str,
    archive_records: Optional[List[Dict[str, Any]]],
    as_of_date: str,
) -> int:
    """
    Computes the number of consecutive prior scan dates a ticker appeared on
    the high-risk radar for the given asset_type ('EQUITY' or 'OPTION').
    
    Continuity is defined across distinct historical scan dates in the archive
    prior to as_of_date, so weekends and market holidays naturally do not break
    consecutive streaks. The first date gap encountered terminates the streak.

    Returns:
        int: Consecutive prior appearances (0 if absent on the immediate prior scan day).
    """
    if not archive_records:
        return 0

    target_ticker = str(ticker).upper().strip()
    norm_type = str(asset_type).upper().strip()
    target_suffix = "_HIGH_RISK_RADAR_STOCK" if norm_type in ("EQUITY", "STOCK") else "_HIGH_RISK_RADAR_OPTION"

    prior_scan_dates = sorted(
        {r.get("date") for r in archive_records if r.get("date") and r.get("date") < as_of_date},
        reverse=True
    )

    if not prior_scan_dates:
        return 0

    matched_dates = set()
    for r in archive_records:
        if str(r.get("ticker", "")).upper().strip() != target_ticker:
            continue
        if not r.get("is_radar"):
            continue

        rec_asset = str(r.get("asset_type", "")).upper().strip()
        rec_id = str(r.get("id", ""))

        if rec_asset == norm_type or rec_id.endswith(target_suffix):
            matched_dates.add(r.get("date"))

    streak = 0
    for dt in prior_scan_dates:
        if dt in matched_dates:
            streak += 1
        else:
            break

    return streak


def evaluate_gatekeepers(
    snapshot: Dict[str, Any],
    reclaim_days: int,
    retrace_type: str,
) -> Dict[str, Any]:
    """
    Evaluates the 6 fundamental gatekeeper conditions for a ticker snapshot.
    Returns a dictionary of individual gate evaluation details (pass, type, current, target, margin).
    """
    price = float(snapshot.get("price", 0.0))
    ema50 = float(snapshot.get("ema50", price))
    
    # 1. Price >= EMA50
    p_above_ema50 = bool(price >= ema50)
    ema50_margin = round(price - ema50, 2)
    ema50_margin_pct = round((price - ema50) / ema50 * 100, 2) if ema50 > 0 else 0.0

    # 2. Reclaim freshness (reclaim_days <= 3)
    reclaim_ok = bool(reclaim_days <= 3)
    reclaim_margin = 3 - reclaim_days

    # 3. Retrace taxonomy in ["EMA50", "DB", "OTE"]
    retrace_ok = bool(retrace_type in ["EMA50", "DB", "OTE"])

    # 4. Overhead runway (has_200, is_above_200 or runway >= 5.0%)
    has_200 = bool(snapshot.get("has_200sma", True) and snapshot.get("sma200") is not None)
    is_above_200 = bool(price >= snapshot["sma200"]) if has_200 else True
    runway_val = 0.0 if is_above_200 else float(snapshot.get("overhead_runway_pct") or 0.0)
    overhead_ok = bool(not has_200 or is_above_200 or (runway_val and runway_val >= 5.0))
    overhead_margin = 0.0 if is_above_200 else round(runway_val - 5.0, 1)

    # 5. RSI floor (RSI >= 45.0)
    rsi_val = float(snapshot.get("rsi", 50.0))
    rsi_floor_ok = bool(rsi_val >= 45.0)
    rsi_margin = round(rsi_val - 45.0, 1)

    # 6. MACD momentum hook (accelerating histogram or positive expansion)
    macd_crawling_up = snapshot.get("macd_crawling_up", False)
    macd_hook_ok = snapshot.get("macd_hook_ok", False)
    macd_hist_val = float(snapshot.get("macd_hist", 0.0)) if snapshot.get("macd_hist") is not None else 0.0
    macd_ok = bool(macd_hook_ok or macd_crawling_up or (macd_hist_val > 0.05 and p_above_ema50))

    # 7. Dow Theory Market Structure (not BEARISH_LH_LL)
    ms_regime = snapshot.get("market_structure", {}).get("regime", "NEUTRAL") if isinstance(snapshot.get("market_structure"), dict) else "NEUTRAL"
    dow_structure_ok = bool(ms_regime != "BEARISH_LH_LL")

    gate_results = {
        "price_above_ema50": {
            "pass": p_above_ema50,
            "label": "50 EMA Floor",
            "type": "CONTINUOUS",
            "current": round(price, 2),
            "target": round(ema50, 2),
            "margin": ema50_margin,
            "margin_pct": ema50_margin_pct,
            "detail": f"${price:.2f} vs 50 EMA ${ema50:.2f} ({ema50_margin_pct:+.1f}%)"
        },
        "reclaim_freshness": {
            "pass": reclaim_ok,
            "label": "Reclaim Freshness",
            "type": "CONTINUOUS",
            "current": reclaim_days,
            "target": 3,
            "margin": reclaim_margin,
            "detail": "Extended above 50 EMA (>15d)" if reclaim_days >= 15 else f"Day {reclaim_days} reclaim (needs ≤ 3)"
        },
        "retrace_taxonomy": {
            "pass": retrace_ok,
            "label": "Retrace Structure",
            "type": "CATEGORICAL",
            "current": retrace_type,
            "target": ["EMA50", "DB", "OTE"],
            "margin": 0,
            "detail": f"Pattern: {retrace_type} (needs EMA50, DB, or OTE)"
        },
        "overhead_200sma_runway": {
            "pass": overhead_ok,
            "label": "200 SMA Runway",
            "type": "CONTINUOUS",
            "current": round(runway_val, 1) if not is_above_200 else 999.0,
            "target": 5.0,
            "margin": overhead_margin,
            "detail": "Clear above 200 SMA" if is_above_200 else f"Runway {runway_val:.1f}% (needs ≥ 5.0%)"
        },
        "rsi_floor": {
            "pass": rsi_floor_ok,
            "label": "RSI(14) Floor",
            "type": "CONTINUOUS",
            "current": round(rsi_val, 1),
            "target": 45.0,
            "margin": rsi_margin,
            "detail": f"RSI {rsi_val:.1f} (needs ≥ 45.0, margin: {rsi_margin:+.1f})"
        },
        "macd_hook": {
            "pass": macd_ok,
            "label": "MACD Momentum Hook",
            "type": "BOOLEAN",
            "current": macd_ok,
            "target": True,
            "margin": 0 if macd_ok else -1,
            "detail": "Momentum accelerating (Hist_t > Hist_t-1)" if macd_ok else "MACD decelerating / no hook"
        },
        "dow_market_structure": {
            "pass": dow_structure_ok,
            "label": "Dow Market Structure",
            "type": "CATEGORICAL",
            "current": ms_regime,
            "target": "NOT BEARISH_LH_LL",
            "margin": 0 if dow_structure_ok else -1,
            "detail": f"Regime: {ms_regime}"
        }
    }

    return gate_results


def build_near_miss_candidates(
    ticker_records: List[Dict[str, Any]],
    qualified_candidates: List[Dict[str, Any]],
    qualified_stock_candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Identifies tickers that failed exactly 1 gatekeeper filter, building a
    prioritized 'Near-Miss Watchlist' ranked by proximity and Alpha potential.
    """
    qualified_tickers = {
        str(c.get("ticker", "")).upper()
        for c in (qualified_candidates or []) + (qualified_stock_candidates or [])
    }

    near_misses = []
    for r in ticker_records:
        ticker = str(r.get("ticker", "")).upper()
        if ticker in qualified_tickers:
            continue
        # Exclude broad market index ETFs
        if ticker in ("SPY", "QQQ", "IWM", "RSP"):
            continue

        gate_results = r.get("gate_results")
        if not gate_results:
            continue

        failed_gates = [k for k, v in gate_results.items() if not v.get("pass")]
        if len(failed_gates) == 1:
            failed_key = failed_gates[0]
            failed_info = gate_results[failed_key]
            
            near_misses.append({
                "ticker": ticker,
                "sector": r.get("sector", "GENERAL"),
                "subsector": r.get("subsector", "General"),
                "price": float(r.get("price", 0.0)),
                "ema50": float(r.get("ema50", 0.0)),
                "rsi": float(r.get("rsi", 50.0)),
                "beta": float(r.get("beta", 1.0)),
                "adr_pct": float(r.get("adr_pct", 2.0)),
                "alpha_score": float(r.get("alpha_score", 65.0)),
                "failed_gate": failed_key,
                "failed_gate_label": failed_info.get("label", failed_key),
                "failed_reason": failed_info.get("detail", ""),
                "margin_to_pass": failed_info.get("margin", 0.0),
                "margin_pct": failed_info.get("margin_pct", 0.0),
                "gate_type": failed_info.get("type", "CONTINUOUS"),
                "gate_details": gate_results,
                "reclaim_days": r.get("reclaim_days", 1),
                "reclaim_date": r.get("reclaim_date") or r.get("date") or "",
                "date": r.get("date") or "",
                "time": r.get("time") or "",
                "retrace": r.get("retrace", "EMA50"),
                "trend": r.get("trend", "NEAR MISS"),
                "execution_intent": "WATCHLIST_NEAR_MISS"
            })

    # Sort near-miss candidates primarily by reclaim freshness (Day 1 reclaim first), then alpha potential
    near_misses.sort(
        key=lambda x: (
            int(x.get("reclaim_days", 99)),
            -float(x.get("alpha_score", 0)),
            -float(x.get("beta", 1.0))
        )
    )
    return near_misses


def build_high_risk_radars(
    ticker_records: List[Dict[str, Any]],
    qualified_stock_candidates: List[Dict[str, Any]],
    qualified_candidates: List[Dict[str, Any]],
    raw_data: Any,
    top_quartile_sectors: List[str],
    macro_confluence: int,
    sector_mom_map: Dict[str, float],
    now_utc: datetime,
    date_str: str,
    archive_records: Optional[List[Dict[str, Any]]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Filters, scores, ranks, and enriches top-10 high-risk stocks and options radar entries.
    """
    if archive_records is None:
        archive_records = []

    stock_score_map = {s["ticker"]: s for s in qualified_stock_candidates if "ticker" in s}
    options_score_map = {c["ticker"]: c for c in qualified_candidates if "ticker" in c}

    # 1. High-Risk Stocks Radar
    high_risk_stocks_radar: List[Dict[str, Any]] = []
    for t in ticker_records:
        if t.get("ticker") in ["SPY", "QQQ", "RSP", "IWM"]:
            continue

        t_beta = float(t.get("beta", 1.0) or 1.0)
        t_adr = float(t.get("adr_pct", 2.0) or 2.0)
        is_hr = (t_beta >= 1.5 and t_adr >= 3.0) or (
            t.get("ticker") in stock_score_map and stock_score_map[t["ticker"]].get("strategy_prong") == "HIGH_RISK"
        )
        if not is_hr:
            continue

        t_price = float(t.get("price", 100.0) or 100.0)
        t_stop = round(t_price * (1.0 - SPRINT_STOP_PCT), 2)
        t_risk = round(t_price - t_stop, 2)
        t_tp05 = round(t_price + (t_risk * 1.0), 2)
        t_tp1 = round(t_price + (t_risk * 2.2), 2)
        t_tp2 = round(t_price + (t_risk * 3.5), 2)

        max_capital_per_trade = DEFAULT_PORTFOLIO_CAPITAL * MAX_CAPITAL_ALLOCATION_PCT
        max_risk_per_trade = DEFAULT_PORTFOLIO_CAPITAL * DOLLAR_AT_RISK_PCT
        t_shares = int(min(max_capital_per_trade / max(1.0, t_price), max_risk_per_trade / max(0.01, t_risk)))

        s_match = stock_score_map.get(t["ticker"])
        if s_match and s_match.get("alpha_score") is not None:
            t_score = float(s_match["alpha_score"])
            t_score_breakdown = s_match.get("alpha_score_breakdown", {})
        else:
            try:
                try:
                    from engine import stocks
                except (ImportError, ModuleNotFoundError):
                    import stocks
                s_sec = (t.get("sector") or "").upper()
                t_score, t_score_breakdown = stocks.compute_alpha_composite_score(
                    reclaim_days=t.get("reclaim_days", 1),
                    rvol=float(t.get("rvol", 1.2)),
                    price=t_price,
                    ema50=float(t.get("ema50", t_price)),
                    sector=t.get("sector"),
                    rr_ratio=2.2,
                    top_quartile_sectors=top_quartile_sectors,
                    market_structure=t.get("market_structure", "BULLISH_HH_HL"),
                    macro_confluence=macro_confluence,
                    mom_spread=sector_mom_map.get(s_sec, 0.0),
                    strategy_prong="HIGH_RISK",
                    return_breakdown=True
                )
            except Exception:
                t_score = 70.0
                t_score_breakdown = {}

        high_risk_stocks_radar.append({
            "action": "BUY",
            "ticker": t["ticker"],
            "sector": t.get("sector", "TECHNOLOGY"),
            "subsector": t.get("subsector", "High-Beta Tech"),
            "beta": t_beta,
            "adr_pct": t_adr,
            "rvol": float(t.get("rvol", 1.2)),
            "price": t_price,
            "stop": t_stop,
            "tp1": t_tp1,
            "tp2": t_tp2,
            "rr_ratio": 2.2,
            "weekly_stage": t.get("weekly_stage", "STAGE 2 (Advancing)"),
            "structure": "High-Risk Sprint (Common Shares)",
            "alpha_score": round(t_score, 1),
            "alpha_score_breakdown": t_score_breakdown,
            "shares": t_shares,
            "capital_deployed": round(t_shares * t_price, 2),
            "actual_risk_dollars": round(t_shares * t_risk, 2),
            "order_ticket": f"BUY {t_shares} SHARES @ ${t_price:.2f} LIMIT · STOP @ ${t_stop:.2f} · TP0.5: ${t_tp05:.2f} / TP1: ${t_tp1:.2f}",
            "execution_guidance": "High-Risk Sprint · Scale 50% at TP0.5 (+1.0R) · Breakeven Stop · Day 10 Velocity Exit (<1.0R)",
            "execution_intent": "RADAR_SURVEILLANCE"
        })

    # Sort strictly by real alpha_score descending (with beta as tie-breaker)
    high_risk_stocks_radar.sort(key=lambda x: (x.get("alpha_score", 0), x.get("beta", 1.0)), reverse=True)
    high_risk_stocks_radar = high_risk_stocks_radar[:10]
    for i, s in enumerate(high_risk_stocks_radar):
        s["rank"] = i + 1
        prior_streak = compute_radar_streak(s["ticker"], "EQUITY", archive_records, date_str)
        s["radar_streak_days"] = 1 + prior_streak

    # 2. High-Risk Options Radar
    high_risk_options_radar: List[Dict[str, Any]] = []
    for t in ticker_records:
        if t.get("ticker") in ["SPY", "QQQ", "RSP", "IWM"]:
            continue

        t_beta = float(t.get("beta", 1.0) or 1.0)
        t_adr = float(t.get("adr_pct", 2.0) or 2.0)
        is_hr = (t_beta >= 1.5 and t_adr >= 3.0) or (
            t.get("ticker") in options_score_map and options_score_map[t["ticker"]].get("strategy_prong") == "HIGH_RISK"
        )
        if not is_hr:
            continue

        t_price = float(t.get("price", 100.0) or 100.0)
        l_strike = round(t_price * 0.98 / 5.0) * 5.0 if t_price > 20 else round(t_price * 0.98 * 2) / 2
        s_width = round(t_price * 0.20 / 5.0) * 5.0 if t_price > 40 else (5.0 if t_price > 15 else 2.5)
        if s_width <= 0:
            s_width = 5.0
        sh_strike = round(l_strike + s_width, 2)
        debit = round(s_width * 0.38, 2)
        max_g = round(s_width - debit, 2)

        opt_match = options_score_map.get(t["ticker"])
        if opt_match and opt_match.get("iv_rank") is not None:
            iv_r = float(opt_match["iv_rank"])
        else:
            try:
                try:
                    from engine.indicators import calculate_iv_rank
                    from engine.market_data import extract_ticker_df
                except (ImportError, ModuleNotFoundError):
                    from indicators import calculate_iv_rank
                    from market_data import extract_ticker_df
                _t_df = extract_ticker_df(raw_data, t["ticker"])
                iv_r = calculate_iv_rank(_t_df["Close"]) if _t_df is not None and len(_t_df) > 20 else 45.0
            except Exception:
                iv_r = 45.0

        try:
            try:
                from engine import patterns
            except (ImportError, ModuleNotFoundError):
                import patterns
            _hr_expiry_date, _hr_dte = patterns.get_target_expiration(now_utc.date(), 45, 90)
            _hr_theta_cliff = (_hr_expiry_date - timedelta(days=21)).strftime("%b %d")
        except Exception:
            _hr_expiry_date = now_utc.date() + timedelta(days=60)
            _hr_dte = 60
            _hr_theta_cliff = (_hr_expiry_date - timedelta(days=21)).strftime("%b %d")

        s_match = stock_score_map.get(t["ticker"])
        if s_match and s_match.get("alpha_score") is not None:
            directional_alpha_val = float(s_match["alpha_score"])
        else:
            try:
                try:
                    from engine import stocks
                except (ImportError, ModuleNotFoundError):
                    import stocks
                s_sec = (t.get("sector") or "").upper()
                directional_alpha_val, _ = stocks.compute_alpha_composite_score(
                    reclaim_days=t.get("reclaim_days", 1),
                    rvol=float(t.get("rvol", 1.2)),
                    price=t_price,
                    ema50=float(t.get("ema50", t_price)),
                    sector=t.get("sector"),
                    rr_ratio=2.2,
                    top_quartile_sectors=top_quartile_sectors,
                    market_structure=t.get("market_structure", "BULLISH_HH_HL"),
                    macro_confluence=macro_confluence,
                    mom_spread=sector_mom_map.get(s_sec, 0.0),
                    strategy_prong="HIGH_RISK",
                    return_breakdown=False
                )
            except Exception as ex:
                logger.debug(f"Fallback to default directional alpha for {t.get('ticker')}: {ex}")
                directional_alpha_val = 75.0

        if opt_match and opt_match.get("options_alpha_score") is not None:
            t_opt_score = float(opt_match["options_alpha_score"])
            t_opt_breakdown = opt_match.get("options_alpha_breakdown", {})
        else:
            try:
                try:
                    from engine import patterns
                except (ImportError, ModuleNotFoundError):
                    import patterns
                t_opt_score, t_opt_breakdown = patterns.compute_options_alpha_score(
                    directional_alpha=directional_alpha_val,
                    iv_rank=iv_r,
                    long_oi=650,
                    short_oi=420,
                    bid_ask_spread_pct=0.05,
                    overhead_runway_pct=float(t.get("overhead_runway_pct", 999.0) or 999.0),
                    days_to_earnings=60,
                    is_leaps=False,
                    strategy_prong="HIGH_RISK",
                    rsi=float(t.get("rsi", 50.0)),
                    macd_hook_ok=bool(t.get("macd_crawling_up", True)),
                    return_breakdown=True
                )
            except Exception as ex:
                logger.warning(f"Could not compute options alpha score for {t.get('ticker')}: {ex}")
                t_opt_score = 75.0
                t_opt_breakdown = {}

        high_risk_options_radar.append({
            "action": "BUY",
            "ticker": t["ticker"],
            "sector": t.get("sector", "GENERAL"),
            "subsector": t.get("subsector", "General"),
            "price": t_price,
            "ema50": float(t.get("ema50", t_price)),
            "rsi": float(t.get("rsi", 50.0)),
            "macd_hist": float(t.get("macd_hist", 0.0)),
            "retrace": t.get("retrace") or t.get("retrace_type", "EMA50"),
            "reclaim_days": int(t.get("reclaim_days", 1)),
            "market_structure": t.get("market_structure", "BULLISH_HH_HL"),
            "stop": round(t_price * (1.0 - SPRINT_STOP_PCT), 2),
            "tp1": round(t_price * 1.15, 2),
            "tp2": round(t_price * 1.25, 2),
            "rr_ratio": f"1:{round(max_g / max(0.01, debit), 1)}",
            "contract": f"{_hr_expiry_date.strftime('%b %d')} ${l_strike:.0f}/${sh_strike:.0f} Call Spread",
            "contract_details": f"Width: ${s_width:.2f} | Est. Debit: ${debit:.2f} | Max Gain: ${max_g:.2f} | Theta Cliff: {_hr_theta_cliff} (21 DTE)",
            "expiry": _hr_expiry_date.strftime("%Y-%m-%d"),
            "dte": _hr_dte,
            "long_strike": l_strike,
            "short_strike": sh_strike,
            "width": s_width,
            "est_debit": debit,
            "max_profit": max_g,
            "beta": t_beta,
            "adr_pct": t_adr,
            "rvol": float(t.get("rvol", 1.2)),
            "iv_rank": iv_r,
            "liquidity": "HIGH",
            "options_alpha_score": round(t_opt_score, 1),
            "options_alpha_breakdown": t_opt_breakdown,
            "alpha_score": round(t_opt_score, 1),
            "routing_guidance": f"LIMIT @ ${debit:.2f} Mid (Do not cross spread; High-Risk BCS)",
            "execution_guidance": f"High-Risk BCS · Exit before 21 DTE Theta Cliff ({_hr_theta_cliff}) or Day 10 Velocity Stop",
            "execution_intent": "RADAR_SURVEILLANCE"
        })

    # Sort strictly by real options_alpha_score descending (with beta as tie-breaker)
    high_risk_options_radar.sort(key=lambda x: (x.get("options_alpha_score", 0), x.get("beta", 1.0)), reverse=True)
    high_risk_options_radar = high_risk_options_radar[:10]
    for i, o in enumerate(high_risk_options_radar):
        o["rank"] = i + 1
        prior_streak = compute_radar_streak(o["ticker"], "OPTION", archive_records, date_str)
        o["radar_streak_days"] = 1 + prior_streak

    return high_risk_stocks_radar, high_risk_options_radar
