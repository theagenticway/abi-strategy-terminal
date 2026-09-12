"""
Deterministic Indicator Engine for ABI Strategy Terminal.
Pure Pandas/NumPy implementation: EMA, SMA, RSI, MACD, ADR%, Beta, and Clearance Metrics.
"""

import numpy as np
import pandas as pd

def calculate_ema(series: pd.Series, span: int) -> pd.Series:
    """Calculates Exponential Moving Average with adjust=False matching TradingView."""
    return series.ewm(span=span, adjust=False).mean()

def calculate_sma(series: pd.Series, window: int) -> pd.Series:
    """Calculates Simple Moving Average."""
    return series.rolling(window=window).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculates RSI using Wilder's Smoothing (matches TradingView ta.rsi)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    # Wilder's exponential moving average (alpha = 1 / period)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Calculates MACD line, signal line, and histogram."""
    fast_ema = calculate_ema(series, fast)
    slow_ema = calculate_ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_adr_pct(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 20) -> float:
    """Calculates 20-day Average Daily Range percentage."""
    if len(close) < window:
        return 0.0
    safe_close = close.replace(0, np.nan)
    daily_range_pct = ((high - low) / safe_close) * 100
    res = float(daily_range_pct.dropna().tail(window).mean())
    return 0.0 if np.isnan(res) else res

def calculate_iv_rank(close: pd.Series, window: int = 252) -> float:
    """
    Computes 1-year (252-day) Implied/Historical Volatility Rank (0 to 100).
    Uses rolling 20-day annualized volatility ranked against its 52-week min/max.
    """
    if len(close) < 40:
        return 30.0
    returns = close.pct_change().dropna()
    rolling_vol = returns.rolling(window=20).std() * np.sqrt(252) * 100
    valid_vol = rolling_vol.dropna().tail(window)
    if len(valid_vol) < 20:
        return 30.0
    current_vol = float(valid_vol.iloc[-1])
    min_vol = float(valid_vol.min())
    max_vol = float(valid_vol.max())
    if max_vol == min_vol or np.isnan(max_vol) or np.isnan(min_vol):
        return 30.0
    iv_rank = ((current_vol - min_vol) / (max_vol - min_vol)) * 100
    if np.isnan(iv_rank):
        return 30.0
    return round(float(np.clip(iv_rank, 0.0, 100.0)), 1)

def calculate_beta(ticker_returns: pd.Series, spy_returns: pd.Series, window: int = 60) -> float:
    """Calculates Beta against SPY over specified window."""
    if spy_returns is None or ticker_returns is None:
        return 1.0
    combined = pd.concat([ticker_returns, spy_returns], axis=1).dropna().tail(window)
    if len(combined) < 20:
        return 1.0
    try:
        cov = np.cov(combined.iloc[:, 0], combined.iloc[:, 1])[0][1]
        var_spy = np.var(combined.iloc[:, 1])
        if var_spy == 0 or np.isnan(cov) or np.isnan(var_spy):
            return 1.0
        return round(float(cov / var_spy), 2)
    except Exception:
        return 1.0


def analyze_market_structure(high: pd.Series, low: pd.Series, close: pd.Series, lookback: int = 60) -> dict:
    """
    Analyzes Dow Theory market structure across rolling swing pivots:
    - Identifies recent swing highs and swing lows.
    - Classifies regime:
      * 'BULLISH_HH_HL': Higher Highs & Higher Lows (ideal for Longs & Bull Call Spreads).
      * 'BEARISH_LH_LL': Lower Highs & Lower Lows (ideal for Downside Hedges, dangerous for Longs).
      * 'CONSOLIDATION_BASE': Mixed / base building (Higher Low formed after a prior swing low).
    - Checks Structural Higher Low confirmation: Is current bounce floor higher than prior swing low?
    - Calculates Overhead Resistance Runway %: Distance to nearest overhead prior swing high.
    - Checks Break of Structure (BOS): Did recent price break above the previous swing high?
    """
    if high is None or low is None or close is None or len(close) < 15:
        return {
            "regime": "NEUTRAL",
            "badge": "⚪ NEUTRAL",
            "higher_high": False,
            "higher_low": True,
            "overhead_resistance_runway": 15.0,
            "break_of_structure": False,
            "prior_swing_high": 100.0,
            "prior_swing_low": 90.0,
            "structure_score": 12.0
        }

    h = high.tail(lookback).values if hasattr(high, "values") else np.array(high)
    l = low.tail(lookback).values if hasattr(low, "values") else np.array(low)
    c = close.tail(lookback).values if hasattr(close, "values") else np.array(close)
    n = len(c)
    current_price = float(c[-1])

    swing_highs = []
    swing_lows = []

    for i in range(2, n - 2):
        if h[i] >= h[i-1] and h[i] >= h[i-2] and h[i] >= h[i+1] and h[i] >= h[i+2]:
            swing_highs.append((i, float(h[i])))
        if l[i] <= l[i-1] and l[i] <= l[i-2] and l[i] <= l[i+1] and l[i] <= l[i+2]:
            swing_lows.append((i, float(l[i])))

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        mid = n // 2
        sh1 = float(np.max(h[:mid]))
        sh2 = float(np.max(h[mid:]))
        sl1 = float(np.min(l[:mid]))
        sl2 = float(np.min(l[mid:]))
    else:
        sh1 = swing_highs[-2][1]
        sh2 = swing_highs[-1][1]
        sl1 = swing_lows[-2][1]
        sl2 = swing_lows[-1][1]

    cur_support_floor = float(np.min(l[-5:])) if n >= 5 else current_price * 0.96

    has_higher_high = bool(sh2 >= sh1 * 0.995)
    has_higher_low = bool(cur_support_floor >= sl1 * 0.99)
    
    recent_max = float(np.max(c[-3:])) if n >= 3 else current_price
    break_of_structure = bool(recent_max >= sh2 * 0.998)

    overhead_targets = [sh for sh in [sh1, sh2] if sh > current_price]
    if overhead_targets:
        nearest_resistance = min(overhead_targets)
        overhead_runway = max(0.0, round(((nearest_resistance - current_price) / current_price) * 100, 2))
    else:
        overhead_runway = 999.0

    # Leading-edge analysis for Day 0 / Day 1 breakout velocity (Item 2E)
    recent_high = float(np.max(h[-2:])) if n >= 2 else current_price
    is_emerging_hh = bool(recent_high > sh2 * 1.002)
    is_emerging_hl = bool(cur_support_floor > sl2 * 0.998)

    if has_higher_high and has_higher_low:
        regime = "BULLISH_HH_HL"
        if break_of_structure or (n >= 4 and h[-1] >= h[-2]):
            badge = "🟢 HH/HL (CONFIRMED)"
            status = "CONFIRMED"
        else:
            badge = "🟢 HH/HL (EMERGING)"
            status = "EMERGING"
        structure_score = 25.0
    elif has_higher_low and not has_higher_high:
        regime = "CONSOLIDATION_BASE"
        if is_emerging_hh:
            badge = "🟡 BASE (EMERGING HH)"
            status = "EMERGING_HH"
            structure_score = 20.0
        else:
            badge = "🟡 BASE BUILDING"
            status = "BASE_BUILDING"
            structure_score = 18.0
    elif not has_higher_low and not has_higher_high:
        regime = "BEARISH_LH_LL"
        badge = "🔴 LH/LL BEARISH"
        status = "BEARISH_TRAP"
        structure_score = 5.0
    else:
        regime = "NEUTRAL"
        badge = "⚪ NEUTRAL"
        status = "NEUTRAL"
        structure_score = 12.0

    return {
        "regime": regime,
        "badge": badge,
        "higher_high": has_higher_high,
        "higher_low": has_higher_low,
        "overhead_resistance_runway": overhead_runway,
        "break_of_structure": break_of_structure,
        "prior_swing_high": round(sh2, 2),
        "prior_swing_low": round(sl1, 2),
        "structure_score": structure_score,
        "status": status,
        "is_emerging_hh": is_emerging_hh,
        "is_emerging_hl": is_emerging_hl
    }


def compute_technical_snapshot(df: pd.DataFrame, spy_returns: pd.Series = None) -> dict:
    """
    Computes complete technical telemetry from an OHLCV dataframe.
    Requires columns: Open, High, Low, Close, Volume.
    """
    if df is None:
        return None

    # Strip any trailing or interspersed rows missing Close to guarantee valid current price
    if "Close" in df.columns:
        df = df.dropna(subset=["Close"]).copy()
    if df is None or len(df) < 50:
        return None

    close = df['Close']
    high = df['High'] if 'High' in df.columns else close
    low = df['Low'] if 'Low' in df.columns else close
    
    current_price = float(close.iloc[-1])
    if np.isnan(current_price) or current_price <= 0:
        return None

    # Moving Averages
    ema10 = calculate_ema(close, 10)
    ema21 = calculate_ema(close, 21)
    ema50 = calculate_ema(close, 50)
    sma150 = calculate_sma(close, 150)
    ema200 = calculate_ema(close, 200)
    sma200 = calculate_sma(close, 200)
    
    # Oscillators
    rsi = calculate_rsi(close, 14)
    macd_line, macd_signal, macd_hist = calculate_macd(close, 12, 26, 9)
    
    current_ema50 = float(ema50.iloc[-1]) if not np.isnan(ema50.iloc[-1]) else current_price
    current_sma150 = float(sma150.iloc[-1]) if not np.isnan(sma150.iloc[-1]) else current_ema50
    current_ema200 = float(ema200.iloc[-1]) if not np.isnan(ema200.iloc[-1]) else current_ema50
    
    # Item 2D: Distinguish stocks with < 200 trading days history vs genuine 200 SMA
    has_200sma = bool(len(close) >= 200 and not np.isnan(sma200.iloc[-1]))
    current_sma200 = float(sma200.iloc[-1]) if has_200sma else None
    
    # Percentages
    ema50_dist_pct = round(((current_price - current_ema50) / current_ema50) * 100, 2) if current_ema50 > 0 else 0.0
    sma150_dist_pct = round(((current_price - current_sma150) / current_sma150) * 100, 2) if current_sma150 > 0 else 0.0
    ema200_dist_pct = round(((current_price - current_ema200) / current_ema200) * 100, 2) if current_ema200 > 0 else 0.0
    sma200_dist_pct = round(((current_price - current_sma200) / current_sma200) * 100, 2) if (has_200sma and current_sma200 > 0) else None
    ema10_dist_pct = round(((current_price - float(ema10.iloc[-1])) / float(ema10.iloc[-1])) * 100, 2) if float(ema10.iloc[-1]) > 0 else 0.0
    ema21_dist_pct = round(((current_price - float(ema21.iloc[-1])) / float(ema21.iloc[-1])) * 100, 2) if float(ema21.iloc[-1]) > 0 else 0.0
    
    # Slopes & Momentum
    ema50_slope = round((float(ema50.iloc[-1]) - float(ema50.iloc[-5])) / float(ema50.iloc[-5]) * 100, 2) if len(ema50) >= 5 and float(ema50.iloc[-5]) > 0 else 0.0
    macd_crawling_up = bool(macd_hist.iloc[-1] > macd_hist.iloc[-2]) if len(macd_hist) >= 2 else False
    macd_hook_ok = macd_crawling_up
    rsi_val = round(float(rsi.iloc[-1]), 2)
    rsi_above_50 = bool(rsi_val >= 50.0)
    rsi_floor_ok = bool(rsi_val >= 45.0)
    
    # Overhead Clearance to 200 MA (Item 2D guardrail)
    if has_200sma:
        overhead_runway_pct = max(0.0, -sma200_dist_pct) if current_price < current_sma200 else 999.0
        overhead_clearance_ok = bool(overhead_runway_pct >= 5.0)
        overhead_runway_label = "CLEAR (Above 200MA)" if overhead_runway_pct >= 900.0 else f"{overhead_runway_pct:.1f}% Runway"
    else:
        overhead_runway_pct = None
        overhead_clearance_ok = True # Does not disqualify, but transparently flagged
        overhead_runway_label = "N/A (<200d History)" 
    
    # ADR% and Beta
    adr_pct = round(calculate_adr_pct(high, low, close, 20), 2)
    returns = close.pct_change()
    beta = calculate_beta(returns, spy_returns) if spy_returns is not None else 1.0
    
    # IV Rank (Volatility Rank 0-100)
    iv_rank = calculate_iv_rank(close)
    if iv_rank < 35:
        iv_status = "LOW (Cheap Vol · Debit Favorable)"
        iv_badge = "emerald"
    elif iv_rank > 65:
        iv_status = "HIGH (Elevated Vol · Credit Favorable)"
        iv_badge = "amber"
    else:
        iv_status = "MODERATE"
        iv_badge = "slate"

    # Relative Volume (RVOL vs. 20-day average)
    rvol = 1.0
    if 'Volume' in df.columns and len(df['Volume']) >= 20:
        vol_s = df['Volume'].astype(float)
        vol_avg = float(vol_s.tail(20).mean())
        if vol_avg > 0:
            rvol = round(float(vol_s.iloc[-1] / vol_avg), 2)

    # Weekly Stage Analysis (30-week / 150-day structural slope)
    if len(close) >= 150:
        base_sma = max(0.001, float(sma150.iloc[-20]))
        sma150_slope = ((current_sma150 - float(sma150.iloc[-20])) / base_sma) * 100
        if current_price >= current_sma150 and sma150_slope >= 0:
            weekly_stage = "STAGE 2 (Advancing)"
        elif current_price < current_sma150 and sma150_slope < 0:
            weekly_stage = "STAGE 4 (Declining)"
        else:
            weekly_stage = "STAGE 1/3 (Consolidation)"
    else:
        weekly_stage = "STAGE 2 (Advancing)" if current_price >= current_ema50 else "STAGE 4 (Declining)"

    # Multi-day returns
    d1_return = round(float(returns.iloc[-1] * 100), 2) if len(returns) > 1 and not np.isnan(returns.iloc[-1]) else 0.0
    d5_return = round(float(((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]) * 100), 2) if len(close) >= 5 and float(close.iloc[-5]) > 0 else 0.0
    d20_return = round(float(((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]) * 100), 2) if len(close) >= 20 and float(close.iloc[-20]) > 0 else 0.0
    market_structure = analyze_market_structure(high, low, close)

    return {
        "price": round(current_price, 2),
        "ema10": round(float(ema10.iloc[-1]), 2),
        "ema21": round(float(ema21.iloc[-1]), 2),
        "ema50": round(current_ema50, 2),
        "sma150": round(current_sma150, 2),
        "ema200": round(current_ema200, 2),
        "sma200": round(current_sma200, 2) if current_sma200 is not None else None,
        "ema50_dist_pct": ema50_dist_pct,
        "sma150_dist_pct": sma150_dist_pct,
        "ema200_dist_pct": ema200_dist_pct,
        "sma200_dist_pct": sma200_dist_pct,
        "ema10_dist_pct": ema10_dist_pct,
        "ema21_dist_pct": ema21_dist_pct,
        "ema50_slope": ema50_slope,
        "rsi": rsi_val,
        "rsi_above_50": rsi_above_50,
        "rsi_floor_ok": rsi_floor_ok,
        "macd_hist": round(float(macd_hist.iloc[-1]), 4),
        "macd_crawling_up": macd_crawling_up,
        "macd_hook_ok": macd_hook_ok,
        "has_200sma": has_200sma,
        "overhead_runway_pct": (round(overhead_runway_pct, 2) if overhead_runway_pct is not None else None),
        "overhead_runway_label": overhead_runway_label,
        "overhead_clearance_ok": overhead_clearance_ok,
        "adr_pct": adr_pct,
        "beta": beta,
        "d1_return": d1_return,
        "d5_return": d5_return,
        "d20_return": d20_return,
        "rvol": rvol,
        "weekly_stage": weekly_stage,
        "iv_rank": iv_rank,
        "iv_status": iv_status,
        "iv_badge": iv_badge,
        "market_structure": market_structure,
        "raw_close": close,
        "raw_high": high,
        "raw_low": low,
        "raw_ema50": ema50,
        "raw_sma150": sma150
    }
