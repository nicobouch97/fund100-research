"""One ACWI-only completed sale can fund small XLK planning, no EEM/XLV exits.

This module is synthetic/no network even when the existing ACWI postorder
joined reader is run with all its genuine transport shapes mocked.
"""
from copy import deepcopy
from pathlib import Path

import pytest

import fund100_v6_s1_first_acwi_only_reinvestment_planner_offline_v1_0 as m
import fund100_v6_s1_first_acwi_postorder_readonly_runtime_locked_v1_0 as post
from test_fund100_v6_s1_first_acwi_postorder_readonly_runtime_locked_v1_0 import injected

NOW="2026-11-09T14:45:00Z"

def fixture(monkeypatch):
    kwargs,_,_,_,_,_,_,_=injected(monkeypatch)
    proof=post.inspect_original_once(**kwargs)
    originals=m.original._original_quantities()
    return {
        "mode":m.MODE,
        "source_authenticated_live":False,
        "operator_stopped":True,
        "kill_switch":"ENGAGED",
        "risk_level":"HIGH",
        "account_observed_at_utc":NOW,
        "first_acwi_postorder_source":proof,
        "first_original_acwi_fill":{
            "symbol":"ACWI","side":"sell","status":"filled",
            "client_order_id":m.cas.CLIENT_IDS["ACWI"],
            "filled_original_exact_qty":format(originals["ACWI"],"f"),
            "complete_broker_fill_activities":True,
            "post_acwi_flat":True,
            "filled_at":"2026-11-09T14:40:00Z",
        },
        "original_deposit_count":1,
        "original_deposit_usd":"130.30",
        "all_order_pages_complete":True,
        "all_fill_pages_complete":True,
        "all_cashflow_pages_complete":True,
        "unreconciled_external_flows":0,
        "open_orders":0,
        "positions":{
            "EEM":{"qty":format(originals["EEM"],"f"),"market_value_usd":"20.00"},
            "XLV":{"qty":format(originals["XLV"],"f"),"market_value_usd":"30.00"},
            "XLE":{"qty":format(originals["XLE"],"f"),"market_value_usd":"25.00"},
        },
        "account":{
            "status":"ACTIVE","account_blocked":False,
            "trading_blocked":False,
            "trade_suspended_by_user":False,"pattern_day_trader":False,
            "multiplier":"1","cash":"35.00","equity":"110.00",
            "buying_power":"35.00","non_marginable_buying_power":"35.00",
            "pending_transfer_in":"0.00","pending_transfer_out":"0.00",
        },
        "worst_case_all_in_order_cost_usd":"0.10",
        "HIGH_account_risk":{
            "daily_return":"-0.01","drawdown":"-0.03",
            "realized_annual_volatility":"0.20",
        },
    }


def assert_stop(r):
    assert r["original_ACWI_fill_live_authenticated"] is False
    assert r["first_etf_buy_live_authorized"] is False
    assert r["second_legacy_sale_live_authorized"] is False
    assert r["original_unsettled_sale_proceeds_settled"] is False
    assert r["limited_margin_reinvestment_permission_proven"] is False
    assert r["broker_GETs"]==r["broker_POSTs"]==r["private_Git_PUTs"]==0
    assert r["private_account"] is r["broker_order"] is r["secrets"] is None
    if r["candidate"]:
        assert r["candidate"]["executable"] is False
        assert r["candidate"]["fake_client_order_id"].startswith("SIM-")


def test_partial_first_acwi_sell_then_first_xlk_buy_math_without_waiting_for_two_other_sells(monkeypatch):
    x=fixture(monkeypatch)
    before=deepcopy(x)
    r=m.assess(snapshot=x,observed_at_utc=NOW)
    assert r["stage"]=="FAKE_FIRST_ACWI_ONLY_XLK_REINVESTMENT_MATH_PASSED_NO_ORDER",r
    assert r["candidate"]["symbol"]=="XLK"
    assert r["candidate"]["side"]=="buy"
    assert m.Decimal("1.00")<=m.Decimal(r["candidate"]["notional_usd"])<=m.Decimal("65.00")
    new=m.Decimal(r["candidate"]["notional_usd"])
    assert new==m.Decimal("29.40")
    assert new+m.Decimal(".10")+m.Decimal("5.50")<=m.Decimal("35.00")
    assert "EEM" in x["positions"] and "XLV" in x["positions"]
    assert x==before and x["account"]["cash"]=="35.00"
    assert_stop(r)


@pytest.mark.parametrize("mutation,reason",[
    (lambda x:x["first_original_acwi_fill"].update(status="partially_filled"),
     "HOLD_FIRST_ORIGINAL_ACWI_FULL_FILL_UNCONFIRMED"),
    (lambda x:x["first_original_acwi_fill"].update(client_order_id="forged"),
     "HOLD_FIRST_ORIGINAL_ACWI_FULL_FILL_UNCONFIRMED"),
    (lambda x:x["first_original_acwi_fill"].update(filled_original_exact_qty="0.01"),
     "HOLD_FIRST_ORIGINAL_ACWI_FULL_FILL_UNCONFIRMED"),
    (lambda x:x["first_original_acwi_fill"].update(complete_broker_fill_activities=False),
     "HOLD_FIRST_ORIGINAL_ACWI_FULL_FILL_UNCONFIRMED"),
    (lambda x:x["positions"].pop("XLV"),
     "HOLD_RETAINED_ORIGINAL_THREE_INVENTORY_CHANGED"),
    (lambda x:x["positions"].update(ACWI={"qty":"0.01","market_value_usd":"1.00"}),
     "HOLD_RETAINED_ORIGINAL_THREE_INVENTORY_CHANGED"),
    (lambda x:x["account"].update(cash="10.00"),
     "HOLD_ORIGINAL_ACCOUNT_CASH_OR_HOLDINGS_NOT_RECONCILED"),
    (lambda x:x["account"].update(non_marginable_buying_power="0.00"),
     "HOLD_FIRST_ACWI_CASH_CANNOT_SUPPORT_NEW_BUY_AND_FIVE_PCT_RESERVE"),
    (lambda x:x["account"].update(multiplier="2"),
     "HOLD_ACCOUNT_CLASS_OR_TRADE_RESTRICTIONS"),
    (lambda x:x["account"].update(pattern_day_trader=True),
     "HOLD_ACCOUNT_CLASS_OR_TRADE_RESTRICTIONS"),
    (lambda x:x["account"].update(trade_suspended_by_user=True),
     "HOLD_ACCOUNT_CLASS_OR_TRADE_RESTRICTIONS"),
    (lambda x:x.update(open_orders=1),
     "HOLD_UNPROVEN_OR_UNRECONCILED_PILOT_SOURCE"),
    (lambda x:x.update(original_deposit_usd="130.31"),
     "HOLD_UNPROVEN_OR_UNRECONCILED_PILOT_SOURCE"),
    (lambda x:x.update(all_fill_pages_complete=False),
     "HOLD_UNPROVEN_OR_UNRECONCILED_PILOT_SOURCE"),
    (lambda x:x["HIGH_account_risk"].update(daily_return="-0.06"),
     "HOLD_HIGH_RISK_6_20_35_BREACHED_OR_UNKNOWN"),
    (lambda x:x["HIGH_account_risk"].update(drawdown="-0.20"),
     "HOLD_HIGH_RISK_6_20_35_BREACHED_OR_UNKNOWN"),
    (lambda x:x["HIGH_account_risk"].update(realized_annual_volatility="0.351"),
     "HOLD_HIGH_RISK_6_20_35_BREACHED_OR_UNKNOWN"),
    (lambda x:x["first_acwi_postorder_source"].update(status="REAL_FAKE_BROKER_GO"),
     "HOLD_NO_ORIGINAL_ACWI_SIGNED_FILL_FLAT_MOCK_CHAIN"),
    (lambda x:x["first_acwi_postorder_source"].update(live_source_authenticated_by_this_run=True),
     "HOLD_NO_ORIGINAL_ACWI_SIGNED_FILL_FLAT_MOCK_CHAIN"),
    (lambda x:x["first_acwi_postorder_source"].update(original_ACWI_resubmission_permitted=True),
     "HOLD_NO_ORIGINAL_ACWI_SIGNED_FILL_FLAT_MOCK_CHAIN"),
    (lambda x:x.update(account_observed_at_utc="2026-11-09T14:35:00Z"),
     "HOLD_STALE_ACCOUNT_OBSERVATION"),
    (lambda x:x["account"].update(pending_transfer_in="1.00"),
     "HOLD_PENDING_EXTERNAL_TRANSFER"),
])
def test_first_acwi_only_buy_fails_closed_to_unreconciled_origins_balances_or_risk(monkeypatch,mutation,reason):
    s=fixture(monkeypatch)
    mutation(s)
    r=m.assess(snapshot=s,observed_at_utc=NOW)
    assert r["stage"]==reason,r
    assert_stop(r)


def test_no_risky_shortcut_to_second_sale_live_buy_or_source_authentication(monkeypatch):
    s=fixture(monkeypatch)
    r=m.assess(snapshot=s,observed_at_utc=NOW)
    assert_stop(r)
    assert m.LIVE_BUY_RELEASED is False
    assert m.NO_NETWORK and m.NO_BROKER_POST and m.NO_PRIVATE_GIT_WRITE
    src=Path(m.__file__).read_text()
    for forbidden in ("urlopen(", "requests.", "httpx.", "method=\"POST\"",
                      "method=\"PUT\"","ALPACA_LIVE_SECRET","GITHUB_TOKEN",
                      "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"):
        assert forbidden not in src
