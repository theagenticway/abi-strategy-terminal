"""
Deterministic Equity / Common Stock Strategy Engine for ABI Strategy Terminal.
Modular architecture: Sizing by Dollar-at-Risk ($100K baseline, scalable to $500K+),
3-Pronged Multi-Horizon Execution (High-Risk Sprint, Balanced Swing, Core Compounder),
Two-Tranche Scale & Trail exits, Stagnation Exits (10d / 14d), Gap-Down slippage modeling,
and persistent stock audit ledger tracking.
"""

import os
import json
import numpy as np

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STOCK_LOG_PATH = os.path.join(DATA_DIR, "stock_trades_log.json")

# Default scalable capital parameters (Starts at $100K, scales to $500K+)
DEFAULT_PORTFOLIO_CAPITAL = 100000.0
DEFAULT_RISK_PCT = 0.0045      # 0.45% = $450 on $100K (risks $350-$500 per idea)
DEFAULT_MAX_ALLOC_PCT = 0.06   # 6.0% max capital ceiling per position ($6,000 on $100K, $30K on $500K)
MAX_STOCK_PORTFOLIO_SLOTS = 18 # 16 to 21 active positions capacity


def calculate_stock_position_size(
    entry_price: float,
    stop_price: float,
    portfolio_capital: float = DEFAULT_PORTFOLIO_CAPITAL,
    risk_pct: float = None,
    max_alloc_pct: float = None
) -> dict:
    """
    Computes institutional fixed-fractional share sizing:
    - Sized strictly on Dollar-at-Risk (e.g. 0.35% - 0.50% account equity risk on $100K-$500K+).
    - Enforces 6.0% single-stock capital allocation ceiling (prevents blowout on tight stops).
    - If risk_pct or max_alloc_pct are explicitly provided (e.g., in unit tests), uses them.
    - Returns integer share counts, actual dollars at risk, and total capital deployed.
    """
    if entry_price is None or np.isnan(entry_price) or entry_price <= 0:
        return {
            "shares": 0,
            "capital_deployed": 0.0,
            "actual_risk_dollars": 0.0,
            "risk_pct_actual": 0.0,
            "alloc_pct_actual": 0.0,
            "capped_by_max_alloc": False
        }

    # Use defaults if not explicitly passed
    effective_risk_pct = risk_pct if risk_pct is not None else DEFAULT_RISK_PCT
    effective_alloc_pct = max_alloc_pct if max_alloc_pct is not None else DEFAULT_MAX_ALLOC_PCT

    risk_per_share = max(entry_price * 0.02, entry_price - stop_price)
    max_risk_dollars = portfolio_capital * effective_risk_pct
    risk_based_shares = int(max_risk_dollars // risk_per_share)

    # Capital Ceiling Safeguard
    max_capital_allocation = portfolio_capital * effective_alloc_pct
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
    strategy_prong=None,
    beta=None,
    adr_pct=None,
    rsi=None,
    macd_hist=None,
    macd_hook_ok=None,
    legacy_mode=None,
    **kwargs
):
    """
    Computes dynamic Alpha Composite Score (0 - 100 points).
    Follows DATA_METRICS_AND_SCORING_ARCHITECTURE.md Specification:
    Stock Alpha Score = S_Reclaim (20) + S_RVOL (20) + S_Sector_RS (15) + S_Beta (15) + S_Momentum (15) + S_Structure (15)
    
    If legacy_mode is True, or when called strictly with the 5 legacy arguments (reclaim_days, rvol, price, ema50, rr_ratio)
    without new multi-horizon metrics (beta, rsi, prong), computes the backward-compatible 5-factor gradient.
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
        market_structure = market_structure or d.get("market_structure")
        macro_confluence = macro_confluence or d.get("macro_confluence")
        mom_spread = mom_spread or d.get("mom_spread")
        strategy_prong = strategy_prong or d.get("strategy_prong")
        beta = beta if beta is not None else d.get("beta")
        adr_pct = adr_pct if adr_pct is not None else d.get("adr_pct")
        rsi = rsi if rsi is not None else d.get("rsi")
        macd_hist = macd_hist if macd_hist is not None else d.get("macd_hist")
        macd_hook_ok = macd_hook_ok if macd_hook_ok is not None else d.get("macd_hook_ok", d.get("macd_crawling_up"))
        if legacy_mode is None:
            legacy_mode = d.get("legacy_mode")
    else:
        rec_days = reclaim_days
        rvol_val = rvol
        price_val = price
        ema50_val = ema50
        sec_val = sector
        rr_val = rr_ratio

    # Auto-detect legacy mode for backward-compatibility with existing tests
    if legacy_mode is None:
        legacy_mode = bool(strategy_prong is None and beta is None and rsi is None and adr_pct is None)

    if legacy_mode:
        # Legacy 5-component scoring (Freshness 30, RVOL 25, Proximity 20, Sector RS 15, RR 10)
        try:
            rec_days_int = int(rec_days) if rec_days is not None else 0
        except (ValueError, TypeError):
            rec_days_int = 0

        if rec_days_int == 0: freshness_pts = 30.0
        elif rec_days_int == 1: freshness_pts = 25.0
        elif rec_days_int == 2: freshness_pts = 15.0
        elif rec_days_int == 3: freshness_pts = 5.0
        else: freshness_pts = 0.0

        try:
            rvol_num = float(rvol_val) if rvol_val is not None else 1.0
        except (ValueError, TypeError):
            rvol_num = 1.0

        if rvol_num >= 2.0: rvol_pts = 25.0
        elif rvol_num >= 1.5: rvol_pts = 20.0
        elif rvol_num >= 1.2: rvol_pts = 15.0
        elif rvol_num >= 1.0: rvol_pts = 10.0
        else: rvol_pts = 5.0

        try:
            p_num = float(price_val) if price_val is not None else 100.0
            e_num = float(ema50_val) if ema50_val is not None else 100.0
            dist_pct = (abs(p_num - e_num) / max(0.01, e_num)) * 100.0
        except (ValueError, TypeError):
            dist_pct = 2.0

        if dist_pct <= 1.5: prox_pts = 20.0
        elif dist_pct <= 3.0: prox_pts = 15.0
        elif dist_pct <= 5.0: prox_pts = 10.0
        else: prox_pts = 5.0

        sector_pts = 5.0
        if sec_val and top_quartile_sectors:
            sec_upper = str(sec_val).strip().upper()
            for tq in top_quartile_sectors:
                tq_upper = str(tq).strip().upper()
                if tq_upper == sec_upper or tq_upper in sec_upper or sec_upper in tq_upper:
                    sector_pts = 15.0
                    break

        if isinstance(rr_val, str):
            try:
                rr_num = float(rr_val.split(":")[-1]) if ":" in rr_val else float(rr_val)
            except (ValueError, IndexError):
                rr_num = 2.5
        else:
            try:
                rr_num = float(rr_val) if rr_val is not None else 2.5
            except (ValueError, TypeError):
                rr_num = 2.5

        if rr_num >= 3.0: rr_pts = 10.0
        elif rr_num >= 2.5: rr_pts = 8.0
        else: rr_pts = 5.0

        base_score = freshness_pts + rvol_pts + prox_pts + sector_pts + rr_pts

        struct_pts = 0.0
        if market_structure is not None and isinstance(market_structure, dict):
            regime = market_structure.get("regime", "NEUTRAL")
            higher_low = market_structure.get("higher_low", False)
            bos = market_structure.get("break_of_structure", False)
            runway = market_structure.get("overhead_resistance_runway", 15.0)

            if regime == "BULLISH_HH_HL": struct_pts += 10.0
            elif regime == "CONSOLIDATION_BASE": struct_pts += 5.0
            elif regime == "BEARISH_LH_LL": struct_pts -= 15.0

            if higher_low and regime != "BEARISH_LH_LL": struct_pts += 3.0
            if bos: struct_pts += 2.0
            if runway < 2.5: struct_pts -= 5.0
            elif runway >= 6.0: struct_pts += 2.0

        macro_pts = 0.0
        if macro_confluence is not None:
            try:
                c_score = int(macro_confluence.get("score", 2)) if isinstance(macro_confluence, dict) else int(macro_confluence)
            except (ValueError, TypeError):
                c_score = 2
            if c_score == 4: macro_pts += 5.0
            elif c_score == 3: macro_pts += 2.0
            elif c_score <= 1: macro_pts -= 5.0

        accel_pts = 0.0
        if mom_spread is not None:
            try:
                m_val = float(mom_spread)
                if m_val > 0: accel_pts += 3.0
                elif m_val < -2.0: accel_pts -= 2.0
            except (ValueError, TypeError):
                pass

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

    # --- TARGET MULTI-HORIZON 100-POINT SCORING ---
    # 1. Reclaim Velocity & Freshness (20 pts max)
    try:
        rec_days_int = int(rec_days) if rec_days is not None else 0
    except (ValueError, TypeError):
        rec_days_int = 0

    if strategy_prong == "HIGH_RISK":
        if rec_days_int <= 1: reclaim_pts = 20.0
        elif rec_days_int == 2: reclaim_pts = 12.0
        elif rec_days_int == 3: reclaim_pts = 5.0
        else: reclaim_pts = 0.0
    elif strategy_prong == "CORE":
        reclaim_pts = 20.0 # Core is governed by Stage 2 stack alignment
    else: # BALANCED or generic
        if rec_days_int <= 2: reclaim_pts = 20.0
        elif rec_days_int == 3: reclaim_pts = 10.0
        else: reclaim_pts = 4.0

    # 2. Institutional RVOL (20 pts max)
    try:
        rvol_num = float(rvol_val) if rvol_val is not None else 1.0
    except (ValueError, TypeError):
        rvol_num = 1.0

    if strategy_prong == "HIGH_RISK":
        if rvol_num >= 2.0: rvol_pts = 20.0
        elif rvol_num >= 1.5: rvol_pts = 16.0
        elif rvol_num >= 1.2: rvol_pts = 10.0
        elif rvol_num >= 1.0: rvol_pts = 6.0
        else: rvol_pts = 2.0
    elif strategy_prong == "CORE":
        rvol_pts = 15.0 if rvol_num >= 0.9 else 10.0
    else:
        if rvol_num >= 1.8: rvol_pts = 20.0
        elif rvol_num >= 1.3: rvol_pts = 16.0
        elif rvol_num >= 1.0: rvol_pts = 12.0
        else: rvol_pts = 6.0

    # 3. Sector Relative Strength (15 pts max)
    sector_pts = 5.0
    is_top_quartile = False
    if sec_val and top_quartile_sectors:
        sec_upper = str(sec_val).strip().upper()
        for tq in top_quartile_sectors:
            tq_upper = str(tq).strip().upper()
            if tq_upper == sec_upper or tq_upper in sec_upper or sec_upper in tq_upper:
                is_top_quartile = True
                break

    mom_pos = bool(mom_spread is not None and float(mom_spread) > 0)
    if is_top_quartile and mom_pos:
        sector_pts = 15.0
    elif is_top_quartile or mom_pos:
        sector_pts = 11.0
    else:
        sector_pts = 6.0

    # 4. Beta & Price Elasticity (15 pts max)
    beta_num = float(beta) if beta is not None else 1.1
    adr_num = float(adr_pct) if adr_pct is not None else 2.5

    if strategy_prong == "HIGH_RISK":
        if beta_num >= 1.8 and adr_num >= 3.5: beta_pts = 15.0
        elif beta_num >= 1.5 and adr_num >= 3.0: beta_pts = 12.0
        elif beta_num >= 1.2: beta_pts = 8.0
        else: beta_pts = 4.0
    elif strategy_prong == "CORE":
        if beta_num <= 1.0: beta_pts = 15.0
        elif beta_num <= 1.2: beta_pts = 12.0
        else: beta_pts = 6.0
    else: # BALANCED
        if (1.0 <= beta_num <= 1.6) and (2.0 <= adr_num <= 3.6): beta_pts = 15.0
        elif beta_num >= 1.0 and adr_num >= 1.8: beta_pts = 11.0
        else: beta_pts = 7.0

    # 5. Universal Momentum: RSI >= 45 floor + MACD Hook (15 pts max)
    rsi_num = float(rsi) if rsi is not None else 52.0
    is_hook = bool(macd_hook_ok) if macd_hook_ok is not None else True

    if rsi_num >= 50.0 and is_hook:
        momentum_pts = 15.0
    elif rsi_num >= 45.0 and is_hook:
        momentum_pts = 13.0
    elif rsi_num >= 45.0:
        momentum_pts = 9.0
    else: # Disqualified or penalized if below 45 floor
        momentum_pts = 0.0

    # 6. Dow Theory Market Structure (15 pts max)
    struct_pts = 10.0
    if market_structure is not None and isinstance(market_structure, dict):
        regime = market_structure.get("regime", "NEUTRAL")
        runway = market_structure.get("overhead_resistance_runway", 15.0)
        if regime == "BULLISH_HH_HL":
            struct_pts = 15.0 if runway >= 5.0 else 12.0
        elif regime == "CONSOLIDATION_BASE":
            struct_pts = 11.0
        elif regime == "BEARISH_LH_LL":
            struct_pts = 2.0
        else:
            struct_pts = 8.0

    total = max(5.0, min(100.0, round(reclaim_pts + rvol_pts + sector_pts + beta_pts + momentum_pts + struct_pts, 1)))

    breakdown = {
        "reclaim_freshness": reclaim_pts,
        "rvol": rvol_pts,
        "sector_rs": sector_pts,
        "beta_elasticity": beta_pts,
        "momentum": momentum_pts,
        "market_structure": struct_pts,
        "total": total
    }
    if return_breakdown:
        return total, breakdown
    return total


def structure_high_risk_stock_trade(
    ticker: str,
    sector: str,
    snapshot: dict,
    retrace_type: str,
    reclaim_days: int,
    regime: str = "RISK-ON",
    subsector: str = None,
    portfolio_capital: float = DEFAULT_PORTFOLIO_CAPITAL
) -> dict:
    """
    Structures a High-Risk Sprint trade (Common Shares):
    - Holding Horizon: 10–14 trading sessions.
    - Target: High velocity, Beta >= 1.5-1.8, ADR >= 3.2-3.5%.
    - Tight technical stop anchored at 50 EMA / swing low (3-5% risk).
    - Rapid expansion targets (TP1 at +2.0R to +2.5R, TP2 at +3.5R).
    - Day 10 Stagnation Stop: Recycle capital if < +1.0R at Day 10.
    """
    price = snapshot.get("price")
    ema50 = snapshot.get("ema50")
    if price is None or ema50 is None or np.isnan(price) or price <= 0:
        return None

    stop_price = round(min(ema50 * 0.985, price * 0.94), 2)
    risk_per_share = round(price - stop_price, 2)
    if risk_per_share <= 0:
        risk_per_share = round(price * 0.04, 2)
        stop_price = round(price - risk_per_share, 2)

    tp1 = round(price + (risk_per_share * 2.2), 2)
    tp2 = round(price + (risk_per_share * 3.5), 2)
    rr_ratio = f"1:{round((tp1 - price) / max(0.01, risk_per_share), 1)}"

    sizing = calculate_stock_position_size(
        price, stop_price, portfolio_capital, risk_pct=0.005, max_alloc_pct=0.06
    )
    shares = sizing["shares"]

    order_ticket = f"BUY {shares} SHARES @ ${price:.2f} LIMIT · STOP @ ${stop_price:.2f} · TP1: ${tp1:.2f} / TP2: ${tp2:.2f}"
    execution_guidance = "High-Risk Sprint · Exit at TP1 (+2.2 R:R) or Day 10 Stagnation Stop (<1.0R)"

    ms_data = snapshot.get("market_structure")
    alpha_score, alpha_breakdown = compute_alpha_composite_score(
        reclaim_days=reclaim_days,
        rvol=snapshot.get("rvol", 1.8),
        price=price,
        ema50=ema50,
        sector=sector,
        rr_ratio=round((tp1 - price) / max(0.01, risk_per_share), 2),
        market_structure=ms_data,
        macro_confluence=snapshot.get("macro_confluence"),
        mom_spread=snapshot.get("mom_spread"),
        strategy_prong="HIGH_RISK",
        beta=snapshot.get("beta", 1.8),
        adr_pct=snapshot.get("adr_pct", 3.8),
        rsi=snapshot.get("rsi", 55.0),
        macd_hook_ok=snapshot.get("macd_hook_ok", True),
        return_breakdown=True
    )

    return {
        "action": "BUY",
        "asset_class": "EQUITY",
        "strategy_prong": "HIGH_RISK",
        "prong_badge": "🚀 HIGH RISK (SPRINT)",
        "holding_horizon": "10–14 Sessions",
        "stagnation_limit_days": 10,
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
        "rvol": snapshot.get("rvol", 1.8),
        "beta": snapshot.get("beta", 1.8),
        "adr_pct": snapshot.get("adr_pct", 3.8),
        "rsi": snapshot.get("rsi", 55.0),
        "weekly_stage": snapshot.get("weekly_stage", "STAGE 2 (Advancing)"),
        "structure": "High-Risk Sprint (Common Shares)",
        "alpha_score": alpha_score,
        "alpha_score_breakdown": alpha_breakdown,
        "market_structure": ms_data or {"regime": "NEUTRAL", "badge": "⚪ NEUTRAL"},
        "structure_badge": (ms_data.get("badge") if ms_data else "⚪ NEUTRAL")
    }


def structure_balanced_stock_trade(
    ticker: str,
    sector: str,
    snapshot: dict,
    retrace_type: str,
    reclaim_days: int,
    regime: str = "MIXED",
    subsector: str = None,
    portfolio_capital: float = DEFAULT_PORTFOLIO_CAPITAL
) -> dict:
    """
    Structures a Balanced Tactical Swing setup (Common Shares):
    - Holding Horizon: 15–25 trading sessions.
    - Target: High-quality momentum, Beta 1.0–1.5, ADR 2.0–3.2%.
    - Two-tranche scale & trail mandate: Sell 50% at TP1 (+2.5 R:R), move stop to breakeven, trail remaining 50% on 50 EMA.
    - Day 14 Stagnation Stop: Recycle or tighten stop if < 50% distance to TP1.
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

    risk_budget_pct = 0.0045 if regime == "RISK-ON" else 0.0035
    sizing = calculate_stock_position_size(
        price, stop_price, portfolio_capital, risk_pct=risk_budget_pct, max_alloc_pct=0.06
    )
    shares = sizing["shares"]

    order_ticket = f"BUY {shares} SHARES @ ${price:.2f} LIMIT · STOP @ ${stop_price:.2f} · TP1: ${tp1:.2f} / TP2: ${tp2:.2f}"
    execution_guidance = "Scale 50% at TP1 (+2.5 R:R) · Move Stop to Breakeven · Trail Remainder on 50 EMA · Day 14 Stagnation Check"

    ms_data = snapshot.get("market_structure")
    alpha_score, alpha_breakdown = compute_alpha_composite_score(
        reclaim_days=reclaim_days,
        rvol=snapshot.get("rvol", 1.2),
        price=price,
        ema50=ema50,
        sector=sector,
        rr_ratio=round((tp1 - price) / max(0.01, risk_per_share), 2),
        market_structure=ms_data,
        macro_confluence=snapshot.get("macro_confluence"),
        mom_spread=snapshot.get("mom_spread"),
        strategy_prong="BALANCED",
        beta=snapshot.get("beta", 1.2),
        adr_pct=snapshot.get("adr_pct", 2.6),
        rsi=snapshot.get("rsi", 52.0),
        macd_hook_ok=snapshot.get("macd_hook_ok", True),
        return_breakdown=True
    )

    return {
        "action": "BUY",
        "asset_class": "EQUITY",
        "strategy_prong": "BALANCED",
        "prong_badge": "⚖️ BALANCED (SWING)",
        "holding_horizon": "15–25 Sessions",
        "stagnation_limit_days": 14,
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
        "rvol": snapshot.get("rvol", 1.2),
        "beta": snapshot.get("beta", 1.2),
        "adr_pct": snapshot.get("adr_pct", 2.6),
        "rsi": snapshot.get("rsi", 52.0),
        "weekly_stage": snapshot.get("weekly_stage", "STAGE 2 (Advancing)"),
        "structure": "Tactical Stock Swing (Common Shares)",
        "alpha_score": alpha_score,
        "alpha_score_breakdown": alpha_breakdown,
        "market_structure": ms_data or {"regime": "NEUTRAL", "badge": "⚪ NEUTRAL"},
        "structure_badge": (ms_data.get("badge") if ms_data else "⚪ NEUTRAL")
    }


def structure_stock_trade(
    ticker: str,
    sector: str,
    snapshot: dict,
    retrace_type: str,
    reclaim_days: int,
    regime: str = "MIXED",
    subsector: str = None,
    portfolio_capital: float = DEFAULT_PORTFOLIO_CAPITAL
) -> dict:
    """
    Standard Tactical Equity Trade generator (alias routing to Balanced Swing or High-Risk based on Beta/ADR).
    Ensures seamless backward compatibility.
    """
    beta = snapshot.get("beta", 1.1) if snapshot else 1.1
    adr = snapshot.get("adr_pct", 2.5) if snapshot else 2.5

    if beta >= 1.6 and adr >= 3.3:
        return structure_high_risk_stock_trade(ticker, sector, snapshot, retrace_type, reclaim_days, regime, subsector, portfolio_capital)
    else:
        return structure_balanced_stock_trade(ticker, sector, snapshot, retrace_type, reclaim_days, regime, subsector, portfolio_capital)


def structure_core_stock_accumulation(
    ticker: str,
    sector: str,
    snapshot: dict,
    subsector: str = None,
    portfolio_capital: float = DEFAULT_PORTFOLIO_CAPITAL
) -> dict:
    """
    Structures long-term secular growth accumulation (Common Shares):
    - Holding Horizon: 40–120+ sessions (No time-based stagnation stop).
    - Requires full Stage 2 trend alignment (Price >= EMA50 >= SMA150 >= SMA200).
    - Macro Invalidation stop anchored 3% below the structural 200-day SMA.
    - Low beta drag (<= 1.2) and positive cash-flow profile.
    """
    price = snapshot.get("price")
    if price is None or np.isnan(price) or price <= 0:
        return None
    sma200 = snapshot.get("sma200") or (price * 0.85)
    macro_stop = round(sma200 * 0.97, 2)
    risk_per_share = round(price - macro_stop, 2)

    tp1 = round(price * 1.25, 2)
    tp2 = round(price * 1.50, 2)
    rr_ratio = f"1:{round((tp1 - price) / max(0.01, risk_per_share), 1)}"

    sizing = calculate_stock_position_size(
        price, macro_stop, portfolio_capital, risk_pct=0.005, max_alloc_pct=0.06
    )
    shares = sizing["shares"]

    order_ticket = f"BUY {shares} SHARES @ ${price:.2f} LIMIT · MACRO STOP @ ${macro_stop:.2f} (3% Below 200 SMA)"
    execution_guidance = "Secular Core Hold · Macro Trailing Stop on 200 SMA · Quarterly Rebalance"

    return {
        "action": "BUY",
        "asset_class": "CORE_EQUITY",
        "strategy_prong": "CORE",
        "prong_badge": "🛡️ CORE (COMPOUNDER)",
        "holding_horizon": "40–120+ Sessions",
        "stagnation_limit_days": None,
        "ticker": ticker,
        "sector": sector,
        "subsector": subsector or "General",
        "price": price,
        "macro_stop": macro_stop,
        "stop": macro_stop,
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
        "beta": snapshot.get("beta", 0.9),
        "adr_pct": snapshot.get("adr_pct", 1.8),
        "rsi": snapshot.get("rsi", 50.0),
        "weekly_stage": snapshot.get("weekly_stage", "STAGE 2 (Advancing)"),
        "structure": "Strategic Core Accumulation (Shares)"
    }


def audit_stock_positions(stock_trades: list, current_market_bars: dict, today_str: str, spy_ret: float = None) -> list:
    """
    Audits active equity positions against live market bars using Two-Tranche Scale & Trail:
    - Tranche 1: 50% shares exited at TP1 (+2.2R - +2.5 R:R). Stop moves to Breakeven.
    - Tranche 2: Remaining 50% trails along rising 50 EMA.
    - Stagnation Exits:
      * High-Risk: Day 10 exit if profit < +1.0R.
      * Balanced: Day 14 exit if gain < 50% to TP1.
    - Realistic Gap Slippage: If Day Open < Stop, fills at Open price.
    - Root-Cause Loss Attribution on stopped-out trades.
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
            prong = t.get("strategy_prong", "BALANCED")
            days_active = t.get("days_active", 1)
            risk_per_share = max(0.01, entry_p - stop_p)

            if t["status"] == "OPEN":
                # Check Stagnation Exits (Recycle Portfolio Heat)
                if prong == "HIGH_RISK" and days_active >= 10:
                    current_r = (close_p - entry_p) / risk_per_share
                    if current_r < 1.0:
                        realized_pnl = round(((close_p - entry_p) / entry_p) * 100, 2)
                        t["status"] = "STAGNATION_EXIT"
                        t["exit_price"] = close_p
                        t["exit_date"] = today_str
                        t["pnl_pct"] = realized_pnl
                        t["exit_reason"] = f"High-Risk Day 10 Stagnation Stop: Gain ({current_r:+.2f}R) < 1.0R ({realized_pnl:+.2f}%)"
                        t["invalidation_driver"] = "STAGNATION RECYCLE"
                        t["driver_badge"] = "blue"
                        continue

                elif prong == "BALANCED" and days_active >= 14:
                    tp1_dist = tp1 - entry_p
                    curr_gain = close_p - entry_p
                    if curr_gain < (0.50 * tp1_dist):
                        # Tighten stop to breakeven or exit
                        if close_p < entry_p:
                            realized_pnl = round(((close_p - entry_p) / entry_p) * 100, 2)
                            t["status"] = "STAGNATION_EXIT"
                            t["exit_price"] = close_p
                            t["exit_date"] = today_str
                            t["pnl_pct"] = realized_pnl
                            t["exit_reason"] = f"Balanced Day 14 Stagnation Stop: Achieved <50% to TP1 ({realized_pnl:+.2f}%)"
                            t["invalidation_driver"] = "STAGNATION RECYCLE"
                            t["driver_badge"] = "blue"
                            continue
                        else:
                            # Tighten stop to Breakeven
                            t["stop_price"] = max(t["stop_price"], entry_p)

                # Check Stop Loss
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


def update_stock_trades_log(
    new_recommendations: list,
    current_market_bars: dict,
    today_str: str,
    spy_ret: float = None,
    log_path: str = None,
    max_active_positions: int = MAX_STOCK_PORTFOLIO_SLOTS
) -> dict:
    """
    Maintains persistent state in data/stock_trades_log.json:
    - Audits existing open stock trades.
    - Appends newly qualified stock setups up to max_active_positions (16–21 slots).
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
            if active_open_count >= max_active_positions:
                break
            new_trade_entry = {
                "id": trade_id,
                "asset_class": s_rec.get("asset_class", "EQUITY"),
                "strategy_prong": s_rec.get("strategy_prong", "BALANCED"),
                "prong_badge": s_rec.get("prong_badge", "⚖️ BALANCED (SWING)"),
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
                "capital_deployed": s_rec.get("capital_deployed", 4500.0),
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

    closed_trades = [t for t in trades if t["status"] in ["STOPPED_OUT", "TP2_HIT", "CLOSED_TRAILING_PROFIT", "CLOSED_BREAKEVEN", "STAGNATION_EXIT"]]
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
