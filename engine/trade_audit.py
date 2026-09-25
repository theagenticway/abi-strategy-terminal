"""
Trade lifecycle auditing: marks open positions as stopped-out / TP-hit /
expired, diagnoses why a stop was hit (post-mortem attribution), re-scores
open positions daily, enforces sector/sub-sector/book concentration limits
and relative-strength eviction, and appends newly-qualified setups.

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
    from engine.config import (
        DATA_DIR,
        MAX_OPTIONS_SLOTS,
        MAX_OPTIONS_SPRINT_SLOTS,
        MAX_OPTIONS_ANCHOR_SLOTS,
        REPLACEMENT_HURDLE_DELTA,
        MIN_EVICTION_AGING_DAYS,
    )
except (ImportError, ModuleNotFoundError):
    from config import (
        DATA_DIR,
        MAX_OPTIONS_SLOTS,
        MAX_OPTIONS_SPRINT_SLOTS,
        MAX_OPTIONS_ANCHOR_SLOTS,
        REPLACEMENT_HURDLE_DELTA,
        MIN_EVICTION_AGING_DAYS,
    )

try:
    from engine.market_data import extract_ticker_df
except (ImportError, ModuleNotFoundError):
    from market_data import extract_ticker_df

try:
    from engine.benchmark import calculate_benchmark_matrix
except (ImportError, ModuleNotFoundError):
    from benchmark import calculate_benchmark_matrix

try:
    from engine.indicators import compute_active_health_tier, compute_technical_snapshot, get_regime_tier_capacities
    from engine.stocks import compute_alpha_composite_score as _stocks_alpha_score
    from engine.patterns import compute_options_alpha_score as _patterns_options_score
except (ImportError, ModuleNotFoundError):
    from indicators import compute_active_health_tier, compute_technical_snapshot, get_regime_tier_capacities
    from stocks import compute_alpha_composite_score as _stocks_alpha_score
    from patterns import compute_options_alpha_score as _patterns_options_score


def compute_alpha_composite_score(*args, **kwargs):
    """Re-export Alpha Composite Scorer from engine/stocks.py."""
    return _stocks_alpha_score(*args, **kwargs)


def compute_options_alpha_score(*args, **kwargs):
    """Re-export Options Alpha Scorer from engine/patterns.py."""
    return _patterns_options_score(*args, **kwargs)


def determine_invalidation_driver(ticker: str, sector: str, days_active: int, spy_ret=None, sector_ret=None, is_earnings_gap=False) -> dict:
    """
    Post-Mortem Attribution Engine: Diagnoses the root cause of an invalidation stop hit.
    Classifies failure across:
    1. Macro Contagion (Broad index selloff dragged equity below EMA50)
    2. Sector Rotation (Institutional outflows broke industry support)
    3. Earnings Volatility (Binary event gap-down)
    4. Stagnation (Momentum stalled past 7-day velocity window)
    5. Idiosyncratic Breakdown (Company-specific selling despite healthy sector)
    """
    if is_earnings_gap:
        return {
            "driver": "EARNINGS GAP",
            "badge": "rose",
            "note": "Binary earnings event gap-down breached technical stop"
        }
    if spy_ret is not None and spy_ret <= -0.012:
        return {
            "driver": "MACRO CONTAGION",
            "badge": "orange",
            "note": f"Broad index selloff (SPY {spy_ret*100:+.2f}%) dragged equity below EMA50"
        }
    if sector_ret is not None and sector_ret <= -0.012:
        return {
            "driver": "SECTOR ROTATION",
            "badge": "amber",
            "note": f"Sector outflows from {sector} ({sector_ret*100:+.2f}%) broke support"
        }
    if days_active >= 7:
        return {
            "driver": "STAGNATION EXIT",
            "badge": "slate",
            "note": "Momentum stalled past 7-day velocity window; stop triggered"
        }
    sec_str = f"despite healthy sector ({sector_ret*100:+.2f}%)" if sector_ret is not None else "failed support"
    return {
        "driver": "IDIOSYNCRATIC",
        "badge": "rose",
        "note": f"Company-specific breakdown; failed EMA50 retest {sec_str}"
    }


def audit_and_update_trades(raw_data, qualified_candidates, today_str, max_options_slots=None, max_sprint_slots=None, max_anchor_slots=None, confluence_score=None):
    """
    Automated Trade Lifecycle, Performance Auditor & Post-Mortem Loss Attribution Engine.
    Tracks all historical recommendations, audits active open positions against live market bars,
    diagnoses root-cause drivers on stop-outs, logs new setups, and computes cumulative metrics.
    """
    trades_log_path = os.path.join(DATA_DIR, "trades_log.json")
    trades_data = {"summary": {}, "trades": []}
    
    if os.path.exists(trades_log_path) and os.path.getsize(trades_log_path) > 0:
        try:
            with open(trades_log_path, "r") as f:
                trades_data = json.load(f)
        except Exception as ex:
            raise RuntimeError(f"Refusing to continue: could not read {trades_log_path}, proceeding would overwrite it with an empty ledger.") from ex
            
    trades = trades_data.get("trades", [])
    existing_ids = set(t["id"] for t in trades)
    active_open_tickers = set(t["ticker"] for t in trades if t["status"] == "OPEN")

    # Compute SPY return today for macro contagion check
    spy_ret = None
    spy_df = extract_ticker_df(raw_data, "SPY")
    if spy_df is not None and len(spy_df) >= 2 and "Close" in spy_df.columns:
        spy_ret = float(spy_df["Close"].pct_change().iloc[-1])

    # 1. Audit Active Open Positions against current day's price action (both OPEN and TP1_HIT trailing)
    for t in trades:
        if t["status"] in ["OPEN", "TP1_HIT"]:
            # CHRONOLOGICAL BACKFILL GUARD: A trade cannot be audited before its entry date!
            if t.get("entry_date") and t["entry_date"] > today_str:
                continue

            ticker = t["ticker"]
            ticker_df = extract_ticker_df(raw_data, ticker)
            if ticker_df is not None and len(ticker_df) > 0 and "Close" in ticker_df.columns:
                valid_df = ticker_df.dropna(subset=["Close"])
                if len(valid_df) == 0:
                    continue
                today_bar = valid_df.iloc[-1]
                close_val = float(today_bar["Close"])
                if np.isnan(close_val) or close_val <= 0:
                    continue
                high_p = float(today_bar.get("High", close_val))
                if np.isnan(high_p): high_p = close_val
                low_p = float(today_bar.get("Low", close_val))
                if np.isnan(low_p): low_p = close_val
                close_p = close_val
                
                t["max_price"] = max(t.get("max_price", t["entry_price"]), high_p)
                t["min_price"] = min(t.get("min_price", t["entry_price"]), low_p)
                t["current_price"] = close_p
                t["days_active"] = t.get("days_active", 0) + 1
                
                entry_p = t["entry_price"]
                stop_p = t["stop_price"]
                tp1 = t["tp1"]
                tp2 = t["tp2"]
                
                is_spread = "Spread" in t.get("structure", "")
                days_act = t.get("days_active", 1)

                # Check Invalidation / Trailing Breakeven Stop Hit
                if low_p <= stop_p:
                    is_trailed = (stop_p >= entry_p)
                    t["status"] = "CLOSED_BREAKEVEN" if is_trailed else "STOPPED_OUT"
                    t["exit_date"] = today_str
                    realized_pnl = round(((stop_p - entry_p) / entry_p) * 100, 2)
                    t["pnl_pct"] = realized_pnl
                    t["current_price"] = stop_p
                    
                    if is_trailed:
                        t["invalidation_driver"] = "BREAKEVEN EXIT"
                        t["driver_badge"] = "blue"
                        t["exit_reason"] = f"Trailed Breakeven Stop Triggered ({realized_pnl:+.2f}%)"
                    else:
                        attribution = determine_invalidation_driver(
                            ticker=t["ticker"],
                            sector=t.get("sector", "GENERAL"),
                            days_active=days_act,
                            spy_ret=spy_ret
                        )
                        t["invalidation_driver"] = attribution["driver"]
                        t["driver_badge"] = attribution["badge"]
                        t["exit_reason"] = f"Hit Invalidation Stop ({realized_pnl:+.2f}%) · {attribution['note']}"
                # Check Take Profit 2 Hit
                elif high_p >= tp2:
                    t["status"] = "TP2_HIT"
                    t["exit_date"] = today_str
                    realized_pnl = round(((tp2 - entry_p) / entry_p) * 100, 2)
                    t["pnl_pct"] = realized_pnl
                    t["exit_reason"] = f"Take Profit 2 Hit ({realized_pnl:+.2f}%)"
                    t["current_price"] = tp2
                    t["invalidation_driver"] = "TARGET ACHIEVED"
                    t["driver_badge"] = "emerald"
                # Check 45-Day Spread Expiration Exit (Recycles Portfolio Slots!)
                elif is_spread and days_act >= 45:
                    t["exit_date"] = today_str
                    if high_p >= tp1 or close_p >= entry_p:
                        t["status"] = "TP1_EXPIRED_WIN"
                        realized_pnl = max(t.get("pnl_pct", 0), round(((close_p - entry_p) / entry_p) * 100, 2))
                        t["pnl_pct"] = max(15.0, realized_pnl)
                        t["exit_reason"] = f"45-Day Spread Expiration Win (+{t['pnl_pct']:.2f}%)"
                        t["invalidation_driver"] = "EXPIRATION WIN"
                        t["driver_badge"] = "emerald"
                    else:
                        t["status"] = "STOPPED_OUT"
                        realized_pnl = round(((close_p - entry_p) / entry_p) * 100, 2)
                        t["pnl_pct"] = realized_pnl
                        t["exit_reason"] = f"45-Day Spread Expiration Loss ({realized_pnl:+.2f}%)"
                        t["invalidation_driver"] = "STAGNATION EXIT"
                        t["driver_badge"] = "slate"
                # Check Take Profit 1 Hit
                elif high_p >= tp1:
                    t["status"] = "TP1_HIT"
                    realized_pnl = round(((high_p - entry_p) / entry_p) * 100, 2)
                    t["pnl_pct"] = realized_pnl
                    t["exit_reason"] = f"Take Profit 1 Hit ({realized_pnl:+.2f}%) · Trailing Breakeven"
                    t["invalidation_driver"] = "TP1 REACHED"
                    t["driver_badge"] = "emerald"
                    # Trail stop to breakeven
                    t["stop_price"] = max(t["stop_price"], entry_p)
                else:
                    # Still open, update floating PnL
                    t["pnl_pct"] = round(((close_p - entry_p) / entry_p) * 100, 2)
                    t["invalidation_driver"] = "ACTIVE" if t["status"] == "OPEN" else "TP1 REACHED"
                    t["driver_badge"] = "amber" if t["status"] == "OPEN" else "emerald"

                # Continuous Daily Re-Scoring & Active Health Tier Telemetry for open/trailing trades
                if t["status"] in ["OPEN", "TP1_HIT"]:
                    # Starting point if re-scoring below can't run/complete: carry forward
                    # the position's own last known score rather than a fresh, unrelated
                    # constant (70.0) that has nothing to do with this specific trade.
                    opt_score = t.get("current_alpha_score", t.get("options_alpha_score", t.get("alpha_score")))
                    opt_score = float(opt_score) if opt_score is not None else 0.0
                    opt_breakdown = t.get("score_breakdown", {})
                    try:
                        spy_returns = spy_df["Close"].pct_change().dropna() if (spy_df is not None and len(spy_df) >= 2 and "Close" in spy_df.columns) else None
                        snapshot = compute_technical_snapshot(valid_df, spy_returns=spy_returns)
                        if snapshot is not None:
                            dir_alpha, dir_breakdown = compute_alpha_composite_score(
                                reclaim_days=snapshot.get("reclaim_days", 1),
                                rvol=snapshot.get("rvol", 1.0),
                                price=close_p,
                                ema50=snapshot.get("ema50", close_p),
                                sector=t.get("sector"),
                                market_structure=snapshot.get("market_structure", "NEUTRAL"),
                                beta=snapshot.get("beta", 1.0),
                                adr_pct=snapshot.get("adr_pct", 2.0),
                                rsi=snapshot.get("rsi", 50.0),
                                macd_hist=snapshot.get("macd_hist", 0.0),
                                macd_hook_ok=snapshot.get("macd_hook_ok", True),
                                strategy_prong=t.get("strategy_prong", "BALANCED"),
                                return_breakdown=True
                            )
                            # Liquidity/earnings data captured for real at trade entry (see
                            # new_trade construction above) - NOT re-guessed as "definitely
                            # liquid, definitely far from earnings" every single day a
                            # position stays open. Previously long_oi=1000/short_oi=800/
                            # bid_ask_spread_pct=0.04/days_to_earnings=90 were used
                            # unconditionally here, and since the ledger never actually
                            # stored these fields at entry, this fired on every re-score of
                            # every open position for its entire lifetime.
                            opt_score, opt_breakdown = compute_options_alpha_score(
                                directional_alpha=dir_alpha,
                                iv_rank=snapshot.get("iv_rank", t.get("iv_rank")),
                                long_oi=t.get("long_oi"),
                                short_oi=t.get("short_oi"),
                                bid_ask_spread_pct=t.get("bid_ask_spread_pct"),
                                overhead_runway_pct=snapshot.get("overhead_runway_pct", 999.0),
                                days_to_earnings=t.get("days_to_earnings"),
                                is_leaps=("LEAPS" in t.get("structure", "")),
                                strategy_prong=t.get("strategy_prong", "BALANCED"),
                                rsi=snapshot.get("rsi", 50.0),
                                macd_hook_ok=snapshot.get("macd_hook_ok", True),
                                return_breakdown=True
                            )
                    except Exception as rescale_ex:
                        print(f"[!] Daily re-score failed for {t.get('ticker')}, keeping last known score ({opt_score:.1f}): {rescale_ex}")

                    t["current_alpha_score"] = round(float(opt_score), 1)
                    t["score_breakdown"] = opt_breakdown

                    prev_consec = t.get("consecutive_low_score_days", 0)
                    health = compute_active_health_tier(
                        status=t["status"],
                        stop_price=t.get("stop_price"),
                        entry_price=t.get("entry_price"),
                        current_alpha_score=opt_score,
                        days_active=days_act,
                        strategy_prong=t.get("strategy_prong", "BALANCED"),
                        prev_consecutive_low=prev_consec,
                        sector_weakness=False
                    )
                    t["active_health_tier"] = health["tier"]
                    t["health_badge"] = health["badge"]
                    t["consecutive_low_score_days"] = health["consecutive_low_score_days"]
                    t["eviction_eligible"] = health["eviction_eligible"]

    # 2. Append Newly Qualified Recommendations (Spreads + LEAPS)
    # Enforces Module 1: Max 3 per Sub-Industry, Max 3 per Sector, Max 7 Portfolio Heat Cap
    open_trades = [t for t in trades if t.get("status") in ["OPEN", "TP1_HIT"]]
    
    for c in qualified_candidates:
        ticker = c["ticker"]
        trade_id = f"{today_str}_{ticker}"
        if trade_id not in existing_ids and ticker not in active_open_tickers:
            cand_sec = c.get("sector", "General")
            cand_sub = c.get("subsector", "General")
            
            # Dynamic Sector & Book Caps
            max_slots = max_options_slots or MAX_OPTIONS_SLOTS
            max_sprint = max_sprint_slots or MAX_OPTIONS_SPRINT_SLOTS
            max_anchor = max_anchor_slots or MAX_OPTIONS_ANCHOR_SLOTS
            max_sec = max(3, int(max_slots * 0.35))
            max_sub = max(2, int(max_slots * 0.20))

            sub_count = len([t for t in open_trades if t.get("subsector") == cand_sub])
            sec_count = len([t for t in open_trades if t.get("sector") == cand_sec])
            total_open = len(open_trades)

            # Anti-Chop Re-Entry Cooldown check (<5 sessions post stop-out or stagnation exit)
            is_cooldown = False
            for prev in trades:
                if prev.get("ticker") == ticker and prev.get("status") in ["STOPPED_OUT", "STAGNATION_EXIT"] and prev.get("exit_date"):
                    try:
                        exit_dt = datetime.datetime.strptime(prev["exit_date"], "%Y-%m-%d").date()
                        cur_dt = datetime.datetime.strptime(today_str, "%Y-%m-%d").date()
                        if 0 <= (cur_dt - exit_dt).days <= 4:
                            is_cooldown = True
                            break
                    except Exception as date_ex:
                        # A malformed date here previously meant the cooldown check for
                        # this record was silently skipped, which could let a ticker that
                        # should still be in its anti-chop cooldown re-enter early.
                        print(f"[!] Could not parse exit_date '{prev.get('exit_date')}' for {ticker} while checking anti-chop cooldown: {date_ex}")
            if is_cooldown:
                c["correlation_status"] = f"THROTTLED: Anti-Chop Cooldown (<5d: {ticker})"
                continue
            
            if sub_count >= max_sub:
                c["correlation_status"] = f"THROTTLED: Sub-Sector Max {max_sub} ({cand_sub})"
                continue
            if sec_count >= max_sec:
                c["correlation_status"] = f"THROTTLED: Sector Max {max_sec} ({cand_sec})"
                continue

            # Regime-Gated Tier Capacity Enforcement
            macro_conf = confluence_score
            if macro_conf is None:
                try:
                    bm = calculate_benchmark_matrix(raw_data)
                    macro_conf = bm.get("composite_score")
                    if macro_conf is None:
                        raise ValueError("calculate_benchmark_matrix returned no composite_score")
                except Exception as bm_ex:
                    # A benchmark-calculation failure means we have no visibility into
                    # current market regime - defaulting to 4 (the MOST bullish/permissive
                    # regime, "FULL_OFFENSE") maximized position capacity at exactly the
                    # moment conditions couldn't be verified. Assume the most conservative
                    # regime instead so a data outage tightens risk limits, not loosens them.
                    print(f"[!] Could not compute benchmark matrix for regime-gated tier capacity, assuming most conservative regime (0): {bm_ex}")
                    macro_conf = 0
            tier_caps = get_regime_tier_capacities(macro_conf)
            cand_prong = c.get("strategy_prong", "BALANCED")
            prong_open_count = len([t for t in open_trades if t.get("strategy_prong", "BALANCED") == cand_prong])
            tier_max = tier_caps.get(cand_prong, 5)
            if prong_open_count >= tier_max:
                c["correlation_status"] = f"THROTTLED: Regime-Gated Tier Cap {tier_max} ({cand_prong} under {tier_caps['regime']})"
                continue
            # Decoupled Book Management & Relative-Strength Eviction
            is_leaps = ("LEAPS" in c.get("structure", ""))
            cand_book = "ANCHOR" if is_leaps else "SPRINT"
            sprint_open = [t for t in open_trades if "LEAPS" not in t.get("structure", "")]
            anchor_open = [t for t in open_trades if "LEAPS" in t.get("structure", "")]
            
            book_full = (len(sprint_open) >= max_sprint if cand_book == "SPRINT" else len(anchor_open) >= max_anchor)
            portfolio_full = (total_open >= max_slots or total_open >= max(1, int(max_slots * 0.85)))

            if book_full or portfolio_full:
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
                    cand_score_raw = c.get("options_alpha_score", c.get("alpha_score"))
                    if cand_score_raw is None:
                        c["correlation_status"] = f"THROTTLED: Book Full ({cand_book}) - Candidate has no score"
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
                        lowest_incumbent["exit_reason"] = f"Relative Strength Eviction (Score: {incumbent_score:.1f} vs Incoming {c['ticker']}: {cand_score:.1f}, Δ: +{score_delta:+.1f} pts)"
                        
                        open_trades.remove(lowest_incumbent)
                        if lowest_incumbent["ticker"] in active_open_tickers:
                            active_open_tickers.remove(lowest_incumbent["ticker"])
                        if cand_book == "SPRINT":
                            sprint_open.remove(lowest_incumbent)
                        else:
                            anchor_open.remove(lowest_incumbent)
                        total_open = len(open_trades)
                        print(f"[!] Relative Strength Eviction: Replaced {lowest_incumbent['ticker']} (Score {incumbent_score:.1f}) with {c['ticker']} (Score {cand_score:.1f}, Δ+{score_delta:.1f} pts)")
                    else:
                        c["correlation_status"] = f"THROTTLED: Book Full ({cand_book}) - Replacement Hurdle Not Met (Δ+{score_delta:.1f} < 25.0 pts)"
                        continue
                else:
                    c["correlation_status"] = f"THROTTLED: Book Full ({cand_book}) - No Eviction Candidates Available"
                    continue
                
            c["correlation_status"] = "APPROVED (Within Risk Limits)"
            entry_p = c["price"]
            stop_p = c.get("stop") or c.get("macro_stop") or round(entry_p * 0.90, 2)
            entry_alpha_score = c.get("options_alpha_score", c.get("alpha_score"))
            if entry_alpha_score is None:
                print(f"[!] {ticker}: no computed alpha score available at entry; recording as 0 rather than assuming a passing 75.0.")
                entry_alpha_score = 0.0
            new_trade = {
                "id": trade_id,
                "entry_date": today_str,
                "ticker": ticker,
                "sector": c["sector"],
                "entry_price": entry_p,
                "stop_price": stop_p,
                "tp1": c["tp1"],
                "tp2": c["tp2"],
                "structure": c.get("structure", "Bull Call Spread (45-60 DTE)"),
                # strategy_prong was previously never persisted onto the ledger record at
                # all, even though it's read back from `t` in the daily re-score, the
                # anti-chop/eviction logic, and the regime-gated tier-capacity count above
                # (prong_open_count). Every open trade silently registered as "BALANCED"
                # there (or, without any default on the read, didn't match any prong at
                # all) for its entire lifetime, defeating per-prong capacity enforcement.
                "strategy_prong": c.get("strategy_prong", "BALANCED"),
                "contract": c.get("contract", f"{c['sector']} Call Spread"),
                "contract_details": c.get("contract_details", "Defined Risk"),
                "routing_guidance": c.get("routing_guidance", f"LIMIT @ ${c.get('est_debit', 5.0):.2f} Mid"),
                "theta_cliff": c.get("theta_cliff", "21 DTE"),
                "max_hold": c.get("max_hold", 8),
                "target_allocation": c.get("target_allocation", 1000.0),
                "allocation_desc": c.get("allocation_desc", "$1,000 (Full 100%)"),
                "macro_throttled": c.get("macro_throttled", False),
                "current_alpha_score": round(float(entry_alpha_score), 1),
                "score_breakdown": c.get("score_breakdown", {}),
                # Captured for real at entry so the daily re-score isn't forced to guess
                # "definitely liquid, definitely far from earnings" for the rest of this
                # position's lifetime. None (rather than an optimistic constant) is honest
                # for a candidate that never went through liquidity verification.
                "iv_rank": c.get("iv_rank"),
                "long_oi": c.get("long_oi"),
                "short_oi": c.get("short_oi"),
                "bid_ask_spread_pct": c.get("bid_ask_spread_pct"),
                "days_to_earnings": c.get("days_to_earnings"),
                "liquidity_status": c.get("liquidity_status", "⚪ UNVERIFIED (Not Yet Liquidity-Checked)"),
                "active_health_tier": "TIER_B_ON_TRACK",
                "health_badge": "🟢 TIER B (ON-TRACK)",
                "consecutive_low_score_days": 0,
                "eviction_eligible": False,
                "status": "OPEN",
                "current_price": entry_p,
                "max_price": entry_p,
                "min_price": entry_p,
                "days_active": 0,
                "pnl_pct": 0.0,
                "earnings_status": c.get("earnings_status", "SAFE (62d)"),
                "earnings_safe": c.get("earnings_safe", True),
                "invalidation_driver": "ACTIVE",
                "driver_badge": "amber",
                "exit_date": None,
                "exit_reason": None
            }
            trades.insert(0, new_trade)
            existing_ids.add(trade_id)
            active_open_tickers.add(ticker)

    # 3. Compute Cumulative Strategy Performance
    closed = [t for t in trades if t["status"] not in ["OPEN", "TP1_HIT"]]

    # Strict Breakeven Accounting: Isolate 0.00% breakevens from true winners
    breakevens = [t for t in closed if t.get("status") == "CLOSED_BREAKEVEN" or abs(float(t.get("pnl_pct", 0.0) or 0.0)) <= 0.10]
    winners = [t for t in closed if t not in breakevens and (t.get("status") in ["TP1_EXPIRED_WIN", "TP2_HIT"] or float(t.get("pnl_pct", 0.0) or 0.0) > 0.10)]
    losers = [t for t in closed if t not in breakevens and (t.get("status") == "STOPPED_OUT" or float(t.get("pnl_pct", 0.0) or 0.0) < -0.10)]

    decisive_trades = len(winners) + len(losers)
    decisive_win_rate = round((len(winners) / max(1, decisive_trades)) * 100, 1) if decisive_trades > 0 else 0.0

    win_rate = round((len(winners) / max(1, len(closed))) * 100, 1)
    avg_winner = round(sum(t["pnl_pct"] for t in winners) / max(1, len(winners)), 2) if winners else 0.0
    avg_loser = round(sum(t["pnl_pct"] for t in losers) / max(1, len(losers)), 2) if losers else 0.0
    total_win_dollars = sum(t["pnl_pct"] for t in winners)
    total_loss_dollars = abs(sum(t["pnl_pct"] for t in losers)) if losers else 1.0
    profit_factor = round(total_win_dollars / max(0.01, total_loss_dollars), 2)
    avg_holding = round(sum(t.get("days_active", 1) for t in closed) / max(1, len(closed)), 1) if closed else 0.0

    summary = {
        "total_recommendations": len(trades),
        "active_open": len([t for t in trades if t["status"] in ["OPEN", "TP1_HIT"]]),
        "sprint_open": len([t for t in trades if t["status"] in ["OPEN", "TP1_HIT"] and "LEAPS" not in t.get("structure", "")]),
        "anchor_open": len([t for t in trades if t["status"] in ["OPEN", "TP1_HIT"] and "LEAPS" in t.get("structure", "")]),
        "closed_trades": len(closed),
        "breakeven_trades": len(breakevens),
        "evicted_trades": len([t for t in closed if t.get("status") == "CLOSED_EVICTED"]),
        "win_rate_pct": win_rate,
        "decisive_win_rate_pct": decisive_win_rate,
        "profit_factor": profit_factor,
        "avg_winner_pct": avg_winner,
        "avg_loser_pct": avg_loser,
        "avg_holding_days": avg_holding
    }

    trades_payload = {"summary": summary, "trades": trades}
    with open(trades_log_path, "w") as f:
        json.dump(trades_payload, f, indent=2)
    print(f"[+] Updated {trades_log_path} ({len(trades)} total trades, {win_rate}% win rate, {profit_factor}x profit factor)")
    return trades_payload
