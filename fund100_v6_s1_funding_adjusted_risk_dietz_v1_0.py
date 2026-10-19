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
