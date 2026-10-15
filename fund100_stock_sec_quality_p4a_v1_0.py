"""Phase 4A: offline SEC EDGAR filing-linked annual company QUALITY research.

SEC companyfacts is a TODAY-RETRIEVED API containing historic disclosures;
it is NOT a historically archived point-in-time vendor feed. For any
historical as-of lookup, select ONLY the original accession's own
full-year facts, require matching SEC submissions ledger accession/form,
and wait two weekdays after its filing date. Corrections, amendments,
late facts or later restatements must never be relabelled earlier.

Not analyst earnings estimate revisions; no share-price backtest,
universe survivorship proof, PAPER/LIVE trading, or broker access.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

import pandas as pd

SCHEMA = "FUND100_PHASE4A_SEC_FILING_LINKED_ANNUAL_QUALITY_V1"
ANNUAL_TAGS = {
    "revenue": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "operating_income": "OperatingIncomeLoss",
    "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
    "capital_expenditure": "PaymentsToAcquirePropertyPlantAndEquipment",
}
REQUIRED_FILINGS = ("accessionNumber", "form", "filingDate", "reportDate",
                    "acceptanceDateTime")
FORM = "10-K"
MAX_STALENESS_DAYS = 550
MIN_FY_DAYS = 330
MAX_FY_DAYS = 380


class StockSourceStop(ValueError):
    pass


def iso_date(value: object, label: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\d", value):
        raise StockSourceStop(f"{label} requires ISO date.")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise StockSourceStop(f"Invalid {label}.") from exc
    if d.isoformat() != value:
        raise StockSourceStop(f"Invalid {label}.")
    return d


def availability_day(filed: str) -> str:
    """Conservative two-WEEKDAY lag; not US-holiday/release-time proof."""
    d = iso_date(filed, "filing day")
    return (pd.Timestamp(d) + pd.offsets.BDay(2)).date().isoformat()


def validate_identity(facts: object, submissions: object, expected_cik: str) -> None:
    if (not isinstance(expected_cik, str)
        or not re.fullmatch(r"\d{10}", expected_cik)
        or not isinstance(facts, dict)
        or not isinstance(submissions, dict)
        or isinstance(facts.get("cik"), bool)
        or isinstance(submissions.get("cik"), bool)):
        raise StockSourceStop("SEC source or zero-padded CIK missing.")
    if int(expected_cik) != facts.get("cik") or int(expected_cik) != submissions.get("cik"):
        raise StockSourceStop("CompanyFacts and SEC submissions CIK differ.")
    if not isinstance(facts.get("facts"), dict) or not isinstance(
        facts["facts"].get("us-gaap"), dict
    ):
        raise StockSourceStop("Missing source SEC US-GAAP facts.")
    if not isinstance(submissions.get("filings"), dict) or not isinstance(
        submissions["filings"].get("recent"), dict
    ):
        raise StockSourceStop("Missing SEC source recent filings chronology.")


def submissions_index(submissions: dict) -> dict[str, dict]:
    recent = submissions["filings"]["recent"]
    if not all(isinstance(recent.get(k), list) for k in REQUIRED_FILINGS):
        raise StockSourceStop("Incomplete SEC accession/date/acceptance arrays.")
    length = len(recent["accessionNumber"])
    if length == 0 or any(len(recent[k]) != length for k in REQUIRED_FILINGS):
        raise StockSourceStop("Inconsistent SEC recent filings arrays.")
    index = {}
    for i in range(length):
        accession = recent["accessionNumber"][i]
        form = recent["form"][i]
        filed = recent["filingDate"][i]
        end = recent["reportDate"][i]
        accepted = recent["acceptanceDateTime"][i]
        if not isinstance(accession, str) or not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
            raise StockSourceStop("SEC accession identifier corrupt.")
        if accession in index:
            raise StockSourceStop("Duplicate SEC submissions accession.")
        # Other form types need not report a valid fiscal report date.
        if form == FORM:
            iso_date(filed, "10-K filed date")
            iso_date(end, "10-K annual period end")
            if not isinstance(accepted, str) or not re.fullmatch(
                r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)?", accepted
            ):
                raise StockSourceStop("10-K acceptance clock missing/invalid.")
            # SEC reported acceptance clock timezone is not treated
            # as independently authenticated moment-of-distribution.
        index[accession] = {"form": form, "filed": filed,
                             "end": end, "accepted": accepted}
    return index


def annual_packets(facts: dict, submissions: dict, cik: str) -> list[dict]:
    validate_identity(facts, submissions, cik)
    filings = submissions_index(submissions)
    concepts = facts["facts"]["us-gaap"]
    values: dict[tuple, dict[str, float]] = {}
    for label, tag in ANNUAL_TAGS.items():
        concept = concepts.get(tag)
        if concept is None:
            continue  # Missing fundamentals remain unavailable, never zero-filled.
        unit_rows = concept.get("units", {}).get("USD", [])
        if not isinstance(unit_rows, list):
            raise StockSourceStop("Malformed SEC companyfact USD concept array.")
        for row in unit_rows:
            if not isinstance(row, dict):
                raise StockSourceStop("Malformed SEC XBRL fact row.")
            accn = row.get("accn")
            filing = filings.get(accn)
            if filing is None or filing["form"] != FORM or row.get("form") != FORM:
                continue
            if row.get("filed") != filing["filed"] or row.get("end") != filing["end"]:
                # SEC companyfacts reports comparative facts under later
                # accession. Only original annual report's own FY end allowed.
                continue
            start, end = row.get("start"), row.get("end")
            try:
                start_date = iso_date(start, "annual fact period start")
                end_date = iso_date(end, "annual fact period end")
            except StockSourceStop:
                continue
            if not MIN_FY_DAYS <= (end_date - start_date).days <= MAX_FY_DAYS:
                continue
            raw_value = row.get("val")
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise StockSourceStop("Invalid SEC fundamental dollar value.")
            value = float(raw_value)
            if not math.isfinite(value) or abs(value) > 1e15:
                raise StockSourceStop("Invalid/non-finite SEC fundamental value.")
            key = (end, start, accn, filing["filed"])
            packet = values.setdefault(key, {})
            if label in packet and packet[label] != value:
                raise StockSourceStop("Conflicting duplicate SEC same-period accession facts.")
            packet[label] = value
    out = []
    for (end, start, accn, filed), measurements in sorted(values.items()):
        if set(measurements) != set(ANNUAL_TAGS):
            continue
        if measurements["revenue"] <= 0 or measurements["capital_expenditure"] < 0:
            continue
        out.append({
            "period_start": start, "period_end": end,
            "accession": accn, "filed": filed,
            "available_date": availability_day(filed),
            "metrics": measurements,
        })
    if len({p["period_end"] for p in out}) != len(out):
        raise StockSourceStop("Multiple 10-K versions for same FY: resolve restatements explicitly.")
    return out


def asof_quality(facts: dict, submissions: dict, cik: str,
                 asof: str) -> dict:
    day = iso_date(asof, "research decision date")
    packets = annual_packets(facts, submissions, cik)
    available = [
        p for p in packets
        if iso_date(p["available_date"], "availability") <= day
        and iso_date(p["period_end"], "FY end") <= day
    ]
    available.sort(key=lambda p: (p["period_end"], p["filed"]))
    result = {
        "schema": SCHEMA, "cik": cik, "asof_research_date": asof,
        "state": "MISSING_ELIGIBLE_FULL_YEAR_FILINGS",
        "score": None, "annual_asof_source_period": None,
        "source_accession": None, "source_available_date": None,
        "prior_annual_accession": None,
        "revenue_growth_yoy": None, "operating_margin": None,
        "free_cash_flow_margin": None,
        "analyst_earnings_revision_signal": None,
        "source_historical_vintage_independently_archived": False,
        "point_in_time_stock_price_and_delistings_verified": False,
        "survivorship_safe_historical_backtest_eligible": False,
        "paper_authorized": False, "live_authorized": False,
        "broker_order_count": 0,
    }
    if len(available) < 2:
        return result
    current, previous = available[-1], available[-2]
    if (iso_date(current["period_end"], "period") -
        iso_date(previous["period_end"], "period")).days not in range(330, 400):
        return result
    if (day - iso_date(current["period_end"], "period")).days > MAX_STALENESS_DAYS:
        result["state"] = "LAST_ANNUAL_REPORT_TOO_STALE"
        return result
    now, prev = current["metrics"], previous["metrics"]
    if prev["revenue"] <= 0:
        return result
    revenue_growth = now["revenue"]/prev["revenue"] - 1
    op_margin = now["operating_income"]/now["revenue"]
    fcf_margin = (now["operating_cash_flow"] -
                  now["capital_expenditure"])/now["revenue"]
    score = int(revenue_growth >= 0) + int(op_margin >= .10) + int(fcf_margin >= .05)
    result.update({
        "state": "ANNUAL_REPORTED_QUALITY_AVAILABLE_NOT_TRADE_READY",
        "score": score,
        "score_max": 3,
        "rule": "nonnegative_reported_revenue_growth + operating_margin_at_least_10pct + fcf_margin_at_least_5pct",
        "annual_asof_source_period": current["period_end"],
        "source_accession": current["accession"],
        "source_available_date": current["available_date"],
        "prior_annual_accession": previous["accession"],
        "revenue_growth_yoy": round(revenue_growth, 8),
        "operating_margin": round(op_margin, 8),
        "free_cash_flow_margin": round(fcf_margin, 8),
    })
    return result


def main() -> None:
    p = argparse.ArgumentParser(description="Offline source-linked SEC annual stock-quality evidence")
    p.add_argument("--companyfacts-json", required=True)
    p.add_argument("--submissions-json", required=True)
    p.add_argument("--expected-cik", required=True)
    p.add_argument("--asof-date", required=True)
    p.add_argument("--output-json", required=True)
    args = p.parse_args()
    raw_f = Path(args.companyfacts_json).read_bytes()
    raw_s = Path(args.submissions_json).read_bytes()
    facts = json.loads(raw_f)
    submissions = json.loads(raw_s)
    output = asof_quality(facts, submissions, args.expected_cik, args.asof_date)
    output["source_sha256_companyfacts_json"] = hashlib.sha256(raw_f).hexdigest()
    output["source_sha256_submissions_json"] = hashlib.sha256(raw_s).hexdigest()
    Path(args.output_json).write_text(json.dumps(output, indent=2, sort_keys=True)+"\n")
    print("Phase 4A historical reporting only:", output["state"])
    print("SEC issuer:", output["cik"], "source annual accession:", output["source_accession"])
    print("No analyst earnings estimate revisions, broker orders or PAPER/LIVE permission.")


if __name__ == "__main__":
    main()
