"""SEC100 actual original annual-quality source is replayable, never a trade.

All 200 SEC HTTP calls here use injected deterministic fake bytes. The real
workflow can only call the existing bounded data.sec.gov official GET helper.
"""
from __future__ import annotations
from copy import deepcopy
import gzip
from hashlib import sha256
import json
from pathlib import Path

import pytest

import fund100_v8_sec100_original_annual_quality_source_v1_0 as mod
import fund100_stock_sec_source_p4b_v1_0 as sec
from test_fund100_stock_sec_quality_p4a_v1_0 import sample
from test_fund100_v7_u4_100issuer_original_sec_baseline_v1_0 import u3_files

AGENT = "FixtureLab genuine-test@fund100-laboratory.dev"
CAPTURED = "2026-11-09T12:10:00Z"


def make_u3(tmp_path):
    u3 = tmp_path / "u3"
    u3_files(u3)
    return u3


def sample_loader(*, bad_cik=False, missing=False, conflict=False):
    facts, submissions = sample()
    if missing:
        del facts["facts"]["us-gaap"]["Revenues"]
    if conflict:
        # Quarantine same-year structural fact contradictions, not all issuers.
        concept = next(iter(facts["facts"]["us-gaap"].values()))
        concept["units"]["USD"][0]["val"] = "not-an-int"
    records = []
    def load(url, agent):
        assert agent == AGENT
        assert url.startswith("https://data.sec.gov/")
        cik = url.split("CIK", 1)[1].split(".json")[0]
        assert len(cik) == 10
        doc = deepcopy(facts if "companyfacts" in url else submissions)
        doc["cik"] = int("0000000001" if bad_cik else cik)
        records.append(url)
        return json.dumps(doc, sort_keys=True).encode()
    return load, records


def save(root, report, raw):
    root.mkdir(parents=True, exist_ok=True)
    for path, data in raw.items():
        file = root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
    (root / "manifest.json").write_text(json.dumps(report, sort_keys=True))


def test_full_original_frozen_100_actual_format_companyfacts_and_submissions_replay(
        tmp_path):
    u3 = make_u3(tmp_path)
    loader, seen = sample_loader()
    report, archived = mod.collect(
        u3_dir=u3, agent=AGENT, loader=loader, clock=lambda: CAPTURED)
    assert len(seen) == 200
    assert len(archived) == 200
    assert len(set(seen)) == 200
    assert report["schema"] == mod.SCHEMA
    assert report["source_issuer_count"] == 100
    assert report["original_official_SEC_endpoint_get_count"] == 200
    assert report["source_quality_full_year_comparable_issuer_count"] == 100
    assert report["quarantined_structurally_conflicting_financials_count"] == 0
    assert all(row["quality_score"] == 3 for row in report["source_issuer_rows"])
    assert not report["full_stock_value_alpha_established"]
    assert not report["live_authorized"]
    assert report["broker_gets"] == report["broker_posts"] == report["broker_orders"] == 0
    assert report["private_git_writes"] == 0
    save(tmp_path / "original", report, archived)
    assert mod.verify(
        u3_dir=u3, report_dir=tmp_path / "original") == report
    for row in report["source_issuer_rows"]:
        assert row["original_official_source_received_utc"] == CAPTURED
        assert row["original_frozen_weight_rank"] >= 1
        assert not row["stock_share_count_or_market_price_verified"]
        assert not row["undervalued_stock_or_true_alpha_proven"]


def test_noncomparable_issuer_is_retained_as_missing_no_invented_quality(tmp_path):
    u3 = make_u3(tmp_path)
    loader, _ = sample_loader(missing=True)
    result, _ = mod.collect(
        u3_dir=u3, agent=AGENT, loader=loader, clock=lambda: CAPTURED)
    assert result["source_issuer_count"] == 100
    assert result["source_quality_full_year_comparable_issuer_count"] == 0
    assert all(x["quality_score"] is None for x in result["source_issuer_rows"])


def test_broken_reporting_conflicts_are_quarantined_not_backfilled(tmp_path):
    u3 = make_u3(tmp_path)
    loader, _ = sample_loader(conflict=True)
    r, _ = mod.collect(
        u3_dir=u3, agent=AGENT, loader=loader, clock=lambda: CAPTURED)
    assert r["source_issuer_count"] == 100
    assert r["source_quality_full_year_comparable_issuer_count"] == 0
    assert r["quarantined_structurally_conflicting_financials_count"] == 100
    assert all(x["latest_eligible_annual_accession"] is None
               for x in r["source_issuer_rows"])


def test_capture_before_actual_filing_availability_does_not_look_ahead(tmp_path):
    u3 = make_u3(tmp_path)
    loader, _ = sample_loader()
    r, _ = mod.collect(u3_dir=u3, agent=AGENT, loader=loader,
                       clock=lambda: "2026-11-04T12:10:00Z")
    assert r["source_quality_full_year_comparable_issuer_count"] == 0
    assert all(x["quality_score"] is None for x in r["source_issuer_rows"])


@pytest.mark.parametrize("fault", ["wrong_cik", "invalid_json", "missing_one", "extra_path"])
def test_incomplete_wrong_issuer_or_corrupt_official_source_fails_atomic(
        tmp_path, fault):
    u3 = make_u3(tmp_path)
    good, seen = sample_loader()
    def fake(url, agent):
        if fault == "wrong_cik":
            doc = json.loads(good(url, agent))
            doc["cik"] = 98765
            return json.dumps(doc).encode()
        if fault == "invalid_json":
            good(url, agent)
            return b"this is not SEC json"
        if fault == "missing_one" and url.endswith("submissions/CIK0000000001.json"):
            raise mod.OfficialQualityStop("Unavailable original official issuer")
        if fault == "extra_path" and "companyfacts" in url:
            doc = json.loads(good(url, agent))
            doc["cik"] = "FORGED"
            return json.dumps(doc).encode()
        return good(url, agent)
    with pytest.raises(Exception):
        mod.collect(u3_dir=u3, agent=AGENT, loader=fake,
                    clock=lambda: CAPTURED)
    assert not (tmp_path / "original").exists()


@pytest.mark.parametrize("fault", ["raw", "manifest", "gzip", "issuer_clock", "u3"])
def test_official_original_sha_manifest_roster_and_clock_tampering_fails_replay(
        tmp_path, fault):
    u3 = make_u3(tmp_path)
    raw_loader, _ = sample_loader()
    report, archive = mod.collect(
        u3_dir=u3, agent=AGENT, loader=raw_loader, clock=lambda: CAPTURED)
    root = tmp_path / "original"
    save(root, report, archive)
    target = root / next(iter(archive))
    if fault == "raw":
        data = gzip.decompress(target.read_bytes()).replace(b"120000000", b"999999999")
        target.write_bytes(gzip.compress(data, mtime=0))
    elif fault == "gzip":
        target.write_bytes(b"\x00" * 10)
    elif fault == "manifest":
        doc = json.loads((root / "manifest.json").read_text())
        doc["source_quality_full_year_comparable_issuer_count"] = 101
        (root / "manifest.json").write_text(json.dumps(doc))
    elif fault == "issuer_clock":
        doc = json.loads((root / "manifest.json").read_text())
        doc["source_issuer_rows"][0]["original_official_source_received_utc"] = (
            "2026-10-01T12:10:00Z")
        (root / "manifest.json").write_text(json.dumps(doc))
    elif fault == "u3":
        source = u3 / "U3-first-100-issuer-research-roster.json"
        doc = json.loads(source.read_text())
        doc["first_100_distinct_SEC_CIK_mapped_issuer_roster"][0]["ticker"] = "FAKE"
        source.write_text(json.dumps(doc))
    with pytest.raises(Exception):
        mod.verify(u3_dir=u3, report_dir=root)


def test_no_synthetic_current_100_vintage_relabels_historical_fund_or_live_trades(tmp_path):
    src = Path(mod.__file__).read_text()
    assert mod.ISSUERS == 100
    assert mod.NO_BROKER_NETWORK and mod.NO_BROKER_ORDERS
    assert mod.NO_PRIVATE_GIT_MUTATION and mod.NO_LIVE_STRATEGY_RELEASE
    for forbidden in ("ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
                      "requests.post(", "method=\"POST\"", "broker.submit("):
        assert forbidden not in src
    assert "original.original_issuer_roster(u3_dir)" in src
    assert "sec.fetch_one" in src
    assert "quality.asof_quality" in src
    with pytest.raises(mod.OfficialQualityStop):
        mod._name("../PRIVATE", "0000320193", "companyfacts")


def test_complete_source_size_and_clock_bounds_remain_atomic(tmp_path, monkeypatch):
    u3 = make_u3(tmp_path)
    load, seen = sample_loader()
    monkeypatch.setattr(mod, "MAX_TOTAL_ORIGINAL_JSON_BYTES", 100)
    with pytest.raises(mod.OfficialQualityStop, match="Unbounded"):
        mod.collect(u3_dir=u3, agent=AGENT, loader=load,
                    clock=lambda: CAPTURED)
    assert len(seen) <= 2
    monkeypatch.setattr(mod, "MAX_TOTAL_ORIGINAL_JSON_BYTES", 480_000_000)
    with pytest.raises(mod.OfficialQualityStop, match="predates"):
        mod.collect(u3_dir=u3, agent=AGENT, loader=load,
                    clock=lambda: "2026-10-01T12:00:00Z")
