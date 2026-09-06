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
    daily_range_pct = ((high - low) / close) * 100
    return float(daily_range_pct.tail(window).mean())

def calculate_beta(ticker_returns: pd.Series, spy_returns: pd.Series, window: int = 60) -> float:
    """Calculates Beta against SPY over specified window."""
    combined = pd.concat([ticker_returns, spy_returns], axis=1).dropna().tail(window)
    if len(combined) < 20:
        return 1.0
    cov = np.cov(combined.iloc[:, 0], combined.iloc[:, 1])[0][1]
    var_spy = np.var(combined.iloc[:, 1])
    if var_spy == 0:
        return 1.0
    return round(float(cov / var_spy), 2)

def compute_technical_snapshot(df: pd.DataFrame, spy_returns: pd.Series = None) -> dict:
    """
    Computes complete technical telemetry from an OHLCV dataframe.
    Requires columns: Open, High, Low, Close, Volume.
    """
    if df is None or len(df) < 50:
        return None

    close = df['Close']
    high = df['High']
    low = df['Low']
    
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
    
    current_price = float(close.iloc[-1])
    current_ema50 = float(ema50.iloc[-1])
    current_sma150 = float(sma150.iloc[-1]) if not np.isnan(sma150.iloc[-1]) else current_ema50
    current_ema200 = float(ema200.iloc[-1]) if not np.isnan(ema200.iloc[-1]) else current_ema50
    current_sma200 = float(sma200.iloc[-1]) if not np.isnan(sma200.iloc[-1]) else current_ema50
    
    # Percentages
    ema50_dist_pct = round(((current_price - current_ema50) / current_ema50) * 100, 2)
    sma150_dist_pct = round(((current_price - current_sma150) / current_sma150) * 100, 2)
    ema200_dist_pct = round(((current_price - current_ema200) / current_ema200) * 100, 2)
    sma200_dist_pct = round(((current_price - current_sma200) / current_sma200) * 100, 2)
    ema10_dist_pct = round(((current_price - float(ema10.iloc[-1])) / float(ema10.iloc[-1])) * 100, 2)
    ema21_dist_pct = round(((current_price - float(ema21.iloc[-1])) / float(ema21.iloc[-1])) * 100, 2)
    
    # Slopes & Momentum
    ema50_slope = round((float(ema50.iloc[-1]) - float(ema50.iloc[-5])) / float(ema50.iloc[-5]) * 100, 2)
    macd_crawling_up = bool(macd_hist.iloc[-1] > macd_hist.iloc[-2])
    rsi_above_50 = bool(rsi.iloc[-1] >= 50.0)
    
    # Overhead Clearance to 200 MA (Mandatory Options Alpha Radar rule: 5-8% clearance runway)
    overhead_runway_pct = max(0.0, -sma200_dist_pct) if current_price < current_sma200 else 999.0
    overhead_clearance_ok = bool(overhead_runway_pct >= 5.0)  # Either >200 MA or at least 5% runway below it
    
    # ADR% and Beta
    adr_pct = round(calculate_adr_pct(high, low, close, 20), 2)
    returns = close.pct_change()
    beta = calculate_beta(returns, spy_returns) if spy_returns is not None else 1.0
    
    # Multi-day returns
    d1_return = round(float(returns.iloc[-1] * 100), 2) if len(returns) > 1 else 0.0
    d5_return = round(float(((close.iloc[-1] - close.iloc[-5]) / close.iloc[-5]) * 100), 2) if len(close) >= 5 else 0.0
    d20_return = round(float(((close.iloc[-1] - close.iloc[-20]) / close.iloc[-20]) * 100), 2) if len(close) >= 20 else 0.0

    return {
        "price": round(current_price, 2),
        "ema10": round(float(ema10.iloc[-1]), 2),
        "ema21": round(float(ema21.iloc[-1]), 2),
        "ema50": round(current_ema50, 2),
        "sma150": round(current_sma150, 2),
        "ema200": round(current_ema200, 2),
        "sma200": round(current_sma200, 2),
        "ema50_dist_pct": ema50_dist_pct,
        "sma150_dist_pct": sma150_dist_pct,
        "ema200_dist_pct": ema200_dist_pct,
        "sma200_dist_pct": sma200_dist_pct,
        "ema10_dist_pct": ema10_dist_pct,
        "ema21_dist_pct": ema21_dist_pct,
        "ema50_slope": ema50_slope,
        "rsi": round(float(rsi.iloc[-1]), 2),
        "rsi_above_50": rsi_above_50,
        "macd_hist": round(float(macd_hist.iloc[-1]), 4),
        "macd_crawling_up": macd_crawling_up,
        "overhead_runway_pct": round(overhead_runway_pct, 2),
        "overhead_clearance_ok": overhead_clearance_ok,
        "adr_pct": adr_pct,
        "beta": beta,
        "d1_return": d1_return,
        "d5_return": d5_return,
        "d20_return": d20_return,
        "raw_close": close,
        "raw_high": high,
        "raw_low": low,
        "raw_ema50": ema50,
        "raw_sma150": sma150
    }
