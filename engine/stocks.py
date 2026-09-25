"""
Deterministic Equity / Common Stock Strategy Engine for ABI Strategy Terminal.
Modular architecture: Sizing by Dollar-at-Risk ($100K baseline, scalable to $500K+),
3-Pronged Multi-Horizon Execution (High-Risk Sprint, Balanced Swing, Core Compounder),
Two-Tranche Scale & Trail exits, Stagnation Exits (10d / 14d), Gap-Down slippage modeling,
and persistent stock audit ledger tracking.
"""

import os
import json
import logging
import math

try:
    import numpy as np
    _isnan = np.isnan
except (ImportError, ModuleNotFoundError):
    np = None
    _isnan = math.isnan

logger = logging.getLogger(__name__)
try:
    from engine.indicators import compute_active_health_tier, get_regime_tier_capacities
except (ImportError, ModuleNotFoundError):
    try:
        from indicators import compute_active_health_tier, get_regime_tier_capacities
    except (ImportError, ModuleNotFoundError):
        def get_regime_tier_capacities(confluence_score: int = 4) -> dict:
            caps = {
                4: {"HIGH_RISK": 5, "BALANCED": 5, "CORE": 5, "regime": "RISK-ON (BROAD EXPANSION)"},
                3: {"HIGH_RISK": 3, "BALANCED": 5, "CORE": 5, "regime": "CAUTIOUS RISK-ON"},
                2: {"HIGH_RISK": 1, "BALANCED": 3, "CORE": 4, "regime": "MIXED / SECTOR ROTATION"},
                1: {"HIGH_RISK": 0, "BALANCED": 1, "CORE": 2, "regime": "DEFENSIVE / CHOP"},
                0: {"HIGH_RISK": 0, "BALANCED": 0, "CORE": 0, "regime": "SYSTEMIC LIQUIDATION"}
            }
            try:
                score = max(0, min(4, int(confluence_score if confluence_score is not None else 4)))
            except (ValueError, TypeError):
                score = 4
            return caps.get(score, caps[4])

        def compute_active_health_tier(
            status: str = "OPEN",
            stop_price: float = None,
            entry_price: float = None,
            current_alpha_score: float = 65.0,
            days_active: int = 1,
            strategy_prong: str = "BALANCED",
            prev_consecutive_low: int = 0,
            sector_weakness: bool = False,
            **kwargs
        ) -> dict:
            is_de_risked = (status in ["TP1_HIT", "TP1_SCALED"]) or (
                stop_price is not None and entry_price is not None and stop_price >= entry_price
            )
            if is_de_risked:
                return {
                    "tier": "TIER_A_HOUSE_MONEY",
                    "badge": "🔵 TIER A (HOUSE MONEY)",
                    "consecutive_low_score_days": 0,
                    "eviction_eligible": False
                }

            score_val = float(current_alpha_score) if current_alpha_score is not None else 65.0
            is_low = bool(score_val < 55.0 or sector_weakness)
            consecutive_low = (int(prev_consecutive_low or 0) + 1) if is_low else 0
            days_act = int(days_active or 1)

            if (consecutive_low >= 2 and days_act >= 5) or (score_val < 58.0 and days_act >= 18):
                return {
                    "tier": "TIER_D_EVICTION_CANDIDATE",
                    "badge": "🔴 TIER D (EVICTION CANDIDATE)",
                    "consecutive_low_score_days": consecutive_low,
                    "eviction_eligible": True
                }

            prong_upper = (strategy_prong or "BALANCED").upper()
            is_stagnant_time = (days_act >= 15 if "HIGH" in prong_upper else days_act >= 25)
            if is_stagnant_time or score_val < 62.0:
                return {
                    "tier": "TIER_C_STAGNANT",
                    "badge": "🟡 TIER C (STAGNANT)",
                    "consecutive_low_score_days": consecutive_low,
                    "eviction_eligible": False
                }

            return {
                "tier": "TIER_B_ON_TRACK",
                "badge": "🟢 TIER B (ON-TRACK)",
                "consecutive_low_score_days": consecutive_low,
                "eviction_eligible": False
            }
try:
    from engine.config import DEFAULT_PORTFOLIO_CAPITAL, DOLLAR_AT_RISK_PCT as DEFAULT_RISK_PCT, MAX_CAPITAL_ALLOCATION_PCT as DEFAULT_MAX_ALLOC_PCT
except (ImportError, ModuleNotFoundError):
    try:
        from config import DEFAULT_PORTFOLIO_CAPITAL, DOLLAR_AT_RISK_PCT as DEFAULT_RISK_PCT, MAX_CAPITAL_ALLOCATION_PCT as DEFAULT_MAX_ALLOC_PCT
    except (ImportError, ModuleNotFoundError):
        # config.py not on the path (e.g. stocks.py imported standalone outside the engine
        # package) - fall back to the same values so behavior is unchanged either way.
        DEFAULT_PORTFOLIO_CAPITAL = 100000.0
        DEFAULT_RISK_PCT = 0.0045
        DEFAULT_MAX_ALLOC_PCT = 0.06

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
STOCK_LOG_PATH = os.path.join(DATA_DIR, "stock_trades_log.json")

MAX_STOCK_PORTFOLIO_SLOTS = 18 # 16 to 21 active positions capacity
MAX_STOCK_SPRINT_SLOTS = 12    # Tactical Swings (High-Risk & Balanced)
MAX_STOCK_ANCHOR_SLOTS = 6     # Core Secular Compounders
REPLACEMENT_HURDLE_DELTA = 18.0 # Required alpha score advantage to trigger eviction
MIN_EVICTION_AGING_DAYS = 5     # Minimum sessions held before eviction eligibility


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
    if entry_price is None or _isnan(entry_price) or entry_price <= 0:
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
            runway = market_structure.get("overhead_resistance_runway", 0.0)  # unknown runway treated as no confirmed clearance, not an optimistic pass

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
                if isinstance(macro_confluence, dict):
                    c_score = int(macro_confluence.get("composite_score", macro_confluence.get("score", 2)))
                else:
                    c_score = int(macro_confluence)
            except (ValueError, TypeError) as ex:
                logger.warning(f"Could not parse macro_confluence '{macro_confluence}': {ex}")
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
            except (ValueError, TypeError) as ex:
                logger.debug(f"Could not parse mom_spread '{mom_spread}': {ex}")

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

    # If price is below EMA50 floor, the reclaim structure is invalid/broken
    try:
        p_num = float(price_val) if price_val is not None else 100.0
        e_num = float(ema50_val) if ema50_val is not None else 100.0
        if p_num < e_num:
            rec_days_int = 999
    except (ValueError, TypeError) as ex:
        logger.debug(f"Could not compare price_val '{price_val}' to ema50_val '{ema50_val}': {ex}")

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
    if market_structure is not None:
        if isinstance(market_structure, dict):
            regime = market_structure.get("regime", "NEUTRAL")
            runway = market_structure.get("overhead_resistance_runway", 0.0)  # unknown runway treated as no confirmed clearance, not an optimistic pass
        else:
            regime = str(market_structure).strip().upper()
            runway = 15.0
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
    if price is None or ema50 is None or _isnan(price) or price <= 0:
        return None

    # Anchor stop tightly: maximum 8.0% loss from entry to prevent runaway drawdowns
    stop_price = round(max(ema50 * 0.985, price * 0.92), 2)
    risk_per_share = round(price - stop_price, 2)
    if risk_per_share <= 0:
        risk_per_share = round(price * 0.04, 2)
        stop_price = round(price - risk_per_share, 2)

    # Velocity Harvest Target Geometry: TP0.5 at +1.0R (Scale 50%), TP1 at +2.2R, TP2 at +3.5R
    tp0_5 = round(price + (risk_per_share * 1.0), 2)
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
        "tp0_5": tp0_5,
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
    if price is None or ema50 is None or _isnan(price) or price <= 0:
        return None

    # Anchor stop tightly: maximum 9.5% risk from entry
    stop_price = round(max(ema50 * 0.98, price * 0.905), 2)
    risk_per_share = round(price - stop_price, 2)
    if risk_per_share <= 0:
        risk_per_share = round(price * 0.05, 2)
        stop_price = round(price - risk_per_share, 2)

    # Balanced Swing Geometry: TP0.5 at +1.0R (Scale 50%), TP1 at +2.5R, TP2 at +3.5R
    tp0_5 = round(price + (risk_per_share * 1.0), 2)
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
        "tp0_5": tp0_5,
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
    if price is None or _isnan(price) or price <= 0:
        return None
    sma200 = snapshot.get("sma200")
    if sma200 is None or _isnan(sma200) or sma200 <= 0:
        # This strategy requires genuine SMA200 confirmation (full Stage 2 trend
        # alignment) and anchors the macro stop 3% below it. Synthesizing a fake SMA200
        # (e.g. price*0.85) when unavailable (e.g. <200 days of history) would fabricate
        # both the stop-loss level and position sizing for a "CORE" long-term hold.
        print(f"[!] {ticker}: no 200-day SMA available (insufficient history); excluding from Core Accumulation rather than synthesizing a fake structural stop.")
        return None
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
        "ema50": snapshot.get("ema50", price),
        "reclaim_days": 0,  # Buy-and-hold core compounders don't track a reclaim event
        "market_structure": snapshot.get("market_structure"),
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
        # alpha_score is deliberately NOT set here - snapshot never carries a real
        # "alpha_score"/"alpha_composite_score" field, so this used to silently fall back
        # to a hardcoded 75.0 for every single core stock candidate, identically. It's
        # computed for real in process_universe() once sector/macro context
        # (top_quartile_sectors, macro_confluence, sector_mom_map) is available.
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
            if _isnan(close_p) or close_p <= 0:
                continue
            high_p = float(bar.get("High", close_p))
            if _isnan(high_p): high_p = close_p
            low_p = float(bar.get("Low", close_p))
            if _isnan(low_p): low_p = close_p
            open_p = float(bar.get("Open", close_p))
            if _isnan(open_p): open_p = close_p
            ema50_p = float(bar.get("EMA50", close_p))
            if _isnan(ema50_p): ema50_p = close_p

            t["max_price"] = max(t.get("max_price", t["entry_price"]), high_p)
            t["min_price"] = min(t.get("min_price", t["entry_price"]), low_p)
            t["current_price"] = close_p
            t["days_active"] = t.get("days_active", 0) + 1

            entry_p = t["entry_price"]
            stop_p = t["stop_price"]
            tp1 = t.get("tp1", round(entry_p * 1.15, 2))
            tp2 = t.get("tp2", round(entry_p * 1.25, 2))
            prong = t.get("strategy_prong", "BALANCED")
            days_active = t.get("days_active", 1)
            risk_per_share = max(0.01, entry_p - stop_p)

            if t["status"] == "OPEN":
                # Check Stagnation Exits (Recycle Portfolio Heat)
                if prong == "HIGH_RISK" and days_active >= 10:
                    current_r = (close_p - entry_p) / risk_per_share
                    # If trade is healthy, trending above EMA50, and profitable, let it run!
                    is_healthy_runner = (close_p > entry_p and close_p >= ema50_p and current_r >= 0.5)
                    if is_healthy_runner and days_active < 25:
                        # Trail stop to breakeven to lock in house money, give it extended runway
                        t["stop_price"] = max(t["stop_price"], entry_p)
                    elif current_r < 1.0:
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
                    is_healthy_runner = (close_p > entry_p and close_p >= ema50_p)
                    if is_healthy_runner and days_active < 45:
                        # Trail stop to breakeven, allow extended 45-day trend compounding
                        t["stop_price"] = max(t["stop_price"], entry_p)
                    elif curr_gain < (0.50 * tp1_dist):
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
                            t["stop_price"] = max(t["stop_price"], entry_p)

                # Check Stop Loss (with hard stop capping maximum drawdown to 8.0-9.5%)
                hard_stop = round(entry_p * (0.92 if prong == "HIGH_RISK" else 0.905), 2)
                effective_stop = max(stop_p, hard_stop)
                if low_p <= effective_stop:
                    fill_price = open_p if open_p < effective_stop else effective_stop
                    if t.get("tp0_5_scaled"):
                        tp0_5_fill = float(t.get("tp0_5_fill_price", entry_p * 1.05))
                        pnl_tranche1 = ((tp0_5_fill - entry_p) / entry_p) * 100
                        pnl_tranche2 = ((fill_price - entry_p) / entry_p) * 100
                        blended_pnl = round((0.5 * pnl_tranche1) + (0.5 * pnl_tranche2), 2)
                        t["status"] = "CLOSED_TRAILING_PROFIT" if blended_pnl > 0.01 else "CLOSED_BREAKEVEN"
                        t["exit_price"] = fill_price
                        t["exit_date"] = today_str
                        t["pnl_pct"] = blended_pnl
                        t["exit_reason"] = f"Scaled 50% at TP0.5 (${tp0_5_fill:.2f}, +{pnl_tranche1:.1f}%) · Remainder Closed at ${fill_price:.2f} (Blended PnL: {blended_pnl:+.2f}%)"
                        t["invalidation_driver"] = "TRAILING STOP EXIT"
                        t["driver_badge"] = "emerald" if blended_pnl > 0 else "slate"
                    else:
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
                    continue

                elif high_p >= tp1:
                    t["status"] = "TP1_SCALED"
                    t["stop_price"] = max(t["stop_price"], entry_p)
                    t["tp1_hit_date"] = today_str
                    t["tp1_fill_price"] = tp1
                    t["invalidation_driver"] = "TP1 SCALED (+2.5 R:R)"
                    t["driver_badge"] = "emerald"
                    t["exit_reason"] = f"Scaled 50% at TP1 (${tp1:.2f}) · Stop Trailed to Breakeven (${entry_p:.2f})"
                    t["pnl_pct"] = round(((close_p - entry_p) / entry_p) * 100, 2)
                    continue

                elif t.get("tp0_5") and high_p >= t["tp0_5"] and not t.get("tp0_5_scaled"):
                    tp0_5_val = float(t["tp0_5"])
                    t["tp0_5_scaled"] = True
                    t["stop_price"] = max(t["stop_price"], entry_p)
                    t["tp0_5_hit_date"] = today_str
                    t["tp0_5_fill_price"] = tp0_5_val
                    t["invalidation_driver"] = "TP0.5 SCALED (+1.0 R:R)"
                    t["driver_badge"] = "emerald"
                    t["exit_reason"] = f"Scaled 50% at TP0.5 (${tp0_5_val:.2f}, +1.0R) · Stop Trailed to Breakeven (${entry_p:.2f})"
                    t["pnl_pct"] = round(((close_p - entry_p) / entry_p) * 100, 2)

                # Floating PnL update for active open position
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
                    tp1_fill = float(t.get("tp1_fill_price", tp1))
                    pnl_tranche1 = ((tp1_fill - entry_p) / entry_p) * 100
                    pnl_tranche2 = ((fill_price - entry_p) / entry_p) * 100
                    blended_pnl = round((0.5 * pnl_tranche1) + (0.5 * pnl_tranche2), 2)
                    t["status"] = "CLOSED_TRAILING_PROFIT" if blended_pnl > 0.01 else "CLOSED_BREAKEVEN"
                    t["exit_price"] = fill_price
                    t["exit_date"] = today_str
                    t["pnl_pct"] = blended_pnl
                    t["exit_reason"] = f"Scaled 50% at TP1 (${tp1_fill:.2f}, +{pnl_tranche1:.1f}%) · Remainder Closed at ${fill_price:.2f} (Blended PnL: {blended_pnl:+.2f}%)"
                    t["invalidation_driver"] = "TRAILING STOP EXIT"
                    t["driver_badge"] = "emerald" if blended_pnl > 0 else "slate"
                else:
                    t["pnl_pct"] = round(((close_p - entry_p) / entry_p) * 100, 2)

            # Continuous Daily Re-Scoring & Active Health Tier Telemetry
            if t["status"] in ["OPEN", "TP1_SCALED"]:
                reclaim_d = bar.get("reclaim_days", 1)
                rvol_v = float(bar.get("rvol", 1.0))
                ema50_v = float(bar.get("EMA50", close_p))
                m_struct = bar.get("market_structure", "BULLISH_HH_HL")
                beta_v = float(bar.get("beta", 1.0))
                adr_v = float(bar.get("adr_pct", 2.0))
                rsi_v = float(bar.get("rsi", 50.0))
                macd_h = float(bar.get("macd_hist", 0.0))
                macd_hk = bool(bar.get("macd_crawling_up", bar.get("macd_hook_ok", True)))
                sec_weak = bool(bar.get("sector_weakness", False))

                try:
                    cur_score, breakdown = compute_alpha_composite_score(
                        reclaim_days=reclaim_d,
                        rvol=rvol_v,
                        price=close_p,
                        ema50=ema50_v,
                        sector=t.get("sector"),
                        market_structure=m_struct,
                        beta=beta_v,
                        adr_pct=adr_v,
                        rsi=rsi_v,
                        macd_hist=macd_h,
                        macd_hook_ok=macd_hk,
                        strategy_prong=prong,
                        return_breakdown=True
                    )
                except Exception as ex:
                    logger.warning("Failed recalculating alpha score for position %s: %s", t.get("ticker"), ex)
                    cur_score = float(t.get("current_alpha_score", t.get("alpha_score", 0.0)))
                    breakdown = t.get("score_breakdown", {})

                t["current_alpha_score"] = round(float(cur_score), 1)
                t["score_breakdown"] = breakdown

                prev_consec = t.get("consecutive_low_score_days", 0)
                health = compute_active_health_tier(
                    status=t["status"],
                    stop_price=t.get("stop_price"),
                    entry_price=t.get("entry_price"),
                    current_alpha_score=cur_score,
                    days_active=t.get("days_active", 1),
                    strategy_prong=prong,
                    prev_consecutive_low=prev_consec,
                    sector_weakness=sec_weak
                )
                t["active_health_tier"] = health["tier"]
                t["health_badge"] = health["badge"]
                t["consecutive_low_score_days"] = health["consecutive_low_score_days"]
                t["eviction_eligible"] = health["eviction_eligible"]

    return stock_trades


def update_stock_trades_log(
    new_recommendations: list,
    current_market_bars: dict,
    today_str: str,
    spy_ret: float = None,
    log_path: str = None,
    max_active_positions: int = MAX_STOCK_PORTFOLIO_SLOTS,
    confluence_score: int = 4
) -> dict:
    """
    Maintains persistent state in data/stock_trades_log.json:
    - Audits existing open stock trades.
    - Appends newly qualified stock setups up to max_active_positions (16–21 slots).
    - Computes independent equity performance metrics: Win Rate %, Profit Factor, Realized Gains.
    """
    path = log_path or STOCK_LOG_PATH
    log_data = {"summary": {}, "trades": []}

    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            with open(path, "r") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict) and "trades" in loaded:
                    log_data = loaded
                else:
                    logger.error(f"Unexpected schema in stock trades log {path}: missing 'trades' key")
        except (json.JSONDecodeError, OSError) as ex:
            logger.error(f"Failed to read stock trades log from {path}: {ex}. Preserving path without overwriting with empty schema.")
            raise

    trades = log_data.get("trades", [])
    existing_ids = set(t["id"] for t in trades)
    open_tickers = set(t["ticker"] for t in trades if t["status"] in ["OPEN", "TP1_SCALED"])

    trades = audit_stock_positions(trades, current_market_bars, today_str, spy_ret)
    open_trades = [t for t in trades if t["status"] in ["OPEN", "TP1_SCALED"]]
    active_open_count = len(open_trades)

    for s_rec in new_recommendations:
        ticker = s_rec["ticker"]
        trade_id = f"STOCK_{today_str}_{ticker}"
        if trade_id not in existing_ids and ticker not in open_tickers:
            is_core = (s_rec.get("strategy_prong") == "CORE" or "CORE" in s_rec.get("prong_badge", ""))
            cand_book = "ANCHOR" if is_core else "SPRINT"
            sprint_open = [t for t in open_trades if t.get("strategy_prong") != "CORE"]
            anchor_open = [t for t in open_trades if t.get("strategy_prong") == "CORE"]
            total_open = len(open_trades)

            # Regime-Gated Sector Guard: In hostile or rotation regimes (confluence_score <= 2), block Tech/Growth common share swings
            cand_prong = s_rec.get("strategy_prong", "BALANCED")
            if confluence_score <= 2 and cand_prong in ["HIGH_RISK", "BALANCED"]:
                sec_upper = (s_rec.get("sector") or "").upper()
                if any(kw in sec_upper for kw in ["TECH", "SEMIS", "SOFTWARE"]):
                    continue  # Protect against Nasdaq/tech distribution contagion

            # Regime-Gated Tier Capacity Enforcement
            tier_caps = get_regime_tier_capacities(confluence_score)
            prong_open = [t for t in open_trades if t.get("strategy_prong") == cand_prong]
            tier_max = tier_caps.get(cand_prong, 5)
            if len(prong_open) >= tier_max:
                continue

            max_sprint = kwargs.get("max_sprint_slots", MAX_STOCK_SPRINT_SLOTS) if "kwargs" in locals() else MAX_STOCK_SPRINT_SLOTS
            max_anchor = kwargs.get("max_anchor_slots", MAX_STOCK_ANCHOR_SLOTS) if "kwargs" in locals() else MAX_STOCK_ANCHOR_SLOTS
            book_full = (len(sprint_open) >= max_sprint if cand_book == "SPRINT" else len(anchor_open) >= max_anchor)
            portfolio_full = (total_open >= max_active_positions or total_open >= max(1, int(max_active_positions * 0.85)))
            target_book_trades = sprint_open if cand_book == "SPRINT" else anchor_open
            has_eviction_eligible = any(
                t.get("eviction_eligible") is True and t.get("days_active", 0) >= MIN_EVICTION_AGING_DAYS
                for t in target_book_trades
            )

            # Active replacement triggers if book/portfolio is full OR if an incumbent is marked Tier D Eviction Eligible
            if book_full or portfolio_full or has_eviction_eligible:
                target_book_trades = sprint_open if cand_book == "SPRINT" else anchor_open
                eviction_pool = [
                    t for t in target_book_trades 
                    if t.get("eviction_eligible") is True and t.get("days_active", 0) >= MIN_EVICTION_AGING_DAYS
                ]
                if eviction_pool:
                    def _incumbent_score(x):
                        val = x.get("current_alpha_score", x.get("options_alpha_score", x.get("alpha_score")))
                        if val is None:
                            return 0.0
                        return float(val)

                    lowest_incumbent = min(eviction_pool, key=_incumbent_score)
                    incumbent_score = _incumbent_score(lowest_incumbent)
                    cand_score_raw = s_rec.get("alpha_score")
                    if cand_score_raw is None:
                        continue
                    cand_score = float(cand_score_raw)
                    score_delta = round(cand_score - incumbent_score, 1)

                    if score_delta >= REPLACEMENT_HURDLE_DELTA:
                        lowest_incumbent["status"] = "CLOSED_EVICTED"
                        lowest_incumbent["exit_date"] = today_str
                        curr_p = float(lowest_incumbent.get("current_price", lowest_incumbent["entry_price"]))
                        lowest_incumbent["exit_price"] = curr_p
                        ent_p = float(lowest_incumbent["entry_price"])
                        realized_pnl = round(((curr_p - ent_p) / ent_p) * 100, 2)
                        lowest_incumbent["pnl_pct"] = realized_pnl
                        lowest_incumbent["invalidation_driver"] = "RELATIVE_STRENGTH_EVICTION"
                        lowest_incumbent["driver_badge"] = "purple"
                        lowest_incumbent["exit_reason"] = f"Relative Strength Eviction (Score: {incumbent_score:.1f} vs Incoming {s_rec['ticker']}: {cand_score:.1f}, Δ: +{score_delta:+.1f} pts)"
                        
                        open_trades.remove(lowest_incumbent)
                        if lowest_incumbent["ticker"] in open_tickers:
                            open_tickers.remove(lowest_incumbent["ticker"])
                        if cand_book == "SPRINT":
                            sprint_open.remove(lowest_incumbent)
                        else:
                            anchor_open.remove(lowest_incumbent)
                        total_open = len(open_trades)
                        active_open_count = total_open
                        print(f"[!] Relative Strength Eviction: Replaced {lowest_incumbent['ticker']} (Score {incumbent_score:.1f}) with {s_rec['ticker']} (Score {cand_score:.1f}, Δ+{score_delta:.1f} pts)")
                    else:
                        continue
                else:
                    continue
            
            ent_price = float(s_rec["price"])
            # calculate_stock_position_size() always sets stop/shares/capital_deployed/
            # actual_risk_dollars on every candidate this pipeline structures - a missing
            # value means something upstream is broken, not a case to paper over with a
            # fixed -8% stop / 4500/price shares / derived-risk assumption.
            for _required_field in ("stop", "shares", "capital_deployed", "actual_risk_dollars"):
                if s_rec.get(_required_field) is None:
                    raise ValueError(
                        f"{ticker}: candidate is missing required position-sizing field '{_required_field}'; "
                        f"refusing to substitute a hardcoded default."
                    )
            st_price = float(s_rec["stop"])
            shs = int(s_rec["shares"])
            cap_dep = float(s_rec["capital_deployed"])
            act_risk = float(s_rec["actual_risk_dollars"])

            entry_alpha_score = s_rec.get("alpha_score")
            if entry_alpha_score is None:
                print(f"[!] {ticker}: no computed alpha score at entry; recording 0 rather than assuming a passing score.")
                entry_alpha_score = 0.0

            new_trade_entry = {
                "id": trade_id,
                "asset_class": s_rec.get("asset_class", "EQUITY"),
                "strategy_prong": s_rec.get("strategy_prong", "BALANCED"),
                "prong_badge": s_rec.get("prong_badge", "⚖️ BALANCED (SWING)"),
                "entry_date": today_str,
                "ticker": ticker,
                "sector": s_rec["sector"],
                "subsector": s_rec.get("subsector", "General"),
                "entry_price": ent_price,
                "stop_price": st_price,
                "tp0_5": s_rec.get("tp0_5", round(ent_price + max(0.01, ent_price - st_price) * 1.0, 2)),
                "tp1": s_rec.get("tp1", round(ent_price * 1.15, 2)),
                "tp2": s_rec.get("tp2", round(ent_price * 1.25, 2)),
                "rr_ratio": s_rec.get("rr_ratio", "1:2.5"),
                "shares": shs,
                "capital_deployed": cap_dep,
                "actual_risk_dollars": act_risk,
                "current_alpha_score": round(float(entry_alpha_score), 1),
                "score_breakdown": s_rec.get("alpha_score_breakdown", s_rec.get("score_breakdown", {})),
                "active_health_tier": "TIER_B_ON_TRACK",
                "health_badge": "🟢 TIER B (ON-TRACK)",
                "consecutive_low_score_days": 0,
                "eviction_eligible": False,
                "status": "OPEN",
                "current_price": ent_price,
                "max_price": ent_price,
                "min_price": ent_price,
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

    closed_trades = [t for t in trades if t["status"] in ["STOPPED_OUT", "TP2_HIT", "CLOSED_TRAILING_PROFIT", "CLOSED_BREAKEVEN", "STAGNATION_EXIT", "CLOSED_EVICTED"]]
    
    # Strict Breakeven Accounting
    breakevens = [t for t in closed_trades if t.get("status") == "CLOSED_BREAKEVEN" or abs(float(t.get("pnl_pct", 0.0) or 0.0)) <= 0.10]
    winners = [t for t in closed_trades if t not in breakevens and float(t.get("pnl_pct", 0.0) or 0.0) > 0.10]
    losers = [t for t in closed_trades if t not in breakevens and float(t.get("pnl_pct", 0.0) or 0.0) < -0.10]

    def _capital_deployed(t):
        val = t.get("capital_deployed")
        if val is None:
            print(f"[!] {t.get('ticker')}: closed trade has no recorded capital_deployed; excluding from gross gain/loss $ totals rather than estimating one from entry_price*shares.")
            return None
        return float(val)

    gross_gains = sum(cd * ((t.get("pnl_pct") or 0) / 100) for t, cd in ((t, _capital_deployed(t)) for t in winners) if cd is not None)
    gross_losses = abs(sum(cd * ((t.get("pnl_pct") or 0) / 100) for t, cd in ((t, _capital_deployed(t)) for t in losers) if cd is not None))

    win_rate = round((len(winners) / max(1, len(closed_trades))) * 100, 1)
    profit_factor = round(gross_gains / max(1.0, gross_losses), 2)
    avg_win = round(float(sum([t["pnl_pct"] for t in winners]) / len(winners)), 2) if winners else 0.0
    avg_loss = round(float(sum([t["pnl_pct"] for t in losers]) / len(losers)), 2) if losers else 0.0
    avg_holding = round(float(sum([t.get("days_active", 1) for t in closed_trades]) / len(closed_trades)), 1) if closed_trades else 0.0

    summary = {
        "total_recommendations": len(trades),
        "active_open": len([t for t in trades if t["status"] in ["OPEN", "TP1_SCALED"]]),
        "sprint_open": len([t for t in trades if t["status"] in ["OPEN", "TP1_SCALED"] and t.get("strategy_prong") != "CORE"]),
        "anchor_open": len([t for t in trades if t["status"] in ["OPEN", "TP1_SCALED"] and t.get("strategy_prong") == "CORE"]),
        "closed_trades": len(closed_trades),
        "breakeven_trades": len(breakevens),
        "evicted_trades": len([t for t in closed_trades if t.get("status") == "CLOSED_EVICTED"]),
        "win_rate_pct": win_rate,
        "decisive_win_rate_pct": round((len(winners) / max(1, len(winners) + len(losers))) * 100, 1) if (len(winners) + len(losers)) > 0 else 0.0,
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
