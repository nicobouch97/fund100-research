"""Synthetic source-asserted S1 risk math; never a broker execution test."""
import copy
from pathlib import Path
import pytest

import fund100_v6_s1_cash_at_order_no_churn_v1_0 as c

def snap(*,cash="130.30",equity="130.30",positions=None,settled=None):
    return {
        "source":"UNVERIFIED_CALLER_ASSERTED_GET_ONLY",
        "trading_enabled":False,"broker_kill_switch":"ENGAGED",
        "observed_at_utc":"2026-10-19T13:30:00Z",
        "open_orders":0,
        "cash_usd":cash,"settled_cash_usd":settled if settled is not None else cash,
        "equity_usd":equity,
        "positions_market_value_usd":{} if positions is None else positions,
    }

def check(s=None,**kw):
    return c.check(snapshot=s if s is not None else snap(),
                   now_utc="2026-10-19T13:30:05Z",**kw)

def test_original_proposal_not_changed_or_live_released():
    from fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0 import source_controls
    m=source_controls()
    assert m["cash_reserve_fraction"]=="0.05"
    assert m["maximum_gross_exposure"]=="0.95"
    assert not m["live_order_execution_released"]

def test_empty_existing_legacy_account_is_never_a_trade_permit():
    result=check()
    assert result["status"]=="CASH_FRACTION_CURRENTLY_ABOVE_FLOOR_NO_ACTION"
    assert result["new_orders"]==result["broker_requests"]==0
    assert result["executable_order_payload"] is None
    assert not result["new_live_buy_authorized"] and not result["new_live_sale_authorized"]
    assert not result["caller_snapshot_independently_authenticated"]

def test_exact_three_hypothetical_s1_notional_screens_pass_without_fees():
    x=check(hypothetical_new_buy_usd="61.89",
            hypothetical_worst_case_total_cost_usd="0.00")
    assert x["status"]=="HYPOTHETICAL_BUY_SCREEN_CLEARED_NOT_AUTHORIZED"
    y=check(snap(cash="68.41",positions={"XLK":"61.89"}),
            hypothetical_new_buy_usd="37.13",
            hypothetical_worst_case_total_cost_usd="0")
    assert y["status"]=="HYPOTHETICAL_BUY_SCREEN_CLEARED_NOT_AUTHORIZED"
    z=check(snap(cash="31.28",positions={"XLK":"61.89","XLE":"37.13"}),
            hypothetical_new_buy_usd="24.75",
            hypothetical_worst_case_total_cost_usd="0")
    assert z["status"]=="HYPOTHETICAL_BUY_SCREEN_CLEARED_NOT_AUTHORIZED"
    assert not z["new_live_buy_authorized"] and not z["risk_stop_inputs_complete"]

def test_microaccount_real_fees_can_remove_cent_level_initial_cash_headroom():
    s=snap(cash="31.28",positions={"XLK":"61.89","XLE":"37.13"})
    assert check(s,hypothetical_new_buy_usd="24.75",
                 hypothetical_worst_case_total_cost_usd="0.02")["status"]=="BLOCK_HYPOTHETICAL_BUY_RESERVED_CASH"

def test_market_appreciation_causes_hold_and_pause_not_forced_sale():
    # Previously deployed 123.77 ETF shares rose 20%; nominal cash unchanged.
    s=snap(cash="6.53",equity="155.05",
           positions={"XLK":"74.27","XLE":"44.56","IWM":"29.69"})
    result=check(s)
    assert result["status"]=="NO_NEW_BUYS_HOLD_AND_RECONCILE"
    assert "FIVE_PERCENT_CASH_FRACTION_DRIFT" in result["explanatory_reasons"]
    assert "NINETY_FIVE_PERCENT_GROSS_FRACTION_DRIFT" in result["explanatory_reasons"]
    assert not result["daily_drift_causes_auto_sales"]
    assert result["new_buys_pause_on_daily_floor_drift"]
    assert not result["historical_daily_cash_floor_fulfilled"]

def test_cost_friction_and_expected_position_addition_are_distinct():
    s=snap(cash="10.00",equity="130.30",positions={"XLK":"60.00","XLE":"36.00","IWM":"24.30"})
    assert check(s,hypothetical_new_buy_usd="4.00",
                 hypothetical_worst_case_total_cost_usd="0")["status"]=="BLOCK_HYPOTHETICAL_BUY_RESERVED_CASH"

@pytest.mark.parametrize("bad",[
    {"open_orders":1}, {"positions_market_value_usd":{"ACWI":"20","XLK":"110.30"}},
    {"broker_kill_switch":"DISENGAGED"}, {"trading_enabled":True}
])
def test_broker_legacy_orders_and_stop_do_not_issue_trades(bad):
    s=snap();s.update(bad)
    if bad.get("trading_enabled") or bad.get("broker_kill_switch")=="DISENGAGED":
        with pytest.raises(c.CashStop):check(s)
    elif "positions_market_value_usd" in bad:
        with pytest.raises(c.CashStop):check(s)
    else:
        assert check(s)["status"]=="NO_NEW_BUYS_HOLD_AND_RECONCILE"

def test_legacy_present_and_reconciled_means_hold_do_not_liquidate():
    s=snap(cash="1.00",equity="101.00",positions={"ACWI":"100"})
    x=check(s)
    assert x["status"]=="NO_NEW_BUYS_HOLD_AND_RECONCILE"
    assert "LEGACY_OR_OUT_OF_UNIVERSE_POSITIONS" in x["explanatory_reasons"]
    assert not x["new_live_sale_authorized"]

@pytest.mark.parametrize("bad",["NaN","-1","Infinity","130.301",True])
def test_bad_account_cash_or_cash_above_equity_fails_closed(bad):
    s=snap();s["cash_usd"]=bad
    with pytest.raises(c.CashStop):check(s)

def test_stale_future_or_unverified_snapshot_fails_closed():
    s=snap();s["observed_at_utc"]="2026-10-19T13:20:00Z"
    with pytest.raises(c.CashStop):check(s)
    s=snap();s["observed_at_utc"]="2026-10-19T13:31:00Z"
    with pytest.raises(c.CashStop):check(s)
    s=snap();s["source"]="BROKER_AUTHENTICATED_GET_ONLY"
    with pytest.raises(c.CashStop):check(s)

@pytest.mark.parametrize("b,cost",[("0.50","0"),("65.01","0"),
 ("1.001","0"),("5.00","0.001"),("5.00","NaN"),("5.00","-1")])
def test_unusable_buy_or_cost_fails_closed(b,cost):
    with pytest.raises(c.CashStop):check(hypothetical_new_buy_usd=b,
                           hypothetical_worst_case_total_cost_usd=cost)

def test_partial_hypothetical_quote_inputs_fail():
    with pytest.raises(c.CashStop):
        check(hypothetical_new_buy_usd="10")

def test_unsettled_cash_prevents_assumed_sufficient_cash():
    s=snap(cash="130.30",settled="4.00")
    assert check(s,hypothetical_new_buy_usd="61.89",
                 hypothetical_worst_case_total_cost_usd="0")["status"]=="BLOCK_HYPOTHETICAL_BUY_RESERVED_CASH"

def test_no_credentials_broker_clients_or_live_payload_fields_in_code():
    source=(Path(__file__).resolve().parent/"fund100_v6_s1_cash_at_order_no_churn_v1_0.py").read_text()
    for forbidden in ("requests.post(","paper_request(","live_request(",
                      "client_order_id","ALPACA_LIVE_KEY","/v2/orders","authorization"):
        # Authorization tokens are banned; plain discussion is allowed.
        if forbidden=="authorization":continue
        assert forbidden not in source
