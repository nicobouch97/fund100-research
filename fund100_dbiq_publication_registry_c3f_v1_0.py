"""C3F: official DBIQ commodity contract-selection publication registry.

Issuer DBIQ public publications catalogue lists monthly 'Optimum Yield
indices Selection Report' PDFs, but a name/date is NOT the PDF body,
a specific DBLCDBCE selected contract, basket weight, realized roll
profit, or proof the PDF was available at a timezone-specific moment.

This module refuses strategy promotion without verified, hash-bound
source document bytes and manually reviewed report-row provenance.
Network and brokerage free; NO PDF is supplied or pretended to exist.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

REGISTRY_FILE = Path(
    "research_lab/commodities/dbiq_official_selection_report_registry_2025_2026.csv"
)
INDEX_CODE = "DBLCDBCE"
OFFICIAL_INDEX_PAGE = "https://index.db.com/dbiq-web/indices/95400"
OFFICIAL_PUBLICATIONS_PAGE = "https://dbindex.db.com/dbiq-web/publications"
REGISTRY_COLUMNS = (
    "report_month", "official_document_title",
    "issuer_site_listed_date", "issuer_site_listed_clock_timezone_unknown",
    "portal_url", "source_class", "official_pdf_bytes_acquired",
    "document_verified_for_dbc_constituents",
)
FIRST_MONTH = "2025-11"
LAST_MONTH = "2026-10"


class IssuerEvidenceStop(ValueError):
    pass


def _canonical_date(value: str, *, name: str) -> pd.Timestamp:
    if not isinstance(value, str) or not re.fullmatch(r"20\d\d-(0[1-9]|1[0-2])-([0-2]\d|3[01])", value):
        raise IssuerEvidenceStop(f"{name} must be ISO yyyy-mm-dd.")
    try:
        parsed = pd.Timestamp(value)
    except (ValueError, TypeError) as exc:
        raise IssuerEvidenceStop(f"Invalid {name}.") from exc
    if parsed.date().isoformat() != value:
        raise IssuerEvidenceStop(f"Invalid {name}.")
    return parsed


def validate_registry(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or set(raw.columns) != set(REGISTRY_COLUMNS):
        raise IssuerEvidenceStop("Incomplete official DBIQ publication source schema.")
    data = raw.loc[:, list(REGISTRY_COLUMNS)].copy()
    expected_months = pd.period_range(FIRST_MONTH, LAST_MONTH, freq="M")
    if len(data) != len(expected_months) or data["report_month"].tolist() != [
        str(month) for month in expected_months
    ]:
        raise IssuerEvidenceStop("Expected all twelve chronological issuer report months.")
    for i, row in enumerate(data.itertuples(index=False)):
        expected = expected_months[i]
        name = f"DBIQ Optimum Yield indices Selection Report {expected.start_time.strftime('%b %y')}.pdf"
        if row.official_document_title != name:
            raise IssuerEvidenceStop("Issuer source document title differs from indexed catalogue.")
        published = _canonical_date(row.issuer_site_listed_date, name="issuer site publication date")
        # Reports are published within the named report month,
        # but are not assumed available on the first trading session.
        if published.to_period("M") != expected:
            raise IssuerEvidenceStop("Issuer publication date not in actual report month.")
        if not isinstance(row.issuer_site_listed_clock_timezone_unknown, str) or not re.fullmatch(
            r"([01]\d|2[0-3]):[0-5]\d", row.issuer_site_listed_clock_timezone_unknown
        ):
            raise IssuerEvidenceStop("Original website listing clock missing or invalid.")
        if row.portal_url != OFFICIAL_PUBLICATIONS_PAGE:
            raise IssuerEvidenceStop("Official issuer provenance source changed.")
        if row.source_class != "ISSUER_MONTHLY_SELECTION_REPORT":
            raise IssuerEvidenceStop("Unsupported class of contract selection publication.")
        if row.official_pdf_bytes_acquired != "false" or row.document_verified_for_dbc_constituents != "false":
            raise IssuerEvidenceStop("Registry tracks publication listing, NOT a downloaded/verified PDF.")
    return data


def load_registry(path: Path = REGISTRY_FILE) -> pd.DataFrame:
    # Force literals, not auto-coerced bools or date/time fields.
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    return validate_registry(raw)


def conservative_first_eligible_day(published_date: str) -> str:
    """Research *calendar proxy*, NOT independent publication-time proof.

    Advance two weekday sessions from the listed date. We deliberately
    do not claim US exchange holiday support or verified DBIQ website TZ.
    """
    day = _canonical_date(published_date, name="issuer report publication date")
    return (day + pd.offsets.BDay(2)).date().isoformat()


def visible_publications_on(registry: pd.DataFrame, asof_date: str) -> list[str]:
    rows = validate_registry(registry)
    current = _canonical_date(asof_date, name="as-of date")
    return [
        row.report_month
        for row in rows.itertuples(index=False)
        if pd.Timestamp(conservative_first_eligible_day(row.issuer_site_listed_date)) <= current
    ]


def validate_pdf_evidence(
    *, report_month: str, pdf_bytes: bytes, evidence: dict, registry: pd.DataFrame
) -> dict:
    """Validate separately acquired genuine source PDF; never fabricate content.

    This verifies document format, digest and source declaration only.
    It intentionally does not claim to have authenticated PDF contents,
    identified a DBC basket contract, or demonstrated future lookahead.
    """
    rows = validate_registry(registry)
    matches = rows.loc[rows["report_month"] == report_month]
    if len(matches) != 1:
        raise IssuerEvidenceStop("Monthly issuer document not catalogued.")
    item = matches.iloc[0]
    if not isinstance(pdf_bytes, bytes) or len(pdf_bytes) < 500 or not pdf_bytes.startswith(b"%PDF-"):
        raise IssuerEvidenceStop("Not actual nontrivial PDF source bytes.")
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    keys = {
        "report_month", "document_title", "publisher_page_url",
        "actual_pdf_url", "source_pdf_sha256", "acquired_at_utc",
        "right_to_store_and_analyze", "manual_content_review_performed",
    }
    if not isinstance(evidence, dict) or set(evidence) != keys:
        raise IssuerEvidenceStop("Source-document evidence manifest incomplete.")
    if (
        evidence["report_month"] != report_month
        or evidence["document_title"] != item["official_document_title"]
        or evidence["publisher_page_url"] != OFFICIAL_PUBLICATIONS_PAGE
        or evidence["source_pdf_sha256"] != digest
    ):
        raise IssuerEvidenceStop("Issuer PDF not bound to catalogued report and exact SHA256.")
    pdf_url = urlparse(str(evidence["actual_pdf_url"]))
    if pdf_url.scheme != "https" or not pdf_url.netloc:
        raise IssuerEvidenceStop("Verified actual PDF source URL must use HTTPS.")
    instant = evidence["acquired_at_utc"]
    if not isinstance(instant, str) or not re.fullmatch(
        r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ", instant
    ):
        raise IssuerEvidenceStop("Actual document-acquisition UTC timestamp required.")
    acquired = pd.Timestamp(instant)
    if acquired < pd.Timestamp(item["issuer_site_listed_date"], tz="UTC"):
        raise IssuerEvidenceStop("Cannot have acquired the report before indexed publication date.")
    if evidence["right_to_store_and_analyze"] is not True:
        raise IssuerEvidenceStop("Permission to store source document not established.")
    if not isinstance(evidence["manual_content_review_performed"], bool):
        raise IssuerEvidenceStop("Manual review status must be explicit.")
    return {
        "report_month": report_month,
        "pdf_sha256": digest,
        "issuer_publication_date": item["issuer_site_listed_date"],
        "pdf_acquired_at_utc": instant,
        "pdf_source_url": evidence["actual_pdf_url"],
        "manual_content_review_performed": evidence["manual_content_review_performed"],
        "issuer_contract_mapping_confirmed": False,
        "dbc_index_constituent_rolls_confirmed": False,
        "live_or_paper_trade_authorized": False,
    }


def report(registry: pd.DataFrame, source_sha256: str) -> dict:
    items = validate_registry(registry)
    listed = [
        {
            "month": item.report_month,
            "issuer_title": item.official_document_title,
            "issuer_listing_date": item.issuer_site_listed_date,
            "issuer_listing_time_timezone": "NOT_DISCLOSED",
            "issuer_site_clock": item.issuer_site_listed_clock_timezone_unknown,
            "first_conservative_research_calendar_day":
                conservative_first_eligible_day(item.issuer_site_listed_date),
            "pdf_bytes_downloaded": False,
            "contract_selection_extracted": False,
            "source_page": item.portal_url,
        }
        for item in items.itertuples(index=False)
    ]
    return {
        "schema": "FUND100_DBIQ_C3F_OFFICIAL_SELECTION_REPORT_REGISTRY_V1",
        "status": "OFFICIAL_PUBLICATION_METADATA_ONLY_NO_ROLL_PNL",
        "index_name": "DBIQ Optimum Yield Diversified Commodity Index Excess Return",
        "official_index_ticker": INDEX_CODE,
        "source_index_page": OFFICIAL_INDEX_PAGE,
        "source_publication_catalogue": OFFICIAL_PUBLICATIONS_PAGE,
        "source_sha256": source_sha256,
        "reports_listed": len(listed),
        "listed": listed,
        "first_listed_month": listed[0]["month"],
        "last_listed_month": listed[-1]["month"],
        "source_page_does_not_reveal_pdf_bytes": True,
        "individual_commodity_subindex_selections_may_not_equal_dbc_basket": True,
        "issuer_index_guidance_pdf_discovered_but_unverified": True,
        "issuer_annual_2025_weights_pdf_discovered_but_unverified": True,
        "issuance_timezone_confirmed": False,
        "release_vintages_confirmed": False,
        "contract_expiries_confirmed": False,
        "underlying_futures_settlement_quotes_available": False,
        "strategy_carry_pnl_validated": False,
        "historical_backtest_eligible": False,
        "trading_authorized": False,
        "paper_authorized": False,
        "live_authorized": False,
        "broker_order_count": 0,
        "publication_asof_examples": {
            day: visible_publications_on(items, day)
            for day in ("2025-11-03", "2025-11-05", "2025-12-01",
                        "2026-01-01", "2026-03-02", "2026-03-04",
                        "2026-10-01", "2026-10-05")
        },
    }


def main() -> None:
    import argparse
    cli = argparse.ArgumentParser()
    cli.add_argument("--output-json", required=True)
    args = cli.parse_args()
    raw = REGISTRY_FILE.read_bytes()
    overview = report(load_registry(), hashlib.sha256(raw).hexdigest())
    Path(args.output_json).write_text(json.dumps(overview, indent=2, sort_keys=True) + "\n")
    print("C3F official DBIQ selection-report publications:", overview["reports_listed"])
    print("Published issuer listings:", overview["first_listed_month"], "to", overview["last_listed_month"])
    print("PDF source bodies or annual index weights downloaded: NO")
    print("DBC actual contract roll, carry PnL, or futures quotes: NO")
    print("No trading permissions, broker calls or PAPER/LIVE orders.")


if __name__ == "__main__":
    main()
