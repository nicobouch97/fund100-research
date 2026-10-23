"""V6-S1 pure funding-aware diagnostics, NOT production account risk clearance.

Original six GET account history returned real external transfer types, but
NO values or timestamps. This strictly research-only calculator consumes
invented, source-shaped fixtures. Modified Dietz is an approximation,
not exact time-weighted return nor a LIVE stop/order permit.
"""
from __future__ import annotations

from bisect import bisect_left
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from math import sqrt
from statistics import stdev

SCHEMA="FUND100_V6_S1_SYNTHETIC_EXTERNAL_FLOW_RISK_INPUT_V1"
RESULT_SCHEMA="FUND100_V6_S1_FLOW_AWARE_DIETZ_DIAGNOSTIC_RESEARCH_ONLY_V1"
MODE="INVENTED_EQUITY_AND_ACCOUNT_ACTIVITY_FIXTURES_ONLY"
TRANSFER={"CSD":1,"CSW":-1}
UNSUPPORTED_ASSET_TRANSFERS=frozenset({"ACATC","ACATS","JNL","JNLC","JNLS","TRANS"})
OTHER=frozenset({"DIV","DIVCGL","DIVCGS","DIVFEE","DIVFT","DIVNRA","DIVROC",
                 "DIVTW","DIVTXEX","FEE","CFEE","INT","INTNRA","INTTW",
                 "MISC","PTC","PTR","MA","NC","REORG","SC","SSO","SSP"})
MAX_ADJUSTED_RETURN=Decimal(".25")
MAX_DAILY_LOSS=Decimal("-.06")
MAX_UNIT_DRAWDOWN=Decimal(".20")
MAX_ANNUAL_VOL=Decimal(".35")
MAX_ACTIVITY_ROWS=100
MAX_POINTS=70
MIN_POINTS=6

class FundingRiskStop(ValueError):pass

def dec(raw,label,positive=False):
    if type(raw) not in (str,int,Decimal):raise FundingRiskStop("Bad "+label)
    try:v=Decimal(str(raw))
    except (InvalidOperation,ValueError) as exc:raise FundingRiskStop("Non-numeric "+label) from exc
    if not v.is_finite() or (positive and v<=0):
        raise FundingRiskStop("Nonfinite or nonpositive "+label)
    return v

def stamp(value):
    if type(value) is not str or not value:
        raise FundingRiskStop("Missing authentic event transaction timestamp")
    try:
        result=datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:raise FundingRiskStop("Malformed ISO event timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise FundingRiskStop("Naive event timestamp/settlement date forbidden")
    return result.astimezone(timezone.utc)

def analyze(*,fixture:dict,now_utc:str)->dict:
    if (not isinstance(fixture,dict) or fixture.get("schema")!=SCHEMA
        or fixture.get("mode")!=MODE
        or fixture.get("authenticated_broker_source") is not False
        or fixture.get("live_operator_stopped") is not True
        or fixture.get("broker_kill_switch")!="ENGAGED"
        or fixture.get("risk_level")!="HIGH"):
        raise FundingRiskStop("No authentic LIVE inputs, orders or release")
    now=stamp(now_utc)
    h=fixture.get("portfolio_history")
    if not isinstance(h,dict) or h.get("timeframe")!="1D":
        raise FundingRiskStop("Missing original one-day equity series")
    ts=h.get("timestamp");v=h.get("equity")
    if (not isinstance(ts,list) or not isinstance(v,list)
        or len(ts)!=len(v) or not MIN_POINTS<=len(ts)<=MAX_POINTS):
        raise FundingRiskStop("Invalid length of source day-series")
    if any(type(t) is not int or t<=0 for t in ts):
        raise FundingRiskStop("Invalid day timestamp")
    if any(b<=a or b-a>5*86400 for a,b in zip(ts,ts[1:])):
        raise FundingRiskStop("Missing or repeated daily source values")
    first=datetime.fromtimestamp(ts[0],timezone.utc)
    last=datetime.fromtimestamp(ts[-1],timezone.utc)
    if not 0<=(now-last).total_seconds()<=10*86400:
        raise FundingRiskStop("Stale or future day observation")
    equities=[dec(a,"source daily equity",positive=True) for a in v]
    start=stamp(fixture.get("nontrade_activity_query_after"))
    if start>first:
        raise FundingRiskStop("Account activities did not cover full returns window")
    rows=fixture.get("nontrade_activities")
    if type(rows) is not list or len(rows)>=MAX_ACTIVITY_ROWS:
        raise FundingRiskStop("Activities unpaged or non-list, no complete cashflow ledger")
    transfer_intervals={i:[] for i in range(1,len(ts))}
    ids=set();transfers=0
    for a in rows:
        if type(a) is not dict:raise FundingRiskStop("Malformed original activity event")
        aid=a.get("id")
        if type(aid) is not str or not aid or aid in ids:
            raise FundingRiskStop("Missing/duplicate original activity identity")
        ids.add(aid)
        typ=a.get("activity_type")
        if type(typ) is not str or typ!=typ.strip() or not typ.isupper():
            raise FundingRiskStop("Unknown/malformed original brokerage activity type")
        if typ in UNSUPPORTED_ASSET_TRANSFERS:
            raise FundingRiskStop("Noncash account transfers lack source asset valuation")
        if typ not in TRANSFER and typ not in OTHER:
            raise FundingRiskStop("New/unrecognized original accounting event type")
        if typ not in TRANSFER:
            continue  # Dividend/fee/interest are investment economics, NOT deposits.
        value=dec(a.get("net_amount"),"signed original cash transfer")
        if value*TRANSFER[typ]<=0:
            raise FundingRiskStop("Original signed transfer contradicts debit/credit type")
        t=stamp(a.get("transaction_time"))  # NOT settlement 'date'
        if t<=first:
            continue  # Transfer at/before first baseline is baked into first NAV.
        if t>last:
            raise FundingRiskStop("Transfer occurs after most recent observed equity")
        index=bisect_left(ts,int(t.timestamp()))
        if index<=0 or index>=len(ts):
            raise FundingRiskStop("Transfer has no valid portfolio interval")
        # If time includes fractional seconds, int() truncates; verify strictly.
        left=datetime.fromtimestamp(ts[index-1],timezone.utc)
        right=datetime.fromtimestamp(ts[index],timezone.utc)
        if not left<t<=right:
            raise FundingRiskStop("Cash transfer cannot be allocated to close interval")
        transfers+=1
        transfer_intervals[index].append((t,value))
    dietz=[];raw=[]
    units=[Decimal(1)]
    for i in range(1,len(ts)):
        a,b=equities[i-1],equities[i]
        begin=datetime.fromtimestamp(ts[i-1],timezone.utc)
        end=datetime.fromtimestamp(ts[i],timezone.utc)
        period=Decimal(str((end-begin).total_seconds()))
        flows=transfer_intervals[i]
        flow_sum=sum((f for _,f in flows),Decimal(0))
        weighted=sum((f*Decimal(str((end-t).total_seconds()))/period
                      for t,f in flows),Decimal(0))
        base=a+weighted
        if base<=0:
            raise FundingRiskStop("Nonpositive invested modified-Dietz denominator")
        r=(b-a-flow_sum)/base
        if not -MAX_ADJUSTED_RETURN<=r<=MAX_ADJUSTED_RETURN:
            raise FundingRiskStop("Untrusted >25pct adjusted interval magnitude")
        raw.append(b/a-Decimal(1))
        dietz.append(r)
        newer=units[-1]*(Decimal(1)+r)
        if newer<=0:raise FundingRiskStop("Unusable normalized index")
        units.append(newer)
    latest=dietz[-1]
    peak=units[0];maximum_drawdown=Decimal(0)
    for item in units:
        peak=max(peak,item)
        maximum_drawdown=max(maximum_drawdown,Decimal(1)-item/peak)
    vol=Decimal(str(stdev([float(x) for x in dietz])*sqrt(252)))
    risk_stop=(latest<=MAX_DAILY_LOSS or maximum_drawdown>=MAX_UNIT_DRAWDOWN
               or vol>MAX_ANNUAL_VOL)
    notable=any(abs(x-y)>Decimal("0.000001") for x,y in zip(raw,dietz))
    return {
      "schema":RESULT_SCHEMA,
      "research_status":"OFFLINE_MODIFIED_DIETZ_FLOW_ADJUSTED_ESTIMATE_ONLY",
      "original_source_broker_authenticated":False,
      "synthetic_original_sample_complete":True,
      "funding_events_economically_mapped_in_fixture":True,
      "eligible_external_cash_transfers_in_fixture":transfers>0,
      "raw_and_flow_adjusted_intervals_differ":notable,
      "dietz_risk_limit_breached_in_synthetic_history":risk_stop,
      "dietz_daily_loss_limit_breached_in_fixture":latest<=MAX_DAILY_LOSS,
      "dietz_drawdown_limit_breached_in_fixture":maximum_drawdown>=MAX_UNIT_DRAWDOWN,
      "dietz_realized_vol_limit_breached_in_fixture":vol>MAX_ANNUAL_VOL,
      "dietz_is_exact_true_time_weighted_return":False,
      "real_broker_account_flow_data_qualified":False,
      "real_s1_high_account_risk_approved":False,
      "real_t_plus_one_sale_cash_settled":False,
      "order_writer_released":False,
      "live_buy_authorized":False,"live_sell_authorized":False,
      "broker_requests":0,"broker_orders":0,
      "private_usd_dollar_amounts":None,
      "private_adjusted_returns":None,
      "activity_ids_and_transaction_times":None,
      "executable_order_payload":None,
    }


def diagnose_one_date_only_transfer(*,fixture:dict,now_utc:str)->dict:
    """Conservative one-transfer timing *diagnostic*, not a LIVE risk permit.

    Brokerage nontrade date is not assumed to be a transaction timestamp.
    Consider EVERY sampled close interval and both endpoints of intraday
    capital weighting. Reject any interval whose other uncompensated daily
    equity jumps exceed 25%, but keep all still-admissible placements.
    If multiple placements remain, or any scenario breaches HIGH 6/20/35,
    report HOLD. Do not infer a real transfer time from settlement date.
    Does not replace authenticated source completeness or operator approvals.
    """
    if (type(fixture) is not dict or fixture.get("schema")!=SCHEMA
        or fixture.get("mode")!=MODE
        or fixture.get("authenticated_broker_source") is not False
        or fixture.get("live_operator_stopped") is not True
        or fixture.get("broker_kill_switch")!="ENGAGED"
        or fixture.get("risk_level")!="HIGH"):
        raise FundingRiskStop("Date-only diagnostic requires synthetic stopped fixture")
    now=stamp(now_utc)
    h=fixture.get("portfolio_history")
    if type(h) is not dict or h.get("timeframe")!="1D":
        raise FundingRiskStop("No daily broker-shaped history")
    times=h.get("timestamp"); values=h.get("equity")
    if (type(times) is not list or type(values) is not list
        or len(times)!=len(values) or not MIN_POINTS<=len(times)<=MAX_POINTS
        or any(type(t) is not int or t<=0 for t in times)
        or any(b<=a or b-a>5*86400 for a,b in zip(times,times[1:]))):
        raise FundingRiskStop("Daily source incomplete, unordered or implausible")
    balances=[dec(x,"sampled account equity",positive=True) for x in values]
    first=datetime.fromtimestamp(times[0],timezone.utc)
    last=datetime.fromtimestamp(times[-1],timezone.utc)
    if not 0<=(now-last).total_seconds()<=10*86400:
        raise FundingRiskStop("Daily source date unverified")
    start=stamp(fixture.get("nontrade_activity_query_after"))
    if start>first:
        raise FundingRiskStop("Nontrade source misses first funded observation")
    activities=fixture.get("nontrade_activities")
    if type(activities) is not list or len(activities)>=MAX_ACTIVITY_ROWS:
        raise FundingRiskStop("Incomplete, unpaged account activity source")
    seen=set(); flow=None
    for event in activities:
        if type(event) is not dict:
            raise FundingRiskStop("Malformed account activity")
        ident=event.get("id")
        typ=event.get("activity_type")
        if (type(ident) is not str or not ident or ident in seen
            or type(typ) is not str or not typ or typ!=typ.strip()):
            raise FundingRiskStop("Missing, duplicated or invalid event identity")
        seen.add(ident)
        if typ not in TRANSFER and typ not in OTHER:
            raise FundingRiskStop("Noncash/unknown transfer cannot be bounded")
        if typ not in TRANSFER:
            continue
        if flow is not None:
            raise FundingRiskStop("More than one date-only funding transfer needs a distinct model")
        amount=dec(event.get("net_amount"),"signed nontrade cashflow")
        if amount*TRANSFER[typ]<=0:
            raise FundingRiskStop("Signed cashflow conflicts with event type")
        raw_date=event.get("date")
        if type(raw_date) is not str:
            raise FundingRiskStop("Nontrade activity lacks original date")
        from datetime import date
        try:
            dated=date.fromisoformat(raw_date)
        except ValueError:
            raise FundingRiskStop("Nontrade activity date unreadable") from None
        if dated>now.date():
            raise FundingRiskStop("Future nontrade activity date")
        if event.get("transaction_time") is not None:
            raise FundingRiskStop("This diagnostic is solely for date-only sources")
        flow=amount
    if flow is None:
        raise FundingRiskStop("No date-only funding event to analyze")
    accepted=[]
    for candidate in range(1,len(balances)):
        at_extremes=[]
        for weight in (Decimal(0),Decimal(1)):
            returns=[];unit=[Decimal(1)]
            valid=True
            for i in range(1,len(balances)):
                a,b=balances[i-1],balances[i]
                cf=flow if i==candidate else Decimal(0)
                denominator=a+weight*cf
                if denominator<=0:
                    valid=False;break
                r=(b-a-cf)/denominator
                if abs(r)>MAX_ADJUSTED_RETURN:
                    valid=False;break
                returns.append(r)
                unit.append(unit[-1]*(Decimal(1)+r))
            if not valid:
                continue
            peak=max(unit)
            end_dd=Decimal(1)-unit[-1]/peak
            vol=Decimal(str(stdev([float(v) for v in returns])*sqrt(252)))
            at_extremes.append({
                "daily":returns[-1],
                "current_drawdown":end_dd,
                "volatility":vol,
                "threshold_breached":returns[-1]<=MAX_DAILY_LOSS
                 or end_dd>=MAX_UNIT_DRAWDOWN or vol>MAX_ANNUAL_VOL,
            })
        if len(at_extremes)==2:
            accepted.append(at_extremes)
    # If no placement satisfies the existing 25% data-quality guard, this
    # is NOT proof a transfer was zero; source remains ambiguous => HOLD.
    bounded=len(accepted)==1
    all_safe=bounded and all(not row["threshold_breached"]
                             for row in accepted[0])
    return {
        "schema":"FUND100_V6_S1_UNTIMED_SINGLE_FUNDING_DIAGNOSTIC_V1",
        "status":("UNIQUE_CONDITIONALLY_PLAUSIBLE_PLACEMENT_RESEARCH_ONLY"
                  if bounded else "AMBIGUOUS_OR_INCONSISTENT_SOURCE_HOLD"),
        "candidate_sampled_intervals":len(balances)-1,
        "quality_admissible_intervals":len(accepted),
        "both_intra_interval_timing_extremes_checked":True,
        "assumes_underlying_true_session_return_within_25pct":True,
        "conditional_all_scenarios_below_original_HIGH_limits":bool(all_safe),
        "exact_economic_funding_date_proven":False,
        "funding_effective_date_inferred_as_fact":False,
        "original_source_broker_authenticated":False,
        "nontrade_activity_history_complete_from_API_proven":False,
        "account_equity_after_last_history_reconciled":False,
        "real_s1_high_account_risk_approved":False,
        "live_buy_authorized":False,"live_sell_authorized":False,
        "broker_requests":0,"broker_orders":0,
        "private_balance":None,"private_funding_amount":None,
        "private_funding_date":None,"transaction_id":None,
        "executable_order_payload":None,
    }
