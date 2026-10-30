"""Fund-100 V6-S1 repeatable monthly ETF risk/cash maintenance, PURE NO-TRADE core.

Unlike the once-only ACWI/EEM/XLV migration, a funded strategy needs a
subsequent rebalance rule. This module is NOT a broker source or writer:
it only accepts strictly labelled hypothetical fixture state. It cannot
prove external order history, settled cash, funding, prices or current GO.
The recurring strategy is intentionally the *already registered* fixed S1
target/band policy, not post-hoc selection of a stronger-performing rule.

Any future production runner needs independently authenticated source and
standing mandate/STOP, a distinct reviewed recurring signed order ledger,
a unique broker client ID and separate event/settlement safety release.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
from hashlib import sha256
from zoneinfo import ZoneInfo
import re

import fund100_v6_s1_staged_controller_core_v1_0 as migration
import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as policy

SCHEMA="FUND100_V6_S1_RECURRING_MONTHLY_REBALANCE_OFFLINE_V1"
MODE="UNAUTHENTICATED_IN_MEMORY_PORTFOLIO_SCENARIO_ONLY"
NO_BROKER_NETWORK=True
NO_BROKER_ORDER=True
NO_PRIVATE_STATE_WRITE=True
LIVE_RECURRING_EXECUTION_RELEASED=False
MONTH_END_EVENT="MONTH_END_REVIEW_HYPOTHETICAL_ONLY"
NY=ZoneInfo("America/New_York")
BAND=Decimal("0.10")  # Original registered 10 percentage-point maintenance band.
TARGET=dict(migration.TARGETS)
UNIVERSE=frozenset(TARGET)
CENTS=Decimal(".01")
MAX_FEE=Decimal("5.00")
# Do not pay >100bps estimated all-in cost merely to place a dust trade.
MAX_SIDE_COST_FRACTION=Decimal(".01")
MAX_HISTORY=100

class RecurringStop(ValueError): pass

def _num(v,label,*,positive=False):
    if type(v) is not str or re.fullmatch(
        r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?",v) is None:
        raise RecurringStop("Bad non-negative decimal "+label)
    try: x=Decimal(v)
    except InvalidOperation:raise RecurringStop("Invalid "+label) from None
    if not x.is_finite() or (positive and x==0):
        raise RecurringStop("Non-finite/zero "+label)
    return x

def _signed(v,label):
    if type(v) is not str or re.fullmatch(
        r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?",v) is None:
        raise RecurringStop("Bad signed decimal "+label)
    d=Decimal(v)
    if not d.is_finite():raise RecurringStop("Non-finite "+label)
    return d

def _time(v):
    if type(v) is not str or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",v):
        raise RecurringStop("Noncanonical UTC source timestamp")
    try:d=datetime.strptime(v,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:raise RecurringStop("Invalid UTC time") from None
    return d

def _id(period,symbol,side):
    """Stable within period, unlike new random IDs after a process restart.

    The SIM- prefix expressly makes this NOT an executable Alpaca client ID.
    A future live signed ledger must bind its own reviewed real client ID.
    """
    if (type(period) is not str or not re.fullmatch(r"\d{4}-\d{2}",period)
        or symbol not in UNIVERSE or side not in ("buy","sell")):
        raise RecurringStop("Invalid recurring event identity")
    material="fund100-S1-monthly-v1|"+period+"|"+symbol+"|"+side
    return "SIM-f100s1-"+sha256(material.encode("ascii")).hexdigest()[:24]

def _report(stage,reason=None,*,candidate=None,period=None):
    return {
        "schema":SCHEMA,"status":stage,"reason":reason,
        "period":period,"hypothetical_candidate":candidate,
        "candidate_executable":False,
        "standing_mandate_automatic_monthly_review_intended":True,
        "manual_per_order_approval_required_by_this_research_core":False,
        "original_V6_95pct_targets_and_10pp_band_unchanged":True,
        "market_data_or_account_independently_authenticated":False,
        "original_migration_broker_fills_independently_authenticated":False,
        "broker_settled_cash_independently_authenticated":False,
        "broker_history_or_signed_ledger_independently_verified":False,
        "can_submit_real_portfolio_rebalance":False,
        "can_override_STOP_or_HIGH_risk":False,
        "actual_order_count":0,"broker_GETs":0,"broker_POSTs":0,
        "private_Git_writes":0,
    }

def assess(*,snapshot:dict,now_utc:str)->dict:
    """Return at most one *hypothetical* monthly SELL then BUY after settlement.

    This can run repeatedly as pure arithmetic without duplicate order sends.
    All historical order and funding completeness flags are *invented* inputs:
    no return value constitutes independent broker authentication or a trade.
    """
    # Reuse the original source-locked STOPPED HIGH candidate, not an invented
    # concentration/capital contract or a silent bypass of the old V5 policy.
    p=policy.contract()
    if (p.get("orders_authorized") is not False
        or p.get("target_weights")!=
            {"XLK":"0.475","XLE":"0.285","IWM":"0.190"}):
        raise RecurringStop("Original V6 investment or STOP contract changed")
    if (type(snapshot) is not dict
        or snapshot.get("mode")!=MODE
        or snapshot.get("source_authenticated_live") is not False
        or snapshot.get("operator_stopped") is not True
        or snapshot.get("broker_kill_switch")!="ENGAGED"
        or snapshot.get("risk_level")!="HIGH"
        or snapshot.get("initial_migration_all_three_sells_reconciled") is not True
        or snapshot.get("initial_migration_all_three_buys_reconciled") is not True
        or snapshot.get("source_full_account_order_history_complete") is not True
        or snapshot.get("source_all_fill_pages_complete") is not True
        or snapshot.get("source_external_cashflows_reconciled") is not True
        or snapshot.get("review_event")!=MONTH_END_EVENT):
        raise RecurringStop("Not a fully reconciled stopped research scenario")
    now=_time(now_utc)
    observed=_time(snapshot.get("observed_at_utc"))
    age=(now-observed).total_seconds()
    if age<0 or age>300:
        return _report("HOLD_STALE_OR_FUTURE_SOURCE")
    period=observed.astimezone(NY).strftime("%Y-%m")
    if snapshot.get("review_month")!=period:
        return _report("HOLD_MONTHLY_REVIEW_PERIOD_MISMATCH")
    if snapshot.get("review_due") is not True:
        return _report("HOLD_NOT_MONTHLY_REVIEW",period=period)
    if type(snapshot.get("unresolved_broker_orders")) is not int:
        raise RecurringStop("Unknown number of current orders")
    if snapshot["unresolved_broker_orders"]!=0:
        return _report("HOLD_UNRECONCILED_ORDER",period=period)
    nav=_num(snapshot.get("equity_usd"),"portfolio NAV",positive=True)
    cash=_num(snapshot.get("cash_usd"),"account cash")
    settled=_num(snapshot.get("settled_cash_usd"),"settled USD")
    deposit=_num(snapshot.get("original_contributed_principal_usd"),
                 "original pilot contribution",positive=True)
    if (deposit>migration.CAP
        or type(snapshot.get("original_contribution_events")) is not int
        or snapshot.get("original_contribution_events")!=1):
        return _report("HOLD_ORIGINAL_PILOT_FUNDING_NOT_PROVEN",period=period)
    if cash>nav or settled>cash:
        return _report("HOLD_CASH_MORE_THAN_NAV_OR_UNRECONCILED",period=period)
    marks=snapshot.get("position_values_usd")
    if type(marks) is not dict or set(marks)!=UNIVERSE:
        raise RecurringStop("Expected exactly three original postmigration ETFs")
    values={s:_num(marks[s],s+" marked USD") for s in TARGET}
    gross=sum(values.values(),Decimal(0))
    if abs(gross+cash-nav)>CENTS:
        return _report("HOLD_BROKER_BALANCE_AND_MARKS_DISAGREE",period=period)
    risks=snapshot.get("risk_metrics")
    if type(risks) is not dict or set(risks)!={
        "daily_return","rolling_drawdown","annualized_volatility"}:
        raise RecurringStop("Missing account-wide HIGH risk facts")
    daily=_signed(risks["daily_return"],"daily account return")
    dd=_signed(risks["rolling_drawdown"],"rolling drawdown")
    vol=_num(risks["annualized_volatility"],"annualized vol")
    if daily<Decimal("-1") or daily>Decimal("1") or dd<Decimal("-1") or dd>0:
        return _report("HOLD_ACCOUNT_RISK_SOURCE_INVALID",period=period)
    if daily<=Decimal("-.06") or dd<=Decimal("-.20") or vol>Decimal(".35"):
        return _report("HOLD_HIGH_RISK_LOSS_DRAWDOWN_OR_VOL_STOP",period=period)
    # Existing gross, symbol or minimum-cash breaches must NEVER enable a
    # new BUY. But an offline SELL-only cash/risk repair may be assessed
    # *after* exact event-ledger and conservative fee checks below. The
    # original monthly 10pp target band alone left cash <5% on many closes.
    gross_breach=gross>nav*migration.MAX_GROSS
    symbol_breaches={sym for sym in UNIVERSE
                    if values[sym]>nav*migration.MAX_SYMBOL}
    cash_breach=cash<nav*migration.CASH_FLOOR
    history=snapshot.get("monthly_seen_client_ids")
    completed=snapshot.get("monthly_fully_reconciled_client_ids")
    if (type(history) is not list or type(completed) is not list
        or len(history)>MAX_HISTORY or len(completed)>MAX_HISTORY
        or any(type(x) is not str or re.fullmatch(
            r"SIM-f100s1-[a-f0-9]{24}",x) is None for x in history+completed)
        or len(history)!=len(set(history))
        or len(completed)!=len(set(completed))
        or not set(completed)<=set(history)):
        raise RecurringStop("Incomplete or ambiguous hypothetical monthly journal")
    possible={_id(period,sym,side) for sym in UNIVERSE for side in ("sell","buy")}
    if not set(history)<=possible:
        return _report("HOLD_UNEXPECTED_MONTHLY_ACTION_ID",period=period)
    if set(history)!=set(completed):
        return _report("HOLD_UNRECONCILED_PREVIOUS_MONTHLY_ACTION",period=period)
    quotes=snapshot.get("all_in_fee_buffers_usd")
    if type(quotes) is not dict or set(quotes)!=UNIVERSE:
        raise RecurringStop("Missing all three conservative cost estimates")
    fees={symbol:_num(value,symbol+" all-in fee") for symbol,value in quotes.items()}
    if any(f>MAX_FEE for f in fees.values()):
        return _report("HOLD_UNBOUNDED_BROKER_FRICTION",period=period)
    # Risk-reducing maintenance is separate from the 10pp *alpha/turnover*
    # band: a passive cash-floor or gross drift must not persist forever
    # solely because no sector exceeds its discretionary month-end band.
    # The proposed SELL is STILL UNAUTHENTICATED and NONEXECUTABLE. Live
    # runner must source genuine fractional quantity, price, fees and a
    # signed client ID before any order; settlement is required before BUY.
    if gross_breach or symbol_breaches or cash_breach:
        # One corrective monthly SALE at most, even if the original SELL
        # filled but a later snapshot still shows a smaller cash deficit.
        # A new independently reviewed later-period event can reconsider.
        if any(_id(period,sym,"sell") in history for sym in UNIVERSE):
            return _report(
                "HOLD_CASH_OR_EXPOSURE_REPAIR_ALREADY_ATTEMPTED_OR_NOT_FEASIBLE",
                period=period)
        ranked=sorted(UNIVERSE,key=lambda sym:(
            sym in symbol_breaches,
            values[sym]/nav-TARGET[sym],
            values[sym]),reverse=True)
        for sym in ranked:
            # Keep already-underweight sectors untouched unless they alone
            # exceed the hard 50% single-name limit.
            surplus=values[sym]-TARGET[sym]*nav
            if surplus<=0 and sym not in symbol_breaches:
                continue
            ident=_id(period,sym,"sell")
            if ident in history:
                # Never regenerate a same-month SELL with changed sizing.
                continue
            fee=fees[sym]
            # A sale consumes fees from NAV; all three constraints must be
            # evaluated on conservative AFTER-FEE quantities.
            needed_cash=max(Decimal(0),
                            nav*migration.CASH_FLOOR-cash+fee)
            needed_gross=max(Decimal(0),
                             gross-migration.MAX_GROSS*(nav-fee))
            needed_symbol=max(Decimal(0),
                              values[sym]-migration.MAX_SYMBOL*(nav-fee))
            required=max(needed_cash,needed_gross,needed_symbol,
                         max(Decimal(0),surplus))
            # Very small reserve breaches cannot justify a 10%+ all-in
            # execution drag. Seek one economical ticket only if that can
            # remain inside the original +/-10pp underweight tolerance.
            # Do not simulate repeated $1 repairs or free zero-cost fills.
            economical=(fee/MAX_SIDE_COST_FRACTION).quantize(
                CENTS,rounding=ROUND_UP)
            desired=max(required,economical,migration.MIN_ORDER)
            size=min(desired.quantize(CENTS,rounding=ROUND_UP),
                     migration.MAX_ORDER,values[sym])
            lowest_within_band=max(
                Decimal(0),(TARGET[sym]-BAND)*nav)
            if (size<migration.MIN_ORDER
                or fee>=size or fee>MAX_SIDE_COST_FRACTION*size
                or (sym not in symbol_breaches
                    and values[sym]-size<lowest_within_band)):
                return _report("HOLD_CASH_OR_EXPOSURE_REPAIR_TOO_SMALL_OR_COSTLY",
                               period=period)
            if (cash+size-fee<=cash
                or gross-size>=gross
                or values[sym]-size<0):
                raise RecurringStop("Hypothetical risk repair not reducing risk")
            # A $65 maximum ticket or limited position quantity may make
            # a one-sale repair impossible. Do not label a partial reduction
            # a repair when ANY hard portfolio limit still fails after
            # conservative fees. The caller must HOLD; no second monthly
            # sale, automatic order, or fabricated continuous cash promise.
            after_nav=nav-fee
            after_cash=cash+size-fee
            after_gross=gross-size
            after_marks={**values,sym:values[sym]-size}
            if (after_nav<=0
                or after_cash<after_nav*migration.CASH_FLOOR
                or after_gross>after_nav*migration.MAX_GROSS
                or any(value>after_nav*migration.MAX_SYMBOL
                       for value in after_marks.values())):
                return _report(
                    "HOLD_CASH_OR_EXPOSURE_REPAIR_INCOMPLETE_AFTER_TICKET_CAP",
                    period=period)
            return _report(
                "HYPOTHETICAL_MONTHLY_CASH_OR_EXPOSURE_REPAIR_SELL_NO_TRANSPORT",
                period=period,candidate={
                    "symbol":sym,"side":"sell",
                    "estimated_notional_usd":format(size,".2f"),
                    "stable_simulation_event_id":ident,
                    "repair_reason":(
                        "HARD_SYMBOL_LIMIT" if sym in symbol_breaches else
                        "MINIMUM_CASH_OR_GROSS_DRIFT"),
                    "requires_independent_order_and_settlement_reconciliation":True,
                    "after_fee_entire_portfolio_risk_repair_proven":False,
                    "executable":False})
        return _report("HOLD_CASH_OR_EXPOSURE_REPAIR_ALREADY_ATTEMPTED_OR_NOT_FEASIBLE",
                       period=period)
    # Existing original monthly +/- 10 percentage-point tolerance. SELL
    # the biggest excess first; existing XLE is NOT a forced legacy exit.
    excess=[]
    for sym in sorted(UNIVERSE):
        delta=values[sym]/nav-TARGET[sym]
        if delta>BAND:
            excess.append((delta,sym))
    for _,sym in sorted(excess,key=lambda x:(-x[0],x[1])):
        ident=_id(period,sym,"sell")
        if ident in history:continue
        trim=(values[sym]-TARGET[sym]*nav).quantize(CENTS,rounding=ROUND_DOWN)
        size=min(trim,migration.MAX_ORDER).quantize(CENTS,rounding=ROUND_DOWN)
        if (size<migration.MIN_ORDER or fees[sym]>=size
            or fees[sym]>MAX_SIDE_COST_FRACTION*size):
            return _report("HOLD_SELL_TOO_SMALL_OR_TOO_COSTLY",period=period)
        return _report("HYPOTHETICAL_MONTHLY_TRIM_SELL_NO_TRANSPORT",
            period=period,candidate={
                "symbol":sym,"side":"sell","estimated_notional_usd":format(size,".2f"),
                "stable_simulation_event_id":ident,
                "requires_independent_order_and_settlement_reconciliation":True,
                "executable":False})
    # New buys are screened on both available and SETTLED cash, 5% postfee
    # reserve, 95% gross, 50% single-name and $1-$65 per-order bounds.
    shortage=[]
    for sym in sorted(UNIVERSE):
        delta=TARGET[sym]-values[sym]/nav
        if delta>BAND:shortage.append((delta,sym))
    for _,sym in sorted(shortage,key=lambda x:(-x[0],x[1])):
        ident=_id(period,sym,"buy")
        if ident in history:continue
        fee=fees[sym]
        headroom=min(
            TARGET[sym]*nav-values[sym],
            migration.MAX_ORDER,
            min(cash,settled)-fee-migration.CASH_FLOOR*(nav-fee),
            migration.MAX_GROSS*(nav-fee)-gross,
            migration.MAX_SYMBOL*(nav-fee)-values[sym],
        )
        size=headroom.quantize(CENTS,rounding=ROUND_DOWN)
        if size<migration.MIN_ORDER:
            return _report("HOLD_BUY_REQUIRES_SETTLED_CASH_OR_RISK_HEADROOM",
                           period=period)
        if fee>MAX_SIDE_COST_FRACTION*size:
            return _report("HOLD_BUY_ALL_IN_COST_EXCEEDS_1PCT",period=period)
        if (min(cash,settled)-size-fee<migration.CASH_FLOOR*(nav-fee)
            or gross+size>migration.MAX_GROSS*(nav-fee)
            or values[sym]+size>migration.MAX_SYMBOL*(nav-fee)):
            raise RecurringStop("Calculated hypothetical BUY fails post-cost bounds")
        return _report("HYPOTHETICAL_MONTHLY_REPLENISH_BUY_NO_TRANSPORT",
            period=period,candidate={
                "symbol":sym,"side":"buy","estimated_notional_usd":format(size,".2f"),
                "stable_simulation_event_id":ident,
                "requires_independent_order_and_settlement_reconciliation":True,
                "executable":False})
    return _report("HOLD_WITHIN_MONTHLY_10PP_BAND_NO_FORCED_CHURN",period=period)
