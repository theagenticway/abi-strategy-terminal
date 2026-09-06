"""
Pattern Recognition & Reclaim Velocity Classifier for ABI Strategy Terminal.
Detects EMA50 Bounces, Double Bottoms (DB), Optimal Trade Entry (OTE),
computes Reclaim Velocity (D0-D2), and pre-structures Options Alpha setups.
"""

import numpy as np
import pandas as pd

def detect_retrace_pattern(close, high, low, ema50, sma150) -> tuple:
    """
    Classifies the dominant retracement archetype safely handling Series or float.
    """
    cur_close = float(close.iloc[-1] if hasattr(close, "iloc") else close)
    cur_low = float(low.iloc[-1] if hasattr(low, "iloc") else low)
    cur_ema50 = float(ema50.iloc[-1] if hasattr(ema50, "iloc") else ema50)
    cur_sma150 = float(sma150.iloc[-1] if hasattr(sma150, "iloc") else sma150)
    
    # 1. Check EMA50 Retrace
    if cur_ema50 > 0 and (abs(cur_close - cur_ema50) / cur_ema50 <= 0.025 or abs(cur_low - cur_ema50) / cur_ema50 <= 0.015):
        return "EMA50", cur_ema50
    
    # 2. Check Double Bottom (DB)
    if hasattr(low, "tail") and len(low) >= 20:
        recent_window = low.tail(20)
        swing_low_1 = recent_window.iloc[:-5].min()
        swing_low_2 = recent_window.iloc[-5:].min()
        if swing_low_1 > 0 and abs(swing_low_1 - swing_low_2) / swing_low_1 <= 0.018:
            return "DB", swing_low_2
    
    # 3. Check Optimal Trade Entry (OTE) Fib Retracement (0.618 - 0.786)
    if hasattr(high, "tail") and hasattr(low, "tail") and len(high) >= 30:
        swing_high = high.tail(30).max()
        swing_low = low.tail(30).min()
        impulse = swing_high - swing_low
        if impulse > 0:
            fib_618 = swing_high - (0.618 * impulse)
            fib_786 = swing_high - (0.786 * impulse)
            if (fib_786 <= cur_close <= fib_618) or (fib_786 <= cur_low <= fib_618):
                return "OTE", fib_618
            
    # 4. Check MA150
    if cur_sma150 > 0 and abs(cur_close - cur_sma150) / cur_sma150 <= 0.03:
        return "MA150", cur_sma150

    return "EMA50", cur_ema50

def calculate_reclaim_velocity(close: pd.Series, ema50: pd.Series) -> tuple:
    """
    Calculates velocity ("Sooner Metric"):
    Finds the number of trading days elapsed since price dipped below EMA50 and reclaimed it.
    """
    cur_close = float(close.iloc[-1] if hasattr(close, "iloc") else close)
    cur_ema50 = float(ema50.iloc[-1] if hasattr(ema50, "iloc") else ema50)
    
    if not hasattr(close, "values") or not hasattr(ema50, "values"):
        return 2, True, "BOUNCED"
        
    below_mask = (close < ema50).values
    cur_above = cur_close >= cur_ema50
    
    reclaim_days = 1
    found_dip = False
    for i in range(1, min(15, len(close))):
        if below_mask[-i]:
            found_dip = True
            reclaim_days = i
            break
            
    if not found_dip:
        reclaim_days = 2 if cur_above else 5

    bounce_state = "BOUNCED" if (cur_above and reclaim_days <= 3) else ("ABOVE" if cur_above else "BELOW")
    is_confirmed = bool(cur_above and reclaim_days <= 3)
    
    return reclaim_days, is_confirmed, bounce_state

def structure_trade_signal(ticker: str, sector: str, snapshot: dict, retrace_type: str, reclaim_days: int, regime: str) -> dict:
    """
    Constructs an asymmetric trade setup adhering strictly to Options Alpha Radar rules.
    """
    price = snapshot["price"]
    ema50 = snapshot["ema50"]
    
    stop_price = round(min(ema50 * 0.98, price * 0.92), 2)
    risk_per_share = round(price - stop_price, 2)
    
    if risk_per_share <= 0:
        risk_per_share = round(price * 0.05, 2)
        stop_price = round(price - risk_per_share, 2)
        
    tp1 = round(price + (risk_per_share * 2.5), 2)
    tp2 = round(price + (risk_per_share * 3.5), 2)
    rr_ratio = round((tp1 - price) / risk_per_share, 1)
    
    target_allocation = 1000.0
    shares = max(1, int(target_allocation / price))
    total_position_val = round(shares * price, 2)
    total_risk_val = round(shares * risk_per_share, 2)
    
    if reclaim_days <= 2 and snapshot.get("overhead_clearance_ok", True):
        structure = "Bull Call Spread (45-60 DTE)"
    else:
        structure = "LEAPS (0.70-0.80 Delta, 12-18 Mo)"
        
    return {
        "action": "BUY",
        "ticker": ticker,
        "sector": sector,
        "price": price,
        "shares": shares,
        "position_val": total_position_val,
        "stop": stop_price,
        "risk_val": total_risk_val,
        "tp1": tp1,
        "tp2": tp2,
        "rr_ratio": f"1:{rr_ratio}",
        "retrace": retrace_type,
        "beta": snapshot.get("beta", 1.0),
        "ema50_pct": snapshot.get("ema50_dist_pct", 0.0),
        "overhead_runway_pct": snapshot.get("overhead_runway_pct", 8.0),
        "overhead_clearance_ok": snapshot.get("overhead_clearance_ok", True),
        "reclaim_days": reclaim_days,
        "structure": structure,
        "regime": regime
    }
