"""Fund-100 V6-S1 exact 95%-invested historical/cash-floor diagnostic.

Uses original immutable research history and the PRE-EXISTING 50/30/20
sector thesis. Not a new tuned alpha strategy, nor an executable LIVE
order plan. Shows why a 5% cash TARGET cannot be called a 5% daily FLOOR.
"""
from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path

import pandas as pd

import fund100_v6_fast_launch_vol_regime_l1_v1_0 as l1
import fund100_v6_l1_fixed_mix_attribution_v1_0 as original
import fund100_v6_s1_concentrated_risk_and_paper_asset_v1_0 as contract

SCHEMA="FUND100_V6_S1_EXACT_95PCT_COSTED_CASH_FLOOR_DIAGNOSTIC_V1"
TARGET={"XLK":.475,"XLE":.285,"IWM":.190}
FLOOR=.05
EPS=1e-10

class S1EconomicsStop(ValueError): pass


def verify_contract()->dict:
    m=contract.source_controls()
    if (m.get("schema")!=contract.SCHEMA
        or m.get("status")!="PROPOSED_NOT_LIVE"
        or m.get("target_weights")!={k:format(v,".3f") for k,v in TARGET.items()}
        or m.get("investable_gross_fraction")!="0.95"
        or m.get("cash_reserve_fraction")!="0.05"
        or m.get("maximum_symbol_weight")!="0.50"
        or m.get("live_order_execution_released") is not False):
        raise S1EconomicsStop("S1 original static 95% proposal changed")
    if abs(sum(TARGET.values())-(1-FLOOR))>EPS:
        raise S1EconomicsStop("S1 originally registered exposure does not sum to 95%")
    return m


def simulate(prices:pd.DataFrame, *, cost_bps:int, targets:dict[str,float]|None=None)->pd.DataFrame:
    """Actual daily drift; month-end trades only if >=10pp away from targets.

    NAV cost method intentionally mirrors prior frozen L1 fixed-mix
    comparator, which is favorable to the cash buffer because cost
    financing is not debited separately from allocated cash weights.
    It is NOT a broker cash-settlement or actual-fill simulator.
    """
    if cost_bps not in l1.COST_BPS:
        raise S1EconomicsStop("Original 5/15/35 bps trading-cost set required")
    chosen=TARGET.copy() if targets is None else targets
    if (not isinstance(chosen,dict) or set(chosen)!=set(l1.NAMES)
        or any(type(v) is not float or not isfinite(v) or v<0 for v in chosen.values())
        or sum(chosen.values())>1+EPS):
        raise S1EconomicsStop("Unrecognized or leveraged exposure")
    data=l1.validate(prices)
    returns=data.pct_change(fill_method=None).fillna(0)
    nav=benchmark=l1.NAV0
    weights={s:0.0 for s in l1.NAMES}
    engaged=False
    rows=[]
    for t,(date,session) in enumerate(returns.iterrows()):
        daily=sum(weights[s]*float(session[s]) for s in l1.NAMES) if t else 0.0
        if not isfinite(daily) or daily<=-1:
            raise S1EconomicsStop("Unusable session return")
        nav*=1+daily
        benchmark*=1+float(session[l1.BENCH]) if t else 1.0
        if t:
            weights={s:weights[s]*(1+float(session[s]))/(1+daily) for s in l1.NAMES}
        cash_pre=1-sum(weights.values())
        reserve_violation_pre=engaged and cash_pre<FLOOR-EPS
        symbol_violation_pre=engaged and max(weights.values())>.50+EPS
        traded=False
        turnover=0.0
        if l1.month_end_session(data.index,t):
            differences={s:abs(chosen[s]-weights[s]) for s in l1.NAMES}
            if max(differences.values())>=l1.BAND:
                turnover=sum(differences.values())
                nav*=1-turnover*cost_bps/10_000
                weights=chosen.copy()
                engaged=True
                traded=True
        gross=sum(weights.values())
        cash=1-gross
        if not isfinite(nav) or nav<=0 or cash<-EPS or not isfinite(cash):
            raise S1EconomicsStop("NAV or cash became invalid")
        rows.append({
            "date":date,"nav":nav,"acwi_nav":benchmark,
            "turnover":turnover,"trade":traded,
            "gross_risk_exposure":gross,"cash":max(0.0,cash),
            "risk_off_at_decision":False,
            "risk_month_end_vol":None,
            "cash_floor_breach_before_trade":bool(reserve_violation_pre),
            "cash_floor_breach_end_of_day":bool(engaged and cash<FLOOR-EPS),
            "single_symbol_breach_before_trade":bool(symbol_violation_pre),
            "single_symbol_breach_end_of_day":bool(engaged and max(weights.values())>.5+EPS),
            "invested":engaged,
            **{"weight_"+s:weights[s] for s in l1.NAMES},
        })
    return pd.DataFrame(rows).set_index("date")



def simulate_daily_cash_floor(prices:pd.DataFrame, *, cost_bps:int,
                              reserve_fraction:float=FLOOR,
                              daily_trims:bool=True)->pd.DataFrame:
    """Research sensitivity: restore a true 5% EOD cash floor with daily trims.

    All positions and cash are accounted in dollars, including every fee.
    Monthly 10pp-band decisions are unchanged. If natural appreciation
    consumes the buffer, sell a pro-rata slice at that close; do NOT buy.
    Assumes idealized fractional executions at close, instantaneous sale
    proceeds and proportional costs. At $130.30 these tiny trades may be
    below actual broker minimums. For fixed 10%/15% cash-buffer research,
    disable daily trims and retain the original month-end 10pp band.
    NOT an executable policy or a new alpha fit.
    """
    if cost_bps not in l1.COST_BPS:
        raise S1EconomicsStop("Original 5/15/35 bps stress only")
    if (type(reserve_fraction) is not float or reserve_fraction not in
            (FLOOR,.10,.15) or type(daily_trims) is not bool
            or (daily_trims and reserve_fraction!=FLOOR)):
        raise S1EconomicsStop("Only predeclared passive 10/15% cash buffers, or original 5% daily repair")
    targets={symbol:TARGET[symbol]*(1-reserve_fraction)/(1-FLOOR)
             for symbol in l1.NAMES}
    data=l1.validate(prices)
    rate=cost_bps/10_000.
    nav=l1.NAV0
    benchmark=l1.NAV0
    cash=float(nav)
    holdings={s:0. for s in l1.NAMES}
    engaged=False
    rows=[]
    for t,date in enumerate(data.index):
        if t:
            previous=data.iloc[t-1]
            current=data.iloc[t]
            for symbol in l1.NAMES:
                holdings[symbol]*=float(current[symbol]/previous[symbol])
            benchmark*=float(current[l1.BENCH]/previous[l1.BENCH])
        nav=cash+sum(holdings.values())
        if not isfinite(nav) or nav<=0:
            raise S1EconomicsStop("Invalid daily dollar NAV")
        weights={s:holdings[s]/nav for s in l1.NAMES}
        traded=False
        turnover=0.
        trim=0.
        if l1.month_end_session(data.index,t) and max(
                abs(targets[s]-weights[s]) for s in l1.NAMES)>=l1.BAND:
            # Solve NAV_after = NAV_before - fee * sum(abs(target$-held$)).
            # Fee is charged to cash, not silently financed by the buffer.
            post=nav
            for _ in range(100):
                traded_dollars=sum(abs(targets[s]*post-holdings[s])
                                   for s in l1.NAMES)
                nxt=nav-rate*traded_dollars
                if not isfinite(nxt) or nxt<=0:
                    raise S1EconomicsStop("Monthly rebalance insolvent")
                if abs(nxt-post)<=1e-12*nav:
                    post=nxt
                    break
                post=nxt
            else:
                raise S1EconomicsStop("Monthly fee/target solver did not converge")
            traded_dollars=sum(abs(targets[s]*post-holdings[s])
                               for s in l1.NAMES)
            post=nav-rate*traded_dollars
            holdings={s:targets[s]*post for s in l1.NAMES}
            cash=post-sum(holdings.values())
            turnover+=traded_dollars/nav
            nav=post
            traded=True
            engaged=True
        # Close-to-close drift may erode the reserve on any session.
        # S solves (cash + S*(1-fee))/(NAV-fee*S) == FLOOR.
        if daily_trims and engaged and cash/nav<FLOOR-1e-12:
            pre_nav=nav
            deficit=FLOOR*nav-cash
            trim=deficit/(1-rate*(1-FLOOR))
            gross=sum(holdings.values())
            if not 0<trim<=gross:
                raise S1EconomicsStop("Cannot restore daily cash floor")
            scale=1-trim/gross
            holdings={s:value*scale for s,value in holdings.items()}
            cash+=trim*(1-rate)
            nav=cash+sum(holdings.values())
            turnover+=trim/pre_nav
            traded=True
        if (not isfinite(nav) or not isfinite(cash)
            or cash<0 or any(not isfinite(v) or v<0 for v in holdings.values())
            or (daily_trims and engaged and cash/nav<FLOOR-1e-10)):
            raise S1EconomicsStop("Daily costed cash floor not preserved")
        weights={s:holdings[s]/nav for s in l1.NAMES}
        rows.append({
            "date":date,"nav":nav,"acwi_nav":benchmark,
            "turnover":turnover,"trade":traded,
            "gross_risk_exposure":sum(weights.values()),
            "cash":cash/nav,"invested":engaged,
            "risk_off_at_decision":False,"risk_month_end_vol":None,
            "cash_floor_breach_before_trade":False,
            "cash_floor_breach_end_of_day":bool(engaged and cash/nav<FLOOR-1e-10),
            "single_symbol_breach_before_trade":False,
            "single_symbol_breach_end_of_day":bool(engaged and max(weights.values())>.5+EPS),
            "daily_floor_trim":trim>0,
            "daily_floor_trim_usd_per_130_30":130.30*trim/(nav+rate*trim) if trim else 0.,
            "month_end_rebalance":bool(traded and trim==0 and l1.month_end_session(data.index,t)),
            **{"weight_"+s:weights[s] for s in l1.NAMES},
        })
    return pd.DataFrame(rows).set_index("date")


def daily_floor_feasibility(path:pd.DataFrame,start:str)->dict:
    """Descriptive ideal-fill economics and microticket feasibility only."""
    sub=path.loc[start:]
    invested=sub.loc[sub["invested"]]
    trims=invested.loc[invested["daily_floor_trim"]]
    notional=trims["daily_floor_trim_usd_per_130_30"]
    return {
        "costed_path":period_diagnostics(path,start),
        "idealized_daily_pro_rata_trim_events":int(len(trims)),
        "idealized_trims_below_1_usd_at_130_30":int((notional<1.).sum()),
        "idealized_trims_below_5_usd_at_130_30":int((notional<5.).sum()),
        "smallest_idealized_trim_usd_at_130_30":(
            round(float(notional.min()),8) if len(trims) else None),
        "daily_close_cash_floor_enforced_after_model_fees":bool(
            len(invested) and (invested["cash"]>=FLOOR-1e-10).all()),
        "instant_fractional_close_sales_and_cash_settlement_assumed":True,
        "actual_broker_minimum_and_settlement_not_verified":True,
        "research_sensitivity_not_released_trading_policy":True,
    }


def passive_cash_buffer_feasibility(path:pd.DataFrame,start:str)->dict:
    """Historical cash-drift/cost tradeoff; no daily microticket sales."""
    sub=path.loc[start:]
    invested=sub.loc[sub["invested"]]
    return {
        "costed_path":period_diagnostics(path,start),
        "month_end_trade_events":int(sub["month_end_rebalance"].sum()),
        "daily_trim_events":int(sub["daily_floor_trim"].sum()),
        "cash_floor_satisfied_at_all_invested_closes":bool(
            len(invested) and (invested["cash"]>=FLOOR-1e-10).all()),
        "still_requires_intraday_and_broker_cash_validation":True,
        "fixed_buffer_not_an_optimized_or_released_strategy":True,
        "no_independent_alpha_claim":True,
    }


def period_diagnostics(path:pd.DataFrame,start:str)->dict:
    m=l1.metrics(path,start)
    sub=path.loc[start:]
    held=sub.loc[sub["invested"]]
    return {
      "metrics":m,
      "cash_below_5pct_sessions_end_of_day":int(sub["cash_floor_breach_end_of_day"].sum()),
      "cash_below_5pct_sessions_before_monthend_trade":int(sub["cash_floor_breach_before_trade"].sum()),
      "sector_weight_over_50pct_sessions":int(sub["single_symbol_breach_end_of_day"].sum()),
      "minimum_cash_fraction_during_investment":round(float(held["cash"].min()),8) if len(held) else None,
      "maximum_gross_risk_exposure_during_investment":round(float(held["gross_risk_exposure"].max()),8) if len(held) else None,
      "monthly_band_does_not_enforce_daily_minimum":True,
    }


def evaluate(raw:pd.DataFrame,*,source_sha256:str)->dict:
    verify_contract()
    if source_sha256!=l1.ORIGINAL_SHA:
        raise S1EconomicsStop("Wrong original source digest; no retrospective data replacement")
    data=l1.validate(raw)
    results={}
    for bp in l1.COST_BPS:
        s=simulate(data,cost_bps=bp)
        original_full=original.fixed_mix(data,cost_bps=bp)
        if len(s)!=len(original_full) or not s.index.equals(original_full.index):
            raise S1EconomicsStop("Mismatched original sector comparison sessions")
        results[str(bp)]={}
        for name,start in (("2014_onward","2014-01-01"),("2020_onward","2020-01-01")):
            risk=period_diagnostics(s,start)
            full=period_diagnostics(original_full.assign(
                invested=original_full["gross_risk_exposure"]>0,
                cash_floor_breach_end_of_day=False,
                cash_floor_breach_before_trade=False,
                single_symbol_breach_end_of_day=False,
            ),start)["metrics"]
            results[str(bp)][name]={
              "actual_S1_95pct_target_with_drift":risk,
              "original_100pct_invested_fixed_sector_comparator":full,
              "ACWI_historical_cagr_pct":risk["metrics"]["acwi_nav"]["annual_return_pct"],
              "S1_minus_original_100pct_cagr_pp":round(
                 risk["metrics"]["nav"]["annual_return_pct"]-full["nav"]["annual_return_pct"],5),
              "S1_cash_floor_satisfied_on_all_sessions":risk["cash_below_5pct_sessions_end_of_day"]==0,
            }
    # Separate unoptimized daily-floor sensitivity on the SAME original
    # frozen history. This does not alter the original monthly S1 result.
    repair={}
    for bp in l1.COST_BPS:
        path=simulate_daily_cash_floor(data,cost_bps=bp)
        repair[str(bp)]={
            name:daily_floor_feasibility(path,start)
            for name,start in (("2014_onward","2014-01-01"),
                               ("2020_onward","2020-01-01"))
        }
    # A larger static cash buffer may avoid impractical sub-dollar daily
    # sells. These are predeclared sensitivities, not a retrospective search
    # for the best reserve or a modification of the original 95% contract.
    passive_buffers={}
    for reserve in (.10,.15):
        passive_buffers[str(int(reserve*100))]={}
        for bp in l1.COST_BPS:
            path=simulate_daily_cash_floor(
                data,cost_bps=bp,reserve_fraction=reserve,daily_trims=False)
            passive_buffers[str(int(reserve*100))][str(bp)]={
                name:passive_cash_buffer_feasibility(path,start)
                for name,start in (("2014_onward","2014-01-01"),
                                   ("2020_onward","2020-01-01"))
            }
    floor_ok=all(
      x["actual_S1_95pct_target_with_drift"]["cash_below_5pct_sessions_end_of_day"]==0
      for section in results.values() for x in section.values())
    return {
      "schema":SCHEMA,
      "candidate":"V6_S1_FIXED_SECTOR_RISK_PREMIUM",
      "exact_whole_account_target":TARGET,
      "original_frozen_history_sha256":source_sha256,
      "history_exploratory_not_out_of_sample":True,
      "original_unmanaged_100pct_basket_is_not_the_95pct_strategy":True,
      "risk_rebalance_month_end_if_any_absolute_weight_delta_at_least":l1.BAND,
      "no_volatility_timing_overlay":True,
      "unremunerated_cash_assumption":True,
      "transaction_cost_method_matches_original_L1_unmanaged_diagnostic":True,
      "cash_floor_after_transaction_costs_not_broker_certified":True,
      "cost_bps_one_way":list(l1.COST_BPS),
      "results":results,
      "daily_cash_floor_ideal_fill_sensitivity":repair,
      "daily_cash_floor_ideal_fill_not_broker_executable":True,
      "fixed_10_and_15pct_passive_cash_buffer_sensitivities":passive_buffers,
      "passive_cash_buffers_not_live_authorized":True,
      "cash_reserve_minimum_met_in_historical_model":floor_ok,
      "minimum_cash_floor_live_execution_requires_separate_design_review":not floor_ok,
      "independent_alpha_proved":False,
      "price_source_cannot_authenticate_future_fill":True,
      "paper_orders":0,"live_orders":0,"broker_calls":0,
      "new_strategy_live_authorized":False,
      "old_operator_stop_still_required":True,
    }


def main():
    args=argparse.ArgumentParser()
    args.add_argument("--frozen-history",type=Path,default=Path("research_lab/frozen_history_v2.csv"))
    args.add_argument("--output",required=True,type=Path)
    x=args.parse_args()
    prices,digest=l1.load_frozen(x.frozen_history)
    report=evaluate(prices,source_sha256=digest)
    x.output.parent.mkdir(parents=True,exist_ok=True)
    x.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    for cost,periods in report["results"].items():
        for name,item in periods.items():
            m=item["actual_S1_95pct_target_with_drift"]
            print("V6_S1_EXACT_95",name,cost,"BP",
                "CAGR",m["metrics"]["nav"]["annual_return_pct"],
                "ACWI_CAGR",item["ACWI_historical_cagr_pct"],
                "ORIGINAL_100_CAGR",item["original_100pct_invested_fixed_sector_comparator"]["nav"]["annual_return_pct"],
                "MAX_DD",m["metrics"]["nav"]["max_drawdown_pct"],
                "CASH_BREACH_SESSIONS",m["cash_below_5pct_sessions_end_of_day"],
                "MIN_CASH",m["minimum_cash_fraction_during_investment"])
    print("NOT_ALPHA_NOT_BROKER_RELEASE",report["live_orders"])


if __name__=="__main__":
    main()
