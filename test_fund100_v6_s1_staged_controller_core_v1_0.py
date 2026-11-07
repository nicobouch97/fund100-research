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
      "risk_metrics":{"daily_return":"0.002","drawdown":"-0.02","annual_volatility":"0.18",
                      "drawdown_basis":c.RISK_BASIS},
      "hypothetical_fee_buffers_usd":{"XLK":"0.10","XLE":"0.10","IWM":"0.10"},
    }

def assert_no_broker(r):
    assert r["broker_requests"]==r["broker_order_posts"]==0
    assert not r["new_live_order_release"]
    assert not r["live_buy_submitted"] and not r["live_sell_submitted"]
    assert not r["observed_broker_state_authenticated"]
    if r["candidate_instruction"]:
        assert r["candidate_instruction"]["executable"] is False
        intent=r["candidate_instruction"]
        if intent["side"]=="sell":
            assert intent["client_order_id"]==c.original_cas.CLIENT_IDS[intent["symbol"]]
        else:
            assert intent["client_order_id"].startswith("SIM-v6s1-")

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

def test_original_three_legacy_sell_ids_are_identical_to_signed_private_cas():
    assert tuple(c.original_cas.LEGACY)==c.OLD
    for symbol in c.OLD:
        assert c.candidate_id(symbol,"sell")==c.original_cas.CLIENT_IDS[symbol]
        assert c.candidate_id(symbol,"sell").startswith("f100v6s1-")
    for symbol in c.BUYS:
        assert c.candidate_id(symbol,"buy").startswith("SIM-v6s1-")
    for invalid in ("XLK","IWM"):
        with pytest.raises(c.TransitionStop):
            c.candidate_id(invalid,"sell")
    for invalid in ("ACWI","EEM","XLV"):
        with pytest.raises(c.TransitionStop):
            c.candidate_id(invalid,"buy")


def test_real_original_acwi_signed_fill_and_flat_source_advances_to_eem_no_resell():
    x=fixture()
    original_acwi=c.original_cas.CLIENT_IDS["ACWI"]
    x["cash_usd"]="89.30"
    x["positions"].pop("ACWI")
    x["order_history"][original_acwi]={
        "symbol":"ACWI","side":"sell","qty":"0.89","status":"filled"}
    evidence=c.assess(snap=x,now_utc=NOW)
    assert evidence["stage"]=="SYNTHETIC_CANDIDATE_LEGACY_SELL_NO_TRANSPORT"
    assert evidence["candidate_instruction"]["symbol"]=="EEM"
    assert evidence["candidate_instruction"]["client_order_id"]==c.original_cas.CLIENT_IDS["EEM"]
    assert_no_broker(evidence)


def test_fake_or_forged_original_acwi_id_cannot_count_as_reconciled_fill():
    x=fixture()
    x["cash_usd"]="89.30"
    x["positions"].pop("ACWI")
    x["order_history"]["SIM-v6s1-fake-s"]={
        "symbol":"ACWI","side":"sell","qty":"0.89","status":"filled"}
    with pytest.raises(c.TransitionStop,match="client ID"):
        c.assess(snap=x,now_utc=NOW)


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

@pytest.mark.parametrize("metric,value",[
    ("daily_return","0.251"), ("daily_return","-0.251"),
    ("drawdown","0.01"), ("drawdown","-1.01"),
    ("drawdown","Infinity"), ("daily_return","-Infinity"),
    ("annual_volatility","-0.01"),
])
def test_ambiguous_or_impossible_account_risk_fails_closed(metric,value):
    x=fixture()
    x["risk_metrics"][metric]=value
    with pytest.raises(c.TransitionStop):
        c.assess(snap=x,now_utc=NOW)


@pytest.mark.parametrize("wrong",[
    "LIFETIME_BACKTEST_MAX_DRAWDOWN",
    "PORTFOLIO_1Y_PEAK_TO_TROUGH",
    "UNADJUSTED_BROKER_1M_HISTORY",
    "BROKER_1M_DAILY_ACCOUNT_EQUITY_PEAK_TO_CURRENT_WRONG",
    "",None,True,
])
def test_backtest_drawdown_cannot_substitute_for_account_circuit_breaker(wrong):
    x=fixture()
    x["risk_metrics"]["drawdown_basis"]=wrong
    with pytest.raises(c.TransitionStop,match="trailing 1M"):
        c.assess(snap=x,now_utc=NOW)


def test_missing_risk_timeframe_is_not_assumed():
    x=fixture()
    del x["risk_metrics"]["drawdown_basis"]
    with pytest.raises(c.TransitionStop,match="trailing 1M"):
        c.assess(snap=x,now_utc=NOW)


@pytest.mark.parametrize("field,value,expected_reason",[
    ("daily_return","-0.060","DAILY_ACCOUNT_LOSS_6PCT"),
    ("drawdown","-0.200","BROKER_TRAILING_1M_ACCOUNT_DRAWDOWN_20PCT"),
    ("annual_volatility","0.351","ANNUALIZED_REALIZED_ACCOUNT_VOLATILITY_35PCT"),
])
def test_risk_stop_reason_is_specific_but_never_liquidates_or_autorestarts(
    field,value,expected_reason
):
    x=fixture()
    x["risk_metrics"][field]=value
    out=c.assess(snap=x,now_utc=NOW)
    assert out["stage"]=="BLOCKED_ACCOUNT_RISK_STOP"
    assert out["reason"]==expected_reason
    assert out["candidate_instruction"] is None
    assert_no_broker(out)


def test_20pct_lifetime_historical_drawdown_not_automatically_1month_breach():
    # The new source label states that THIS metric is a 1M broker-account
    # reading; full-history strategy DD is a different statistic.
    x=fixture()
    x["risk_metrics"]["drawdown"]="-0.19"
    x["risk_metrics"]["daily_return"]="-0.059"
    x["risk_metrics"]["annual_volatility"]="0.35"
    out=c.assess(snap=x,now_utc=NOW)
    assert out["stage"]=="SYNTHETIC_CANDIDATE_LEGACY_SELL_NO_TRANSPORT"
    assert_no_broker(out)


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
])
def test_forged_malformed_or_nonfake_snapshot_fails_closed(changes):
    x=fixture();x.update(changes)
    with pytest.raises(c.TransitionStop):
        c.assess(snap=x,now_utc=NOW)

def test_signed_original_sell_ids_are_reused_but_buy_ids_stay_fake():
    for sym in c.OLD:
        cid=c.candidate_id(sym,"sell")
        assert cid==c.original_cas.CLIENT_IDS[sym]
        assert not cid.startswith("SIM-")
    for sym in c.BUYS:
        cid=c.candidate_id(sym,"buy")
        assert cid.startswith("SIM-")
        assert not cid.startswith("f100v6s1-")
    assert c.TRANSPORT_RELEASED is False
    assert c.PUBLIC_EXECUTION_ENABLED is False

def test_actual_live_transport_is_permanently_disconnected():
    assert c.TRANSPORT_RELEASED is False
    assert c.PUBLIC_EXECUTION_ENABLED is False
    with pytest.raises(c.TransitionStop):
        c.release_transport()
    from pathlib import Path
    path=Path(c.__file__).read_text()
    for bad in ("urlopen(", "requests.post(", "httpx.post(", "ALPACA_LIVE_KEY", "/v2/orders"):
        assert bad not in path


def test_missing_all_in_fee_quotes_are_rejected_exactly_when_buy_stage_arrives():
    x,_=exited()
    x["independent_t_plus_one_settlement_proven"]=True
    x["settled_cash_usd"]=x["cash_usd"]
    x["hypothetical_fee_buffers_usd"]={"XLK":"0.10"}
    with pytest.raises(c.TransitionStop):
        c.assess(snap=x,now_utc=NOW)


def test_original_protected_live_broker_report_routes_to_staged_stop_without_synthetic_candidate():
    from test_fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 import scenario
    from fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 import evaluate
    actual_shape=evaluate(**scenario())
    out=c.assess_stopped_live_readiness(source_report=actual_shape)
    assert out["stage"]=="BLOCKED_UNPROVEN_CASHFLOW_ADJUSTED_1M_ACCOUNT_RISK"
    assert out["candidate_instruction"] is None
    assert out["new_live_order_release"] is False
    assert out["live_seven_get_report_shape_checked"]
    assert out["live_broker_source_authenticated_by_this_pure_module"] is False
    assert out["broker_requests"]==out["broker_order_posts"]==0


@pytest.mark.parametrize("change",[
    {"broker_get_requests":6},{"broker_get_requests":True},
    {"broker_non_get_requests":1},{"live_orders":1},
    {"live_buy_sell_authorized":True},
    {"actual_sale_proceeds_t_plus_one_settled":True},
    {"actual_cashflow_adjusted_dietz_returns_calculated":True},
    {"source":"IN_MEMORY_FAKE_BROKER_ONLY"},
    {"one_month_date_only_cashflow_risk_status":None},
])
def test_live_staged_routing_rejects_broker_provenance_or_order_change(change):
    from test_fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 import scenario
    from fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 import evaluate
    source=evaluate(**scenario())
    source.update(change)
    with pytest.raises(c.TransitionStop):
        c.assess_stopped_live_readiness(source_report=source)


def test_even_claimed_live_account_risk_pass_cannot_bypass_missing_ledger_join():
    from test_fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 import scenario
    from fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 import evaluate
    source=evaluate(**scenario())
    source["actual_s1_6_20_35_risk_verified"]=True
    out=c.assess_stopped_live_readiness(source_report=source)
    assert out["stage"]=="BLOCKED_NO_INDEPENDENT_SIGNED_LEDGER_AND_SETTLEMENT_JOIN"
    assert out["candidate_instruction"] is None and not out["new_live_order_release"]


def test_staged_live_path_does_not_accept_real_account_values_as_simulation():
    from test_fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 import scenario
    from fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 import evaluate
    source=evaluate(**scenario())
    with pytest.raises(c.TransitionStop):
        c.assess(snap=source,now_utc=NOW)
