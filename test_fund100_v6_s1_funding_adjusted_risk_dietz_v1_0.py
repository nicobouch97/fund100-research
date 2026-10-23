"""Original LIVE account raw funding correction: synthetic financial fixtures ONLY."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
import pytest
import fund100_v6_s1_funding_adjusted_risk_dietz_v1_0 as f

NOW="2026-10-19T18:00:00Z"
BASE=datetime(2026,10,12,20,0,tzinfo=timezone.utc)

def event(*,kind="CSD",dollars="100.00",second=0,id_="FAKE-CSD-1"):
    time=BASE+timedelta(days=1,hours=-1,seconds=second)
    return {"id":id_,"activity_type":kind,"net_amount":dollars,
            "transaction_time":time.isoformat().replace("+00:00","Z"),
            "date":"2026-10-15"}

def fixture():
    timestamps=[int((BASE+timedelta(days=i)).timestamp()) for i in range(6)]
    return {"schema":f.SCHEMA,"mode":f.MODE,
      "authenticated_broker_source":False,"live_operator_stopped":True,
      "broker_kill_switch":"ENGAGED","risk_level":"HIGH",
      "portfolio_history":{"timeframe":"1D","timestamp":timestamps,
                           "equity":["100","200","200","200","200","200"]},
      "nontrade_activity_query_after":"2026-09-01T00:00:00Z",
      "nontrade_activities":[event()]
    }

def check(d):
    return f.analyze(fixture=d,now_utc=NOW)

def test_original_deposit_false_raw_plus100pct_is_adjusted_to_zero_proxy():
    z=check(fixture())
    assert z["research_status"]=="OFFLINE_MODIFIED_DIETZ_FLOW_ADJUSTED_ESTIMATE_ONLY"
    assert z["raw_and_flow_adjusted_intervals_differ"] is True
    assert not z["dietz_risk_limit_breached_in_synthetic_history"]
    assert z["eligible_external_cash_transfers_in_fixture"]
    assert z["dietz_is_exact_true_time_weighted_return"] is False
    assert not z["real_broker_account_flow_data_qualified"]
    assert not z["real_s1_high_account_risk_approved"]
    assert not z["live_buy_authorized"] and not z["live_sell_authorized"]
    assert z["broker_orders"]==z["broker_requests"]==0
    assert z["private_adjusted_returns"] is None
    assert z["executable_order_payload"] is None
    for secret in ("FAKE-CSD-1","100.00","2026-10-15"):
        assert secret not in str(z)

def test_withdrawal_is_not_minus_50pct_market_crash():
    d=fixture()
    d["nontrade_activities"]=[event(kind="CSW",dollars="-50.00",id_="WD1")]
    d["portfolio_history"]["equity"]=["100","50","50","50","50","50"]
    z=check(d)
    assert z["raw_and_flow_adjusted_intervals_differ"]
    assert not z["dietz_daily_loss_limit_breached_in_fixture"]
    assert not z["dietz_risk_limit_breached_in_synthetic_history"]

def test_funding_with_actual_10pct_investment_growth_stays_economic():
    d=fixture()
    d["portfolio_history"]["equity"]=["100","210","210","210","210","210"]
    z=check(d)
    assert z["raw_and_flow_adjusted_intervals_differ"]
    assert z["dietz_realized_vol_limit_breached_in_fixture"]
    assert not z["real_s1_high_account_risk_approved"]

def test_end_timestamp_transfer_weight_zero_still_cashflow_corrected():
    d=fixture()
    d["nontrade_activities"]=[event(second=3600)]
    z=check(d)
    assert z["raw_and_flow_adjusted_intervals_differ"]
    assert not z["dietz_risk_limit_breached_in_synthetic_history"]

def test_dividends_or_fees_are_not_mistaken_for_cash_contributions():
    d=fixture()
    d["portfolio_history"]["equity"]=["100","100","100","100","100","90"]
    d["nontrade_activities"]=[
        {"id":"D1","activity_type":"DIV","net_amount":"10"},
        {"id":"F1","activity_type":"FEE","net_amount":"-5"}]
    z=check(d)
    assert z["dietz_daily_loss_limit_breached_in_fixture"]
    assert not z["raw_and_flow_adjusted_intervals_differ"]
    assert not z["eligible_external_cash_transfers_in_fixture"]

def test_daily_loss_and_unitized_drawdown_really_trigger():
    d=fixture()
    d["nontrade_activities"]=[]
    d["portfolio_history"]["equity"]=["100","100","100","100","100","80"]
    z=check(d)
    assert z["dietz_daily_loss_limit_breached_in_fixture"]
    assert z["dietz_drawdown_limit_breached_in_fixture"]
    assert z["dietz_risk_limit_breached_in_synthetic_history"]

@pytest.mark.parametrize("typ",["ACATC","ACATS","JNL","JNLC","JNLS","TRANS"])
def test_asset_transfers_not_mislabeled_signed_usd_cash(typ):
    d=fixture();d["nontrade_activities"]=[event(kind=typ)]
    with pytest.raises(f.FundingRiskStop,match="Noncash"):check(d)

@pytest.mark.parametrize("typ,dollars",[
    ("CSD","-10"),("CSW","10"),("CSW","0"),("CSD","NaN"),
    ("CSD","Infinity"),("CSD",10.0)
])
def test_cash_direction_and_numeric_provenance_must_be_unambiguous(typ,dollars):
    d=fixture();d["nontrade_activities"]=[event(kind=typ,dollars=dollars)]
    with pytest.raises(f.FundingRiskStop):check(d)

def test_transaction_time_not_reconstructed_from_settlement_date():
    d=fixture()
    del d["nontrade_activities"][0]["transaction_time"]
    with pytest.raises(f.FundingRiskStop,match="transaction timestamp"):check(d)

def test_naive_timestamp_rejected_even_with_date():
    d=fixture()
    d["nontrade_activities"][0]["transaction_time"]="2026-10-13T19:00:00"
    with pytest.raises(f.FundingRiskStop,match="Naive"):check(d)

def test_flow_outside_latest_equity_is_not_silent():
    d=fixture()
    d["nontrade_activities"][0]["transaction_time"]="2026-10-19T00:00:00Z"
    with pytest.raises(f.FundingRiskStop,match="after most recent"):check(d)

@pytest.mark.parametrize("bad",[
    [{"id":"A","activity_type":"CSD","net_amount":"100",
      "transaction_time":"2026-10-13T19:00:00Z"},
     {"id":"A","activity_type":"CSW","net_amount":"-10",
      "transaction_time":"2026-10-14T19:00:00Z"}],
    [{"id":"A","activity_type":"UNRECOGNIZED"}],
    [{"activity_type":"CSD","net_amount":"100","transaction_time":"2026-10-13T19:00:00Z"}],
    [{"id":"B","activity_type":"csd","net_amount":"100","transaction_time":"2026-10-13T19:00:00Z"}],
])
def test_duplicate_unknown_and_unverifiable_activities_fail(bad):
    d=fixture();d["nontrade_activities"]=bad
    with pytest.raises(f.FundingRiskStop):check(d)

def test_full_100_records_means_next_page_required():
    d=fixture()
    d["nontrade_activities"]=[{"id":str(i),"activity_type":"DIV"} for i in range(100)]
    with pytest.raises(f.FundingRiskStop,match="unpaged"):check(d)

def test_missing_time_coverage_must_fail():
    d=fixture()
    d["nontrade_activity_query_after"]="2026-10-14T00:00:00Z"
    with pytest.raises(f.FundingRiskStop,match="cover full returns"):check(d)

@pytest.mark.parametrize("change",[
    {"mode":"REAL_ALPACA_LIVE_ACCOUNT"},
    {"authenticated_broker_source":True},
    {"risk_level":"MEDIUM"},
    {"broker_kill_switch":"DISENGAGED"},
    {"live_operator_stopped":False},
])
def test_even_valid_actual_looking_inputs_not_promoted_to_live(change):
    d=fixture();d.update(change)
    with pytest.raises(f.FundingRiskStop):check(d)

def test_history_gap_duplicate_timestamp_and_negative_equity_rejected():
    d=fixture();d["portfolio_history"]["timestamp"][2]=d["portfolio_history"]["timestamp"][1]
    with pytest.raises(f.FundingRiskStop):check(d)
    d=fixture();d["portfolio_history"]["equity"][1]="-4"
    with pytest.raises(f.FundingRiskStop):check(d)
    d=fixture();d["portfolio_history"]["equity"][1]="NaN"
    with pytest.raises(f.FundingRiskStop):check(d)

def test_observation_clock_and_points_are_bounded():
    d=fixture()
    with pytest.raises(f.FundingRiskStop):
        f.analyze(fixture=d,now_utc="2026-11-20T19:00:00Z")
    d["portfolio_history"]["timestamp"].pop()
    with pytest.raises(f.FundingRiskStop):check(d)

def test_all_external_contributions_must_have_an_investable_denominator():
    d=fixture()
    d["nontrade_activities"]=[event(kind="CSW",dollars="-300")]
    # Almost the entire interval remains after the withdrawal, so its
    # Modified Dietz capital weight exceeds the $100 opening balance.
    d["nontrade_activities"][0]["transaction_time"]=(BASE+timedelta(seconds=1)).isoformat().replace("+00:00","Z")
    with pytest.raises(f.FundingRiskStop,match="Nonpositive invested"):check(d)

def test_account_risk_estimator_has_no_broker_or_environment_access():
    s=Path(f.__file__).read_text()
    for banned in ("urlopen(", "requests.post(", "method=\"POST\"",
                   "ALPACA_LIVE_KEY","submit_"+"authorized_order_batch(",
                   "os.environ","getenv(", "/v2/orders"):
        assert banned not in s


def undated_fixture():
    d=fixture()
    d["nontrade_activities"][0].pop("transaction_time")
    return d

def test_date_only_original_deposit_no_fabricated_timestamp_or_release():
    d=undated_fixture()
    r=f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)
    assert r["status"]=="UNIQUE_CONDITIONALLY_PLAUSIBLE_PLACEMENT_RESEARCH_ONLY"
    assert r["quality_admissible_intervals"]==1
    assert r["conditional_all_scenarios_below_original_HIGH_limits"] is True
    assert not r["exact_economic_funding_date_proven"]
    assert not r["funding_effective_date_inferred_as_fact"]
    assert not r["original_source_broker_authenticated"]
    assert not r["real_s1_high_account_risk_approved"]
    assert not r["live_buy_authorized"] and not r["live_sell_authorized"]
    assert r["broker_orders"]==r["broker_requests"]==0
    for private in ("FAKE-CSD-1","100.00","2026-10-15"):
        assert private not in str(r)

def test_date_only_cashflow_followed_by_real_loss_still_halts():
    d=undated_fixture()
    d["portfolio_history"]["equity"]=["100","200","200","200","200","188"]
    r=f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)
    assert r["quality_admissible_intervals"]==1
    assert r["conditional_all_scenarios_below_original_HIGH_limits"] is False
    assert r["real_s1_high_account_risk_approved"] is False

def test_date_only_deposit_plus_big_drawdown_does_not_hide_account_loss():
    d=undated_fixture()
    d["portfolio_history"]["equity"]=["100","200","200","200","200","160"]
    r=f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)
    assert r["quality_admissible_intervals"]==1
    assert not r["conditional_all_scenarios_below_original_HIGH_limits"]

def test_date_only_withdrawal_not_a_fake_negative_market_return():
    d=undated_fixture()
    d["nontrade_activities"][0]["activity_type"]="CSW"
    d["nontrade_activities"][0]["net_amount"]="-50.00"
    d["portfolio_history"]["equity"]=["100","50","50","50","50","50"]
    r=f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)
    assert r["quality_admissible_intervals"]==1
    assert r["conditional_all_scenarios_below_original_HIGH_limits"]
    assert not r["live_sell_authorized"]

def test_date_only_small_flow_has_many_plausible_intervals_no_approval():
    d=undated_fixture()
    d["nontrade_activities"][0]["net_amount"]="1.00"
    d["portfolio_history"]["equity"]=["100","101","101","101","101","101"]
    r=f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)
    assert r["status"]=="AMBIGUOUS_OR_INCONSISTENT_SOURCE_HOLD"
    assert r["quality_admissible_intervals"]>1
    assert not r["conditional_all_scenarios_below_original_HIGH_limits"]

def test_date_only_unexplained_huge_equity_jump_not_assumed_to_be_solved():
    d=undated_fixture()
    d["nontrade_activities"][0]["net_amount"]="20.00"
    r=f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)
    assert r["quality_admissible_intervals"]==0
    assert r["status"]=="AMBIGUOUS_OR_INCONSISTENT_SOURCE_HOLD"
    assert not r["real_s1_high_account_risk_approved"]

@pytest.mark.parametrize("change",[
    {"mode":"TRADING_LIVE"},
    {"authenticated_broker_source":True},
    {"live_operator_stopped":False},
    {"broker_kill_switch":"DISENGAGED"},
    {"risk_level":"LOW"},
])
def test_date_only_source_never_crosses_a_live_boundary(change):
    d=undated_fixture();d.update(change)
    with pytest.raises(f.FundingRiskStop):
        f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)

@pytest.mark.parametrize("event_bad",[
    {"date":"2026-11-01"},
    {"date":"2026-10-14T10:00:00Z"},
    {"date":None},
    {"date":"bad-date"},
    {"net_amount":"-100.00"},
    {"net_amount":"Infinity"},
    {"net_amount":"NaN"},
    {"activity_type":"JNL"},
    {"activity_type":"UNRECOGNIZED"},
    {"transaction_time":"2026-10-13T19:00:00Z"},
])
def test_date_only_bad_funding_evidence_fails_closed(event_bad):
    d=undated_fixture()
    d["nontrade_activities"][0].update(event_bad)
    with pytest.raises(f.FundingRiskStop):
        f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)

def test_date_only_two_cashflows_need_separate_research_not_silent_netting():
    d=undated_fixture()
    d["nontrade_activities"].append(
        {"id":"FAKE-WITHDRAW","activity_type":"CSW",
         "net_amount":"-20","date":"2026-10-14"})
    with pytest.raises(f.FundingRiskStop,match="More than one"):
        f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)

def test_date_only_incomplete_history_and_unfunded_capital_block():
    d=undated_fixture()
    d["nontrade_activity_query_after"]="2026-10-15T00:00:00Z"
    with pytest.raises(f.FundingRiskStop):
        f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)
    d=undated_fixture()
    d["portfolio_history"]["equity"][0]="0"
    with pytest.raises(f.FundingRiskStop):
        f.diagnose_one_date_only_transfer(fixture=d,now_utc=NOW)

def test_date_only_diagnostic_uses_no_real_secrets_or_network():
    s=Path(f.__file__).read_text()
    assert 'def diagnose_one_date_only_transfer' in s
    for banned in ("urlopen(","requests.post(","ALPACA_LIVE_KEY",
                   "ALPACA_LIVE_SECRET","os.environ","getenv("):
        assert banned not in s
