"""Original first ACWI sell: real GET-derived ACTIVE HIGH source V2 (HARD LOCKED).

This is a tightly scoped *sell-only* pretrade gate, not a new order writer.
Unlike the original V1 read-only risk source, this version requires the
CURRENT operator to be RUNNING and the broker emergency stop disengaged. It
does not change the original stopped V5 historical evidence. No executable
entrypoint, no broker POST, no credential/log persistence.

Default ACTIVE_HIGH_SELL_SOURCE_RELEASED=False makes all active broker
reads unreachable. A separately reviewed release and protected workflow
must explicitly select this version; historical STOP-only V1 remains intact.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import os

import fund100_alpaca_live_readonly_smoke as broker
import fund100_live_operator_control_v1_0 as operator
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as four
import fund100_v6_s1_live_risk_history_getonly_v1_0 as five
import fund100_v6_s1_live_private_xle_activity_getonly_v1_0 as six
import fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 as seven
import fund100_v6_s1_live_cashflow_risk_bounds_v1_0 as cashrisk
import fund100_v6_s1_independent_high_exante_policy_v1_0 as limits

SCHEMA="FUND100_V6_S1_ACTIVE_HIGH_FIRST_ACWI_SELL_ORDER_TIME_RISK_V2"
ACTIVE_HIGH_SELL_SOURCE_RELEASED=False
NO_BROKER_POST=True
SYMBOL="ACWI"
ORIGINAL_POSITIONS=frozenset(("ACWI","EEM","XLE","XLV"))

class ActiveSellStop(RuntimeError):
    pass

def _money(raw,*,zero=False):
    try:
        x=original.positive(raw,"private broker money",allow_zero=zero)
    except Exception:
        raise ActiveSellStop("Untrusted broker currency or share value") from None
    return x

def _scope():
    if (ACTIVE_HIGH_SELL_SOURCE_RELEASED is not True
        or os.getenv("GITHUB_ACTIONS")!="true"
        or os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("GITHUB_EVENT_NAME")!="workflow_dispatch"
        or os.getenv("GITHUB_RUN_ATTEMPT")!="1"
        or os.getenv("FUND100_RISK_LEVEL")!="HIGH"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="DISENGAGED"
        or os.getenv("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"):
        raise ActiveSellStop("First original ACTIVE sell-only HIGH source HARD LOCKED")
    try:
        if operator.validate_control(operator.read_current_control()) is not True:
            raise ActiveSellStop("Current LIVE operator not enabled")
        broker.require_readonly_arm()
    except Exception:
        raise ActiveSellStop("LIVE operator or broker GET eligibility unavailable") from None

def evaluate_original_sell_only(*,account,positions,orders,clock,history,
                                activities,native_none_history,bootstrap,
                                original_policy,original_qty,observed_at_utc):
    """Review the actual seven GET objects. Never accept a cached redacted GO.

    Original bootstrap/policy are historical signed evidence, not current
    operator instructions. Must be followed by another authenticated current
    operator check, including immediately at the reviewed writer boundary.
    """
    try:
        original_fills=original.check_original(
            bootstrap,original_policy,
            {"schema":original.CONTROL_SCHEMA,"trading_enabled":False})
        if (set(original_fills)!=ORIGINAL_POSITIONS
            or original_policy.get("capital_ceiling_usd")!="130.30"
            or original_policy.get("leverage_allowed") is not False
            or original_policy.get("shorting_allowed") is not False
            or original_policy.get("additional_deposits_automatically_usable") is not False):
            raise ActiveSellStop("Original V5 cap and historical fill provenance changed")
        if (type(account) is not dict or type(positions) is not list
            or type(orders) is not list or orders or len(positions)!=4
            or type(clock) is not dict or type(activities) is not list):
            raise ActiveSellStop("Original account, open orders or 4 positions invalid")
        if (account.get("status")!="ACTIVE"
            or account.get("account_blocked") is True
            or account.get("trading_blocked") is True
            or str(account.get("multiplier"))!="1"
            or type(account.get("id")) is not str
            or not account["id"].strip()):
            raise ActiveSellStop("Broker account not active, unblocked, cash only")
        bound=sha256(("FUND100-LIVE-ACCOUNT|"+account["id"].strip()).encode()).hexdigest()
        if bound!=original_policy.get("account_binding_sha256"):
            raise ActiveSellStop("Broker account binding changed")
        import fund100_v6_s1_fresh_acwi_order_time_risk_getonly_v1_0 as baseline
        baseline._fresh_clocks(
            clock=clock,observed=baseline._utc(observed_at_utc,"broker acquisition"))
        wanted=baseline._qty(original_qty)
        if wanted!=original_fills[SYMBOL]:
            raise ActiveSellStop("Proposed ACWI quantity not original historical fill")
        by_symbol={}
        gross=Decimal(0)
        for item in positions:
            if type(item) is not dict:
                raise ActiveSellStop("Malformed current brokerage position")
            name=item.get("symbol")
            if name not in ORIGINAL_POSITIONS or name in by_symbol:
                raise ActiveSellStop("Changed brokerage positions/duplicate symbol")
            qty=baseline._qty(item.get("qty"))
            price=_money(item.get("current_price"))
            value=_money(item.get("market_value"))
            if (qty!=original_fills[name]
                or abs(value-qty*price)>max(Decimal(".03"),value*Decimal(".01"))):
                raise ActiveSellStop("Current original holdings no longer reconcile")
            gross+=value
            by_symbol[name]=(qty,value)
        if set(by_symbol)!=ORIGINAL_POSITIONS or by_symbol[SYMBOL][0]!=wanted:
            raise ActiveSellStop("Current original full ACWI holding not available")
        cash=_money(account.get("cash"),zero=True)
        equity=_money(account.get("equity"))
        if abs(equity-cash-gross)>max(Decimal("1.00"),equity*Decimal(".02")):
            raise ActiveSellStop("Cash/equity/holdings no longer reconcile")
        # First ACWI is a SELL; no new buys, leverage, excess deposits,
        # wash sale consideration, or unsettled sale proceeds are authorized.
        if by_symbol[SYMBOL][1]>limits.MAX_ORDER:
            raise ActiveSellStop("Full original ACWI sell exceeds $65 order cap")
        if (len(activities)>=100
            or sum(row.get("activity_type")=="CSD" for row in activities
                   if type(row) is dict)!=1
            or any(type(row) is not dict for row in activities)):
            raise ActiveSellStop("Original account funding source not singly qualified")
        deposits=[
            cashrisk._decimal(row.get("net_amount"))
            for row in activities if row["activity_type"]=="CSD"]
        if len(deposits)!=1 or not Decimal(0)<deposits[0]<=limits.CAP:
            raise ActiveSellStop("Original authorized $130.30 funded capital breached")
        # Apply unchanged authenticated 6% daily / 20% drawdown /
        # 35% volatility risk guard to the actual 1M funded equity history.
        # This proof itself is categorical historical equity risk, and does
        # not establish strategy returns or a future account-risk permit.
        status=cashrisk.inspect(
            history=history,activities=activities,account=account,
            observed_at_utc=observed_at_utc)
        if (status.get("schema")!=cashrisk.STATUS_SCHEMA
            or status.get("strictly_postfunding_account_6_20_35_source_verified") is not True
            or status.get("source_rejection_category")!="NONE"):
            raise ActiveSellStop("Fresh cashflow-sensitive HIGH risk 6/20/35 HOLD")
        if (type(native_none_history) is not dict
            or seven.broker_native_none_source(history,native_none_history)
               in ("BROKER_NATIVE_NONE_TIME_SERIES_NOT_COMPARABLE",
                   "BROKER_NATIVE_NONE_PNL_SERIES_MISSING_OR_UNCOMPARABLE")):
            raise ActiveSellStop("Second original portfolio-history source not comparable")
    except ActiveSellStop:
        raise
    except Exception:
        raise ActiveSellStop("Actual original broker HIGH sell source inadmissible") from None
    return {
        "schema":SCHEMA,
        "status":"ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2",
        "same_process_real_broker_gets":7,
        "original_acwi_exact_fractional_holdings_verified":True,
        "original_open_market_and_no_pending_order_verified":True,
        "original_strict_postfunding_6_20_35_risk_pass":True,
        "sell_only_original_legacy_ACWI":True,
        "capital_ceiling_usd":"130.30",
        "max_single_sell_notional_usd":"65.00",
        "broker_order_authorized":True,
        "broker_post_attempts":0,
        "orders_submitted_here":0,
        "buy_authorized":False,
        "settled_cash_verified":False,
        "account_id":None,"account_equity":None,
        "holdings":None,"activities":None,
        "original_qty":None,"broker_secrets":None,
    }

def inspect_active_original_acwi_sell(*,original_qty:str,key:str,secret:str)->dict:
    """Seven actual Alpaca GETs in exactly the same final writer process."""
    _scope()
    approved=(
        ("/v2/account",None),("/v2/positions",None),
        ("/v2/orders",{"status":"open","limit":100}),
        ("/v2/clock",None),
        (five.HISTORY_PATH,five.HISTORY_PARAMS),
        (six.ACTIVITIES_PATH,six.ACTIVITY_PARAMS),
        (five.HISTORY_PATH,seven.EXTRA_PARAMS))
    if tuple(p for p,_ in approved)!=seven.PATHS:
        raise ActiveSellStop("Original 7GET source endpoints changed")
    docs=[]
    for path,params in approved:
        try:
            docs.append(broker.get_json(
                path=path,params=params,key=key,secret=secret))
        except Exception:
            raise ActiveSellStop("Actual broker read timed out or unavailable; HOLD") from None
    _scope()  # Current main operator and kill switch checked AGAIN after GET.
    boots,_=original.original(four.BOOT)
    old_policy,_=original.original(four.POLICY)
    now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return evaluate_original_sell_only(
        account=docs[0],positions=docs[1],orders=docs[2],clock=docs[3],
        history=docs[4],activities=docs[5],native_none_history=docs[6],
        bootstrap=boots,original_policy=old_policy,
        original_qty=original_qty,observed_at_utc=now)
