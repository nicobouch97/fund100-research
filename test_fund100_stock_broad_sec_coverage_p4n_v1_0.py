"""Offline, brokerless P4N official-identity and source-provenance tests."""
import hashlib
import json
import re

import pytest

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_broad_sec_coverage_p4n_v1_0 as p4n
import fund100_stock_sec_source_p4b_v1_0 as p4b


AGENT = "Fund100 Research research@valid-firm.co.uk"


def registry_obj():
    frozen = {r["ticker"]: int(r["cik_10_digit"]) for r in p4b.read_cohort()}
    extra = sorted(set(p4l.SECTORS) - set(frozen))
    values = dict(frozen)
    values.update({ticker: 9_000_000 + i for i, ticker in enumerate(extra)})
    return {str(i): {"cik_str": cik, "ticker": ticker,
                     "title": "Official example fixture " + ticker}
            for i, (ticker, cik) in enumerate(sorted(values.items()))}


def raw_registry(obj=None):
    return json.dumps(registry_obj() if obj is None else obj, sort_keys=True).encode()


def fake_loader(url, agent):
    assert agent == AGENT
    match = re.search(r"CIK(\d{10})\.json$", url)
    assert match
    cik = int(match.group(1))
    if "/companyfacts/" in url:
        doc = {"cik": cik, "facts": {"us-gaap": {}}}
    else:
        doc = {"cik": cik, "filings": {"recent": {
            "accessionNumber": [f"{cik:010d}-26-000001", f"{cik:010d}-25-000001"],
            "form": ["10-K", "10-K"],
            "filingDate": ["2026-02-13", "2025-02-13"],
            "reportDate": ["2025-12-31", "2024-12-31"],
            "acceptanceDateTime": ["2026-02-13T12:00:00Z", "2025-02-13T12:00:00Z"],
        }}}
    return json.dumps(doc, sort_keys=True).encode()


@pytest.fixture
def patched_quality(monkeypatch):
    def generic_quality(facts, submissions, cik, asof):
        assert asof == "2026-10-24"
        assert facts["cik"] == submissions["cik"] == int(cik)
        return {"state": "MISSING_GENERIC_GAAP_TAGS", "score": None,
                "paper_authorized": False, "live_authorized": False}
    monkeypatch.setattr(p4n.p4a, "asof_quality", generic_quality)


def test_original_eight_identity_and_exact_new_sixteen_roster():
    ids = p4n.resolve_registry(raw_registry())
    assert set(ids) == set(p4l.SECTORS)
    assert len(ids) == 24 and len(set(ids.values())) == 24
    assert len(set(ids) - {r["ticker"] for r in p4b.read_cohort()}) == 16


def test_source_capture_hashes_missing_scores_and_no_trading(patched_quality):
    registry = raw_registry()
    report, files = p4n.capture(
        user_agent=AGENT, registry=registry, loader=fake_loader,
        captured_utc="2026-10-24T05:30:00Z",
    )
    assert report["new_issuers_captured"] == 16
    assert report["source_count"] == 32
    assert report["new_issuers_generic_score_available"] == 0
    assert report["new_issuers_source_matched_score_available"] == 0
    assert report["new_issuer_source_matched_scores_are_descriptive_not_trade_ready"]
    assert len(p4n.SOURCE_MATCHED_TAGS) == 12
    assert len(p4n.UNRESOLVED_ACCOUNTING) == 4
    assert report["official_registry_sha256"] == hashlib.sha256(registry).hexdigest()
    assert files["official-sec-ticker-registry.json"] == registry
    assert not report["historic_stock_alpha_backtest_eligible"]
    assert not report["new_issuer_specific_accounting_review_complete"]
    assert not report["sector_neutral_quality_comparison_validated"]
    assert not report["trading_authorized"] and not report["paper_authorized"]
    assert not report["live_authorized"] and report["broker_orders"] == 0
    for row in report["observations"]:
        assert row["missing_generic_quality_remains_missing"]
        assert not row["fundamental_quality_for_trading_approved"]
        for provenance in row["source_provenance"].values():
            data = files[provenance["source_file"]]
            assert hashlib.sha256(data).hexdigest() == provenance["raw_sha256"]
            assert len(data) == provenance["byte_count"]


def test_limit_does_not_claim_full_coverage(patched_quality):
    report, files = p4n.capture(
        user_agent=AGENT, registry=raw_registry(), loader=fake_loader,
        captured_utc="2026-10-24T05:30:00Z", limit=2)
    assert report["new_issuers_in_roster"] == 16
    assert report["new_issuers_captured"] == 2
    assert report["source_count"] == 4 and len(files) == 5


def test_missing_duplicate_and_changed_frozen_identity_rejected():
    data = registry_obj()
    removed = dict(data)
    removed.pop(next(iter(removed)))
    with pytest.raises(p4n.BroadSecStop, match="Incomplete"):
        p4n.resolve_registry(raw_registry(removed))
    duplicate = dict(data)
    duplicate["extra"] = dict(next(iter(data.values())))
    with pytest.raises(p4n.BroadSecStop, match="Duplicate"):
        p4n.resolve_registry(raw_registry(duplicate))
    mismatch = dict(data)
    frozen_ticker = p4b.read_cohort()[0]["ticker"]
    entry = next(v for v in mismatch.values() if v["ticker"] == frozen_ticker)
    entry["cik_str"] = 8888888
    with pytest.raises(p4n.BroadSecStop, match="conflicts"):
        p4n.resolve_registry(raw_registry(mismatch))



def test_official_ticker_cik_drift_quarantined_not_rewritten(patched_quality):
    # The official SEC registry can change a ticker's registrant CIK.
    # P4E's 2026 frozen issuer evidence must NEVER be silently rekeyed.
    registry = registry_obj()
    xom = next(v for v in registry.values() if v["ticker"] == "XOM")
    frozen = next(r["cik_10_digit"] for r in p4b.read_cohort()
                  if r["ticker"] == "XOM")
    xom["cik_str"] = 2115436
    assert f"{xom['cik_str']:010d}" != frozen
    with pytest.raises(p4n.BroadSecStop, match="conflicts"):
        p4n.resolve_registry(raw_registry(registry))
    report, files = p4n.capture(
        user_agent=AGENT, registry=raw_registry(registry),
        loader=fake_loader, captured_utc="2026-10-24T05:30:00Z")
    assert report["new_issuers_captured"] == 16
    assert report["source_count"] == 32
    assert not report["original_eight_registry_identity_all_match"]
    assert report["original_eight_identity_drift_quarantined"] == [{
        "ticker": "XOM", "frozen_p4e_cik": frozen,
        "current_sec_registry_cik": "0002115436"}]
    assert report["drifted_original_eight_issuer_scores_not_joined_to_current_cik"]
    assert all(row["ticker"] != "XOM" for row in report["observations"])
    assert not report["trading_authorized"] and report["broker_orders"] == 0


def test_source_identity_mismatch_fails_before_any_report(patched_quality):
    def bad_loader(url, agent):
        obj = json.loads(fake_loader(url, agent))
        obj["cik"] += 1
        return json.dumps(obj).encode()
    with pytest.raises(p4b.SecIntakeStop, match="identity"):
        p4n.capture(user_agent=AGENT, registry=raw_registry(),
                    loader=bad_loader, captured_utc="2026-10-24T05:30:00Z")


@pytest.mark.parametrize("bad", ["bad", "2026-10-24T05:30:00+00:00", None])
def test_noncanonical_clock_rejected(bad, patched_quality):
    with pytest.raises(p4n.BroadSecStop, match="Canonical"):
        p4n.capture(user_agent=AGENT, registry=raw_registry(),
                    loader=fake_loader, captured_utc=bad or "bad")


def test_oversized_registry_and_invalid_limits_rejected(patched_quality):
    with pytest.raises(p4n.BroadSecStop, match="oversized"):
        p4n.resolve_registry(b" " * (p4n.REGISTRY_LIMIT + 1))
    for limit in (0, 17, True):
        with pytest.raises(p4n.BroadSecStop, match="limit"):
            p4n.capture(user_agent=AGENT, registry=raw_registry(),
                        loader=fake_loader, limit=limit,
                        captured_utc="2026-10-24T05:30:00Z")


def test_source_matched_latest_10k_comparatives_are_causal_and_not_trade_ready():
    ticker, cik = "CAT", "0000018230"
    accession = "0000018230-26-000008"
    filings = {"cik": int(cik), "filings": {"recent": {
        "accessionNumber": [accession, "0000018230-25-000008"],
        "form": ["10-K", "10-K"],
        "filingDate": ["2026-02-13", "2025-02-13"],
        "reportDate": ["2025-12-31", "2024-12-31"],
        "acceptanceDateTime": ["2026-02-13T12:00:00Z", "2025-02-13T12:00:00Z"],
    }}}
    tags = {
        "Revenues": (1100, 1000),
        "OperatingIncomeLoss": (220, 200),
        "NetCashProvidedByUsedInOperatingActivities": (300, 280),
        "PaymentsToAcquirePropertyPlantAndEquipment": (100, 90),
    }
    concepts = {}
    for tag, (now, prior) in tags.items():
        concepts[tag] = {"units": {"USD": [
            {"accn": accession, "filed": "2026-02-13", "form": "10-K",
             "start": "2025-01-01", "end": "2025-12-31", "val": now},
            {"accn": accession, "filed": "2026-02-13", "form": "10-K",
             "start": "2024-01-01", "end": "2024-12-31", "val": prior},
        ]}}
    facts = {"cik": int(cik), "facts": {"us-gaap": concepts}}
    result = p4n.source_matched_annual_quality(
        facts, filings, cik, ticker, "2026-10-24")
    assert result["state"] == "SOURCE_MATCHED_LATEST_10K_DESCRIPTIVE_ONLY"
    assert result["score"] == 3
    assert result["latest_10k_accession"] == accession
    assert result["comparative_from_same_latest_accession"]
    assert not result["cross_sector_economics_reviewed"]
    assert not result["for_trading_approved"]
    assert result["revenue_growth_yoy"] == .1
    # Never infer the comparative from a different 10-K accession.
    altered = json.loads(json.dumps(facts))
    altered["facts"]["us-gaap"]["Revenues"]["units"]["USD"][1]["accn"] = (
        "0000018230-25-000008")
    missing = p4n.source_matched_annual_quality(
        altered, filings, cik, ticker, "2026-10-24")
    assert missing["score"] is None
    assert missing["state"] == "LATEST_10K_MISSING_SAME_ACCESSION_COMPARATIVE"
    # Before the filing's conservative publication lag, latest report unavailable.
    before = p4n.source_matched_annual_quality(
        facts, filings, cik, ticker, "2026-02-13")
    assert before["score"] is None
    assert before["state"] == "INSUFFICIENT_10K_CHRONOLOGY"
    # A later restated current-period fact with a different accession
    # cannot overwrite this accession's original source observation.
    restated = json.loads(json.dumps(facts))
    restated["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append({
        "accn": "0000018230-26-000099", "filed": "2026-09-01",
        "form": "10-K/A", "start": "2025-01-01",
        "end": "2025-12-31", "val": 99999})
    assert p4n.source_matched_annual_quality(
        restated, filings, cik, ticker, "2026-10-24")["score"] == 3


def test_unresolved_issuer_never_gets_a_source_matched_quality_score():
    for ticker in p4n.UNRESOLVED_ACCOUNTING:
        cik = "0000093410"
        facts = {"cik": int(cik), "facts": {"us-gaap": {}}}
        submissions = {"cik": int(cik), "filings": {"recent": {}}}
        result = p4n.source_matched_annual_quality(
            facts, submissions, cik, ticker, "2026-10-24")
        assert result["score"] is None
        assert not result["for_trading_approved"]
        assert result["state"] == p4n.UNRESOLVED_ACCOUNTING[ticker]


def test_source_matched_mapping_covers_exactly_the_original_new_sixteen():
    new = set(p4l.SECTORS) - {r["ticker"] for r in p4b.read_cohort()}
    assert set(p4n.SOURCE_MATCHED_TAGS).isdisjoint(p4n.UNRESOLVED_ACCOUNTING)
    assert set(p4n.SOURCE_MATCHED_TAGS) | set(p4n.UNRESOLVED_ACCOUNTING) == new


def jpm_2026_original_10k_source_derived_fixture():
    """2025/2024 JPM figures from official SEC P4N archive run 40069130408.

    Minimal reproducible accession-linked excerpt, not a replacement for
    the original archived SEC companyfacts or an independent data vintage.
    Amounts are original USD values; no broker credentials or order paths.
    """
    cik = "0000019617"
    acc = "0001628280-26-008131"
    values = {
        "InterestIncomeExpenseNet": (95443000000, 92583000000),
        "NoninterestIncome": (87004000000, 84973000000),
        "NoninterestExpense": (95640000000, 91797000000),
        "RevenuesNetOfInterestExpense": (182447000000, 177556000000),
    }
    concepts = {}
    for tag, (current, prior) in values.items():
        concepts[tag] = {"units": {"USD": [
            {"accn": acc, "filed": "2026-02-13", "form": "10-K",
             "start": "2025-01-01", "end": "2025-12-31", "val": current},
            {"accn": acc, "filed": "2026-02-13", "form": "10-K",
             "start": "2024-01-01", "end": "2024-12-31", "val": prior},
        ]}}
    facts = {"cik": int(cik), "facts": {"us-gaap": concepts}}
    submissions = {"cik": int(cik), "filings": {"recent": {
        # JPM's genuine SEC recent index contains only this one 10-K.
        # The 2024 annual comparative is within its 2025 accession.
        "accessionNumber": [acc],
        "form": ["10-K"],
        "filingDate": ["2026-02-13"],
        "reportDate": ["2025-12-31"],
        "acceptanceDateTime": ["2026-02-13T12:00:00Z"],
    }}}
    return cik, facts, submissions


def test_jpm_bank_diagnostics_from_archived_sec_values_not_industrial_score():
    cik, facts, subs = jpm_2026_original_10k_source_derived_fixture()
    q = p4n.source_matched_annual_quality(facts, subs, cik, "JPM", "2026-10-24")
    assert q["score"] is None
    assert q["state"] == "BANK_NET_INTEREST_AND_CASH_FLOW_MODEL_REQUIRED"
    b = q["bank_diagnostics"]
    assert b["state"] == "BANK_LATEST_10K_DESCRIPTIVE_ONLY"
    assert b["latest_10k_accession"] == "0001628280-26-008131"
    assert b["net_revenue_identity_reconciled_both_years"]
    assert b["current_efficiency_ratio"] == pytest.approx(.52420703)
    assert b["prior_efficiency_ratio"] == pytest.approx(.51700309)
    assert b["efficiency_ratio_change_percentage_points"] == pytest.approx(.720394)
    assert b["net_revenue_growth_yoy"] == pytest.approx(.02754624)
    assert b["current_net_interest_revenue_share"] == pytest.approx(.52312726)
    assert b["bank_specific_diagnostic_not_industrial_fcf_score"]
    assert not b["cross_sector_comparison_approved"] and not b["for_trading_approved"]


def test_jpm_diagnostics_reject_future_filing_missing_comparative_and_bad_bridge():
    cik, facts, subs = jpm_2026_original_10k_source_derived_fixture()
    before = p4n.jpm_bank_annual_diagnostics(facts, subs, cik, "2026-02-13")
    assert before["state"] == "BANK_10K_UNAVAILABLE"
    assert before["current_efficiency_ratio"] is None

    missing = json.loads(json.dumps(facts))
    missing["facts"]["us-gaap"]["NoninterestExpense"]["units"]["USD"][1][
        "accn"] = "0000019617-25-000001"
    q = p4n.jpm_bank_annual_diagnostics(missing, subs, cik, "2026-10-24")
    assert q["state"] == "BANK_MISSING_SAME_ACCESSION_COMPARATIVE"
    assert q["current_efficiency_ratio"] is None

    mismatched = json.loads(json.dumps(facts))
    mismatched["facts"]["us-gaap"]["RevenuesNetOfInterestExpense"][
        "units"]["USD"][0]["val"] = 190000000000
    q = p4n.jpm_bank_annual_diagnostics(mismatched, subs, cik, "2026-10-24")
    assert q["state"] == "BANK_NET_REVENUE_IDENTITY_MISMATCH"
    assert not q["net_revenue_identity_reconciled_both_years"]
    assert q["current_efficiency_ratio"] is None

    # A changed bank FY convention must be reviewed, not inferred.
    bad_year_end = json.loads(json.dumps(subs))
    bad_year_end["filings"]["recent"]["reportDate"][0] = "2025-12-30"
    q = p4n.jpm_bank_annual_diagnostics(
        facts, bad_year_end, cik, "2026-10-24")
    assert q["state"] == "BANK_UNEXPECTED_FISCAL_YEAR_END"

    # Later restatement accession must not rewrite the latest 10-K's facts.
    later = json.loads(json.dumps(facts))
    later["facts"]["us-gaap"]["NoninterestExpense"]["units"]["USD"].append({
        "accn": "0001628280-26-999999", "filed": "2026-09-01",
        "form": "10-K/A", "start": "2025-01-01", "end": "2025-12-31",
        "val": 999999999999,
    })
    q = p4n.jpm_bank_annual_diagnostics(later, subs, cik, "2026-10-24")
    assert q["current_efficiency_ratio"] == pytest.approx(.52420703)
