"""Synthetic SEC facts and accession chronology. No real company data is invented."""
from __future__ import annotations

from copy import deepcopy
import json
import math

import pytest

import fund100_stock_sec_quality_p4a_v1_0 as p4a


CIK = "0000320193"
ACCESSIONS = ["0000320193-25-000001", "0000320193-26-000002"]
DATES = ["2025-10-31", "2026-10-30"]
FY_START = ["2024-11-01", "2025-11-01"]
FILINGS = ["2025-11-04", "2026-11-04"]


def sample():
    sub = {
        "cik": int(CIK),
        "filings": {"recent": {
            "accessionNumber": ACCESSIONS[:],
            "form": ["10-K", "10-K"],
            "filingDate": FILINGS[:],
            "reportDate": DATES[:],
            "acceptanceDateTime": [
                "2025-11-04T17:00:00.000Z",
                "2026-11-04T18:00:00.000Z",
            ],
        }},
    }
    facts = {"cik": int(CIK), "facts": {"us-gaap": {}}}
    amounts = {
        "revenue": (100_000_000, 120_000_000),
        "operating_income": (11_000_000, 18_000_000),
        "operating_cash_flow": (14_000_000, 20_000_000),
        "capital_expenditure": (4_000_000, 5_000_000),
    }
    for name, tag in p4a.ANNUAL_TAGS.items():
        facts["facts"]["us-gaap"][tag] = {
            "units": {"USD": [
                {
                    "accn": ACCESSIONS[i], "form": "10-K",
                    "filed": FILINGS[i], "start": FY_START[i],
                    "end": DATES[i], "val": val,
                }
                for i, val in enumerate(amounts[name])
            ]},
        }
    return facts, sub


def test_filing_date_gate_rejects_period_end_and_public_filing_day():
    f, s = sample()
    for d in ("2025-10-31", "2026-10-30", "2026-11-04", "2026-11-05"):
        out = p4a.asof_quality(f, s, CIK, d)
        assert out["score"] is None
    assert p4a.availability_day("2026-11-04") == "2026-11-06"
    out = p4a.asof_quality(f, s, CIK, "2026-11-06")
    assert out["score"] == 3
    assert out["source_accession"] == ACCESSIONS[-1]


def test_strict_annual_form_data_period_and_growth_quality_components():
    f, s = sample()
    result = p4a.asof_quality(f, s, CIK, "2026-12-01")
    assert result["revenue_growth_yoy"] == pytest.approx(.20)
    assert result["operating_margin"] == pytest.approx(.15)
    assert result["free_cash_flow_margin"] == pytest.approx(.125)
    assert result["score"] == 3
    assert result["score_max"] == 3


def test_no_analyst_revisions_delisting_assumptions_or_trading():
    f, s = sample()
    result = p4a.asof_quality(f, s, CIK, "2026-12-01")
    assert result["analyst_earnings_revision_signal"] is None
    assert result["source_historical_vintage_independently_archived"] is False
    assert result["point_in_time_stock_price_and_delistings_verified"] is False
    assert result["survivorship_safe_historical_backtest_eligible"] is False
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False
    assert result["broker_order_count"] == 0


def test_future_restatement_cannot_be_reused_as_original_annual_facts():
    f, s = sample()
    for concept in f["facts"]["us-gaap"].values():
        x = concept["units"]["USD"][0]
        # This is a 2025 fiscal comparative restated in the 2026 filing.
        x["accn"] = ACCESSIONS[-1]
        x["filed"] = FILINGS[-1]
    out = p4a.asof_quality(f, s, CIK, "2026-12-01")
    assert out["score"] is None
    assert out["state"] == "MISSING_ELIGIBLE_FULL_YEAR_FILINGS"


def test_unfiled_fact_cannot_be_reused_on_earlier_date():
    f, s = sample()
    for c in f["facts"]["us-gaap"].values():
        c["units"]["USD"][1]["filed"] = "2026-10-30"
    out = p4a.asof_quality(f, s, CIK, "2026-12-01")
    assert out["score"] is None


def test_quarter_and_year_to_date_rows_not_interpreted_as_full_year():
    f, s = sample()
    for concept in f["facts"]["us-gaap"].values():
        r = concept["units"]["USD"][1]
        r["start"] = "2026-08-01"
    assert p4a.asof_quality(f, s, CIK, "2026-12-01")["score"] is None


def test_no_imputation_when_quality_concept_missing():
    f, s = sample()
    del f["facts"]["us-gaap"][p4a.ANNUAL_TAGS["capital_expenditure"]]
    out = p4a.asof_quality(f, s, CIK, "2026-12-01")
    assert out["score"] is None


def test_no_conflation_of_different_filings_annual_facts():
    f, s = sample()
    f["facts"]["us-gaap"][p4a.ANNUAL_TAGS["operating_income"]]["units"]["USD"][1]["accn"] = ACCESSIONS[0]
    assert p4a.asof_quality(f, s, CIK, "2026-12-01")["score"] is None


def test_bad_cik_or_conflicting_duplicate_facts_refused():
    f, s = sample()
    with pytest.raises(p4a.StockSourceStop, match="CIK"):
        p4a.asof_quality(f, s, "0000000001", "2026-12-01")
    f, s = sample()
    duplicates = f["facts"]["us-gaap"][p4a.ANNUAL_TAGS["revenue"]]["units"]["USD"]
    disagree = deepcopy(duplicates[-1])
    disagree["val"] = 121_000_000
    duplicates.append(disagree)
    with pytest.raises(p4a.StockSourceStop, match="Conflicting"):
        p4a.asof_quality(f, s, CIK, "2026-12-01")


def test_incomplete_recent_arrays_and_duplicate_filing_accession_rejected():
    f, s = sample()
    s["filings"]["recent"]["reportDate"].pop()
    with pytest.raises(p4a.StockSourceStop, match="Inconsistent"):
        p4a.asof_quality(f, s, CIK, "2026-12-01")
    f, s = sample()
    s["filings"]["recent"]["accessionNumber"][0] = ACCESSIONS[1]
    with pytest.raises(p4a.StockSourceStop, match="Duplicate"):
        p4a.asof_quality(f, s, CIK, "2026-12-01")


def test_margins_below_thresholds_produce_low_not_fake_quality_score():
    f, s = sample()
    d = f["facts"]["us-gaap"]
    d[p4a.ANNUAL_TAGS["revenue"]]["units"]["USD"][1]["val"] = 95_000_000
    d[p4a.ANNUAL_TAGS["operating_income"]]["units"]["USD"][1]["val"] = 4_000_000
    d[p4a.ANNUAL_TAGS["operating_cash_flow"]]["units"]["USD"][1]["val"] = 3_000_000
    out = p4a.asof_quality(f, s, CIK, "2026-12-01")
    assert out["score"] == 0


def test_missing_old_10k_cannot_fabricate_annual_revenue_growth():
    f, s = sample()
    s["filings"]["recent"] = {k: v[1:] for k, v in s["filings"]["recent"].items()}
    r = p4a.asof_quality(f, s, CIK, "2026-12-01")
    assert r["score"] is None
    assert r["prior_annual_accession"] is None


def test_stale_filings_cannot_claim_current_quality():
    f, s = sample()
    assert p4a.asof_quality(f, s, CIK, "2030-01-01")["state"] == "LAST_ANNUAL_REPORT_TOO_STALE"


def test_invalid_date_and_non_finite_values_fail_closed():
    f, s = sample()
    with pytest.raises(p4a.StockSourceStop):
        p4a.asof_quality(f, s, CIK, "2026-02-30")
    f, s = sample()
    f["facts"]["us-gaap"][p4a.ANNUAL_TAGS["revenue"]]["units"]["USD"][1]["val"] = math.inf
    with pytest.raises(p4a.StockSourceStop, match="non-finite"):
        p4a.asof_quality(f, s, CIK, "2026-12-01")
