"""P4Q synthetic SEC accession chronology, provenance and no-order tests."""
import hashlib
import json
from pathlib import Path
import re

import pytest

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_broad_sec_annual_replay_p4q_v1_0 as p4q
import fund100_stock_broad_sec_coverage_p4n_v1_0 as p4n
import fund100_stock_sec_quality_p4a_v1_0 as p4a
import fund100_stock_sec_source_p4b_v1_0 as p4b


AGENT = "Fund100 Research research@valid-firm.co.uk"


def _registry():
    frozen = {r["ticker"]: int(r["cik_10_digit"]) for r in p4b.read_cohort()}
    extra = sorted(set(p4l.SECTORS) - set(frozen))
    frozen.update({ticker: 9000000 + i for i, ticker in enumerate(extra)})
    return json.dumps({
        str(i): {"cik_str": cik, "ticker": ticker, "title": "Fixture " + ticker}
        for i, (ticker, cik) in enumerate(sorted(frozen.items()))
    }, sort_keys=True).encode()


def _fact(acc, filed, year, val):
    return {
        "accn": acc, "filed": filed, "form": "10-K",
        "start": f"{year}-01-01", "end": f"{year}-12-31", "val": val,
    }


def _source(url, agent):
    assert agent == AGENT
    cik = int(re.search(r"CIK(\d{10})\.json$", url).group(1))
    is_cat = cik == 9000000 + sorted(
        set(p4l.SECTORS) - {r["ticker"] for r in p4b.read_cohort()}
    ).index("CAT")
    years = [2025, 2024, 2023]
    filings = {
        "accessionNumber": [f"{cik:010d}-{y % 100:02d}-000001" for y in (2026, 2025, 2024)],
        "form": ["10-K"] * 3,
        "filingDate": [f"{y}-02-15" for y in (2026, 2025, 2024)],
        "reportDate": [f"{y}-12-31" for y in years],
        "acceptanceDateTime": [f"{y}-02-15T12:00:00Z" for y in (2026, 2025, 2024)],
    }
    if "/submissions/" in url:
        return json.dumps({"cik": cik, "filings": {"recent": filings}}).encode()
    concepts = {}
    if is_cat:
        # The 2025 filing revises the 2024 comparative from 120 to 150.
        # A replay of the original 2024 filing must still use 120.
        values = {
            "Revenues": ((110, 150), (120, 100), (100, 90)),
            "OperatingIncomeLoss": ((11, 30), (24, 20), (20, 18)),
            "NetCashProvidedByUsedInOperatingActivities": ((30, 40), (35, 30), (30, 28)),
            "PaymentsToAcquirePropertyPlantAndEquipment": ((20, 10), (10, 10), (10, 9)),
        }
        for tag, periods in values.items():
            rows = []
            for i, (current, comparative) in enumerate(periods):
                fy = years[i]
                acc = filings["accessionNumber"][i]
                filed = filings["filingDate"][i]
                rows += [_fact(acc, filed, fy, current),
                         _fact(acc, filed, fy - 1, comparative)]
            concepts[tag] = {"units": {"USD": rows}}
    return json.dumps({"cik": cik, "facts": {"us-gaap": concepts}}).encode()


@pytest.fixture
def archive(tmp_path):
    report, files = p4n.capture(
        user_agent=AGENT, registry=_registry(), loader=_source,
        captured_utc="2026-10-24T12:00:00Z",
    )
    for name, raw in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    (tmp_path / "manifest.json").write_text(json.dumps(report))
    return tmp_path


def test_historical_original_accession_replay_not_later_comparative(archive):
    out = p4q.evaluate(archive)
    assert out["new_issuers_verified"] == 16
    assert out["industrial_issuer_chronologies"] == 12
    assert out["sector_specific_issuers_not_replayed"] == ["CVX", "JPM", "LLY", "NEE"]
    assert out["industrial_annual_scores_available"] == 2
    assert out["industrial_annual_filing_dates_reviewed"] == 36
    cat = next(row for row in out["observations"] if row["ticker"] == "CAT")
    assert cat["annual_filing_dates_reviewed"] == 3
    assert [e["score"] for e in cat["annual_events"]] == [None, 3, 2]
    assert cat["annual_events"][1]["revenue_growth_yoy"] == .2
    assert cat["annual_events"][2]["revenue_growth_yoy"] < 0
    assert cat["annual_events"][1]["source_10k_accession"] != (
        cat["annual_events"][2]["source_10k_accession"])
    assert cat["annual_events"][1]["asof_conservative_available_date"] == (
        p4a.availability_day("2025-02-15"))
    assert out["original_accession_and_filed_day_used"]
    assert out["today_retrieved_companyfacts_not_original_historical_capture"]
    assert out["issuer_roster_selected_with_2026_knowledge"]
    assert not out["historical_investable_backtest_eligible"]
    assert not out["independent_alpha_validated"]
    assert not out["trading_authorized"] and not out["paper_authorized"]
    assert not out["live_authorized"]
    assert out["broker_requests"] == out["broker_orders"] == 0


def test_original_source_hash_tampering_fails_closed(archive):
    path = next((archive / "raw").glob("*-CAT-companyfacts.json"))
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(p4q.AnnualReplayStop, match="hash/size"):
        p4q.evaluate(archive)


def test_original_manifest_quality_must_reproduce(archive):
    path = archive / "manifest.json"
    report = json.loads(path.read_text())
    cat = next(row for row in report["observations"] if row["ticker"] == "CAT")
    cat["source_matched_latest_10k_quality"]["score"] = 0
    path.write_text(json.dumps(report))
    with pytest.raises(p4q.AnnualReplayStop, match="not reproducible"):
        p4q.evaluate(archive)


def test_missing_source_and_registry_identity_fails_closed(archive):
    (archive / "raw" / next((archive / "raw").iterdir()).name).unlink()
    with pytest.raises(p4q.AnnualReplayStop, match="incomplete"):
        p4q.evaluate(archive)


def test_incomplete_or_executable_manifest_rejected(archive):
    path = archive / "manifest.json"
    report = json.loads(path.read_text())
    report["trading_authorized"] = True
    path.write_text(json.dumps(report))
    with pytest.raises(p4q.AnnualReplayStop, match="executable"):
        p4q.evaluate(archive)


def test_historical_scores_are_missing_not_backfilled(archive):
    out = p4q.evaluate(archive)
    other = next(row for row in out["observations"] if row["ticker"] == "AVGO")
    assert other["annual_filing_dates_reviewed"] == 3
    assert other["available_score_count"] == 0
    assert all(event["score"] is None for event in other["annual_events"])
    assert out["sector_neutral_quality_or_valuation_not_validated"]


def test_canonical_capture_time_required(archive):
    path = archive / "manifest.json"
    report = json.loads(path.read_text())
    report["capture_timestamp_utc"] = "2026-10-24T12:00:00+00:00"
    path.write_text(json.dumps(report))
    with pytest.raises(p4q.AnnualReplayStop, match="timestamp"):
        p4q.evaluate(archive)
