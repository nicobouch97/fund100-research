"""Credentialless first-original ACWI ACTIVE HIGH SELL-only broker-source checks."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from hashlib import sha256
import pytest
import pandas as pd
import exchange_calendars as xcals

import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as active
import fund100_v6_s1_fresh_acwi_order_time_risk_getonly_v1_0 as stopped

ORIGINAL_CASHRISK_INSPECT=active.cashrisk.inspect

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
        "GITHUB_EVENT_NAME":"schedule",
        "GITHUB_WORKFLOW_REF":active.FIRST_ACWI_SCHEDULE_REF,
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
    # Derive exact XNYS sessions (no Sundays, fake weekdays or skipped
    # market closes) so the new 3M source has a genuine pre-funding prefix.
    market=xcals.get_calendar("XNYS")
    days=market.sessions_in_range(
        pd.Timestamp(now.date())-pd.Timedelta(days=40),
        pd.Timestamp(now.date())-pd.Timedelta(days=1))[-12:]
    assert len(days)==12
    stamps=[int(x.timestamp()) for x in days]
    nav=[None,0,0,0]+[100]*8
    month={"timeframe":"1D","timestamp":stamps[-6:],"equity":nav[-6:]}
    extended_history={"timeframe":"1D","timestamp":stamps,"equity":nav}
    first_funded=days[4].date()
    funding_date=(first_funded-timedelta(days=1)).isoformat()
    docs=[
        account,positions,[],
        {"is_open":True,"timestamp":now.isoformat(),
         "next_close":(now+timedelta(hours=2)).isoformat()},
        month,
        [{"id":"funding-only","activity_type":"CSD","net_amount":"100.00",
          "date":funding_date}],
        {"history":"masked-none"},
        extended_history,
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
        (active.five.HISTORY_PATH,active.extended.EXTENDED_PARAMS),
    )
    def get_json(*,path,params,key,secret):
        assert key==KEY and secret==SECRET
        n=state["reads"]
        assert n<8 and (path,params)==endpoints[n]
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
    assert got["same_process_real_broker_gets"]==8
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
    ("GITHUB_EVENT_NAME","push"),
    ("GITHUB_WORKFLOW_REF","untrusted/.github/workflows/other.yml@refs/heads/main"),("GITHUB_RUN_ATTEMPT","2"),
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



@pytest.mark.parametrize("field",["account_blocked","trading_blocked"])
@pytest.mark.parametrize("value",[None,"false",0,1,True])
def test_original_first_sell_requires_explicit_false_broker_unblocked_flags(
        monkeypatch,field,value):
    # A missing/null/mistyped account flag is not evidence that the
    # broker permits execution. These are all no-POST source-only tests.
    def mutate(docs):
        docs[0][field]=value
    state,_=mock_sources(monkeypatch,mutations=mutate)
    with pytest.raises(active.ActiveSellStop):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert state["reads"]==7


@pytest.mark.parametrize("field",["account_blocked","trading_blocked"])
def test_original_first_sell_missing_broker_block_flag_fails_closed(monkeypatch,field):
    def mutate(docs):
        docs[0].pop(field)
    state,_=mock_sources(monkeypatch,mutations=mutate)
    with pytest.raises(active.ActiveSellStop):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert state["reads"]==7


def test_full_existing_acwi_inventory_exit_can_exceed_new_order_65_without_expanding_exposure(monkeypatch):
    """Original bootstrap ACWI was > $65; an authenticated full exit is not a new buy."""
    def owned_inventory(docs):
        docs[0].update(cash="10.00",equity="120.00",last_equity="120.00")
        docs[1][0].update(current_price="80.00",market_value="80.00")
        # Existing other three $10 holdings remain as original; $10 cash and
        # $80 ACWI + $30 other gross = $120 original broker account equity.
    state,_=mock_sources(monkeypatch,mutations=owned_inventory)
    got=active.inspect_active_original_acwi_sell(
        original_qty=QTY,key=KEY,secret=SECRET)
    assert state["reads"]==7
    assert got["full_original_acwi_exit_bounded_by_authenticated_inventory"] is True
    assert got["maximum_new_order_notional_usd"]=="65.00"
    assert got["capital_ceiling_usd"]=="130.30"
    assert got["sell_only_original_legacy_ACWI"] is True
    assert got["buy_authorized"] is False
    assert got["orders_submitted_here"]==got["broker_post_attempts"]==0
    assert "80.00" not in str(got)
    assert active.ACTIVE_HIGH_SELL_SOURCE_RELEASED is True  # test fixture only


def test_original_one_month_source_without_earlier_prefunding_does_not_pass(monkeypatch):
    def mutate(doc):
        doc[7] = deepcopy(doc[4])
    state,_=mock_sources(monkeypatch,mutations=mutate)
    with pytest.raises(active.ActiveSellStop,match="disagreement"):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert state["reads"]==8


def test_changed_funded_mark_in_3m_cannot_reuse_original_1m(monkeypatch):
    def mutate(doc):
        doc[7]["equity"][-1]=float(98)
    state,_=mock_sources(monkeypatch,mutations=mutate)
    with pytest.raises(active.ActiveSellStop,match="disagreement"):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert state["reads"]==8


def test_funding_prefix_missing_inside_covered_history_fails_closed(monkeypatch):
    def mutate(doc):
        doc[7]["equity"][:4]=[100,100,100,100]
    state,_=mock_sources(monkeypatch,mutations=mutate)
    with pytest.raises(active.ActiveSellStop,match="disagreement"):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert state["reads"]==8


def test_funded_market_session_gap_can_not_hide_daily_loss(monkeypatch):
    def mutate(doc):
        # Remove one funded older daily close outside the 1M suffix.
        # The 1M suffix remains identical, so XNYS completeness matters.
        del doc[7]["timestamp"][5]
        del doc[7]["equity"][5]
    state,_=mock_sources(monkeypatch,mutations=mutate)
    with pytest.raises(active.ActiveSellStop,match="exchange-session"):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert state["reads"]==8


def test_mutated_cashflow_timing_missing_research_risk_stays_locked(monkeypatch):
    state,_=mock_sources(monkeypatch)
    monkeypatch.setattr(active.cashrisk,"inspect",lambda **kw:{
        "schema":active.cashrisk.STATUS_SCHEMA,
        "strictly_postfunding_account_6_20_35_source_verified":False,
        "source_rejection_category":"NONE",
    })
    with pytest.raises(active.ActiveSellStop,match="HIGH risk"):
        active.inspect_active_original_acwi_sell(
            original_qty=QTY,key=KEY,secret=SECRET)
    assert state["reads"]==8


def test_3m_funding_history_uses_existing_cashrisk_on_actual_dates(monkeypatch):
    state,docs=mock_sources(monkeypatch)
    # This test deliberately restores the original evaluator, which was
    # saved before the fixture installed a synthetic mock.
    monkeypatch.setattr(active.cashrisk,"inspect",ORIGINAL_CASHRISK_INSPECT)
    r=active.inspect_active_original_acwi_sell(
        original_qty=QTY,key=KEY,secret=SECRET)
    assert r["same_process_real_broker_gets"]==8
    assert r["original_strict_postfunding_6_20_35_risk_pass"] is True
    assert state["reads"]==8
    assert "private" not in str(r).lower()


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
