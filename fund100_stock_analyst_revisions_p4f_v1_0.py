"""Fund-100 P4F: source-verified (hash) analyst EPS revision RESEARCH contract.

Requires genuine event PUBLICATION timestamps, capture times, an
issuer+security binding, one EPS basis/currency/fiscal period, and a
real source file SHA256. The only shipped data is SYNTHETIC_TEST;
no licensed feed is connected and no real earnings revisions are
observed in this repository. An unverified licensed export remains
unverified even when internally consistent. SEC filings are NEVER
mistaken for broker EPS estimate revisions.

No orders, portfolios, backtested stock returns or PAPER/LIVE promotion.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re

import fund100_stock_sec_source_p4b_v1_0 as sec

SCHEMA = "FUND100_P4F_ANALYST_EPS_REVISION_SOURCE_V1"
MANIFEST_SCHEMA = "FUND100_P4F_ORIGINAL_ESTIMATE_SOURCE_MANIFEST_V1"
PERMITTED_PROVIDERS = {
    "SYNTHETIC_FIXTURE": "SYNTHETIC_FIXTURE",
    "FACTSET_DETAIL": "UNVERIFIED_LICENSED_EXPORT",
    "LSEG_IBES_DETAIL": "UNVERIFIED_LICENSED_EXPORT",
}
MEASURE = "EPS_NORMALIZED_DILUTED"
CURRENCY = "USD"
LOOKBACK_DAYS = 30
PREVIOUS_MAX_AGE_DAYS = 180
FUTURE_PERIOD_MAX_DAYS = 540
CONSERVATIVE_CAPTURE_LAG_HOURS = 24
MIN_DIRECTIONAL_CONTRIBUTORS = 3
MIN_ABS_REVISION_USD = .02
MIN_REL_REVISION = .01


class AnalystEvidenceStop(ValueError):
    pass


def utc(v: object, label: str) -> datetime:
    if not isinstance(v, str) or not re.fullmatch(
        r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", v
    ):
        raise AnalystEvidenceStop(f"{label}: canonical UTC timestamp required.")
    try:
        result = datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise AnalystEvidenceStop(f"{label}: impossible UTC timestamp.") from exc
    return result


def day(v: object) -> date:
    if not isinstance(v, str) or not re.fullmatch(r"20\d\d-\d\d-\d\d",v):
        raise AnalystEvidenceStop("Invalid fiscal period date.")
    try:
        return date.fromisoformat(v)
    except ValueError as exc:
        raise AnalystEvidenceStop("Impossible fiscal period date.") from exc


def parse_source(raw: bytes, manifest: dict) -> tuple[dict, datetime]:
    """Source checksum and claimed rights gate, NOT independent license audit."""
    if not isinstance(raw, bytes) or not 4 <= len(raw) <= 10_000_000:
        raise AnalystEvidenceStop("Original source bytes required and size bounded.")
    if not isinstance(manifest, dict) or manifest.get("schema") != MANIFEST_SCHEMA:
        raise AnalystEvidenceStop("Unknown estimates source evidence manifest.")
    digest = hashlib.sha256(raw).hexdigest()
    if manifest.get("original_file_sha256") != digest:
        raise AnalystEvidenceStop("Original estimate file SHA256 mismatch.")
    provider = manifest.get("provider")
    if provider not in PERMITTED_PROVIDERS or (
        manifest.get("source_class") != PERMITTED_PROVIDERS[provider]
    ):
        raise AnalystEvidenceStop("Provider class and source evidence do not agree.")
    if (provider != "SYNTHETIC_FIXTURE"
        and (manifest.get("research_redistribution_permitted") is not True
             or manifest.get("declared_entitlement_reference") in (None, ""))):
        raise AnalystEvidenceStop("Original vendor research access/rights unconfirmed.")
    if (provider == "SYNTHETIC_FIXTURE"
        and manifest.get("declared_entitlement_reference") != "SYNTHETIC_OFFLINE_TEST"):
        raise AnalystEvidenceStop("Fixture must be explicitly labelled synthetic.")
    reference = manifest.get("source_reference")
    if not isinstance(reference,str) or len(reference) < 8 or len(reference) > 256:
        raise AnalystEvidenceStop("Original dated vendor reference required.")
    received = utc(manifest.get("file_acquired_at_utc"), "original file captured")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise AnalystEvidenceStop("Original estimate source is not UTF-8 JSON.") from exc
    if not isinstance(obj,dict) or obj.get("schema") != SCHEMA or not isinstance(obj.get("events"),list):
        raise AnalystEvidenceStop("Unexpected original estimate event source schema.")
    if len(obj["events"]) > 50000:
        raise AnalystEvidenceStop("Excessive original analyst revision events.")
    return obj, received


def _number(v: object) -> float:
    if type(v) not in (int,float) or not math.isfinite(v) or abs(v) > 1e4:
        raise AnalystEvidenceStop("EPS estimate must be finite numeric per share.")
    return float(v)


def evaluate(raw: bytes, manifest: dict, *, ticker: str, fiscal_year_end: str,
             decision_at_utc: str) -> dict:
    obj, captured = parse_source(raw, manifest)
    asof = utc(decision_at_utc, "decision time")
    target = day(fiscal_year_end)
    cohort = {r["ticker"]:r for r in sec.read_cohort()}
    if ticker not in cohort:
        raise AnalystEvidenceStop("Ticker outside frozen contemporary stock research cohort.")
    expected_cik=cohort[ticker]["cik_10_digit"]
    if (asof.date() < date(2026,10,15)
        or captured > asof
        or target <= asof.date()
        or (target-asof.date()).days > FUTURE_PERIOD_MAX_DAYS):
        raise AnalystEvidenceStop("Prospective as-of/source/fiscal period eligibility failed.")
    if obj.get("provider") != manifest["provider"]:
        raise AnalystEvidenceStop("Raw source and evidence manifest provider differ.")
    if obj.get("estimate_measure") != MEASURE or obj.get("currency") != CURRENCY:
        raise AnalystEvidenceStop("Required identical EPS basis and currency unavailable.")
    qualified = {}
    keys=set()
    canonical_security_id = None
    rejected_noncohort = 0
    for event in obj["events"]:
        if not isinstance(event,dict):
            raise AnalystEvidenceStop("Malformed broker EPS event.")
        required=(
            "revision_id","ticker","issuer_cik","vendor_security_id","broker_contributor_id",
            "fiscal_year_end","old_eps","new_eps","old_published_at_utc",
            "new_published_at_utc","provider_received_at_utc","measure","currency",
        )
        if any(k not in event for k in required):
            raise AnalystEvidenceStop("Incomplete analyst estimate event evidence.")
        revision_id=event["revision_id"]
        broker=event["broker_contributor_id"]
        security_id=event["vendor_security_id"]
        if any(not isinstance(x,str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{3,128}",x)
               for x in (revision_id,broker,security_id)):
            raise AnalystEvidenceStop("Original analyst/contributor/event identity missing.")
        if revision_id in keys:
            raise AnalystEvidenceStop("Duplicate original vendor revision ID.")
        if canonical_security_id is not None and security_id != canonical_security_id:
            raise AnalystEvidenceStop("Mixed security/share-class identities in analyst source.")
        canonical_security_id = security_id
        keys.add(revision_id)
        prev=utc(event["old_published_at_utc"],"prior estimate publication")
        pub=utc(event["new_published_at_utc"],"revision publication")
        rec=utc(event["provider_received_at_utc"],"revision captured")
        if not prev < pub <= rec <= captured:
            raise AnalystEvidenceStop("Future, post-facto or out-of-order estimate chronology.")
        old,new=_number(event["old_eps"]),_number(event["new_eps"])
        if event["measure"] != MEASURE or event["currency"] != CURRENCY:
            raise AnalystEvidenceStop("Mixed EPS basis/currency/measure in source.")
        period=day(event["fiscal_year_end"])
        if event["ticker"] != ticker or event["issuer_cik"] != expected_cik:
            # Do not mix issuers, share classes or CIK/ticker recycles.
            raise AnalystEvidenceStop("Source event not linked to frozen issuer.")
        if period != target:
            rejected_noncohort += 1
            continue
        if (asof - rec < timedelta(hours=CONSERVATIVE_CAPTURE_LAG_HOURS)
            or asof - pub > timedelta(days=LOOKBACK_DAYS)
            or asof < rec
            or pub - prev > timedelta(days=PREVIOUS_MAX_AGE_DAYS)):
            continue
        key=broker
        candidate=(pub,rec,revision_id,old,new)
        if key not in qualified or candidate[:3] > qualified[key][:3]:
            qualified[key]=candidate
    up=down=neutral=0
    for _,_,_,old,new in qualified.values():
        delta = new-old
        threshold=max(MIN_ABS_REVISION_USD,
                      MIN_REL_REVISION*max(abs(old),.5))
        if delta >= threshold - 1e-12:
            up+=1
        elif delta <= -threshold + 1e-12:
            down+=1
        else:
            neutral+=1
    directional=up+down
    pressure=(up-down)/directional if directional>=MIN_DIRECTIONAL_CONTRIBUTORS else None
    synthetic=manifest["source_class"]=="SYNTHETIC_FIXTURE"
    return {
        "schema":SCHEMA,
        "ticker":ticker,
        "cik":expected_cik,
        "target_fiscal_year_end":fiscal_year_end,
        "decision_at_utc":decision_at_utc,
        "source_provider":manifest["provider"],
        "source_class":manifest["source_class"],
        "original_source_sha256":manifest["original_file_sha256"],
        "source_acquired_at_utc":manifest["file_acquired_at_utc"],
        "signal_state":(
            "SYNTHETIC_DIRECTIONAL_PRESSURE_ONLY" if synthetic and pressure is not None
            else "UNVERIFIED_EXPORT_DIRECTIONAL_PRESSURE_ONLY" if pressure is not None
            else "INSUFFICIENT_DATED_BROKER_REVISION_EVIDENCE"
        ),
        "qualified_distinct_contributors":len(qualified),
        "upward_revisions":up,
        "downward_revisions":down,
        "neutral_revisions":neutral,
        "other_fiscal_period_events_excluded":rejected_noncohort,
        "descriptive_revision_pressure":round(pressure,6) if pressure is not None else None,
        "provider_data_independently_authenticated":False,
        "vendor_license_independently_verified":False,
        "real_vendor_revision_data_available_in_fund100":False,
        "prospective_model_ranking_approved":False,
        "point_in_time_historical_backtest_eligible":False,
        "security_master_and_delisting_returns_validated":False,
        "broker_orders":0,
        "paper_authorized":False,
        "live_authorized":False,
    }


def readiness_report() -> dict:
    """Auditable absence-of-data state: never make up historic revisions."""
    cohort = sec.read_cohort()
    return {
        "schema": SCHEMA,
        "status": "PREDECLARED_SOURCE_CONTRACT_NO_REAL_ANALYST_DATA",
        "frozen_contemporary_stock_issuer_count": len(cohort),
        "frozen_contemporary_stock_tickers": [r["ticker"] for r in cohort],
        "contemporary_cohort_not_historical_survivorship_safe": True,
        "licensed_original_analyst_events_retrieved": 0,
        "original_provider_feed_connected": False,
        "broker_level_vendor_entitlement_verified": False,
        "provider_publication_timestamps_verified": False,
        "analyst_earnings_revision_scores_computed_from_real_data": 0,
        "historical_stock_return_alpha_validated": False,
        "historical_delisting_inclusive_universe_verified": False,
        "next_provider_dependency":
            "Original timestamped broker EPS detail from LSEG I/B/E/S or FactSet Detail, rights and security mapping",
        "broker_orders": 0, "paper_authorized": False, "live_authorized": False,
    }


def main() -> None:
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("--readiness-only",action="store_true")
    p.add_argument("--raw-events-json")
    p.add_argument("--manifest-json")
    p.add_argument("--ticker")
    p.add_argument("--fiscal-year-end")
    p.add_argument("--decision-at-utc")
    p.add_argument("--output-json",required=True)
    a=p.parse_args()
    if a.readiness_only:
        report=readiness_report()
    else:
        if not all((a.raw_events_json,a.manifest_json,a.ticker,a.fiscal_year_end,a.decision_at_utc)):
            p.error("Non-readiness evaluation requires original vendor source, manifest and target.")
        report=evaluate(
            Path(a.raw_events_json).read_bytes(),
            json.loads(Path(a.manifest_json).read_text()),
            ticker=a.ticker, fiscal_year_end=a.fiscal_year_end,
            decision_at_utc=a.decision_at_utc,
        )
    Path(a.output_json).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("P4F analyst revisions:",report.get("signal_state",report.get("status")))
    print("No licensed analyst feed attached; no stock PAPER/LIVE or historical alpha.")


if __name__=="__main__":
    main()
