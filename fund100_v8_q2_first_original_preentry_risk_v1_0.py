"""Source-pinned V8-Q2 first eligible 8-stock portfolio trailing risk, NO BROKER.

Uses 2026-10-29 completed price history and original 2026-10-30 08:16
frozen SEC/price/selection SHA256 pin. All 63/126/252-session return
windows PRECEDE first eligible forward entry; the selection was chosen
using these same prices. Therefore figures are hindsight-conditioned
covariance/exposure diagnostics, not a backtest, forecast, executable
risk guard or independent evidence of alpha.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import fund100_stock_broad_momentum_p4l_v1_0 as cohort
import fund100_v8_q2_frozen_forward_63_marks_v1_0 as frozen

SCHEMA="FUND100_V8_Q2_FIRST_ORIGINAL_EIGHT_STOCK_TRAILING_RISK_NO_ORDERS_V1"
WINDOWS=(63,126,252)
SESSIONS_PER_YEAR=252
INVESTED=.95
MAX_VOL=.35
MAX_DAILY_LOSS=.06
MAX_DRAWDOWN=.20
MAX_SECTOR=.25
COSTS_BPS=(5,15,35)
BROKER_GETS=BROKER_POSTS=BROKER_ORDERS=0
LIVE_AUTHORIZED=False

class RiskHold(ValueError):
    pass


def _round(value):
    if not math.isfinite(float(value)):
        raise RiskHold("Nonfinite original risk diagnostic")
    return round(float(value),8)


def _path_metrics(returns:pd.DataFrame, weights:dict[str,float]) -> dict:
    """Hypothetical DAILY fixed-weight return covariance, not actual orders.

    The 95% risky budget and 5% zero-return cash are modeled directly.
    The rebalanced daily return proxy deliberately excludes execution fees.
    """
    if (type(weights) is not dict or not weights
        or not math.isclose(sum(weights.values()),1.,abs_tol=1e-12)
        or any(not 0 <= w <= 1 for w in weights.values())
        or not set(weights)<=set(returns.columns)):
        raise RiskHold("Unexpected hypothetical basket weights")
    weighted=INVESTED*sum((returns[s]*w for s,w in weights.items()))
    if (weighted.isna().any() or (weighted<=-1).any()
        or not np.isfinite(weighted.to_numpy()).all()):
        raise RiskHold("Invalid source-derived daily return")
    path=np.r_[1.,np.cumprod(1.+weighted.to_numpy())]
    maxima=np.maximum.accumulate(path)
    dd=path/maxima-1.
    return {
        "annualized_close_to_close_volatility":_round(
            weighted.std(ddof=1)*math.sqrt(SESSIONS_PER_YEAR)),
        "worst_observed_daily_return":_round(weighted.min()),
        "max_observed_compounded_close_drawdown":_round(dd.min()),
        "daily_return_below_negative_6pct_count":int(
            (weighted<=-MAX_DAILY_LOSS).sum()),
        "historical_drawdown_exceeded_20pct":bool(dd.min()<=-MAX_DRAWDOWN),
        "proxy_gross_return_rebalanced_daily_not_tradable":True,
        "hypothetical_daily_turnover_costs_not_modeled":True,
    }



def _buy_once_costed_risk(returns:pd.DataFrame, weights:dict[str,float],
                          fee_bps:int) -> dict:
    """Buy once at the pre-window close; hold drifting shares, no rebalances.

    The first window return is earned AFTER the hypothetical purchase.
    Entry fees are funded from the same initial $100. The pre-entry $100
    high-water mark captures the fee drawdown. No terminal sale is assumed,
    so this is an unrealized close-marked path, not a realized net return.
    All selected securities were picked using these SAME historical prices.
    """
    if (fee_bps not in COSTS_BPS or type(weights) is not dict or not weights
        or not math.isclose(sum(weights.values()),1.,abs_tol=1e-12)
        or not set(weights)<=set(returns.columns)
        or any(type(w) not in (float,int) or not math.isfinite(w)
               or w<0 or w>1 for w in weights.values())
        or len(returns)<2):
        raise RiskHold("Invalid buy-once source weights or registered costs")
    selected=returns[list(weights)]
    if (selected.isna().any().any()
        or not np.isfinite(selected.to_numpy()).all()
        or (selected<=-1).any().any()):
        raise RiskHold("Invalid buy-once original close returns")
    fee=fee_bps/10000.
    after_entry=100./(1.+INVESTED*fee)
    cash=(1.-INVESTED)*after_entry
    positions={s:INVESTED*after_entry*w for s,w in weights.items()}
    path=[100.,after_entry]
    daily=[]
    gross=[]
    largest=[]
    sectors=[]
    has_sector=all(s in cohort.SECTORS for s in weights)
    for _,row in selected.iterrows():
        for s in positions:
            positions[s]*=1.+float(row[s])
        risky=sum(positions.values())
        nav=cash+risky
        if not math.isfinite(nav) or nav<=0:
            raise RiskHold("Nonfinite buy-once mark")
        daily.append(nav/path[-1]-1.)
        path.append(nav)
        gross.append(risky/nav)
        largest.append(max(positions.values())/nav)
        if has_sector:
            by_sector={}
            for s,value in positions.items():
                sector=cohort.SECTORS[s]
                by_sector[sector]=by_sector.get(sector,0.)+value
            sectors.append(max(by_sector.values())/nav)
    maxima=np.maximum.accumulate(np.asarray(path,dtype=float))
    drawdowns=np.asarray(path)/maxima-1.
    return {
        "entry_cost_bps_per_traded_side":fee_bps,
        "initial_entry_cost_usd_per_100":_round(100.-after_entry),
        "marked_unrealized_return_after_entry_cost_pct":
            _round(path[-1]-100.),
        "annualized_close_to_close_volatility":_round(
            np.std(daily,ddof=1)*math.sqrt(SESSIONS_PER_YEAR)),
        "worst_observed_daily_return":_round(min(daily)),
        "max_observed_compounded_close_drawdown":_round(drawdowns.min()),
        "max_observed_gross_exposure_fraction":_round(max(gross)),
        "gross_over_95pct_completed_close_count":sum(
            v>INVESTED+1e-10 for v in gross),
        "max_observed_single_issuer_fraction":_round(max(largest)),
        "single_issuer_over_50pct_completed_close_count":sum(
            v>.50+1e-10 for v in largest),
        "max_observed_sector_fraction":_round(max(sectors)) if has_sector else None,
        "sector_over_25pct_completed_close_count":sum(
            v>MAX_SECTOR+1e-10 for v in sectors) if has_sector else None,
        "entry_fee_in_initial_high_water_drawdown":True,
        "terminal_exit_cost_not_charged":True,
        "no_rebalance_or_additional_turnover":True,
        "selection_conditioned_historical_close_only_not_forward_alpha":True,
        "not_an_executable_intraday_risk_control":True,
    }



def _sector_aware_sell_only_repair(positions:dict[str,float],cash:float,fee:float):
    """Minimum sell at next completed close; post-fee sector/name/gross caps."""
    if (not positions or not all(s in cohort.SECTORS for s in positions)
        or not math.isfinite(cash) or cash<0 or fee not in (.0005,.0015,.0035)
        or any(not math.isfinite(v) or v<0 for v in positions.values())):
        raise RiskHold("Invalid sector-aware funded sell-only input")
    nav=cash+sum(positions.values())
    if not math.isfinite(nav) or nav<=0:
        raise RiskHold("Invalid sell-only pretrade NAV")
    by_sector={}
    for s in positions:
        by_sector.setdefault(cohort.SECTORS[s],[]).append(s)
    gross=sum(positions.values())
    gross_floor=max(0.,(gross-.95*nav)/(1.-.95*fee))
    sold=gross_floor
    for _ in range(100):
        post=nav-fee*sold
        if post<=0 or sold>gross+1e-8:
            raise RiskHold("Sector repair would overdraw NAV")
        mandatory={s:max(0.,v-.50*post) for s,v in positions.items()}
        sector_floor=sum(
            max(sum(mandatory[s] for s in names),
                max(0.,sum(positions[s] for s in names)-MAX_SECTOR*post))
            for names in by_sector.values())
        updated=max(gross_floor,sector_floor)
        if abs(updated-sold)<1e-11:
            sold=updated
            break
        sold=updated
    else:
        raise RiskHold("Sector-aware minimum sale did not converge")
    post=nav-fee*sold
    wanted={s:min(v,.50*post) for s,v in positions.items()}
    for names in by_sector.values():
        excess=max(0.,sum(wanted[s] for s in names)-MAX_SECTOR*post)
        for s in sorted(names,key=lambda s:(-wanted[s],s)):
            part=min(excess,wanted[s])
            wanted[s]-=part
            excess-=part
            if excess<=1e-12:
                break
        if excess>1e-8:
            raise RiskHold("Unfunded sector cap correction")
    remainder=sold-sum(positions[s]-wanted[s] for s in positions)
    if remainder < -1e-8:
        raise RiskHold("Minimum sale underestimates mandatory sector sales")
    for s in sorted(wanted,key=lambda s:(-wanted[s],s)):
        part=min(max(0.,remainder),wanted[s])
        wanted[s]-=part
        remainder-=part
        if remainder<=1e-12:
            break
    actual=sum(positions[s]-wanted[s] for s in positions)
    charged=fee*actual
    newcash=cash+actual-charged
    newnav=newcash+sum(wanted.values())
    if (remainder>1e-8 or abs(actual-sold)>1e-8
        or abs(newnav-(nav-charged))>1e-8
        or any(v< -1e-10 or v>positions[s]+1e-10 for s,v in wanted.items())
        or sum(wanted.values())/newnav>.95+1e-9
        or newcash/newnav<.05-1e-9
        or max(wanted.values())/newnav>.50+1e-9
        or any(sum(wanted[s] for s in names)/newnav>MAX_SECTOR+1e-9
               for names in by_sector.values())):
        raise RiskHold("Sector-aware repair violates post-fee policy proof")
    return wanted,newcash,charged,actual


def _next_close_sector_repair_path(returns:pd.DataFrame,weights:dict[str,float],
                                    fee_bps:int,initial_invested:float):
    """Buy once; detect at close t and repair at close t+1, no lookahead.

    The original basket was selected using these same historical prices:
    this is risk economics, not a tradeable backtest or alpha evidence.
    """
    if (initial_invested not in (.90,.95) or fee_bps not in COSTS_BPS
        or type(weights) is not dict or len(weights)!=8
        or not math.isclose(sum(weights.values()),1.,abs_tol=1e-12)
        or any(s not in cohort.SECTORS for s in weights)
        or any(type(w) not in (int,float) or not math.isfinite(w)
               or w<0 or w>1 for w in weights.values())
        or not isinstance(returns,pd.DataFrame) or len(returns)<2
        or not set(weights)<=set(returns.columns)):
        raise RiskHold("Invalid registered next-close repair study")
    panel=returns[list(weights)]
    if (panel.isna().any().any() or not np.isfinite(panel.to_numpy()).all()
        or (panel<=-1).any().any()):
        raise RiskHold("Invalid original close return in next-close repair")
    fee=fee_bps/10000.
    entry_nav=100./(1.+initial_invested*fee)
    cash=(1.-initial_invested)*entry_nav
    positions={s:initial_invested*entry_nav*w for s,w in weights.items()}
    path=[100.,entry_nav]
    daily=[]
    repairs=0
    repair_turnover=0.
    repair_fees=0.
    queued=False
    before={"gross":0,"sector":0,"single":0}
    after={"gross":0,"sector":0,"single":0}

    def flags():
        nav=cash+sum(positions.values())
        sectors={}
        for s,v in positions.items():
            k=cohort.SECTORS[s]
            sectors[k]=sectors.get(k,0.)+v
        return {
            "gross":sum(positions.values())/nav>.95+1e-10,
            "sector":max(sectors.values())/nav>MAX_SECTOR+1e-10,
            "single":max(positions.values())/nav>.50+1e-10,
        }

    for _,row in panel.iterrows():
        for s in positions:
            positions[s]*=1.+float(row[s])
        prior=flags()
        for k,v in prior.items():
            before[k]+=int(v)
        if queued:
            positions,cash,charged,sold=_sector_aware_sell_only_repair(
                positions,cash,fee)
            if sold>1e-10:
                repairs+=1
                repair_turnover+=sold
                repair_fees+=charged
        current=flags()
        for k,v in current.items():
            after[k]+=int(v)
        queued=any(current.values())
        nav=cash+sum(positions.values())
        daily.append(nav/path[-1]-1.)
        path.append(nav)
    arr=np.asarray(path,dtype=float)
    drawdown=arr/np.maximum.accumulate(arr)-1.
    return {
        "initial_invested_fraction":initial_invested,
        "initial_cash_fraction":1.-initial_invested,
        "fee_bps_per_traded_side":fee_bps,
        "marked_unrealized_return_after_all_costs_pct":_round(path[-1]-100.),
        "annualized_close_to_close_volatility":_round(
            np.std(daily,ddof=1)*math.sqrt(SESSIONS_PER_YEAR)),
        "max_observed_compounded_close_drawdown":_round(drawdown.min()),
        "worst_observed_daily_return":_round(min(daily)),
        "gross_breach_close_count_before_repair":before["gross"],
        "sector_breach_close_count_before_repair":before["sector"],
        "single_breach_close_count_before_repair":before["single"],
        "gross_breach_close_count_after_repair":after["gross"],
        "sector_breach_close_count_after_repair":after["sector"],
        "single_breach_close_count_after_repair":after["single"],
        "additional_sell_only_repair_dates":repairs,
        "additional_sell_only_turnover_usd_per_100":_round(repair_turnover),
        "total_entry_and_repair_fees_usd_per_100":_round(
            100.-entry_nav+repair_fees),
        "last_close_queued_repair_not_executed":queued,
        "terminal_exit_fee_not_charged":True,
        "next_completed_close_only_no_intraday_guarantee":True,
        "selected_on_same_historical_prices_not_alpha":True,
        "research_only_no_live_execution":True,
    }


def _one_window(ret:pd.DataFrame, names:list[str]) -> dict:
    if (type(names) is not list or len(names)!=8
        or len(set(names))!=8 or not set(names)<=set(cohort.SECTORS)
        or not isinstance(ret,pd.DataFrame) or len(ret) not in WINDOWS
        or ret.isna().any().any() or (ret<=-1).any().any()
        or not np.isfinite(ret.to_numpy()).all()):
        raise RiskHold("Missing finite frozen trailing window")
    selected={s:1./8 for s in names}
    sector=frozen._sector_neutral(names)
    refs={
        "frozen_q2_eight_equal":selected,
        "same_sector_original_24_cohort":sector,
        "passive_95_spy_5_cash":{"SPY":1.},
    }
    stats={key:_path_metrics(ret,w) for key,w in refs.items()}
    # Unlike the daily fixed-weight covariance proxy, these paths purchase
    # once and let exposures drift; costs are funded by initial capital.
    buy_once={
        key:{str(bp):_buy_once_costed_risk(ret,w,bp) for bp in COSTS_BPS}
        for key,w in refs.items()
    }
    q2ret=INVESTED*ret[names].mean(axis=1)
    spyret=INVESTED*ret["SPY"]
    selected_std=q2ret.std(ddof=1)
    market_std=spyret.std(ddof=1)
    if selected_std>0 and market_std>0:
        beta=float(q2ret.cov(spyret)/spyret.var(ddof=1))
        correlation=float(q2ret.corr(spyret))
    else:
        beta=correlation=None
    matrix=ret[names].corr().to_numpy(dtype=float)
    if not np.isfinite(matrix).all():
        effective=None
        max_pair=None
    else:
        eigen=np.maximum(np.linalg.eigvalsh(matrix),0.)
        effective=float((eigen.sum()**2)/(eigen**2).sum()) if (eigen**2).sum()>0 else None
        max_pair=float(matrix[np.triu_indices(len(names),k=1)].max())
    count=max(1,int(math.ceil(len(ret)*.05)))
    spy_tail_indices=np.argsort(spyret.to_numpy(),kind="stable")[:count]
    spy_tail=float(spyret.iloc[spy_tail_indices].mean())
    selected_tail=float(q2ret.iloc[spy_tail_indices].mean())
    return {
        "price_return_window_sessions":len(ret),
        "from_completed_price_session":ret.index[0].date().isoformat(),
        "through_frozen_completed_price_session":ret.index[-1].date().isoformat(),
        "fixed_95pct_risky_5pct_cash_reference_risk":stats,
        "buy_once_costed_no_rebalance_close_risk":buy_once,
        "next_close_sector_repair_cash_buffer_comparison":{
            label:{str(bp):_next_close_sector_repair_path(
                ret,selected,bp,invested) for bp in COSTS_BPS}
            for label,invested in (
                ("95pct_initial_invested",.95),
                ("90pct_initial_invested",.90),
            )
        },
        "q2_eight_spy_beta":_round(beta) if beta is not None else None,
        "q2_eight_spy_correlation":_round(correlation) if correlation is not None else None,
        "issuer_pair_max_correlation":_round(max_pair) if max_pair is not None else None,
        "effective_issuer_correlation_dimensions":_round(effective) if effective is not None else None,
        "spy_worst_5pct_session_count":count,
        "q2_mean_on_same_worst_spy_sessions":_round(selected_tail),
        "spy_mean_on_worst_sessions":_round(spy_tail),
        "q2_to_spy_worst_session_loss_ratio":
            _round(selected_tail/spy_tail) if spy_tail<-1e-12 else None,
        "historical_flags_not_forward_guarantees":{
            "q2_volatility_above_existing_high_35pct":
                stats["frozen_q2_eight_equal"]["annualized_close_to_close_volatility"]>MAX_VOL,
            "q2_observed_any_daily_loss_6pct_or_worse":
                stats["frozen_q2_eight_equal"]["daily_return_below_negative_6pct_count"]>0,
            "q2_observed_historical_drawdown_20pct_or_worse":
                stats["frozen_q2_eight_equal"]["historical_drawdown_exceeded_20pct"],
        },
        "risk_metrics_selection_conditioned_on_same_window":True,
    }


def analyze(original_root:Path,*,pin_path:Path=frozen.FIRST_SOURCE_INDEPENDENT_PIN)->dict:
    """Independent source SHA pin check happens before ANY risk read/marks."""
    proof=frozen.verify_independent_first_source_pin(original_root,pin_path)
    report,screen,raw,captured=frozen._read_source(original_root)
    if (report.get("source_acquired_utc")!=captured
        or screen.get("selection_candidate") is None
        or screen.get("live_order_authorized") is not False):
        raise RiskHold("No first original Q2 nontradeable basket")
    names=screen["selection_candidate"]["symbols"]
    try:
        panel=pd.read_csv(io.BytesIO(raw),index_col="Date",parse_dates=["Date"])
        prices=cohort.validate_prices(panel)
        cohort.p4g.verify_original_nyse_source_sessions(prices.index)
    except Exception as exc:
        raise RiskHold("Unable to verify original 24 issuer preentry market source") from exc
    if (cohort.canonical_csv(prices).encode("utf-8")!=raw
        or len(prices)<max(WINDOWS)+1
        or prices.index[-1].date().isoformat()!=
            report["last_completed_market_session"]):
        raise RiskHold("Changed original market source or too short risk lookback")
    sectors={}
    for name in names:
        s=cohort.SECTORS[name]
        sectors[s]=sectors.get(s,0)+1
    if (len(sectors)<4 or max(sectors.values())>2
        or screen["selection_candidate"]["sector_count"]!=len(sectors)):
        raise RiskHold("Frozen issuer sector diversification corrupted")
    ret=prices.pct_change(fill_method=None)
    windows={}
    for n in WINDOWS:
        returns=ret.iloc[-n:]
        windows[str(n)]=_one_window(returns,names)
    return {
        "schema":SCHEMA,
        "status":"FIRST_ORIGINAL_SELECTION_PREENTRY_TRAILING_RISK_RESEARCH_ONLY",
        "source_acquired_utc":captured,
        "last_original_completed_market_session":
            report["last_completed_market_session"],
        "first_original_sec_price_source_pin_confirmed":proof,
        "first_original_price_csv_sha256":sha256(raw).hexdigest(),
        "original_selected_8_names":names,
        "original_24_issuer_source_coverage":
            screen["matched_positive_annual_net_income_assets"],
        "name_original_share_of_total_NAV":".11875",
        "cash_fraction":".05",
        "maximum_sector_share_of_total_NAV":
            _round(max(sectors.values())*INVESTED/len(names)),
        "original_sector_weight_of_total_NAV":{
            k:_round(v*INVESTED/len(names)) for k,v in sorted(sectors.items())},
        "trailing_completed_source_windows":windows,
        "lookback_selection_conditioned_not_independent_or_prospective_alpha":True,
        "no_real_execution_fill_or_rolling_intraday_stop_proven":True,
        "buy_once_costed_risk_is_selection_conditioned_not_a_live_gate":True,
        "not_a_live_risk_gate_or_promotion_decision":True,
        "no_broker_orders_or_account_mutations":True,
        "live_authorized":False,"broker_gets":0,"broker_posts":0,"broker_orders":0,
    }


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--original-dir",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    result=analyze(args.original_dir)
    if args.output.exists():
        raise RiskHold("Never overwrite first original risk observation")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("V8-Q2 source-pinned preentry risk, windows",
          ",".join(result["trailing_completed_source_windows"]),
          "original selection frozen, 0 broker requests")


if __name__=="__main__":
    main()
