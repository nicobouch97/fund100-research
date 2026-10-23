"""Existing four V6 strategies: joint block-bootstrap selection uncertainty.

Offline descriptive inference on the ALREADY INSPECTED frozen price history.
Uses the original, unchanged four NAV paths (including costs) and common ACWI
benchmark. No new strategy, broker access, parameter search, or live promotion.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SCHEMA="FUND100_V6_FOUR_EXISTING_MODELS_JOINT_BLOCK_BOOTSTRAP_V1"
MODELS=("S1_HIGH_FIXED_SECTORS","R1_WEEKLY_RELATIVE_MOMENTUM",
        "L1_VOL_MANAGED_SECTORS","R2_QUARTERLY_ABSOLUTE_TREND")
SEED=20261023
BLOCK_MEAN_SESSIONS=21
REPLICATIONS=999
ANNUAL_SESSIONS=252
NO_BROKER_ACCESS=True
NO_STRATEGY_PROMOTION=True


class SelectionStop(ValueError):
    pass


def _daily_active(paths:dict,begin:str)->tuple[np.ndarray,int,str,str]:
    """Exact same-session net active daily returns; no synthetic fills."""
    if type(paths) is not dict or set(paths)!=set(MODELS):
        raise SelectionStop("Exactly four original models required")
    if type(begin) is not str or not begin:
        raise SelectionStop("Missing predeclared historical start")
    reference=None
    benchmark=None
    columns=[]
    for model in MODELS:
        frame=paths[model]
        if (not isinstance(frame,pd.DataFrame)
            or not {"nav","benchmark"}<=set(frame.columns)
            or not isinstance(frame.index,pd.DatetimeIndex)
            or frame.index.tz is not None or frame.index.has_duplicates
            or not frame.index.is_monotonic_increasing):
            raise SelectionStop("Unverified common dated NAV path")
        window=frame.loc[begin:,["nav","benchmark"]]
        if len(window)<260:
            raise SelectionStop("Insufficient historical sessions")
        if reference is None:
            reference=window.index
        elif not reference.equals(window.index):
            raise SelectionStop("Different model market sessions")
        values=window.to_numpy(dtype=float)
        if (not np.isfinite(values).all() or (values<=0).any()):
            raise SelectionStop("Missing, nonpositive or nonfinite NAV")
        nav=values[:,0]
        ref=values[:,1]
        if benchmark is None:
            benchmark=ref
        elif not np.allclose(ref,benchmark,rtol=1e-12,atol=1e-10):
            raise SelectionStop("Model benchmark paths do not match")
        daily=nav[1:]/nav[:-1]-1
        ref_daily=ref[1:]/ref[:-1]-1
        if ((daily<=-1).any() or (ref_daily<=-1).any()
            or not np.isfinite(daily).all()):
            raise SelectionStop("Invalid original net daily returns")
        columns.append(daily-ref_daily)
    active=np.column_stack(columns)
    return (active,len(reference),reference[0].date().isoformat(),
            reference[-1].date().isoformat())


def _stationary_bootstrap_indices(n:int,*,seed:int,replications:int,
                                  block_mean:int)->np.ndarray:
    """Stationary circular blocks with shared resampling across four models.

    Each resampled day either advances the previous source session, or starts
    a fresh uniformly sampled session with probability 1 / block_mean.
    No re-ranking, re-fitting, market data download or order execution.
    """
    if (type(n) is not int or n<259 or type(seed) is not int
        or type(replications) is not int or not 99<=replications<=2000
        or type(block_mean) is not int or not 2<=block_mean<=n//4):
        raise SelectionStop("Unreviewed block bootstrap parameters")
    rng=np.random.default_rng(seed)
    ids=np.empty((replications,n),dtype=np.int32)
    ids[:,0]=rng.integers(0,n,size=replications)
    for t in range(1,n):
        restart=rng.random(replications)<1/block_mean
        fresh=rng.integers(0,n,size=replications)
        ids[:,t]=np.where(restart,fresh,(ids[:,t-1]+1)%n)
    return ids


def evaluate(paths:dict,begin:str,*,seed:int=SEED,
             replications:int=REPLICATIONS,
             block_mean:int=BLOCK_MEAN_SESSIONS)->dict:
    """Joint model-selection-aware mean-active-return sensitivity.

    This controls selection among the FOUR specified models for ONE fixed
    historical window/cost, not prior research, overlapping windows, multiple
    transaction-cost scenarios, or searched parameters. Does not imply alpha.
    """
    active,sessions,first,last=_daily_active(paths,begin)
    n=len(active)
    ids=_stationary_bootstrap_indices(n,seed=seed,
        replications=replications,block_mean=block_mean)
    observed=active.mean(axis=0)*ANNUAL_SESSIONS*100
    # Shared resampling retains same-day cross-strategy dependence and
    # geometric-length within-strategy time blocks.
    resampled=active[ids].mean(axis=1)*ANNUAL_SESSIONS*100
    centered=resampled-observed[None,:]
    null_max=centered.max(axis=1)
    observed_max=float(observed.max())
    p_family=(1+int(np.count_nonzero(null_max>=observed_max))) / (replications+1)
    quantiles=np.percentile(resampled,[2.5,97.5],axis=0)
    models={}
    for j,name in enumerate(MODELS):
        p_adj=(1+int(np.count_nonzero(null_max>=observed[j])))/(replications+1)
        models[name]={
            "historical_arithmetic_active_return_annual_pp":round(float(observed[j]),4),
            "descriptive_stationary_block_95pct_interval_annual_pp":[
                round(float(quantiles[0,j]),4),
                round(float(quantiles[1,j]),4)],
            "four_model_familywise_adjusted_one_sided_p":round(float(p_adj),4),
        }
    return {
        "schema":SCHEMA,
        "status":"ALREADY_INSPECTED_HISTORY_FOUR_MODEL_SELECTION_UNCERTAINTY_ONLY",
        "first_session":first,"last_session":last,
        "sessions":sessions,"daily_return_observations":n,
        "same_session_common_benchmark":True,
        "daily_net_of_original_model_transaction_costs":True,
        "method":"CIRCULAR_STATIONARY_BLOCK_BOOTSTRAP_SHARED_DRAWS_CENTERED_MAX_MEAN",
        "seed":seed,"replications":replications,
        "expected_block_sessions":block_mean,
        "historical_best_mean_active_model":MODELS[int(np.argmax(observed))],
        "historical_best_mean_active_annual_pp":round(observed_max,4),
        "familywise_four_model_one_sided_p_for_best":round(float(p_family),4),
        "by_original_model":models,
        "four_model_adjustment_not_entire_strategy_search":True,
        "multiple_windows_costs_and_prior_selection_NOT_adjusted":True,
        "block_length_sensitivity_NOT_estimated":True,
        "no_independent_holdout_or_predictive_alpha_proven":True,
        "strategy_selected_for_live":None,
        "funded_orders":0,"live_trading_authorized":False,
    }
