"""
ABI Strategy Scanner Engine — orchestrator / CLI entry point.

100% Dynamic Engine - All outputs, sub-sectors, and metrics are derived
natively from market feeds.

This file used to contain the entire ~2000-line engine. It has been split
into focused modules living alongside it:

  config.py         - shared constants and on-disk paths
  market_data.py     - downloading bars, extracting a ticker's DataFrame,
                        pruning old history, 1h/4h confluence checks
  benchmark.py        - macro regime detection + executive commentary
  universe_scan.py    - process_universe(): the full per-ticker/ETF scan
  trade_audit.py       - trade lifecycle auditing, scoring, eviction logic
  persistence.py       - ensure_ledgers_exist() / save_payloads()

This file only wires them together and exposes the CLI (`--backfill`).
"""
import os
import sys
import argparse

_engine_dir = os.path.dirname(os.path.abspath(__file__))
_repo_root = os.path.dirname(_engine_dir)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
if _engine_dir not in sys.path:
    sys.path.insert(0, _engine_dir)

from universe import SECTOR_ETFS, get_complete_taxonomy, get_full_universe
from indicators import compute_technical_snapshot
from patterns import detect_retrace_pattern, calculate_reclaim_velocity, structure_trade_signal, screen_strategic_leaps_candidate
import patterns

try:
    import stocks
except ModuleNotFoundError:
    import importlib.util
    _stocks_path = os.path.join(_engine_dir, "stocks.py")
    if os.path.exists(_stocks_path):
        _spec = importlib.util.spec_from_file_location("stocks", _stocks_path)
        stocks = importlib.util.module_from_spec(_spec)
        sys.modules["stocks"] = stocks
        _spec.loader.exec_module(stocks)

try:
    from engine.config import (
        DATA_DIR, HISTORY_DIR, RETENTION_DAYS,
        MAX_OPTIONS_SLOTS, MAX_OPTIONS_SPRINT_SLOTS, MAX_OPTIONS_ANCHOR_SLOTS,
        REPLACEMENT_HURDLE_DELTA, MIN_EVICTION_AGING_DAYS,
    )
except (ImportError, ModuleNotFoundError):
    from config import (
        DATA_DIR, HISTORY_DIR, RETENTION_DAYS,
        MAX_OPTIONS_SLOTS, MAX_OPTIONS_SPRINT_SLOTS, MAX_OPTIONS_ANCHOR_SLOTS,
        REPLACEMENT_HURDLE_DELTA, MIN_EVICTION_AGING_DAYS,
    )

try:
    from engine.market_data import (
        fetch_market_data, extract_ticker_df, verify_multi_timeframe_confluence, prune_old_history,
    )
except (ImportError, ModuleNotFoundError):
    from market_data import (
        fetch_market_data, extract_ticker_df, verify_multi_timeframe_confluence, prune_old_history,
    )

try:
    from engine.benchmark import calculate_benchmark_matrix, generate_market_commentary
except (ImportError, ModuleNotFoundError):
    from benchmark import calculate_benchmark_matrix, generate_market_commentary

try:
    from engine.universe_scan import process_universe, ETF_SECTOR_MAP
except (ImportError, ModuleNotFoundError):
    from universe_scan import process_universe, ETF_SECTOR_MAP

try:
    from engine.trade_audit import (
        determine_invalidation_driver, audit_and_update_trades,
        compute_alpha_composite_score, compute_options_alpha_score,
    )
except (ImportError, ModuleNotFoundError):
    from trade_audit import (
        determine_invalidation_driver, audit_and_update_trades,
        compute_alpha_composite_score, compute_options_alpha_score,
    )

try:
    from engine.persistence import ensure_ledgers_exist, save_payloads
except (ImportError, ModuleNotFoundError):
    from persistence import ensure_ledgers_exist, save_payloads

try:
    from engine import archive
except (ImportError, ModuleNotFoundError):
    import archive


def run_backfill(raw_data, days=30):
    """In-memory historical backfill across N trading days using sliced dates."""
    if raw_data is None:
        print("[!] Cannot backfill without market data.")
        return
    dates = raw_data.index
    if len(dates) == 0:
        print("[!] No dates found.")
        return
    target_dates = [d.strftime('%Y-%m-%d') for d in dates[-days:]]
    print(f"[*] Starting {len(target_dates)}-day historical backfill from {target_dates[0]} to {target_dates[-1]}...")
    for dt_str in target_dates:
        try:
            sliced_df = raw_data.loc[:dt_str]
            payload = process_universe(sliced_df, sample_date_str=dt_str)
            save_payloads(payload, raw_data=sliced_df)
            print(f"    -> Backfilled {dt_str} ({len(payload.get('tickers', []))} tickers)")
        except Exception as e:
            print(f"    [!] Error on {dt_str}: {e}")
    print(f"[✓] Backfilled {len(target_dates)} days successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ABI Strategy Scanner Engine")
    parser.add_argument("--backfill", type=int, default=0, help="Number of historical days to backfill")
    args = parser.parse_args()

    print("[*] Running ABI Strategy Scanner Engine...")
    ensure_ledgers_exist()
    universe = get_full_universe()

    if args.backfill > 0:
        fetch_period = "2y" if args.backfill >= 100 else "1y"
        print(f"[*] Backfill mode ({args.backfill} days). Pulling {fetch_period} data...")
        data = fetch_market_data(universe, period=fetch_period)
        run_backfill(data, days=args.backfill)
    else:
        data = fetch_market_data(universe, period="1y")
        payload = process_universe(data)
        save_payloads(payload, data)

    print("[✓] Execution complete.")
