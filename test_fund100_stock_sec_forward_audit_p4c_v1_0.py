"""Phase 4C genuine-source structural tests. All numbers are synthetic fixtures.

This suite makes ZERO external network calls; real SEC source ZIPs can
be validated separately through the CLI only.
"""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
import json
import zipfile

import pytest

import fund100_stock_sec_forward_audit_p4c_v1_0 as p4c
import fund100_stock_sec_source_p4b_v1_0 as intake
from test_fund100_stock_sec_source_p4b_v1_0 import (
    TEST_AGENT, UTC, fake_loader, limited_cohort,
)


def prepared():
    manifest, blobs = intake.collect(
        user_agent=TEST_AGENT, limit=1, cohort=limited_cohort(),
        loader=fake_loader(), captured_utc=UTC,
    )
    raw = {"manifest-and-quality.json": json.dumps(manifest).encode(), **blobs}
    return manifest, raw


def fake_zip(path, files):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, raw in files.items():
            z.writestr(name, raw)


def test_original_sec_json_bytes_recomputed_quality_and_coverage():
    _, files = prepared()
    r = p4c.audit(files)
    assert r["source_companies"] == 1
    assert r["quality_available"] == 1
    assert r["quality_unavailable"] == 0
    assert r["coverage_percent_of_captured"] == 100
    assert r["coverage_percent_of_frozen_cohort"] == 12.5
    assert len(r["uncaptured_cohort_tickers"]) == 7
    assert r["observations"][0]["ticker"] == "AAPL"
    assert r["observations"][0]["score"] == 3
    assert r["observations"][0]["annual_period_end"] == "2026-10-30"
    assert len(r["source_original_manifest_sha256"]) == 64
    assert r["paper_authorized"] is False
    assert r["live_authorized"] is False
    assert r["historical_stock_return_backtest_eligible"] is False


def test_zip_and_dir_have_same_original_sha_and_researched_values(tmp_path):
    _, files = prepared()
    target = tmp_path / "official-source.zip"
    fake_zip(target, files)
    root = tmp_path / "capture"
    for name, raw in files.items():
        f = root / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(raw)
    assert p4c.audit(p4c.snapshot_files(target)) == p4c.audit(p4c.snapshot_files(root))


def test_incorrect_raw_sec_byte_digest_fails_closed():
    _, files = prepared()
    name = next(n for n in files if n.endswith("-companyfacts.json"))
    files[name] += b" "
    with pytest.raises(p4c.CohortAuditStop, match="SHA"):
        p4c.audit(files)


def test_modified_original_sec_fundamental_even_with_updated_sha_not_accepted():
    man, files = prepared()
    name = next(n for n in files if n.endswith("-companyfacts.json"))
    orig = json.loads(files[name])
    tag = intake.quality.ANNUAL_TAGS["revenue"]
    orig["facts"]["us-gaap"][tag]["units"]["USD"][1]["val"] *= 1.3
    files[name] = json.dumps(orig).encode()
    man["companies"][0]["report_data_provenance"]["companyfacts"]["raw_sha256"] = p4c.digest(files[name])
    man["companies"][0]["report_data_provenance"]["companyfacts"]["byte_count"] = len(files[name])
    files["manifest-and-quality.json"] = json.dumps(man).encode()
    with pytest.raises(p4c.CohortAuditStop, match="annual score not reproducible"):
        p4c.audit(files)


def test_mismatch_stock_cik_and_replaced_source_url_fail():
    man, files = prepared()
    man["companies"][0]["ticker"] = "MSFT"
    files["manifest-and-quality.json"] = json.dumps(man).encode()
    with pytest.raises(p4c.CohortAuditStop, match="cohort identity"):
        p4c.audit(files)
    man, files = prepared()
    man["companies"][0]["report_data_provenance"]["submissions"]["official_url"] = "https://example.com"
    files["manifest-and-quality.json"] = json.dumps(man).encode()
    with pytest.raises(p4c.CohortAuditStop, match="URL"):
        p4c.audit(files)


def test_missing_one_source_or_extra_payload_never_counted_as_valid_coverage():
    _, files = prepared()
    name = next(n for n in files if n.endswith("-submissions.json"))
    files.pop(name)
    with pytest.raises(p4c.CohortAuditStop):
        p4c.audit(files)
    _, files = prepared()
    files["raw/secret.txt"] = b"unreviewed"
    with pytest.raises(p4c.CohortAuditStop):
        p4c.audit(files)


def test_no_stocks_auto_authorized_even_if_manifest_attempts_paper():
    man, files = prepared()
    for field in ("paper_authorized", "live_authorized"):
        edited = deepcopy(man)
        edited[field] = True
        files["manifest-and-quality.json"] = json.dumps(edited).encode()
        with pytest.raises(p4c.CohortAuditStop):
            p4c.audit(files)


def test_zip_slip_or_repeated_paths_rejected(tmp_path):
    for names in (
        [("../evil.txt", b"x")],
        [("/tmp/evil.json", b"x")],
        [("manifest-and-quality.json", b"{}"), ("manifest-and-quality.json", b"{}")],
    ):
        target = tmp_path / "test.zip"
        with zipfile.ZipFile(target, "w") as z:
            for name, data in names:
                z.writestr(name, data)
        with pytest.raises(p4c.CohortAuditStop):
            p4c.snapshot_files(target)


def test_missing_required_schema_and_untrusted_future_capture_rejected():
    man, files = prepared()
    man["schema"] = "SYNTHETIC_APPROVED_TRADE"
    files["manifest-and-quality.json"] = json.dumps(man).encode()
    with pytest.raises(p4c.CohortAuditStop):
        p4c.audit(files)
    man, files = prepared()
    man["capture_timestamp_utc"] = "2015-10-15T12:00:00Z"
    files["manifest-and-quality.json"] = json.dumps(man).encode()
    with pytest.raises(p4c.CohortAuditStop):
        p4c.audit(files)


def test_source_unavailable_must_remain_missing_no_score_or_universe_promotion():
    man, files = prepared()
    facts_path = next(k for k in files if k.endswith("-companyfacts.json"))
    obj = json.loads(files[facts_path])
    del obj["facts"]["us-gaap"][intake.quality.ANNUAL_TAGS["revenue"]]
    files[facts_path] = json.dumps(obj).encode()
    man["companies"][0]["report_data_provenance"]["companyfacts"]["raw_sha256"] = p4c.digest(files[facts_path])
    man["companies"][0]["report_data_provenance"]["companyfacts"]["byte_count"] = len(files[facts_path])
    for field in ("quality_score","quality_maximum","quality_revenue_growth_yoy",
                  "quality_operating_margin","quality_free_cash_flow_margin",
                  "last_eligible_fiscal_year","last_eligible_filing_accession",
                  "last_eligible_filing_available_date"):
        man["companies"][0][field] = None
    man["companies"][0]["quality_state"] = "MISSING_ELIGIBLE_FULL_YEAR_FILINGS"
    files["manifest-and-quality.json"] = json.dumps(man).encode()
    r = p4c.audit(files)
    assert r["quality_available"] == 0
    assert r["missing_quality_tickers"] == ["AAPL"]
    assert r["observations"][0]["score"] is None
    assert r["coverage_percent_of_frozen_cohort"] == 0.


def test_ledger_source_hash_chain_and_multiple_future_acquisitions():
    _, files = prepared()
    r = p4c.audit(files)
    first = p4c.ledger_record(r)
    p4c.validate_ledger([first])
    newer = dict(r, capture_timestamp_utc="2026-12-02T13:00:00Z",
                 source_original_manifest_sha256="a"*64)
    second = p4c.ledger_record(newer, [first])
    p4c.validate_ledger([first, second])
    assert second["previous_record_sha256"] == first["record_sha256"]
    assert first["previous_record_sha256"] is None


def test_ledger_prevents_backdating_duplicate_sources_and_modification():
    _, files = prepared()
    r = p4c.audit(files)
    first = p4c.ledger_record(r)
    with pytest.raises(p4c.CohortAuditStop):
        p4c.ledger_record(r, [first])
    changed = deepcopy(first)
    changed["source_manifest_sha256"] = "0" * 64
    with pytest.raises(p4c.CohortAuditStop, match="SHA256"):
        p4c.validate_ledger([changed])
    changed = deepcopy(first)
    changed["paper_authorized"] = True
    with pytest.raises(p4c.CohortAuditStop):
        p4c.validate_ledger([changed])


def test_existing_two_company_real_sec_anchor_is_not_a_fake_historical_backtest():
    from test_fund100_stock_sec_capture_review_p4b_v1_0 import validate, source as first
    r = first()
    validate(r)
    assert r["company_count"] == 2
    assert all(x["reported_quality_score"] == 3 for x in r["companies"])
    assert r["historical_alpha_established"] is False
    assert r["analyst_revision_signal_available"] is False
