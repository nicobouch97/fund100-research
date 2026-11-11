"""Credentialless original ACWI preclaim economics: NO_TRADE without alpha."""
from copy import deepcopy

import pytest
import fund100_v6_s1_first_acwi_economic_preclaim_v1_0 as economic

QTY="0.1234567"
RISK={
    "status":"ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2",
    "same_process_real_broker_gets":8,
    "original_acwi_exact_fractional_holdings_verified":True,
    "original_strict_postfunding_6_20_35_risk_pass":True,
    "unattributed_credit_or_new_principal_spend_authorized":False,
    "original_acwi_sell_only_no_additional_principal_deployment":True,
}

def fake_qualified():
    """No genuine approved report exists: synthetic test-only."""
    return {
        "schema":economic.SCHEMA,
        "status":economic.MATCH_STATUS,
        "decision":"SELL_ONLY_AFTER_QUALIFIED_ECONOMIC_CASE",
        "original_qty":QTY,
        "economic_reason":"INDEPENDENTLY_SOURCED_COSTED_ROTATION",
        "source_owned_authentication":True,
        "source_premarket_availability_verified":True,
        "original_inventory_bound":True,
        "hold_acwi_comparator_included":True,
        "sale_replacement_and_cash_drag_after_costs_checked":True,
        "costed_positive_economic_case_or_independent_risk_reduction":True,
        "new_buy_or_new_principal_authorized":False,
        "risk_report_is_not_alpha":True,
        "broker_gets":0,"broker_posts":0,
        "signed_state_writes":0,"signed_owner_claims":0,"live_orders":0,
    }


def test_actual_main_economic_source_never_promotes_broker_risk_to_trade():
    assert economic.ECONOMIC_SOURCE_RELEASED is False
    assert economic.NO_BROKER_NETWORK
    assert economic.NO_PRIVATE_STATE_MUTATION
    assert economic.NO_EXECUTABLE_ORDER
    got=economic.inspect_current_original_exit(
        original_qty=QTY,broker_risk=deepcopy(RISK))
    assert got["status"]==economic.NO_TRADE_STATUS
    assert got["decision"]=="NO_TRADE_KEEP_ORIGINAL_ACWI"
    assert got["original_qty"] is None
    assert got["broker_gets"]==got["broker_posts"]==0
    assert got["signed_owner_claims"]==got["signed_state_writes"]==0
    with pytest.raises(economic.EconomicNoTrade):
        economic.require_preclaim_exit_economics(report=got,original_qty=QTY)


def test_even_a_forged_positive_report_cannot_bypass_main_source_release():
    with pytest.raises(economic.EconomicNoTrade):
        economic.require_preclaim_exit_economics(
            report=fake_qualified(),original_qty=QTY)


@pytest.mark.parametrize("field,value",[
    ("status","FORGED_POSITIVE"),
    ("decision","BUY_XLK_DIRECTLY"),
    ("economic_reason","UNVALIDATED_HISTORICAL_MOMENTUM"),
    ("economic_reason",None),
    ("economic_reason",["INDEPENDENTLY_SOURCED_COSTED_ROTATION"]),
    ("source_owned_authentication",False),
    ("source_premarket_availability_verified",False),
    ("original_inventory_bound",False),
    ("original_qty","0.1234568"),
    ("hold_acwi_comparator_included",False),
    ("sale_replacement_and_cash_drag_after_costs_checked",False),
    ("costed_positive_economic_case_or_independent_risk_reduction",False),
    ("new_buy_or_new_principal_authorized",True),
    ("risk_report_is_not_alpha",False),
    ("broker_gets",1),("broker_posts",1),
    ("signed_state_writes",1),("signed_owner_claims",1),
    ("live_orders",1),
])
def test_mock_released_validator_still_rejects_missing_or_corrupted_evidence(
        monkeypatch,field,value):
    monkeypatch.setattr(economic,"ECONOMIC_SOURCE_RELEASED",True)
    forged=fake_qualified()
    forged[field]=value
    with pytest.raises(economic.EconomicNoTrade):
        economic.require_preclaim_exit_economics(report=forged,original_qty=QTY)
    forged.pop(field)
    with pytest.raises(economic.EconomicNoTrade):
        economic.require_preclaim_exit_economics(report=forged,original_qty=QTY)


def test_only_mocked_reviewed_shape_passes_validation_not_production(monkeypatch):
    monkeypatch.setattr(economic,"ECONOMIC_SOURCE_RELEASED",True)
    report=fake_qualified()
    assert economic.require_preclaim_exit_economics(
        report=report,original_qty=QTY) is None
    report["economic_reason"]="INDEPENDENTLY_SOURCED_RISK_REDUCTION"
    assert economic.require_preclaim_exit_economics(
        report=report,original_qty=QTY) is None


@pytest.mark.parametrize("qty",[
    "0","-0.1","01.2","0.1 ","0.1234567891","nan","inf",None,1,
])
def test_absent_or_unrepresentable_original_quantity_is_not_a_decision(qty):
    with pytest.raises(economic.EconomicNoTrade):
        economic.inspect_current_original_exit(original_qty=qty,
                                                broker_risk=deepcopy(RISK))


@pytest.mark.parametrize("field,value",[
    ("status","PAPER_PASS"),
    ("same_process_real_broker_gets",7),
    ("original_acwi_exact_fractional_holdings_verified",False),
    ("original_strict_postfunding_6_20_35_risk_pass",False),
    ("unattributed_credit_or_new_principal_spend_authorized",True),
    ("original_acwi_sell_only_no_additional_principal_deployment",False),
])
def test_actual_unqualified_broker_risk_fails_even_before_economic_hold(
        field,value):
    risk=dict(RISK)
    risk[field]=value
    with pytest.raises(economic.EconomicNoTrade):
        economic.inspect_current_original_exit(original_qty=QTY,broker_risk=risk)
