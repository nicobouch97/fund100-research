"""Synthetic private risk-source sensitivity; zero broker access and zero orders."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import pytest
import fund100_v6_s1_live_cashflow_risk_bounds_v1_0 as bounds

START = datetime(2026, 10, 12, 20, tzinfo=timezone.utc)
NOW = "2026-10-18T20:00:00Z"

def dataset(values=None, flow="100", kind="CSD"):
    values = values or ["100","200","200","200","200","200"]
    return dict(
        history={"timeframe":"1D",
                 "timestamp":[int((START+timedelta(days=i)).timestamp()) for i in range(6)],
                 "equity":values},
        activities=[{"id":"PRIVATE-EVENT","activity_type":kind,
                     "date":"2026-10-13","net_amount":flow}],
        account={"equity":values[-1], "last_equity":values[-1]},
        observed_at_utc=NOW,
    )

def check(fixture):
    result=bounds.inspect(**fixture)
    assert result["s1_high_risk_approved"] is False
    assert result["live_buy_sell_authorized"] is False
    assert result["daily_equity_risk_authorized"] is False
    assert result["drawdown_risk_authorized"] is False
    assert result["annual_volatility_risk_authorized"] is False
    assert result["private_account_equity"] is None
    assert result["private_activity_date_amount_id"] is None
    assert result["private_adjusted_return_series"] is None
    assert "PRIVATE-EVENT" not in str(result)
    assert "2026-10-13" not in str(result)
    return result

def test_actual_json_number_equity_and_activity_fields_are_accepted_without_float_roundtrips():
    d=dataset()
    # Alpaca's history values are JSON numbers; its other account fields
    # may be decimal strings. Decode finite JSON numbers, never treat
    # floats or their textual representations as an account authorization.
    d["history"]["equity"]=[100.0,200.0,200.0,200.0,200.0,200.0]
    d["account"]["last_equity"]=200.0
    d["activities"][0]["net_amount"]=100.0
    r=check(d)
    assert r["status"]=="ONE_CONDITIONALLY_SAFE_TIMING_RESEARCH_ONLY"
    assert r["source_rejection_category"]=="NONE"
    assert not r["s1_high_risk_approved"]
    assert not r["live_buy_sell_authorized"]


@pytest.mark.parametrize("value",[True,False,None,float("nan"),float("inf"),
                                  float("-inf"),"NaN","Infinity","bad"])
def test_json_number_coercion_rejects_nonfinite_bool_missing_and_malformed(value):
    d=dataset()
    d["history"]["equity"][1]=value
    r=check(d)
    assert r["status"]=="SOURCE_NOT_QUALIFIED_HOLD"
    assert r["source_rejection_category"]=="PRIVATE_FINANCIAL_FIELD_UNUSABLE"


def test_live_reader_receives_float_equity_without_broker_trade():
    from test_fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 import scenario
    import fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 as reader
    d=scenario()
    d["history"]["equity"]=[float(x) for x in d["history"]["equity"]]
    d["activities"][0]["date"]="2026-10-13"
    r=reader.evaluate(**d)
    assert r["broker_get_requests"]==7
    assert r["broker_non_get_requests"]==r["live_orders"]==0
    assert r["actual_s1_6_20_35_risk_verified"] is False
    assert r["live_buy_sell_authorized"] is False


def unfunded_prefix_case():
    d=dataset()
    d["history"]["timestamp"]=[
        int((START+timedelta(days=i-2)).timestamp()) for i in range(8)
    ]
    d["history"]["equity"]=[None,0.0,100.0,200.0,200.0,200.0,200.0,200.0]
    return d


def initial_funding_case():
    d=unfunded_prefix_case()
    # Real-origin-shaped hypothesis: deposit booking date is first funded
    # session, after an authentic pre-funding empty prefix.
    d["activities"][0]["date"]="2026-10-12"
    d["history"]["equity"]=[None,0.0,100.0,100.0,100.0,100.0,100.0,100.0]
    d["account"]["last_equity"]="100"
    d["account"]["equity"]="100"
    return d


def test_initial_cash_deposit_as_first_funded_close_is_a_hypothesis_not_alpha():
    r=check(initial_funding_case())
    assert r["status"]=="INITIAL_FUNDING_MAY_BE_IN_FIRST_FUNDED_CLOSE_RESEARCH_ONLY"
    assert r["unfunded_history_prefix_observed"]
    assert r["one_cashflow_sensitivity_evaluated_in_memory"]
    assert not r["broker_actual_economic_transfer_time_verified"]
    assert not r["s1_high_risk_approved"]
    assert not r["live_buy_sell_authorized"]


def test_booking_after_first_funded_close_cannot_be_placed_at_baseline():
    d=initial_funding_case()
    d["activities"][0]["date"]="2026-10-14"
    r=check(d)
    assert r["status"]=="NO_QUALITY_ADMISSIBLE_PLACEMENT_HOLD"


def test_initial_funding_hypothesis_still_enforces_true_daily_loss_stop():
    d=initial_funding_case()
    d["history"]["equity"][-1]=90.0
    d["account"]["last_equity"]="90"
    d["account"]["equity"]="90"
    r=check(d)
    assert r["status"]=="HIGH_RISK_BREACH_POSSIBLE_HOLD"
    assert not r["s1_high_risk_approved"]


def test_no_unfunded_prefix_means_no_inception_reinterpretation():
    d=dataset(["100","100","100","100","100","100"],flow="100")
    d["activities"][0]["date"]="2026-10-12"
    r=check(d)
    assert r["status"]=="NO_QUALITY_ADMISSIBLE_PLACEMENT_HOLD"


def test_unfunded_null_and_zero_prefix_are_not_market_returns():
    d=unfunded_prefix_case()
    result=check(d)
    assert result["unfunded_history_prefix_observed"] is True
    assert result["one_cashflow_sensitivity_evaluated_in_memory"] is True
    assert result["status"]=="ONE_CONDITIONALLY_SAFE_TIMING_RESEARCH_ONLY"
    assert not result["s1_high_risk_approved"]


@pytest.mark.parametrize("post_funding_gap",[None,0.0,-1.0])
def test_post_funding_missing_zero_negative_equity_still_halts(post_funding_gap):
    d=unfunded_prefix_case()
    d["history"]["equity"][4]=post_funding_gap
    r=check(d)
    assert r["status"]=="SOURCE_NOT_QUALIFIED_HOLD"
    assert r["source_rejection_category"] in (
        "EQUITY_FIELDS_UNUSABLE","PRIVATE_FINANCIAL_FIELD_UNUSABLE")
    assert not r["one_cashflow_sensitivity_evaluated_in_memory"]


def test_negative_prefunding_history_is_not_silently_discarded():
    d=unfunded_prefix_case()
    d["history"]["equity"][1]=-1.0
    r=check(d)
    assert r["status"]=="SOURCE_NOT_QUALIFIED_HOLD"
    assert r["source_rejection_category"]=="EQUITY_FIELDS_UNUSABLE"


def test_only_five_funded_observations_cannot_certify_risk():
    d=unfunded_prefix_case()
    d["history"]["equity"][2]=0.0
    r=check(d)
    assert r["status"]=="SOURCE_NOT_QUALIFIED_HOLD"
    assert r["source_rejection_category"]=="INSUFFICIENT_FUNDED_HISTORY"


def test_one_100_deposit_can_explain_apparent_100pct_raw_jump():
    result=check(dataset())
    assert result["status"]=="ONE_CONDITIONALLY_SAFE_TIMING_RESEARCH_ONLY"
    assert result["one_cashflow_sensitivity_evaluated_in_memory"]

def test_exact_economic_time_unobserved_cannot_approve_even_unique_case():
    result=check(dataset())
    assert result["broker_actual_economic_transfer_time_verified"] is False

def test_true_10pct_current_day_loss_is_not_disguised_by_old_deposit():
    d=dataset(["100","200","200","200","200","180"])
    result=check(d)
    assert result["status"]=="HIGH_RISK_BREACH_POSSIBLE_HOLD"

def test_small_transfer_potentially_any_day_is_ambiguous():
    d=dataset(["100"]*6,flow="0.10")
    result=check(d)
    assert result["status"]=="MULTIPLE_PLAUSIBLE_TIMINGS_HOLD"

def test_cash_withdrawal_must_be_negative_and_conservatively_adjusted():
    d=dataset(["100","50","50","50","50","50"],flow="-50",kind="CSW")
    assert check(d)["status"]=="ONE_CONDITIONALLY_SAFE_TIMING_RESEARCH_ONLY"

@pytest.mark.parametrize("corrupt",["no_date","transaction_time","wrong_sign",
             "duplicate","unknown","asset","full_page","history_gap",
             "unsorted","stale","last_equity","bad_value","future_event"])
def test_bad_broker_sources_hold_closed(corrupt):
    d=dataset()
    if corrupt=="no_date":
        d["activities"][0].pop("date")
    elif corrupt=="transaction_time":
        d["activities"][0]["transaction_time"]="2026-10-13T14:30:00Z"
    elif corrupt=="wrong_sign":
        d["activities"][0]["net_amount"]="-100"
    elif corrupt=="duplicate":
        d["activities"].append(deepcopy(d["activities"][0]))
    elif corrupt=="unknown":
        d["activities"][0]["activity_type"]="NEW"
    elif corrupt=="asset":
        d["activities"][0]["activity_type"]="ACATS"
    elif corrupt=="full_page":
        d["activities"]=[{"id":str(i),"activity_type":"DIV"} for i in range(100)]
    elif corrupt=="history_gap":
        d["history"]["timestamp"][2]+=6*86400
    elif corrupt=="unsorted":
        d["history"]["timestamp"][2]=d["history"]["timestamp"][1]
    elif corrupt=="stale":
        d["observed_at_utc"]="2026-11-18T20:00:00Z"
    elif corrupt=="last_equity":
        d["account"]["last_equity"]="180"
    elif corrupt=="bad_value":
        d["history"]["equity"][1]="NaN"
    elif corrupt=="future_event":
        d["activities"][0]["date"]="2026-11-01"
    assert check(d)["status"]=="SOURCE_NOT_QUALIFIED_HOLD"

def test_source_failure_reason_is_from_safe_whitelist_only():
    d=dataset()
    d["account"]["last_equity"]="180"
    result=check(d)
    assert result["source_rejection_category"]=="LATEST_ACCOUNT_CLOSE_MISMATCH"
    d=dataset()
    d["activities"][0].pop("date")
    result=check(d)
    assert result["source_rejection_category"]=="BOOKING_DATE_MISSING"
    assert "PRIVATE-EVENT" not in str(result)


def test_missing_enough_equity_series_holds_instead_of_risk_approval():
    d=dataset()
    d["history"]["timestamp"]=d["history"]["timestamp"][:4]
    d["history"]["equity"]=d["history"]["equity"][:4]
    assert check(d)["status"]=="SOURCE_NOT_QUALIFIED_HOLD"

def test_stopped_live_observer_can_embed_safe_status_with_unmodified_seven_get_contract():
    import fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 as live
    from test_fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 import scenario
    d=scenario()
    d["activities"][0]["date"]="2026-10-13"
    r=live.evaluate(**d)
    assert r["one_month_date_only_cashflow_risk_status"] in (
        "MULTIPLE_PLAUSIBLE_TIMINGS_HOLD",
        "HIGH_RISK_BREACH_POSSIBLE_HOLD",
        "NO_QUALITY_ADMISSIBLE_PLACEMENT_HOLD",
        "SOURCE_NOT_QUALIFIED_HOLD",
        "ONE_CONDITIONALLY_SAFE_TIMING_RESEARCH_ONLY",
    )
    assert r["actual_s1_6_20_35_risk_verified"] is False
    assert r["live_buy_sell_authorized"] is False
    assert r["broker_get_requests"]==7 and r["broker_non_get_requests"]==0
    assert "FAKE-1" not in str(r)
    assert "110.00" not in str(r)
