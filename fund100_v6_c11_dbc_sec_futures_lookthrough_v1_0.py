"""V6-C11 filing-date-safe DBC futures *notional* composition research.

These are SEC-transcribed gross futures notionals, never capital weights,
actual same-day ETF holdings, strategy signals, carry P&L or broker orders.
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha1
from pathlib import Path
import re

SCHEMA = "FUND100_V6_C11_DBC_SEC_FUTURES_LOOKTHROUGH_V1"
ROOT = Path(__file__).resolve().parent
SOURCE_BLOBS = {
    "dbc_sec_futures_holdings_2025_q4_postchange.csv":
        "315fbfab8f95c3290bd156a7eba2ad3bac2e4ac7",
    "dbc_sec_futures_holdings_2026_q1_q2.csv":
        "68953f0f122d00e1d06f893cc879d0ec71117287",
}
SUBDIR = Path("research_lab/commodities")
EXPECTED = {
    "2025-12-31": {
        "available_date": "2026-03-03", "filing_date": "2026-03-02",
        "accession": "0001193125-26-083563",
        "notional": 1223550999, "count": 28,
    },
    "2026-03-31": {
        "available_date": "2026-05-08", "filing_date": "2026-05-07",
        "accession": "0001193125-26-209724",
        "notional": 1689474972, "count": 28,
    },
    "2026-06-30": {
        "available_date": "2026-08-10", "filing_date": "2026-08-07",
        "accession": "0001193125-26-338697",
        "notional": 1576215941, "count": 28,
    },
}
SECTORS = ("Agriculture", "Energy", "Industrial metals",
           "Livestock", "Precious metals")
COLUMNS = ("statement_date", "sec_filing_date", "available_date",
           "accession", "sec_filing_url", "commodity", "sector",
           "delivery_month", "contracts", "notional_usd")
NO_BROKER_REQUESTS = True


class FilingLookthroughStop(ValueError):
    pass


def _date(raw: object) -> date:
    if type(raw) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raise FilingLookthroughStop("Invalid source or decision date")
    try:
        value = date.fromisoformat(raw)
    except ValueError as exc:
        raise FilingLookthroughStop("Impossible source or decision date") from exc
    if value.isoformat() != raw:
        raise FilingLookthroughStop("Noncanonical source date")
    return value


def _blob_sha(raw: bytes) -> str:
    return sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _fraction(raw: object) -> Decimal:
    if type(raw) is not str or not re.fullmatch(r"(?:0|1)(?:\.\d{1,6})?|0\.\d{1,6}", raw):
        raise FilingLookthroughStop("Use explicit unleveraged decimal fraction")
    try:
        x = Decimal(raw)
    except InvalidOperation as exc:
        raise FilingLookthroughStop("Invalid fraction") from exc
    if not Decimal(0) <= x <= Decimal(1):
        raise FilingLookthroughStop("Invalid or leveraged exposure")
    return x


def original_snapshots(*, root: Path = ROOT) -> dict[str, dict]:
    """Require unchanged original in-repo SEC research transcriptions."""
    if not isinstance(root, Path):
        raise FilingLookthroughStop("Source root must be a file path")
    data: dict[str, list[dict]] = {key: [] for key in EXPECTED}
    for filename, digest in SOURCE_BLOBS.items():
        raw = (root / SUBDIR / filename).read_bytes()
        if _blob_sha(raw) != digest:
            raise FilingLookthroughStop("Changed original SEC futures filing transcription")
        try:
            s = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise FilingLookthroughStop("Invalid original CSV encoding") from exc
        reader = csv.DictReader(s.splitlines())
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise FilingLookthroughStop("Original source schema changed")
        for item in reader:
            if set(item) != set(COLUMNS) or any(v is None for v in item.values()):
                raise FilingLookthroughStop("Malformed or truncated original futures holding")
            stmt = item["statement_date"]
            if stmt not in EXPECTED:
                raise FilingLookthroughStop("Unknown quarterly statement date")
            known = EXPECTED[stmt]
            if (item["available_date"] != known["available_date"]
                or item["sec_filing_date"] != known["filing_date"]
                or item["accession"] != known["accession"]
                or item["sector"] not in SECTORS
                or not re.fullmatch(r"\d{4}-\d{2}", item["delivery_month"])
                or not item["commodity"].strip()
                or not item["sec_filing_url"].startswith(
                    "https://www.sec.gov/Archives/edgar/data/1328237/")
                or item["accession"].replace("-", "") not in item["sec_filing_url"]):
                raise FilingLookthroughStop("Invalid original dated filing provenance")
            _date(stmt)
            if not (_date(stmt) < _date(known["filing_date"])
                    < _date(known["available_date"])):
                raise FilingLookthroughStop("Filing chronology is unavailable on decision date")
            for k in ("contracts", "notional_usd"):
                if not re.fullmatch(r"[1-9]\d*", item[k]):
                    raise FilingLookthroughStop("Negative, missing or noninteger futures notional")
            data[stmt].append(item)
    result = {}
    for stmt, records in data.items():
        known = EXPECTED[stmt]
        if (len(records) != known["count"] or
            len(set(x["commodity"] for x in records)) != len(records)):
            raise FilingLookthroughStop("Incomplete or duplicated original 28 commodity holdings")
        notional = sum(int(r["notional_usd"]) for r in records)
        if notional != known["notional"]:
            raise FilingLookthroughStop("Original gross futures notional reconciliation failed")
        sectors = {key: 0 for key in SECTORS}
        for row in records:
            sectors[row["sector"]] += int(row["notional_usd"])
        if sum(sectors.values()) != notional:
            raise FilingLookthroughStop("Cannot reconcile futures sectors")
        result[stmt] = {
            "statement_date": stmt,
            "filing_date": known["filing_date"],
            "available_date": known["available_date"],
            "accession": known["accession"],
            "original_sec_transcribed_contract_count": len(records),
            "gross_futures_notional_usd": notional,
            "gross_notional_by_sector_usd": sectors,
        }
    if set(result) != set(EXPECTED):
        raise FilingLookthroughStop("Original filing set missing")
    return result


def research_asof(*, decision_date: str, hypothetical_dbc_fraction: str = "0.15",
                  root: Path = ROOT) -> dict:
    t = _date(decision_date)
    w = _fraction(hypothetical_dbc_fraction)
    found = original_snapshots(root=root)
    allowed = [s for s in found.values() if _date(s["available_date"]) <= t]
    base = {
        "schema": SCHEMA,
        "research_decision_date": t.isoformat(),
        "hypothetical_dbc_sleeve_fraction": str(w),
        "original_csv_blob_shas": SOURCE_BLOBS,
        "source_original_sec_html_bytes_hashed_in_this_code": False,
        "source_is_transcribed_SEC_quarterly_open_futures_notional": True,
        "theoretical_dbiq_issuer_index_weights_are_not_fund_holdings": True,
        "dbc_commodity_futures_and_xle_energy_equity_are_not_same_exposure": True,
        "security_overlap_or_beta_independently_measured": False,
        "valid_as_current_fund_broker_weights": False,
        "usable_as_LIVE_allocator_risk_factor_weights": False,
        "measured_carry_profit_or_roll_PNL": False,
        "new_trade_authorized": False,
        "broker_request_count": 0,
        "paper_orders": 0, "live_orders": 0,
    }
    if not allowed:
        return {**base, "status": "NO_PUBLICLY_AVAILABLE_FILING_AT_DECISION_DATE",
                "chosen_statement_date": None,
                "sector_weights_fraction_of_reported_futures_notional": None,
                "hypothetical_DBC_sleeve_sector_mix_not_beta": None}
    source = max(allowed, key=lambda x: x["available_date"])
    total = Decimal(source["gross_futures_notional_usd"])
    fractions = {
        k: Decimal(v) / total
        for k, v in source["gross_notional_by_sector_usd"].items()
    }
    return {
        **base,
        "status": "AVAILABLE_HISTORICAL_SEC_TRANSCRIPTION_ONLY",
        "chosen_statement_date": source["statement_date"],
        "chosen_accession": source["accession"],
        "chosen_filing_date": source["filing_date"],
        "earliest_permissible_use_date": source["available_date"],
        "statement_age_calendar_days": (t - _date(source["statement_date"])).days,
        "days_since_filing_available": (t - _date(source["available_date"])).days,
        "dated_snapshot_not_current_daily_holdings": True,
        "gross_futures_notional_usd_not_fund_equity": source["gross_futures_notional_usd"],
        "original_reported_positions": source["original_sec_transcribed_contract_count"],
        "sector_weights_fraction_of_reported_futures_notional": {
            k: format(x.quantize(Decimal("0.00000001")), ".8f")
            for k, x in sorted(fractions.items())
        },
        "hypothetical_DBC_sleeve_sector_mix_not_beta": {
            k: format((w * x).quantize(Decimal("0.00000001")), ".8f")
            for k, x in sorted(fractions.items())
        },
    }


def main() -> None:
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-date", required=True)
    parser.add_argument("--hypothetical-dbc-fraction", default="0.15")
    args = parser.parse_args()
    result = research_asof(
        decision_date=args.decision_date,
        hypothetical_dbc_fraction=args.hypothetical_dbc_fraction,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
