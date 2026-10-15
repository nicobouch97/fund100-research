"""Actual SEC DBC futures disclosure research tests; no external network."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

import fund100_dbc_sec_holdings_c3c_v1_0 as c


@pytest.fixture
def source_data():
    raw = c.DATA.read_bytes()
    data = pd.read_csv(c.DATA, dtype={
        name: "string" for name in c.COLUMNS
        if name not in ("contracts", "notional_usd")
    })
    return raw, data


def test_real_sec_disclosures_cover_both_quarters_all_28_holdings(source_data):
    raw, d = source_data
    c.validate(d)
    assert len(d) == 56
    assert sorted(d["statement_date"].unique()) == ["2026-03-31", "2026-06-30"]
    assert set(d["commodity"]) == c.COMMODITIES
    assert d.loc[d["statement_date"] == "2026-03-31", "notional_usd"].sum() == 1689474972
    assert d.loc[d["statement_date"] == "2026-06-30", "notional_usd"].sum() == 1576215941
    assert len(c.source_sha256(raw)) == 64


def test_concrete_real_comex_copper_delivery_month_shift(source_data):
    _, d = source_data
    r = c.research_summary(d, "frozen-source-digest")
    change = r["changed_delivery_month_observations"]["COMEX Copper"]
    assert change["march_reported_delivery_month"] == "2026-07"
    assert change["june_reported_delivery_month"] == "2027-05"
    assert change["NOT_an_executed_roll_confirmation"] is True


def test_real_fund_futures_positions_not_roll_or_index_strategy(source_data):
    raw, d = source_data
    r = c.research_summary(d, c.source_sha256(raw))
    assert r["status"] == "FILING_DATED_FUTURES_POSITION_RESEARCH_ONLY"
    assert r["source_bytes_are_not_original_sec_html"] is True
    assert r["full_daily_holdings_known"] is False
    assert r["intramonth_actual_roll_dates_known"] is False
    assert r["actual_trading_prices_or_futures_curve_known"] is False
    assert r["actual_roll_pnl_computed"] is False
    assert r["index_weights_or_index_portfolio_replicated"] is False
    assert r["paper_authorized"] is False
    assert r["live_authorized"] is False
    assert r["broker_order_count"] == 0
    assert r["all_holdings_snapshots_after_methodology_change"] is True
    assert r["dbc_index_methodology_change_date"] == "2025-11-10"


def test_sec_quarter_end_is_not_date_futures_position_is_publicly_knowable(source_data):
    _, d = source_data
    assert c.last_knowable_report(d, "2026-03-31") is None
    assert c.last_knowable_report(d, "2026-05-07") is None
    assert c.last_knowable_report(d, "2026-05-08") == "2026-03-31"
    assert c.last_knowable_report(d, "2026-06-30") == "2026-03-31"
    assert c.last_knowable_report(d, "2026-08-07") == "2026-03-31"
    assert c.last_knowable_report(d, "2026-08-10") == "2026-06-30"
    assert c.last_knowable_report(d, "2026-10-15") == "2026-06-30"


def test_reported_equity_notional_reconciliation_per_quarter(source_data):
    _, d = source_data
    summary = c.research_summary(d, "frozen")
    for quarter, result in summary["reported_periods"].items():
        assert result["futures_holdings_count"] == 28
        assert abs(result["gross_notional_to_equity_ratio"] - 1) < .03
        assert abs(sum(result["sector_notional_fraction_of_reported_futures"].values()) - 1) < .000005
        assert set(result["sector_notional_fraction_of_reported_futures"]) == c.SECTORS


def test_filing_source_identity_and_observation_day_cannot_be_rewritten(source_data):
    _, d = source_data
    for change in (
        lambda x: x.assign(sec_filing_date="2026-03-31"),
        lambda x: x.assign(available_date="2026-06-30"),
        lambda x: x.assign(accession="0000000000-00-000000"),
        lambda x: x.assign(sec_filing_url="https://unknown.example/"),
        lambda x: x.assign(statement_date="2026-07-01"),
    ):
        with pytest.raises(c.FilingDataStop):
            c.validate(change(d.copy()))


def test_missing_duplicated_future_lines_fail_closed(source_data):
    _, d = source_data
    for change in (
        lambda x: x.drop(index=1),
        lambda x: pd.concat([x, x.iloc[1:2]], ignore_index=True),
        lambda x: x.assign(commodity="UNLISTED COMMODITY"),
        lambda x: x.assign(sector="Other"),
        lambda x: x.assign(delivery_month="2026-99"),
        lambda x: x.assign(delivery_month="2019-01"),
    ):
        with pytest.raises(c.FilingDataStop):
            c.validate(change(d.copy()))


def test_fund_exposure_must_use_positive_notional_and_contract_counts(source_data):
    _, d = source_data
    for change in (
        lambda x: x.assign(contracts=-1),
        lambda x: x.assign(notional_usd=0),
        lambda x: x.assign(notional_usd=99),
        lambda x: x.assign(notional_usd=1.25),
    ):
        with pytest.raises(c.FilingDataStop):
            c.validate(change(d.copy()))


def test_current_asof_derived_only_from_last_publicly_available_quarter(source_data):
    _, d = source_data
    r = c.research_summary(d, "hash")
    assert r["public_knowability_examples"]["2026-06-30"] == "2026-03-31"
    assert r["public_knowability_examples"]["2026-08-07"] == "2026-03-31"
    assert r["public_knowability_examples"]["2026-08-10"] == "2026-06-30"


def test_source_hash_sensitive_and_source_not_mutated(source_data):
    raw, d = source_data
    copy = d.copy(deep=True)
    c.research_summary(d, c.source_sha256(raw))
    pd.testing.assert_frame_equal(d, copy)
    assert c.source_sha256(raw) != c.source_sha256(raw + b"\n")


def test_us_filing_urls_bind_actual_cik(source_data):
    _, d = source_data
    assert all("www.sec.gov/Archives/edgar/data/1328237/" in x for x in d["sec_filing_url"])
    assert d["accession"].nunique() == 2
