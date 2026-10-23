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

SCHEMA="FUND100_V6_FOUR_EXISTING_STRATEGIES_COMMON_HISTORY_ECONOMICS_V1"
MODELS=("S1_HIGH_FIXED_SECTORS","R1_WEEKLY_RELATIVE_MOMENTUM",
        "L1_VOL_MANAGED_SECTORS","R2_QUARTERLY_ABSOLUTE_TREND")
WINDOWS={"since_2014":"2014-01-01","since_2020":"2020-01-01",
         "since_2023":"2023-01-01"}
COSTS=(5,15,35)
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
    for cost in COSTS:
        frames=_all_paths(data,cost)
        windows={}
        uncertainty_windows={}
        for label,start in WINDOWS.items():
            windows[label]={
                name:_metrics(frame,start,drawdown_guard=.20,vol_guard=.35)
                for name,frame in frames.items()
            }
            if len({m["first_session"] for m in windows[label].values()})!=1:
                raise EconomicsStop("Historical start dates are inconsistent")
            uncertainty_windows[label]=selection.evaluate(frames,start)
        output[str(cost)]=windows
        uncertainty[str(cost)]=uncertainty_windows
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
