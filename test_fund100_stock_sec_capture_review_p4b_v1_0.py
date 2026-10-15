"""P4B genuine SEC two-company capture audit, never a stock trading signal."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import json
from pathlib import Path
import re

import pytest

REPORT = Path("research_lab/stocks/prospective/p4b_actual_sec_2026_10_15.json")


def source():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def validate(r):
    if r.get("schema") != "FUND100_P4B_FIRST_ACTUAL_SEC_QUALITY_CAPTURE_REVIEW_V1":
        raise ValueError("Unknown actual SEC capture record schema")
    captured = datetime.strptime(r["captured_at_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if captured.date() != date.fromisoformat(r["report_utc_asof_date"]):
        raise ValueError("Wrong original SEC acquisition date")
    if r["report_utc_asof_date"] < "2026-10-15":
        raise ValueError("Falsified prospective research start")
    if r["company_count"] != len(r["companies"]) or r["company_count"] != 2:
        raise ValueError("Missing original SEC source/company captures")
    if len({x["ticker"] for x in r["companies"]}) != 2:
        raise ValueError("Duplicated stock observation")
    if r["official_source_capture_types"] != ["companyfacts", "submissions"]:
        raise ValueError("Incorrect real SEC source classes")
    if not re.fullmatch(r"[0-9a-f]{64}", r["original_manifest_sha256"]):
        raise ValueError("Original SEC source manifest SHA missing")
    if not r["original_run_url"].endswith("/38746277418"):
        raise ValueError("Actual GitHub source run reference mismatch")
    if r["original_source_artifact_id"] != 11980335484:
        raise ValueError("Actual GitHub source artifact mismatch")
    for row in r["companies"]:
        if row["ticker"] not in ("AAPL", "MSFT"):
            raise ValueError("Unreviewed company")
        if row["cik"] not in ("0000320193", "0000789019"):
            raise ValueError("Invalid SEC identifier")
        if (date.fromisoformat(row["last_annual_available_date"]) >
            date.fromisoformat(r["report_utc_asof_date"])):
            raise ValueError("Stock quality uses a future SEC filing")
        if (date.fromisoformat(row["annual_period_end"]) >
            date.fromisoformat(row["last_annual_available_date"])):
            raise ValueError("Annual financial period unavailable at filing")
        if not 0 <= row["reported_quality_score"] <= row["maximum_quality_score"] == 3:
            raise ValueError("SEC quality score outside frozen 0–3 scale")
        for key in ("source_companyfacts_sha256", "source_submissions_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", row[key]):
                raise ValueError("Missing original SEC source exact raw SHA256")
        for key in ("revenue_growth_yoy", "operating_income_margin", "free_cash_flow_margin"):
            if not isinstance(row[key], (float, int)) or isinstance(row[key], bool):
                raise ValueError("Non-numeric actual SEC fundamental")
    for flag in (
        "quality_is_reported_annual_fundamentals_not_analyst_estimate_revision",
        "corpus_is_asof_2026_capture_not_independently_archived_historical_vintages",
        "company_cohort_is_2026_contemporaneous_not_survivorship_safe_history",
    ):
        if r[flag] is not True:
            raise ValueError("Source limitations missing")
    for flag in (
        "actual_stock_prices_or_executed_returns_measured",
        "historical_alpha_established", "analyst_revision_signal_available",
        "paper_authorized", "live_authorized",
    ):
        if r[flag] is not False:
            raise ValueError("Inaccurate implied stock performance/trading authority")
    if r["broker_orders"] != 0:
        raise ValueError("SEC score cannot place broker orders")


def test_actual_two_companies_and_filed_source_sha_evidence():
    r = source()
    validate(r)
    assert r["company_count"] == 2
    assert r["captured_at_utc"] == "2026-10-15T13:52:50Z"
    assert [x["ticker"] for x in r["companies"]] == ["AAPL", "MSFT"]
    assert r["artifact_retention_days"] == 90


def test_real_apple_reported_fundamentals_preserved_without_inventing_returns():
    a = source()["companies"][0]
    assert a["last_annual_accession"] == "0000320193-25-000079"
    assert a["annual_period_end"] == "2025-09-27"
    assert a["reported_quality_score"] == 3
    assert a["revenue_growth_yoy"] == pytest.approx(.06425512)
    assert a["operating_income_margin"] == pytest.approx(.319708)
    assert a["free_cash_flow_margin"] == pytest.approx(.23732882)


def test_real_microsoft_reported_fundamentals_from_different_fiscal_calendar():
    m = source()["companies"][1]
    assert m["last_annual_accession"] == "0001193125-26-323660"
    assert m["annual_period_end"] == "2026-06-30"
    assert m["last_annual_available_date"] == "2026-07-31"
    assert m["reported_quality_score"] == 3
    assert m["revenue_growth_yoy"] == pytest.approx(.17788687)
    assert m["operating_income_margin"] == pytest.approx(.46780818)
    assert m["free_cash_flow_margin"] == pytest.approx(.20186597)


def test_false_future_publication_date_will_not_backfill_capture():
    r = source()
    r["companies"][0]["last_annual_available_date"] = "2026-11-01"
    with pytest.raises(ValueError, match="future SEC"):
        validate(r)


def test_sources_are_current_asof_not_independently_archived_at_original_fiscal_year():
    r = source()
    assert r["corpus_is_asof_2026_capture_not_independently_archived_historical_vintages"]
    assert r["company_cohort_is_2026_contemporaneous_not_survivorship_safe_history"]
    assert not r["historical_alpha_established"]
    assert not r["analyst_revision_signal_available"]
    assert not r["actual_stock_prices_or_executed_returns_measured"]


def test_changing_original_source_hash_or_missing_accession_disallowed():
    r = source()
    r["companies"][1]["source_companyfacts_sha256"] = "missing"
    with pytest.raises(ValueError, match="raw SHA256"):
        validate(r)


def test_no_paper_or_live_auto_authorization_possible():
    original = source()
    for flag in ("paper_authorized", "live_authorized",
                 "historical_alpha_established",
                 "actual_stock_prices_or_executed_returns_measured"):
        r = deepcopy(original)
        r[flag] = True
        with pytest.raises(ValueError):
            validate(r)
    r = deepcopy(original)
    r["broker_orders"] = 1
    with pytest.raises(ValueError, match="broker orders"):
        validate(r)


def test_prospective_ledger_does_not_backdate_first_current_cohort():
    r = source()
    r["report_utc_asof_date"] = "2015-01-01"
    with pytest.raises(ValueError):
        validate(r)
