"""Original V6-S1 separate HIGH release-CANDIDATE, NO orders."""
import json
from pathlib import Path
from shutil import copy2

import pytest

import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as m


ORIGINAL_FILES = (
    m.PROPOSAL, m.ORIGINAL_MANIFEST, m.ORIGINAL_V5_POLICY,
    m.ORIGINAL_OPERATOR, m.HIGH_SOURCE, m.SELL_SOURCE, m.CAS_SOURCE,
)


def fixtures(tmp_path):
    for path in ORIGINAL_FILES:
        dest = tmp_path / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        copy2(m.ROOT/path,dest)
    return tmp_path


def override(path, target):
    p=path/m.PROPOSAL
    document=json.loads(p.read_text())
    document.update(target)
    p.write_text(json.dumps(document,indent=2))


def test_source_pinned_real_original_high_and_private_genesis():
    x=m.contract()
    assert x["stage"] == "RECONCILED_SEPARATE_V6_HIGH_PROPOSED_POLICY_NO_ORDERS"
    assert x["legacy_sells_in_order"] == ["ACWI","EEM","XLV"]
    assert x["retains_original_XLE_subject_to_target"]
    assert x["new_V6_HIGH_strategy_uses_separate_50pct_symbol_limit"]
    assert x["V5_25pct_cap_remains_on_old_V5_only"]
    assert x["source_pinned_original_manifest_unchanged"]
    assert x["production_genesis_independent_HMAC_recovery_historical_run"] == 39638576563
    assert x["target_weights"] == {"XLK":"0.475", "XLE":"0.285", "IWM":"0.190"}
    assert x["privileged_future_head_rollback_still_possible"]
    assert x["current_original_operator_stopped"]
    assert not x["actual_broker_state_reauthenticated_by_this_module"]
    assert not x["all_original_order_ids_and_settlement_reconciled"]
    assert not x["orders_authorized"]
    assert x["broker_GETs"] == x["broker_POSTs"] == x["private_Git_writes"] == 0


@pytest.mark.parametrize("wrong", [
    {"status":"LIVE_ACTIVE"},
    {"broker_sell_authorized": True},
    {"broker_buy_authorized": True},
    {"execution_authorized": True},
    {"separately_signed_live_release_present": True},
    {"operator_trading_enabled": True},
    {"environment_kill_switch": "DISENGAGED"},
    {"future_signed_private_head_advances_independently_anchored": True},
    {"production_ledger_future_state_advances_released": True},
    {"real_live_full_broker_fill_history_reconciled": True},
    {"original_private_signed_ledger_mutated": True},
    {"retained_overlap_may_be_sold_automatically": True},
    {"original_exploratory_manifest_lists_XLE_for_legacy_exit": False},
    {"requires_new_separate_V6_risk_policy_instead_of_silent_V5_override": False},
    {"legacy_nonoverlap_etfs_to_sell_in_sequence": ["ACWI","EEM","XLE","XLV"]},
    {"legacy_nonoverlap_etfs_to_sell_in_sequence": ["ACWI","XLV","EEM"]},
    {"evidence_independent_hmac_recovery_run_id": 39634023520},
])
def test_any_silent_live_release_or_incorrect_xle_legacy_exit_denied(tmp_path,wrong):
    fixtures(tmp_path)
    override(tmp_path,wrong)
    with pytest.raises(m.PolicyReconciliationStop):
        m.contract(root=tmp_path)


@pytest.mark.parametrize("wrong",[
    {"proposed_target_weights":{"XLK":"0.50","XLE":"0.285","IWM":"0.190"}},
    {"proposed_target_weights":{"XLK":"0.475","XLE":"0.285","IWM":"0.19","ACWI":"0.001"}},
    {"proposed_target_weights":{"XLK":"0.675","XLE":"0.285","IWM":"0"}},
    {"maximum_single_symbol_fraction":"0.25"},
    {"max_gross_exposure_fraction":"1.00"},
    {"order_time_cash_floor_fraction":"0.00"},
    {"maximum_daily_account_loss_fraction":"0.10"},
    {"maximum_peak_to_trough_drawdown_fraction":"0.40"},
    {"maximum_annual_realized_account_volatility":"0.90"},
    {"maximum_new_order_notional_usd":"130.30"},
    {"original_live_pilot_capital_ceiling_usd":"500.00"},
])
def test_changed_allocation_cap_loss_or_cash_ceiling_denied(tmp_path,wrong):
    fixtures(tmp_path)
    override(tmp_path,wrong)
    with pytest.raises(m.PolicyReconciliationStop):
        m.contract(root=tmp_path)


@pytest.mark.parametrize("source",[
    m.ORIGINAL_V5_POLICY, m.ORIGINAL_MANIFEST, m.HIGH_SOURCE,
    m.SELL_SOURCE,m.CAS_SOURCE])
def test_original_live_or_signed_genesis_source_must_not_be_modified(tmp_path,source):
    fixtures(tmp_path)
    path = tmp_path/source
    path.write_bytes(path.read_bytes()+b"\n")
    with pytest.raises(m.PolicyReconciliationStop):
        m.contract(root=tmp_path)


def test_live_operator_changed_blocks_candidate(tmp_path):
    fixtures(tmp_path)
    path=tmp_path/m.ORIGINAL_OPERATOR
    row=json.loads(path.read_text())
    row["trading_enabled"]=True
    path.write_text(json.dumps(row))
    with pytest.raises(m.PolicyReconciliationStop):
        m.contract(root=tmp_path)


def test_historical_broker_evidence_does_not_authorize_live_orders():
    a=m.contract()
    assert a["orders_authorized"] is False
    assert a["separately_signed_release_present"] is False
    assert a["all_original_order_ids_and_settlement_reconciled"] is False
    s=Path(m.__file__).read_text()
    for forbidden in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
        "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
        "/v2/orders", "urlopen(", "place_order(", "submit_order("):
        assert forbidden not in s
    assert m.REAL_LIVE_ORDER_TRANSPORT_RELEASED is False
