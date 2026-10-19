"""Synthetic tests for non-executable existing-XLE reuse and staged V6 migration."""
import json
from pathlib import Path
import pytest
import fund100_v6_s1_low_churn_migration_v2_0 as m

NOW="2026-10-19T15:00:00Z"

def snapshot(**updates):
    d={
     "schema":"FUND100_V6_S1_SYNTHETIC_LOW_CHURN_SNAPSHOT_V1",
     "mode":"INVENTED_VALUES_ONLY_NO_AUTHENTIC_BROKER",
     "observed_at_utc":"2026-10-19T14:59:50Z",
     "operator_stopped":True,"kill_switch":"ENGAGED",
     "open_orders":0,"equity_usd":"130.30","cash_usd":"10.30",
     "positions_market_value_usd":{"ACWI":"70.00","EEM":"12.00","XLE":"20.00","XLV":"18.00"},
     "independent_t_plus_one_settlement_proven":False
    }
    d.update(updates)
    return d

def test_policy_binds_actual_paper_run_and_new_readonly_live_run_without_order_authority():
    p=m.policy()
    assert p["paper_executable_mechanics"]["workflow_run_id"]==39269640353
    assert p["fresh_original_live_get_only"]["workflow_run_id"]==39272813574
    assert p["legacy_nonoverlap_to_exit_after_risk_review"]==["ACWI","EEM","XLV"]
    assert p["overlap_to_retain_if_no_breach"]==["XLE"]
    assert p["new_cash_rule"]["continuous_minimum_claim"] is False
    assert p["new_cash_rule"]["order_time_cash_floor"]=="0.05"
    assert p["may_place_sell_orders"] is False and p["may_place_buy_orders"] is False

def test_current_four_portfolio_keeps_xle_and_does_not_sell_anything():
    z=m.check(source=snapshot(),now_utc=NOW)
    assert z["status"]=="LEGACY_THREE_NOT_YET_EXITED_HOLD_ONLY"
    assert z["legacy_nonoverlap_count"]==3
    assert z["original_xle_overlap_can_be_reused_after_controls"]
    assert z["broker_orders"]==z["broker_requests"]==0
    assert z["executable_order_payload"] is None
    assert not z["actual_live_sale_authorized"] and not z["actual_live_buy_authorized"]

def test_open_orders_block_any_transition():
    z=m.check(source=snapshot(open_orders=1),now_utc=NOW)
    assert z["status"]=="BLOCKED_EXISTING_ORDER_MANUAL_RECONCILIATION"

def test_overlap_overweight_does_not_auto_sell_xle():
    z=m.check(source=snapshot(cash_usd="5.30",positions_market_value_usd={
        "ACWI":"55","EEM":"12","XLV":"15","XLE":"43"}),now_utc=NOW)
    assert z["status"]=="REVIEW_XLE_OVER_TARGET_BEFORE_REUSE"
    assert not z["original_xle_overlap_can_be_reused_after_controls"]
    assert z["broker_orders"]==0

def test_mixed_migration_needs_reconciliation():
    z=m.check(source=snapshot(positions_market_value_usd={
        "ACWI":"70","XLE":"20","XLK":"30.0"},cash_usd="10.30"),now_utc=NOW)
    assert z["status"]=="BLOCKED_MIXED_V5_V6_HOLDINGS_RECONCILIATION"

def test_legacy_exited_but_settlement_not_attested_stays_blocked():
    z=m.check(source=snapshot(positions_market_value_usd={"XLE":"20"},
             cash_usd="110.30"),now_utc=NOW)
    assert z["status"]=="AWAIT_INDEPENDENT_BROKER_SETTLEMENT_PROOF"

def test_claimed_settlement_alone_does_not_generate_live_orders():
    z=m.check(source=snapshot(positions_market_value_usd={"XLE":"20"},
             cash_usd="110.30",independent_t_plus_one_settlement_proven=True),now_utc=NOW)
    assert z["status"]=="AWAIT_NEW_VERSIONED_LIVE_POLICY_AND_RISK_CONTROLLER"
    assert not z["source_is_original_broker_authenticated"]
    assert not z["cash_settlement_independently_verified_by_module"]
    assert z["broker_orders"]==0

@pytest.mark.parametrize("changes",[
    {"operator_stopped":False},{"kill_switch":"DISENGAGED"},
    {"open_orders":None},{"open_orders":-1},{"open_orders":True},
    {"cash_usd":"Infinity"},{"cash_usd":"-1"},{"cash_usd":"110"},
    {"equity_usd":"0"},
    {"positions_market_value_usd":{"BTCUSD":"120"}},
    {"positions_market_value_usd":{"XLE":0}},
    {"observed_at_utc":"2026-10-19T14:49:00Z"},
    {"observed_at_utc":"2026-10-19T15:00:10Z"},
    {"mode":"ALPACA_LIVE_GET_ONLY"},
])
def test_invalid_or_live_claimed_snapshots_rejected(changes):
    with pytest.raises(m.MigrationStop):
        m.check(source=snapshot(**changes),now_utc=NOW)

@pytest.mark.parametrize("field,bad",[
    ("status","LIVE_AUTHORIZED"),
    ("may_place_sell_orders",True),
    ("may_place_buy_orders",True),
    ("leverage_allowed",True),
    ("original_trial_capital_limit_usd","130.31"),
    ("legacy_nonoverlap_to_exit_after_risk_review",["ACWI","EEM","XLV","XLE"]),
    ("overlap_to_retain_if_no_breach",[]),
])
def test_policy_must_not_mutate_to_accidentally_authorize_live(tmp_path,field,bad):
    data=json.loads(m.CANDIDATE.read_text());data[field]=bad
    path=tmp_path/"candidate.json";path.write_text(json.dumps(data))
    with pytest.raises(m.MigrationStop):m.policy(path)

def test_source_no_broker_client_or_order_operation():
    source=(Path(__file__).resolve().parent/"fund100_v6_s1_low_churn_migration_v2_0.py").read_text()
    for t in ("ALPACA_LIVE_KEY","ALPACA_PAPER_KEY","/v2/orders","requests.post(","urlopen(","submit_authorized_order_batch("):
        assert t not in source
