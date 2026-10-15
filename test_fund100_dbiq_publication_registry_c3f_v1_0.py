"""C3F issuer-published selection-report listing and PDF evidence gates.

Offline fake PDF fixtures test SHA/license/chronology only.
No authentic source PDF has been retrieved by this test module.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib

import pandas as pd
import pytest

import fund100_dbiq_publication_registry_c3f_v1_0 as c


@pytest.fixture
def registry():
    return c.load_registry()


def test_actual_index_issuer_registry_nov2025_through_oct2026(registry):
    assert len(registry) == 12
    assert registry.iloc[0]["report_month"] == "2025-11"
    assert registry.iloc[0]["issuer_site_listed_date"] == "2025-11-03"
    assert registry.iloc[-1]["report_month"] == "2026-10"
    assert registry.iloc[-1]["issuer_site_listed_date"] == "2026-10-01"
    assert all(registry["official_pdf_bytes_acquired"] == "false")
    assert all(registry["document_verified_for_dbc_constituents"] == "false")
    assert set(registry["portal_url"]) == {c.OFFICIAL_PUBLICATIONS_PAGE}


def test_timeline_reports_are_real_official_issuer_listings_not_fabricated_trades(registry):
    r = c.report(registry, "mocksource")
    assert r["reports_listed"] == 12
    assert r["status"] == "OFFICIAL_PUBLICATION_METADATA_ONLY_NO_ROLL_PNL"
    assert r["official_index_ticker"] == "DBLCDBCE"
    assert r["source_page_does_not_reveal_pdf_bytes"] is True
    assert r["issuer_contract_expiries_confirmed"] is not True if "issuer_contract_expiries_confirmed" in r else True
    assert r["underlying_futures_settlement_quotes_available"] is False
    assert r["strategy_carry_pnl_validated"] is False
    assert r["historical_backtest_eligible"] is False
    assert r["live_authorized"] is False
    assert r["paper_authorized"] is False
    assert r["broker_order_count"] == 0
    assert all(not item["pdf_bytes_downloaded"] for item in r["listed"])
    assert all(not item["contract_selection_extracted"] for item in r["listed"])


def test_publication_not_visible_before_conservative_day(registry):
    assert c.visible_publications_on(registry, "2025-11-03") == []
    assert c.visible_publications_on(registry, "2025-11-04") == []
    assert c.visible_publications_on(registry, "2025-11-05") == ["2025-11"]
    assert c.visible_publications_on(registry, "2025-12-01") == ["2025-11"]
    assert c.visible_publications_on(registry, "2025-12-03") == ["2025-11", "2025-12"]
    assert c.visible_publications_on(registry, "2026-10-05")[-1] == "2026-10"


def test_month_of_report_must_match_actual_published_date(registry):
    wrong = registry.copy()
    wrong.loc[0, "issuer_site_listed_date"] = "2025-10-31"
    with pytest.raises(c.IssuerEvidenceStop, match="not in actual report month"):
        c.validate_registry(wrong)


def test_missing_or_duplicate_report_refused(registry):
    for wrong in (
        registry.iloc[:-1],
        pd.concat([registry, registry.iloc[-1:]], ignore_index=True),
        registry.iloc[::-1].copy(),
        registry.drop(columns=["official_document_title"]),
    ):
        with pytest.raises(c.IssuerEvidenceStop):
            c.validate_registry(wrong)


def test_source_title_clock_and_portal_must_match_issuer(registry):
    for col, value in (
        ("official_document_title", "DBIQ Modified Asset List.pdf"),
        ("issuer_site_listed_clock_timezone_unknown", "24:59"),
        ("portal_url", "https://trading.example.com"),
        ("source_class", "broker_buy_signal"),
        ("official_pdf_bytes_acquired", "true"),
        ("document_verified_for_dbc_constituents", "true"),
    ):
        edited = registry.copy()
        edited.loc[2, col] = value
        with pytest.raises(c.IssuerEvidenceStop):
            c.validate_registry(edited)


def test_invalid_asof_rejected(registry):
    for invalid in ("2026-1-1", "2026-02-30", "01/02/2026", None):
        with pytest.raises(c.IssuerEvidenceStop):
            c.visible_publications_on(registry, invalid)


def pdf_fixture(month="2025-11"):
    raw = b"%PDF-1.7\n" + b"FAKE-PDF-UNIT-TEST-NOT-A-REAL-DOCUMENT" * 20
    title = "DBIQ Optimum Yield indices Selection Report Nov 25.pdf"
    evidence = {
        "report_month": month,
        "document_title": title,
        "publisher_page_url": c.OFFICIAL_PUBLICATIONS_PAGE,
        "actual_pdf_url": "https://index.db.com/source/test-document.pdf",
        "source_pdf_sha256": hashlib.sha256(raw).hexdigest(),
        "acquired_at_utc": "2026-10-15T11:00:00Z",
        "right_to_store_and_analyze": True,
        "manual_content_review_performed": False,
    }
    return raw, evidence


def test_source_pdf_hash_document_license_and_utc_acquisition_verified(registry):
    fake_pdf, evidence = pdf_fixture()
    r = c.validate_pdf_evidence(
        report_month="2025-11", pdf_bytes=fake_pdf,
        evidence=evidence, registry=registry,
    )
    assert r["pdf_sha256"] == hashlib.sha256(fake_pdf).hexdigest()
    assert r["issuer_contract_mapping_confirmed"] is False
    assert r["dbc_index_constituent_rolls_confirmed"] is False
    assert r["manual_content_review_performed"] is False
    assert r["live_or_paper_trade_authorized"] is False


def test_fake_pdf_content_and_wrong_hash_fail_closed(registry):
    raw, m = pdf_fixture()
    with pytest.raises(c.IssuerEvidenceStop, match="Not actual"):
        c.validate_pdf_evidence(report_month="2025-11",
                                pdf_bytes=b"fake", evidence=m, registry=registry)
    wrong = deepcopy(m)
    wrong["source_pdf_sha256"] = "0"*64
    with pytest.raises(c.IssuerEvidenceStop, match="SHA256"):
        c.validate_pdf_evidence(report_month="2025-11",
                                pdf_bytes=raw, evidence=wrong, registry=registry)


def test_report_cannot_be_acquired_before_publication(registry):
    raw, m = pdf_fixture()
    m["acquired_at_utc"] = "2025-10-15T15:00:00Z"
    with pytest.raises(c.IssuerEvidenceStop, match="before indexed publication"):
        c.validate_pdf_evidence(report_month="2025-11",
                                pdf_bytes=raw, evidence=m, registry=registry)


def test_wrong_month_wrong_title_and_missing_rights_are_refused(registry):
    raw, evidence = pdf_fixture()
    for key, value in (
        ("document_title", "Wrong report"),
        ("publisher_page_url", "https://example.com"),
        ("actual_pdf_url", "http://not-secure.example/doc.pdf"),
        ("right_to_store_and_analyze", False),
        ("manual_content_review_performed", "yes"),
        ("acquired_at_utc", "yesterday"),
    ):
        m = deepcopy(evidence)
        m[key] = value
        with pytest.raises(c.IssuerEvidenceStop):
            c.validate_pdf_evidence(
                report_month="2025-11", pdf_bytes=raw,
                evidence=m, registry=registry,
            )


def test_unknown_month_cannot_claim_official_selection(registry):
    raw, evidence = pdf_fixture(month="2024-10")
    with pytest.raises(c.IssuerEvidenceStop):
        c.validate_pdf_evidence(
            report_month="2024-10", pdf_bytes=raw,
            evidence=evidence, registry=registry,
        )


def test_source_registry_is_not_modified_by_read_or_report(registry):
    orig = registry.copy()
    out = c.report(registry, "mock")
    assert len(out["listed"]) == 12
    pd.testing.assert_frame_equal(registry, orig)


def test_site_clock_has_no_verified_timezone_or_holiday_calendar(registry):
    r = c.report(registry, "digest")
    assert r["issuance_timezone_confirmed"] is False
    assert r["release_vintages_confirmed"] is False
    assert r["contract_expiries_confirmed"] is False
    for entry in r["listed"]:
        assert entry["issuer_listing_time_timezone"] == "NOT_DISCLOSED"
