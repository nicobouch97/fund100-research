"""V7-X10 brokerless recovery admission: ACCOUNT HARD STOP vs strategy pause.

A hard account stop is never rearmed by market recovery or a model signal.
A softer strategy pause may permit further RESEARCH comparison only when
two subsequent source-vintage checkpoints, account-risk facts, settlement
and the existing X6 opportunity economics independently pass. The model
does NOT verify sources, execute a trade, release a broker, lift the original
funding cap, approve a strategy or validate an alpha forecast.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re

import fund100_v7_x6_costed_multiasset_opportunity_selector_v1_0 as economics

SCHEMA="FUND100_V7_X10_HARD_STOP_VS_SOFT_PAUSE_RECOVERY_ADMISSION_V1"
MODE="SYNTHETIC_UNAUTHENTICATED_RISK_AND_SOURCE_FIXTURES"
PAUSES=("ACCOUNT_HARD_STOP","STRATEGY_SOFT_PAUSE")
LATEST_CAPTURE_MAX_AGE_DAYS=5
SOFT_PAUSE_MIN_CALENDAR_DAYS=5
RESEARCH_RECOVERY_VOL_CEILING=Decimal("0.30")
HIGH_DAILY_LIMIT=Decimal("-0.06")
HIGH_DRAW_LIMIT=Decimal("-0.20")
HIGH_VOL_LIMIT=Decimal("0.35")
REQUIRED_SOURCE_CHECKPOINTS=2
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_TRADING_ENABLED=False
LIVE_CAP_USD="130.30"

class RecoveryStop(ValueError): pass

def _decimal(value,label,*,signed=False):
    if type(value) is not str or re.fullmatch(
            r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?",value) is None:
        raise RecoveryStop("Uncanonical "+label)
    number=Decimal(value)
    if number>Decimal("10000000000") or number<(
            Decimal("-1") if signed else Decimal("0")):
        raise RecoveryStop("Invalid bound for "+label)
    return number

def _utc(raw):
    if (type(raw) is not str or
        re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z",raw) is None):
        raise RecoveryStop("Missing canonical UTC receipt")
    try:
        return datetime.strptime(raw,"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        raise RecoveryStop("Impossible UTC receipt") from None

def _result(reason,eligible=False,summary=None):
    return {
        "schema":SCHEMA,
        "status":"RESEARCH_RECOVERY_ADMISSION_ONLY" if eligible else "HOLD_NO_RECOVERY_ADMISSION",
        "reason":reason,
        "synthetic_soft_pause_recovery_candidate":eligible,
        "hard_account_stop_cleared":False,
        "original_live_operator_stop_cleared":False,
        "original_live_environment_kill_cleared":False,
        "standing_live_reentry_mandate_authenticated":False,
        "input_forecasts_proven_predictive":False,
        "eligible_to_research_more_not_to_place_orders":eligible,
        "cannot_force_resume_a_hard_account_risk_stop":True,
        "authentic_quote_fill_cash_or_risk_history_available":False,
        "capital_authority_usd_unchanged":LIVE_CAP_USD,
        "real_broker_gets":BROKER_GETS,
        "real_broker_posts":BROKER_POSTS,
        "real_broker_orders":BROKER_ORDERS,
        "live_trading_authorized":False,
        "hypothetical_context":summary or {},
    }

def assess(*,snapshot:dict,captures:list,candidate_target_weights:dict,
           expected_returns_fraction:dict,asset_spec:dict,
           hypothetical_capital_limit_usd:str,forecast_horizon_sessions:int,
           now_utc:str):
    """Reject incomplete source chronology; synthetic PASS never means LIVE GO.

    Market-vintage checks are timestamped *after* the pause and must be
    separated by complete calendar days. Never re-label independently
    backfilled adjusted prices as contemporary source-authenticated marks.
    """
    if (type(snapshot) is not dict or set(snapshot)!={
            "mode","pause_kind","pause_recorded_utc","operator_stop",
            "environment_kill_engaged","fully_flat","open_order_count",
            "equity_usd","cash_usd","settled_cash_usd","last_daily_return",
            "account_drawdown","account_annual_volatility","risk_measurement_utc"}
        or snapshot["mode"]!=MODE or snapshot["pause_kind"] not in PAUSES
        or type(snapshot["operator_stop"]) is not bool
        or type(snapshot["environment_kill_engaged"]) is not bool
        or type(snapshot["fully_flat"]) is not bool
        or type(snapshot["open_order_count"]) is not int
        or not 0<=snapshot["open_order_count"]<=100000):
        raise RecoveryStop("Untrusted paused synthetic account snapshot")
    now=_utc(now_utc)
    paused=_utc(snapshot["pause_recorded_utc"])
    observed=_utc(snapshot["risk_measurement_utc"])
    if paused>=now or not paused<=observed<=now or (now-observed).total_seconds()>86400:
        raise RecoveryStop("Future, stale or pre-pause risk observation")
    equity=_decimal(snapshot["equity_usd"],"synthetic NAV")
    cash=_decimal(snapshot["cash_usd"],"synthetic cash")
    settled=_decimal(snapshot["settled_cash_usd"],"hypothetical settled cash")
    daily=_decimal(snapshot["last_daily_return"],"daily account return",signed=True)
    drawdown=_decimal(snapshot["account_drawdown"],"risk drawdown",signed=True)
    vol=_decimal(snapshot["account_annual_volatility"],"annualized volatility")
    if (equity<=0 or cash>equity or settled>cash or
        drawdown>0 or daily>Decimal("2") or vol>Decimal("2")):
        raise RecoveryStop("Synthetic account values do not reconcile")
    # Validate every proposed capture BEFORE deciding on HOLD; do not allow
    # malformed source arrays to be treated as verified evidence.
    if type(captures) is not list or len(captures)!=REQUIRED_SOURCE_CHECKPOINTS:
        raise RecoveryStop("Exactly two independent dated research captures required")
    earlier=None
    replay=[]
    for c in captures:
        if type(c) is not dict or set(c)!={
                "source_mode","price_session","captured_utc","risk_vol_63_fraction",
                "daily_benchmark_return_fraction"}:
            raise RecoveryStop("Invalid historical source-vintage checkpoint")
        if c["source_mode"]!=MODE:
            raise RecoveryStop("Research source is not actually authenticated")
        session=c["price_session"]
        if type(session) is not str or not re.fullmatch(r"20[0-9]{2}-[0-9]{2}-[0-9]{2}",session):
            raise RecoveryStop("Unbounded market session")
        try:
            stamp=datetime.strptime(session,"%Y-%m-%d").date()
        except ValueError:
            raise RecoveryStop("Impossible market source session") from None
        captured=_utc(c["captured_utc"])
        if (captured.date()<=stamp or captured<=paused or captured>now or
            stamp<=paused.date() or (now-captured).days>20):
            raise RecoveryStop("Source future, stale or not post-pause")
        if stamp.weekday()>4:
            raise RecoveryStop("Weekend is not a completed US ETF trading session")
        if earlier is not None and (
            stamp<=earlier[0] or captured<=earlier[1]):
            raise RecoveryStop("Duplicate or reversed market vintages")
        earlier=(stamp,captured)
        v=_decimal(c["risk_vol_63_fraction"],"63-session market volatility")
        ret=_decimal(c["daily_benchmark_return_fraction"],"benchmark daily return",signed=True)
        if v>Decimal("2") or ret>Decimal("2"):
            raise RecoveryStop("Impossible synthetic source return")
        replay.append((stamp,captured,v,ret))
    if (now-replay[-1][1]).total_seconds()>LATEST_CAPTURE_MAX_AGE_DAYS*86400:
        return _result("HOLD_RECOVERY_SOURCE_TOO_OLD")
    if (now-paused).total_seconds()<SOFT_PAUSE_MIN_CALENDAR_DAYS*86400:
        return _result("HOLD_RESEARCH_PAUSE_COOLDOWN_NOT_MET")
    # A hard account breach is NOT merely a soft signal pause. Neither
    # a later good price mark nor a favorable forecast can clear it.
    if snapshot["pause_kind"]=="ACCOUNT_HARD_STOP":
        return _result("BLOCKED_ACCOUNT_HARD_STOP_REQUIRES_INDEPENDENT_RELEASE")
    if snapshot["operator_stop"] or snapshot["environment_kill_engaged"]:
        return _result("BLOCKED_OPERATOR_STOP_OR_BROKER_KILL")
    if not snapshot["fully_flat"] or snapshot["open_order_count"]:
        return _result("HOLD_ACCOUNT_NOT_FLAT_OR_ORDERS_UNRECONCILED")
    if daily<=HIGH_DAILY_LIMIT or drawdown<=HIGH_DRAW_LIMIT or vol>HIGH_VOL_LIMIT:
        return _result("HOLD_POST_PAUSE_ACCOUNT_RISK_OUTSIDE_HIGH_LIMITS")
    if settled<=0 or cash<=0 or settled<cash:
        return _result("HOLD_SETTLED_CASH_SOURCE_AND_RECONCILIATION_REQUIRED")
    if any(v>RESEARCH_RECOVERY_VOL_CEILING or r<=HIGH_DAILY_LIMIT
           for _,_,v,r in replay):
        return _result("HOLD_POST_PAUSE_MARKET_STRESS_NOT_CLEARED")
    # Recompute X6 economics FROM THIS EXACT synthetic NAV and settled cash,
    # never accept a favorable economic report for a different account.
    if hypothetical_capital_limit_usd!=snapshot["equity_usd"]:
        raise RecoveryStop("Reentry opportunity uses a different NAV ceiling")
    try:
        economic_report=economics.select(
            capital_nav_usd=snapshot["equity_usd"],
            prospective_cap_usd=hypothetical_capital_limit_usd,
            settled_cash_usd=snapshot["settled_cash_usd"],
            current_holdings_usd={},
            candidate_target_weights=candidate_target_weights,
            expected_returns_fraction=expected_returns_fraction,
            asset_spec=asset_spec,
            forecast_horizon_sessions=forecast_horizon_sessions)
    except (economics.SelectionStop, economics.capacity.CapacityStop) as exc:
        raise RecoveryStop("Unqualified or inconsistent synthetic X6 inputs") from exc
    winner=economic_report.get("preferred_research_candidate")
    outcomes=economic_report.get("candidate_outcomes")
    if (not isinstance(outcomes,dict) or winner not in outcomes):
        return _result("HOLD_NO_COSTED_OPPORTUNITY_TO_REENTER")
    item=outcomes[winner]
    if (type(item) is not dict or
        item.get("state")!="RESEARCH_SWITCH_SYNTHETIC_CASH_SUFFICIENT" or
        item.get("funding_status")!="HYPOTHETICAL_SETTLED_CASH_SUFFICIENT_ONLY" or
        item.get("capacity_and_risk_warnings")!=[] or
        item.get("broker_order_intent") is not None):
        return _result("HOLD_SWITCH_NOT_COST_SETTLEMENT_AND_CAPACITY_ELIGIBLE")
    return _result("RESEARCH_ONLY_SOFT_PAUSE_CONDITIONS_MET_NOT_A_LIVE_SIGNAL",
                   True,{
                       "selected_synthetic_hypothesis":winner,
                       "market_vintages_count":len(replay),
                       "prior_pause_utc":snapshot["pause_recorded_utc"],
                       "costed_hypothesis_net_advantage_usd":
                       item["hypothetical_net_advantage_usd"],
                       "forecast_provenance":"UNQUALIFIED_SYNTHETIC",
                   })
