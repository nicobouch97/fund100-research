"""Actual frozen-price -> lagged candidate -> HOLD/SWITCH economics (NO ORDERS).

This is a real source-wired experimental algorithm, *not* a proven forecast.
The frozen adjusted ETF history was investigated repeatedly; no independent
holdout, genuine current market quote, live risk check, or funded approval.
The 252-session total-return extrapolation is a fixed exploratory heuristic,
not a calibrated future-return promise. The decision uses ONLY completed
prices through the session BEFORE the labelled decision date.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from hashlib import sha256
from math import exp, isfinite, log, sqrt
from pathlib import Path
import json

import numpy as np
import pandas as pd

import fund100_v6_aggressive_rotation_research_v1_0 as frozen
import fund100_v6_opportunity_rebalance_economics_v1_0 as economics

SCHEMA="FUND100_V6_FROZEN_LAGGED_REAL_PRICE_OPPORTUNITY_RESEARCH_V1"
SOURCE_SHA256=frozen.FROZEN_FILE_SHA256
BENCH=frozen.BENCH
HORIZON=21
LOOKBACK=252
VOL_LIMIT=.35
SLEEVE_WEIGHTS=(Decimal(".475"),Decimal(".285"),Decimal(".190"))
MODEL="UNVALIDATED_252D_TREND_RISK_SCREEN_WITH_21D_EXTRAPOLATION"
UNIVERSE=("ACWI","EEM","XLV","XLE","XLK","IWM")
PRICE_COLUMN={s:(BENCH if s=="ACWI" else s) for s in UNIVERSE}
REAL_BROKER_ORDERS=0
LIVE_SIGNAL_APPROVED=False

class SourceSignalStop(ValueError):pass

def _jsonhash(doc):
    return sha256(json.dumps(doc,sort_keys=True,separators=(",",":")).encode("ascii")).hexdigest()

def inspect(*,history:pd.DataFrame,source_sha256:str,
            decision_index:int,synthetic_account:dict)->dict:
    """Join true immutable-source price data to a non-executable comparison.

    Caller-supplied account values are HYPOTHETICAL. Never pass these values
    to a production broker writer or claim the account is fresh/authentic.
    """
    if source_sha256!=SOURCE_SHA256:
        raise SourceSignalStop("Frozen source commitment not verified")
    try: p=frozen.validate_prices(history)
    except frozen.V6ResearchStop as exc:
        raise SourceSignalStop("Unverified genuine-source market history") from exc
    if (type(decision_index) is not int
        or not LOOKBACK+2<=decision_index<len(p)
        or type(synthetic_account) is not dict
        or synthetic_account.get("mode")!=economics.MODE
        or synthetic_account.get("signal_status")!="UNQUALIFIED_RESEARCH_HYPOTHESIS"):
        raise SourceSignalStop("Unqualified decision time or hypothetical account")
    # The decision date's bar is UNAVAILABLE at ranking and forecast time.
    prior=p.iloc[decision_index-LOOKBACK-1:decision_index]
    if len(prior)!=LOOKBACK+1:
        raise SourceSignalStop("Insufficient prior market observations")
    returns=prior.pct_change(fill_method=None).iloc[1:]
    qualified=[]
    forecasts={}
    daily_vols=[]
    for symbol,column in PRICE_COLUMN.items():
        series=prior[column].to_numpy(dtype=float)
        vals=returns[column].to_numpy(dtype=float)
        growth=log(float(series[-1]/series[0]))
        annual_vol=float(np.std(vals,ddof=1)*sqrt(252))
        if not isfinite(growth) or not isfinite(annual_vol):
            raise SourceSignalStop("Invalid lagged market trend/volatility")
        # Research extrapolation only, never claim this is calibrated alpha.
        # Cap models' input to the economic comparator bounds.
        forecast=max(-.50,min(.50,exp(growth*HORIZON/LOOKBACK)-1.0))
        forecasts[symbol]=str(Decimal(str(round(forecast,6))))
        daily_vols.append(float(np.std(vals,ddof=1)))
        if growth>0 and annual_vol<=VOL_LIMIT:
            qualified.append((growth,symbol))
    qualified.sort(key=lambda x:(-x[0],x[1]))
    chosen=[symbol for _,symbol in qualified[:len(SLEEVE_WEIGHTS)]]
    target={symbol:str(SLEEVE_WEIGHTS[i]) for i,symbol in enumerate(chosen)}
    risk_bps=int((Decimal(str(
        1.64*sqrt(HORIZON)*max(daily_vols)*10000))
        .to_integral_value(rounding=ROUND_CEILING)))
    # The existing economic comparator deliberately rejects >3000bps
    # unreviewed error assumptions; NEVER reduce that risk to force a switch.
    stamp=p.index[decision_index].strftime("%Y-%m-%d")
    last=p.index[decision_index-1].strftime("%Y-%m-%d")
    common={
        "schema":SCHEMA,"status":"RESEARCH_ONLY_FROZEN_HISTORICAL_SIGNAL_NOT_LIVE",
        "strategy_model":MODEL,"source_sha256":source_sha256,
        "decision_session":stamp,"last_price_observation_session":last,
        "all_signals_lagged_one_complete_session":True,
        "historical_source_independent_holdout":False,
        "actual_current_broker_snapshot_authenticated":False,
        "forecast_calibration_or_live_alpha_verified":False,
        "signal_horizon_sessions":HORIZON,
        "price_session_observations_used":LOOKBACK+1,
        "hypothetical_selected_symbols":chosen,
        "hypothetical_target_weights":target,
        "forecast_source":"PRIOR_252_SESSION_REALIZED_PRICE_EXTRAPOLATION_NOT_CONFIRMED_EXPECTED_RETURN",
        "estimated_uncertainty_bps":risk_bps,
        # Retrospective validation reuses the EXACT lagged forecasts fed
        # into the non-executable economic gate. Never label as live alpha.
        "hypothetical_forecast_returns":forecasts,
        "source_price_last_session_never_live_freshness":True,
        "opportunity_order_authorized":False,
        "manual_per_trade_approval_required":False,
        "broker_orders":0,
    }
    if not chosen or risk_bps>3000:
        return dict(common,decision="HOLD_UNQUALIFIED_OR_EXCESSIVELY_UNCERTAIN_SIGNAL",
                    hypothetical_economics=None)
    account=dict(synthetic_account)
    account["forecast_horizon_sessions"]=HORIZON
    held=set(account.get("positions_usd",{}))
    if not held<=set(UNIVERSE):
        raise SourceSignalStop("Unrecognised hypothetical existing holdings")
    forecast_inputs={s:forecasts[s] for s in (held|set(chosen))}
    try:
        costed=economics.evaluate(
            snapshot=account,target_weights=target,
            expected_returns=forecast_inputs,
            round_trip_side_cost_bps="35",
            forecast_uncertainty_bps=str(risk_bps),
            minimum_net_advantage_usd="0.50")
    except economics.OpportunityStop as exc:
        raise SourceSignalStop("Economic comparison rejects hypothetical input") from exc
    # Even hypothetical SWITCH is NOT permission to replace original account.
    return dict(common,
                decision="HOLD_UNTIL_INDEPENDENT_FORECAST_AND_LIVE_BROKER_VALIDATION",
                hypothetical_economics=costed)

def inspect_original_frozen(*,decision_index:int,synthetic_account:dict,
                            file:Path=Path("research_lab/frozen_history_v2.csv")):
    try:history,digest=frozen.load_frozen(file)
    except frozen.V6ResearchStop as exc:
        raise SourceSignalStop("Frozen price content not genuinely verified") from exc
    return inspect(history=history,source_sha256=digest,
                   decision_index=decision_index,synthetic_account=synthetic_account)
