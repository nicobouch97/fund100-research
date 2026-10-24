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
    match = re.search(r"CIK(\\d{10})\\.json$", url)
    assert match
    cik = int(match.group(1))
    if "/companyfacts/" in url:
        doc = {"cik": cik, "facts": {"us-gaap": {}}}
    else:
        doc = {"cik": cik, "filings": {"recent": {}}}
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
