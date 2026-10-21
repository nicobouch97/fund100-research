"""Original-source cross-asset preflight is research-only and fail-closed."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
from shutil import copy2

import pytest

import fund100_v6_c12_source_qualified_multi_asset_preflight_v1_0 as c12
import fund100_v6_c11_dbc_sec_futures_lookthrough_v1_0 as c11
import fund100_multi_asset_portfolio_arbiter_v1_0 as arbiter
import fund100_v6_investment_thesis_gate_v1_0 as thesis


def study(asof="2026-10-21", proposals=None, cash="BASELINE_95", **kw):
    if proposals is None:
        proposals = deepcopy(c12.SYNTHETIC_PROPOSALS)
    return c12.inspect(
        proposals=proposals, decision_date=asof, cash_policy=cash, **kw)


def test_shared_120dollar_synthetic_fund_lookthrough_not_beta():
    r = study()
    assert r["hypothetical_shared_fund_ceiling_usd"] == "130.30"
    assert r["hypothetical_invested_usd"] == "120.00"
    assert r["hypothetical_cash_usd"] == "10.30"
    weights = r["underlying_hypothetical_instrument_usd"]
    assert weights == {
        "DBC": "20.000000000", "IWM": "20.000000000",
        "XLE": "30.000000000", "XLK": "50.000000000",
    }
    assert sum(map(Decimal, weights.values())) == Decimal("120.00")
    assert r["original_registered_live_trading_candidate_count"] == 0
    assert r["live_orders"] == r["paper_orders"] == r["broker_network_requests"] == 0
    assert r["private_state_write_requests"] == 0
    assert not r["new_live_trading_authorized"]
    assert not r["cash_policy_live_changed"]


def test_june_notional_47pct_is_evidence_not_energy_equity_beta():
    r = study()
    assert r["DBC_original_SEC_statement_date"] == "2026-06-30"
    assert r["DBC_original_SEC_filing_available_date"] == "2026-08-10"
    assert r["DBC_lookthrough_freshness_classification"] == (
        "STALE_HISTORICAL_SEC_LOOKTHROUGH")
    assert 0.469 < float(r["DBC_reported_gross_futures_energy_notional_fraction"]) < 0.471
    energy = Decimal(
        r["hypothetical_DBC_dollars_times_historic_SEC_sector_share_not_beta"]["Energy"])
    assert Decimal("9.39") < energy < Decimal("9.41")
    assert r["hypothetical_XLE_energy_company_equity_notional_usd"] == "30.000000000"
    assert r["XLE_equity_DBC_futures_shared_energy_risk_unquantified"]
    assert r["XLE_and_DBC_energy_notional_must_not_be_added_as_common_risk"]
    assert not r["modelled_correlation_or_futures_beta"]
    assert not r["current_underlying_lookthrough_independently_verified"]
    assert not r["safe_to_rely_on_report_for_LIVE_risk_factor_or_beta_weights"]
    assert r["current_underlying_lookthrough_unverified_for_all_scenario_instruments"] == [
        "DBC", "IWM", "XLE", "XLK",
    ]


def test_synthetic_entry_cash_scenarios_do_not_change_source_quality():
    original = study(cash="BASELINE_95")
    full = study(cash="FULLY_ALLOCATED_100")
    assert full["hypothetical_invested_usd"] == original["hypothetical_invested_usd"]
    assert full["DBC_original_SEC_statement_date"] == original[
        "DBC_original_SEC_statement_date"]
    assert not full["new_live_trading_authorized"]


def test_input_order_cannot_prioritize_commodity_over_original_research_ranking():
    a = study(proposals=deepcopy(c12.SYNTHETIC_PROPOSALS))
    b = study(proposals=list(reversed(deepcopy(c12.SYNTHETIC_PROPOSALS))))
    assert a == b


def test_no_sec_source_before_first_availability_does_not_mean_zero_energy():
    # Source-vintage eligibility test ONLY, not a claim V6-S1 existed in March.
    r = study(asof="2026-03-02")
    assert r["DBC_asof_source_status"] == "NO_PUBLICLY_AVAILABLE_FILING_AT_DECISION_DATE"
    assert r["DBC_lookthrough_freshness_classification"] == (
        "NO_PUBLICLY_AVAILABLE_DBC_FILING")
    assert r["DBC_reported_gross_futures_energy_notional_fraction"] is None
    assert r["hypothetical_DBC_dollars_times_historic_SEC_sector_share_not_beta"] is None


def test_at_source_first_available_can_only_use_december_filing():
    r = study(asof="2026-03-03")
    assert r["DBC_original_SEC_statement_date"] == "2025-12-31"
    assert 0.373 < float(r["DBC_reported_gross_futures_energy_notional_fraction"]) < 0.375


def test_refuse_fake_cash_factor_for_real_commodity_futures_ETF():
    p = deepcopy(c12.SYNTHETIC_PROPOSALS)
    p[1]["risk_factors"] = {"CASH": "1"}
    # The original synthetic capital arbiter alone trusts this arbitrary tag;
    # independent source preflight must reject it.
    raw = arbiter.simulate(
        register=json.loads(thesis.REGISTER.read_text()),
        proposals=p,
    )
    assert raw["hypothetical_invested_usd"] == "120.00"
    with pytest.raises(c12.PreflightStop, match="REJECT_CONTRADICTORY"):
        study(proposals=p)


def test_refuse_cash_factor_for_energy_equity():
    p = deepcopy(c12.SYNTHETIC_PROPOSALS)
    p[0]["risk_factors"] = {"CASH": "1"}
    with pytest.raises(c12.PreflightStop, match="REJECT_CONTRADICTORY"):
        study(proposals=p)


def test_original_thesis_guard_prevents_unregistered_strategy():
    p = deepcopy(c12.SYNTHETIC_PROPOSALS)
    p[1]["strategy_id"] = "V6-FUTURES-SUPERPROFIT"
    with pytest.raises(arbiter.ArbiterStop, match="Unknown"):
        study(proposals=p)


def test_pinned_original_C11_source_tamper_refuses_provenance(tmp_path):
    dst = tmp_path / c11.SUBDIR
    dst.mkdir(parents=True)
    for filename in c11.SOURCE_BLOBS:
        copy2(c11.ROOT / c11.SUBDIR / filename, dst / filename)
    assert study(source_root=tmp_path)
    victim = dst / "dbc_sec_futures_holdings_2026_q1_q2.csv"
    victim.write_bytes(victim.read_bytes().replace(b"2026-08-10", b"2026-08-09", 1))
    with pytest.raises(c11.FilingLookthroughStop, match="transcription"):
        study(source_root=tmp_path)


def test_original_live_manifest_and_operator_unaltered():
    manifest = json.loads(
        Path("research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json").read_text())
    control = json.loads(Path("fund100_live_operator_control.json").read_text())
    assert manifest["investable_gross_fraction"] == "0.95"
    assert manifest["live_order_execution_released"] is False
    assert manifest["live_environment_kill_switch"] == "ENGAGED"
    assert control["trading_enabled"] is False
    assert not c12.BROKER_OR_PRIVATE_STATE_ACCESS
    assert not c12.LIVE_AUTHORIZED


def test_pure_research_module_no_broker_network_or_private_state_operations():
    s = Path(c12.__file__).read_text()
    for forbidden in ("requests.get(", "requests.post(", "urlopen(",
                      "api.alpaca.markets", "/v2/orders",
                      "FUND100_PRIVATE_STATE_READ_TOKEN", "place_order(",
                      "GH_TOKEN"):
        assert forbidden not in s
