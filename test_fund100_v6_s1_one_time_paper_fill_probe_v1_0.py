"""S1 exact PAPER-only rehearsal tested with entirely fabricated Alpaca responses.

Unit tests never touch a broker. The live workflow separately runs once
on the intended 2026-10-19 US market session, if conditions permit.
"""
from __future__ import annotations

from datetime import datetime,timezone
from decimal import Decimal
import os
import pytest

import fund100_v6_s1_one_time_paper_fill_probe_v1_0 as s1


class MockClock(datetime):
    @classmethod
    def now(cls,tz=None):
        return datetime(2026,10,19,14,0,tzinfo=timezone.utc)


def arm(monkeypatch):
    monkeypatch.setattr(s1,"datetime",MockClock)
    values={
        "GITHUB_REPOSITORY":"nicobouch97/fund100-research",
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_RUN_ID":"39299920000",
        "GITHUB_RUN_ATTEMPT":"1",
        "FUND100_S1_PAPER_FILL_ARM":"S1_ONLY_2USD_ONCE",
        "FUND100_BROKER_KILL_SWITCH":"ENGAGED",
        "FUND100_RISK_LEVEL":"HIGH",
        "ALPACA_PAPER_KEY":"FAKE",
        "ALPACA_PAPER_SECRET":"FAKE2",
    }
    for k,v in values.items():monkeypatch.setenv(k,v)
    monkeypatch.delenv("ALPACA_LIVE_KEY",raising=False)
    monkeypatch.delenv("ALPACA_LIVE_SECRET",raising=False)
    monkeypatch.setattr(s1.operator,"read_current_control",
                        lambda:{"schema":"FUND100_OPERATOR_CONTROL_V1","trading_enabled":False})
    return values


def assets():
    return {k:{"symbol":k,"class":"us_equity","status":"active",
               "tradable":True,"fractionable":True} for k in s1.SYMBOLS}


def test_one_time_main_only_current_stop_and_day_guard(monkeypatch):
    arm(monkeypatch)
    s1.check_arm(MockClock.now())
    assert s1.regular_session({"is_open":True},MockClock.now())
    assert not s1.regular_session({"is_open":False},MockClock.now())
    assert not s1.regular_session({"is_open":True},
        datetime(2026,10,19,12,0,tzinfo=timezone.utc))
    assert not s1.regular_session({"is_open":True},
        datetime(2026,10,19,20,0,tzinfo=timezone.utc))


@pytest.mark.parametrize("key,value",[
    ("GITHUB_REF","refs/heads/feature"),
    ("GITHUB_REPOSITORY","another/repo"),
    ("FUND100_BROKER_KILL_SWITCH","DISENGAGED"),
    ("FUND100_RISK_LEVEL","LOW"),
    ("GITHUB_RUN_ATTEMPT","2"),
    ("ALPACA_PAPER_KEY",""),
    ("FUND100_S1_PAPER_FILL_ARM","YES"),
    ("ALPACA_LIVE_SECRET","DO_NOT_USE"),
])
def test_any_widened_order_boundary_refuses(monkeypatch,key,value):
    arm(monkeypatch)
    monkeypatch.setenv(key,value)
    with pytest.raises(s1.PaperS1Stop):
        s1.check_arm(MockClock.now())


def test_date_20_oct_or_sunday_rejected(monkeypatch):
    arm(monkeypatch)
    with pytest.raises(s1.PaperS1Stop):
        s1.check_arm(datetime(2026,10,20,14,0,tzinfo=timezone.utc))
    with pytest.raises(s1.PaperS1Stop):
        s1.check_arm(datetime(2026,10,18,14,0,tzinfo=timezone.utc))


def test_live_operator_remote_running_blocks_even_paper(monkeypatch):
    arm(monkeypatch)
    monkeypatch.setattr(s1.operator,"read_current_control",
        lambda:{"schema":"FUND100_OPERATOR_CONTROL_V1","trading_enabled":True})
    with pytest.raises(s1.PaperS1Stop):
        s1.check_arm(MockClock.now())


def test_selects_zero_baseline_etf_and_leaves_held_etfs_alone():
    assert s1.choose_zero_baseline({"XLK":Decimal("0.5")},assets())=="XLE"
    assert s1.choose_zero_baseline({"XLK":Decimal("0.5"),"XLE":Decimal("1")},assets())=="IWM"
    with pytest.raises(s1.PaperS1Stop):
        s1.choose_zero_baseline({s:Decimal("1") for s in s1.SYMBOLS},assets())


def test_duplicate_or_short_positions_are_not_accepted():
    with pytest.raises(s1.PaperS1Stop):
        s1.snapshots([{"symbol":"XLK","qty":"1"},{"symbol":"XLK","qty":"1"}])
    with pytest.raises(s1.PaperS1Stop):
        s1.snapshots([{"symbol":"XLK","qty":"-1"}])
    with pytest.raises(s1.PaperS1Stop):
        s1.snapshots([{"symbol":"XLK","qty":"NaN"}])


def test_client_ids_distinct_repeatable_and_github_run_bound(monkeypatch):
    arm(monkeypatch)
    b=s1.cid("b")
    x=s1.cid("s")
    assert b!=x and b.endswith("-b") and x.endswith("-s")
    assert s1.cid("b")==b
    monkeypatch.setenv("GITHUB_RUN_ID","39299920001")
    assert s1.cid("b")!=b


def test_only_2_dollar_buy_and_same_shares_sell_allowed(monkeypatch):
    arm(monkeypatch)
    monkeypatch.setattr(s1.paper,"get_order_by_client_id",lambda _cid:None)
    bodies=[]
    monkeypatch.setattr(s1.paper,"paper_request",
        lambda **kwargs:bodies.append(kwargs) or
        {"id":"SIMULATED-ID","client_order_id":kwargs["body"]["client_order_id"]})
    s1.submit("XLK","buy",notional=Decimal("2"))
    s1.submit("XLK","sell",qty=Decimal(".05"))
    assert len(bodies)==2
    assert all(x["method"]=="POST" and x["path"]=="/v2/orders" for x in bodies)
    assert bodies[0]["body"]["type"]==bodies[1]["body"]["type"]=="market"
    assert bodies[0]["body"]["time_in_force"]=="day"
    assert bodies[0]["body"]["notional"]=="2.00"
    assert "qty" not in bodies[0]["body"]
    assert bodies[1]["body"]["qty"]=="0.05"
    assert "notional" not in bodies[1]["body"]
    with pytest.raises(s1.PaperS1Stop):
        s1.submit("XLK","buy",notional=Decimal("1"))
    with pytest.raises(s1.PaperS1Stop):
        s1.submit("MCL","buy",notional=Decimal("2"))


def test_duplicate_order_client_id_prevents_any_post(monkeypatch):
    arm(monkeypatch)
    monkeypatch.setattr(s1.paper,"get_order_by_client_id",lambda _id:{"id":"ALREADY"})
    monkeypatch.setattr(s1.paper,"paper_request",
        lambda **k:pytest.fail("Should never POST duplicate client ID."))
    with pytest.raises(s1.PaperS1Stop,match="duplicate"):
        s1.submit("XLK","buy",notional=Decimal("2"))


def test_actual_control_flow_2_paper_orders_restore_original_positions(monkeypatch):
    arm(monkeypatch)
    old={"ACWI":Decimal("1.7"),"EEM":Decimal(".3"),"XLK":Decimal(".1")}
    held=old.copy()
    orders={}
    posts=[]
    def mock_post(*,method,path,body):
        assert method=="POST" and path=="/v2/orders"
        tag=body["client_order_id"]
        assert tag not in orders
        symbol=body["symbol"]
        if body["side"]=="buy":
            assert symbol=="XLE" # XLK already held, choose clean XLE
            assert body.get("notional")=="2.00"
            held[symbol]=held.get(symbol,Decimal(0))+Decimal(".05")
            qty=".05"
        else:
            assert symbol=="XLE" and body.get("qty")=="0.05"
            held.pop(symbol)
            qty=".05"
        order={"id":"MOCK-"+tag,"client_order_id":tag,
               "status":"filled","filled_qty":qty}
        orders[tag]=order
        posts.append(order)
        return order
    monkeypatch.setattr(s1.paper,"get_clock",lambda:{"is_open":True})
    monkeypatch.setattr(s1.paper,"get_account",lambda:{
        "status":"ACTIVE","trading_blocked":False,"cash":"100000"})
    monkeypatch.setattr(s1.paper,"get_open_orders",lambda:[])
    monkeypatch.setattr(s1.paper,"get_positions",lambda:[
        {"symbol":s,"qty":str(q)} for s,q in held.items()])
    monkeypatch.setattr(s1.paper,"get_asset",lambda sym:assets()[sym])
    monkeypatch.setattr(s1.paper,"get_order_by_client_id",
        lambda tag:orders.get(tag))
    monkeypatch.setattr(s1.paper,"get_order_by_id",
        lambda oid:next((o for o in orders.values() if o["id"]==oid),None))
    monkeypatch.setattr(s1.paper,"cancel_order",
        lambda _id:pytest.fail("Fully filled orders cannot be canceled."))
    monkeypatch.setattr(s1.paper,"paper_request",mock_post)
    result=s1.paper_probe()
    assert result["status"]=="PASS"
    assert result["symbol"]=="XLE"
    assert result["mode"]=="REAL_ALPACA_PAPER_ONLY"
    assert result["paper_buy_filled"] and result["paper_sell_filled"]
    assert result["all_starting_paper_positions_preserved"]
    assert result["paper_orders_submitted"]==2 and result["live_orders_submitted"]==0
    assert not result["new_investment_alpha_established"]
    assert not result["new_strategy_live_authorized"]
    assert len(posts)==2 and held==old


def test_open_orders_prevent_trade(monkeypatch):
    arm(monkeypatch)
    monkeypatch.setattr(s1.paper,"get_clock",lambda:{"is_open":True})
    monkeypatch.setattr(s1.paper,"get_account",lambda:{
        "status":"ACTIVE","trading_blocked":False,"cash":"100"})
    monkeypatch.setattr(s1.paper,"get_open_orders",lambda:[{"id":"SOMEONE-ELSE"}])
    with pytest.raises(s1.PaperS1Stop,match="open orders"):
        s1.paper_probe()


def test_bad_partial_or_zero_fill_never_marked_pass():
    for invalid in [
        {"status":"partially_filled","filled_qty":"0.5"},
        {"status":"filled","filled_qty":"0"},
        {"status":"filled","filled_qty":"NaN"},
    ]:
        with pytest.raises(s1.PaperS1Stop):
            s1.require_filled(invalid,"buy")
