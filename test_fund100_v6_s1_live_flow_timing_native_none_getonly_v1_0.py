"""Original seven-GET API-shaped source fixtures, never actual account records."""
from copy import deepcopy
from pathlib import Path
import pytest
from test_fund100_v6_s1_live_private_xle_activity_getonly_v1_0 import case
import fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 as q


def scenario():
    d=case()
    # This shape is invented, not evidence of a broker-calculated return.
    d["history"]["profit_loss_pct"]=[0,0,0,0,0,0,0]
    d["native_none_history"]=deepcopy(d["history"])
    return d


def test_real_source_validation_never_outputs_private_transaction_values():
    d=scenario()
    r=q.evaluate(**d)
    assert r["original_account_and_legacy_positions_verified"]
    assert r["original_external_funding_classification"].startswith("EXTERNAL_TRANSFER_TYPES_SEEN")
    assert r["cash_transfer_amount_and_timestamp_field_status"]=="CASH_TRANSFER_SOURCE_DATE_ONLY_NO_DIETZ"
    assert r["broker_cashflow_types_none_pnl_comparison"]=="BROKER_NATIVE_NONE_PNL_SERIES_SAME"
    assert not r["actual_cashflow_adjusted_dietz_returns_calculated"]
    assert not r["actual_s1_6_20_35_risk_verified"]
    assert not r["live_buy_sell_authorized"]
    assert r["broker_get_requests"]==7 and r["broker_non_get_requests"]==r["live_orders"]==0
    for text in ("FAKE-1","FAKE-2","110.00","SYNTHETIC-ACCOUNT-ID"):
        assert text not in str(r)
    assert r["private_activity_ids_dates_amounts"] is None


def test_signed_exact_original_cash_with_timezone_still_not_trading_approval():
    d=scenario()
    d["activities"][0]["transaction_time"]="2026-10-08T15:44:00-04:00"
    r=q.evaluate(**d)
    assert r["cash_transfer_amount_and_timestamp_field_status"]==(
        "CASH_TRANSFER_AMOUNT_AND_TRANSACTION_TIME_FIELDS_PRESENT_UNRECONCILED")
    assert not r["actual_cashflow_adjusted_dietz_returns_calculated"]


@pytest.mark.parametrize("activity",[
    {"id":"S1","activity_type":"CSD","net_amount":"-100","date":"2026-10-12"},
    {"id":"S1","activity_type":"CSW","net_amount":"100","date":"2026-10-12"},
    {"id":"S1","activity_type":"CSD","date":"2026-10-12"},
    {"id":"S1","activity_type":"CSD","net_amount":"NaN"},
    {"id":"S1","activity_type":"CSW","net_amount":"Infinity"},
    {"id":"S1","activity_type":"CSD","net_amount":0},
])
def test_suspect_cash_transfer_amount_or_sign_is_not_money_for_risk(activity):
    d=scenario();d["activities"]=[activity]
    r=q.evaluate(**d)
    assert r["cash_transfer_amount_and_timestamp_field_status"]=="CASH_AMOUNT_SOURCE_INVALID"
    assert not r["live_buy_sell_authorized"]


@pytest.mark.parametrize("value",["2026-10-12","2026-10-12T09:45:00",None])
def test_date_or_naive_time_does_not_substitute_for_intraday_cashflow(value):
    d=scenario()
    d["activities"][0]["transaction_time"]=value
    r=q.evaluate(**d)
    assert r["cash_transfer_amount_and_timestamp_field_status"]=="CASH_TRANSFER_SOURCE_DATE_ONLY_NO_DIETZ"


def test_non_cash_asset_journals_block_even_with_other_cash_deposits():
    d=scenario()
    d["activities"].append({"id":"A3","activity_type":"ACATC","net_amount":"10"})
    r=q.evaluate(**d)
    assert r["cash_transfer_amount_and_timestamp_field_status"]=="NONCASH_OR_UNKNOWN_TRANSFER_REQUIRES_VALUATION_REVIEW"


def test_incomplete_page_never_grants_clear_cashflow_source():
    d=scenario()
    d["activities"]=[{"id":str(i),"activity_type":"DIV"} for i in range(100)]
    r=q.evaluate(**d)
    assert r["cash_transfer_amount_and_timestamp_field_status"]=="PAGINATION_INCOMPLETE"


def test_no_cash_transfer_in_short_window_is_not_no_funding_in_account_lifetime():
    d=scenario()
    d["activities"]=[{"id":"D","activity_type":"DIV","net_amount":"0.02"}]
    r=q.evaluate(**d)
    assert r["cash_transfer_amount_and_timestamp_field_status"]=="NO_EXTERNAL_TRANSFER_DETECTED_IN_WINDOW"
    assert not r["actual_s1_6_20_35_risk_verified"]


def test_native_none_broker_profit_field_difference_is_diagnostic_only():
    d=scenario();d["native_none_history"]["profit_loss_pct"]=[0,0,0,0,1,0,0]
    r=q.evaluate(**d)
    assert r["broker_cashflow_types_none_pnl_comparison"]=="BROKER_NATIVE_NONE_PNL_SERIES_DIFFERS"
    assert not r["actual_cashflow_adjusted_dietz_returns_calculated"]
    assert not r["broker_native_none_is_validated_true_strategy_return"]


@pytest.mark.parametrize("change",[
    {"timeframe":"1Min"},
    {"timestamp":[7,8,9,10,11,12,13]},
    {"profit_loss_pct":[0,0,0]},
    {"profit_loss_pct":[0,0,"NaN",0,0,0,0]},
    {"profit_loss_pct":None}
])
def test_native_none_mismatched_or_invalid_observations_are_not_claimed_adusted(change):
    d=scenario()
    d["native_none_history"].update(change)
    if change.get("timeframe")=="1Min":
        with pytest.raises(q.FlowTimingStop):
            q.evaluate(**d)
    else:
        z=q.evaluate(**d)
        assert z["broker_cashflow_types_none_pnl_comparison"] in (
            "BROKER_NATIVE_NONE_TIME_SERIES_NOT_COMPARABLE",
            "BROKER_NATIVE_NONE_PNL_SERIES_MISSING_OR_UNCOMPARABLE")


def test_original_live_account_still_rejected_if_open_orders():
    d=scenario()
    d["orders"]=[{"id":"fake","status":"new","symbol":"ACWI"}]
    with pytest.raises(q.FlowTimingStop):
        q.evaluate(**d)


def test_only_existing_seven_get_source_no_order_transport():
    assert q.PATHS==("/v2/account","/v2/positions","/v2/orders",
        "/v2/clock","/v2/account/portfolio/history","/v2/account/activities",
        "/v2/account/portfolio/history")
    assert q.EXTRA_PARAMS=={"period":"1M","timeframe":"1D","cashflow_types":"NONE"}
    src=Path(q.__file__).read_text()
    for forbidden in ('method="POST"','method="DELETE"',
                      'requests.post(', 'submit_'+'authorized_order_batch('):
        assert forbidden not in src


def test_only_one_observed_cashflow_categorised_without_customer_data():
    d=scenario()
    out=q.evaluate(**d)
    assert out["observed_cash_transfer_count_class"]==(
        "OBSERVED_ONE_CASH_TRANSFER_NOT_TIMING_PROOF")
    assert out["actual_s1_6_20_35_risk_verified"] is False
    for private in ("FAKE-1","110.00","SYNTHETIC-ACCOUNT-ID"):
        assert private not in str(out)


def test_multiple_observed_cashflows_block_single_transfer_method():
    d=scenario()
    d["activities"].append({"id":"PRIVATE-B",
        "activity_type":"CSW","net_amount":"-30.00","date":"2026-10-12"})
    out=q.evaluate(**d)
    assert out["observed_cash_transfer_count_class"]==(
        "OBSERVED_MULTIPLE_CASH_TRANSFERS_SINGLE_FLOW_MODEL_INAPPLICABLE")
    assert not out["live_buy_sell_authorized"]
    for private in ("PRIVATE-B","30.00","2026-10-12"):
        assert private not in str(out)


def test_no_cash_transfer_in_queried_page_is_not_account_lifetime_proof():
    d=scenario()
    d["activities"]=[{"id":"PRIVATE-D","activity_type":"DIV"}]
    out=q.evaluate(**d)
    assert out["observed_cash_transfer_count_class"]==(
        "OBSERVED_ZERO_CASH_TRANSFERS_NOT_LIFETIME_PROOF")
    assert not out["actual_s1_6_20_35_risk_verified"]


@pytest.mark.parametrize("a,expected",[
    ([{"id":"PRIVATE-Z","activity_type":"JNL"}],
     "OBSERVED_FUNDING_TYPE_OR_AMOUNT_UNTRUSTED_HOLD"),
    ([{"id":"PRIVATE-Z","activity_type":"CSD","net_amount":"bad"}],
     "OBSERVED_FUNDING_TYPE_OR_AMOUNT_UNTRUSTED_HOLD"),
    ([{"id":"PRIVATE-Z","activity_type":"MYSTERY"}],
     "OBSERVED_FUNDING_TYPE_OR_AMOUNT_UNTRUSTED_HOLD"),
    ([{"id":str(i),"activity_type":"DIV"} for i in range(100)],
     "OBSERVED_FUNDING_PAGE_INCOMPLETE_HOLD"),
])
def test_ambiguous_cash_activity_scope_stays_hold(a,expected):
    d=scenario();d["activities"]=a
    out=q.evaluate(**d)
    assert out["observed_cash_transfer_count_class"]==expected
    assert not out["live_buy_sell_authorized"]


def test_count_class_does_not_change_original_seven_get_scoped_contract():
    assert q.PATHS[-2:]==(
        "/v2/account/activities","/v2/account/portfolio/history")
    out=q.evaluate(**scenario())
    assert out["broker_get_requests"]==7
    assert out["broker_non_get_requests"]==0
    assert out["live_orders"]==0
    assert out["actual_cashflow_adjusted_dietz_returns_calculated"] is False


def test_genuine_source_shape_is_joined_to_original_staged_controller_stop():
    r=q.evaluate(**scenario())
    assert r["staged_v6_live_source_readiness"]==(
        "BLOCKED_UNPROVEN_CASHFLOW_ADJUSTED_1M_ACCOUNT_RISK")
    assert r["staged_controller_verified_full_private_order_ledger"] is False
    assert r["staged_controller_produced_executable_order"] is False
    assert r["broker_get_requests"]==7
    assert r["live_orders"]==r["broker_non_get_requests"]==0
    assert "SIM-v6s1-" not in str(r)


def test_original_seven_get_reports_only_non_private_funding_calendar_relation():
    d=scenario()
    # Use an original unfunded prefix and then six completed funded days,
    # a single cash deposit booking on the first funded sample day.
    from datetime import datetime,timezone,timedelta
    base=datetime(2026,10,10,20,tzinfo=timezone.utc)
    d["history"]["timestamp"]=[
        int((base+timedelta(days=i)).timestamp()) for i in range(8)]
    d["history"]["equity"]=[None,0,100,100,100,100,100,100]
    d["account"]["equity"]="100"
    d["account"]["last_equity"]="100"
    d["activities"][0]["date"]="2026-10-12"
    d["observed_at_utc"]="2026-10-18T20:00:00Z"
    d["native_none_history"]["timestamp"]=d["history"]["timestamp"][:]
    d["native_none_history"]["equity"]=d["history"]["equity"][:]
    d["history"]["profit_loss_pct"]=[0]*8
    d["native_none_history"]["profit_loss_pct"]=[0]*8
    out=q.evaluate(**d)
    assert out["initial_cashflow_booking_vs_first_funded_sample"]==(
        "BOOKED_ON_FIRST_FUNDED_SAMPLE_DATE")
    assert out["actual_s1_6_20_35_risk_verified"] is False
    assert out["staged_v6_live_source_readiness"]==(
        "BLOCKED_UNPROVEN_CASHFLOW_ADJUSTED_1M_ACCOUNT_RISK")
    assert not out["live_buy_sell_authorized"]
    assert out["broker_get_requests"]==7
    assert out["broker_non_get_requests"]==out["live_orders"]==0
    assert "2026-10-12" not in str(out)
