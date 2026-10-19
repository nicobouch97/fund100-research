"""V6-S1 private source reliability on SYNTHETIC original V5 fixtures only."""
from copy import deepcopy
from datetime import datetime,timezone
import ast
from pathlib import Path
import pytest

from test_fund100_v6_real_live_getonly_transition_readiness_v1_0 import fx
import fund100_v6_s1_live_risk_history_getonly_v1_0 as v

def case():
    data=fx()
    equity=data["account"]["equity"]
    data["account"]["last_equity"]=equity
    data["account"]["multiplier"]="1"
    now=int(datetime.now(timezone.utc).timestamp())
    data["history"]={
      "timeframe":"1D",
      "timestamp":[now-86400*(7-i) for i in range(7)],
      "equity":[equity]*7
    }
    return data

def test_valid_fake_original_broker_history_makes_no_live_release_claim():
    r=v.review(**case())
    assert r["schema"]==v.SCHEMA
    assert r["source_original_account_binding_matched"]
    assert r["original_four_positions_quantities_reconciled"]
    assert r["broker_open_order_count"]==0
    assert r["broker_get_requests"]==5 and r["broker_non_get_requests"]==0
    assert r["raw_broker_portfolio_history_guard_passed"]
    assert r["broker_margin_multiplier_one_observed"]
    assert not r["raw_equity_history_cashflow_adjusted"]
    assert not r["account_daily_loss_6pct_pretrade_release_proven"]
    assert not r["account_drawdown_20pct_pretrade_release_proven"]
    assert not r["account_realized_volatility_35pct_pretrade_release_proven"]
    assert not r["actual_t_plus_one_spendable_cash_proven"]
    assert not r["live_order_history_all_client_ids_reconciled"]
    assert not r["live_v6_buy_or_sale_authorized"]
    assert r["live_orders_submitted"]==0
    assert r["executable_order_payload"] is None
    assert "SYNTHETIC-ACCOUNT-ID" not in str(r)
    assert case()["account"]["equity"] not in str(r)

@pytest.mark.parametrize("bad",[
    {},
    {"timeframe":"5Min","timestamp":[1,2],"equity":[1,2]},
    {"timeframe":"1D","timestamp":[1,2],"equity":[10,10]},
    {"timeframe":"1D","timestamp":[1],"equity":["NaN"]},
])
def test_short_malformed_and_unknown_history_do_not_claim_risk_pass(bad):
    f=case();f["history"]=bad
    r=v.review(**f)
    assert r["raw_broker_portfolio_history_result"]=="RAW_BROKER_EQUITY_HISTORY_INSUFFICIENT_OR_RISK_STOP"
    assert r["raw_broker_portfolio_history_guard_passed"] is False
    assert r["live_v6_buy_or_sale_authorized"] is False

@pytest.mark.parametrize("account_field,bad",[
    ("multiplier","4"),("multiplier",None)
])
def test_margin_features_not_mislabeled_as_cash_only(account_field,bad):
    f=case();f["account"][account_field]=bad
    r=v.review(**f)
    assert r["broker_margin_multiplier_one_observed"] is False
    assert not r["live_v6_buy_or_sale_authorized"]

@pytest.mark.parametrize("component,key,bad",[
    ("account","id","SPOOFED"),
    ("account","equity","0"),
    ("account","status","INACTIVE"),
    ("clock","is_open","True"),
    ("positions",None,[]),
    ("orders",None,[{"symbol":"ACWI","status":"new"}]),
])
def test_original_source_spoofed_or_open_orders_fails_closed(component,key,bad):
    f=case()
    if key is None:f[component]=bad
    else:f[component][key]=bad
    with pytest.raises(v.PrivateRiskReadStop):v.review(**f)

def test_history_risk_stop_does_not_forge_good_risk():
    f=case()
    f["account"]["last_equity"]=str(float(f["account"]["equity"])*1.2)
    r=v.review(**f)
    assert not r["raw_broker_portfolio_history_guard_passed"]
    assert not r["live_v6_buy_or_sale_authorized"]

def test_source_only_five_endpoints_and_no_writer_access_in_observer():
    assert v.PATHS==("/v2/account","/v2/positions","/v2/orders","/v2/clock",
                     "/v2/account/portfolio/history")
    assert v.HISTORY_PARAMS=={"period":"1M","timeframe":"1D"}
    src=Path(v.__file__).read_text()
    for needle in ("method=\"POST\"","requests.post(","submit_authorized_order_batch(","place_order(","/v2/orders:by_client_order_id"):
        assert needle not in src
    tree=ast.parse(src)
    assert not any(isinstance(n,ast.FunctionDef) and n.name in ("submit_order","place_order")
                   for n in ast.walk(tree))
