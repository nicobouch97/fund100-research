"""Trading API-compatible post-sale BUY cash screen. OFFLINE / NO ORDERS.

Retail Trading GET /v2/account does not expose Broker-API cash_withdrawable
or cash_transferable. Its cash and buying_power can include unsettled sale
proceeds. Use an intentionally conservative wait, *both* cash and
non_marginable_buying_power, reconstructed sale/fill/position evidence and
a 5% post-buy buffer. None of these alone certifies settled proceeds.

Every input here is CALLER-ASSERTED and cannot confer source authenticity.
The future protected LIVE reader must independently authenticate the whole
account, all FILL and funding history, order status, and market calendar
before considering this conservative mathematical screen. No broker client,
network call, GitHub write, actual buy order, or release.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

SCHEMA="FUND100_V6_S1_TRADING_API_POSTSALE_CASH_SCREEN_OFFLINE_V1"
MODE="INJECTED_UNAUTHENTICATED_TRADING_API_FIXTURES_ONLY"
LIVE_BUY_RELEASED=False
CAP=Decimal("130.30")
MAX_NEW_ORDER=Decimal("65.00")
MIN_NEW_ORDER=Decimal("1.00")
MIN_CASH=Decimal(".05")
MAX_GROSS=Decimal(".95")
MAX_SYMBOL=Decimal(".50")
MAX_XLE_TARGET=Decimal(".285")
EXIT=frozenset(("ACWI","EEM","XLV"))
NEW=frozenset(("XLK","IWM","XLE"))
NY=ZoneInfo("America/New_York")

class TradingCashStop(ValueError):
    pass

def _usd(value,label,*,nonzero=False):
    if type(value) is not str or not value or "e" in value.lower():
        raise TradingCashStop("Missing canonical decimal "+label)
    try:x=Decimal(value)
    except InvalidOperation:raise TradingCashStop("Invalid decimal "+label) from None
    if not x.is_finite() or x<0 or (nonzero and x==0) or x.as_tuple().exponent<-2:
        raise TradingCashStop("Out-of-range USD "+label)
    return x

def _clock(value,label):
    if type(value) is not str or not value.endswith("Z"):
        raise TradingCashStop("Missing exact UTC "+label)
    try:x=datetime.fromisoformat(value[:-1]+"+00:00")
    except ValueError:raise TradingCashStop("Invalid UTC "+label) from None
    if x.utcoffset()!=timedelta(0):
        raise TradingCashStop("Non-UTC "+label)
    return x

def _completed_weekdays_after(*,last_sale,now):
    """Conservative calendar-only buffer, NOT proof of exchange settlement.

    Count only full Monday-Friday sessions strictly after latest US sale date.
    Exchange holidays can overcount: require three full weekdays (vs normal
    equity T+1) AND non-marginable available funds. Calendar alone never
    certifies brokerage settlement or creates live order authority.
    """
    sale_date=last_sale.astimezone(NY).date()
    now_local=now.astimezone(NY)
    day=sale_date+timedelta(days=1)
    done=0
    while day<=now_local.date() and (day-sale_date).days<=30:
        if day.weekday()<5 and (day<now_local.date()
           or (now_local.hour,now_local.minute)>=(16,30)):
            done+=1
        day+=timedelta(days=1)
    return done

def _hold(stage,*,sessions=0):
    return {
        "schema":SCHEMA,"status":stage,
        "conservative_completed_weekdays_after_last_sale":sessions,
        "retail_trading_api_cash_fields_only":True,
        "broker_api_withdrawable_field_required":False,
        "independent_broker_history_authenticated":False,
        "actual_settled_proceeds_certified":False,
        "independent_exchange_calendar_verified":False,
        "eligible_for_separate_approved_live_buy":False,
        "new_buy_notional_validated_for_research_only":
            stage=="CONSERVATIVE_TRADING_API_CASH_ENVELOPE_PASSED_NOT_AUTHORIZED",
        "original_contribution_cap_usd":"130.30",
        "max_new_buy_usd":"65.00",
        "cash_floor_fraction":"0.05",
        "original_xle_sale_required":False,
        "broker_requests":0,"broker_post_attempts":0,
        "account_id":None,"balances":None,
        "order_payload":None,"private_fills":None,
    }

def screen(*,snapshot:dict,now_utc:str,buy_symbol:str,
           buy_usd:str,worst_case_all_in_cost_usd:str)->dict:
    """Pure offline assessment of a proposed future BUY; never trade."""
    if (type(snapshot) is not dict
        or snapshot.get("mode")!=MODE
        or snapshot.get("source_authenticated_live") is not False
        or snapshot.get("operator_stopped") is not True
        or snapshot.get("kill_switch")!="ENGAGED"
        or snapshot.get("risk_level")!="HIGH"):
        raise TradingCashStop("Unverified or improperly armed candidate source")
    now=_clock(now_utc,"observation")
    observed=_clock(snapshot.get("observed_at_utc"),"broker account snapshot")
    if not 0<=(now-observed).total_seconds()<=300:
        return _hold("HOLD_STALE_OR_FUTURE_ACCOUNT_SOURCE")
    if (snapshot.get("original_deposit_events")!=1
        or snapshot.get("original_deposit_total_usd")!="130.30"
        or snapshot.get("all_order_pages_complete") is not True
        or snapshot.get("all_fill_pages_complete") is not True
        or snapshot.get("all_nontrade_activity_pages_complete") is not True
        or snapshot.get("unreconciled_external_cashflows")!=0
        or snapshot.get("unreconciled_open_orders")!=0):
        return _hold("HOLD_UNPROVEN_OR_UNRECONCILED_ACCOUNT_HISTORY")
    account=snapshot.get("account")
    positions=snapshot.get("positions")
    fills=snapshot.get("original_exit_fills")
    if (type(account) is not dict or type(positions) is not dict
        or type(fills) is not dict or set(fills)!=EXIT):
        return _hold("HOLD_MISSING_ORIGINAL_THREE_EXIT_FILLS")
    if (account.get("status")!="ACTIVE"
        or account.get("trading_blocked") is not False
        or account.get("account_blocked") is not False
        or account.get("multiplier")!="1"
        or account.get("pending_transfer_in") not in (None,"0","0.00")
        or account.get("pending_transfer_out") not in (None,"0","0.00")):
        return _hold("HOLD_ACCOUNT_NOT_UNLEVERAGED_ACTIVE_OR_PENDING_TRANSFER")
    if set(positions)!={"XLE"}:
        return _hold("HOLD_LEGACY_NOT_FLAT_OR_XLE_NOT_RETAINED")
    last=None
    for symbol in sorted(EXIT):
        fill=fills[symbol]
        if (type(fill) is not dict
            or fill.get("symbol")!=symbol
            or fill.get("side")!="sell"
            or fill.get("status")!="filled"
            or fill.get("client_order_id") is None
            or fill.get("reconciled_original_exact_qty") is not True
            or fill.get("filled_exact_qty") is not True
            or fill.get("broker_fills_complete") is not True):
            return _hold("HOLD_ORIGINAL_EXIT_FILL_OR_QUANTITY_UNCONFIRMED")
        when=_clock(fill.get("filled_at"),"exit fill")
        if when>observed:
            return _hold("HOLD_SALE_AFTER_ACCOUNT_OBSERVATION")
        last=when if last is None or when>last else last
    sessions=_completed_weekdays_after(last_sale=last,now=now)
    if sessions<3 or now-last<timedelta(days=3):
        return _hold("WAIT_CONSERVATIVE_POSTSALE_TPLUSONE_BUFFER",sessions=sessions)
    try:
        cash=_usd(account.get("cash"),"cash")
        equity=_usd(account.get("equity"),"equity",nonzero=True)
        buying=_usd(account.get("buying_power"),"buying_power")
        nonmargin=_usd(account.get("non_marginable_buying_power"),"non_marginable_buying_power")
        xle=_usd(positions["XLE"],"remaining original XLE position",nonzero=True)
        buy=_usd(buy_usd,"new buy",nonzero=True)
        cost=_usd(worst_case_all_in_cost_usd,"all-in order cost")
    except (KeyError,TypeError,TradingCashStop):
        return _hold("HOLD_TRADING_API_CASH_FIELDS_OR_MARKS_MISSING",sessions=sessions)
    if (equity<=0 or cash>equity or nonmargin>equity or buying<nonmargin
        or abs(equity-cash-xle)>max(Decimal(".02"),equity*Decimal(".002"))):
        return _hold("HOLD_TRADING_ACCOUNT_BALANCE_RECONCILIATION",sessions=sessions)
    if buy_symbol not in NEW or buy<MIN_NEW_ORDER or buy>MAX_NEW_ORDER:
        return _hold("BLOCK_NEW_ORDER_UNIVERSE_OR_65_USD_LIMIT",sessions=sessions)
    if xle>equity*MAX_XLE_TARGET:
        return _hold("HOLD_RETAINED_XLE_OVER_TARGET_REVIEW",sessions=sessions)
    # Never spend apparent settlement credit on the basis of cash or general
    # buying power alone: all three available balances and post-cost NAV must
    # preserve the 5% reserve. This still does NOT prove settlement.
    remaining=buy+cost+equity*MIN_CASH
    if min(cash,nonmargin,buying)<remaining:
        return _hold("BLOCK_INSUFFICIENT_CONSERVATIVE_CASH_OR_RESERVE",sessions=sessions)
    if xle+buy>MAX_GROSS*(equity-cost):
        return _hold("BLOCK_POST_ORDER_GROSS_EXPOSURE",sessions=sessions)
    if (buy_symbol=="XLE" and xle+buy>MAX_XLE_TARGET*(equity-cost)
        or buy_symbol!="XLE" and buy>MAX_SYMBOL*(equity-cost)):
        return _hold("BLOCK_POST_ORDER_SYMBOL_CONCENTRATION",sessions=sessions)
    return _hold("CONSERVATIVE_TRADING_API_CASH_ENVELOPE_PASSED_NOT_AUTHORIZED",
                 sessions=sessions)
