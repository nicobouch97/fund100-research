"""Fund-100 V6-S1 exact 95%-invested historical/cash-floor diagnostic.

Uses original immutable research history and the PRE-EXISTING 50/30/20
sector thesis. Not a new tuned alpha strategy, nor an executable LIVE
order plan. Shows why a 5% cash TARGET cannot be called a 5% daily FLOOR.
"""
from __future__ import annotations

import argparse
import json
from math import isfinite, sqrt
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



def simulate_next_close_monthly(prices:pd.DataFrame, *, cost_bps:int,
                                reserve_fraction:float,
                                prefunded_buy_only:bool=False)->pd.DataFrame:
    """Separate causal monthly timing sensitivity; original model is untouched.

    A completed month-end close can only generate fixed SHARE quantities for
    the NEXT observed session's close. The next-close execution uses those
    quantities, not a newly fitted target. SELL proceeds finance BUYs; if a
    gap makes the full fixed order unaffordable, the whole rebalance is
    skipped, not funded with synthetic margin. Cash/weight drift and HIGH
    account-risk breaches remain visible; this is NOT a LIVE trading plan,
    a broker minimum-ticket proof or an automatic HARD STOP recovery.

    Optional prefunded_buy_only is a separate, fixed conservative
    counterfactual: the BUY leg must be payable from cash present BEFORE
    same-event SELLs. It does not certify that opening cash is settled.
    The original immediate-sale-credit historical path remains the default.
    """
    if (cost_bps not in l1.COST_BPS or type(reserve_fraction) is not float
        or reserve_fraction not in (FLOOR,.10,.15)
        or type(prefunded_buy_only) is not bool):
        raise S1EconomicsStop("Unregistered delayed monthly research scenario")
    data=l1.validate(prices)
    target={s:TARGET[s]*(1-reserve_fraction)/(1-FLOOR) for s in l1.NAMES}
    rate=cost_bps/10000.
    cash=float(l1.NAV0)
    benchmark=float(l1.NAV0)
    holdings={s:0. for s in l1.NAMES}
    pending=None
    engaged=False
    rows=[]
    for t,date in enumerate(data.index):
        px={s:float(data.iloc[t][s]) for s in l1.NAMES}
        if t:
            for s in l1.NAMES:
                holdings[s]*=px[s]/float(data.iloc[t-1][s])
            benchmark*=float(data.iloc[t][l1.BENCH]/data.iloc[t-1][l1.BENCH])
        nav=cash+sum(holdings.values())
        if not isfinite(nav) or nav<=0:
            raise S1EconomicsStop("Invalid next-close marked NAV")
        before_cash=bool(engaged and cash/nav<FLOOR-1e-10)
        before_single=bool(engaged and max(holdings.values())/nav>.5+EPS)
        traded=False
        turnover=0.
        executed_signal=None
        unaffordable=False
        unverified_sale_funding_hold=False
        if pending is not None:
            if t<=pending["index"]:
                raise S1EconomicsStop("Same-close hindsight monthly execution")
            quantities=pending["quantities"]
            dollars={s:quantities[s]*px[s] for s in l1.NAMES}
            sales=sum(-v for v in dollars.values() if v<0)
            purchases=sum(v for v in dollars.values() if v>0)
            # The entire precommitted share basket must be cash-funded.
            remaining=cash+sales*(1-rate)-purchases*(1+rate)
            # Opening cash is the pre-SELL cash observed at this fill
            # close. Even a filled SELL does not authenticate settlement.
            prefunded_shortfall=(
                prefunded_buy_only and purchases*(1+rate)>cash+1e-8)
            sale_credit_would_cover=(
                remaining>=-1e-8
                and all(-dollars[s]<=holdings[s]+1e-8 for s in l1.NAMES))
            unverified_sale_funding_hold=bool(
                prefunded_shortfall and sales>0 and sale_credit_would_cover)
            if (any(-dollars[s]>holdings[s]+1e-8 for s in l1.NAMES)
                or remaining < -1e-8 or prefunded_shortfall):
                unaffordable=True
            else:
                old_nav=nav
                for s in l1.NAMES:
                    holdings[s]+=dollars[s]
                    if holdings[s]<-1e-8:
                        raise S1EconomicsStop("Synthetic short position")
                    holdings[s]=max(0.,holdings[s])
                cash=max(0.,remaining)
                nav=cash+sum(holdings.values())
                if nav<=0 or not isfinite(nav):
                    raise S1EconomicsStop("Invalid post-execution account")
                turnover=(sales+purchases)/old_nav
                traded=bool(sales+purchases>1e-10)
                executed_signal=pending["session"] if traded else None
                engaged=engaged or traded
            pending=None
        nav=cash+sum(holdings.values())
        weights={s:holdings[s]/nav for s in l1.NAMES}
        signal=False
        if l1.month_end_session(data.index,t) and max(
                abs(target[s]-weights[s]) for s in l1.NAMES)>=l1.BAND:
            # Solve the same post-fee target at the SIGNAL close, then
            # freeze share quantities. No same-close rebalance is credited.
            post=nav
            for _ in range(100):
                notional=sum(abs(target[s]*post-holdings[s]) for s in l1.NAMES)
                nxt=nav-rate*notional
                if not isfinite(nxt) or nxt<=0:
                    raise S1EconomicsStop("Invalid delayed rebalance intent")
                if abs(nxt-post)<=1e-12*nav:
                    post=nxt
                    break
                post=nxt
            else:
                raise S1EconomicsStop("Delayed fee solver did not converge")
            pending={
                "index":t,"session":date.date().isoformat(),
                "quantities":{s:(target[s]*post-holdings[s])/px[s]
                              for s in l1.NAMES},
            }
            signal=True
        if (not isfinite(cash) or cash<0
            or any(not isfinite(v) or v<0 for v in holdings.values())):
            raise S1EconomicsStop("Invalid delayed holdings/cash")
        rows.append({
            "date":date,"nav":nav,"acwi_nav":benchmark,
            "turnover":turnover,"trade":traded,
            "gross_risk_exposure":sum(weights.values()),
            "cash":cash/nav,"invested":engaged,
            "risk_off_at_decision":False,"risk_month_end_vol":None,
            "cash_floor_breach_before_trade":before_cash,
            "cash_floor_breach_end_of_day":bool(engaged and cash/nav<FLOOR-1e-10),
            "single_symbol_breach_before_trade":before_single,
            "single_symbol_breach_end_of_day":bool(engaged and max(weights.values())>.5+EPS),
            "daily_floor_trim":False,
            "month_end_rebalance":traded,
            "monthly_rebalance_signal":signal,
            "monthly_rebalance_execution":traded,
            "executed_prior_close_signal_session":executed_signal,
            "unaffordable_next_close_rebalance":unaffordable,
            "unverified_sale_funding_hold":unverified_sale_funding_hold,
            "prefunded_buy_only_counterfactual":prefunded_buy_only,
            "pending_unexecuted_signal_at_final_close":bool(
                t==len(data)-1 and pending is not None),
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
    diagnostic=period_diagnostics(path,start)
    return {
        "costed_path":diagnostic,
        "all_cash_and_single_symbol_limits_met_at_daily_close":bool(
            len(invested) and
            diagnostic["cash_below_5pct_sessions_end_of_day"]==0 and
            diagnostic["sector_weight_over_50pct_sessions"]==0),
        "month_end_trade_events":int(sub["month_end_rebalance"].sum()),
        "daily_trim_events":int(sub["daily_floor_trim"].sum()),
        "cash_floor_satisfied_at_all_invested_closes":bool(
            len(invested) and (invested["cash"]>=FLOOR-1e-10).all()),
        "still_requires_intraday_and_broker_cash_validation":True,
        "fixed_buffer_not_an_optimized_or_released_strategy":True,
        "no_independent_alpha_claim":True,
    }


def high_risk_eod_feasibility(path:pd.DataFrame,start:str)->dict:
    """Descriptive HIGH-risk breaches on an UNINTERRUPTED hypothetical NAV.

    Do not infer executable performance after the first STOP: this research
    path deliberately continues to show the original strategy's economics.
    The 70-close rolling peak and 69-return volatility are approximations
    of the existing broker-history risk horizon, NOT a LIVE risk attestation.
    No deposits/withdrawals or broker intraday marks are represented.
    """
    # Build trailing risk windows from all prior invested closes, even when
    # reporting a later subperiod such as 2020 onward.
    active=path.loc[path["invested"]]
    if len(active)<6:
        raise S1EconomicsStop("Too few invested closes for HIGH risk diagnosis")
    nav=active["nav"].astype(float)
    if (not nav.map(isfinite).all() or (nav<=0).any()
        or nav.index.has_duplicates or not nav.index.is_monotonic_increasing):
        raise S1EconomicsStop("Invalid risk diagnostic equity history")
    daily=nav.pct_change(fill_method=None)
    rolling_dd=1-nav/nav.rolling(70,min_periods=1).max()
    # At least five real daily returns, not an invented zero return.
    rolling_vol=daily.rolling(69,min_periods=5).std(ddof=1)*sqrt(252)
    loss_hit=daily.lt(-.06)
    draw_hit=rolling_dd.gt(.20)
    vol_hit=rolling_vol.gt(.35)
    cash_hit=active["cash_floor_breach_end_of_day"].astype(bool)
    concentration_hit=active["single_symbol_breach_end_of_day"].astype(bool)
    # Scope only the counts to the requested era; retain the earlier
    # 70-close risk history used by its first observations.
    daily=daily.loc[start:]
    rolling_dd=rolling_dd.loc[start:]
    rolling_vol=rolling_vol.loc[start:]
    loss_hit=loss_hit.loc[start:]
    draw_hit=draw_hit.loc[start:]
    vol_hit=vol_hit.loc[start:]
    cash_hit=cash_hit.loc[start:]
    concentration_hit=concentration_hit.loc[start:]
    if not len(daily):
        raise S1EconomicsStop("No invested closes in requested risk period")
    risk_hit=loss_hit|draw_hit|vol_hit
    combined=risk_hit|cash_hit|concentration_hit

    # Attribute the FIRST breach, rather than conflating a cash/weight
    # maintenance violation with an account-level HIGH emergency STOP.
    # These are retrospective completed-close observations, not authority
    # to restart, liquidate or override a real operator STOP.
    first_combined_detail=None
    if combined.any():
        at=combined.index[combined][0]
        flags={
            "daily_account_loss":bool(loss_hit.loc[at]),
            "rolling_70_close_drawdown":bool(draw_hit.loc[at]),
            "rolling_69_return_volatility":bool(vol_hit.loc[at]),
            "cash_below_5pct":bool(cash_hit.loc[at]),
            "single_symbol_above_50pct":bool(concentration_hit.loc[at]),
        }
        hard_risk=any(flags[k] for k in (
            "daily_account_loss","rolling_70_close_drawdown",
            "rolling_69_return_volatility"))
        weight_columns=["weight_"+symbol for symbol in l1.NAMES]
        first_combined_detail={
            "date":at.date().isoformat(),
            "triggered_constraints":[key for key,value in flags.items() if value],
            "account_high_risk_threshold_triggered":hard_risk,
            "portfolio_cash_or_concentration_only":not hard_risk,
            "cash_fraction_at_breach":(
                float(active.loc[at,"cash"]) if "cash" in active else None),
            "largest_symbol_weight_fraction_at_breach":(
                max(float(active.loc[at,col]) for col in weight_columns)
                if all(col in active for col in weight_columns) else None),
            "not_a_live_hard_stop_classification_or_trade_authority":True,
        }

    def first(mask:pd.Series)->str|None:
        matches=mask.index[mask]
        return matches[0].date().isoformat() if len(matches) else None

    return {
        "high_daily_loss_limit_fraction":.06,
        "high_rolling_drawdown_limit_fraction":.20,
        "high_annual_realized_volatility_limit":.35,
        "daily_loss_breach_closes":int(loss_hit.sum()),
        "rolling_70_close_drawdown_breach_closes":int(draw_hit.sum()),
        "rolling_69_return_volatility_breach_closes":int(vol_hit.sum()),
        "cash_floor_breach_closes":int(cash_hit.sum()),
        "single_symbol_concentration_breach_closes":int(concentration_hit.sum()),
        "any_high_account_risk_breach_closes":int(risk_hit.sum()),
        "any_combined_risk_cash_concentration_breach_closes":int(combined.sum()),
        "first_high_account_risk_breach_date":first(risk_hit),
        "first_combined_breach_date":first(combined),
        "first_combined_breach_attribution":first_combined_detail,
        "worst_modelled_daily_return_pct":round(100*float(daily.min()),5),
        "worst_rolling_70_close_drawdown_pct":round(100*float(rolling_dd.max()),5),
        "latest_rolling_70_close_drawdown_pct":round(100*float(rolling_dd.iloc[-1]),5),
        "highest_rolling_69_return_volatility_pct":round(
            100*float(rolling_vol.max()),5) if rolling_vol.notna().any() else None,
        "all_observed_high_account_risk_limits_met":bool(not risk_hit.any()),
        "all_observed_high_risk_cash_and_concentration_limits_met":bool(
            not combined.any()),
        "first_five_returns_have_insufficient_volatility_history":True,
        "rolling_windows_include_prior_invested_closes_before_report_period":True,
        "intraday_risk_and_broker_cashflows_not_observed":True,
        "risk_stops_not_simulated_returns_after_first_stop_counterfactual":True,
        "research_only_not_live_release":True,
    }



def hypothetical_first_stop_next_close_cash(
        path:pd.DataFrame, prices:pd.DataFrame, *, cost_bps:int)->tuple[pd.DataFrame,dict]:
    """Research-only absorbing STOP sensitivity, NOT a funded liquidation policy.

    Detect the FIRST combined HIGH-risk/cash/concentration breach on the
    uninterrupted daily-close path. No same-close execution or knowledge of
    the next close is assumed: hold the breached positions for one further
    session, then hypothetically sell ALL at that next completed close,
    charge the registered one-way cost, and hold unremunerated cash forever.
    No re-entry or recovery is modeled. The original strategy path is not
    modified. This does not guarantee a fill, cash settlement, intraday
    protection, a real STOP response, or an authorised sale.
    """
    if cost_bps not in l1.COST_BPS:
        raise S1EconomicsStop("Only original 5/15/35bps cost stress permitted")
    data=l1.validate(prices)
    if not path.index.equals(data.index) or len(path)<7:
        raise S1EconomicsStop("Stop sensitivity requires exact ordered price sessions")
    required={"nav","invested","cash_floor_breach_end_of_day",
              "single_symbol_breach_end_of_day","acwi_nav","turnover","trade",
              "gross_risk_exposure","cash","risk_off_at_decision"}
    required.update("weight_"+s for s in l1.NAMES)
    if not required.issubset(path.columns):
        raise S1EconomicsStop("Missing original portfolio/stop observations")
    risk_report=high_risk_eod_feasibility(
        path,path.index[0].date().isoformat())
    first=risk_report["first_combined_breach_date"]
    out=path.copy(deep=True)
    assumptions={
        "first_combined_breach_date":first,
        "first_combined_breach_attribution":risk_report[
            "first_combined_breach_attribution"],
        "hypothetical_next_close_exit_date":None,
        "hypothetical_exit_fee_nav_units":None,
        "hypothetical_exit_turnover_fraction":None,
        "hypothetical_flat_cash_after_exit":False,
        "breach_detected_only_after_completed_close":True,
        "next_close_fill_and_immediate_cash_settlement_assumed":True,
        "no_restart_or_new_risk_allocation_after_exit":True,
        "not_a_live_stop_or_liquidation_authorization":True,
        "intraday_gaps_slippage_and_real_broker_execution_unverified":True,
    }
    if first is None:
        return out,assumptions
    i=path.index.get_loc(pd.Timestamp(first))
    if not isinstance(i,int):
        raise S1EconomicsStop("Ambiguous first breach index")
    if i==len(path)-1:
        assumptions["breach_at_last_observation_exit_not_yet_observable"]=True
        return out,assumptions
    row=path.iloc[i]
    weights={s:float(row["weight_"+s]) for s in l1.NAMES}
    gross=sum(weights.values())
    nav=float(row["nav"])
    if (not isfinite(nav) or nav<=0 or any(not isfinite(w) or w<0 for w in weights.values())
        or gross>1+EPS or not bool(row["invested"])):
        raise S1EconomicsStop("Invalid holdings at first stop")
    ratios={s:float(data.iloc[i+1][s]/data.iloc[i][s]) for s in l1.NAMES}
    if any(not isfinite(x) or x<=0 for x in ratios.values()):
        raise S1EconomicsStop("Invalid next-close exit prices")
    # Do not use the original simulator's next-day NAV: it might have
    # performed a month-end rebalance that a STOP would prohibit.
    cash_value=nav*(1-gross)
    liquidation_value=sum(nav*weights[s]*ratios[s] for s in l1.NAMES)
    fee=liquidation_value*cost_bps/10_000.
    net=cash_value+liquidation_value-fee
    if not isfinite(net) or net<=0:
        raise S1EconomicsStop("Hypothetical exit insolvent")
    exit_date=path.index[i+1]
    assumptions["hypothetical_next_close_exit_date"]=exit_date.date().isoformat()
    assumptions["hypothetical_exit_fee_nav_units"]=round(fee,10)
    assumptions["hypothetical_exit_turnover_fraction"]=round(
        liquidation_value/(cash_value+liquidation_value),10)
    assumptions["hypothetical_flat_cash_after_exit"]=True
    # A combined STOP at the completed signal close supersedes any
    # ordinary monthly rebalance intent created at that same close.
    if "monthly_rebalance_signal" in out.columns:
        out.at[path.index[i],"monthly_rebalance_signal"]=False
    if "pending_unexecuted_signal_at_final_close" in out.columns:
        out.at[path.index[i],"pending_unexecuted_signal_at_final_close"]=False
    for t in range(i+1,len(out)):
        day=out.index[t]
        out.at[day,"nav"]=net
        out.at[day,"gross_risk_exposure"]=0.
        out.at[day,"cash"]=1.
        out.at[day,"invested"]=False
        out.at[day,"turnover"]=(
            liquidation_value/(cash_value+liquidation_value) if t==i+1 else 0.)
        out.at[day,"trade"]=bool(t==i+1)
        out.at[day,"risk_off_at_decision"]=False
        out.at[day,"cash_floor_breach_before_trade"]=False
        out.at[day,"cash_floor_breach_end_of_day"]=False
        out.at[day,"single_symbol_breach_before_trade"]=False
        out.at[day,"single_symbol_breach_end_of_day"]=False
        for symbol in l1.NAMES:
            out.at[day,"weight_"+symbol]=0.
        for optional in (
            "daily_floor_trim","month_end_rebalance",
            "monthly_rebalance_signal","monthly_rebalance_execution",
            "unaffordable_next_close_rebalance","unverified_sale_funding_hold",
            "pending_unexecuted_signal_at_final_close",
        ):
            if optional in out.columns:
                out.at[day,optional]=False
        if "executed_prior_close_signal_session" in out.columns:
            out.at[day,"executed_prior_close_signal_session"]=None
    return out,assumptions


# Distinct hypothetical launch cohorts, fixed before inspecting these results.
# A 2008 stop in a continuously invested strategy must not be silently
# inherited by a genuinely NEW 2014 or 2020 account inception. Conversely,
# merely resetting a backtest is not an authorised real-world STOP restart.
FRESH_INCEPTION_DATES={
    "2014_fresh_inception":"2014-01-01",
    "2020_fresh_inception":"2020-01-01",
}


def fresh_inception_first_stop_sensitivity(
        prices:pd.DataFrame, *, cost_bps:int, reserve_fraction:float|None)->dict:
    """Costed no-restart STOP paths for independent historical launch dates.

    Each cohort begins in cash with NAV=100 and the SAME 40-session warmup,
    10pp month-end rebalance rule, 50/30/20 sector mix and 5/15/35bp costs.
    Account drawdown and volatility start at cohort inception, rather than
    inheriting an unrelated account's pre-inception risk history. This is
    retrospective scenario analysis on already inspected data, not an
    optimised re-entry signal, actual account restart or trade permission.
    """
    if cost_bps not in l1.COST_BPS or reserve_fraction not in (None,.10,.15):
        raise S1EconomicsStop("Only original S1 costs and registered buffers")
    data=l1.validate(prices)
    cohorts={}
    for label,start in FRESH_INCEPTION_DATES.items():
        launched=data.loc[start:].copy()
        # Prevent an apparent zero-risk result from a truncated history
        # with no possible qualified investment or 1-year return window.
        if len(launched)<840:
            raise S1EconomicsStop("Insufficient original sessions for fresh inception")
        unhalted=(simulate(launched,cost_bps=cost_bps) if reserve_fraction is None
                  else simulate_daily_cash_floor(
                      launched,cost_bps=cost_bps,
                      reserve_fraction=reserve_fraction,daily_trims=False))
        active=unhalted.index[unhalted["invested"]]
        if not len(active):
            raise S1EconomicsStop("Fresh inception never reached a first investment")
        stopped,assumptions=hypothetical_first_stop_next_close_cash(
            unhalted,launched,cost_bps=cost_bps)
        cohorts[label]={
            "requested_inception_date":start,
            "first_observed_market_session":launched.index[0].date().isoformat(),
            "first_invested_close":active[0].date().isoformat(),
            "fresh_initial_nav":l1.NAV0,
            "pre_inception_trades_or_stops_inherited":False,
            "risk_history_restarted_only_for_new_hypothetical_account":True,
            "warmup_and_costed_initial_entry_included":True,
            "stop_and_exit_assumptions":assumptions,
            "fresh_inception_no_restart_metrics":l1.metrics(stopped,start),
            "uninterrupted_returns_after_stop_counterfactual":True,
            "previously_inspected_history_not_independent_alpha":True,
            "not_a_live_restart_or_trading_authorization":True,
        }
    return cohorts


def fresh_prefunded_next_close_first_breach_sensitivity(
        prices:pd.DataFrame, *, cost_bps:int, reserve_fraction:float)->dict:
    """Combined funding + next-close + absorbing first-breach economics.

    Two genuinely separate hypothetical 2014/2020 cash-account inceptions
    reset the risk history. A completed-close HIGH account-risk, cash-floor
    or issuer-concentration breach cancels pending monthly rotation and
    hypothetically liquidates at the FOLLOWING close, with a sale fee.
    There is no re-entry. This uses the repeatedly inspected frozen history,
    not a new independent alpha test, and does NOT authenticate opening cash,
    brokerage fills, settlement or an executable sub-$1 exit.
    """
    if (cost_bps not in l1.COST_BPS
        or type(reserve_fraction) is not float
        or reserve_fraction not in (FLOOR,.10,.15)):
        raise S1EconomicsStop("Unregistered prefunded HIGH stop sensitivity")
    data=l1.validate(prices)
    results={}
    for label,start in FRESH_INCEPTION_DATES.items():
        launched=data.loc[start:].copy()
        if len(launched)<840:
            raise S1EconomicsStop("Insufficient frozen history for fresh inception")
        unhalted=simulate_next_close_monthly(
            launched,cost_bps=cost_bps,reserve_fraction=reserve_fraction,
            prefunded_buy_only=True)
        if not unhalted["invested"].any():
            raise S1EconomicsStop("No first investment in prefunded scenario")
        stopped,stop=hypothetical_first_stop_next_close_cash(
            unhalted,launched,cost_bps=cost_bps)
        first=stop["first_combined_breach_date"]
        before=unhalted.loc[:first] if first is not None else unhalted
        exit_date=stop["hypothetical_next_close_exit_date"]
        if exit_date is not None:
            after=stopped.loc[exit_date:]
            if (not (after["gross_risk_exposure"]==0).all()
                or not (after["cash"]==1).all()
                or after["monthly_rebalance_execution"].any()
                or after["monthly_rebalance_signal"].any()
                or after["unverified_sale_funding_hold"].any()):
                raise S1EconomicsStop("Absorbing STOP leaked a future rotation")
        results[label]={
            "requested_inception":start,
            "first_invested_close":unhalted.index[
                unhalted["invested"]][0].date().isoformat(),
            "first_combined_breach_close":first,
            "first_breach_reasons":(
                (stop["first_combined_breach_attribution"] or {})
                .get("triggered_constraints",[])),
            "hypothetical_next_close_exit":exit_date,
            "hypothetical_exit_fee_nav_units":stop[
                "hypothetical_exit_fee_nav_units"],
            "costed_no_restart_cagr_pct":l1.metrics(
                stopped,start)["nav"]["annual_return_pct"],
            "uninterrupted_prefunded_cagr_not_executable_pct":l1.metrics(
                unhalted,start)["nav"]["annual_return_pct"],
            "prefunded_monthly_rotations_through_first_breach":int(
                before["monthly_rebalance_execution"].sum()),
            "unverified_sale_funding_holds_through_first_breach":int(
                before["unverified_sale_funding_hold"].sum()),
            "post_exit_cash_only_closes":(
                len(stopped.loc[exit_date:])-1 if exit_date else 0),
            "breach_on_last_close_has_no_invented_exit":bool(
                stop.get("breach_at_last_observation_exit_not_yet_observable",False)),
            "cash_only_after_hypothetical_exit_no_restart":bool(
                stop["hypothetical_flat_cash_after_exit"]),
            "first_breach_includes_cash_and_concentration_not_only_high_stop":True,
            "initial_cash_is_not_authenticated_settlement":True,
            "same_frozen_history_not_independent_alpha":True,
            "idealized_next_close_exit_not_broker_proven":True,
            "new_live_trade_authority":False,
        }
    return results


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
      "high_risk_stop_feasibility":high_risk_eod_feasibility(path,start),
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
    # Absorbing STOP counterfactual on the SAME frozen history. Unlike the
    # uninterrupted CAGR above, this explicitly stops after the FIRST
    # completed-close violation and never assumes automatic re-entry.
    stop_cash_sensitivity={}
    for label,reserve in (("original_95pct",None),("10pct_buffer",.10),
                          ("15pct_buffer",.15)):
        stop_cash_sensitivity[label]={}
        for bp in l1.COST_BPS:
            unhalted=(simulate(data,cost_bps=bp) if reserve is None
                      else simulate_daily_cash_floor(
                          data,cost_bps=bp,reserve_fraction=reserve,
                          daily_trims=False))
            stopped,stop_assumptions=hypothetical_first_stop_next_close_cash(
                unhalted,data,cost_bps=bp)
            stop_cash_sensitivity[label][str(bp)]={
                "stop_and_exit_assumptions":stop_assumptions,
                "after_first_stop_hypothetical_cash_hold_metrics":{
                    name:l1.metrics(stopped,start)
                    for name,start in (("2014_onward","2014-01-01"),
                                       ("2020_onward","2020-01-01"))
                },
            }
    # Do not confuse the full-history 2008 absorbing STOP with an account
    # actually launched afresh in 2014/2020. This is a separate historical
    # inception sensitivity, never a recovery from an earlier hard STOP.
    fresh_inception_stops={}
    for label,reserve in (("original_95pct",None),("10pct_buffer",.10),
                          ("15pct_buffer",.15)):
        fresh_inception_stops[label]={
            str(bp):fresh_inception_first_stop_sensitivity(
                data,cost_bps=bp,reserve_fraction=reserve)
            for bp in l1.COST_BPS
        }
    # Correct the month-end signal/fill chronology separately from the
    # original same-close study. These fixed-share next-close fills are
    # retrospective, not a promotion or a hard-STOP-compliant return path.
    next_close_monthly={}
    for label,reserve in (("original_95pct",FLOOR),
                          ("10pct_buffer",.10),("15pct_buffer",.15)):
        next_close_monthly[label]={}
        for bp in l1.COST_BPS:
            delayed=simulate_next_close_monthly(
                data,cost_bps=bp,reserve_fraction=reserve)
            prefunded=simulate_next_close_monthly(
                data,cost_bps=bp,reserve_fraction=reserve,
                prefunded_buy_only=True)
            # Fee-matched original month-end CLOSE fills are the proper
            # counterfactual; the legacy 95% simulator uses a different,
            # more favorable fee-financing convention.
            same_close=simulate_daily_cash_floor(
                data,cost_bps=bp,reserve_fraction=reserve,daily_trims=False)
            next_close_monthly[label][str(bp)]={
                name:{
                    "costed_path":period_diagnostics(delayed,start),
                    "fee_matched_same_close_cagr_pct":l1.metrics(
                        same_close,start)["nav"]["annual_return_pct"],
                    "legacy_95_fee_convention_not_used_for_timing_attribution":True,
                    "month_end_signals":int(delayed.loc[start:,"monthly_rebalance_signal"].sum()),
                    "following_close_executions":int(delayed.loc[start:,"monthly_rebalance_execution"].sum()),
                    "unaffordable_full_order_skips":int(delayed.loc[start:,"unaffordable_next_close_rebalance"].sum()),
                    "prefunded_only_cagr_pct":l1.metrics(
                        prefunded,start)["nav"]["annual_return_pct"],
                    "prefunded_only_minus_sale_credit_cagr_pp":round(
                        l1.metrics(prefunded,start)["nav"]["annual_return_pct"]
                        - l1.metrics(delayed,start)["nav"]["annual_return_pct"],5),
                    "prefunded_only_executions":int(
                        prefunded.loc[start:,"monthly_rebalance_execution"].sum()),
                    "prefunded_only_unverified_sale_funding_holds":int(
                        prefunded.loc[start:,"unverified_sale_funding_hold"].sum()),
                    "prefunded_only_total_unaffordable_skips":int(
                        prefunded.loc[start:,"unaffordable_next_close_rebalance"].sum()),
                    "prefunded_opening_cash_not_authenticated_settlement":True,
                    "unexecuted_final_close_signal":bool(
                        delayed.iloc[-1]["pending_unexecuted_signal_at_final_close"]),
                    "no_same_close_fill_or_broker_minimum_assumed":True,
                    "hard_account_stops_not_simulated":True,
                } for name,start in (("2014_onward","2014-01-01"),
                                     ("2020_onward","2020-01-01"))
            }
    # Combine PR #502's prefunded-only cash restriction with the existing
    # first-breach/next-close/no-restart HIGH-risk research, rather than
    # quoting uninterrupted high CAGR after a hypothetical hard STOP.
    # Fixed original 5/15/35bp costs and 5/10/15% cash scenarios only.
    fresh_prefunded_stop={}
    for label,reserve in (("original_95pct",FLOOR),
                          ("10pct_buffer",.10),("15pct_buffer",.15)):
        fresh_prefunded_stop[label]={
            str(bp):fresh_prefunded_next_close_first_breach_sensitivity(
                data,cost_bps=bp,reserve_fraction=reserve)
            for bp in l1.COST_BPS
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
      "first_combined_breach_next_close_exit_then_cash_sensitivity":stop_cash_sensitivity,
      "first_stop_exit_is_idealized_not_executable":True,
      "fresh_inception_first_stop_next_close_cash_sensitivity":fresh_inception_stops,
      "fresh_inception_is_not_a_hard_stop_recovery":True,
      "causal_next_close_monthly_rebalance_sensitivity":next_close_monthly,
      "fresh_prefunded_next_close_first_breach_no_restart":fresh_prefunded_stop,
      "fresh_prefunded_stop_is_not_live_broker_settlement_proof":True,
      "original_same_close_historical_results_preserved":True,
      "next_close_monthly_research_does_not_prove_broker_fills_or_alpha":True,
      "prefunded_next_close_is_fixed_conservative_funding_sensitivity_only":True,
      "prefunded_next_close_cannot_prove_opening_cash_settlement":True,
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
    # Keep observed HIGH-risk violations visible in the same CI evidence as
    # attractive CAGR figures; modeled NAV continues after hypothetical STOP.
    for reserve in ("10","15"):
        for name in ("2014_onward","2020_onward"):
            x=report["fixed_10_and_15pct_passive_cash_buffer_sensitivities"][
                reserve]["15"][name]["costed_path"]["high_risk_stop_feasibility"]
            print("PASSIVE_BUFFER_HIGH_RISK",reserve,name,
                  "ACCOUNT_RISK_BREACH_CLOSES",x["any_high_account_risk_breach_closes"],
                  "COMBINED_BREACH_CLOSES",x["any_combined_risk_cash_concentration_breach_closes"],
                  "FIRST_COMBINED",x["first_combined_breach_date"],
                  "RETURNS_AFTER_STOP_COUNTERFACTUAL",
                  x["risk_stops_not_simulated_returns_after_first_stop_counterfactual"])
    for label in ("original_95pct","10pct_buffer","15pct_buffer"):
        x=report["first_combined_breach_next_close_exit_then_cash_sensitivity"][
            label]["15"]
        a=x["stop_and_exit_assumptions"]
        m=x["after_first_stop_hypothetical_cash_hold_metrics"]["2014_onward"]
        print("FIRST_STOP_NEXT_CLOSE_CASH",label,
              "BREACH",a["first_combined_breach_date"],
              "EXIT",a["hypothetical_next_close_exit_date"],
              "CASH_HOLD_CAGR",m["nav"]["annual_return_pct"],
              "UNEXECUTABLE_SENSITIVITY",True)
    for label in ("original_95pct","10pct_buffer","15pct_buffer"):
        for cohort in FRESH_INCEPTION_DATES:
            x=report["fresh_inception_first_stop_next_close_cash_sensitivity"][
                label]["15"][cohort]
            a=x["stop_and_exit_assumptions"]
            m=x["fresh_inception_no_restart_metrics"]
            print("FRESH_INCEPTION_FIRST_STOP",label,cohort,
                  "ENTRY",x["first_invested_close"],
                  "BREACH",a["first_combined_breach_date"],
                  "EXIT",a["hypothetical_next_close_exit_date"],
                  "FIRST_BREACH_TRIGGERS",",".join(
                      (a["first_combined_breach_attribution"] or {})
                      .get("triggered_constraints",[])),
                  "ACCOUNT_HIGH_RISK_STOP",(
                      (a["first_combined_breach_attribution"] or {})
                      .get("account_high_risk_threshold_triggered")),
                  "COSTED_CAGR_PCT",m["nav"]["annual_return_pct"],
                  "ACWI_CAGR_PCT",m["acwi_nav"]["annual_return_pct"],
                  "RESEARCH_ONLY",True)
    for label in ("original_95pct","10pct_buffer","15pct_buffer"):
        for era in ("2014_onward","2020_onward"):
            d=report["causal_next_close_monthly_rebalance_sensitivity"][
                label]["15"][era]
            metrics=d["costed_path"]
            print("NEXT_CLOSE_MONTHLY_CAUSAL",label,era,
                  "CAGR_PCT",metrics["metrics"]["nav"]["annual_return_pct"],
                  "FEE_MATCHED_SAME_CLOSE_CAGR_PCT",
                  d["fee_matched_same_close_cagr_pct"],
                  "CASH_BREACH_CLOSES",metrics["cash_below_5pct_sessions_end_of_day"],
                  "CONCENTRATION_BREACH_CLOSES",metrics["sector_weight_over_50pct_sessions"],
                  "HARD_RISK_BREACH_CLOSES",metrics["high_risk_stop_feasibility"][
                      "any_high_account_risk_breach_closes"],
                  "SIGNALS",d["month_end_signals"],
                  "EXECUTED",d["following_close_executions"],
                  "UNAFFORDABLE",d["unaffordable_full_order_skips"],
                  "NOT_EXECUTABLE_OR_ALPHA",True)
    for reserve in ("original_95pct","10pct_buffer","15pct_buffer"):
        for cohort in FRESH_INCEPTION_DATES:
            result=report["fresh_prefunded_next_close_first_breach_no_restart"][
                reserve]["15"][cohort]
            print("PREFUNDED_NEXT_CLOSE_FIRST_BREACH",reserve,cohort,
                  "BREACH",result["first_combined_breach_close"],
                  "NEXT_CLOSE_EXIT",result["hypothetical_next_close_exit"],
                  "NO_RESTART_CAGR",result["costed_no_restart_cagr_pct"],
                  "UNINTERRUPTED_CAGR_NOT_EXECUTABLE",
                  result["uninterrupted_prefunded_cagr_not_executable_pct"],
                  "PREFUNDING_HOLDS_BEFORE_BREACH",
                  result["unverified_sale_funding_holds_through_first_breach"],
                  "NOT_ALPHA_OR_LIVE",True)
    print("NOT_ALPHA_NOT_BROKER_RELEASE",report["live_orders"])


if __name__=="__main__":
    main()
