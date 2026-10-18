"""V6 actual LIVE GET-only account preflight: synthetic response contracts.

No authentic user account finance appears in fixtures. All account
values and IDs in this test are fictional. Do not print or archive
actual LIVE mark, balance, quantity or cash data in Actions.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from decimal import Decimal
from pathlib import Path
import pytest

import fund100_v6_real_live_getonly_transition_readiness_v1_0 as v6
import fund100_v6_brokerless_transition_preview_v1_0 as original

ROOT=Path(__file__).resolve().parent


def fx():
    boots,_=original.original(ROOT/"live_activation_outputs/v5_002/live_bootstrap_v1_0.json")
    policy,_=original.original(ROOT/"live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
    ctrl,_=original.original(ROOT/"fund100_live_operator_control.json")
    # The binding hash is tested against the existing original pilot
    # policy; no real IDs ever need to appear in tests.
    import hashlib
    # Test only pure economic checks by replacing original policy with a
    # synthetic binding matching synthetic identity.
    policy=deepcopy(policy)
    policy["account_binding_sha256"]=hashlib.sha256(b"FUND100-LIVE-ACCOUNT|SYNTHETIC-ACCOUNT-ID").hexdigest()
    boots=deepcopy(boots)
    boots["account_binding_sha256"]=policy["account_binding_sha256"]
    qty={s:Decimal(str(item["filled_qty"])) for s,item in boots["orders"].items()}
    marks={s:Decimal("100") for s in qty}
    pos=[{"symbol":s,"qty":str(q),"current_price":"100.00",
          "market_value":str((q*marks[s]).quantize(Decimal(".000001")))}
         for s,q in qty.items()]
    assets=sum(Decimal(x["market_value"]) for x in pos)
    cash=Decimal("0.37")
    account={
        "id":"SYNTHETIC-ACCOUNT-ID","status":"ACTIVE",
        "account_blocked":False,"trading_blocked":False,
        "cash":str(cash),"equity":str(assets+cash),
    }
    return {
        "account":account,"positions":pos,"orders":[],
        "clock":{"is_open":False},
        "bootstrap":boots,"policy":policy,"control":ctrl,
        "remotely_stopped":True,"kill_switch":"ENGAGED","risk_level":"HIGH",
        "observed_at_utc":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def test_original_four_holdings_and_get_only_safe_summary():
    f=fx()
    result=v6.check_account(**f)
    assert result["schema"]==v6.SCHEMA
    assert result["account_binding_matches_original_policy"]
    assert result["historic_four_original_etf_quantities_reconciled"]
    assert result["present_symbols_correspond_to_original_four"]
    assert result["market_regular_session_open"] is False
    assert result["open_order_count"]==0
    assert result["equity_usd"] is None and result["cash_usd"] is None
    assert result["position_quantities"] is None and result["account_id"] is None
    assert result["broker_get_requests"]==4
    assert result["broker_non_get_requests"]==0
    assert result["broker_orders_submitted"]==0
    assert result["current_strategy_decision"]=="HOLD_EXISTING_FOUR_ETFS_NO_SELL"
    assert result["future_v6_replacement_strategy_approved"] is False
    assert not result["account_real_sell_orders_authorized"]
    assert not result["live_autonomous_order_execution_authorized"]
    assert "SYNTHETIC-ACCOUNT-ID" not in str(result)
    assert "100.00" not in str(result)


@pytest.mark.parametrize("type_,field,value",[
    ("account","id","WRONG-ACCOUNT"),
    ("account","status","INACTIVE"),
    ("account","trading_blocked",True),
    ("account","cash","-1.00"),
    ("account","equity","NaN"),
    ("account","equity","10000.00"),
    ("clock","is_open","False"),
    ("clock","is_open",None),
])
def test_wrong_account_cash_or_clock_refused(type_,field,value):
    f=fx()
    f[type_][field]=value
    with pytest.raises(v6.ReadinessStop):
        v6.check_account(**f)


def test_futures_and_unapproved_positions_never_fit_old_account():
    f=fx()
    f["positions"][0]["symbol"]="MCL"
    with pytest.raises(v6.ReadinessStop):
        v6.check_account(**f)
    f=fx()
    f["positions"].append(deepcopy(f["positions"][0]))
    with pytest.raises(v6.ReadinessStop):
        v6.check_account(**f)


def test_account_drift_change_quantity_or_price_coherence_refused():
    f=fx()
    f["positions"][0]["qty"]="99.00"
    with pytest.raises(v6.ReadinessStop):
        v6.check_account(**f)
    f=fx()
    f["positions"][0]["market_value"]="1000000.00"
    with pytest.raises(v6.ReadinessStop):
        v6.check_account(**f)


def test_unreconciled_existing_broker_orders_block_transition():
    f=fx()
    f["orders"]=[{"symbol":"ACWI","id":"FICTIONAL-OPEN-ORDER"}]
    with pytest.raises(v6.ReadinessStop,match="Existing LIVE orders"):
        v6.check_account(**f)


@pytest.mark.parametrize("key,value",[
    ("kill_switch","DISENGAGED"),
    ("risk_level","LOW"),
    ("remotely_stopped",False),
])
def test_remote_stop_and_environment_switch_cannot_be_bypassed(key,value):
    f=fx()
    f[key]=value
    with pytest.raises(v6.ReadinessStop):
        v6.check_account(**f)


def test_controlled_cash_threshold_can_be_below_one_dollar():
    f=fx()
    out=v6.check_account(**f)
    assert out["account_cash_and_holdings_reconcile_to_equity"]
    assert not out["unsettled_sale_proceeds_spendable_verified"]


def test_future_or_stale_observation_refused():
    f=fx()
    f["observed_at_utc"]=(datetime.now(timezone.utc)-timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with pytest.raises(v6.ReadinessStop,match="not recent"):
        v6.check_account(**f)
    f=fx()
    f["observed_at_utc"]=(datetime.now(timezone.utc)+timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with pytest.raises(v6.ReadinessStop,match="not recent"):
        v6.check_account(**f)


def test_no_live_permission_even_if_market_open():
    f=fx()
    f["clock"]["is_open"]=True
    out=v6.check_account(**f)
    assert out["market_regular_session_open"]
    assert out["broker_orders_submitted"]==0
    assert not out["account_real_sell_orders_authorized"]


def test_policy_approval_creep_is_blocked():
    f=fx()
    f["policy"]["live_order_authorization_present"]=True
    with pytest.raises(v6.ReadinessStop):
        v6.check_account(**f)
