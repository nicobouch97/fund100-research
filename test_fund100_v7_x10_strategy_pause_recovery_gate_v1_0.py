"""Synthetic X10 scenarios reject emergency-stop relaunches and fake sources."""
from copy import deepcopy
import pytest

import fund100_v7_x5_capacity_aware_portfolio_router_v1_0 as x5
import fund100_v7_x6_costed_multiasset_opportunity_selector_v1_0 as x6
import fund100_v7_x10_strategy_pause_recovery_gate_v1_0 as x10

NOW="2026-10-26T21:00:00Z"

CANDIDATES={
    "RESEARCH_GROWTH":{"XLK":"0.45","XLE":"0.30"},
    "RESEARCH_VALUE":{"XLK":"0.25","XLE":"0.45"},
}

def fixture():
    return {
        "mode":x10.MODE,
        "pause_kind":"STRATEGY_SOFT_PAUSE",
        "pause_recorded_utc":"2026-10-12T21:00:00Z",
        "operator_stop":False,
        "environment_kill_engaged":False,
        "fully_flat":True,"open_order_count":0,
        "equity_usd":"1000.00","cash_usd":"1000.00",
        "settled_cash_usd":"1000.00",
        "last_daily_return":"0.001",
        "account_drawdown":"-0.05",
        "account_annual_volatility":"0.25",
        "risk_measurement_utc":"2026-10-26T20:00:00Z",
    }

def captures():
    return [
        {"source_mode":x10.MODE,
         "price_session":"2026-10-20","captured_utc":"2026-10-21T09:00:00Z",
         "risk_vol_63_fraction":"0.27","daily_benchmark_return_fraction":"0.001"},
        {"source_mode":x10.MODE,
         "price_session":"2026-10-22","captured_utc":"2026-10-23T09:00:00Z",
         "risk_vol_63_fraction":"0.28","daily_benchmark_return_fraction":"0.002"},
    ]

def call(s=None,c=None,forecasts=None,cap="1000.00",spec=None):
    return x10.assess(
        snapshot=fixture() if s is None else s,
        captures=captures() if c is None else c,
        candidate_target_weights=CANDIDATES,
        expected_returns_fraction=forecasts or {"XLK":"0.10","XLE":"0.05"},
        asset_spec=x5.sample_spec() if spec is None else spec,
        hypothetical_capital_limit_usd=cap,
        forecast_horizon_sessions=21,
        now_utc=NOW)

def test_soft_pause_can_only_be_marked_research_eligible_not_live():
    r=call()
    assert r["synthetic_soft_pause_recovery_candidate"]
    assert r["reason"]=="RESEARCH_ONLY_SOFT_PAUSE_CONDITIONS_MET_NOT_A_LIVE_SIGNAL"
    assert r["hypothetical_context"]["selected_synthetic_hypothesis"]=="RESEARCH_GROWTH"
    assert r["hard_account_stop_cleared"] is False
    assert r["standing_live_reentry_mandate_authenticated"] is False
    assert not r["live_trading_authorized"]
    assert r["real_broker_gets"]==r["real_broker_posts"]==r["real_broker_orders"]==0

def test_account_emergency_stop_cannot_be_auto_reset_even_if_recovery_bright():
    s=fixture()
    s["pause_kind"]="ACCOUNT_HARD_STOP"
    r=call(s=s)
    assert r["reason"]=="BLOCKED_ACCOUNT_HARD_STOP_REQUIRES_INDEPENDENT_RELEASE"
    assert not r["synthetic_soft_pause_recovery_candidate"]
    assert not r["hard_account_stop_cleared"]

def test_original_operator_stop_and_kill_remain_absolute_blockers():
    for k in ("operator_stop","environment_kill_engaged"):
        s=fixture()
        s[k]=True
        r=call(s=s)
        assert r["reason"]=="BLOCKED_OPERATOR_STOP_OR_BROKER_KILL"
        assert not r["live_trading_authorized"]

def test_no_self_reentry_when_cash_unsettled_or_open_orders_or_not_flat():
    for key,value,expected in (
        ("settled_cash_usd","999.00","HOLD_SETTLED_CASH_SOURCE_AND_RECONCILIATION_REQUIRED"),
        ("open_order_count",1,"HOLD_ACCOUNT_NOT_FLAT_OR_ORDERS_UNRECONCILED"),
        ("fully_flat",False,"HOLD_ACCOUNT_NOT_FLAT_OR_ORDERS_UNRECONCILED")):
        s=fixture()
        s[key]=value
        assert call(s=s)["reason"]==expected

def test_risk_break_not_overridden_by_attractive_signal():
    for key,value in (("last_daily_return","-0.06"),
                      ("account_drawdown","-0.20"),
                      ("account_annual_volatility","0.36")):
        s=fixture()
        s[key]=value
        assert call(s=s)["reason"]=="HOLD_POST_PAUSE_ACCOUNT_RISK_OUTSIDE_HIGH_LIMITS"

def test_costed_candidate_must_be_at_least_hypothetically_eligible():
    r=call(forecasts={"XLK":"0.0001","XLE":"0.0001"})
    assert r["reason"]=="HOLD_NO_COSTED_OPPORTUNITY_TO_REENTER"
    assert not r["synthetic_soft_pause_recovery_candidate"]
    spec=x5.sample_spec()
    for item in spec.values():
        item["minimum_notional_usd"]="1000"
        item["maximum_ticket_usd"]="1000"
    # A model that cannot split or afford the required tickets is a HOLD.
    assert call(spec=spec)["reason"]=="HOLD_NO_COSTED_OPPORTUNITY_TO_REENTER"

def test_chronology_revision_or_late_market_vintage_never_passes():
    for field,value in (
        ("price_session","2026-10-19"),
        ("captured_utc","2026-10-21T09:00:00Z"),
        ("price_session","2026-10-24"),
        ("captured_utc","2026-10-22T01:00:00Z")):
        c=captures()
        c[1][field]=value
        with pytest.raises(x10.RecoveryStop):
            call(c=c)
    for field,value in (
        ("risk_vol_63_fraction","0.40"),
        ("daily_benchmark_return_fraction","-0.07")):
        c=captures()
        c[1][field]=value
        assert call(c=c)["reason"]=="HOLD_POST_PAUSE_MARKET_STRESS_NOT_CLEARED"
    for c in (
        captures()[:1],
        [captures()[0],captures()[0]],
        [{**captures()[0],"captured_utc":"2026-10-19T08:00:00Z"},captures()[1]],
        [{**captures()[0],"source_mode":"AUTHENTICATED_LIVE"},captures()[1]]):
        with pytest.raises(x10.RecoveryStop):
            call(c=c)

def test_invalid_synthetic_opportunity_or_unbound_nav_cannot_pass():
    with pytest.raises(x10.RecoveryStop):
        call(cap="130.30")
    with pytest.raises(x10.RecoveryStop):
        call(forecasts={"XLK":"NaN","XLE":"0.1"})
    s=fixture()
    s["risk_measurement_utc"]="2026-10-24T20:00:00Z"
    with pytest.raises(x10.RecoveryStop):
        call(s=s)

def test_premature_soft_pause_cooldown_holds():
    s=fixture()
    s["pause_recorded_utc"]="2026-10-21T22:00:00Z"
    c=[
        {"source_mode":x10.MODE,"price_session":"2026-10-22",
         "captured_utc":"2026-10-23T09:00:00Z",
         "risk_vol_63_fraction":"0.27","daily_benchmark_return_fraction":"0.001"},
        {"source_mode":x10.MODE,"price_session":"2026-10-23",
         "captured_utc":"2026-10-24T09:00:00Z",
         "risk_vol_63_fraction":"0.28","daily_benchmark_return_fraction":"0.002"},
    ]
    assert call(s=s,c=c)["reason"]=="HOLD_RESEARCH_PAUSE_COOLDOWN_NOT_MET"
