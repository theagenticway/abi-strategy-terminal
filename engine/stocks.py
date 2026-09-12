"""
Deterministic Equity / Common Stock Strategy Engine for ABI Strategy Terminal.
Modular architecture: Sizing by Dollar-at-Risk, Two-Tranche Scale & Trail exits,
Gap-Down slippage modeling, and persistent stock audit ledger tracking.
"""

import os
import json
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STOCK_LOG_PATH = os.path.join(DATA_DIR, "stock_trades_log.json")


def calculate_stock_position_size(entry_price: float, stop_price: float, portfolio_capital: float = 50000.0, risk_pct: float = 0.015, max_alloc_pct: float = 0.20) -> dict:
    """
    Computes institutional fixed-fractional share sizing:
    - Sized strictly on Dollar-at-Risk (e.g. 1.5% account equity risk).
    - Enforces 20% single-stock capital allocation ceiling (prevents blowout on tight stops).
    - Returns integer share counts, actual dollars at risk, and total capital deployed.
    """
    if entry_price is None or np.isnan(entry_price) or entry_price <= 0:
        return {"shares": 0, "capital_deployed": 0.0, "actual_risk_dollars": 0.0, "risk_pct_actual": 0.0, "alloc_pct_actual": 0.0, "capped_by_max_alloc": False}

    risk_per_share = max(entry_price * 0.02, entry_price - stop_price)
    max_risk_dollars = portfolio_capital * risk_pct
    risk_based_shares = int(max_risk_dollars // risk_per_share)

    # 20% Capital Ceiling Safeguard
    max_capital_allocation = portfolio_capital * max_alloc_pct
    alloc_based_shares = int(max_capital_allocation // entry_price)

    final_shares = max(1, min(risk_based_shares, alloc_based_shares))
    capital_deployed = round(final_shares * entry_price, 2)
    actual_risk_dollars = round(final_shares * risk_per_share, 2)

    return {
        "shares": final_shares,
        "capital_deployed": capital_deployed,
        "actual_risk_dollars": actual_risk_dollars,
        "risk_pct_actual": round((actual_risk_dollars / max(1.0, portfolio_capital)) * 100, 2),
        "alloc_pct_actual": round((capital_deployed / max(1.0, portfolio_capital)) * 100, 2),
        "capped_by_max_alloc": bool(risk_based_shares > alloc_based_shares)
    }



def compute_alpha_composite_score(
    reclaim_days=0,
    rvol=1.0,
    price=100.0,
    ema50=100.0,
    sector=None,
    rr_ratio=2.5,
    top_quartile_sectors=None,
    return_breakdown=False,
    market_structure=None,
    macro_confluence=None,
    mom_spread=None,
    **kwargs
):
    """
    Computes dynamic Alpha Composite Score (0 - 100 points):
    Core Model = Freshness (30%) + RVOL (25%) + EMA50 Proximity (20%) + Sector RS (15%) + R:R (10%)
    Strengthened Model: Incorporates Dow Theory Market Structure (HH/HL confirmation vs LH/LL bear trap penalty),
    Macro 4-Index Confluence, and Sector Momentum Acceleration.

    1. Freshness of Reclaim (30 pts max):
       - Day 0 (reclaimed today): 30 pts — immediate breakout velocity
       - Day 1 (reclaimed yesterday): 25 pts — strong confirmation follow-through
       - Day 2: 15 pts
       - Day 3: 5 pts
       - Day > 3: 0 pts

    2. Relative Volume Surge (RVOL) (25 pts max):
       - RVOL >= 2.0x: 25 pts (strong institutional footprint)
       - RVOL >= 1.5x: 20 pts
       - RVOL >= 1.2x: 15 pts
       - RVOL >= 1.0x: 10 pts
       - RVOL < 1.0x: 5 pts

    3. Proximity to 50 EMA (20 pts max):
       - Distance <= 1.5%: 20 pts (tight support retest, minimal stop distance)
       - Distance <= 3.0%: 15 pts
       - Distance <= 5.0%: 10 pts
       - Distance > 5.0%: 5 pts

    4. Sector Momentum & Relative Strength (15 pts max):
       - Tickers belonging to top-quartile ETF sectors receive 15 pts
       - Otherwise: 5 pts

    5. Reward-to-Risk Ratio (10 pts max):
       - R:R >= 3.0: 10 pts
       - R:R >= 2.5: 8 pts
       - R:R < 2.5: 5 pts

    6. Market Structure Modifier (Optional enhancement when available):
       - Bullish HH/HL: +10 pts
       - Consolidation Base: +5 pts
       - Bearish LH/LL: -15 pts (severe penalty against bear trap bounces)
       - Confirmed Higher Low: +3 pts
       - Break of Structure (BOS): +2 pts
       - Tight Resistance Shelf (<2.5% runway): -5 pts

    7. Macro 4-Index Confluence (Optional enhancement when available):
       - 4/4 Confluence (SPY, QQQ, RSP, IWM all > EMA50): +5 pts
       - <= 1/4 Confluence: -5 pts

    8. Sector Acceleration (Optional enhancement when available):
       - 5d Mom > 20d Mom (accelerating inflows): +3 pts
    """
    if isinstance(reclaim_days, dict):
        d = reclaim_days
        rec_days = d.get("reclaim_days", 0)
        rvol_val = d.get("rvol", rvol)
        price_val = d.get("price", price)
        ema50_val = d.get("ema50", ema50)
        sec_val = d.get("sector", sector)
        if "rr_ratio" in d:
            rr_val = d.get("rr_ratio")
        elif "risk_per_share" in d and "tp1" in d and "price" in d:
            rr_val = (float(d["tp1"]) - float(d["price"])) / max(0.01, float(d["risk_per_share"]))
        else:
            rr_val = rr_ratio
        if market_structure is None:
            market_structure = d.get("market_structure")
        if macro_confluence is None:
            macro_confluence = d.get("macro_confluence")
        if mom_spread is None:
            mom_spread = d.get("mom_spread")
    else:
        rec_days = reclaim_days
        rvol_val = rvol
        price_val = price
        ema50_val = ema50
        sec_val = sector
        rr_val = rr_ratio

    # 1. Freshness of Reclaim (30 pts max)
    try:
        rec_days_int = int(rec_days) if rec_days is not None else 0
    except (ValueError, TypeError):
        rec_days_int = 0

    if rec_days_int == 0:
        freshness_pts = 30.0
    elif rec_days_int == 1:
        freshness_pts = 25.0
    elif rec_days_int == 2:
        freshness_pts = 15.0
    elif rec_days_int == 3:
        freshness_pts = 5.0
    else:
        freshness_pts = 0.0

    # 2. Relative Volume Surge (RVOL) (25 pts max)
    try:
        rvol_num = float(rvol_val) if rvol_val is not None else 1.0
    except (ValueError, TypeError):
        rvol_num = 1.0

    if rvol_num >= 2.0:
        rvol_pts = 25.0
    elif rvol_num >= 1.5:
        rvol_pts = 20.0
    elif rvol_num >= 1.2:
        rvol_pts = 15.0
    elif rvol_num >= 1.0:
        rvol_pts = 10.0
    else:
        rvol_pts = 5.0

    # 3. Proximity to 50 EMA (20 pts max)
    try:
        p_num = float(price_val) if price_val is not None else 100.0
        e_num = float(ema50_val) if ema50_val is not None else 100.0
        dist_pct = (abs(p_num - e_num) / max(0.01, e_num)) * 100.0
    except (ValueError, TypeError):
        dist_pct = 2.0

    if dist_pct <= 1.5:
        prox_pts = 20.0
    elif dist_pct <= 3.0:
        prox_pts = 15.0
    elif dist_pct <= 5.0:
        prox_pts = 10.0
    else:
        prox_pts = 5.0

    # 4. Sector Relative Strength (15 pts max)
    sector_pts = 5.0
    if sec_val and top_quartile_sectors:
        sec_upper = str(sec_val).strip().upper()
        for tq in top_quartile_sectors:
            tq_upper = str(tq).strip().upper()
            if tq_upper == sec_upper or tq_upper in sec_upper or sec_upper in tq_upper:
                sector_pts = 15.0
                break

    # 5. Reward-to-Risk (10 pts max)
    if isinstance(rr_val, str):
        try:
            if ":" in rr_val:
                rr_num = float(rr_val.split(":")[-1])
            else:
                rr_num = float(rr_val)
        except (ValueError, IndexError):
            rr_num = 2.5
    else:
        try:
            rr_num = float(rr_val) if rr_val is not None else 2.5
        except (ValueError, TypeError):
            rr_num = 2.5

    if rr_num >= 3.0:
        rr_pts = 10.0
    elif rr_num >= 2.5:
        rr_pts = 8.0
    else:
        rr_pts = 5.0

    base_score = freshness_pts + rvol_pts + prox_pts + sector_pts + rr_pts

    # 6. Market Structure Strengthening (HH/HL vs LH/LL)
    struct_pts = 0.0
    if market_structure is not None and isinstance(market_structure, dict):
        regime = market_structure.get("regime", "NEUTRAL")
        higher_low = market_structure.get("higher_low", False)
        bos = market_structure.get("break_of_structure", False)
        runway = market_structure.get("overhead_resistance_runway", 15.0)

        if regime == "BULLISH_HH_HL":
            struct_pts += 10.0
        elif regime == "CONSOLIDATION_BASE":
            struct_pts += 5.0
        elif regime == "BEARISH_LH_LL":
            struct_pts -= 15.0

        if higher_low and regime != "BEARISH_LH_LL":
            struct_pts += 3.0
        if bos:
            struct_pts += 2.0
        if runway < 2.5:
            struct_pts -= 5.0
        elif runway >= 6.0:
            struct_pts += 2.0

    # 7. Macro 4-Index Confluence
    macro_pts = 0.0
    if macro_confluence is not None:
        try:
            c_score = int(macro_confluence.get("score", 2)) if isinstance(macro_confluence, dict) else int(macro_confluence)
        except (ValueError, TypeError):
            c_score = 2
        if c_score == 4:
            macro_pts += 5.0
        elif c_score == 3:
            macro_pts += 2.0
        elif c_score <= 1:
            macro_pts -= 5.0

    # 8. Sector Acceleration
    accel_pts = 0.0
    if mom_spread is not None:
        try:
            m_val = float(mom_spread)
            if m_val > 0:
                accel_pts += 3.0
            elif m_val < -2.0:
                accel_pts -= 2.0
        except (ValueError, TypeError):
            pass

    # When no enhanced context is provided, preserve exact 100-pt base score
    if market_structure is None and macro_confluence is None and mom_spread is None:
        total = round(base_score, 1)
    else:
        total = max(5.0, min(100.0, round(base_score + struct_pts + macro_pts + accel_pts, 1)))

    breakdown = {
        "freshness": freshness_pts,
        "rvol": rvol_pts,
        "proximity": prox_pts,
        "sector_rs": sector_pts,
        "rr": rr_pts,
        "market_structure": struct_pts,
        "macro_confluence": macro_pts,
        "sector_accel": accel_pts,
        "total": total
    }
    if return_breakdown:
        return total, breakdown
    return total


def structure_stock_trade(ticker: str, sector: str, snapshot: dict, retrace_type: str, reclaim_days: int, regime: str = "MIXED", subsector: str = None, portfolio_capital: float = 50000.0) -> dict:
    """
    Structures a tactical equity swing trade setup (Common Shares):
    - Technical stop anchored below 50-day EMA or swing floor.
    - Minimum 1:2.5 Risk/Reward to TP1; TP2 at 1:3.5 R:R.
    - Two-tranche scale & trail mandate: Sell 50% at TP1, move stop to breakeven, trail remaining 50% on 50 EMA.
    """
    price = snapshot.get("price")
    ema50 = snapshot.get("ema50")
    if price is None or ema50 is None or np.isnan(price) or price <= 0:
        return None

    stop_price = round(min(ema50 * 0.98, price * 0.92), 2)
    risk_per_share = round(price - stop_price, 2)
    if risk_per_share <= 0:
        risk_per_share = round(price * 0.05, 2)
        stop_price = round(price - risk_per_share, 2)

    tp1 = round(price + (risk_per_share * 2.5), 2)
    tp2 = round(price + (risk_per_share * 3.5), 2)
    rr_ratio = f"1:{round((tp1 - price) / max(0.01, risk_per_share), 1)}"

    risk_budget_pct = 0.015 if regime == "RISK-ON" else (0.010 if regime == "MIXED" else 0.0075)
    sizing = calculate_stock_position_size(price, stop_price, portfolio_capital, risk_pct=risk_budget_pct, max_alloc_pct=0.20)
    shares = sizing["shares"]

    order_ticket = f"BUY {shares} SHARES @ ${price:.2f} LIMIT · STOP @ ${stop_price:.2f} · TP1: ${tp1:.2f} / TP2: ${tp2:.2f}"
    execution_guidance = "Scale 50% at TP1 (+2.5 R:R) · Move Stop to Breakeven · Trail Remainder on 50 EMA"

    ms_data = snapshot.get("market_structure")
    alpha_score, alpha_breakdown = compute_alpha_composite_score(
        reclaim_days=reclaim_days,
        rvol=snapshot.get("rvol", 1.0),
        price=price,
        ema50=ema50,
        sector=sector,
        rr_ratio=round((tp1 - price) / max(0.01, risk_per_share), 2),
        market_structure=ms_data,
        macro_confluence=snapshot.get("macro_confluence"),
        mom_spread=snapshot.get("mom_spread"),
        return_breakdown=True
    )

    return {
        "action": "BUY",
        "asset_class": "EQUITY",
        "ticker": ticker,
        "sector": sector,
        "subsector": subsector or "General",
        "price": price,
        "stop": stop_price,
        "tp1": tp1,
        "tp2": tp2,
        "rr_ratio": rr_ratio,
        "risk_per_share": risk_per_share,
        "retrace": retrace_type,
        "reclaim_days": reclaim_days,
        "shares": shares,
        "capital_deployed": sizing["capital_deployed"],
        "actual_risk_dollars": sizing["actual_risk_dollars"],
        "risk_pct_actual": sizing["risk_pct_actual"],
        "alloc_pct_actual": sizing["alloc_pct_actual"],
        "order_ticket": order_ticket,
        "execution_guidance": execution_guidance,
        "rvol": snapshot.get("rvol", 1.0),
        "weekly_stage": snapshot.get("weekly_stage", "STAGE 2 (Advancing)"),
        "structure": "Tactical Stock Swing (Common Shares)",
        "alpha_score": alpha_score,
        "alpha_score_breakdown": alpha_breakdown,
        "market_structure": ms_data or {"regime": "NEUTRAL", "badge": "⚪ NEUTRAL"},
        "structure_badge": (ms_data.get("badge") if ms_data else "⚪ NEUTRAL")
    }


def structure_core_stock_accumulation(ticker: str, sector: str, snapshot: dict, subsector: str = None, portfolio_capital: float = 50000.0) -> dict:
    """
    Structures long-term secular growth accumulation (Common Shares):
    - Requires full Stage 2 trend alignment (Price >= EMA50 >= SMA150 >= SMA200).
    - Macro Invalidation stop anchored 3% below the structural 200-day SMA.
    - Low beta drag (<= 2.2) and positive cash-flow profile.
    """
    price = snapshot.get("price")
    if price is None or np.isnan(price) or price <= 0:
        return None
    sma200 = snapshot.get("sma200", price * 0.85)
    macro_stop = round(sma200 * 0.97, 2)
    risk_per_share = round(price - macro_stop, 2)

    tp1 = round(price * 1.25, 2)
    tp2 = round(price * 1.50, 2)
    rr_ratio = f"1:{round((tp1 - price) / max(0.01, risk_per_share), 1)}"

    sizing = calculate_stock_position_size(price, macro_stop, portfolio_capital, risk_pct=0.02, max_alloc_pct=0.25)
    shares = sizing["shares"]

    order_ticket = f"BUY {shares} SHARES @ ${price:.2f} LIMIT · MACRO STOP @ ${macro_stop:.2f} (3% Below 200 SMA)"
    execution_guidance = "Secular Core Hold · Macro Trailing Stop on 200 SMA · Quarterly Rebalance"

    return {
        "action": "BUY",
        "asset_class": "CORE_EQUITY",
        "ticker": ticker,
        "sector": sector,
        "subsector": subsector or "General",
        "price": price,
        "macro_stop": macro_stop,
        "tp1": tp1,
        "tp2": tp2,
        "rr_ratio": rr_ratio,
        "shares": shares,
        "capital_deployed": sizing["capital_deployed"],
        "actual_risk_dollars": sizing["actual_risk_dollars"],
        "trend_stack": "Price >= EMA50 >= SMA200",
        "order_ticket": order_ticket,
        "execution_guidance": execution_guidance,
        "rvol": snapshot.get("rvol", 1.0),
        "weekly_stage": snapshot.get("weekly_stage", "STAGE 2 (Advancing)"),
        "structure": "Strategic Core Accumulation (Shares)"
    }


def audit_stock_positions(stock_trades: list, current_market_bars: dict, today_str: str, spy_ret: float = None) -> list:
    """
    Audits active equity positions against live market bars using Two-Tranche Scale & Trail:
    - Tranche 1: 50% shares exited at TP1 (+2.5 R:R). Stop moves to Breakeven.
    - Tranche 2: Remaining 50% trails along rising 50 EMA.
    - Realistic Gap Slippage: If Day Open < Stop, fills at Open price.
    - 5-Way Root-Cause Loss Attribution on stopped-out trades.
    """
    for t in stock_trades:
        if t["status"] in ["OPEN", "TP1_SCALED"]:
            if t.get("entry_date") and t["entry_date"] > today_str:
                continue

            ticker = t["ticker"]
            bar = current_market_bars.get(ticker)
            if not bar:
                continue

            close_p = float(bar.get("Close", t["entry_price"]))
            if np.isnan(close_p) or close_p <= 0:
                continue
            high_p = float(bar.get("High", close_p))
            if np.isnan(high_p): high_p = close_p
            low_p = float(bar.get("Low", close_p))
            if np.isnan(low_p): low_p = close_p
            open_p = float(bar.get("Open", close_p))
            if np.isnan(open_p): open_p = close_p
            ema50_p = float(bar.get("EMA50", close_p))
            if np.isnan(ema50_p): ema50_p = close_p

            t["max_price"] = max(t.get("max_price", t["entry_price"]), high_p)
            t["min_price"] = min(t.get("min_price", t["entry_price"]), low_p)
            t["current_price"] = close_p
            t["days_active"] = t.get("days_active", 0) + 1

            entry_p = t["entry_price"]
            stop_p = t["stop_price"]
            tp1 = t["tp1"]
            tp2 = t["tp2"]

            if t["status"] == "OPEN":
                if low_p <= stop_p:
                    fill_price = open_p if open_p < stop_p else stop_p
                    realized_pnl = round(((fill_price - entry_p) / entry_p) * 100, 2)
                    t["status"] = "STOPPED_OUT"
                    t["exit_price"] = fill_price
                    t["exit_date"] = today_str
                    t["pnl_pct"] = realized_pnl
                    t["exit_reason"] = f"Technical Stop Hit at ${fill_price:.2f} ({realized_pnl:+.2f}%)"
                    
                    if spy_ret is not None and spy_ret <= -0.012:
                        t["invalidation_driver"] = "MACRO CONTAGION"
                        t["driver_badge"] = "orange"
                    else:
                        t["invalidation_driver"] = "IDIOSYNCRATIC"
                        t["driver_badge"] = "rose"

                elif high_p >= tp1:
                    t["status"] = "TP1_SCALED"
                    t["tp1_hit_date"] = today_str
                    t["tp1_fill_price"] = tp1
                    t["stop_price"] = entry_p
                    t["invalidation_driver"] = "TP1 SCALED (+2.5 R:R)"
                    t["driver_badge"] = "emerald"
                    t["exit_reason"] = f"Scaled 50% at TP1 (${tp1:.2f}) · Stop Trailed to Breakeven (${entry_p:.2f})"
                    t["pnl_pct"] = round(((close_p - entry_p) / entry_p) * 100, 2)
                else:
                    t["pnl_pct"] = round(((close_p - entry_p) / entry_p) * 100, 2)
                    t["invalidation_driver"] = "ACTIVE"
                    t["driver_badge"] = "amber"

            elif t["status"] == "TP1_SCALED":
                if ema50_p > t["stop_price"]:
                    t["stop_price"] = round(ema50_p * 0.99, 2)

                if high_p >= tp2:
                    t["status"] = "TP2_HIT"
                    t["exit_price"] = tp2
                    t["exit_date"] = today_str
                    t["pnl_pct"] = round(((tp2 - entry_p) / entry_p) * 100, 2)
                    t["exit_reason"] = f"Final TP2 Target Achieved at ${tp2:.2f} (+3.5 R:R)"
                    t["invalidation_driver"] = "TARGET ACHIEVED"
                    t["driver_badge"] = "emerald"

                elif low_p <= t["stop_price"]:
                    fill_price = open_p if open_p < t["stop_price"] else t["stop_price"]
                    realized_pnl = round(((fill_price - entry_p) / entry_p) * 100, 2)
                    t["status"] = "CLOSED_TRAILING_PROFIT" if fill_price >= entry_p else "CLOSED_BREAKEVEN"
                    t["exit_price"] = fill_price
                    t["exit_date"] = today_str
                    t["pnl_pct"] = realized_pnl
                    t["exit_reason"] = f"Remaining 50% Closed on Trailing Stop at ${fill_price:.2f} ({realized_pnl:+.2f}%)"
                    t["invalidation_driver"] = "TRAILING STOP EXIT"
                    t["driver_badge"] = "emerald" if realized_pnl > 0 else "slate"
                else:
                    t["pnl_pct"] = round(((close_p - entry_p) / entry_p) * 100, 2)

    return stock_trades


def update_stock_trades_log(new_recommendations: list, current_market_bars: dict, today_str: str, spy_ret: float = None, log_path: str = None) -> dict:
    """
    Maintains persistent state in data/stock_trades_log.json:
    - Audits existing open stock trades.
    - Appends newly qualified stock setups.
    - Computes independent equity performance metrics: Win Rate %, Profit Factor, Realized Gains.
    """
    path = log_path or STOCK_LOG_PATH
    log_data = {"summary": {}, "trades": []}

    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                log_data = json.load(f)
        except Exception:
            pass

    trades = log_data.get("trades", [])
    existing_ids = set(t["id"] for t in trades)
    open_tickers = set(t["ticker"] for t in trades if t["status"] in ["OPEN", "TP1_SCALED"])

    trades = audit_stock_positions(trades, current_market_bars, today_str, spy_ret)
    active_open_count = len([t for t in trades if t["status"] in ["OPEN", "TP1_SCALED"]])

    for s_rec in new_recommendations:
        ticker = s_rec["ticker"]
        trade_id = f"STOCK_{today_str}_{ticker}"
        if trade_id not in existing_ids and ticker not in open_tickers:
            if active_open_count >= 7:
                break
            new_trade_entry = {
                "id": trade_id,
                "asset_class": "EQUITY",
                "entry_date": today_str,
                "ticker": ticker,
                "sector": s_rec["sector"],
                "subsector": s_rec.get("subsector", "General"),
                "entry_price": s_rec["price"],
                "stop_price": s_rec["stop"],
                "tp1": s_rec["tp1"],
                "tp2": s_rec["tp2"],
                "rr_ratio": s_rec["rr_ratio"],
                "shares": s_rec.get("shares", 50),
                "capital_deployed": s_rec.get("capital_deployed", 3000.0),
                "actual_risk_dollars": s_rec.get("actual_risk_dollars", 450.0),
                "status": "OPEN",
                "current_price": s_rec["price"],
                "max_price": s_rec["price"],
                "min_price": s_rec["price"],
                "days_active": 0,
                "pnl_pct": 0.0,
                "order_ticket": s_rec.get("order_ticket"),
                "execution_guidance": s_rec.get("execution_guidance"),
                "invalidation_driver": "ACTIVE",
                "driver_badge": "amber",
                "exit_date": None,
                "exit_price": None,
                "exit_reason": None
            }
            trades.append(new_trade_entry)
            existing_ids.add(trade_id)
            open_tickers.add(ticker)
            active_open_count += 1

    closed_trades = [t for t in trades if t["status"] in ["STOPPED_OUT", "TP2_HIT", "CLOSED_TRAILING_PROFIT", "CLOSED_BREAKEVEN"]]
    winners = [t for t in closed_trades if (t.get("pnl_pct") or 0) > 0]
    losers = [t for t in closed_trades if (t.get("pnl_pct") or 0) <= 0]

    gross_gains = sum([(t.get("capital_deployed", 1000) * ((t.get("pnl_pct") or 0) / 100)) for t in winners])
    gross_losses = abs(sum([(t.get("capital_deployed", 1000) * ((t.get("pnl_pct") or 0) / 100)) for t in losers]))

    win_rate = round((len(winners) / max(1, len(closed_trades))) * 100, 1)
    profit_factor = round(gross_gains / max(1.0, gross_losses), 2)
    avg_win = round(float(np.mean([t["pnl_pct"] for t in winners])), 2) if winners else 0.0
    avg_loss = round(float(np.mean([t["pnl_pct"] for t in losers])), 2) if losers else 0.0
    avg_holding = round(float(np.mean([t.get("days_active", 1) for t in closed_trades])), 1) if closed_trades else 0.0

    summary = {
        "total_recommendations": len(trades),
        "active_open": len([t for t in trades if t["status"] in ["OPEN", "TP1_SCALED"]]),
        "closed_trades": len(closed_trades),
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "gross_realized_gain": round(gross_gains - gross_losses, 2),
        "avg_winner_pct": avg_win,
        "avg_loser_pct": avg_loss,
        "avg_holding_days": avg_holding
    }

    log_data["summary"] = summary
    log_data["trades"] = trades

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(log_data, f, indent=2)

    return log_data
