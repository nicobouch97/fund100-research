"""First fully exited synthetic ETF set -> 1x cash-screen -> first XLK PLAN.

Exactly the source-hash pinned old staged controller is reused unchanged;
no fake settlement field, no broker/private HTTP, no order write or unlock.
"""
from copy import deepcopy
from pathlib import Path

import pytest

import fund100_v6_s1_first_limited_margin_etf_buy_planner_offline_v1_0 as p
import fund100_v6_s1_staged_controller_core_v1_0 as stage
from test_fund100_v6_s1_staged_controller_core_v1_0 import exited, NOW
import audit_fund100_live_boundary as audit


def fixture():
    x,_=exited()
    assert x["independent_t_plus_one_settlement_proven"] is False
    assert x["settled_cash_usd"]=="0.30"
    cash={
        "mode":p.cashscreen.MODE,
        "source_authenticated_live":False,
        "risk_level":"HIGH","operator_stopped":True,"kill_switch":"ENGAGED",
        "observed_at_utc":x["observed_at_utc"],
        "original_deposit_events":1,
        "original_deposit_total_usd":"130.30",
        "all_order_pages_complete":True,
        "all_fill_pages_complete":True,
        "all_nontrade_activity_pages_complete":True,
        "unreconciled_external_cashflows":0,
        "unreconciled_open_orders":0,
        "account":{
            "status":"ACTIVE","trading_blocked":False,"account_blocked":False,
            "multiplier":"1",
            "trade_suspended_by_user":False,"pattern_day_trader":False,
            "cash":x["cash_usd"],"equity":x["equity_usd"],
            "buying_power":x["cash_usd"],
            "non_marginable_buying_power":x["cash_usd"],
        },
        "positions":{"XLE":x["positions"]["XLE"]["market_value_usd"]},
        "original_exit_fills":{
            s:{
                "symbol":s,"side":"sell","status":"filled",
                "client_order_id":stage.candidate_id(s,"sell"),
                "reconciled_original_exact_qty":True,
                "filled_exact_qty":True,
                "broker_fills_complete":True,
                "filled_at":"2026-10-19T17:29:00Z",
            } for s in stage.OLD
        },
    }
    return x,cash


def run(x=None,cash=None):
    a,b=fixture()
    return p.assess(staged_snapshot=a if x is None else x,
                    limited_margin_snapshot=b if cash is None else cash,
                    observed_at_utc=NOW)


def assert_stop(r):
    assert r["broker_GETs"]==r["broker_POSTs"]==r["private_Git_writes"]==0
    assert r["broker_source_authenticated"] is False
    assert r["original_signed_live_head_authenticated"] is False
    assert r["original_sell_fills_live_authenticated"] is False
    assert r["actual_settled_cash_verified"] is False
    assert r["limited_margin_equity_reinvestment_live_authorized"] is False
    assert r["live_buy_order_authorized"] is False
    assert r["broker_receipts"] is r["private_account"] is None
    if r["first_etf_candidate"]:
        assert r["first_etf_candidate"]["executable"] is False
        assert r["first_etf_candidate"]["simulated_client_order_id"].startswith("SIM-")


def test_same_day_first_etf_buy_math_after_three_signed_exits_without_spoofed_settlement():
    x,c=fixture()
    assert stage.assess(snap=x,now_utc=NOW)["stage"]=="WAIT_ACTUAL_BROKER_SETTLEMENT_PROOF"
    before=deepcopy(x)
    r=run(x,c)
    assert r["status"]=="TEST_ONLY_FIRST_XLK_1X_ETF_REINVESTMENT_CANDIDATE_NO_TRANSPORT",r
    q=r["first_etf_candidate"]
    assert q["symbol"]=="XLK" and q["side"]=="buy"
    assert p.Decimal("1")<=p.Decimal(q["estimated_notional_usd"])<=p.Decimal("65")
    assert p.Decimal(x["cash_usd"])-p.Decimal(q["estimated_notional_usd"])-p.Decimal(".10") >=p.Decimal(x["equity_usd"])*stage.CASH_FLOOR
    assert x==before and x["settled_cash_usd"]=="0.30"
    assert_stop(r)


@pytest.mark.parametrize("mutation,status",[
    (lambda x,c:c["account"].update(multiplier="2"),"HOLD_1X_ETF_CASH_SCREEN_OR_FIELDS_UNQUALIFIED"),
    (lambda x,c:c["account"].update(pattern_day_trader=True),"HOLD_1X_ETF_CASH_SCREEN_OR_FIELDS_UNQUALIFIED"),
    (lambda x,c:c["account"].update(trade_suspended_by_user=True),"HOLD_1X_ETF_CASH_SCREEN_OR_FIELDS_UNQUALIFIED"),
    (lambda x,c:c.update(original_deposit_total_usd="130.31"),"HOLD_1X_ETF_CASH_SCREEN_OR_FIELDS_UNQUALIFIED"),
    (lambda x,c:c.update(all_fill_pages_complete=False),"HOLD_1X_ETF_CASH_SCREEN_OR_FIELDS_UNQUALIFIED"),
    (lambda x,c:c.update(unreconciled_open_orders=1),"HOLD_1X_ETF_CASH_SCREEN_OR_FIELDS_UNQUALIFIED"),
    (lambda x,c:c["account"].update(cash="99.99"),"HOLD_LIMITED_MARGIN_OBSERVATION_OR_ORIGINAL_FILL_MISMATCH"),
    (lambda x,c:c["positions"].update(XLE="18.00"),"HOLD_LIMITED_MARGIN_OBSERVATION_OR_ORIGINAL_FILL_MISMATCH"),
    (lambda x,c:c["original_exit_fills"]["EEM"].update(client_order_id="forged"),"HOLD_LIMITED_MARGIN_OBSERVATION_OR_ORIGINAL_FILL_MISMATCH"),
    (lambda x,c:c.update(observed_at_utc="2026-10-19T17:29:55Z"),"HOLD_LIMITED_MARGIN_OBSERVATION_OR_ORIGINAL_FILL_MISMATCH"),
    (lambda x,c:c["account"].update(non_marginable_buying_power="0.00"),"HOLD_LIMITED_MARGIN_AVAILABLE_FUNDS_OR_FIVE_PCT_CASH_FLOOR"),
    (lambda x,c:x["risk_metrics"].update(daily_return="-0.06"),"HOLD_THREE_LEGACY_EXITS_NOT_FULLY_RECONCILED"),
    (lambda x,c:x.update(open_orders=1),"HOLD_THREE_LEGACY_EXITS_NOT_FULLY_RECONCILED"),
    (lambda x,c:x["order_history"][stage.candidate_id("ACWI","sell")].update(status="partially_filled"),"HOLD_THREE_LEGACY_EXITS_NOT_FULLY_RECONCILED"),
    (lambda x,c:x["positions"].update(ACWI={"qty":"0.1","market_value_usd":"1.00"}),"HOLD_ORIGINAL_STAGED_ACCOUNT_OR_RISK_SOURCE_INVALID"),
])
def test_reconciliation_and_cash_reinvestment_sources_cannot_be_claimed_by_forged_flags(mutation,status):
    x,c=fixture()
    mutation(x,c)
    r=run(x,c)
    assert r["status"]==status,r
    assert_stop(r)


def test_no_reused_xle_only_snapshot_after_first_xlk_purchase():
    x,c=fixture()
    x["positions"]["XLK"]={"qty":"0.01","market_value_usd":"61.89"}
    x["cash_usd"]="51.41"
    x["equity_usd"]="130.30"
    x["order_history"][stage.candidate_id("XLK","buy")]={
        "symbol":"XLK","side":"buy","notional":"61.89","status":"filled"}
    r=run(x,c)
    assert r["status"]=="HOLD_LIMITED_MARGIN_OBSERVATION_OR_ORIGINAL_FILL_MISMATCH"
    assert_stop(r)


def test_subcent_fee_is_not_silently_rounded_down_to_pass():
    x,c=fixture()
    x["hypothetical_fee_buffers_usd"]["XLK"]="0.001"
    r=run(x,c)
    assert r["status"]=="HOLD_1X_ETF_CASH_SCREEN_OR_FIELDS_UNQUALIFIED"
    assert_stop(r)


def test_new_planner_does_not_change_hash_pinned_protected_broker_reader_dependencies():
    assert audit.git_blob_digest(Path(stage.__file__))=="640066fddb56c1d8a6cd19d7377147dc426329ec"
    assert stage.TRANSPORT_RELEASED is False
    assert stage.PUBLIC_EXECUTION_ENABLED is False
    assert p.NO_BROKER_NETWORK and p.NO_BROKER_POST and p.NO_PRIVATE_STATE_WRITES
    assert p.LIVE_BUY_RELEASED is False
    assert p.cashscreen.LIVE_BUY_RELEASED is False
    script=Path(p.__file__).read_text()
    for term in ("urlopen(", "requests.", "httpx.", "ALPACA_LIVE_KEY",
                 "ALPACA_LIVE_SECRET", "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
                 "method=\"POST\"", "GITHUB_TOKEN"):
        assert term not in script
