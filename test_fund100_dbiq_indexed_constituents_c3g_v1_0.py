"""C3G indexed issuer futures constituents: offline integrity and no-trade."""
from __future__ import annotations

from copy import deepcopy
import hashlib

import pandas as pd
import pytest

import fund100_dbiq_indexed_constituents_c3g_v1_0 as c
import fund100_dbc_sec_holdings_c3c_v1_0 as sec


@pytest.fixture
def inputs():
    indexed = c.read_snapshot()
    holdings = pd.read_csv(sec.DATA, dtype={
        x:"string" for x in sec.COLUMNS if x not in ("contracts","notional_usd")
    })
    return indexed, holdings


def test_all_28_official_indexed_contracts_99_99_percent(inputs):
    data, secdata = inputs
    validated = c.validate_snapshot(data, secdata)
    assert len(validated) == 28
    assert validated["issuer_futures_contract_code"].nunique() == 28
    assert validated["mapped_sec_commodity"].nunique() == 28
    assert sum(validated["issuer_index_weight_percent"]) == pytest.approx(99.99)
    assert set(validated["mapped_sec_commodity"]) == sec.COMMODITIES


def test_known_codes_explicit_and_displayed_contract_month_is_not_expiry(inputs):
    data, secdata = inputs
    c.validate_snapshot(data, secdata)
    required = {
        "Brent Crude": ("LCOZ6", "2026-10-30", 17.85),
        "Light Crude": ("CLX26", "2026-10-20", 15.07),
        "Gold": ("GCZ26", "2026-12-29", 8.95),
        "Copper": ("HGK27", "2027-05-26", 2.70),
        "Copper - Grade A": ("MCUH27", "2027-03-17", 2.86),
    }
    by_name = data.set_index("issuer_commodity")
    for commodity, (code, date, weight) in required.items():
        assert by_name.loc[commodity, "issuer_futures_contract_code"] == code
        assert by_name.loc[commodity, "issuer_displayed_contract_date"] == date
        assert by_name.loc[commodity, "issuer_index_weight_percent"] == pytest.approx(weight)


def test_index_sector_weights_are_not_sec_position_weights(inputs):
    data, secdata = inputs
    result = c.analyze(data, secdata, "snapshotdigest")
    weights = result["sector_index_weight_percent_of_listed_constituents"]
    assert weights["Energy"] == pytest.approx(53.27)
    assert weights["Agriculture"] == pytest.approx(17.14)
    assert weights["Industrial metals"] == pytest.approx(11.29)
    assert weights["Precious metals"] == pytest.approx(11.76)
    assert weights["Livestock"] == pytest.approx(6.53)
    assert sum(weights.values()) == pytest.approx(99.99)
    assert result["historical_june_2026_fund_positions_are_not_synchronous_with_web_indexed_table"] is True
    assert result["index_vs_dbc_tracking_difference_at_same_instant_calculated"] is False


def test_unverified_provider_effective_time_not_promoted_to_trading(inputs):
    data, secdata = inputs
    r = c.analyze(data, secdata, "digest")
    assert r["status"] == "ISSUER_SEARCH_INDEXED_SNAPSHOT_NO_VERIFIED_EFFECTIVE_TIME"
    assert r["actual_provider_html_or_pdf_bytes_archived"] is False
    assert r["exact_issuer_portfolio_effective_date"] is None
    assert r["source_content_is_manual_transcription_from_web_search"] is True
    assert r["historical_replay_or_backtest_eligible"] is False
    assert r["issuer_column_named_contract_month_not_verified_exchange_last_trade"] is True
    assert r["source_must_not_be_sent_to_c3b_expiry_importer"] is True
    assert r["current_tradable_futures_prices_known"] is False
    assert r["futures_roll_return_calculated"] is False
    assert r["portfolio_live_authorized"] is False
    assert r["portfolio_paper_authorized"] is False
    assert r["broker_order_count"] == 0


def test_source_is_a_real_official_index_page_not_dbci_shares(inputs):
    data, secdata = inputs
    r = c.analyze(data, secdata, "x")
    assert r["official_index_page"] == "https://index.db.com/dbiq-web/indices/95400"
    assert r["issuer_index_ticker"] == "DBLCDBCE"
    assert r["web_indexed_text_retrieved_date_not_original_issuer_capture"] == "2026-10-15"
    assert r["mapped_to_distinct_sec_commodity_descriptions"] == 28


def test_missing_unknown_or_duplicate_tickers_rejected(inputs):
    data, secdata = inputs
    cases = (
        data.iloc[:-1],
        pd.concat([data, data.iloc[-1:]], ignore_index=True),
        data.assign(issuer_futures_contract_code="CLX26"),
        data.assign(mapped_sec_commodity="COMEX Gold"),
        data.assign(issuer_commodity="Other"),
        data.drop(columns=["issuer_commodity"]),
    )
    for x in cases:
        with pytest.raises(c.IndexedBasketStop):
            c.validate_snapshot(x, secdata)


def test_invalid_weights_cannot_claim_full_index(inputs):
    data, secdata = inputs
    for a in (
        data.assign(issuer_index_weight_percent=0),
        data.assign(issuer_index_weight_percent=-1.0),
        data.assign(issuer_index_weight_percent=40),
        data.assign(issuer_index_weight_percent=float("nan")),
        data.assign(issuer_index_weight_percent="missing"),
        data.assign(issuer_index_weight_percent=data["issuer_index_weight_percent"]*0.5),
    ):
        with pytest.raises(c.IndexedBasketStop):
            c.validate_snapshot(a, secdata)


def test_bad_calendar_date_and_undocumented_contract_id_rejected(inputs):
    data, secdata = inputs
    for column, new in (
        ("issuer_displayed_contract_date", "2026-02-30"),
        ("issuer_displayed_contract_date", "2026-10-1"),
        ("issuer_futures_contract_code", "CLX26/$"),
    ):
        altered = data.copy()
        altered.loc[0, column] = new
        with pytest.raises(c.IndexedBasketStop):
            c.validate_snapshot(altered, secdata)


def test_sec_holdings_mapping_cannot_hide_missing_commodities(inputs):
    data, secdata = inputs
    changed = data.copy()
    changed.loc[0, "mapped_sec_commodity"] = "UNLISTED METAL"
    with pytest.raises(c.IndexedBasketStop):
        c.validate_snapshot(changed, secdata)


def test_source_hash_changes_when_transcription_bytes_changed(inputs):
    raw = c.CSV.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert len(digest) == 64
    assert hashlib.sha256(raw+b"\n").hexdigest() != digest


def test_no_mutation_of_public_issuer_or_sec_data(inputs):
    data, secdata = inputs
    a, b = data.copy(deep=True), secdata.copy(deep=True)
    c.analyze(data, secdata, "source")
    pd.testing.assert_frame_equal(data, a)
    pd.testing.assert_frame_equal(secdata, b)


def test_official_document_probe_domain_allowlist_and_no_trading():
    import fund100_dbiq_official_pdf_discovery_probe_c3g as p
    assert p.approved_url("https://index.db.com/dbiq-web/indices/95400")
    assert p.approved_url("https://dbindex.db.com/asset.pdf")
    for bad in (
        "http://index.db.com/asset.pdf",
        "https://evilindex.db.com.example.net/file.pdf",
        "https://example.org/dbc-trading.pdf",
        "javascript:alert(1)",
        "file:///etc/passwd",
    ):
        assert not p.approved_url(bad)
    assert len(p.DOCUMENTS) == 2
