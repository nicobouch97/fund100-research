"""V7-X7 pure research: compare flow-neutral fund NAV with a passive ETF index.

Synthetic, explicit mark/flow boundary semantics only. A deposit is NOT profit.
There is no broker connection, verified price feed, strategy signal or order.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import re

SCHEMA="FUND100_V7_X7_FLOW_NEUTRAL_FUND_VS_BENCHMARK_RESEARCH_V1"
MODE="SYNTHETIC_UNAUTHENTICATED_PORTFOLIO_AND_INDEX_ONLY"
LIVE_PILOT_PRINCIPAL_CEILING_USD="130.30"
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_EXECUTION_ENABLED=False
MAX_MARKS=4000
MIN_NAV=Decimal("0.01")
MAX_AMOUNT=Decimal("1000000000000")

class PerformanceStop(ValueError):
    pass

def _amount(s,label,*,signed=False):
    if type(s) is not str or re.fullmatch(
            r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?",s) is None:
        raise PerformanceStop("Uncanonical "+label)
    try:
        v=Decimal(s)
    except InvalidOperation:
        raise PerformanceStop("Invalid "+label) from None
    if not v.is_finite() or v>MAX_AMOUNT or v < (-MAX_AMOUNT if signed else 0):
        raise PerformanceStop("Unbounded "+label)
    return v

def _stamp(value):
    if (type(value) is not str
        or re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",value) is None):
        raise PerformanceStop("Timestamp must be explicit UTC second")
    try:
        result=datetime.strptime(value,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise PerformanceStop("Invalid UTC timestamp") from None
    return result

def _fmt(v):
    return format(v,"f")

def evaluate(*,marks,benchmark_symbol="ACWI"):
    """Unitise NAV across independently documented boundary-timed external flows.

    A valuation gap containing a flow with UNKNOWN timestamp cannot be
    retrospectively interpolated. BEFORE means after the prior NAV mark but
    before this period's return; AFTER means after its return before this NAV.
    Never label internal ETF sale proceeds, dividends or fees external flows.
    """
    if (type(benchmark_symbol) is not str
        or benchmark_symbol not in {"ACWI","SPY"}
        or type(marks) is not list or not 2<=len(marks)<=MAX_MARKS):
        raise PerformanceStop("Unsupported research benchmark or observations")
    parsed=[]
    prev_t=None
    for i,row in enumerate(marks):
        if (type(row) is not dict or set(row)!={
                "asof_utc","account_nav_usd","external_flow_usd",
                "flow_boundary","benchmark_adjusted_index","mode"}):
            raise PerformanceStop("Incomplete mark or external-flow chronology")
        if row["mode"]!=MODE:
            raise PerformanceStop("Unverified or pretended real brokerage source")
        timestamp=_stamp(row["asof_utc"])
        if prev_t is not None and timestamp<=prev_t:
            raise PerformanceStop("Stale, duplicated or unsorted account marks")
        prev_t=timestamp
        nav=_amount(row["account_nav_usd"],"account NAV")
        index=_amount(row["benchmark_adjusted_index"],"benchmark adjusted index")
        flow=_amount(row["external_flow_usd"],"external cash movement",signed=True)
        boundary=row["flow_boundary"]
        if nav<MIN_NAV or index<=0:
            raise PerformanceStop("Invalid positive NAV or benchmark index")
        if i==0:
            if flow!=0 or boundary!="NONE":
                raise PerformanceStop("Initial mark defines clean performance inception")
        elif flow==0:
            if boundary!="NONE":
                raise PerformanceStop("No flow must use NONE boundary")
        elif boundary not in ("BEFORE_PERIOD_RETURN","AFTER_PERIOD_RETURN"):
            raise PerformanceStop("Flow without independently known valuation boundary")
        parsed.append((timestamp,nav,index,flow,boundary))
    fund_unit=Decimal(1)
    bench_unit=Decimal(1)
    peak=Decimal(1)
    worst_dd=Decimal(0)
    total_flows=Decimal(0)
    ledger=[]
    for i in range(1,len(parsed)):
        _,before_nav,before_index,_,_=parsed[i-1]
        current_t,after_nav,after_index,flow,boundary=parsed[i]
        if boundary=="BEFORE_PERIOD_RETURN":
            invested_start=before_nav+flow
            invested_end=after_nav
        elif boundary=="AFTER_PERIOD_RETURN":
            invested_start=before_nav
            invested_end=after_nav-flow
        else:
            invested_start=before_nav
            invested_end=after_nav
        if invested_start<=0 or invested_end<0:
            raise PerformanceStop("Boundary flow would invent impossible invested NAV")
        net_fund_factor=invested_end/invested_start
        benchmark_factor=after_index/before_index
        if net_fund_factor<0 or benchmark_factor<=0:
            raise PerformanceStop("Invalid interval return factor")
        total_flows+=flow
        fund_unit*=net_fund_factor
        bench_unit*=benchmark_factor
        peak=max(peak,fund_unit)
        worst_dd=min(worst_dd,fund_unit/peak-Decimal(1))
        ledger.append({
            "asof_utc":current_t.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "external_flow_usd":_fmt(flow),
            "verified_flow_boundary_for_this_synthetic_example":boundary,
            "flow_neutral_fund_interval_return_fraction":_fmt(net_fund_factor-1),
            "benchmark_interval_return_fraction":_fmt(benchmark_factor-1),
            "account_nav_includes_external_flows":True,
        })
    first_nav=parsed[0][1]
    final_nav=parsed[-1][1]
    net_pnl=final_nav-first_nav-total_flows
    return {
        "schema":SCHEMA,
        "status":"RESEARCH_FLOW_NEUTRAL_COMPARISON_NOT_LIVE_PERFORMANCE",
        "benchmark":benchmark_symbol,
        "account_mark_count":len(parsed),
        "observed_intervals":len(ledger),
        "starting_synthetic_nav_usd":_fmt(first_nav),
        "ending_synthetic_nav_usd":_fmt(final_nav),
        "net_external_contributions_usd":_fmt(total_flows),
        "accounting_gain_excluding_net_external_flows_usd":_fmt(net_pnl),
        "fund_unitised_growth":_fmt(fund_unit),
        "benchmark_unitised_growth":_fmt(bench_unit),
        "fund_flow_neutral_cumulative_return_pct":_fmt((fund_unit-1)*100),
        "benchmark_same_period_cumulative_return_pct":_fmt((bench_unit-1)*100),
        "fund_minus_benchmark_cumulative_return_pp":_fmt((fund_unit-bench_unit)*100),
        "fund_unitised_max_drawdown_pct":_fmt(worst_dd*100),
        "intervals":ledger,
        "benchmark_is_not_risk_matched_or_funded_costed":True,
        "external_flows_are_only_deposits_or_withdrawals":True,
        "actual_broker_cashflows_and_prices_authenticated":False,
        "does_not_measure_live_track_record_or_alpha":True,
        "funded_principal_ceiling_usd_unchanged":LIVE_PILOT_PRINCIPAL_CEILING_USD,
        "capital_ceiling_increase_authorized":False,
        "portfolio_rebalance_authorized":False,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "live_authorized":False,
    }
