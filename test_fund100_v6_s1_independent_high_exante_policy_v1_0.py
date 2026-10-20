"""Independent V6 HIGH synthetic price/risk contract, no broker/secret dependencies."""
from copy import deepcopy
from datetime import date,timedelta
from decimal import Decimal
from pathlib import Path
import pytest
import fund100_v6_s1_independent_high_exante_policy_v1_0 as p
import fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0 as original

TODAY=date(2026,10,20)
TODAY_STRING=TODAY.isoformat()

def market_days(n=61):
    dates=[];day=TODAY
    while len(dates)<n:
        if day.weekday()<5:dates.append(day)
        day-=timedelta(days=1)
    return [x.isoformat() for x in reversed(dates)]

def fixtures(shock=Decimal(".002"),n=61):
    dates=market_days(n)
    prices={}
    for s in p.TARGET:
        level=Decimal("100")
        rows=[]
        for i,d in enumerate(dates):
            level=level*(Decimal(1)+shock*(1 if i%2==0 else -1))
            rows.append({"date":d,"adjusted_close":str(level)})
        prices[s]=rows
    return {"mode":p.MODE,"source_authenticated_live":False,"prices":prices}

def buy():
    return {
      "mode":p.MODE,"source_authenticated_live":False,"risk_level":"HIGH",
      "operator_stopped":True,"kill_switch":"ENGAGED",
      "equity":"130.30","cash":"110.30","settled_cash":"110.30",
      "positions":{"XLE":"20.00"},"synthetic_independently_settled":True,
      "buy_symbol":"XLK","buy_notional":"61.89","estimated_cost":".10",
    }

def warmup():
    return {
      "mode":p.MODE,"source_authenticated_live":False,
      "operator_stopped":True,"kill_switch":"ENGAGED",
      "post_migration_clean_baseline_proven_synthetically":True,
      "external_flows_reconciled_synthetically":True,
      "completed_strategy_daily_closes":2,
      "daily_return":"-0.01","peak_to_trough_drawdown":"-0.05",
      "aligned_etf_exante_vol":"0.22","actual_annual_volatility":None,
    }

def assert_nonexec(result):
    assert result["live_order_authorized"] is False
    assert result["broker_order_posts"]==0
    assert result["broker_requests"]==0
    assert result["order"] is None

def test_separate_v6_contract_explicitly_corrects_original_manifest_xle_overlap():
    old=original.source_controls()
    assert old["legacy_holdings_must_be_reconciled_and_exited_before_any_buy"]==[
        "ACWI","EEM","XLE","XLV"]
    new=p.contract()
    assert new["corrected_v6_only_staged_exits"]==("ACWI","EEM","XLV")
    assert new["original_xle_not_a_mandatory_exit"]
    assert new["original_source_remains_unchanged"]
    assert new["target_weights"]=={"XLK":"0.475","XLE":"0.285","IWM":"0.190"}
    assert new["live_broker_authenticated"] is False
    assert new["order_submission_authorized"] is False

def test_v6_concentrated_cap_not_misrepresented_as_old_v5_25pct_cap():
    from fund100_live_portfolio_risk_v1_0 import get_profile
    assert get_profile("HIGH").max_satellite_weight==Decimal(".25")
    assert p.TARGET["XLK"]>Decimal(".25")
    assert p.TARGET["XLE"]>Decimal(".25")
    assert sum(p.TARGET.values())==Decimal(".95")
    assert p.MAX_SYMBOL==Decimal(".50")

def test_aligned_low_volatility_synthetic_returns_a_planning_estimate_only():
    r=p.project_vol(fixtures=fixtures(),now_date=TODAY_STRING)
    assert r["price_observations"]==61
    assert r["aligned_daily_returns"]==60
    assert r["exante_30pct_planning_threshold_passed"] is True
    assert r["actual_v6_35pct_volatility_limit_verified"] is False
    assert r["authentic_live_account_risk_verified"] is False
    assert not r["live_buy_sell_authorized"]
    assert r["broker_order_posts"]==r["broker_get_requests"]==0

def test_high_projected_volatility_must_fail_stricter_30pct_planning_gate():
    r=p.project_vol(fixtures=fixtures(Decimal(".025")),now_date=TODAY_STRING)
    assert Decimal(r["illustrative_annualized_volatility"])>Decimal(".30")
    assert not r["exante_30pct_planning_threshold_passed"]
    assert not r["actual_v6_35pct_volatility_limit_verified"]

@pytest.mark.parametrize("problem",[
    "missing_xlk","extra_symbol","missing_data","misaligned","repeated_date",
    "future_date","stale_date","zero_close","bad_close","boolean_close",
    "large_adjustment","wrong_source","real_flag","missing_schema",
])
def test_price_source_failclosed_no_fake_etf_vol_pass(problem):
    x=fixtures()
    if problem=="missing_xlk":del x["prices"]["XLK"]
    elif problem=="extra_symbol":x["prices"]["SPY"]=deepcopy(x["prices"]["XLK"])
    elif problem=="missing_data":x["prices"]["IWM"]=x["prices"]["IWM"][:-1]
    elif problem=="misaligned":x["prices"]["XLK"][6]["date"]=market_days()[7]
    elif problem=="repeated_date":x["prices"]["XLE"][10]["date"]=x["prices"]["XLE"][9]["date"]
    elif problem=="future_date":
        for s in p.TARGET:
            x["prices"][s][-1]["date"]="2026-10-22"
    elif problem=="stale_date":
        for s in p.TARGET:
            for row in x["prices"][s]:
                row["date"]=(date.fromisoformat(row["date"])-timedelta(days=30)).isoformat()
    elif problem=="zero_close":x["prices"]["XLK"][4]["adjusted_close"]="0"
    elif problem=="bad_close":x["prices"]["XLK"][4]["adjusted_close"]="NaN"
    elif problem=="boolean_close":x["prices"]["XLK"][4]["adjusted_close"]=True
    elif problem=="large_adjustment":x["prices"]["XLK"][18]["adjusted_close"]="10000000"
    elif problem=="wrong_source":x["mode"]="LIVE"
    elif problem=="real_flag":x["source_authenticated_live"]=True
    elif problem=="missing_schema":del x["source_authenticated_live"]
    with pytest.raises(p.S1HighStop):
        p.project_vol(fixtures=x,now_date=TODAY_STRING)

def test_61_close_minimum_will_not_accept_a_one_week_paper_sample():
    with pytest.raises(p.S1HighStop):
        p.project_vol(fixtures=fixtures(n=8),now_date=TODAY_STRING)

def test_original_xle_holdings_and_buy_envelope_hypothetical_only():
    r=p.hypothetical_buy_envelope(snapshot=buy())
    assert r["stage"]=="HYPOTHETICAL_V6_ENVELOPE_PASSED_NO_TRADE_AUTHORIZATION"
    assert_nonexec(r)

@pytest.mark.parametrize("field,value,stage",[
    ("positions",{"ACWI":"15.00","XLE":"5.00"},"BLOCKED_LEGACY_ACWI_EEM_XLV_NOT_FLAT"),
    ("synthetic_independently_settled",False,"BLOCKED_SETTLED_CASH_SOURCE_UNAVAILABLE"),
    ("settled_cash","0.50","BLOCKED_FIVE_PERCENT_CASH_FLOOR"),
    ("buy_notional","0.99","BLOCKED_ORDER_SIZE_OR_CASH"),
    ("buy_notional","65.01","BLOCKED_ORDER_SIZE_OR_CASH"),
    ("buy_notional","65.00","HYPOTHETICAL_V6_ENVELOPE_PASSED_NO_TRADE_AUTHORIZATION"),
    ("cash","10","BLOCKED_ORDER_SIZE_OR_CASH"),
    ("estimated_cost","45","BLOCKED_FIVE_PERCENT_CASH_FLOOR"),
    ("positions",{"XLE":"39.00"},"BLOCKED_ACCOUNT_GROSS_CASH_MISMATCH"),
])
def test_projected_cash_and_no_churn_controls(field,value,stage):
    x=buy();x[field]=value
    r=p.hypothetical_buy_envelope(snapshot=x)
    assert r["stage"]==stage
    assert_nonexec(r)

def test_original_xle_overweight_stops_and_never_emits_sell():
    x=buy();x["positions"]={"XLE":"39.00"};x["cash"]="91.30";x["settled_cash"]="91.30"
    r=p.hypothetical_buy_envelope(snapshot=x)
    assert r["stage"]=="BLOCKED_ORIGINAL_XLE_OVERWEIGHT_REVIEW_NOT_SELL"
    assert_nonexec(r)

def test_buy_cannot_spend_below_cash_floor_or_exceed_symbol_cap():
    x=buy();x["buy_notional"]="62.30";x["estimated_cost"]="0.20"
    r=p.hypothetical_buy_envelope(snapshot=x)
    assert r["stage"]=="HYPOTHETICAL_V6_ENVELOPE_PASSED_NO_TRADE_AUTHORIZATION"
    assert_nonexec(r)
    x=buy()
    x["positions"]={"XLK":"50.00","XLE":"20.00"}
    x["cash"]="60.30";x["settled_cash"]="60.30"
    x["buy_notional"]="18.00"
    r=p.hypothetical_buy_envelope(snapshot=x)
    assert r["stage"]=="BLOCKED_FIFTY_PERCENT_SINGLE_SYMBOL"
    assert_nonexec(r)

@pytest.mark.parametrize("changed",[
    {"operator_stopped":False},{"kill_switch":"DISENGAGED"},
    {"mode":"LIVE"},{"source_authenticated_live":True},
    {"risk_level":"LOW"},{"buy_symbol":"ACWI"},
])
def test_no_real_order_released_by_envelope_inputs(changed):
    x=buy();x.update(changed)
    with pytest.raises(p.S1HighStop):
        p.hypothetical_buy_envelope(snapshot=x)

def test_early_warmup_reports_only_exante_proxy_not_verified_35pct_actual():
    r=p.hypothetical_warmup_risk(snapshot=warmup())
    assert r["stage"]=="HYPOTHETICAL_WARMUP_EXANTE_PROXY_ONLY_NOT_ACTUAL_35PCT_PROOF"
    assert r["actual_35pct_volatility_verified"] is False
    assert_nonexec(r)

@pytest.mark.parametrize("change,stage",[
    ({"completed_strategy_daily_closes":0},"BLOCKED_NO_REAL_DAILY_ACCOUNT_RISK_OBSERVATION"),
    ({"daily_return":"-0.06"},"BLOCKED_SIX_PERCENT_DAILY_OR_TWENTY_PERCENT_DRAWDOWN"),
    ({"peak_to_trough_drawdown":"-0.20"},"BLOCKED_SIX_PERCENT_DAILY_OR_TWENTY_PERCENT_DRAWDOWN"),
    ({"aligned_etf_exante_vol":"0.31"},"BLOCKED_EXANTE_VOLATILITY_NOT_BELOW_30PCT"),
    ({"external_flows_reconciled_synthetically":False},"BLOCKED_MISSING_CLEAN_V6_ACCOUNT_RISK_BASELINE"),
    ({"post_migration_clean_baseline_proven_synthetically":False},"BLOCKED_MISSING_CLEAN_V6_ACCOUNT_RISK_BASELINE"),
    ({"completed_strategy_daily_closes":6,"actual_annual_volatility":"0.36"},"BLOCKED_THIRTY_FIVE_PERCENT_REALIZED_VOLATILITY"),
    ({"completed_strategy_daily_closes":6,"actual_annual_volatility":"0.34"},"HYPOTHETICAL_SIX_TWENTY_THIRTYFIVE_RISK_ENVELOPE_NO_LIVE_AUTH"),
])
def test_warmup_daily_drawdown_realized_risk_constraints(change,stage):
    x=warmup();x.update(change)
    r=p.hypothetical_warmup_risk(snapshot=x)
    assert r["stage"]==stage
    assert_nonexec(r)

def test_no_early_false_realized_volatility_or_missing_actual_post_warmup():
    x=warmup();x["actual_annual_volatility"]="0.10"
    with pytest.raises(p.S1HighStop):
        p.hypothetical_warmup_risk(snapshot=x)
    x=warmup();x["completed_strategy_daily_closes"]=6
    with pytest.raises(p.S1HighStop):
        p.hypothetical_warmup_risk(snapshot=x)

def test_no_broker_host_keys_state_repo_or_http_write_path_added():
    source=Path(p.__file__).read_text()
    assert p.RELEASE_LIVE_ORDER_EXECUTION is False
    for forbidden in ("urlopen(","method=\"POST\"","method=\"PUT\"",
                      "api.alpaca.markets","ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                      "FUND100_PRIVATE_STATE_READ_TOKEN","FUND100_PRIVATE_STATE_WRITE_TOKEN",
                      "submit_"+"authorized_order_batch("):
        assert forbidden not in source
