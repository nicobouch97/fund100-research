"""Synthetic, offline-only V6-S1 transition tests. NO customer account data."""
import copy
import json
from pathlib import Path
import pytest
import fund100_v6_s1_transition_staging_v1_0 as t

PROPOSAL={
 "schema":t.PROPOSAL_SCHEMA,"status":"PROPOSED_NOT_LIVE",
 "strategy_id":"V6_S1_FIXED_SECTOR_RISK_PREMIUM",
 "original_trial_max_capital_usd":"130.30",
 "target_weights":{"XLK":"0.475","XLE":"0.285","IWM":"0.190"},
 "cash_reserve_fraction":"0.05","maximum_gross_exposure":"0.95",
 "live_order_execution_released":False,"live_operator_trading_enabled":False,
 "live_environment_kill_switch":"ENGAGED","allow_margin":False,
 "allow_leverage":False,"allow_new_deposits":False}
STOP={"schema":"FUND100_OPERATOR_CONTROL_V1","trading_enabled":False}
BINDING="a"*64

def input_snapshot():
 return {
  "schema":t.SNAPSHOT_SCHEMA,"mode":"ALPACA_LIVE_GET_ONLY",
  "request_methods":["GET"]*4,"request_paths":sorted(t.EXPECTED_PATHS),
  "orders_submitted":0,"account_binding_sha256":BINDING,
  "observed_at_utc":"2026-10-19T15:00:00Z",
  "account":{"status":"ACTIVE","trading_blocked":False,"equity":"121.75",
             "cash":"0.50","buying_power":"0.50"},
  "clock":{"is_open":True},"open_orders":[],
  "positions":[{"symbol":s,"qty":"0.01","market_value":"25"}
               for s in sorted(t.OLD)],
 }

def review(x=None,**kwargs):
 return t.review(snapshot=x if x is not None else input_snapshot(),proposal=PROPOSAL,operator=STOP,
    expected_account_binding_sha256=BINDING,
    now_utc="2026-10-19T15:00:20Z",**kwargs)

def test_exact_repository_proposal_and_stop_contract():
 root=Path(__file__).resolve().parent
 orig=json.loads((root/"research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json").read_text())
 for k,v in PROPOSAL.items():
  assert orig[k]==v
 assert json.loads((root/"fund100_live_operator_control.json").read_text())==STOP

def test_legacy_hold_is_sanitized_and_never_an_order():
 result=review()
 assert result["stage"]=="LEGACY_FOUR_STILL_HELD_NO_SELL"
 assert result["legacy_positions_present"]==4
 assert result["sell_orders"]==result["buy_orders"]==result["broker_requests"]==0
 assert result["executable_order_payload"] is None
 assert "121.75" not in str(result) and "0.01" not in str(result)
 assert not result["new_live_orders_authorized"]

@pytest.mark.parametrize("change",[
 ("orders_submitted",1),("mode","ALPACA_PAPER"),
 ("request_methods",["GET","GET","POST","GET"]),
 ("account_binding_sha256","b"*64),
 ("observed_at_utc","2026-10-19T14:50:00Z")])
def test_invalid_get_provenance_refused(change):
 x=input_snapshot();x[change[0]]=change[1]
 with pytest.raises(t.StageStop):review(x)

@pytest.mark.parametrize("symbol,quantity",[("BTC","0.1"),("XLK","0.01"),("EEM","-1")])
def test_unknown_new_or_short_holdings_do_not_pass(symbol,quantity):
 x=input_snapshot();x["positions"]=[{"symbol":symbol,"qty":quantity,"market_value":"25"}]
 with pytest.raises(t.StageStop):review(x)

def test_open_or_partial_order_state_is_never_ready():
 x=input_snapshot();x["open_orders"]=[{"id":"mock"}]
 assert review(x)["stage"]=="BLOCKED_OPEN_BROKER_ORDERS"
 x=input_snapshot();x["positions"]=x["positions"][:2]
 assert review(x)["stage"]=="PARTIAL_LEGACY_EXIT_MANUAL_RECONCILIATION"

def test_empty_holdings_go_through_real_paper_then_settlement_then_risk():
 x=input_snapshot();x["positions"]=[]
 x["account"]["cash"]="121.75";x["account"]["buying_power"]="121.75"
 assert review(x)["stage"]=="AWAIT_S1_REAL_PAPER_FILL_MECHANICS"
 assert review(x,paper_round_trip_verified=True)["stage"]=="AWAIT_INDEPENDENT_T_PLUS_ONE_SETTLEMENT_PROOF"
 assert review(x,paper_round_trip_verified=True,independent_settlement_proof=True)["stage"]=="AWAIT_FRESH_ACCOUNT_RISK_MEASUREMENTS"
 r={"daily_return":"-0.02","peak_drawdown":"-0.10","annualized_volatility":"0.20"}
 result=review(x,paper_round_trip_verified=True,independent_settlement_proof=True,risk_measurements=r)
 assert result["stage"]=="MECHANICALLY_PLAUSIBLE_NO_ORDER_RELEASE"
 assert not result["strategy_alpha_established"] and not result["new_live_orders_authorized"]
 x["clock"]["is_open"]=False
 assert review(x,paper_round_trip_verified=True,independent_settlement_proof=True,risk_measurements=r)["stage"]=="AWAIT_REGULAR_MARKET_SESSION"

@pytest.mark.parametrize("risk",[
 {"daily_return":"-0.06","peak_drawdown":"-0.10","annualized_volatility":"0.20"},
 {"daily_return":"0.01","peak_drawdown":"-0.20","annualized_volatility":"0.20"},
 {"daily_return":"0.01","peak_drawdown":"-0.10","annualized_volatility":"0.351"}])
def test_frozen_account_stop_boundaries(risk):
 x=input_snapshot();x["positions"]=[]
 x["account"]["cash"]="121.75";x["account"]["buying_power"]="121.75"
 assert review(x,paper_round_trip_verified=True,independent_settlement_proof=True,risk_measurements=risk)["stage"]=="BLOCKED_ACCOUNT_LOSS_OR_VOLATILITY_STOP"

def test_no_usable_cash_even_if_other_flags_true():
 x=input_snapshot();x["positions"]=[]
 r={"daily_return":"-0.02","peak_drawdown":"-0.1","annualized_volatility":"0.2"}
 assert review(x,paper_round_trip_verified=True,independent_settlement_proof=True,risk_measurements=r)["stage"]=="BLOCKED_UNFUNDED_SETTLED_CASH_TARGET"

def test_no_silent_release_through_control_or_manifest():
 x=input_snapshot()
 bad=copy.deepcopy(PROPOSAL);bad["live_order_execution_released"]=True
 with pytest.raises(t.StageStop):t.review(snapshot=x,proposal=bad,operator=STOP,
     expected_account_binding_sha256=BINDING,now_utc="2026-10-19T15:00:20Z")
 bad_stop={**STOP,"trading_enabled":True}
 with pytest.raises(t.StageStop):t.review(snapshot=x,proposal=PROPOSAL,operator=bad_stop,
     expected_account_binding_sha256=BINDING,now_utc="2026-10-19T15:00:20Z")

@pytest.mark.parametrize("bad",["NaN","Infinity","-1","1e1000000"])
def test_broker_cash_and_position_nonfinite_rejected(bad):
 x=input_snapshot();x["account"]["cash"]=bad
 with pytest.raises(t.StageStop):review(x)

def test_bad_risk_metric_rejected():
 x=input_snapshot();x["positions"]=[]
 x["account"]["cash"]="121.75";x["account"]["buying_power"]="121.75"
 with pytest.raises(t.StageStop):review(x,paper_round_trip_verified=True,
     independent_settlement_proof=True,risk_measurements={"daily_return":"NaN","peak_drawdown":"0","annualized_volatility":"0"})
