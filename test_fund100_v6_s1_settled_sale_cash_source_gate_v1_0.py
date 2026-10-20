"""V6 post-sale T+1 cash-source proof: only synthetic invented account data."""
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_s1_settled_sale_cash_source_gate_v1_0 as g
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as original

NOW="2026-10-20T14:27:00Z"

def fake():
    positions={"ACWI":{"qty":"0.89","market_value":"89.00"},
       "EEM":{"qty":"0.30","market_value":"15.00"},
       "XLV":{"qty":"0.08","market_value":"9.00"},
       "XLE":{"qty":"0.10","market_value":"17.00"}}
    receipts={}
    for s in ("ACWI","EEM","XLV"):
        receipts[s]={"id":"FICTIONAL-"+s,"client_order_id":original._id(s),
            "symbol":s,"side":"sell","type":"market","time_in_force":"day",
            "status":"filled","qty":positions[s]["qty"],
            "filled_qty":positions[s]["qty"],"notional":None,
            "filled_at":"2026-10-19T15:30:00Z"}
    return {"mode":g.MODE,"source_authenticated_live":False,
        "risk_level":"HIGH","operator_stopped":True,
        "kill_switch":"ENGAGED","old_v5_live_execution_enabled":False,
        "settlement_calendar_authenticated":False,
        "before_account":{
            "id":"FAKE-ORIGINAL-ACCOUNT-NOT_REAL","status":"ACTIVE",
            "account_blocked":False,"trading_blocked":False,
            "equity":"130.30","cash":"0.30",
            "cash_withdrawable":"0.30","cash_transferable":"0.30",
        },
        "after_account":{
            "id":"FAKE-ORIGINAL-ACCOUNT-NOT_REAL","status":"ACTIVE",
            "account_blocked":False,"trading_blocked":False,
            "equity":"130.00","cash":"113.00",
            "cash_withdrawable":"113.00","cash_transferable":"113.00",
            "non_marginable_buying_power":"113.00",
        },
        "before_positions":positions,
        "after_positions":{"XLE":{"qty":"0.10","market_value":"17.00"}},
        "original_exit_receipts":receipts,
        "unreconciled_open_orders":0,
        "unreconciled_nontrade_activities":0,
        "nontrade_activity_history_complete":True,
        "after_account_observed_at_utc":"2026-10-20T14:26:50Z",
        "invented_us_equity_settlement_sessions":[
           "2026-10-16","2026-10-19","2026-10-20","2026-10-21"],
        "next_hypothetical_buy_symbol":"XLK",
        "next_hypothetical_buy_notional":"61.89",
        "next_hypothetical_buy_cost_buffer":"0.10",
    }

def checked(x,*,at=NOW):
    result=g.evaluate(snap=x,now_utc=at)
    assert result["live_buy_authorized"] is False
    assert result["live_sell_authorized"] is False
    assert result["broker_requests"]==result["broker_order_posts"]==0
    assert result["genuine_broker_cash_settlement_proven"] is False
    assert result["actual_trading_api_settled_cash_field_supported"] is False
    assert result["sell_order_receipts"] is None
    assert result["account_id"] is None and result["actual_cash"] is None
    assert result["executable_order"] is None
    return result["stage"]

def test_synthetic_three_full_fills_tplusone_spendable_fields_validate_but_no_trade():
    assert checked(fake())=="SYNTHETIC_CASH_EVIDENCE_ENVELOPE_VALIDATED_NOT_LIVE"

@pytest.mark.parametrize("field",["cash_withdrawable","cash_transferable"])
@pytest.mark.parametrize("account",["after_account","before_account"])
def test_missing_actual_trading_api_settled_field_is_hard_hold(field,account):
    x=fake()
    x[account].pop(field)
    assert checked(x)=="BROKER_SETTLED_FIELD_UNSUPPORTED_HOLD"

def test_immediate_cash_credit_without_tplusone_does_not_prove_settlement():
    x=fake()
    x["after_account_observed_at_utc"]="2026-10-19T16:30:00Z"
    assert checked(x,at="2026-10-19T16:30:25Z")=="WAIT_US_EQUITY_T_PLUS_ONE_SETTLEMENT_SESSION"

def test_unsettled_cash_credit_and_large_buying_power_cannot_override_withdrawable_cash():
    x=fake()
    x["after_account"]["cash_withdrawable"]="0.30"
    x["after_account"]["cash_transferable"]="0.30"
    x["after_account"]["non_marginable_buying_power"]="999.00"
    assert checked(x)=="BLOCKED_INDEPENDENT_SPENDABLE_CASH_OR_FIVE_PERCENT_FLOOR"

def test_broker_trading_account_not_assumed_to_have_settled_fields():
    x=fake()
    x["after_account"].pop("cash_withdrawable")
    x["after_account"]["buying_power"]="113.00"
    assert checked(x)=="BROKER_SETTLED_FIELD_UNSUPPORTED_HOLD"

def test_net_buy_plus_costs_cannot_breach_reserved_5pct_nav():
    x=fake();x["after_account"]["cash_withdrawable"]="65"
    x["after_account"]["cash_transferable"]="65"
    assert checked(x)=="BLOCKED_INDEPENDENT_SPENDABLE_CASH_OR_FIVE_PERCENT_FLOOR"

@pytest.mark.parametrize("status",["new","partially_filled","pending_cancel",
                                    "rejected","expired","canceled","replaced"])
def test_no_partial_nonfilled_or_canceled_sell_may_credit_settled_proceeds(status):
    x=fake();x["original_exit_receipts"]["ACWI"]["status"]=status
    with pytest.raises(g.SettlementStop):
        g.evaluate(snap=x,now_utc=NOW)

@pytest.mark.parametrize("field,value",[
    ("client_order_id","WRONG"),
    ("symbol","XLK"),("side","buy"),
    ("time_in_force","gtc"),("type","limit"),
    ("qty","1"),("filled_qty","0.01"),("notional","10"),
    ("id",""),("filled_at","2026-10-21T15:30:00Z"),
])
def test_order_id_timestamp_side_price_qty_mismatch_is_invalid(field,value):
    x=fake();x["original_exit_receipts"]["EEM"][field]=value
    with pytest.raises(g.SettlementStop):
        g.evaluate(snap=x,now_utc=NOW)

def test_duplicate_broker_receipt_ids_failclosed():
    x=fake();x["original_exit_receipts"]["XLV"]["id"]="FICTIONAL-ACWI"
    with pytest.raises(g.SettlementStop):g.evaluate(snap=x,now_utc=NOW)

@pytest.mark.parametrize("bad",["XLE","EXTRA"])
def test_extra_or_flattened_xle_original_is_denied(bad):
    x=fake()
    if bad=="XLE":del x["after_positions"]["XLE"]
    else:x["after_positions"]["SPY"]={"qty":"1","market_value":"1"}
    with pytest.raises(g.SettlementStop):
        g.evaluate(snap=x,now_utc=NOW)

def test_changed_original_xle_qty_failclosed():
    x=fake();x["after_positions"]["XLE"]["qty"]="0.11"
    with pytest.raises(g.SettlementStop):g.evaluate(snap=x,now_utc=NOW)

def test_original_xle_too_heavy_requires_review_not_autosell():
    x=fake();x["after_positions"]["XLE"]["market_value"]="40"
    x["after_account"]["cash"]="90";x["after_account"]["equity"]="130"
    x["after_account"]["cash_transferable"]="90"
    x["after_account"]["cash_withdrawable"]="90"
    x["after_account"]["non_marginable_buying_power"]="90"
    assert checked(x)=="BLOCKED_ORIGINAL_XLE_OVERWEIGHT_REVIEW"

def test_unexplained_cash_and_equity_change_stops():
    x=fake();x["after_account"]["equity"]="180"
    assert checked(x)=="BLOCKED_UNRECONCILED_GROSS_EQUITY_CASH"

@pytest.mark.parametrize("delta",["-1","0","-0.01"])
def test_no_sale_cash_credit_stops(delta):
    x=fake();x["after_account"]["cash"]=delta
    x["after_account"]["equity"]="17"
    if delta.startswith("-"):
        with pytest.raises(g.SettlementStop):g.evaluate(snap=x,now_utc=NOW)
    else:
        assert checked(x)=="BLOCKED_NO_SALE_CASH_CREDIT_OBSERVED"

@pytest.mark.parametrize("field,value",[
    ("unreconciled_open_orders",1),
    ("unreconciled_nontrade_activities",1),
    ("nontrade_activity_history_complete",False),
])
def test_unknown_trade_transfer_or_unpaginated_flow_ledger_blocks(field,value):
    x=fake();x[field]=value
    assert checked(x)=="BLOCKED_UNKNOWN_ORDER_OR_CASHFLOW_HISTORY"

@pytest.mark.parametrize("change",[
    {"risk_level":"MEDIUM"},{"operator_stopped":False},
    {"kill_switch":"DISENGAGED"},{"source_authenticated_live":True},
    {"mode":"LIVE"},{"settlement_calendar_authenticated":True},
    {"old_v5_live_execution_enabled":True},
])
def test_only_synthetic_stopped_high_inputs_accepted(change):
    x=fake();x.update(change)
    with pytest.raises(g.SettlementStop):
        g.evaluate(snap=x,now_utc=NOW)

def test_snapshot_older_than_five_minutes_not_a_trade_readiness_signal():
    x=fake();x["after_account_observed_at_utc"]="2026-10-20T14:00:00Z"
    with pytest.raises(g.SettlementStop):g.evaluate(snap=x,now_utc=NOW)

def test_changed_original_broker_account_identity_invalidates_spendable_proof():
    x=fake();x["after_account"]["id"]="FAKE-OTHER"
    with pytest.raises(g.SettlementStop):g.evaluate(snap=x,now_utc=NOW)

def test_nonmarginable_spending_capacity_is_not_replaced_with_margin_buying_power():
    x=fake();x["after_account"].pop("non_marginable_buying_power")
    x["after_account"]["buying_power"]="113"
    with pytest.raises(g.SettlementStop):g.evaluate(snap=x,now_utc=NOW)

def test_thanksgiving_not_trading_settlement_day_in_injected_calendar():
    x=fake()
    for s in x["original_exit_receipts"]:
        x["original_exit_receipts"][s]["filled_at"]="2026-11-25T17:30:00Z"
    x["invented_us_equity_settlement_sessions"]=[
       "2026-11-24","2026-11-25","2026-11-27","2026-11-30"]
    x["after_account_observed_at_utc"]="2026-11-26T15:26:50Z"
    assert checked(x,at="2026-11-26T15:27:00Z")=="WAIT_US_EQUITY_T_PLUS_ONE_SETTLEMENT_SESSION"
    x["after_account_observed_at_utc"]="2026-11-27T15:26:50Z"
    assert checked(x,at="2026-11-27T15:27:00Z")=="SYNTHETIC_CASH_EVIDENCE_ENVELOPE_VALIDATED_NOT_LIVE"

def test_settlement_calendar_must_include_trade_day():
    x=fake()
    x["invented_us_equity_settlement_sessions"]=["2026-10-16","2026-10-20","2026-10-21"]
    with pytest.raises(g.SettlementStop):
        g.evaluate(snap=x,now_utc=NOW)

def test_no_broker_mutation_or_private_token_access_added():
    s=Path(g.__file__).read_text()
    assert g.RELEASE_LIVE_BUY is False
    for blocked in ("urlopen(","requests.post(","method=\"POST\"",
                    "api.alpaca.markets","ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                    "FUND100_PRIVATE_STATE_READ_TOKEN","FUND100_PRIVATE_STATE_WRITE_TOKEN"):
        assert blocked not in s
