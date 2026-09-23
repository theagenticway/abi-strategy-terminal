"""
Market data access layer: downloading OHLCV bars, extracting a single
ticker's DataFrame out of a combined/batch download, pruning old history
files, and multi-timeframe (1h/4h) confluence checks.

Extracted verbatim from the original scanner.py (no logic changes).
"""
import os
import datetime
import logging
import pandas as pd
import numpy as np

logger = logging.getLogger("market_data")

try:
    from engine.config import HISTORY_DIR, RETENTION_DAYS
except (ImportError, ModuleNotFoundError):
    from config import HISTORY_DIR, RETENTION_DAYS


def prune_old_history():
    """Flushes out historical snapshots and summary entries older than 365 days."""
    if not os.path.exists(HISTORY_DIR):
        return
    cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    pruned_count = 0
    for filename in os.listdir(HISTORY_DIR):
        if filename.endswith(".json"):
            file_date = filename.replace(".json", "")
            if file_date < cutoff_date:
                try:
                    os.remove(os.path.join(HISTORY_DIR, filename))
                    pruned_count += 1
                except Exception:
                    pass
    if pruned_count > 0:
        print(f"[*] Pruned {pruned_count} historical files older than {RETENTION_DAYS} days.")


def fetch_market_data(tickers, period="1y", interval="1d"):
    """Downloads data in batches of 75 tickers to avoid Yahoo rate limits."""
    try:
        import yfinance as yf
        cleaned_tickers = [t.replace(".", "-") for t in tickers]
        unique_cleaned = sorted(list(set(cleaned_tickers)))
        
        batch_size = 75
        combined_df = None
        print(f"[*] Downloading market data for {len(unique_cleaned)} tickers across {len(unique_cleaned)//batch_size + 1} batches ({period} period)...")

        for i in range(0, len(unique_cleaned), batch_size):
            batch = unique_cleaned[i:i + batch_size]
            try:
                batch_data = yf.download(batch, period=period, interval=interval, group_by="ticker", auto_adjust=False, threads=True, progress=False)
                if batch_data is not None and len(batch_data) > 0:
                    if combined_df is None:
                        combined_df = batch_data
                    else:
                        combined_df = pd.concat([combined_df, batch_data], axis=1)
            except Exception as batch_err:
                print(f"[!] Warning on batch {i//batch_size + 1}: {batch_err}")

        # Guard: Truncate any trailing phantom/unfinalized session row with >50% NaNs
        if combined_df is not None and len(combined_df) > 0:
            try:
                last_null_ratio = combined_df.iloc[-1].isna().sum() / max(1, len(combined_df.columns))
                if last_null_ratio > 0.50:
                    print(f"[*] Trimming unfinalized trailing market bar ({combined_df.index[-1]}) with {last_null_ratio*100:.1f}% NaNs")
                    combined_df = combined_df.iloc[:-1]
            except Exception as trim_err:
                print(f"[!] Warning checking trailing market bar: {trim_err}")

        return combined_df
    except Exception as e:
        print(f"[!] Warning: yfinance download failed: {e}")
        return None


def extract_ticker_df(raw_data, ticker):
    """Robust extractor: Handles MultiIndex with Level 0 = Ticker, Level 1 = Ticker, or single ticker."""
    if raw_data is None:
        return None
    clean_variants = [ticker, ticker.replace(".", "-"), ticker.replace("-", ".")]
    for t in clean_variants:
        if isinstance(raw_data.columns, pd.MultiIndex):
            if t in raw_data.columns.levels[0]:
                try:
                    df = raw_data[t].copy()
                    if "Close" in df.columns:
                        df = df.dropna(subset=["Close"])
                    if len(df) >= 30 and "Close" in df.columns and not np.isnan(float(df["Close"].iloc[-1])):
                        return df
                except Exception:
                    pass
            if len(raw_data.columns.levels) > 1 and t in raw_data.columns.levels[1]:
                try:
                    df = raw_data.xs(t, axis=1, level=1).copy()
                    if "Close" in df.columns:
                        df = df.dropna(subset=["Close"])
                    if len(df) >= 30 and "Close" in df.columns and not np.isnan(float(df["Close"].iloc[-1])):
                        return df
                except Exception:
                    pass
        else:
            if t in raw_data.columns:
                try:
                    df = raw_data[[t]].copy()
                    if "Close" in df.columns:
                        df = df.dropna(subset=["Close"])
                    else:
                        df = df.dropna()
                    if len(df) >= 30 and not np.isnan(float(df.iloc[-1, 0])):
                        return df
                except Exception:
                    pass
    return None


def verify_multi_timeframe_confluence(ticker: str, daily_ema50: float) -> dict:
    """
    Module 3: Checks 1-hour and 4-hour candles to confirm price closed above the daily EMA50.
    Filters morning spikes and false breakouts before daily close.
    """
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        df_1h = t.history(period="5d", interval="1h")
        if df_1h is None or len(df_1h) < 4:
            logger.warning("Insufficient 1H data for %s (len: %s), cannot confirm 4H confluence.", ticker, len(df_1h) if df_1h is not None else 0)
            return {
                "confirmed_4h": False,
                "badge": "🟡 UNVERIFIED (Data Unavailable)",
                "status": "PENDING_4H",
                "data_unavailable": True,
                "reason": "Insufficient 1H bar history"
            }

        df_4h = df_1h.resample("4h").agg({
            "Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"
        }).dropna()

        if len(df_4h) > 0:
            last_4h_close = float(df_4h["Close"].iloc[-1])
            is_above_ema50 = (last_4h_close >= daily_ema50)
            if is_above_ema50:
                return {"confirmed_4h": True, "badge": "🟢 4H CONFLUENCE OK", "status": "CONFIRMED_4H", "last_4h_close": last_4h_close}
            else:
                return {"confirmed_4h": False, "badge": "🟡 PENDING 4H CLOSE", "status": "PENDING_4H", "last_4h_close": last_4h_close}
        logger.warning("Empty 4H resampled data for %s, cannot confirm 4H confluence.", ticker)
        return {
            "confirmed_4h": False,
            "badge": "🟡 UNVERIFIED (Data Unavailable)",
            "status": "PENDING_4H",
            "data_unavailable": True,
            "reason": "Empty 4H bar history"
        }
    except Exception as ex:
        logger.warning("Error computing 4H confluence for %s: %s", ticker, ex)
        return {
            "confirmed_4h": False,
            "badge": "🟡 UNVERIFIED (Data Unavailable)",
            "status": "PENDING_4H",
            "data_unavailable": True,
            "reason": str(ex)
        }
