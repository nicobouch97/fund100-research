"""Credentialless synthetic tests: no Trading API GET and no LIVE BUY."""
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_s1_trading_api_post_sale_cash_screen_v1_0 as cash

NOW="2026-11-10T20:45:00Z"
FILLED="2026-11-02T15:30:00Z"

def fixture():
    fills={s:{
        "symbol":s,"side":"sell","status":"filled",
        "client_order_id":"synthetic-"+s,
        "reconciled_original_exact_qty":True,
        "filled_exact_qty":True,
        "broker_fills_complete":True,
        "filled_at":FILLED,
    } for s in ("ACWI","EEM","XLV")}
    return {
        "mode":cash.MODE,
        "source_authenticated_live":False,
        "operator_stopped":True,"kill_switch":"ENGAGED","risk_level":"HIGH",
        "observed_at_utc":"2026-11-10T20:44:00Z",
        "original_deposit_events":1,"original_deposit_total_usd":"130.30",
        "all_order_pages_complete":True,"all_fill_pages_complete":True,
        "all_nontrade_activity_pages_complete":True,
        "unreconciled_external_cashflows":0,"unreconciled_open_orders":0,
        "account":{
            "status":"ACTIVE","trading_blocked":False,"account_blocked":False,
            "multiplier":"1","pending_transfer_in":"0","pending_transfer_out":"0",
            "cash":"100.00","equity":"120.00","buying_power":"100.00",
            "non_marginable_buying_power":"100.00",
        },
        "positions":{"XLE":"20.00"},
        "original_exit_fills":fills,
    }

def check(snapshot=None,*,buy="50.00",cost="0.10",symbol="XLK",now=NOW):
    return cash.screen(
        snapshot=fixture() if snapshot is None else snapshot,
        now_utc=now,buy_symbol=symbol,buy_usd=buy,
        worst_case_all_in_cost_usd=cost)

def test_trading_api_fields_and_conservative_buffer_can_pass_math_without_authority():
    report=check()
    assert report["status"]=="CONSERVATIVE_TRADING_API_CASH_ENVELOPE_PASSED_NOT_AUTHORIZED"
    assert report["conservative_completed_weekdays_after_last_sale"]>=3
    assert report["new_buy_notional_validated_for_research_only"] is True
    assert report["broker_api_withdrawable_field_required"] is False
    assert report["eligible_for_separate_approved_live_buy"] is False
    assert report["actual_settled_proceeds_certified"] is False
    assert report["independent_broker_history_authenticated"] is False
    assert report["independent_exchange_calendar_verified"] is False
    assert report["max_new_buy_usd"]=="65.00"
    assert report["broker_requests"]==report["broker_post_attempts"]==0
    assert report["balances"] is report["order_payload"] is None
    assert not cash.LIVE_BUY_RELEASED

@pytest.mark.parametrize("change,stage",[
    (lambda s:s["account"].pop("non_marginable_buying_power"),"HOLD_TRADING_API_CASH_FIELDS_OR_MARKS_MISSING"),
    (lambda s:s["account"].update(non_marginable_buying_power="10.00"),"BLOCK_INSUFFICIENT_CONSERVATIVE_CASH_OR_RESERVE"),
    (lambda s:s["account"].update(cash="20.00",equity="40.00",buying_power="100.00",non_marginable_buying_power="100.00"),"HOLD_TRADING_ACCOUNT_BALANCE_RECONCILIATION"),
    (lambda s:s.update(unreconciled_external_cashflows=1),"HOLD_UNPROVEN_OR_UNRECONCILED_ACCOUNT_HISTORY"),
    (lambda s:s.update(unreconciled_open_orders=1),"HOLD_UNPROVEN_OR_UNRECONCILED_ACCOUNT_HISTORY"),
    (lambda s:s.update(all_fill_pages_complete=False),"HOLD_UNPROVEN_OR_UNRECONCILED_ACCOUNT_HISTORY"),
    (lambda s:s["original_exit_fills"]["ACWI"].update(status="partially_filled"),"HOLD_ORIGINAL_EXIT_FILL_OR_QUANTITY_UNCONFIRMED"),
    (lambda s:s["original_exit_fills"]["EEM"].update(reconciled_original_exact_qty=False),"HOLD_ORIGINAL_EXIT_FILL_OR_QUANTITY_UNCONFIRMED"),
    (lambda s:s["original_exit_fills"].pop("XLV"),"HOLD_MISSING_ORIGINAL_THREE_EXIT_FILLS"),
    (lambda s:s["positions"].update(ACWI="1.00"),"HOLD_LEGACY_NOT_FLAT_OR_XLE_NOT_RETAINED"),
    (lambda s:s["account"].update(multiplier="2"),"HOLD_ACCOUNT_NOT_UNLEVERAGED_ACTIVE_OR_PENDING_TRANSFER"),
    (lambda s:s["account"].update(pending_transfer_in="50.00"),"HOLD_ACCOUNT_NOT_UNLEVERAGED_ACTIVE_OR_PENDING_TRANSFER"),
    (lambda s:s["account"].update(cash="80.00",equity="120.00"),"HOLD_TRADING_ACCOUNT_BALANCE_RECONCILIATION"),
    (lambda s:s.update(observed_at_utc="2026-11-10T20:30:00Z"),"HOLD_STALE_OR_FUTURE_ACCOUNT_SOURCE"),
])
def test_incomplete_or_unsupported_broker_inputs_hold(change,stage):
    s=fixture();change(s)
    assert check(s)["status"]==stage
    assert check(s)["broker_post_attempts"]==0

def test_original_funding_is_a_maximum_not_a_required_exact_deposit():
    s=fixture()
    s["original_deposit_total_usd"]="120.00"
    result=check(s)
    assert result["status"]=="CONSERVATIVE_TRADING_API_CASH_ENVELOPE_PASSED_NOT_AUTHORIZED"
    assert result["original_contribution_cap_usd"]=="130.30"
    assert result["eligible_for_separate_approved_live_buy"] is False
    assert result["actual_settled_proceeds_certified"] is False


@pytest.mark.parametrize("deposit",["0","130.31","999.99","-1","NaN","1e2",""])
def test_invalid_zero_or_over_ceiling_original_deposit_cannot_pass(deposit):
    s=fixture()
    s["original_deposit_total_usd"]=deposit
    assert check(s)["status"]=="HOLD_INVALID_OR_EXCESS_INITIAL_PILOT_FUNDING"


def test_multiple_original_deposit_events_are_not_reinterpreted_as_pilot_cap():
    s=fixture()
    s["original_deposit_events"]=2
    s["original_deposit_total_usd"]="120.00"
    assert check(s)["status"]=="HOLD_UNPROVEN_OR_UNRECONCILED_ACCOUNT_HISTORY"


@pytest.mark.parametrize("pending",["0","0.00","0.0000",0])
def test_real_trading_account_zero_pending_transfer_formats(pending):
    s=fixture()
    s["account"]["pending_transfer_in"]=pending
    s["account"]["pending_transfer_out"]=pending
    assert check(s)["status"]=="CONSERVATIVE_TRADING_API_CASH_ENVELOPE_PASSED_NOT_AUTHORIZED"


@pytest.mark.parametrize("pending",["0.01","-0.01","NaN","1e1","unknown",True,1])
def test_nonzero_or_malformed_pending_transfer_always_holds(pending):
    s=fixture()
    s["account"]["pending_transfer_in"]=pending
    assert check(s)["status"]=="HOLD_ACCOUNT_NOT_UNLEVERAGED_ACTIVE_OR_PENDING_TRANSFER"


def test_tplusone_calendar_not_used_as_immediate_buy_license():
    s=fixture()
    for f in s["original_exit_fills"].values():
        f["filled_at"]="2026-11-10T15:30:00Z"
    assert check(s)["status"]=="WAIT_CONSERVATIVE_POSTSALE_TPLUSONE_BUFFER"

def test_weekend_must_not_count_as_three_completed_weekdays():
    s=fixture()
    for f in s["original_exit_fills"].values():
        f["filled_at"]="2026-11-06T15:30:00Z"
    assert check(s)["status"]=="WAIT_CONSERVATIVE_POSTSALE_TPLUSONE_BUFFER"

@pytest.mark.parametrize("value",["65.01","0.99"])
def test_new_buy_notional_stays_within_one_to_sixtyfive(value):
    assert check(buy=value)["status"]=="BLOCK_NEW_ORDER_UNIVERSE_OR_65_USD_LIMIT"

def test_no_new_buy_spend_can_break_five_percent_cash_floor():
    assert check(buy="65.00",cost="35.00")["status"]=="BLOCK_INSUFFICIENT_CONSERVATIVE_CASH_OR_RESERVE"

def test_original_xle_over_target_requires_review_not_forced_sale():
    s=fixture()
    s["positions"]["XLE"]="40.00"
    s["account"].update(cash="80.00",equity="120.00")
    assert check(s)["status"]=="HOLD_RETAINED_XLE_OVER_TARGET_REVIEW"

@pytest.mark.parametrize("name,value",[
    ("mode","LIVE_BROKER"),("source_authenticated_live",True),
    ("operator_stopped",False),("kill_switch","DISENGAGED"),("risk_level","LOW"),
])
def test_no_caller_could_claim_actual_broker_authentication_or_live_permission(name,value):
    s=fixture();s[name]=value
    with pytest.raises(cash.TradingCashStop):
        check(s)

def test_missing_malformed_data_never_fabricates_cash():
    s=fixture();s["account"]["cash"]="NaN"
    assert check(s)["status"]=="HOLD_TRADING_API_CASH_FIELDS_OR_MARKS_MISSING"
    s=fixture();s["account"]["cash"]="1e5"
    assert check(s)["status"]=="HOLD_TRADING_API_CASH_FIELDS_OR_MARKS_MISSING"

def test_no_network_credentials_private_state_writer_or_orders():
    src=Path(cash.__file__).read_text()
    for forbidden in ("urlopen(", "requests.", "httpx.", "method=\"POST\"",
                      "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET","FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"):
        assert forbidden not in src
    assert "LIVE_BUY_RELEASED=False" in src
    assert cash.MODE=="INJECTED_UNAUTHENTICATED_TRADING_API_FIXTURES_ONLY"
