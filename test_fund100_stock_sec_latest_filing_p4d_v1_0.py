"""P4D missing latest original annual SEC facts: no false fallback to old year."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import pytest

import fund100_stock_sec_latest_filing_p4d_v1_0 as p4d
from test_fund100_stock_sec_quality_p4a_v1_0 import (
    sample, CIK, ACCESSIONS,
)
from test_fund100_stock_sec_forward_audit_p4c_v1_0 import prepared, fake_zip


def test_latest_complete_original_10k_score_retained_as_descriptive_only():
    f, s = sample()
    r = p4d.diagnose(f, s, CIK, "2026-12-01", 3, ACCESSIONS[1])
    assert r["status"] == "LATEST_10K_FIXED_SOURCE_FACTS_COMPLETE"
    assert r["latest_original_accession"] == ACCESSIONS[1]
    assert r["descriptive_score_after_latest_filing_gate"] == 3
    assert r["missing_original_concepts"] == []
    assert r["broker_orders"] == 0


def test_newer_annual_filing_missing_revenue_forbids_old_year_fallback():
    f, s = sample()
    tag = p4d.p4a.ANNUAL_TAGS["revenue"]
    f["facts"]["us-gaap"][tag]["units"]["USD"].pop()
    # Later 10-K exists, revenue for that accession is absent;
    # must not turn earlier complete financials into a current score.
    r = p4d.diagnose(f, s, CIK, "2026-12-01", 3, ACCESSIONS[0])
    assert r["latest_original_accession"] == ACCESSIONS[1]
    assert r["status"] == "LATEST_10K_NOT_ELIGIBLE_FOR_FROZEN_SCORE"
    assert "revenue" in r["missing_original_concepts"]
    assert r["descriptive_score_after_latest_filing_gate"] is None
    assert r["frozen_capture_score_not_rewritten"] == 3
    assert r["original_capture_accession_not_rewritten"] == ACCESSIONS[0]


def test_absent_tag_different_from_tag_present_but_no_current_annual_fact():
    f, s = sample()
    op = p4d.p4a.ANNUAL_TAGS["operating_income"]
    f["facts"]["us-gaap"].pop(op)
    r = p4d.diagnose(f, s, CIK, "2026-12-01", None, None)
    assert r["incomplete_fixed_source_details"]["operating_income"] == (
        "FIXED_GAAP_TAG_ABSENT_FROM_CURRENT_SEC_SOURCE"
    )
    f, s = sample()
    f["facts"]["us-gaap"][op]["units"]["USD"].pop()
    r = p4d.diagnose(f, s, CIK, "2026-12-01", None, None)
    assert r["incomplete_fixed_source_details"]["operating_income"] == (
        "NO_MATCHING_LATEST_ORIGINAL_FULL_YEAR_10K_FACT"
    )


def test_alternate_gaap_taxonomy_is_diagnostic_only_not_substituted():
    f, s = sample()
    tag = p4d.p4a.ANNUAL_TAGS["revenue"]
    f["facts"]["us-gaap"].pop(tag)
    f["facts"]["us-gaap"]["Revenues"] = {"units": {"USD": []}}
    out = p4d.diagnose(f, s, CIK, "2026-12-01", None, None)
    assert "Revenues" in out["alternate_US_GAAP_tags_PRESENT_ONLY_not_substituted"]["revenue"]
    assert out["descriptive_score_after_latest_filing_gate"] is None


def test_complete_latest_10k_mismatched_frozen_source_accession_gives_no_score():
    f, s = sample()
    r = p4d.diagnose(f, s, CIK, "2026-12-01", 3, ACCESSIONS[0])
    assert r["missing_original_concepts"] == []
    assert r["descriptive_score_after_latest_filing_gate"] is None


def test_no_unpublished_future_10k_data_on_filing_day():
    f, s = sample()
    r = p4d.diagnose(f, s, CIK, "2026-11-04", None, None)
    assert r["latest_original_accession"] == ACCESSIONS[0]
    assert r["descriptive_score_after_latest_filing_gate"] is None


def test_real_source_frozen_artifact_can_be_reviewed_without_sec_network(tmp_path):
    _, files = prepared()
    archive = tmp_path / "sec-capture.zip"
    fake_zip(archive, files)
    r = p4d.review_original_source_archive(archive)
    assert r["captured_company_count"] == 1
    assert r["latest_year_eligible_quality_count"] == 1
    assert r["companies"][0]["ticker"] == "AAPL"
    assert r["companies"][0]["descriptive_score_after_latest_filing_gate"] == 3
    assert not r["model_thresholds_changed"]
    assert not r["automatic_tag_substitutions_performed"]
    assert not r["older_p4b_p4c_prospective_results_mutated"]
    assert not r["paper_authorized"] and not r["live_authorized"]


def test_original_sec_source_bad_sha_fails_before_latest_filing_diagnosis(tmp_path):
    _, files = prepared()
    name = next(n for n in files if n.endswith("-companyfacts.json"))
    files[name] += b"not a reported SEC amendment"
    archive = tmp_path / "sec-capture.zip"
    fake_zip(archive, files)
    with pytest.raises(p4d.p4c.CohortAuditStop, match="SHA"):
        p4d.review_original_source_archive(archive)


def test_bad_fiscal_date_rejected_and_no_broker_implication():
    f, s = sample()
    with pytest.raises(p4d.p4a.StockSourceStop):
        p4d.diagnose(f, s, CIK, "2026-02-30", None, None)
    out = p4d.diagnose(f, s, CIK, "2026-12-01", 3, ACCESSIONS[1])
    assert out["analyst_estimate_revisions_available"] is False
    assert out["survivorship_safe_historical_backtest_eligible"] is False
    assert out["live_authorized"] is False
    assert out["paper_authorized"] is False
    assert out["broker_orders"] == 0
