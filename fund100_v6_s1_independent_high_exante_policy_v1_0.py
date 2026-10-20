"""V6-S1 separate, research-only HIGH sector/account risk launch policy.

Original V5 HIGH 25%-satellite policy is NOT the V6 47.5%-XLK policy.
The exploratory S1 manifest still lists XLE among mandatory legacy exits;
this separate policy intentionally preserves authenticated original XLE.
ALL numerical tests below use synthetic market closes, NOT LIVE returns.
NO broker, credentials, order transport, release flags or live permission.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal,InvalidOperation
from pathlib import Path

import fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0 as original
import fund100_live_portfolio_risk_v1_0 as legacy

SCHEMA="FUND100_V6_S1_SEPARATE_HIGH_RISK_EXANTE_RESEARCH_V1"
MODE="INVENTED_ADJUSTED_CLOSE_FIXTURES_ONLY"
SELL=("ACWI","EEM","XLV")
RETAIN=("XLE",)
BUY=("XLK","IWM","XLE")
TARGET={"XLK":Decimal(".475"),"XLE":Decimal(".285"),
        "IWM":Decimal(".190")}
CAP=Decimal("130.30")
MAX_GROSS=Decimal(".95")
MAX_SYMBOL=Decimal(".50")
CASH_FLOOR=Decimal(".05")
MAX_ORDER=Decimal("65.00")
MIN_BUY=Decimal("1.00")
MAX_DAILY_LOSS=Decimal(".06")
MAX_DRAWDOWN=Decimal(".20")
MAX_ACTUAL_VOL=Decimal(".35")
EXANTE_PLANNING_VOL=Decimal(".30")
MIN_CLOSES=61
MAX_CLOSES=90
RELEASE_LIVE_ORDER_EXECUTION=False

class S1HighStop(ValueError):pass

def dec(raw,label,*,positive=False):
    if type(raw) not in (str,int,Decimal):
        raise S1HighStop("Exact decimal missing for "+label)
    try:v=Decimal(str(raw))
    except (InvalidOperation,ValueError):raise S1HighStop("Invalid "+label) from None
    if not v.is_finite() or v<0 or (positive and v==0):
        raise S1HighStop("Nonpositive/negative/nonfinite "+label)
    return v

def contract():
    """Separate economic contract only; never alters source-pinned V5/S1."""
    m=original.source_controls()
    old_rule=m.get("legacy_holdings_must_be_reconciled_and_exited_before_any_buy")
    if old_rule!=["ACWI","EEM","XLE","XLV"]:
        raise S1HighStop("Source-pinned original S1 overlap discrepancy changed")
    if legacy.get_profile("HIGH").max_satellite_weight!=Decimal(".25"):
        raise S1HighStop("Legacy HIGH risk contract changed")
    if ({symbol:dec(weight,"S1 target") for symbol,weight in m["target_weights"].items()}
        !=TARGET
        or m.get("original_trial_max_capital_usd")!="130.30"
        or m.get("max_daily_account_loss_fraction")!="0.06"
        or m.get("max_peak_to_trough_account_drawdown_fraction")!="0.20"
        or m.get("max_annual_realized_account_volatility")!="0.35"
        or m.get("cash_reserve_fraction")!="0.05"
        or m.get("live_order_execution_released") is not False
        or m.get("live_operator_trading_enabled") is not False
        or m.get("live_environment_kill_switch")!="ENGAGED"):
        raise S1HighStop("Original V6 source/risk or LIVE STOP changed")
    if sum(TARGET.values())!=MAX_GROSS or max(TARGET.values())>MAX_SYMBOL:
        raise S1HighStop("Independent concentrated allocation contract incoherent")
    return {
      "schema":SCHEMA,
      "legacy_manifest_contains_xle_for_unnecessary_exit":True,
      "original_source_remains_unchanged":True,
      "corrected_v6_only_staged_exits":SELL,
      "retain_original_xle_only_while_below_target":True,
      "original_xle_not_a_mandatory_exit":True,
      "target_weights":{s:str(x) for s,x in TARGET.items()},
      "separate_v6_35_percent_realized_vol_hard_limit":"0.35",
      "exante_illustrative_planning_vol_limit":"0.30",
      "short_clean_ledger_warmup_requires_separate_live_release":True,
      "daily_loss_stop":"0.06","drawdown_stop":"0.20",
      "max_pilot_capital":"130.30","cash_floor":"0.05",
      "live_broker_authenticated":False,
      "actual_risk_history_verified":False,
      "original_live_operator_stopped":True,
      "order_submission_authorized":False,
      "broker_requests":0,"order_posts":0,
    }

def _day(raw):
    if type(raw) is not str or len(raw)!=10:
        raise S1HighStop("Missing canonical date")
    try:d=date.fromisoformat(raw)
    except ValueError:raise S1HighStop("Bad adjusted-close date") from None
    if d.isoformat()!=raw:
        raise S1HighStop("Noncanonical adjusted-close date")
    return d

def project_vol(*,fixtures:dict,now_date:str)->dict:
    """Volatility of fixed weighted daily returns with 5% nominal cash.

    The prices are explicitly INVENTED; this is NOT actual LIVE evidence.
    An authentic feed + source proof is a separate future release.
    """
    contract()
    if (type(fixtures) is not dict
        or set(fixtures)!={"mode","prices","source_authenticated_live"}
        or fixtures["mode"]!=MODE
        or fixtures["source_authenticated_live"] is not False):
        raise S1HighStop("Only invented adjusted-close market fixtures supported")
    price_data=fixtures["prices"]
    if type(price_data) is not dict or set(price_data)!=set(TARGET):
        raise S1HighStop("Missing or extra ETF close history")
    today=_day(now_date)
    aligned=None;returns={}
    for symbol in TARGET:
        rows=price_data[symbol]
        if type(rows) is not list or not MIN_CLOSES<=len(rows)<=MAX_CLOSES:
            raise S1HighStop("Insufficient comparable adjusted-close observations")
        dates=[];prices=[]
        for row in rows:
            if type(row) is not dict or set(row)!={"date","adjusted_close"}:
                raise S1HighStop("Malformed adjusted-close price row")
            d=_day(row["date"])
            p=dec(row["adjusted_close"],symbol+" market-adjusted close",positive=True)
            dates.append(d);prices.append(p)
        if (any(not 1<=(b-a).days<=5 for a,b in zip(dates,dates[1:]))
            or (today-dates[-1]).days<0 or (today-dates[-1]).days>7):
            raise S1HighStop("Unaligned or stale adjusted-close source dates")
        if aligned is None:aligned=dates
        elif dates!=aligned:
            raise S1HighStop("ETF date windows are unaligned")
        series=[(b/a)-1 for a,b in zip(prices,prices[1:])]
        if any(abs(x)>Decimal(".30") for x in series):
            raise S1HighStop("Extreme return/adjustment ambiguity: manual pricing review")
        returns[symbol]=series
    weighted=[
      sum((TARGET[s]*returns[s][i] for s in TARGET),Decimal(0))
      for i in range(len(aligned)-1)
    ]
    n=len(weighted)
    avg=sum(weighted,Decimal(0))/Decimal(n)
    var=sum(((r-avg)**2 for r in weighted),Decimal(0))/Decimal(n-1)
    annual=(var*Decimal(252)).sqrt()
    return {
      "schema":SCHEMA,"source_mode":MODE,
      "price_observations":len(aligned),
      "aligned_daily_returns":n,
      "illustrative_annualized_volatility":str(annual.quantize(Decimal(".000001"))),
      "exante_30pct_planning_threshold_passed":annual<=EXANTE_PLANNING_VOL,
      "actual_v6_35pct_volatility_limit_verified":False,
      "cashflow_adjusted_original_v5_return_used":False,
      "authentic_live_account_risk_verified":False,
      "requires_clean_live_launch_baseline":True,
      "live_buy_sell_authorized":False,
      "source_etf_daily_prices_verified":False,
      "broker_get_requests":0,"broker_order_posts":0,
      "private_financial_data_logged":False,
    }

def hypothetical_buy_envelope(*,snapshot:dict)->dict:
    """Separate V6 HIGH 5%-cash envelope; NEVER emits an executable order."""
    contract()
    if (type(snapshot) is not dict
        or snapshot.get("mode")!=MODE
        or snapshot.get("source_authenticated_live") is not False
        or snapshot.get("risk_level")!="HIGH"
        or snapshot.get("operator_stopped") is not True
        or snapshot.get("kill_switch")!="ENGAGED"):
        raise S1HighStop("Original HIGH STOP and synthetic-only inputs required")
    equity=dec(snapshot.get("equity"),"synthetic equity",positive=True)
    cash=dec(snapshot.get("cash"),"synthetic cash")
    settled=dec(snapshot.get("settled_cash"),"synthetic settled cash")
    order_cost=dec(snapshot.get("estimated_cost"),"execution cost buffer")
    amount=dec(snapshot.get("buy_notional"),"BUY notional",positive=True)
    symbol=snapshot.get("buy_symbol")
    original_positions=snapshot.get("positions")
    if (symbol not in BUY or type(original_positions) is not dict
        or not set(original_positions)<=set(BUY)|set(SELL)):
        raise S1HighStop("Unapproved BUY symbol or unknown original positions")
    pos={s:dec(x,s+" synthetic market value") for s,x in original_positions.items()}
    if set(pos)&set(SELL):
        return _hold("BLOCKED_LEGACY_ACWI_EEM_XLV_NOT_FLAT")
    if snapshot.get("synthetic_independently_settled") is not True:
        return _hold("BLOCKED_SETTLED_CASH_SOURCE_UNAVAILABLE")
    if amount<MIN_BUY or amount>MAX_ORDER or settled>cash or cash>equity:
        return _hold("BLOCKED_ORDER_SIZE_OR_CASH")
    if abs(sum(pos.values())+cash-equity)>Decimal(".02"):
        return _hold("BLOCKED_ACCOUNT_GROSS_CASH_MISMATCH")
    cap=min(equity,CAP)
    if pos.get("XLE",Decimal(0))>cap*TARGET["XLE"]:
        return _hold("BLOCKED_ORIGINAL_XLE_OVERWEIGHT_REVIEW_NOT_SELL")
    if (cash-amount-order_cost<equity*CASH_FLOOR
        or settled-amount-order_cost<equity*CASH_FLOOR):
        return _hold("BLOCKED_FIVE_PERCENT_CASH_FLOOR")
    gross=sum(pos.values())+amount
    if gross>equity*MAX_GROSS:
        return _hold("BLOCKED_NINETY_FIVE_PERCENT_GROSS")
    if pos.get(symbol,Decimal(0))+amount>equity*MAX_SYMBOL:
        return _hold("BLOCKED_FIFTY_PERCENT_SINGLE_SYMBOL")
    return _hold("HYPOTHETICAL_V6_ENVELOPE_PASSED_NO_TRADE_AUTHORIZATION")

def _hold(status):
    return {"schema":SCHEMA,"stage":status,
            "source_mode":MODE,
            "hypothetical_envelope_only":True,
            "cash_verified_by_live_broker":False,
            "real_account_loss_or_drawdown_verified":False,
            "actual_35pct_volatility_verified":False,
            "private_ledger_continuity_verified":False,
            "original_live_order_execution_released":False,
            "broker_order_posts":0,"broker_requests":0,
            "live_order_authorized":False,"order":None}


def _signed(raw,label):
    if type(raw) not in (str,int,Decimal):
        raise S1HighStop("Missing signed "+label)
    try:value=Decimal(str(raw))
    except (InvalidOperation,ValueError):
        raise S1HighStop("Malformed signed "+label) from None
    if not value.is_finite() or value<Decimal("-1") or value>Decimal("1"):
        raise S1HighStop("Signed account risk outside reasonable limits")
    return value

def hypothetical_warmup_risk(*,snapshot:dict)->dict:
    """Research-only clean post-migration 6/20/35 bridge.

    A 60-session ETF price proxy is NOT live realized-volatility.
    No actual V6 LIVE risk release without independently reviewed source.
    """
    contract()
    if (type(snapshot) is not dict
        or snapshot.get("mode")!=MODE
        or snapshot.get("source_authenticated_live") is not False
        or snapshot.get("operator_stopped") is not True
        or snapshot.get("kill_switch")!="ENGAGED"
        or snapshot.get("post_migration_clean_baseline_proven_synthetically") is not True
        or snapshot.get("external_flows_reconciled_synthetically") is not True):
        return _hold("BLOCKED_MISSING_CLEAN_V6_ACCOUNT_RISK_BASELINE")
    closes=snapshot.get("completed_strategy_daily_closes")
    if type(closes) is not int or closes<1:
        return _hold("BLOCKED_NO_REAL_DAILY_ACCOUNT_RISK_OBSERVATION")
    daily=_signed(snapshot.get("daily_return"),"clean V6 daily return")
    drawdown=_signed(snapshot.get("peak_to_trough_drawdown"),"clean V6 drawdown")
    if drawdown>0:
        raise S1HighStop("Drawdown cannot be positive")
    if daily<=-MAX_DAILY_LOSS or drawdown<=-MAX_DRAWDOWN:
        return _hold("BLOCKED_SIX_PERCENT_DAILY_OR_TWENTY_PERCENT_DRAWDOWN")
    exante=dec(snapshot.get("aligned_etf_exante_vol"),"illustrative ex-ante volatility")
    if exante>EXANTE_PLANNING_VOL:
        return _hold("BLOCKED_EXANTE_VOLATILITY_NOT_BELOW_30PCT")
    if closes<6:
        if snapshot.get("actual_annual_volatility") is not None:
            raise S1HighStop("Do not claim stable realized volatility before 6 closes")
        return _hold("HYPOTHETICAL_WARMUP_EXANTE_PROXY_ONLY_NOT_ACTUAL_35PCT_PROOF")
    actual=dec(snapshot.get("actual_annual_volatility"),"synthetic clean actual vol")
    if actual>MAX_ACTUAL_VOL:
        return _hold("BLOCKED_THIRTY_FIVE_PERCENT_REALIZED_VOLATILITY")
    return _hold("HYPOTHETICAL_SIX_TWENTY_THIRTYFIVE_RISK_ENVELOPE_NO_LIVE_AUTH")
