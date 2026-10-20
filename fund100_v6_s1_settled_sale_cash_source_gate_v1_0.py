"""V6-S1 *synthetic-only* post-sale settlement + private cash evidence gate.

Trading account cash can increase at sale fill, prior to T+1 settlement.
Never assume cash or buying power proves settled proceeds. If the actual
Trading API lacks broker cash_withdrawable/transferable, it must STOP.
No HTTP, broker credentials, PRIVATE state access or executable BUY.
"""
from __future__ import annotations

from datetime import date, datetime,timezone
from decimal import Decimal,InvalidOperation
from zoneinfo import ZoneInfo

import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as orders
import fund100_v6_s1_independent_high_exante_policy_v1_0 as policy

SCHEMA="FUND100_V6_S1_SYNTHETIC_SETTLED_SALE_CASH_EVIDENCE_V1"
MODE="INVENTED_SETTLEMENT_AND_ACCOUNT_FIXTURES_ONLY"
ALLOWED_ORIGINAL=("ACWI","EEM","XLV","XLE")
ACCOUNT_SETTLED_FIELDS=("cash_withdrawable","cash_transferable")
MAX_SNAPSHOT_AGE_SECONDS=300
ALLOWED_SETTLEMENT_LOOKBACK_SESSIONS=12
RELEASE_LIVE_BUY=False

class SettlementStop(ValueError):pass

def _d(value,label,*,positive=False):
    if type(value) not in (str,int,Decimal):raise SettlementStop("Missing exact "+label)
    try:x=Decimal(str(value))
    except (InvalidOperation,ValueError):raise SettlementStop("Bad "+label) from None
    if not x.is_finite() or x<0 or (positive and x==0):
        raise SettlementStop("Invalid amount for "+label)
    return x

def _at(value):
    if type(value) is not str or not value.endswith("Z"):
        raise SettlementStop("Missing source UTC stamp")
    try:dt=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError:raise SettlementStop("Malformed source UTC stamp") from None
    if dt.utcoffset()!=timezone.utc.utcoffset(dt):
        raise SettlementStop("Non-UTC broker timestamp")
    return dt

def _date(value):
    if type(value) is not str or len(value)!=10:
        raise SettlementStop("Missing calendar date")
    try:d=date.fromisoformat(value)
    except ValueError:raise SettlementStop("Bad trading settlement date") from None
    if d.isoformat()!=value or d.weekday()>4:
        raise SettlementStop("Invalid stock-settlement business date")
    return d

def _summary(stage):
    return {"schema":SCHEMA,"stage":stage,
        "source_mode":MODE,
        "original_xle_sold":False,
        "genuine_broker_cash_settlement_proven":False,
        "actual_trading_api_settled_cash_field_supported":False,
        "original_three_live_exit_receipts_authenticated":False,
        "private_attempts_offhost_anchored":False,
        "account_loss_drawdown_actual_vol_verified":False,
        "broker_fields_measured_by_this_code":False,
        "live_buy_authorized":False,"live_sell_authorized":False,
        "broker_requests":0,"broker_order_posts":0,
        "actual_cash":None,"account_id":None,"share_quantities":None,
        "sell_order_receipts":None,"executable_order":None}

def evaluate(*,snap:dict,now_utc:str)->dict:
    """Source-shaped private snapshots; *ONLY invented fixtures* accepted.

    The positive result NEVER certifies authentic broker settlement.
    """
    policy.contract()
    if (type(snap) is not dict
        or snap.get("mode")!=MODE
        or snap.get("source_authenticated_live") is not False
        or snap.get("risk_level")!="HIGH"
        or snap.get("operator_stopped") is not True
        or snap.get("kill_switch")!="ENGAGED"
        or snap.get("old_v5_live_execution_enabled") is not False
        or snap.get("settlement_calendar_authenticated") is not False):
        raise SettlementStop("Only HIGH/STOPPED invented source-bound fixtures")
    before=snap.get("before_account")
    after=snap.get("after_account")
    original=snap.get("before_positions")
    current=snap.get("after_positions")
    receipts=snap.get("original_exit_receipts")
    if (type(before) is not dict or type(after) is not dict
        or type(original) is not dict or type(current) is not dict
        or type(receipts) is not dict):
        raise SettlementStop("Missing account and full exit ledger")
    if (type(before.get("id")) is not str or not before["id"]
        or after.get("id")!=before["id"]
        or before.get("status")!="ACTIVE" or after.get("status")!="ACTIVE"
        or before.get("account_blocked") is not False
        or after.get("account_blocked") is not False
        or before.get("trading_blocked") is not False
        or after.get("trading_blocked") is not False):
        raise SettlementStop("Account binding or active/nonblocked status changed")
    seen_at=_at(snap.get("after_account_observed_at_utc"))
    now=_at(now_utc)
    freshness=(now-seen_at).total_seconds()
    if freshness<0 or freshness>MAX_SNAPSHOT_AGE_SECONDS:
        raise SettlementStop("Source after-account snapshot is stale/future")
    if (type(snap.get("unreconciled_open_orders")) is not int
        or snap["unreconciled_open_orders"]!=0
        or type(snap.get("unreconciled_nontrade_activities")) is not int
        or snap["unreconciled_nontrade_activities"]!=0
        or snap.get("nontrade_activity_history_complete") is not True):
        return _summary("BLOCKED_UNKNOWN_ORDER_OR_CASHFLOW_HISTORY")
    if (set(original)!=set(ALLOWED_ORIGINAL)
        or set(current)!={"XLE"} or set(receipts)!=set(orders.LEGACY_TO_EXIT)):
        raise SettlementStop("Legacy holdings/sale ledger missing or original XLE not retained")
    original_data={}
    for sym,record in original.items():
        if type(record) is not dict or set(record)!={"qty","market_value"}:
            raise SettlementStop("Malformed original position record")
        original_data[sym]=(_d(record["qty"],"original share quantity",positive=True),
                            _d(record["market_value"],"original market value",positive=True))
    xle_record=current["XLE"]
    if (type(xle_record) is not dict or set(xle_record)!={"qty","market_value"}):
        raise SettlementStop("Original XLE retention status missing")
    if _d(xle_record["qty"],"remaining XLE shares",positive=True)!=original_data["XLE"][0]:
        raise SettlementStop("Original XLE share quantity changed unexpectedly")
    val=_d(xle_record["market_value"],"remaining XLE value",positive=True)
    first_cash=_d(before.get("cash"),"before sale cash")
    first_equity=_d(before.get("equity"),"before sale equity",positive=True)
    cash=_d(after.get("cash"),"post sale cash")
    nav=_d(after.get("equity"),"post sale equity",positive=True)
    if (abs(first_cash+sum((x[1] for x in original_data.values()),Decimal(0))-first_equity)>Decimal(".03")
        or abs(cash+val-nav)>Decimal(".03")):
        return _summary("BLOCKED_UNRECONCILED_GROSS_EQUITY_CASH")
    if first_equity>policy.CAP or nav>policy.CAP*Decimal("1.5"):
        return _summary("BLOCKED_PILOT_CAP_OR_UNEXPECTED_EQUITY")
    if cash<=first_cash:
        return _summary("BLOCKED_NO_SALE_CASH_CREDIT_OBSERVED")
    if val>min(nav,policy.CAP)*policy.TARGET["XLE"]:
        return _summary("BLOCKED_ORIGINAL_XLE_OVERWEIGHT_REVIEW")
    sessions=snap.get("invented_us_equity_settlement_sessions")
    if (type(sessions) is not list or not 2<=len(sessions)<=ALLOWED_SETTLEMENT_LOOKBACK_SESSIONS):
        raise SettlementStop("No independent calendar session sequence supplied")
    ds=[_date(x) for x in sessions]
    if any(a>=b or (b-a).days>5 for a,b in zip(ds,ds[1:])):
        raise SettlementStop("Unsorted/incomplete simulated settlement calendar")
    ids=set()
    for sym in orders.LEGACY_TO_EXIT:
        order=receipts[sym]
        if type(order) is not dict:
            raise SettlementStop("Missing exact original filled SELL")
        q=original_data[sym][0]
        expected_id=orders._id(sym)
        if (order.get("client_order_id")!=expected_id
            or order.get("symbol")!=sym or order.get("side")!="sell"
            or order.get("type")!="market"
            or order.get("time_in_force")!="day"
            or order.get("status")!="filled"
            or order.get("notional") is not None):
            raise SettlementStop("Original SELL receipt identity/shape/status mismatch")
        if (type(order.get("id")) is not str or not order["id"]
            or order["id"] in ids):
            raise SettlementStop("Original duplicate/missing broker SELL order identity")
        ids.add(order["id"])
        if (_d(order.get("qty"),"original submitted share quantity",positive=True)!=q
            or _d(order.get("filled_qty"),"original filled share quantity",positive=True)!=q):
            raise SettlementStop("Partial or excess SELL fill; cash must be reconciled")
        fill=_at(order.get("filled_at"))
        if fill>seen_at:
            raise SettlementStop("Order fill timestamp after observed account")
        trade=fill.astimezone(ZoneInfo("America/New_York")).date()
        if trade not in ds:
            raise SettlementStop("Calendar does not include original trade session")
        index=ds.index(trade)
        if index+1>=len(ds):
            return _summary("WAIT_US_EQUITY_T_PLUS_ONE_SETTLEMENT_SESSION")
        if seen_at.astimezone(ZoneInfo("America/New_York")).date()<ds[index+1]:
            return _summary("WAIT_US_EQUITY_T_PLUS_ONE_SETTLEMENT_SESSION")
    # Some Trading API accounts do not expose the Broker API settle fields.
    # They must fail CLOSED rather than alias buying_power/cash to settlement.
    for account in (before,after):
        if any(account.get(field) is None for field in ACCOUNT_SETTLED_FIELDS):
            return _summary("BROKER_SETTLED_FIELD_UNSUPPORTED_HOLD")
    before_withdrawable=_d(before["cash_withdrawable"],"opening withdrawable cash")
    before_transferable=_d(before["cash_transferable"],"opening transferable cash")
    withdrawable=_d(after["cash_withdrawable"],"post withdrawal cash")
    transferable=_d(after["cash_transferable"],"post transferable cash")
    nonmarginable=_d(after.get("non_marginable_buying_power"),"post nonmarginable buying power")
    if (max(withdrawable,transferable)>cash+Decimal(".01")
        or max(before_withdrawable,before_transferable)>first_cash+Decimal(".01")
        or withdrawable<before_withdrawable
        or transferable<before_transferable):
        return _summary("BROKER_SETTLED_BALANCE_INCONSISTENT_HOLD")
    spendable=min(cash,withdrawable,transferable,nonmarginable)
    # The hypothetical buy is a deliberately separate no-execution envelope.
    symbol=snap.get("next_hypothetical_buy_symbol")
    if symbol not in policy.BUY:
        raise SettlementStop("Invalid new V6 BUY symbol")
    desired=_d(snap.get("next_hypothetical_buy_notional"),"hypothetical buy",positive=True)
    fees=_d(snap.get("next_hypothetical_buy_cost_buffer"),"hypothetical buy fee buffer")
    if desired<policy.MIN_BUY or desired>policy.MAX_ORDER:
        return _summary("BLOCKED_BUY_SIZE")
    if spendable-desired-fees<nav*policy.CASH_FLOOR:
        return _summary("BLOCKED_INDEPENDENT_SPENDABLE_CASH_OR_FIVE_PERCENT_FLOOR")
    if (val+desired>nav*policy.MAX_GROSS
        or (symbol=="XLE" and val+desired>min(nav,policy.CAP)*policy.TARGET["XLE"])):
        return _summary("BLOCKED_NEW_BUY_GROSS_OR_XLE_CHURN")
    if (symbol=="XLE" and val+desired>nav*policy.MAX_SYMBOL
        or symbol!="XLE" and desired>nav*policy.MAX_SYMBOL):
        return _summary("BLOCKED_SYMBOL_CONCENTRATION")
    return _summary("SYNTHETIC_CASH_EVIDENCE_ENVELOPE_VALIDATED_NOT_LIVE")
