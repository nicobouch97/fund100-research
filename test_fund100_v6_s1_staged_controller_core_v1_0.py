"""S1 staged controller synthetic broker mechanical regression, NO REAL ORDERS."""
from copy import deepcopy
import pytest
import fund100_v6_s1_staged_controller_core_v1_0 as c

NOW="2026-10-19T17:30:00Z"

def fixture():
    return {
      "schema":c.SCHEMA,"mode":"IN_MEMORY_FAKE_BROKER_ONLY",
      "observed_at_utc":"2026-10-19T17:29:56Z",
      "risk_level":"HIGH","operator_stopped":True,
      "kill_switch":"ENGAGED","old_v5_controller_active":False,
      "equity_usd":"130.30","cash_usd":"0.30","settled_cash_usd":"0.30",
      "positions":{
        "ACWI":{"qty":"0.89","market_value_usd":"89.00"},
        "EEM":{"qty":"0.3","market_value_usd":"15.00"},
        "XLV":{"qty":"0.08","market_value_usd":"9.00"},
        "XLE":{"qty":"0.1","market_value_usd":"17.00"},
      },
      "open_orders":0,"order_history":{},
      "independent_t_plus_one_settlement_proven":False,
      "risk_metrics":{"daily_return":"0.002","drawdown":"-0.02","annual_volatility":"0.18"},
      "hypothetical_fee_buffers_usd":{"XLK":"0.10","XLE":"0.10","IWM":"0.10"},
    }

def assert_no_broker(r):
    assert r["broker_requests"]==r["broker_order_posts"]==0
    assert not r["new_live_order_release"]
    assert not r["live_buy_submitted"] and not r["live_sell_submitted"]
    assert not r["observed_broker_state_authenticated"]
    if r["candidate_instruction"]:
        assert r["candidate_instruction"]["executable"] is False
        assert r["candidate_instruction"]["client_order_id"].startswith("SIM-v6s1-")

def sell_fill(x,sym):
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="SYNTHETIC_CANDIDATE_LEGACY_SELL_NO_TRANSPORT",r
    a=r["candidate_instruction"]
    assert a["symbol"]==sym and a["side"]=="sell"
    assert a["qty"]==x["positions"][sym]["qty"]
    old=x["positions"].pop(sym)
    x["cash_usd"]=str(c.Decimal(x["cash_usd"])+c.Decimal(old["market_value_usd"]))
    x["order_history"][a["client_order_id"]]={
        "symbol":sym,"side":"sell","qty":a["qty"],"status":"filled"}
    # Treat actual sale proceeds as initially not T+1 settled.
    return a

def exited():
    x=fixture()
    ids=[sell_fill(x,s) for s in ("ACWI","EEM","XLV")]
    return x,ids

def fake_buy_fill(x,a):
    sym=a["symbol"];notional=c.Decimal(a["notional"])
    cost=c.Decimal(x["hypothetical_fee_buffers_usd"][sym])
    v=x["positions"].get(sym,{"qty":"0","market_value_usd":"0"})
    x["positions"][sym]={"qty":str(c.Decimal(v["qty"])+c.Decimal("0.01")),
                         "market_value_usd":str(c.Decimal(v["market_value_usd"])+notional)}
    x["cash_usd"]=str(c.Decimal(x["cash_usd"])-notional-cost)
    x["settled_cash_usd"]=x["cash_usd"]
    x["equity_usd"]=str(c.Decimal(x["equity_usd"])-cost)
    x["order_history"][a["client_order_id"]]={
      "symbol":sym,"side":"buy","notional":a["notional"],"status":"filled"}

def test_original_v5_overweight_acwi_can_be_risk_reducing_sell_candidate():
    x=fixture()
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="SYNTHETIC_CANDIDATE_LEGACY_SELL_NO_TRANSPORT"
    assert r["candidate_instruction"]["symbol"]=="ACWI"
    assert r["xle_original_overlap_retained"]
    assert_no_broker(r)

def test_restart_preserves_same_client_id_and_never_orders_again():
    x=fixture()
    a=c.assess(snap=x,now_utc=NOW)["candidate_instruction"]
    b=c.assess(snap=deepcopy(x),now_utc=NOW)["candidate_instruction"]
    assert a==b
    x["order_history"][a["client_order_id"]]={
      "symbol":"ACWI","side":"sell","qty":a["qty"],"status":"new"}
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="WAIT_OPEN_OR_PARTIAL_ORDER_RECONCILIATION"
    assert r["candidate_instruction"] is None
    assert_no_broker(r)

def test_three_sells_in_order_then_confirm_no_automatic_buy_without_settlement():
    x,ids=exited()
    assert [a["symbol"] for a in ids]==["ACWI","EEM","XLV"]
    assert set(x["positions"])=={"XLE"}
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="WAIT_ACTUAL_BROKER_SETTLEMENT_PROOF"
    assert r["xle_original_overlap_retained"]
    assert_no_broker(r)

def test_claimed_settlement_but_only_partial_settled_cash_blocks_buy():
    x,_=exited()
    x["independent_t_plus_one_settlement_proven"]=True
    x["settled_cash_usd"]="1.00"
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="WAIT_CASH_FLOOR_OR_SIZING_MINIMUM"
    assert_no_broker(r)

def test_sequential_buy_stages_and_cash_floor_investment_vignette():
    x,_=exited()
    x["independent_t_plus_one_settlement_proven"]=True
    x["settled_cash_usd"]=x["cash_usd"]
    candidates=[]
    for expected in ("XLK","IWM","XLE"):
        r=c.assess(snap=x,now_utc=NOW)
        assert r["stage"]=="SYNTHETIC_CANDIDATE_BUY_NO_TRANSPORT",r
        a=r["candidate_instruction"]
        assert a["symbol"]==expected
        assert a["side"]=="buy"
        assert c.Decimal(a["notional"])>=1
        assert c.Decimal(a["notional"])<=65
        assert c.Decimal(x["cash_usd"])-c.Decimal(a["notional"])-c.Decimal("0.10")>=c.Decimal(x["equity_usd"])*c.Decimal("0.05")
        assert a["client_order_id"]==c.candidate_id(expected,"buy")
        assert_no_broker(r)
        candidates.append(a)
        fake_buy_fill(x,a)
    assert set(x["positions"])=={"XLK","IWM","XLE"}
    end=c.assess(snap=x,now_utc=NOW)
    assert end["stage"]=="NO_NEW_ORDERS_PENDING_FRESH_TARGET_REVIEW",end
    assert end["candidate_instruction"] is None
    assert_no_broker(end)
    assert c.Decimal(x["cash_usd"])/c.Decimal(x["equity_usd"])>=c.Decimal(".05")
    assert all(a["executable"] is False for a in candidates)

def test_while_new_buy_receipt_pending_never_submits_second_order():
    x,_=exited()
    x["independent_t_plus_one_settlement_proven"]=True
    x["settled_cash_usd"]=x["cash_usd"]
    a=c.assess(snap=x,now_utc=NOW)["candidate_instruction"]
    x["order_history"][a["client_order_id"]]={
      "symbol":"XLK","side":"buy","notional":a["notional"],"status":"partially_filled"}
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="WAIT_OPEN_OR_PARTIAL_ORDER_RECONCILIATION"
    assert r["candidate_instruction"] is None
    assert_no_broker(r)

def test_filled_order_without_position_cannot_proceed():
    x,_=exited()
    x["independent_t_plus_one_settlement_proven"]=True
    x["settled_cash_usd"]=x["cash_usd"]
    a=c.assess(snap=x,now_utc=NOW)["candidate_instruction"]
    x["order_history"][a["client_order_id"]]={
      "symbol":"XLK","side":"buy","notional":a["notional"],"status":"filled"}
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="BLOCKED_FILLED_BUY_MISSING_POSITION"
    assert_no_broker(r)

def test_sell_filled_but_position_is_still_there_requires_reconciliation():
    x=fixture()
    cid=c.candidate_id("ACWI","sell")
    x["order_history"][cid]={"symbol":"ACWI","side":"sell",
        "qty":"0.89","status":"filled"}
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="BLOCKED_ORDER_FILLED_BUT_LEGACY_NOT_FLAT"

def test_legacy_missing_without_original_order_receipt_is_not_verified_flat():
    x=fixture()
    x["positions"].pop("ACWI")
    x["cash_usd"]="89.30"
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="BLOCKED_UNEXPLAINED_LEGACY_EXIT_WITH_NO_RECEIPT"

@pytest.mark.parametrize("bad",["partially_filled","canceled","rejected","replaced","expired","held"])
def test_existing_order_never_automatically_reposted_after_unsafe_status(bad):
    x=fixture()
    a=c.assess(snap=x,now_utc=NOW)["candidate_instruction"]
    x["order_history"][a["client_order_id"]]={
      "symbol":"ACWI","side":"sell","qty":a["qty"],"status":bad}
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"] in {"WAIT_OPEN_OR_PARTIAL_ORDER_RECONCILIATION",
                            "BLOCKED_TERMINAL_OR_UNSAFE_HISTORICAL_ORDER"}
    assert r["candidate_instruction"] is None
    assert_no_broker(r)

@pytest.mark.parametrize("metric,val",[
    ("daily_return","-0.06"),("daily_return","-0.08"),
    ("drawdown","-0.2"),("drawdown","-0.35"),
    ("annual_volatility","0.35001")])
def test_portfolio_stop_halts_all_candidate_orders(metric,val):
    x=fixture();x["risk_metrics"][metric]=val
    assert c.assess(snap=x,now_utc=NOW)["stage"]=="BLOCKED_ACCOUNT_RISK_STOP"

def test_xle_above_original_target_is_review_not_forced_xle_sell():
    x=fixture()
    x["positions"]["XLE"]["market_value_usd"]="40.00"
    x["positions"]["ACWI"]["market_value_usd"]="66.00"
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="REVIEW_ORIGINAL_XLE_OVERWEIGHT"
    assert not r["candidate_instruction"]

def test_nonzero_overstated_all_in_cost_blocks_new_buy():
    x,_=exited()
    x["independent_t_plus_one_settlement_proven"]=True
    x["settled_cash_usd"]=x["cash_usd"]
    x["hypothetical_fee_buffers_usd"]["XLK"]="999.00"
    r=c.assess(snap=x,now_utc=NOW)
    assert r["stage"]=="WAIT_CASH_FLOOR_OR_SIZING_MINIMUM"
    assert_no_broker(r)

@pytest.mark.parametrize("changes",[
    {"mode":"ALPACA_LIVE_GET_ONLY"},
    {"operator_stopped":False},
    {"kill_switch":"DISENGAGED"},
    {"old_v5_controller_active":True},
    {"risk_level":"LOW"},
    {"observed_at_utc":"2026-10-19T17:20:00Z"},
    {"observed_at_utc":"2026-10-19T17:31:00Z"},
    {"open_orders":-1},
    {"open_orders":True},
    {"cash_usd":"infinite"},
    {"equity_usd":"0"},
    {"settled_cash_usd":"1300"},
    {"positions":{"BTCUSD":{"qty":"1","market_value_usd":"120.00"}}},
    {"order_history":{"not-a-reviewed-id":{"symbol":"ACWI","side":"sell","qty":"1","status":"filled"}}},
    {"risk_metrics":{"daily_return":"NaN","drawdown":"-0.02","annual_volatility":"0.18"}},
    {"hypothetical_fee_buffers_usd":{"XLK":"0.10"}},
])
def test_forged_malformed_or_nonfake_snapshot_fails_closed(changes):
    x=fixture();x.update(changes)
    with pytest.raises(c.TransitionStop):
        c.assess(snap=x,now_utc=NOW)

def test_fake_client_ids_cannot_pass_original_live_writer_namespace():
    for sym in c.UNIVERSE:
        for side in ("buy","sell"):
            assert c.candidate_id(sym,side).startswith("SIM-")
            assert not c.candidate_id(sym,side).startswith("f100live-")

def test_actual_live_transport_is_permanently_disconnected():
    assert c.TRANSPORT_RELEASED is False
    assert c.PUBLIC_EXECUTION_ENABLED is False
    with pytest.raises(c.TransitionStop):
        c.release_transport()
    from pathlib import Path
    path=Path(c.__file__).read_text()
    for bad in ("urlopen(", "requests.post(", "httpx.post(", "ALPACA_LIVE_KEY", "/v2/orders"):
        assert bad not in path
