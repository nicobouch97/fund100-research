"""V6-S1 research-only staged migration controller; no broker/network imports.

This is a reusable deterministic decision CORE for future independently
source-authenticated production code. It requires IN_MEMORY_FAKE_BROKER_ONLY
input, returns NON-EXECUTABLE hypothetical candidate(s), and NEVER places
an Alpaca order. Public trading entry point ALWAYS raises.
"""
from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from hashlib import sha256

import fund100_v6_s1_low_churn_migration_v2_0 as previous

SCHEMA="FUND100_V6_S1_FAKE_BROKER_ORDER_CONTROLLER_SNAPSHOT_V1"
RESULT_SCHEMA="FUND100_V6_S1_STAGED_CONTROLLER_RESEARCH_ONLY_V1"
MIGRATION="FUND100-S1-ORIGINAL-20261019-V1"
OLD=("ACWI","EEM","XLV")
BUYS=("XLK","IWM","XLE")
UNIVERSE=frozenset(OLD+BUYS)
CAP=Decimal("130.30")
CASH_FLOOR=Decimal("0.05")
MAX_GROSS=Decimal("0.95")
MAX_SYMBOL=Decimal("0.50")
MIN_ORDER=Decimal("1.00")
MAX_ORDER=Decimal("65.00")
TARGETS={"XLK":Decimal("0.475"),"XLE":Decimal("0.285"),
         "IWM":Decimal("0.190")}
FINAL={"filled"}
ACTIVE={"new","accepted","pending_new","partially_filled",
        "pending_cancel","done_for_day","calculated"}
UNSAFE={"canceled","cancelled","expired","rejected","replaced",
        "pending_replace","suspended","held"}
CLOCK_AGE=300
TRANSPORT_RELEASED=False
PUBLIC_EXECUTION_ENABLED=False

class TransitionStop(ValueError):pass

def release_transport(*args,**kwargs):
    raise TransitionStop("V6-S1 actual LIVE execution transport not built or authorised")

def amount(raw,label,*,positive=False):
    if type(raw) not in (str,int,Decimal):
        raise TransitionStop(label+" must be source-consistent exact decimal")
    try:v=Decimal(str(raw))
    except (ValueError,InvalidOperation) as exc:
        raise TransitionStop("Invalid numeric "+label) from exc
    if not v.is_finite() or v<0 or (positive and v==0):
        raise TransitionStop("Negative/nonfinite/zero "+label)
    return v

def candidate_id(symbol,side):
    if symbol not in UNIVERSE or side not in {"buy","sell"}:
        raise TransitionStop("Unknown client-order identity")
    h=sha256((MIGRATION+"|"+side+"|"+symbol).encode()).hexdigest()[:20]
    return "SIM-v6s1-"+h+"-"+side[0]

def utc(v):
    if type(v) is not str:raise TransitionStop("Missing ISO UTC timestamp")
    try:d=datetime.strptime(v,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:raise TransitionStop("Noncanonical broker stamp") from exc
    if d.strftime("%Y-%m-%dT%H:%M:%SZ")!=v:
        raise TransitionStop("Noncanonical UTC source")
    return d

def blocked(state,*,reason=None,candidate=None,holdings=None,prior_orders=0):
    if candidate is not None:
        if candidate.get("executable") is not False:
            raise TransitionStop("Candidate cannot be executable")
    return {
        "schema":RESULT_SCHEMA,"stage":state,"reason":reason,
        "candidate_instruction":candidate,
        "candidate_is_nonexecutable":True,
        "observed_broker_state_authenticated":False,
        "proved_real_cash_settlement":False,
        "prior_fill_history_from_live_authenticated":False,
        "client_ids_stable_across_restarts":True,
        "xle_original_overlap_retained":bool(holdings is not None and "XLE" in holdings),
        "unresolved_orders_count":prior_orders,
        "original_live_capital_usd":"130.30",
        "new_live_order_release":False,"live_buy_submitted":False,
        "live_sell_submitted":False,"broker_requests":0,
        "broker_order_posts":0,
    }

def assess(*,snap:dict,now_utc:str)->dict:
    p=previous.policy()  # source-locked V2 draft + original V1 policy
    if p["may_place_buy_orders"] is not False or p["may_place_sell_orders"] is not False:
        raise TransitionStop("Current source research only")
    if (not isinstance(snap,dict)
        or snap.get("schema")!=SCHEMA
        or snap.get("mode")!="IN_MEMORY_FAKE_BROKER_ONLY"
        or snap.get("risk_level")!="HIGH"
        or snap.get("operator_stopped") is not True
        or snap.get("kill_switch")!="ENGAGED"
        or snap.get("old_v5_controller_active") is not False):
        raise TransitionStop("Broker inputs are not isolated synthetic STOPPED fixtures")
    delta=(utc(now_utc)-utc(snap.get("observed_at_utc"))).total_seconds()
    if delta<0 or delta>CLOCK_AGE:raise TransitionStop("Stale/future research snapshot")
    equity=amount(snap.get("equity_usd"),"equity",positive=True)
    cash=amount(snap.get("cash_usd"),"cash")
    settled=amount(snap.get("settled_cash_usd"),"spendable settled cash")
    if cash>equity or settled>cash:raise TransitionStop("Cash or settled cash exceeds equity")
    observed=snap.get("positions")
    if not isinstance(observed,dict) or not set(observed)<=UNIVERSE:
        raise TransitionStop("Unknown/missing holdings set")
    holdings={}
    for symbol,row in observed.items():
        if not isinstance(row,dict):raise TransitionStop("Malformed holdings")
        qty=amount(row.get("qty"),symbol+" fractional qty",positive=True)
        market=amount(row.get("market_value_usd"),symbol+" USD market value",positive=True)
        holdings[symbol]={"qty":qty,"market":market}
    gross=sum((v["market"] for v in holdings.values()),Decimal(0))
    if abs(gross+cash-equity)>Decimal(".02"):
        raise TransitionStop("Equity mismatch or unexplained assets")
    open_orders=snap.get("open_orders")
    if type(open_orders) is not int or open_orders<0:
        raise TransitionStop("Unreconciled existing open-order set")
    history=snap.get("order_history")
    if not isinstance(history,dict) or len(history)>6:
        raise TransitionStop("Original order ledger absent or malformed")
    for cid,row in history.items():
        if not isinstance(row,dict) or cid!=candidate_id(row.get("symbol"),row.get("side")):
            raise TransitionStop("Order ledger client ID, side or symbol mismatch")
        symbol,side=row["symbol"],row["side"]
        if (side=="sell" and symbol not in OLD) or (side=="buy" and symbol not in BUYS):
            raise TransitionStop("Invalid original migration order identity")
        state=row.get("status")
        if type(state) is not str or state not in FINAL|ACTIVE|UNSAFE:
            raise TransitionStop("Ambiguous order status; no resubmission")
        if side=="sell":
            if "qty" not in row or amount(row["qty"],"original order qty",positive=True)<=0:
                raise TransitionStop("Invalid recorded exit order qty")
        elif "notional" not in row or amount(row["notional"],"original buy notional",positive=True)<MIN_ORDER:
            raise TransitionStop("Invalid earlier buy notional")
    risk=snap.get("risk_metrics")
    if not isinstance(risk,dict) or set(risk)!={"daily_return","drawdown","annual_volatility"}:
        raise TransitionStop("Missing combined account-level risk history")
    # Preserve signed returns and drawdown without accepting float repr.
    def signed(k):
        v=risk.get(k)
        if type(v) not in (str,int,Decimal):raise TransitionStop("Invalid "+k)
        try:d=Decimal(str(v))
        except InvalidOperation as exc:raise TransitionStop("Invalid "+k) from exc
        if not d.is_finite():raise TransitionStop("Nonfinite "+k)
        return d
    daily=signed("daily_return");drawdown=signed("drawdown")
    vol=amount(risk["annual_volatility"],"annualized realized vol")
    if daily<=Decimal("-0.06") or drawdown<=Decimal("-0.20") or vol>Decimal("0.35"):
        return blocked("BLOCKED_ACCOUNT_RISK_STOP",holdings=holdings,
                       prior_orders=open_orders)
    if any(x["market"]/equity>MAX_SYMBOL for x in holdings.values()):
        return blocked("BLOCKED_SYMBOL_CONCENTRATION",holdings=holdings,prior_orders=open_orders)
    if gross/equity>MAX_GROSS and not set(holdings)&set(OLD):
        return blocked("BLOCKED_TOTAL_EXPOSURE",holdings=holdings,prior_orders=open_orders)
    if holdings.get("XLE",{}).get("market",Decimal(0)) > min(CAP,equity)*TARGETS["XLE"]:
        return blocked("REVIEW_ORIGINAL_XLE_OVERWEIGHT",holdings=holdings,prior_orders=open_orders)
    # Every existing order is source-matched before considering even another synthetic candidate.
    bad=[x for x in history.values() if x["status"] in UNSAFE]
    if bad:return blocked("BLOCKED_TERMINAL_OR_UNSAFE_HISTORICAL_ORDER",
                          holdings=holdings,prior_orders=open_orders)
    waiting=[x for x in history.values() if x["status"] in ACTIVE]
    if waiting or open_orders:
        return blocked("WAIT_OPEN_OR_PARTIAL_ORDER_RECONCILIATION",
                       holdings=holdings,prior_orders=open_orders)
    for sym in OLD:
        cid=candidate_id(sym,"sell")
        existing=history.get(cid)
        held=holdings.get(sym)
        if existing is not None and existing["status"]=="filled":
            if held is not None:
                return blocked("BLOCKED_ORDER_FILLED_BUT_LEGACY_NOT_FLAT",
                               holdings=holdings,prior_orders=open_orders)
        elif held is None:
            return blocked("BLOCKED_UNEXPLAINED_LEGACY_EXIT_WITH_NO_RECEIPT",
                           holdings=holdings,prior_orders=open_orders)
        else:
            intent={"client_order_id":cid,"symbol":sym,"side":"sell",
                    "qty":str(held["qty"]),"type":"market","time_in_force":"day",
                    "executable":False}
            return blocked("SYNTHETIC_CANDIDATE_LEGACY_SELL_NO_TRANSPORT",
                           candidate=intent,holdings=holdings,prior_orders=open_orders)
    # ALL three original SELL IDs filled and their positions actually flat.
    if set(holdings)&set(OLD):
        raise TransitionStop("Unreconciled legacy holdings after source ledger")
    if snap.get("independent_t_plus_one_settlement_proven") is not True:
        return blocked("WAIT_ACTUAL_BROKER_SETTLEMENT_PROOF",
                       holdings=holdings,prior_orders=open_orders)
    if cash/equity<CASH_FLOOR or gross/equity>MAX_GROSS:
        return blocked("WAIT_PASSIVE_CASH_OR_GROSS_DRIFT_NO_FORCED_SELL",
                       holdings=holdings,prior_orders=open_orders)
    quotes=snap.get("hypothetical_fee_buffers_usd")
    if not isinstance(quotes,dict) or set(quotes)!=set(BUYS):
        raise TransitionStop("All-in execution buffers must be sourced afresh")
    for sym in BUYS:amount(quotes[sym],sym+" projected all-in execution costs")
    target_nav=min(equity,CAP)
    if "XLK" in holdings and candidate_id("XLK","buy") not in history:
        return blocked("BLOCKED_UNEXPLAINED_NEW_ETF_POSITION",
                       holdings=holdings,prior_orders=open_orders)
    if "IWM" in holdings and candidate_id("IWM","buy") not in history:
        return blocked("BLOCKED_UNEXPLAINED_NEW_ETF_POSITION",
                       holdings=holdings,prior_orders=open_orders)
    for sym in BUYS:
        past=history.get(candidate_id(sym,"buy"))
        if past is not None:
            if past["status"]!="filled":
                raise TransitionStop("Prior BUY receipt not final")
            if sym not in holdings:
                return blocked("BLOCKED_FILLED_BUY_MISSING_POSITION",
                               holdings=holdings,prior_orders=open_orders)
            # A source-consistent filled order cannot be silently repeated.
            continue
        desired=target_nav*TARGETS[sym]-holdings.get(sym,{}).get("market",Decimal(0))
        if desired<MIN_ORDER:
            continue
        cost=amount(quotes[sym],sym+" full cost")
        cash_limit=min(cash,settled)-target_nav*CASH_FLOOR-cost
        exposure_limit=equity*MAX_GROSS-gross
        symbol_limit=equity*MAX_SYMBOL-holdings.get(sym,{}).get("market",Decimal(0))
        size=min(desired,MAX_ORDER,cash_limit,exposure_limit,symbol_limit)
        size=size.quantize(Decimal("0.01"),rounding=ROUND_DOWN)
        if size<MIN_ORDER:
            return blocked("WAIT_CASH_FLOOR_OR_SIZING_MINIMUM",
                           holdings=holdings,prior_orders=open_orders)
        if cash-size-cost<equity*CASH_FLOOR or settled-size-cost<equity*CASH_FLOOR:
            raise TransitionStop("Cash floor could be violated by candidate")
        return blocked("SYNTHETIC_CANDIDATE_BUY_NO_TRANSPORT",
                       candidate={"client_order_id":candidate_id(sym,"buy"),
                         "symbol":sym,"side":"buy","notional":str(size),"type":"market",
                         "time_in_force":"day","executable":False},
                       holdings=holdings,prior_orders=open_orders)
    return blocked("NO_NEW_ORDERS_PENDING_FRESH_TARGET_REVIEW",
                   holdings=holdings,prior_orders=open_orders)
