"""V7-E3: source-verified SEC earnings signal chronology audit.

Audits pinned, independently archived SEC and two P4G price observations.
This is a pre-trade signal-availability *audit*, not a return backtest.
No network, no broker, no mutation of source archives and no trading authority.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

SCHEMA = "FUND100_V7_E3_PINNED_SEC_EVENT_SIGNAL_TIMELINE_V1"
ORIGINAL_PRICE_SESSION = "2026-10-16"
EARLIEST_FILED = "2026-10-15"
MAX_EVENT_AGE_SESSIONS = 10
REACTION_MIN = 0.02

class EvidenceStop(ValueError):
    pass

def timestamp(value: str) -> datetime:
    try:
        result = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError) as exc:
        raise EvidenceStop("noncanonical UTC source acquisition timestamp") from exc
    return result.replace(tzinfo=timezone.utc)

def classify(filed: str, sec_acquired: str, signal_asof: str,
             signal_acquired: str, observed_sessions: list[str],
             quality: int | None) -> dict:
    """Fail-closed availability of an original Item 2.02 signal.

    Uses completed session *dates* from a validated later source only as a
    calendar. Signal strength must come from an ORIGINAL pre-entry snapshot.
    Entry model is the third postfiling CLOSE; morning T+1 data is allowed
    only if captured by noon UTC on that third session (before US opening).
    This conservative cutoff is not a claim of authentic executable fills.
    """
    try:
        filing = date.fromisoformat(filed)
        session_dates = [date.fromisoformat(v) for v in observed_sessions]
        original_asof = date.fromisoformat(signal_asof)
        sec_time = timestamp(sec_acquired)
        signal_time = timestamp(signal_acquired)
    except (ValueError, TypeError) as exc:
        raise EvidenceStop("invalid original event/source dates") from exc
    if session_dates != sorted(set(session_dates)):
        raise EvidenceStop("market sessions not unique and ordered")
    if filing > sec_time.date():
        raise EvidenceStop("filing not available when SEC capture occurred")
    base = [d for d in session_dates if d < filing]
    later = [d for d in session_dates if d > filing]
    if filed < EARLIEST_FILED:
        reason = "BEFORE_FROZEN_QUALITY_REGISTRATION"
    elif quality is None or quality < 2:
        reason = "NO_CONTEMPORANEOUS_QUALITY_COVERAGE"
    elif not base or len(later) < 3:
        reason = "MISSING_PRE_EVENT_OR_THIRD_POST_EVENT_SESSION"
    elif original_asof < later[1]:
        reason = "SECOND_POST_EVENT_CLOSE_NOT_IN_PRE_ENTRY_SNAPSHOT"
    elif original_asof > later[1]:
        reason = "SIGNAL_SNAPSHOT_CONTAINS_EXTRA_POST_SIGNAL_SESSIONS"
    elif sec_time > signal_time:
        reason = "SEC_CAPTURE_NOT_AVAILABLE_AT_SIGNAL"
    elif signal_time.date() <= later[1]:
        reason = "SIGNAL_PRICE_CAPTURE_BEFORE_COMPLETED_SECOND_SESSION"
    elif signal_time >= datetime.combine(later[2], datetime.min.time(),
                                          tzinfo=timezone.utc).replace(hour=12):
        reason = "SIGNAL_SOURCE_TOO_LATE_FOR_THIRD_SESSION"
    elif len(later) > MAX_EVENT_AGE_SESSIONS:
        reason = "EVENT_TOO_OLD_FOR_ORIGINAL_SCREEN"
    else:
        reason = "TIMELINE_ELIGIBLE_NEEDS_ORIGINAL_PRICE_REACTION"
    return {"reason": reason, "second_session":later[1].isoformat()
            if len(later)>=2 else None,
            "third_session":later[2].isoformat() if len(later)>=3 else None}

def audit(sec_dir: Path, original_json: Path, original_csv: Path,
          later_json: Path, later_csv: Path) -> dict:
    import fund100_v6_sec_earnings_catalyst_e1_v1_0 as e1
    import fund100_stock_forward_return_ledger_p4h_v1_0 as p4h
    import fund100_stock_quality_momentum_p4g_v1_0 as p4g

    original_manifest_bytes = (sec_dir / "manifest-and-quality.json").read_bytes()
    sec_manifest_sha = sha256(original_manifest_bytes).hexdigest()
    if sec_manifest_sha != p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256:
        raise EvidenceStop("SEC manifest bytes not original frozen manifest")
    manifest, submissions = e1.original_sec_sources(sec_dir)
    baseline, baseline_prices, baseline_sha = p4h.read_snapshot(original_json, original_csv)
    follow, follow_prices, follow_sha = p4h.read_snapshot(later_json, later_csv)
    if (baseline["asof_completed_session"] != ORIGINAL_PRICE_SESSION
        or baseline["source_acquired_at_utc"][:10] != "2026-10-17"
        or timestamp(manifest["capture_timestamp_utc"]) > timestamp(baseline["source_acquired_at_utc"])
        or timestamp(follow["source_acquired_at_utc"]) <= timestamp(baseline["source_acquired_at_utc"])
        or follow_prices.index[-1] <= baseline_prices.index[-1]):
        raise EvidenceStop("wrong original source vintages or time ordering")

    original_dates = baseline_prices.index
    if not original_dates.isin(follow_prices.index).all():
        raise EvidenceStop("later source omitted previously observed session")
    later_prefix = follow_prices.loc[original_dates]
    previous_history_unchanged = baseline_prices.equals(later_prefix)
    # Vendor revision is explicitly labelled; later prices may NOT rewrite
    # what the original signal snapshot was able to observe.
    calendar = [d.date().isoformat() for d in follow_prices.index]
    counts = Counter()
    reviewed = []
    for ticker in sorted(submissions):
        for event in e1.filing_candidates(
                submissions[ticker], ticker,
                e1.capture_time(manifest["capture_timestamp_utc"], "SEC acquisition")):
            if event["filed_date"] < EARLIEST_FILED:
                continue
            result = classify(event["filed_date"], manifest["capture_timestamp_utc"],
                              baseline["asof_completed_session"],
                              baseline["source_acquired_at_utc"], calendar,
                              p4g.FROZEN_P4E_SCORES[ticker])
            reason = result["reason"]
            reaction = None
            if reason == "TIMELINE_ELIGIBLE_NEEDS_ORIGINAL_PRICE_REACTION":
                # Compute from the ORIGINAL signal vintage, never the revisable later copy.
                prev = max(d for d in original_dates if d.date().isoformat() < event["filed_date"])
                second = result["second_session"]
                if second not in {d.date().isoformat() for d in original_dates}:
                    raise EvidenceStop("original price evidence absent on signal date")
                s = baseline_prices
                relative = ((float(s.loc[second, ticker] / s.loc[prev, ticker]) - 1)
                            - (float(s.loc[second, "SPY"] / s.loc[prev, "SPY"]) - 1))
                reaction = round(relative, 10)
                reason = ("ORIGINAL_SIGNAL_PASSED_NO_POST_ENTRY_RETURN_PROVEN"
                          if relative >= REACTION_MIN else "ORIGINAL_SIGNAL_BELOW_THRESHOLD")
            counts[reason] += 1
            reviewed.append({"ticker":ticker, "original_sec_accession":event["accession"],
                             "filed_date":event["filed_date"], "status":reason,
                             "original_snapshot_relative_reaction":reaction,
                             "broker_orders":0})
    eligible = counts["ORIGINAL_SIGNAL_PASSED_NO_POST_ENTRY_RETURN_PROVEN"]
    return {
        "schema": SCHEMA,
        "status": "ORIGINAL_ARCHIVES_CHRONOLOGY_AUDITED_NO_TRADE",
        "original_sec_run_id":38756477914,
        "original_price_run_id":39015519726,
        "later_price_run_id":39750446875,
        "original_sec_manifest_sha256":sec_manifest_sha,
        "original_price_report_sha256":baseline_sha,
        "later_price_report_sha256":follow_sha,
        "original_price_csv_sha256":baseline["canonical_price_csv_sha256"],
        "later_price_csv_sha256":follow["canonical_price_csv_sha256"],
        "original_price_asof_session":baseline["asof_completed_session"],
        "later_price_asof_session":follow["asof_completed_session"],
        "later_vendor_original_price_prefix_unchanged":bool(previous_history_unchanged),
        "later_vendor_revisions_do_not_rewrite_original_signal":True,
        "events_from_authenticated_original_SEC_since_registration":len(reviewed),
        "original_signal_pass_count_not_a_trade":eligible,
        "rejection_and_signal_counts":dict(sorted(counts.items())),
        "event_audit":reviewed,
        "hypothetical_post_entry_return_calculated":False,
        "original_analyst_surprises_available":False,
        "historical_alpha_proven":False,
        "live_positions_changed":False,
        "paper_authorized":False, "live_authorized":False,
        "trading_authorized":False,"broker_orders":0,
    }

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--sec-original-directory",type=Path,required=True)
    p.add_argument("--original-json",type=Path,required=True)
    p.add_argument("--original-csv",type=Path,required=True)
    p.add_argument("--later-json",type=Path,required=True)
    p.add_argument("--later-csv",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    out=audit(a.sec_original_directory,a.original_json,a.original_csv,
              a.later_json,a.later_csv)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("V7E3",out["status"], "AUTHENTIC_POST_REGISTRATION_EVENTS",
          out["events_from_authenticated_original_SEC_since_registration"],
          "SOURCE_ELIGIBLE_EVENTS",out["original_signal_pass_count_not_a_trade"],
          "REVISED_VENDOR_PREFIX",not out["later_vendor_original_price_prefix_unchanged"])
    print("NO POST-ENTRY RETURNS, LIVE ORDERS, OR INVESTMENT ALPHA PROVEN")

if __name__ == "__main__":
    main()
