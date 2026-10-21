"""B4 original-web-snapshot bond duration separate from equity and futures."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from shutil import copy2

import pytest

import fund100_v6_b4_issuer_bond_duration_crossasset_v1_0 as b4
import fund100_multi_asset_portfolio_arbiter_v1_0 as arbiter


def report(date="2026-10-21", proposals=None, **kw):
    return b4.research(
        proposals=deepcopy(b4.SYNTHETIC_PROPOSALS) if proposals is None else proposals,
        decision_date=date, **kw)


def test_all_five_issuer_effective_durations_verbatim_and_pinned():
    d=b4.source()
    assert set(d)=={"TLT","IEF","SHY","TIP","LQD"}
    assert {s:r["duration_years"] for s,r in d.items()} == {
        "TLT":"14.79","IEF":"6.83","SHY":"1.80",
        "TIP":"6.16","LQD":"7.54"}
    assert all(r["url"].startswith("https://www.ishares.com/us/products/") for r in d.values())


def test_one_fund_three_asset_classes_first_order_rate_driver_separation():
    r=report()
    assert r["hypothetical_shared_fund_ceiling_usd"]=="130.30"
    assert r["hypothetical_invested_usd"]=="110.00"
    assert r["hypothetical_cash_usd"]=="20.30"
    assert r["hypothetical_XLE_energy_equity_usd"]=="15.000000000"
    assert r["hypothetical_DBC_commodity_futures_usd"]=="20.000000000"
    assert r["hypothetical_bond_exposure_usd"]=="40.00"
    assert r["distinct_bond_driver_duration_dollar_years"]=={
        "NOMINAL_TREASURY_RATE":"187.360000",
        "TIPS_REAL_YIELD":"49.280000",
        "CORPORATE_TOTAL_RATE_AND_CREDIT_SPREAD":"60.320000",
    }
    assert r["combined_bond_duration_dollar_years_not_one_common_beta"]=="296.960000"
    assert r["illustrative_joint_up_100bp_each_instrument_own_driver_price_only_usd"]=="-2.969600"
    assert r["hypothetical_bond_duration_by_instrument"]["TLT"][
        "approx_price_change_if_own_driver_up_100bp_usd"]=="-1.183200"
    assert r["hypothetical_bond_duration_by_instrument"]["SHY"][
        "approx_price_change_if_own_driver_up_100bp_usd"]=="-0.144000"
    assert not r["actual_portfolio_holdings_captured"]
    assert not r["new_live_risk_factor_weights_approved"]
    assert not r["new_live_orders_authorized"]
    assert r["broker_requests"]==r["live_orders"]==r["paper_orders"]==0


def test_issuer_web_observed_after_asof_prevents_hindsight_backtest():
    for date in ("2026-10-20","2026-10-19","2014-07-01"):
        with pytest.raises(b4.DurationSourceStop, match="not captured"):
            report(date=date)
    current=report("2026-10-21")
    assert current["issuer_snapshot_age_calendar_days"]==2
    assert current["issuer_snapshot_freshness"]=="RECENT_RESEARCH_WEB_TRANSCRIPTION_NOT_LIVE"
    future=report("2026-11-02")
    assert future["issuer_snapshot_freshness"]=="STALE_RESEARCH_WEB_TRANSCRIPTION"
    assert future["not_suitable_for_historical_simulation_before_observed_date"]


def test_permuting_registered_proposals_cannot_change_risk():
    original=report()
    changed=report(proposals=list(reversed(deepcopy(b4.SYNTHETIC_PROPOSALS))))
    assert original==changed


def test_factors_do_not_confer_new_authority_or_independent_spread_measurement():
    r=report()
    assert r["joint_shock_is_not_a_single_credible_rate_path"]
    assert r["different_duration_drivers_must_not_be_treated_as_equivalent"]
    assert r["credit_spread_risk_not_independently_decomposed"]
    assert r["key_rate_duration_convexity_carry_and_tax_not_measured"]
    assert not r["actual_issuer_html_bytes_archived_or_first_published_clock_verified"]
    assert not r["new_live_risk_factor_weights_approved"]
    assert r["DBC_original_SEC_statement_date"]=="2026-06-30"
    assert r["DBC_lookthrough_freshness"]=="STALE_HISTORICAL_SEC_LOOKTHROUGH"


def test_negative_bond_factor_self_declared_cash_rejected():
    p=deepcopy(b4.SYNTHETIC_PROPOSALS)
    p[2]["risk_factors"]={"CASH":"1"}
    with pytest.raises(b4.DurationSourceStop,match="not cash"):
        report(proposals=p)


def test_unproven_new_bond_etf_cannot_inherit_duration():
    p=deepcopy(b4.SYNTHETIC_PROPOSALS)
    p[2]["instruments"]={"TLT":"0.5","BND":"0.5"}
    with pytest.raises(b4.DurationSourceStop,match="lacks issuer"):
        report(proposals=p)


def test_improper_extra_fund_capital_fails_in_base_arbiter():
    p=deepcopy(b4.SYNTHETIC_PROPOSALS)
    p[1]["requested_usd"]="200.00"
    with pytest.raises(arbiter.ArbiterStop):
        report(proposals=p)


def test_original_source_blob_must_not_be_modified(tmp_path):
    dst=tmp_path / b4.FILE
    dst.parent.mkdir(parents=True)
    copy2(b4.ROOT / b4.FILE,dst)
    assert b4.source(root=tmp_path)
    dst.write_bytes(dst.read_bytes().replace(b"14.79",b"14.80"))
    with pytest.raises(b4.DurationSourceStop,match="changed"):
        b4.source(root=tmp_path)


def test_unchanged_original_s1_manifest_and_stopped_live_operator():
    import json
    manifest=json.loads(Path("research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json").read_text())
    control=json.loads(Path("fund100_live_operator_control.json").read_text())
    assert manifest["investable_gross_fraction"]=="0.95"
    assert manifest["maximum_gross_exposure"]=="0.95"
    assert manifest["live_environment_kill_switch"]=="ENGAGED"
    assert not manifest["live_order_execution_released"]
    assert not control["trading_enabled"]
    assert b4.NO_LIVE_ORDERS


def test_no_broker_or_private_state_network_imports():
    code=Path(b4.__file__).read_text()
    for forbidden in ("requests.post(", "requests.get(", "urlopen(",
                      "api.alpaca.markets", "api.github.com/",
                      "ALPACA_LIVE", "GH_TOKEN", "/v2/orders",
                      "place_order(", "FUND100_PRIVATE_STATE_READ_TOKEN"):
        assert forbidden not in code
