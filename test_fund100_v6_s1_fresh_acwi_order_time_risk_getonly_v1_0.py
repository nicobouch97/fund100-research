"""Same-process original ACWI broker seven-GET verifier, NO LIVE requests."""
from datetime import datetime,timezone,timedelta
from copy import deepcopy

import pytest

import fund100_v6_s1_fresh_acwi_order_time_risk_getonly_v1_0 as r

QTY="0.123456789"
GETS=r.seven.PATHS
REPORT={
    "schema":r.seven.SCHEMA,
    "source":"PRIVATE_ORIGINAL_SEVEN_GET_SOURCE_QUALIFICATION_ONLY",
    "original_account_and_legacy_positions_verified":True,
    "actual_s1_6_20_35_risk_verified":True,
    "broker_get_requests":7,"broker_non_get_requests":0,
    "live_orders":0,"live_buy_sell_authorized":False,
}

def fixture(monkeypatch,change=None):
    env={
        "GITHUB_ACTIONS":"true","GITHUB_EVENT_NAME":"workflow_dispatch",
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_REPOSITORY":"nicobouch97/fund100-research",
        "GITHUB_RUN_ATTEMPT":"1",
        "FUND100_BROKER_KILL_SWITCH":"ENGAGED",
        "FUND100_RISK_LEVEL":"HIGH",
        "FUND100_ENABLE_LIVE_READONLY":"YES_READ_ONLY_LIVE",
    }
    for k,v in env.items():monkeypatch.setenv(k,v)
    monkeypatch.setattr(r.operator,"read_current_control",lambda: {})
    monkeypatch.setattr(r.operator,"validate_control",lambda _: False)
    monkeypatch.setattr(r.live,"require_readonly_arm",lambda: None)
    monkeypatch.setattr(r.original,"original",lambda _:(
        {"live_order_authorization_present":False},None))
    now=datetime.now(timezone.utc)
    vals=[
        {"status":"ACTIVE"},
        [{"symbol":symbol,"qty":QTY if symbol=="ACWI" else "0.11"}
         for symbol in ("ACWI","EEM","XLE","XLV")],
        [],
        {"timestamp":now.isoformat(),
         "next_close":(now+timedelta(hours=2)).isoformat(),
         "is_open":True},
        {"history":"dummy"},
        [{"activity_type":"CSD","id":"redacted"}],
        {"history":"cashflow NONE dummy"},
    ]
    if change:
        change(vals)
    calls=[]
    def fake_get(*,path,key,secret,params=None):
        assert key=="test-key" and secret=="test-secret"
        idx=len(calls)
        assert idx<7
        assert (path,params)==(
            ("/v2/account",None),("/v2/positions",None),
            ("/v2/orders",{"status":"open","limit":100}),
            ("/v2/clock",None),
            (r.five.HISTORY_PATH,r.five.HISTORY_PARAMS),
            (r.six.ACTIVITIES_PATH,r.six.ACTIVITY_PARAMS),
            (r.five.HISTORY_PATH,r.seven.EXTRA_PARAMS),
        )[idx]
        calls.append(path)
        return deepcopy(vals[idx])
    monkeypatch.setattr(r.live,"get_json",fake_get)
    flags={"evaluate_calls":0}
    def evaluator(**kw):
        flags["evaluate_calls"]+=1
        assert kw["remotely_stopped"] is True
        assert kw["kill_switch"]=="ENGAGED"
        assert kw["risk_level"]=="HIGH"
        assert kw["positions"]==vals[1]
        assert kw["orders"]==vals[2]
        return deepcopy(REPORT)
    monkeypatch.setattr(r.seven,"evaluate",evaluator)
    return calls,flags

def test_same_process_seven_original_authenticated_gets_and_exact_qty_are_redacted(monkeypatch):
    calls,flags=fixture(monkeypatch)
    v=r.inspect_actual_original_seven_get(
        original_qty=QTY,key="test-key",secret="test-secret")
    assert tuple(calls)==GETS
    assert flags["evaluate_calls"]==1
    assert v["status"]=="ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_PASSED_STILL_STOPPED"
    assert v["original_acwi_exact_fractional_holdings_verified"]
    assert v["original_open_market_and_no_pending_order_verified"]
    assert v["original_strict_postfunding_6_20_35_risk_pass"]
    assert v["broker_order_authorized"] is False
    assert v["broker_post_attempts"]==0
    assert all(v[k] is None for k in (
        "account","positions","orders","original_qty","client_order_id",
        "private_risk_history","broker_credentials"))
    assert QTY not in str(v)

@pytest.mark.parametrize("key,value",[
    ("GITHUB_ACTIONS","false"),("GITHUB_EVENT_NAME","pull_request"),
    ("GITHUB_REF","refs/heads/something"),("GITHUB_RUN_ATTEMPT","2"),
    ("FUND100_BROKER_KILL_SWITCH","DISENGAGED"),
    ("FUND100_RISK_LEVEL","LOW"),
    ("FUND100_ENABLE_LIVE_READONLY","NO"),
])
def test_missing_original_protected_first_attempt_environment_no_get(monkeypatch,key,value):
    calls,_=fixture(monkeypatch)
    monkeypatch.setenv(key,value)
    with pytest.raises(r.OrderTimeStop):
        r.inspect_actual_original_seven_get(
            original_qty=QTY,key="test-key",secret="test-secret")
    assert calls==[]

@pytest.mark.parametrize("bad",["0","-1","1e-8","0.1234567891","NaN",""])
def test_invalid_qty_no_broker_network(monkeypatch,bad):
    calls,_=fixture(monkeypatch)
    with pytest.raises(r.OrderTimeStop):
        r.inspect_actual_original_seven_get(
            original_qty=bad,key="test-key",secret="test-secret")
    assert calls==[]

@pytest.mark.parametrize("mutation",[
    lambda v: v[1][0].update(qty="0.12"),
    lambda v: v[1][0].update(symbol="MSFT"),
    lambda v: v[1].append({"symbol":"BND","qty":"1"}),
    lambda v: v[2].append({"symbol":"ACWI","side":"buy"}),
    lambda v: v[3].update(is_open=False),
    lambda v: v[3].update(timestamp="2020-01-01T00:00:00Z"),
    lambda v: v[3].update(next_close="2020-01-01T00:00:00Z"),
])
def test_stale_market_broker_holdings_or_orders_block_before_risk_admission(monkeypatch,mutation):
    calls,flags=fixture(monkeypatch,mutation)
    with pytest.raises(r.OrderTimeStop):
        r.inspect_actual_original_seven_get(
            original_qty=QTY,key="test-key",secret="test-secret")
    assert len(calls)==7
    assert flags["evaluate_calls"]==0

@pytest.mark.parametrize("tamper",[
    {"actual_s1_6_20_35_risk_verified":False},
    {"live_orders":1},
    {"broker_get_requests":6},
    {"original_account_and_legacy_positions_verified":False},
    {"live_buy_sell_authorized":True},
    {"schema":"FORGED"},
])
def test_existing_real_risk_source_must_pass_unmodified(monkeypatch,tamper):
    calls,flags=fixture(monkeypatch)
    monkeypatch.setattr(r.seven,"evaluate",lambda **_:dict(REPORT,**tamper))
    with pytest.raises(r.OrderTimeStop,match="risk"):
        r.inspect_actual_original_seven_get(
            original_qty=QTY,key="test-key",secret="test-secret")
    assert len(calls)==7

def test_source_missing_broker_get_or_changed_operator_during_seven_get_blocks(monkeypatch):
    calls,_=fixture(monkeypatch)
    def fail(*,path,key,secret,params=None):
        calls.append(path)
        raise TimeoutError("mock broker GET lost")
    monkeypatch.setattr(r.live,"get_json",fail)
    with pytest.raises(r.OrderTimeStop):
        r.inspect_actual_original_seven_get(
            original_qty=QTY,key="test-key",secret="test-secret")
    assert len(calls)==1

def test_no_new_live_entrypoint_no_order_transport_and_legacy_stopped_contract():
    from pathlib import Path
    source=Path(r.__file__).read_text()
    assert "method=\"POST\"" not in source
    assert "urlopen(" not in source
    assert "def main(" not in source
    assert "if __name__" not in source
    assert "live.get_json(" in source
    assert "seven.evaluate(" in source
    assert "LIVE_WRITER_RELEASED=False" in source
    assert r.NO_EXECUTABLE_BROKER_POST is True
