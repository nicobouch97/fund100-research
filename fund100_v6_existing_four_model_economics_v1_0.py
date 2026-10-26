"""Source-exact historical economics for FOUR previously implemented V6 models.

NO new signal parameters, candidate optimisation or order capability. Reuses
each frozen original signal engine with its original trade timing, 5/15/35bps
one-way costs and the SAME ACWI market-price benchmark. Outputs comparable
realized risk, cash, turnover and existing HIGH guard compatibility metrics.
This history is already studied, not an independent test or predicted alpha.
"""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_v6_aggressive_rotation_research_v1_0 as r1
import fund100_v6_r1_vs_s1_historical_comparison_v1_0 as s1
import fund100_v6_fast_launch_vol_regime_l1_v1_0 as l1
import fund100_v6_quarterly_concentrated_trend_r2_v1_0 as r2
import fund100_v6_four_model_selection_uncertainty_v1_0 as selection
import fund100_v6_four_model_walkforward_selector_v1_0 as adaptive

SCHEMA="FUND100_V6_FOUR_EXISTING_STRATEGIES_COMMON_HISTORY_ECONOMICS_V1"
MODELS=("S1_HIGH_FIXED_SECTORS","R1_WEEKLY_RELATIVE_MOMENTUM",
        "L1_VOL_MANAGED_SECTORS","R2_QUARTERLY_ABSOLUTE_TREND")
WINDOWS={"since_2014":"2014-01-01","since_2020":"2020-01-01",
         "since_2023":"2023-01-01"}
COSTS=(5,15,35)
# ETF-level, not constituent-stock, exposures from each original post-close path.
WEIGHT_SYMBOLS={MODELS[0]:tuple(r1.UNIVERSE),MODELS[1]:tuple(r1.UNIVERSE),
                MODELS[2]:tuple(l1.NAMES),MODELS[3]:tuple(r2.UNIVERSE)}
ALL_ETFS=tuple(sorted({symbol for symbols in WEIGHT_SYMBOLS.values()
                       for symbol in symbols}))
NO_NEW_SIGNAL_PARAMETERS=True
NO_BROKER_NETWORK=True
NO_ORDER_RELEASE=True
NO_FUTURE_PROFIT_CLAIM=True

class EconomicsStop(ValueError):
    pass

def _normalized(label:str,path:pd.DataFrame)->pd.DataFrame:
    cols={
        MODELS[0]:("v6_nav","one_way_turnover","gross_equity_exposure","cash_weight"),
        MODELS[1]:("v6_nav","one_way_turnover","gross_equity_exposure","cash_weight"),
        MODELS[2]:("nav","turnover","gross_risk_exposure","cash"),
        MODELS[3]:("r2_nav","gross_turnover","gross_equity_exposure","cash_weight"),
    }
    if label not in cols or not isinstance(path,pd.DataFrame):
        raise EconomicsStop("Unknown original frozen strategy")
    a,b,c,d=cols[label]
    try:
        out=path.loc[:,[a,"acwi_nav",b,c,d]].copy()
    except KeyError:
        raise EconomicsStop("Original strategy backtest changed reporting contract") from None
    out.columns=["nav","benchmark","turnover","gross","cash"]
    symbols=WEIGHT_SYMBOLS[label]
    if any("weight_"+s not in path.columns for s in symbols):
        raise EconomicsStop("Original post-close ETF weights unavailable")
    for symbol in symbols:
        out["weight_"+symbol]=path["weight_"+symbol]
    if (out.index.has_duplicates or not out.index.is_monotonic_increasing
        or not isinstance(out.index,pd.DatetimeIndex) or out.index.tz is not None
        or not np.isfinite(out.to_numpy(dtype=float)).all()):
        raise EconomicsStop("Original NAV dates/values invalid")
    if ((out["nav"]<=0).any() or (out["benchmark"]<=0).any()
        or (out["turnover"]<0).any()
        or (out["gross"]<-1e-8).any()
        or (out["gross"]>1+1e-8).any()
        or ((out["cash"]+out["gross"]-1).abs()>1e-8).any()):
        raise EconomicsStop("Original NAV, leverage or cash invalid")
    weights=out[["weight_"+s for s in symbols]]
    if ((weights<-1e-10).any().any() or (weights>1+1e-10).any().any()
        or not np.allclose(weights.sum(axis=1).to_numpy(),out["gross"].to_numpy(),
                            atol=1e-8,rtol=0)):
        raise EconomicsStop("Original ETF weights disagree with reported exposure")
    return out

def _all_paths(prices:pd.DataFrame,cost:int):
    if cost not in COSTS or type(cost) is not int:
        raise EconomicsStop("Only original 5/15/35bps research costs supported")
    raw={
        MODELS[0]:s1.fixed_backtest(prices,cost_bps=cost),
        MODELS[1]:r1.backtest(prices,cost_bps=cost),
        MODELS[2]:l1.simulate(prices,cost_bps=cost),
        MODELS[3]:r2.simulate(prices,cost_bps=cost),
    }
    result={name:_normalized(name,path) for name,path in raw.items()}
    original=result[MODELS[0]]
    for name,frame in result.items():
        if (not original.index.equals(frame.index)
            or not np.allclose(original["benchmark"],frame["benchmark"],
                               rtol=1e-11,atol=1e-8)):
            raise EconomicsStop("Four independent models disagree about benchmark history")
    return result

def _fixed_blend_etf_lookthrough(paths:dict,begin:str)->dict:
    """Exact ETF-level exposures of the fixed 25%-per-model synthetic blend.

    Each model sleeve is purchased at the common first eligible quarter close,
    then its *units* are held; the four sleeve weights drift with their original
    costed NAVs. The original after-close ETF holdings drift/rebalance within
    each model. No constituent-stock, issuer, sector or ETF-fund look-through is
    inferred. This is descriptive historical research, never an order plan.
    """
    if type(paths) is not dict or set(paths)!=set(MODELS):
        raise EconomicsStop("Exactly four original model paths required")
    dates=paths[MODELS[0]].index
    if (not isinstance(dates,pd.DatetimeIndex) or dates.tz is not None
        or dates.has_duplicates or not dates.is_monotonic_increasing):
        raise EconomicsStop("Invalid historical look-through dates")
    for model in MODELS:
        frame=paths[model]
        if not isinstance(frame,pd.DataFrame) or not dates.equals(frame.index):
            raise EconomicsStop("Historical look-through dates differ")
        if any("weight_"+s not in frame.columns for s in WEIGHT_SYMBOLS[model]):
            raise EconomicsStop("Missing original ETF exposure observations")
        original=frame[["weight_"+s for s in WEIGHT_SYMBOLS[model]]].to_numpy(dtype=float)
        gross=frame["gross"].to_numpy(dtype=float)
        if (not np.isfinite(original).all() or not np.isfinite(gross).all()
            or (original<-1e-10).any() or (original>1+1e-10).any()
            or not np.allclose(original.sum(axis=1),gross,rtol=0,atol=1e-8)):
            raise EconomicsStop("Inconsistent original model ETF exposure")
    first=next((t for t in range(adaptive.TRAINING_RETURNS+1,len(dates))
                if dates[t].to_period("Q")!=dates[t-1].to_period("Q")),None)
    if first is None:
        raise EconomicsStop("No common eligible fixed-blend entry")
    start=max(first,int(dates.searchsorted(pd.Timestamp(begin))))
    if len(dates)-start<260:
        raise EconomicsStop("Insufficient eligible look-through sessions")
    levels=np.column_stack([paths[m]["nav"].to_numpy(dtype=float)
                            for m in MODELS])
    if not np.isfinite(levels).all() or (levels<=0).any():
        raise EconomicsStop("Invalid model sleeve NAV for look-through")
    units=levels[first:]/levels[first]
    sleeve_weights=units/units.sum(axis=1)[:,None]
    if not np.isfinite(sleeve_weights).all():
        raise EconomicsStop("Invalid drifting model sleeve fractions")
    etf=np.zeros((len(dates)-first,len(ALL_ETFS)))
    owners=np.zeros_like(etf,dtype=int)
    column={symbol:i for i,symbol in enumerate(ALL_ETFS)}
    for j,model in enumerate(MODELS):
        for symbol in WEIGHT_SYMBOLS[model]:
            raw=paths[model]["weight_"+symbol].to_numpy(dtype=float)[first:]
            k=column[symbol]
            etf[:,k]+=sleeve_weights[:,j]*raw
            owners[:,k]+=(raw>1e-8).astype(int)
    total=etf.sum(axis=1)
    expected=sum(sleeve_weights[:,j]*
                 paths[m]["gross"].to_numpy(dtype=float)[first:]
                 for j,m in enumerate(MODELS))
    if ((etf<-1e-9).any() or (total>1+1e-8).any()
        or not np.allclose(total,expected,rtol=0,atol=1e-8)):
        raise EconomicsStop("Fixed-blend ETF exposure cannot be reconciled")
    etf=etf[start-first:]
    owners=owners[start-first:]
    total=total[start-first:]
    overlap=np.where(owners>=2,etf,0.).sum(axis=1)
    largest=etf.max(axis=1)
    top3=np.sort(etf,axis=1)[:,-3:].sum(axis=1)
    peak_t,peak_sym=np.unravel_index(int(np.argmax(etf)),etf.shape)
    return {
        "first_session":dates[start].date().isoformat(),
        "last_session":dates[-1].date().isoformat(),
        "sessions":len(etf),
        "first_eligible_entry_session":dates[first].date().isoformat(),
        "method":"ORIGINAL_POST_CLOSE_ETF_WEIGHTS_DRIFTING_COSTED_MODEL_UNITS",
        "fixed_initial_sleeve_weight_each":0.25,
        "model_sleeves_rebalanced_after_entry":False,
        "ETF_constituent_stock_overlap_NOT_measured":True,
        "not_independent_out_of_sample_or_live_authority":True,
        "average_gross_ETF_exposure_pct":round(100*float(total.mean()),4),
        "average_cash_pct":round(100*float((1-total).mean()),4),
        "average_largest_single_ETF_pct":round(100*float(largest.mean()),4),
        "maximum_single_ETF_pct":round(100*float(etf[peak_t,peak_sym]),4),
        "symbol_at_maximum_single_ETF":ALL_ETFS[peak_sym],
        "maximum_top_three_ETFs_pct":round(100*float(top3.max()),4),
        "average_ETF_notional_shared_by_two_or_more_models_pct":
            round(100*float(overlap.mean()),4),
        "sessions_single_ETF_over_35pct_descriptive":int((largest>.35+1e-10).sum()),
        "distinct_ETF_tickers_held_during_window":
            int((etf>1e-8).any(axis=0).sum()),
    }



# These are contemporaneous, price-based equity factor PROXIES, not point-in-time
# constituent holdings, independently sourced factors or investable hedges.
FACTOR_PROXY_NAMES=("ACWI","XLK_MINUS_SPY","XLE_MINUS_SPY","IWM_MINUS_SPY")
FACTOR_PROXY_PRICE_COLUMNS=("ACWI_BENCHMARK","SPY","XLK","XLE","IWM")


def _fixed_blend_factor_proxy_attribution(prices:pd.DataFrame, paths:dict,
                                          begin:str, cost_bps:int)->dict:
    """Decompose fixed-blend historical returns using original equity ETF proxies.

    A same-close explanatory regression, NOT a forecast, causal sector
    attribution, true stock look-through or an alpha promotion test. The
    dependent variable includes each original model's costs and the synthetic
    fixed-blend entry cost. Factors come from the *same* frozen adjusted-price
    vintage. All series use identical close-to-close sessions AFTER entry.
    """
    if type(cost_bps) is not int or cost_bps not in COSTS:
        raise EconomicsStop("Unregistered historical cost scenario")
    try:
        dates,benchmark,navs=adaptive._verified_paths(paths)
    except adaptive.WalkforwardStop as exc:
        raise EconomicsStop("Invalid original model paths for factor attribution") from exc
    if (not isinstance(prices,pd.DataFrame) or not dates.equals(prices.index)
        or any(c not in prices.columns for c in FACTOR_PROXY_PRICE_COLUMNS)):
        raise EconomicsStop("Frozen factor price dates or columns disagree")
    px=prices.loc[:,FACTOR_PROXY_PRICE_COLUMNS].to_numpy(dtype=float)
    if not np.isfinite(px).all() or (px<=0).any():
        raise EconomicsStop("Missing or invalid frozen factor prices")
    # Compare the market-price benchmark *returns*, not its arbitrary NAV base.
    price_benchmark=px[:,0]/px[0,0]
    nav_benchmark=benchmark/benchmark[0]
    if not np.allclose(price_benchmark,nav_benchmark,atol=1e-9,rtol=1e-9):
        raise EconomicsStop("Original ACWI benchmark differs from factor source")
    first=next((t for t in range(adaptive.TRAINING_RETURNS+1,len(dates))
                if dates[t].to_period("Q")!=dates[t-1].to_period("Q")),None)
    if first is None:
        raise EconomicsStop("No eligible original fixed-blend entry")
    start=max(first,int(dates.searchsorted(pd.Timestamp(begin))))
    if len(dates)-start<260:
        raise EconomicsStop("Insufficient completed factor-return observations")
    levels=adaptive._fixed_equal_model_blend(dates,navs,cost_bps)
    y=levels[start+1:]/levels[start:-1]-1
    rets=px[1:]/px[:-1]-1
    daily=rets[start:]
    # The three spreads are EXCESS RETURNS of sector/size ETF price proxies
    # versus SPY, not pure industry factors or issuer-level allocations.
    factors=np.column_stack((daily[:,0],
                             daily[:,2]-daily[:,1],
                             daily[:,3]-daily[:,1],
                             daily[:,4]-daily[:,1]))
    if (len(y)!=len(factors) or not np.isfinite(y).all()
        or not np.isfinite(factors).all() or (y<=-1).any()
        or (rets<=-1).any()):
        raise EconomicsStop("Invalid or misaligned historical factor returns")
    common={
        "status":"UNIDENTIFIABLE_FACTOR_PROXIES",
        "method":"SAME_CLOSE_HISTORICAL_COSTED_BLEND_OLS_HAC5",
        "first_session":dates[start].date().isoformat(),
        "last_session":dates[-1].date().isoformat(),
        "return_observations":len(y),
        "factors":list(FACTOR_PROXY_NAMES),
        "factor_coefficients":None,
        "historical_ACWI_only_R2_pct":None,
        "historical_joint_factor_R2_pct":None,
        "historical_incremental_fit_vs_ACWI_pp":None,
        "arithmetic_annual_intercept_pct":None,
        "intercept_HAC5_95pct_interval_annual_pct":None,
        "historical_residual_annual_vol_pct":None,
        "original_model_and_synthetic_entry_costs_included":True,
        "same_vintage_contemporaneous_adjusted_ETF_price_proxies":True,
        "factor_betas_are_not_underlying_stock_or_sector_holdings":True,
        "not_point_in_time_constituent_or_independent_factor_data":True,
        "historical_intercept_is_not_investable_alpha":True,
        "already_inspected_history_not_independent_out_of_sample":True,
        "not_a_funded_strategy_or_live_release":True,
    }
    if np.std(y,ddof=1)<1e-8 or (np.std(factors,axis=0,ddof=1)<1e-8).any():
        return common
    # Scale to check identification without mistaking daily-return units for
    # collinearity. Reject singular/near-singular proxy sets rather than
    # publishing arbitrary factor coefficients.
    z=(factors-factors.mean(axis=0))/factors.std(axis=0,ddof=1)
    if np.linalg.cond(z)>1e6:
        return common
    x=np.column_stack((np.ones(len(y)),factors))
    coef=np.linalg.lstsq(x,y,rcond=None)[0]
    residual=y-x@coef
    xx=x.T@x
    if np.linalg.cond(xx)>1e12:
        return common
    xu=x*residual[:,None]
    meat=xu.T@xu
    for lag in range(1,6):
        cross=xu[lag:].T@xu[:-lag]
        meat+=(1-lag/6)*(cross+cross.T)
    inv=np.linalg.inv(xx)
    variance=float((inv@meat@inv)[0,0])
    if variance < -1e-12:
        raise EconomicsStop("Invalid historical factor intercept variance")
    se=float(np.sqrt(max(0.,variance)))
    alpha=float(coef[0])*252
    base=factors[:,0]
    baseline_residual=y-(y.mean()+
                        np.dot(y-y.mean(),base-base.mean())/
                        np.dot(base-base.mean(),base-base.mean())*
                        (base-base.mean()))
    var_y=float(np.var(y,ddof=1))
    r2=1-float(np.var(residual,ddof=1))/var_y
    base_r2=1-float(np.var(baseline_residual,ddof=1))/var_y
    vals=[*coef,alpha,se,r2,base_r2]
    if not np.isfinite(vals).all() or r2+1e-8<base_r2:
        raise EconomicsStop("Invalid historical factor attribution fit")
    return dict(common,
        status="DESCRIPTIVE_FACTOR_PROXY_FIT",
        factor_coefficients={name:round(float(beta),5)
                             for name,beta in zip(FACTOR_PROXY_NAMES,coef[1:])},
        historical_ACWI_only_R2_pct=round(100*max(0.,min(1.,base_r2)),4),
        historical_joint_factor_R2_pct=round(100*max(0.,min(1.,r2)),4),
        historical_incremental_fit_vs_ACWI_pp=round(
            100*max(0.,r2-base_r2),4),
        arithmetic_annual_intercept_pct=round(100*alpha,4),
        intercept_HAC5_95pct_interval_annual_pct=[
            round(100*(alpha-1.96*252*se),4),
            round(100*(alpha+1.96*252*se),4)],
        historical_residual_annual_vol_pct=round(
            100*float(np.std(residual,ddof=1)*np.sqrt(252)),4))


def _beta_attribution(path:pd.DataFrame)->dict:
    """Descriptive same-session OLS, not a forward alpha estimate or strategy.

    Newey-West/Bartlett 5-session HAC confidence interval describes historical
    residual uncertainty, NOT data-snooping or parameter-selection uncertainty.
    Uses original already-inspected price history, no risk-free cash return.
    """
    if (not isinstance(path,pd.DataFrame) or len(path)<260
        or not {"nav","benchmark"}<=set(path)):
        raise EconomicsStop("Risk attribution needs full original NAV/benchmark")
    if (not np.isfinite(path[["nav","benchmark"]].to_numpy(dtype=float)).all()
        or (path[["nav","benchmark"]]<=0).any().any()):
        raise EconomicsStop("Nonfinite or nonpositive strategy/benchmark NAV")
    r=path["nav"].pct_change(fill_method=None).iloc[1:].to_numpy(dtype=float)
    b=path["benchmark"].pct_change(fill_method=None).iloc[1:].to_numpy(dtype=float)
    if (not np.isfinite(r).all() or not np.isfinite(b).all()
        or (r<=-1).any() or (b<=-1).any()):
        raise EconomicsStop("Invalid same-session daily returns")
    active=r-b
    te=float(np.std(active,ddof=1)*np.sqrt(252))
    info=(float(np.mean(active)*252/te) if te>1e-12 else None)
    base={
        "method":"HISTORICAL_SAME_SESSION_DAILY_OLS_HAC5_NOT_PREDICTIVE",
        "risk_free_cash_return_assumed_zero":True,
        "already_inspected_history_no_independent_holdout":True,
        "tracking_error_annual_pct":round(te*100,4),
        "historical_active_information_ratio":round(info,4) if info is not None else None,
        "benchmark_beta":None,
        "arithmetic_beta_adjusted_alpha_annual_pct":None,
        "historical_alpha_HAC5_95pct_interval_annual_pct":None,
        "historical_market_R_squared":None,
        "alpha_significance_not_a_promotion_rule":True,
    }
    if float(np.std(b,ddof=1))<1e-8:
        return dict(base,regression_status="BENCHMARK_VARIANCE_TOO_LOW_UNIDENTIFIABLE")
    n=len(r)
    X=np.column_stack((np.ones(n),b))
    xtx=X.T@X
    if not np.isfinite(xtx).all() or np.linalg.cond(xtx)>1e12:
        return dict(base,regression_status="ILL_CONDITIONED_BENCHMARK_UNIDENTIFIABLE")
    coeff=np.linalg.solve(xtx,X.T@r)
    residual=r-X@coeff
    xu=X*residual[:,None]
    # Sandwich Newey-West HAC, 5 trading-day lags with Bartlett weights.
    meat=xu.T@xu
    for lag in range(1,6):
        cross=xu[lag:].T@xu[:-lag]
        meat+=(1-lag/6)*(cross+cross.T)
    inv=np.linalg.inv(xtx)
    cov=inv@meat@inv
    se_alpha=float(np.sqrt(max(0.0,cov[0,0])))
    alpha=float(coeff[0])*252
    interval=[round((alpha-1.96*252*se_alpha)*100,4),
              round((alpha+1.96*252*se_alpha)*100,4)]
    variance_r=float(np.var(r,ddof=1))
    r2=(1-float(np.var(residual,ddof=1))/variance_r
        if variance_r>1e-18 else None)
    values=[alpha,coeff[1],se_alpha,*(interval)]
    if not np.isfinite(values).all() or (r2 is not None and not np.isfinite(r2)):
        raise EconomicsStop("Nonfinite risk-adjusted research statistic")
    return dict(base,
        regression_status="HISTORICAL_DESCRIPTIVE_ONLY",
        benchmark_beta=round(float(coeff[1]),4),
        arithmetic_beta_adjusted_alpha_annual_pct=round(alpha*100,4),
        historical_alpha_HAC5_95pct_interval_annual_pct=interval,
        historical_market_R_squared=round(max(0.0,min(1.0,r2)),4)
            if r2 is not None else None)


def _metrics(path:pd.DataFrame,begin:str,*,drawdown_guard:float,vol_guard:float):
    view=path.loc[begin:]
    if len(view)<260:
        raise EconomicsStop("Insufficient completed source sessions")
    years=(view.index[-1]-view.index[0]).days/365.25
    nav=view["nav"]
    ref=view["benchmark"]
    returns=nav.pct_change(fill_method=None).dropna()
    peak=nav.cummax()
    dd=nav/peak-1
    annual=(nav.iloc[-1]/nav.iloc[0])**(1/years)-1
    vol=float(returns.std(ddof=1)*np.sqrt(252))
    refannual=(ref.iloc[-1]/ref.iloc[0])**(1/years)-1
    if (not all(np.isfinite(x) for x in (years,annual,vol,refannual))
        or years<=0 or (dd>0.00000001).any()):
        raise EconomicsStop("Impossible model risk or annualisation values")
    return {
        "first_session":view.index[0].date().isoformat(),
        "last_session":view.index[-1].date().isoformat(),
        "sessions":len(view),
        "historical_annualised_return_pct":round(100*annual,4),
        "historical_ACWI_annualised_return_pct":round(100*refannual,4),
        "historical_excess_over_ACWI_pp":round(100*(annual-refannual),4),
        "historical_max_drawdown_pct":round(100*float(dd.min()),4),
        "historical_realised_vol_pct":round(100*vol,4),
        "historical_worst_session_pct":round(100*float(returns.min()),4),
        "historical_one_way_turnover_NAV_per_year":round(
            float(view["turnover"].iloc[1:].sum()/years),4),
        "average_equity_exposure_pct":round(100*float(view["gross"].mean()),4),
        "below_five_percent_cash_sessions":int((view["cash"]<.05-1e-9).sum()),
        "sessions_more_than_20pct_under_previous_peak":int(
            (dd<-drawdown_guard-1e-10).sum()),
        "exceeds_historical_HIGH_20pct_drawdown_screen":
            bool(dd.min()<-drawdown_guard-1e-10),
        "exceeds_historical_HIGH_35pct_volatility_screen":
            bool(vol>vol_guard+1e-10),
        "descriptive_beta_adjusted_attribution":_beta_attribution(view),
        "historical_screen_is_NOT_broker_halt_or_trade_instruction":True,
    }

def evaluate(prices:pd.DataFrame,*,source_sha:str,
             policy_path:Path=s1.S1_POLICY)->dict:
    if source_sha!=r1.FROZEN_FILE_SHA256:
        raise EconomicsStop("Original frozen research source SHA mismatch")
    data=r1.validate_prices(prices)
    policy,policy_sha=s1.policy(policy_path)
    if (policy.get("maximum_peak_to_trough_drawdown_fraction")!="0.20"
        or policy.get("maximum_annual_realized_account_volatility")!="0.35"
        or policy.get("execution_authorized") is not False):
        raise EconomicsStop("HIGH historic risk screen/source status drifted")
    output={}
    uncertainty={}
    causal_switching={}
    lookthrough={}
    factor_proxy_attribution={}
    for cost in COSTS:
        frames=_all_paths(data,cost)
        causal_switching[str(cost)] = adaptive.evaluate(
            frames, switch_side_cost_bps=cost)
        windows={}
        uncertainty_windows={}
        lookthrough_windows={}
        factor_windows={}
        for label,start in WINDOWS.items():
            windows[label]={
                name:_metrics(frame,start,drawdown_guard=.20,vol_guard=.35)
                for name,frame in frames.items()
            }
            if len({m["first_session"] for m in windows[label].values()})!=1:
                raise EconomicsStop("Historical start dates are inconsistent")
            uncertainty_windows[label]=selection.evaluate(frames,start)
            lookthrough_windows[label]=_fixed_blend_etf_lookthrough(frames,start)
            factor_windows[label]=_fixed_blend_factor_proxy_attribution(
                data,frames,start,cost)
        output[str(cost)]=windows
        uncertainty[str(cost)]=uncertainty_windows
        lookthrough[str(cost)]=lookthrough_windows
        factor_proxy_attribution[str(cost)]=factor_windows
    return {
        "schema":SCHEMA,
        "status":"ORIGINAL_MODELS_COMPARABLE_HISTORICAL_NOT_INDEPENDENT_NOT_LIVE",
        "source_frozen_history_sha256":source_sha,
        "unchanged_reconciled_HIGH_policy_sha256":policy_sha,
        "original_strategy_implementations_reused_verbatim":list(MODELS),
        "same_priced_ACWI_benchmark":True,
        "same_dated_historical_windows":True,
        "trading_timing_and_concentration_NOT_homogenized":True,
        "identical_transaction_cost_bps_each_side":list(COSTS),
        "cash_yield_assumption":0,
        "historically_preinspected_no_new_holdout":True,
        "no_additional_strategy_parameter_search":True,
        "historical_20pct_peak_drawdown_screen_is_NOT_live_stop":True,
        "original_sector_95pct_allocation_not_mutated":True,
        "risk_adjusted_attribution_is_historical_not_forward_alpha":True,
        "historical_HAC_interval_does_not_correct_model_selection_bias":True,
        "market_spread_fills_tax_and_foreign_exchange_not_modelled":True,
        "evaluated_models":output,
        "joint_four_model_selection_uncertainty":uncertainty,
        "causal_quarterly_model_switching_exploratory":causal_switching,
        "fixed_four_model_ETF_lookthrough_by_window":lookthrough,
        "fixed_four_model_factor_proxy_attribution_by_window":factor_proxy_attribution,
        "factor_proxy_regression_is_descriptive_not_stock_lookthrough":True,
        "lookthrough_is_ETF_ticker_level_not_underlying_stock_constituents":True,
        "meta_selection_rule_predeclared_not_parameter_optimized":True,
        "meta_selector_not_independent_holdout_or_live_strategy":True,
        "selection_adjustment_only_within_four_original_models":True,
        "selection_bootstrap_does_not_correct_prior_strategy_search":True,
        "strategy_promoted_for_funded_trading":None,
        "authorised_live_orders":False,
        "operator_switch_changed":False,
        "real_broker_orders":0,
    }

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--frozen-prices",default="research_lab/frozen_history_v2.csv")
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    data,src=r1.load_frozen(Path(args.frozen_prices))
    res=evaluate(data,source_sha=src)
    output=Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(res,indent=2,sort_keys=True)+"\n")
    for cost,years in res["evaluated_models"].items():
        print("Original historical models; one-way cost",cost,"bps")
        for label,items in years.items():
            print("Window",label)
            for name,val in items.items():
                print(name,"return",val["historical_annualised_return_pct"],
                    "maxDD",val["historical_max_drawdown_pct"],
                    "vol",val["historical_realised_vol_pct"],
                    "turnover",val["historical_one_way_turnover_NAV_per_year"])
    print("Four existing strategies, no new parameters, no LIVE trading permission.")

if __name__=="__main__":
    main()
