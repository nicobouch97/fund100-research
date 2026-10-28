"""Credentialless first-original ACWI ACTIVE HIGH SELL-only broker-source checks."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import pytest

import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as active
import fund100_v6_s1_fresh_acwi_order_time_risk_getonly_v1_0 as stopped

QTY="1.0"
KEY="synthetic-no-live-key"
SECRET="synthetic-no-live-secret"
ACCOUNT="synthetic-original-account-for-test"

def mock_sources(monkeypatch, *, enabled=True, mutations=None):
    monkeypatch.setattr(active,"ACTIVE_HIGH_SELL_SOURCE_RELEASED",enabled)
    env={
        "GITHUB_ACTIONS":"true",
        "GITHUB_REPOSITORY":"nicobouch97/fund100-research",
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_EVENT_NAME":"workflow_dispatch",
        "GITHUB_RUN_ATTEMPT":"1","FUND100_RISK_LEVEL":"HIGH",
        "FUND100_BROKER_KILL_SWITCH":"DISENGAGED",
        "FUND100_ENABLE_LIVE_READONLY":"YES_READ_ONLY_LIVE",
    }
    for k,v in env.items(): monkeypatch.setenv(k,v)
    state={"operator":True,"v5_stopped":True,"reads":0,"operator_gets":0}
    def old_control():
        return {"schema":active.operator.CONTROL_SCHEMA,
                "trading_enabled":not state["v5_stopped"]}
    monkeypatch.setattr(active.operator,"read_current_control",old_control)
    def v6_running():
        state["operator_gets"]+=1
        if not state["operator"]:
            raise active.v6_operator.V6OperatorStop("V6 execution stopped")
        return True
    monkeypatch.setattr(active.v6_operator,"require_s1_running",v6_running)
    monkeypatch.setattr(active.broker,"require_readonly_arm",lambda:None)
    bound=sha256(("FUND100-LIVE-ACCOUNT|"+ACCOUNT).encode()).hexdigest()
    bootstrap={"bootstrap":"synthetic"}
    policy={
        "capital_ceiling_usd":"130.30",
        "leverage_allowed":False,
        "shorting_allowed":False,
        "additional_deposits_automatically_usable":False,
        "account_binding_sha256":bound,
    }
    monkeypatch.setattr(active.original,"original",
       lambda x:(deepcopy(bootstrap if x==active.four.BOOT else policy),"sha"))
    monkeypatch.setattr(active.original,"check_original",
       lambda bootstrap,policy,control: {p:active.Decimal("1.0") for p in
              ("ACWI","EEM","XLE","XLV")})
    now=datetime.now(timezone.utc)
    account={
        "id":ACCOUNT,"status":"ACTIVE","account_blocked":False,
        "trading_blocked":False,"multiplier":"1",
        "cash":"60.00","equity":"100.00","last_equity":"100.00",
    }
    positions=[
        {"symbol":s,"qty":"1.0","current_price":"10.00",
         "market_value":"10.00"}
        for s in ("ACWI","EEM","XLE","XLV")
    ]
    docs=[
        account,positions,[],
        {"is_open":True,"timestamp":now.isoformat(),
         "next_close":(now+timedelta(hours=2)).isoformat()},
        {"history":"masked"},
        [{"id":"funding-only","activity_type":"CSD","net_amount":"100.00",
          "date":"2026-10-01"}],
        {"history":"masked-none"},
    ]
    if mutations is not None:mutations(docs)
    endpoints=(
        ("/v2/account",None),
        ("/v2/positions",None),
        ("/v2/orders",{"status":"open","limit":100}),
        ("/v2/clock",None),
        (active.five.HISTORY_PATH,active.five.HISTORY_PARAMS),
        (active.six.ACTIVITIES_PATH,active.six.ACTIVITY_PARAMS),
        (active.five.HISTORY_PATH,active.seven.EXTRA_PARAMS),
    )
    def get_json(*,path,params,key,secret):
        assert key==KEY and secret==SECRET
        n=state["reads"]
        assert n<7 and (path,params)==endpoints[n]
        state["reads"]+=1
        return deepcopy(docs[n])
    monkeypatch.setattr(active.broker,"get_json",get_json)
    monkeypatch.setattr(active.cashrisk,"inspect",lambda **kw:{
        "schema":active.cashrisk.STATUS_SCHEMA,
        "strictly_postfunding_account_6_20_35_source_verified":True,
        "source_rejection_category":"NONE",
        "live_buy_sell_authorized":False,
    })
    monkeypatch.setattr(active.seven,"broker_native_none_source",lambda *a:
       "BROKER_NATIVE_NONE_PNL_SERIES_SAME")
    return state,docs

def test_source_is_hard_locked_and_makes_zero_broker_gets_by_default(monkeypatch):
    s,_=mock_sources(monkeypatch,enabled=False)
    with pytest.raises(active.ActiveSellStop,match="HARD LOCKED"):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert s["reads"]==s["operator_gets"]==0
    assert active.NO_BROKER_POST is True

def test_active_high_exact_real_get_path_yields_only_sell_scope(monkeypatch):
    s,_=mock_sources(monkeypatch)
    got=stopped.inspect_actual_original_seven_get(
        original_qty=QTY,key=KEY,secret=SECRET)
    assert got["status"]=="ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2"
    assert got["broker_order_authorized"] is True
    assert got["same_process_real_broker_gets"]==7
    assert got["sell_only_original_legacy_ACWI"] is True
    assert got["buy_authorized"] is False
    assert got["full_original_acwi_exit_bounded_by_authenticated_inventory"] is True
    assert got["maximum_new_order_notional_usd"]=="65.00"
    assert got["capital_ceiling_usd"]=="130.30"
    assert got["broker_post_attempts"]==0
    assert s["reads"]==7 and s["operator_gets"]==2
    for private in (ACCOUNT,QTY,KEY,SECRET):
        assert private not in str(got)
    assert all(got.get(k) is None for k in (
        "account_id","account_equity","holdings","activities",
        "original_qty","broker_secrets"))

@pytest.mark.parametrize("key,value",[
    ("GITHUB_ACTIONS","false"),("GITHUB_REF","refs/heads/test"),
    ("GITHUB_EVENT_NAME","push"),("GITHUB_RUN_ATTEMPT","2"),
    ("FUND100_RISK_LEVEL","LOW"),("FUND100_BROKER_KILL_SWITCH","ENGAGED"),
    ("FUND100_ENABLE_LIVE_READONLY","NO"),
])
def test_unauthorized_environment_never_contacts_broker(monkeypatch,key,value):
    s,_=mock_sources(monkeypatch)
    monkeypatch.setenv(key,value)
    with pytest.raises(active.ActiveSellStop):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert s["reads"]==0

def test_independent_current_v6_operator_must_be_enabled_before_and_after_reads(monkeypatch):
    s,_=mock_sources(monkeypatch)
    s["operator"]=False
    with pytest.raises(active.ActiveSellStop):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert s["reads"]==0
    s["operator"]=True
    old=active.broker.get_json
    def changed(**kwargs):
        response=old(**kwargs)
        if s["reads"]==7:s["operator"]=False
        return response
    monkeypatch.setattr(active.broker,"get_json",changed)
    with pytest.raises(active.ActiveSellStop):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert s["reads"]==7

def test_original_v5_operator_must_remain_stop_even_if_v6_operator_enabled(monkeypatch):
    state,_=mock_sources(monkeypatch)
    state["v5_stopped"]=False
    with pytest.raises(active.ActiveSellStop):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert state["reads"]==0 and state["operator_gets"]==0


@pytest.mark.parametrize("change",[
    lambda z:z[0].update(id="different-account"),
    lambda z:z[0].update(trading_blocked=True),
    lambda z:z[0].update(status="INACTIVE"),
    lambda z:z[0].update(multiplier="2"),
    lambda z:z[0].update(cash="200"),
    lambda z:z[1][0].update(qty="0.98"),
    lambda z:z[1][0].update(current_price="80",market_value="80"),
    lambda z:z[1][0].update(market_value="15"),
    lambda z:z[1].append({"symbol":"SPY","qty":"1","market_value":"1"}),
    lambda z:z[2].append({"symbol":"ACWI","side":"buy"}),
    lambda z:z[3].update(is_open=False),
    lambda z:z[3].update(timestamp="2020-01-01T00:00:00Z"),
    lambda z:z[3].update(next_close="2020-01-01T00:00:00Z"),
    lambda z:z[5][0].update(net_amount="200.00"),
    lambda z:z[5].append({"activity_type":"CSD","net_amount":"1","id":"extra"}),
])
def test_active_broker_source_rejects_modified_account_holdings_clock_or_funding(
        monkeypatch,change):
    s,_=mock_sources(monkeypatch,mutations=change)
    with pytest.raises(active.ActiveSellStop):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert s["reads"]==7

@pytest.mark.parametrize("risk",[
    {"strictly_postfunding_account_6_20_35_source_verified":False},
    {"source_rejection_category":"INSUFFICIENT_FUNDED_HISTORY"},
    {"schema":"FAKE"},
])
def test_risk_break_cannot_authorize_sell(monkeypatch,risk):
    s,_=mock_sources(monkeypatch)
    def bad(**kwargs):
        return dict({
            "schema":active.cashrisk.STATUS_SCHEMA,
            "strictly_postfunding_account_6_20_35_source_verified":True,
            "source_rejection_category":"NONE",
        },**risk)
    monkeypatch.setattr(active.cashrisk,"inspect",bad)
    with pytest.raises(active.ActiveSellStop):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert s["reads"]==7

def test_live_source_cannot_send_broker_order_and_original_hist_evidence_is_unchanged():
    from pathlib import Path
    code=Path(active.__file__).read_text()
    assert "method=\"POST\"" not in code
    assert "urlopen(" not in code
    assert "def main(" not in code
    assert "ACTIVE_HIGH_SELL_SOURCE_RELEASED=False" in code
    assert "broker.get_json(" in code
    assert "cashrisk.inspect(" in code
    assert "operator.read_current_control()" in code
    assert "v6_operator.require_s1_running()" in code
    assert "operator.validate_control(operator.read_current_control()) is not False" in code
    assert "trading_enabled\":False" in code
