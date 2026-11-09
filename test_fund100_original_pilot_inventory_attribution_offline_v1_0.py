"""Source-bound synthetic inventory diagnostics, never an ACWI SELL release."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import fund100_original_pilot_inventory_attribution_offline_v1_0 as m
import fund100_scalable_live_funding_history_getonly_v1_0 as funding

ROOT=Path(__file__).resolve().parent


def fixtures():
    root=ROOT/"live_activation_outputs"/"v5_002"
    boot=json.loads((root/"live_bootstrap_v1_0.json").read_text())
    policy=json.loads((root/"live_micro_pilot_policy_v1_0.json").read_text())
    ctrl=json.loads((ROOT/"fund100_live_operator_control.json").read_text())
    return boot,policy,ctrl


def report():
    return {
        "schema":funding.SCHEMA,
        "status":"OBSERVED_GROSS_FUNDING_ABOVE_ORIGINAL_PILOT_HOLD",
        "source_currency_metadata_missing":False,
        "original_account_identity_source_matched":True,
        "fixed_after_filter_inception_coverage_proved":False,
        "live_buy_sell_authorized":False,
        "broker_non_get_requests":0,
        "broker_orders":0,
    }


def evaluate(boot=None,policy=None,ctrl=None,funding_observation=None,
             positions=None,binding=None,orders=None,stop=True,kill="ENGAGED"):
    a,b,c=fixtures()
    boot=boot if boot is not None else a
    policy=policy if policy is not None else b
    ctrl=ctrl if ctrl is not None else c
    positions=positions if positions is not None else [
        {"symbol":name,"qty":str(boot["orders"][name]["filled_qty"])}
        for name in sorted(m.EXPECTED)]
    return m.evaluate(
        bootstrap=boot,policy=policy,control=ctrl,
        funding_observation=report() if funding_observation is None
            else funding_observation,
        model_positions=positions,
        broker_model_binding_sha256=policy.get("account_binding_sha256")
           if binding is None else binding,
        model_open_orders=[] if orders is None else orders,
        operator_stop=stop,broker_kill=kill)


def stopped(x):
    assert x["live_order_authorized"] is False
    assert x["original_acwi_sell_currently_released"] is False
    assert x["new_buy_authorized"] is False
    assert x["standing_capital_mandate_approved"] is False
    assert x["excess_deposits_actually_segregated"] is False
    assert x["settled_sale_proceeds_verified"] is False
    assert x["current_broker_positions_authenticated"] is False
    assert x["underlying_source_cashflow_complete_from_inception"] is False
    assert x["broker_GETs"]==x["broker_POSTs"]==x["actual_orders"]==0
    assert x["private_ledger_writes"]==0
    assert x["cash_usd"] is None
    assert x["account_id"] is None
    assert x["filled_quantities"] is None
    assert x["deposit_amounts"] is None
    assert x["historical_fill_dollars"] is None
    assert x["original_pilot_cap_unchanged"] is True


def test_checked_in_four_original_fills_are_face_value_within_pilot_cap():
    x=evaluate()
    assert x["stage"]=="RESEARCH_ONLY_ORIGINAL_FILLED_INVENTORY_WITHIN_CAP_NO_CASH_ATTRIBUTION"
    stopped(x)


def test_historical_fill_cost_over_cap_cannot_be_accepted():
    boot,_,_=fixtures()
    boot["orders"]["ACWI"]["filled_avg_price"]="999999.00"
    x=evaluate(boot=boot)
    assert x["stage"]=="HOLD_ORIGINAL_FILLS_FACE_COST_OVER_PILOT_CAP"
    stopped(x)


@pytest.mark.parametrize("mutate", [
    lambda x: x.pop(0),
    lambda x: x.append({"symbol":"QQQ","qty":"1"}),
    lambda x: x.__setitem__(0,{"symbol":"ACWI","qty":"0.0001"}),
    lambda x: x.__setitem__(0,{"symbol":"ACWI","qty":"10000"}),
    lambda x: x.__setitem__(0,{"symbol":"ACWI","qty":"-1.00"}),
    lambda x: x.__setitem__(0,{"symbol":"ACWI","qty":"NaN"}),
    lambda x: x.__setitem__(0,{"symbol":"ACWI","qty":"1e10"}),
    lambda x: x.__setitem__(0,{"symbol":"ACWI","qty":None}),
])
def test_current_holdings_drift_never_proves_original_inventory(mutate):
    positions=[{"symbol":s,"qty":str(q["filled_qty"])}
               for s,q in sorted(fixtures()[0]["orders"].items())]
    mutate(positions)
    result=evaluate(positions=positions)
    assert result["stage"].startswith("HOLD_")
    stopped(result)


def test_duplicate_symbol_inventory_is_held():
    boot=fixtures()[0]
    positions=[{"symbol":s,"qty":str(q["filled_qty"])}
               for s,q in sorted(boot["orders"].items())]
    positions[1]["symbol"]=positions[0]["symbol"]
    x=evaluate(positions=positions)
    assert x["stage"]=="HOLD_CURRENT_ORIGINAL_INVENTORY_DIFFERS_FROM_FILLS"
    stopped(x)


def test_an_open_broker_order_denies_any_inventory_based_candidate():
    x=evaluate(orders=[{"id":"untrusted"}])
    assert x["stage"]=="HOLD_CURRENT_ORIGINAL_ACCOUNT_INVENTORY_NOT_COBOUND"
    stopped(x)


@pytest.mark.parametrize("stop,kill",[(False,"ENGAGED"),(True,"DISENGAGED"),(None,"ENGAGED")])
def test_stop_stays_engaged_for_inventory_diagnostics(stop,kill):
    x=evaluate(stop=stop,kill=kill)
    assert x["stage"]=="HOLD_ORIGINAL_CAP_OR_STOP_POLICY_CHANGED"
    stopped(x)


def test_wrong_binding_rejects_candidate():
    x=evaluate(binding="f"*64)
    assert x["stage"]=="HOLD_CURRENT_ORIGINAL_ACCOUNT_INVENTORY_NOT_COBOUND"
    stopped(x)


def test_changed_original_mandate_cannot_authorize_more_cash():
    boot,policy,ctrl=fixtures()
    policy["capital_ceiling_usd"]="10000.00"
    x=evaluate(boot=boot,policy=policy,ctrl=ctrl)
    assert x["stage"]=="HOLD_ORIGINAL_BOOTSTRAP_OR_POLICY_NOT_AUTHENTICATED"
    stopped(x)
    boot,policy,ctrl=fixtures()
    policy["additional_deposits_automatically_usable"]=True
    x=evaluate(boot=boot,policy=policy,ctrl=ctrl)
    assert x["stage"]=="HOLD_ORIGINAL_BOOTSTRAP_OR_POLICY_NOT_AUTHENTICATED"
    stopped(x)


@pytest.mark.parametrize("changed", [
    {"status":"OBSERVED_FUNDING_WITHIN_ORIGINAL_CAP_REVIEW_ONLY"},
    {"status":"RESEARCH_ONLY_NEW_CAP_RELEASABLE"},
    {"source_currency_metadata_missing":True},
    {"original_account_identity_source_matched":False},
    {"fixed_after_filter_inception_coverage_proved":True},
    {"live_buy_sell_authorized":True},
    {"broker_orders":1},
    {"broker_non_get_requests":1},
    {"schema":"UNKNOWN_SOURCE"},
])
def test_untrusted_funding_source_does_not_promote_candidates(changed):
    source=report()
    source.update(changed)
    x=evaluate(funding_observation=source)
    assert x["stage"]=="HOLD_EXCESS_ACCOUNT_FUNDING_SOURCE_NOT_QUALIFIED"
    stopped(x)


def test_checked_in_loader_is_equally_stopped_and_no_private_source_returns():
    boot,policy,_=fixtures()
    x=m.run_checked_in_sources(
        funding_observation=report(),
        model_positions=[{"symbol":s,"qty":str(q["filled_qty"])}
                         for s,q in sorted(boot["orders"].items())],
        broker_model_binding_sha256=policy["account_binding_sha256"],
        model_open_orders=[],operator_stop=True,broker_kill="ENGAGED")
    assert x["stage"]=="RESEARCH_ONLY_ORIGINAL_FILLED_INVENTORY_WITHIN_CAP_NO_CASH_ATTRIBUTION"
    stopped(x)
    assert policy["account_binding_sha256"] not in str(x)


def test_source_has_no_remote_broker_or_trade_execution():
    code=(ROOT/"fund100_original_pilot_inventory_attribution_offline_v1_0.py").read_text()
    assert "urlopen" not in code
    assert "requests.post(" not in code
    assert "load_credentials" not in code
    assert "submit_order" not in code
    assert m.LIVE_ORDER_AUTHORIZED is False
    assert m.BROKER_GETS==m.BROKER_POSTS==m.PRIVATE_LEDGER_WRITES==0
