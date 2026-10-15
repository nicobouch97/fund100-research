"""Fund-100 V6-R1: aggressive relative momentum candidate; strictly RESEARCH ONLY.

The user has NOT authorised liquidation, strategy migration, new LIVE positions
or a new portfolio risk profile. This module is isolated from Alpaca.
Backtests run against the existing immutable v2 research price snapshot;
that past interval was examined repeatedly and is EXPLORATORY, not a
new independent holdout or an achievable return projection.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

SCHEMA = "FUND100_V6_R1_AGGRESSIVE_ROTATION_RESEARCH_V1"
UNIVERSE = (
    "SPY", "IWM", "EFA", "EEM", "VNQ",
    "XLK", "XLF", "XLI", "XLV", "XLP", "XLY", "XLE", "XLU",
)
BENCH = "ACWI_BENCHMARK"
FROZEN_FILE_SHA256 = "acc2c8c08953b895ca5062b3cfba287efb97143b10e108e8ce4bd8b82ffb0d28"
PREREGISTERED_HORIZONS = (63, 126)
FIRST_POSSIBLE_T = 201
MAX_NAMES = 3
FULL_WEIGHTS = (.35, .35, .30)
RISK_OFF_SCALE = .35
TRADE_BAND = .05
COSTS_BPS = (5, 15, 35)
START_NAV = 100.0
MIN_HISTORY = 840


class V6ResearchStop(ValueError):
    pass


@dataclass(frozen=True)
class Allocation:
    decision_date: str
    risk_on: bool
    weights: dict[str, float]
    signal_scores: dict[str, float]


def validate_prices(raw: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(raw, pd.DataFrame) or set(raw.columns) != set(UNIVERSE) | {BENCH}:
        raise V6ResearchStop("Missing or unexpected frozen symbol/benchmark.")
    idx = raw.index
    if (not isinstance(idx, pd.DatetimeIndex) or idx.tz is not None
        or not idx.is_monotonic_increasing or idx.has_duplicates
        or any(x != x.normalize() for x in idx)
        or len(idx) < MIN_HISTORY):
        raise V6ResearchStop("Invalid dated market history or insufficient sessions.")
    result = raw.loc[:, list(UNIVERSE)+[BENCH]].copy()
    if any(not pd.api.types.is_numeric_dtype(result[x]) for x in result):
        raise V6ResearchStop("Non-numeric market history.")
    values = result.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise V6ResearchStop("Invalid or missing adjusted history.")
    if (result.pct_change().iloc[1:].abs().to_numpy(dtype=float) > .45).any():
        raise V6ResearchStop("Unverified split/market data discontinuity.")
    return result


def signal(raw: pd.DataFrame, t: int) -> Allocation:
    """Friday end-of-session target from bars ENDING THE PRIOR SESSION."""
    data = validate_prices(raw)
    if type(t) is not int or not FIRST_POSSIBLE_T <= t < len(data):
        raise V6ResearchStop("Attempt to compute signal without 200 prior sessions.")
    if data.index[t].weekday() != 4:
        raise V6ResearchStop("Signals only on genuine Friday trading sessions.")
    old = data.iloc[:t]  # excludes decision day's prices: no same-close lookahead
    spy = old["SPY"]
    risk_on = float(spy.iloc[-1]) > float(spy.iloc[-200:].mean())
    spy63 = float(spy.iloc[-1] / spy.iloc[-64] - 1)
    spy126 = float(spy.iloc[-1] / spy.iloc[-127] - 1)
    qualified = []
    for s in UNIVERSE:
        x = old[s]
        ret63 = float(x.iloc[-1] / x.iloc[-64] - 1)
        ret126 = float(x.iloc[-1] / x.iloc[-127] - 1)
        score = .6 * (ret63-spy63) + .4 * (ret126-spy126)
        eligible = (
            float(x.iloc[-1]) > float(x.iloc[-150:].mean())
            and ret126 > 0
            and ret63 > spy63
            and score > 0
        )
        if eligible:
            qualified.append((s, score))
    qualified.sort(key=lambda p: (-p[1], p[0]))
    winners = qualified[:MAX_NAMES]
    targets = {s: 0.0 for s in UNIVERSE}
    for i,(s,_) in enumerate(winners):
        targets[s] = FULL_WEIGHTS[i] * (1.0 if risk_on else RISK_OFF_SCALE)
    # Cash is the residual; cannot add leverage or short a product.
    gross = sum(targets.values())
    if any(not 0 <= x <= .35 for x in targets.values()) or gross > 1 + 1e-12:
        raise V6ResearchStop("Improperly concentrated or leveraged V6 target.")
    return Allocation(
        str(data.index[t].date()),
        risk_on,
        targets,
        {s: round(score, 8) for s,score in winners},
    )


def backtest(raw: pd.DataFrame, *, cost_bps: int) -> pd.DataFrame:
    data = validate_prices(raw)
    if cost_bps not in COSTS_BPS:
        raise V6ResearchStop("Unsupported one-way transaction cost.")
    active = {s: 0.0 for s in UNIVERSE}
    nav = START_NAV
    benchmark_nav = START_NAV
    rows = []
    change = data.pct_change().fillna(0.0)
    for t,(when,daily) in enumerate(change.iterrows()):
        # Earn today with yesterday's holdings; trade ONLY after the close.
        ret = sum(active[s]*float(daily[s]) for s in UNIVERSE)
        if ret <= -1:
            raise V6ResearchStop("Impossible depleted portfolio.")
        nav *= (1+ret)
        benchmark_nav *= 1+float(daily[BENCH])
        active = {s: active[s]*(1+float(daily[s]))/(1+ret) for s in UNIVERSE}
        turnover = 0.0
        signaled = False
        risk_on = None
        if t >= FIRST_POSSIBLE_T and when.weekday() == 4:
            choice = signal(data,t)
            risk_on=choice.risk_on
            diffs = [abs(choice.weights[s]-active[s]) for s in UNIVERSE]
            # If target differs meaningfully in any slot, execute all legs.
            if max(diffs) >= TRADE_BAND:
                turnover = sum(diffs)
                nav *= 1 - turnover * cost_bps/10000
                active = choice.weights
            signaled = True
        gross = sum(active.values())
        if not (0 <= gross <= 1.0000000001) or nav <= 0 or not math.isfinite(nav):
            raise V6ResearchStop("Invalid long-only research NAV.")
        rows.append({
            "date": when,
            "v6_nav": nav,
            "acwi_nav": benchmark_nav,
            "one_way_turnover": turnover,
            "gross_equity_exposure": gross,
            "cash_weight": max(0.0,1-gross),
            "signal_day": signaled,
            "risk_on_at_decision": risk_on,
            "held_names": ",".join(sorted(s for s,x in active.items() if x > 1e-6)),
        })
    result=pd.DataFrame(rows).set_index("date")
    return result


def metrics(path: pd.DataFrame, start_date: str) -> dict:
    cut = path.loc[start_date:].copy()
    if len(cut) < 100:
        raise V6ResearchStop("Insufficient comparison window.")
    nav, ref = cut["v6_nav"], cut["acwi_nav"]
    ret = nav.pct_change().dropna()
    years = (cut.index[-1]-cut.index[0]).days / 365.25
    strategy_cagr = float((nav.iloc[-1]/nav.iloc[0])**(1/years)-1)
    benchmark_cagr = float((ref.iloc[-1]/ref.iloc[0])**(1/years)-1)
    ddown = (nav/nav.cummax()-1).min()
    n_ref = (ref/ref.cummax()-1).min()
    returns = cut["v6_nav"].pct_change().dropna()
    bref = cut["acwi_nav"].pct_change().dropna()
    equity_corr = returns.corr(bref) if returns.std() > 0 and bref.std() > 0 else None
    worst = float(ret.min()) if len(ret) else None
    return {
        "first_session": str(cut.index[0].date()),
        "last_session": str(cut.index[-1].date()),
        "sessions": len(cut),
        "v6_cagr": round(strategy_cagr, 6),
        "acwi_cagr": round(benchmark_cagr, 6),
        "v6_less_acwi_cagr_percentage_points": round(100*(strategy_cagr-benchmark_cagr), 4),
        "v6_max_drawdown_pct": round(float(ddown)*100,4),
        "acwi_max_drawdown_pct": round(float(n_ref)*100,4),
        "v6_annual_volatility": round(float(ret.std(ddof=1)*np.sqrt(252)),6),
        "v6_worst_day_return_pct": None if worst is None else round(100*worst,4),
        "annualized_gross_turnover": round(float(cut["one_way_turnover"].iloc[1:].sum()/years),5),
        "days_with_signals": int(cut["signal_day"].sum()),
        "days_with_realigned_positions": int((cut["one_way_turnover"]>0).sum()),
        "mean_equity_exposure": round(float(cut["gross_equity_exposure"].mean()),5),
        "v6_correlation_to_acwi": None if equity_corr is None else round(float(equity_corr),5),
    }


def analyze(prices: pd.DataFrame, source_sha256: str) -> dict:
    data = validate_prices(prices)
    if not isinstance(source_sha256,str) or len(source_sha256)!=64:
        raise V6ResearchStop("Original research source hash missing.")
    return {
        "schema": SCHEMA,
        "status": "EXPLORATORY_ALREADY_EXAMINED_HISTORY_NOT_LIVE_APPROVED",
        "source_frozen_v2_file_sha256": source_sha256,
        "source_data_first":str(data.index[0].date()),
        "source_data_last":str(data.index[-1].date()),
        "signal_horizons_sessions":list(PREREGISTERED_HORIZONS),
        "weekly_friday_decision_uses_prior_session_only":True,
        "top_three_concentration":list(FULL_WEIGHTS),
        "risk_off_max_gross":RISK_OFF_SCALE,
        "risk_profile_rewrite_required_before_any_live_use":True,
        "historical_period_was_previously_studied":True,
        "independent_fresh_holdout_available":False,
        "actual_forward_strategy_returns":0,
        "commissions_and_spread_not_independently_verified":True,
        "results_by_one_way_cost_bps": {
            str(cost): {
                "full_exploratory":metrics(backtest(data,cost_bps=cost), "2014-01-01"),
                "recent_exploratory":metrics(backtest(data,cost_bps=cost), "2020-01-01"),
            }
            for cost in COSTS_BPS
        },
        "operator_authorised_liquidation":False,
        "operator_authorised_v6_live":False,
        "paper_authorized":False,
        "live_authorized":False,
        "trading_authorized":False,
        "broker_orders":0,
    }


def load_frozen(path: Path) -> tuple[pd.DataFrame,str]:
    source = path.read_bytes()
    digest = hashlib.sha256(source).hexdigest()
    if digest != FROZEN_FILE_SHA256:
        raise V6ResearchStop("Research v2 frozen file bytes changed or source is wrong.")
    original = pd.read_csv(path,parse_dates=["date"]).set_index("date")
    return validate_prices(original),digest


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--frozen-prices-csv",default="research_lab/frozen_history_v2.csv")
    p.add_argument("--output-json",required=True)
    a=p.parse_args()
    data,digest=load_frozen(Path(a.frozen_prices_csv))
    result=analyze(data,digest)
    out=Path(a.output_json)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("V6-R1 historical review (exploratory, not independent holdout)")
    for cost,item in result["results_by_one_way_cost_bps"].items():
        m=item["full_exploratory"]
        print(cost,"bps: V6 less ACWI CAGR percentage points",m["v6_less_acwi_cagr_percentage_points"],
              "max drawdown",m["v6_max_drawdown_pct"],
              "annual turnover",m["annualized_gross_turnover"])
    print("No LIVE/PAPER permission, new orders or liquidation.")


if __name__=="__main__":
    main()
