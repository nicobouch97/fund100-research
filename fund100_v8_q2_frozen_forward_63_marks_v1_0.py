"""V8-Q2 first original source -> independently dated forward price marks.

Never retune original 24-issuer SEC/ROA/12-2 source selection. First
possible entry is the first completed NYSE close AFTER Q2 original capture;
following closed bars only. No broker, no strategy release or annualized
alpha assertion. Original artifact may need a hash-checked carry-forward
copy because public GitHub Actions artifacts expire after 90 days.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isclose
from pathlib import Path

import exchange_calendars as xcals
import numpy as np
import pandas as pd

import fund100_stock_broad_momentum_p4l_v1_0 as cohort
import fund100_v7_m1_original_24stock_momentum_forward_v1_0 as market
import fund100_v8_q2_first_actual_sec_roa_price_source_v1_0 as source
import fund100_v8_q2_net_income_roa_momentum_v1_0 as q2

SCHEMA = "FUND100_V8_Q2_FIXED_ORIGINAL_63_FOLLOWING_CLOSE_MARKS_V1"
FIRST_SOURCE_REPORT = "first-new-vintage-q2-source-coverage-and-candidate-NO-LIVE.json"
ORIGINAL_PRICE_CSV = "original-24-issuer-completed-adjusted-prices.csv"
ORIGINAL_REGISTRY = "current-official-sec-registry.json"
FOLLOWING_SESSIONS = 63
COSTS_BPS = (5, 15, 35)
BROKER_GETS = BROKER_POSTS = BROKER_ORDERS = 0
LIVE_AUTHORIZED = False

class MarkHold(ValueError):
    pass


def _read_source(root: Path):
    """Byte-check entire frozen source archive, not only copied ticker labels."""
    if not isinstance(root, Path):
        raise MarkHold("Unverifiable original artifact directory")
    try:
        b = (root/FIRST_SOURCE_REPORT).read_bytes()
        report = json.loads(b)
        registry = (root/ORIGINAL_REGISTRY).read_bytes()
        prices = (root/ORIGINAL_PRICE_CSV).read_bytes()
    except (OSError, ValueError) as exc:
        raise MarkHold("Missing first original Q2 archived bytes") from exc
    if (not isinstance(report, dict)
        or report.get("schema") != source.SCHEMA
        or report.get("status") != "ACTUAL_PUBLIC_ORIGINAL_Q2_SOURCE_ACQUIRED_RESEARCH_ONLY"
        or report.get("live_order_authorized") is not False
        or report.get("broker_orders") != 0
        or report.get("forward_63_sessions_not_observed") is not True
        or sha256(registry).hexdigest() != report.get("current_original_registry_sha256")
        or sha256(prices).hexdigest() != report.get("completed_original_price_panel_sha256")):
        raise MarkHold("First original Q2 archived source or digest changed")
    raw_receipts = report.get("complete_current_original_24_sec_source_receipts")
    rows = report.get("source_rows")
    if (type(raw_receipts) is not list or len(raw_receipts) != 24
        or type(rows) is not list or len(rows) != 24):
        raise MarkHold("Original complete 24 SEC issuer receipts unavailable")
    from_original = {}
    for rec in raw_receipts:
        if type(rec) is not dict or set(rec) != {
            "symbol","current_registry_cik","official_companyfacts_sha256",
            "official_submissions_sha256"}:
            raise MarkHold("Original SEC raw receipt schema altered")
        ticker, cik = rec["symbol"], rec["current_registry_cik"]
        if (type(ticker) is not str or type(cik) is not str
            or len(cik) != 10 or not cik.isdigit() or ticker in from_original):
            raise MarkHold("Unverifiable original issuer identity")
        d = {}
        for kind, key in (("companyfacts", "official_companyfacts_sha256"),
                          ("submissions", "official_submissions_sha256")):
            blob = root/f"raw/CIK{cik}-{ticker}-{kind}.json"
            try:
                contents = blob.read_bytes()
            except OSError as exc:
                raise MarkHold("Missing permanently frozen SEC raw source") from exc
            digest = sha256(contents).hexdigest()
            if digest != rec.get(key):
                raise MarkHold("Original raw SEC source bytes changed")
            d[kind] = digest
        from_original[ticker] = sha256(
            (d["companyfacts"]+d["submissions"]).encode("ascii")).hexdigest()
    if set(from_original) != set(cohort.SECTORS):
        raise MarkHold("Incomplete original 24-issuer roster")
    if any(type(row) is not dict or row.get("symbol") not in from_original
           or row.get("original_raw_sec_receipt_sha256") != from_original[row["symbol"]]
           for row in rows):
        raise MarkHold("Original Q2 scorer receipts diverged from raw official SEC files")
    try:
        original_price_panel = pd.read_csv(
            root/ORIGINAL_PRICE_CSV, index_col="Date", parse_dates=["Date"])
        normalized = cohort.canonical_csv(original_price_panel).encode("utf-8")
    except Exception as exc:
        raise MarkHold("First original price panel not verified") from exc
    if normalized != prices:
        raise MarkHold("Original price bytes noncanonical or source revised")
    original_session = original_price_panel.index[-1].date().isoformat()
    acquired = report.get("source_acquired_utc")
    if original_session != report.get("last_completed_market_session"):
        raise MarkHold("Original completed session relabelled")
    try:
        screen = q2.select(
            rows=rows,
            benchmark_minus252=format(
                __import__("decimal").Decimal(str(original_price_panel["SPY"].iloc[
                    -1-q2.LOOKBACK_SESSIONS])), ".8f"),
            benchmark_minus42=format(
                __import__("decimal").Decimal(str(original_price_panel["SPY"].iloc[
                    -1-q2.SKIP_RECENT_SESSIONS])), ".8f"),
            decision_utc=acquired,price_session=original_session,
            source_mode=q2.SOURCE_MODE)
    except Exception as exc:
        raise MarkHold("Frozen original V8-Q2 scorer could not be reproduced") from exc
    if screen != report.get("source_derived_research_selection"):
        raise MarkHold("Original forward selection or missingness altered")
    return report, screen, prices, acquired


def _sector_neutral(selected):
    """Predeclared frozen cohort sector-peer control; no later winners used."""
    weights={}
    for s in selected:
        peers=sorted(k for k,v in cohort.SECTORS.items()
                     if v == cohort.SECTORS[s])
        if not peers:
            raise MarkHold("Frozen sector control has no original peers")
        for peer in peers:
            weights[peer]=weights.get(peer,0.)+1/(len(selected)*len(peers))
    if not isclose(sum(weights.values()),1.,abs_tol=1e-12):
        raise MarkHold("Frozen sector control does not sum to one")
    return dict(sorted(weights.items()))


def _costed_hypothetical(entry, final, weights, fee_bps, *, horizon_done):
    """Long-only self-financed entry, plus exit cost ONLY on final session."""
    if fee_bps not in COSTS_BPS:
        raise MarkHold("Unregistered cost stress")
    if not isclose(sum(weights.values()),1.,abs_tol=1e-12):
        raise MarkHold("Invalid frozen sector/stock weights")
    fee=fee_bps/10000.
    entry_net=100./(1.+.95*fee)
    cash=.05*entry_net
    holdings={}
    for sym, weight in weights.items():
        a,b=float(entry[sym]),float(final[sym])
        if not (np.isfinite(a) and np.isfinite(b) and a>0 and b>0
                and weight>=0):
            raise MarkHold("Missing or impossible actual stock forward prices")
        holdings[sym]=entry_net*.95*weight*b/a
    gross=sum(holdings.values())
    terminal_fee=fee*gross if horizon_done else 0.
    mark=cash+gross-terminal_fee
    if not np.isfinite(mark) or mark<=0:
        raise MarkHold("Insolvent or invalid hypothetical NAV")
    return {
        "net_value_per_100_original_usd":round(mark,8),
        "net_return_pct":round(mark-100.,8),
        "entry_side_bps":fee_bps,
        "terminal_exit_charged_only_at_63rd_following_close":bool(horizon_done),
        "gross_exposure_at_latest_observed_mark_pct":round(100.*gross/(cash+gross),6),
        "cash_after_original_entry_usd_per_100":round(cash,8),
        "no_hypothetical_rebalances":True,
    }


def evaluate(*, original_root:Path, later_prices:pd.DataFrame, observed_at_utc:str):
    report, screen, original_prices, captured = _read_source(original_root)
    try:
        now=q2._utc(observed_at_utc)
        selection_at=q2._utc(captured)
        later=cohort.validate_prices(later_prices)
        cohort.p4g.verify_original_nyse_source_sessions(later.index)
        market._source_close_qualified(
            last_session=later.index[-1].date().isoformat(),capture=now)
    except Exception as exc:
        raise MarkHold("Later original vendor close or dated NYSE source not valid") from exc
    if now <= selection_at:
        raise MarkHold("Future marks cannot predate original selection")
    original_session=pd.Timestamp(report["last_completed_market_session"])
    if later.index[-1] < original_session:
        raise MarkHold("Latest original vendor source precedes frozen source")
    cal=xcals.get_calendar("XNYS")
    # Only sessions whose actual exchange close was strictly AFTER the
    # frozen original acquisition are prospective entry/mark candidates.
    eligible=[day for day in later.index
              if day>original_session and
              cal.session_close(day).to_pydatetime()>selection_at]
    complete=len(eligible)
    if complete>FOLLOWING_SESSIONS:
        # Once horizon was complete, observations cannot be silently moved
        # to a later, more favorable endpoint.
        eligible=eligible[:FOLLOWING_SESSIONS]
    qualified=len(eligible)
    result={
        "schema":SCHEMA,
        "research_only":True,
        "source_acquired_utc":captured,
        "source_report_sha256":sha256(
            (original_root/FIRST_SOURCE_REPORT).read_bytes()).hexdigest(),
        "original_market_price_csv_sha256":sha256(original_prices).hexdigest(),
        "original_frozen_source_price_session":
            report["last_completed_market_session"],
        "observed_forward_price_vintage_utc":observed_at_utc,
        "latest_observed_close":later.index[-1].date().isoformat(),
        "forward_close_sessions_observed":qualified,
        "required_future_close_sessions":FOLLOWING_SESSIONS,
        "real_broker_orders":0,
        "strategy_live_released":False,
        "proven_statistical_alpha":False,
        "source_is_contemporary_survivor_selected":True,
        "original_adjusted_price_source_independently_authenticated":False,
        "candidate_reselected_or_refit_after_new_prices":False,
        "first_source_archive_retention_is_not_permanent":True,
        "complete_horizon":qualified==FOLLOWING_SESSIONS,
        "basis": "First eligible completed NYSE close after original acquisition is hypothetical entry, never the pre-acquisition close",
    }
    basket=screen.get("selection_candidate")
    if basket is None:
        result["status"]="ORIGINAL_Q2_SOURCE_HOLD_NO_BASKET"
        result["source_coverage"]=screen["matched_positive_annual_net_income_assets"]
        result["performance"]=None
        return result
    selected=basket["symbols"]
    if (type(selected) is not list or len(selected)!=8
        or len(set(selected))!=8 or any(s not in cohort.SECTORS for s in selected)):
        raise MarkHold("Original frozen investment basket inconsistent")
    if qualified==0:
        result["status"]="WAITING_FOR_FIRST_POST_CAPTURE_NYSE_CLOSE"
        result["selected_original_names"]=selected
        result["performance"]=None
        return result
    entry=eligible[0]
    end=eligible[-1]
    row_entry=later.loc[entry]
    row_end=later.loc[end]
    # Study ends at the original 63rd *following* close (62 intervening
    # close-to-close intervals from the first hypothetically entered close).
    complete_horizon=qualified==FOLLOWING_SESSIONS
    comparators={
        "frozen_q2_eight_equal":{name:1/8 for name in selected},
        "same_sector_original_24_cohort":_sector_neutral(selected),
        "passive_95_spy_5_cash":{"SPY":1.},
    }
    perf={str(bps):{
        name:_costed_hypothetical(
            row_entry,row_end,weights,bps,horizon_done=complete_horizon)
        for name,weights in comparators.items()}
        for bps in COSTS_BPS}
    result.update({
        "status":("63_FOLLOWING_CLOSES_DESCRIPTIVE_COMPLETE_NOT_ALPHA"
                  if complete_horizon else "EARLY_DESCRIPTIVE_FORWARD_MARK_ONLY"),
        "hypothetical_entry_close":entry.date().isoformat(),
        "last_63_close_checkpoint":end.date().isoformat(),
        "completed_close_to_close_intervals_since_entry":qualified-1,
        "selected_original_names":selected,
        "sector_neutral_weights_frozen_from_contemporary_24":
            comparators["same_sector_original_24_cohort"],
        "performance":perf,
        "modeled_entry_at_first_completed_close_not_a_firm_fill":True,
        "all_historical_2026_stock_names_not_survivorship_free":True,
    })
    return result


def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--original-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--later-price-csv",type=Path,required=True)
    a=p.parse_args()
    current=market._later_original_public_prices()
    observed=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    analysis=evaluate(original_root=a.original_dir,
                      later_prices=current,observed_at_utc=observed)
    if a.output.exists() or a.later_price_csv.exists():
        raise MarkHold("Never overwrite independent forward-mark artifact")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.later_price_csv.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(analysis,indent=2,sort_keys=True)+"\n")
    a.later_price_csv.write_text(cohort.canonical_csv(current))
    print(analysis["status"],"forward NYSE closes",analysis[
        "forward_close_sessions_observed"],"no orders")


if __name__=="__main__":
    main()
