"""
Disk persistence layer: guarantees the trade ledgers exist, writes
latest.json / dated history snapshots / the rolling summary.json, prunes
old history, and triggers the trades-log and recommendations-archive
updates on every scan run.

Extracted verbatim from the original scanner.py (no logic changes).
"""
import os
import sys
import json
import datetime
import numpy as np

_this_dir = os.path.dirname(os.path.abspath(__file__))
if _this_dir not in sys.path:
    sys.path.append(_this_dir)

try:
    from engine.config import DATA_DIR, HISTORY_DIR, RETENTION_DAYS
except (ImportError, ModuleNotFoundError):
    from config import DATA_DIR, HISTORY_DIR, RETENTION_DAYS

try:
    from engine.market_data import extract_ticker_df, prune_old_history
except (ImportError, ModuleNotFoundError):
    from market_data import extract_ticker_df, prune_old_history

try:
    from engine.trade_audit import audit_and_update_trades
except (ImportError, ModuleNotFoundError):
    from trade_audit import audit_and_update_trades

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

try:
    from engine import archive
except (ImportError, ModuleNotFoundError):
    try:
        import archive
    except (ImportError, ModuleNotFoundError):
        import importlib.util
        _arch_file = os.path.join(_this_dir, "archive.py")
        if os.path.exists(_arch_file):
            _spec = importlib.util.spec_from_file_location("archive", _arch_file)
            archive = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(archive)
        else:
            archive = None


def ensure_ledgers_exist():
    """Guarantees that both trades_log.json and stock_trades_log.json exist on disk."""
    for fname in ["trades_log.json", "stock_trades_log.json"]:
        fpath = os.path.join(DATA_DIR, fname)
        if not os.path.exists(fpath):
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(fpath, "w") as f:
                json.dump({
                    "summary": {
                        "total_recommendations": 0,
                        "active_open": 0,
                        "closed_trades": 0,
                        "win_rate_pct": 0.0,
                        "profit_factor": 0.0,
                        "gross_realized_gain": 0.0,
                        "avg_winner_pct": 0.0,
                        "avg_loser_pct": 0.0,
                        "avg_holding_days": 0.0
                    },
                    "trades": []
                }, f, indent=2)
            print(f"[+] Auto-initialized missing ledger file: {fpath}")

    arch_path = os.path.join(DATA_DIR, "recommendations_archive.json")
    if not os.path.exists(arch_path):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(arch_path, "w") as f:
            json.dump([], f, indent=2)
        print(f"[+] Auto-initialized missing archive file: {arch_path}")


def save_payloads(payload: dict, raw_data=None):
    """Writes latest.json, updates summary.json, and prunes old files."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)
    
    ticker_count = len(payload.get("tickers", []))
    latest_path = os.path.join(DATA_DIR, "latest.json")
    
    if ticker_count == 0:
        print("[!] CIRCUIT BREAKER: Scan produced 0 tickers. Preserving existing latest.json.")
        if os.path.exists(latest_path):
            return

    date_str = payload["macro_breadth"]["date"]
    
    # Ensure both options and stock ledger files exist on disk
    ensure_ledgers_exist()

    # Audit and update options paper trades log (Spreads + LEAPS)
    try:
        combined_recs = payload.get("top_candidates", []) + payload.get("strategic_leaps", [])
        audit_and_update_trades(raw_data, combined_recs, date_str)
    except Exception as audit_err:
        print(f"[!] Warning updating trades log: {audit_err}")

    # Audit and update dedicated stock trades log (Equities)
    try:
        current_bars = {}
        for t_rec in payload.get("tickers", []):
            tick = t_rec.get("ticker")
            if not tick:
                continue
            df_t = extract_ticker_df(raw_data, tick) if raw_data is not None else None
            p = t_rec.get("price")
            gate_res = t_rec.get("gate_results", {}) or {}
            dow_ms = gate_res.get("dow_market_structure", {}).get("current", t_rec.get("market_structure", "NEUTRAL"))
            
            if df_t is not None and len(df_t) > 0:
                last_row = df_t.iloc[-1]
                current_bars[tick] = {
                    "High": float(last_row.get("High", p)),
                    "Low": float(last_row.get("Low", p)),
                    "Open": float(last_row.get("Open", p)),
                    "Close": float(last_row.get("Close", p)),
                    "EMA50": t_rec.get("ema50", p),
                    "rsi": t_rec.get("rsi", 50.0),
                    "macd_hist": t_rec.get("macd_hist", 0.0),
                    "macd_crawling_up": t_rec.get("macd_crawling_up", False),
                    "rvol": t_rec.get("rvol", 1.0),
                    "beta": t_rec.get("beta", 1.0),
                    "adr_pct": t_rec.get("adr_pct", 2.0),
                    "market_structure": dow_ms,
                    "reclaim_days": t_rec.get("reclaim_days", 1)
                }
            elif p is not None and not np.isnan(p) and p > 0:
                current_bars[tick] = {
                    "High": t_rec.get("High", p),
                    "Low": t_rec.get("Low", p),
                    "Open": t_rec.get("Open", p),
                    "Close": p,
                    "EMA50": t_rec.get("ema50", p),
                    "rsi": t_rec.get("rsi", 50.0),
                    "macd_hist": t_rec.get("macd_hist", 0.0),
                    "macd_crawling_up": t_rec.get("macd_crawling_up", False),
                    "rvol": t_rec.get("rvol", 1.0),
                    "beta": t_rec.get("beta", 1.0),
                    "adr_pct": t_rec.get("adr_pct", 2.0),
                    "market_structure": dow_ms,
                    "reclaim_days": t_rec.get("reclaim_days", 1)
                }
        spy_df = extract_ticker_df(raw_data, "SPY") if raw_data is not None else None
        spy_ret = float(spy_df["Close"].pct_change().iloc[-1]) if (spy_df is not None and len(spy_df) >= 2) else 0.0
        stock_recs = payload.get("stock_recommendations", []) + payload.get("core_stocks", [])
        stocks.update_stock_trades_log(stock_recs, current_bars, date_str, spy_ret)
        print(f"[+] Updated stock_trades_log.json ({len(stock_recs)} stock recommendations evaluated)")
    except Exception as s_log_err:
        print(f"[!] Warning updating stock trades log: {s_log_err}")
    
    with open(latest_path, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[+] Wrote {latest_path} ({ticker_count} tickers)")

    history_path = os.path.join(HISTORY_DIR, f"{date_str}.json")
    with open(history_path, "w") as f:
        json.dump(payload, f, indent=2)

    summary_path = os.path.join(DATA_DIR, "summary.json")
    summary_data = []
    if os.path.exists(summary_path):
        try:
            with open(summary_path, "r") as f:
                summary_data = json.load(f)
        except Exception:
            summary_data = []
            
    cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=RETENTION_DAYS)).strftime("%Y-%m-%d")
    summary_data = [item for item in summary_data if item.get("date") != date_str and item.get("date") >= cutoff_date]
    summary_data.append(payload["macro_breadth"])
    summary_data = sorted(summary_data, key=lambda x: x["date"], reverse=True)
    
    with open(summary_path, "w") as f:
        json.dump(summary_data, f, indent=2)
    prune_old_history()

    # Update 365-day rolling recommendations archive on every scan run
    try:
        archive.update_recommendations_archive(payload, date_str)
    except Exception as arch_err:
        print(f"[!] Warning updating recommendations archive: {arch_err}")
