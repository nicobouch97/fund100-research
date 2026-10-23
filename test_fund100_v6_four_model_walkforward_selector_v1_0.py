"""Offline causal switching tests; artificial NAV paths are NOT alpha evidence."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

import fund100_v6_four_model_walkforward_selector_v1_0 as w
import fund100_v6_existing_four_model_economics_v1_0 as economics
import fund100_v6_aggressive_rotation_research_v1_0 as original


def paths(n=1000):
    dates = pd.bdate_range("2012-01-02", periods=n)
    t = np.arange(n)
    benchmark = 100 * (1.00025 ** t)
    out = {}
    for i, model in enumerate(w.MODELS):
        daily = .0002 + (.0006 if i == 0 else -.0001 * i)
        nav = 100 * (1 + daily) ** t
        out[model] = pd.DataFrame({"nav": nav, "benchmark": benchmark}, index=dates)
    return out


def test_causal_quarterly_selection_and_no_same_close_hindsight():
    baseline = paths()
    a = w.evaluate(baseline, switch_side_cost_bps=15)
    assert a["training_ends_at_previous_session_close"]
    assert a["new_model_first_earns_next_session_return"]
    assert a["comparison_windows"]["since_2014"]["sessions"] >= 260
    dates = next(iter(baseline.values())).index
    t = next(i for i in range(300, len(dates))
             if dates[i].to_period("Q") != dates[i - 1].to_period("Q"))
    _, b, navs = w._verified_paths(baseline)
    before = w._lagged_choice(b, navs, t)
    modified = paths()
    # A giant move at decision day's close is not yet available to rank.
    modified[w.MODELS[1]].iloc[t, 0] *= 10
    _, b2, navs2 = w._verified_paths(modified)
    assert w._lagged_choice(b2, navs2, t) == before


def test_switch_costs_are_charged_for_entry_and_not_on_no_change():
    p = paths()
    a = w.evaluate(p, switch_side_cost_bps=5)
    b = w.evaluate(p, switch_side_cost_bps=35)
    assert a["comparison_windows"]["since_2014"]["switches"] >= 1
    assert a["comparison_windows"]["since_2014"]["historical_selector_cagr_pct"] > b["comparison_windows"]["since_2014"]["historical_selector_cagr_pct"]
    assert a["comparison_windows"]["since_2014"]["model_switch_one_way_notional_NAV"] == b["comparison_windows"]["since_2014"]["model_switch_one_way_notional_NAV"]


def test_cash_when_no_model_beats_benchmark():
    p = paths()
    for frame in p.values():
        frame["nav"] = 100 * (1.0001 ** np.arange(len(frame)))
    result = w.evaluate(p, switch_side_cost_bps=15)
    assert result["comparison_windows"]["since_2014"]["switches"] == 0
    assert result["comparison_windows"]["since_2014"]["historical_selector_cagr_pct"] == 0.0
    assert result["comparison_windows"]["since_2014"]["cash_held_sessions"] == result["comparison_windows"]["since_2014"]["sessions"]


def test_bad_history_or_cost_refused():
    p = paths()
    for invalid in (0, 12, True, 100):
        with pytest.raises(w.WalkforwardStop, match="cost"):
            w.evaluate(p, switch_side_cost_bps=invalid)
    q = paths()
    q[w.MODELS[1]].iloc[-1, 1] *= 2
    with pytest.raises(w.WalkforwardStop, match="benchmark"):
        w.evaluate(q, switch_side_cost_bps=15)
    q = paths()
    q[w.MODELS[0]].iloc[10, 0] = np.nan
    with pytest.raises(w.WalkforwardStop, match="NAV"):
        w.evaluate(q, switch_side_cost_bps=15)
    q = paths()
    q[w.MODELS[0]] = q[w.MODELS[0]].iloc[:-1]
    with pytest.raises(w.WalkforwardStop, match="sessions"):
        w.evaluate(q, switch_side_cost_bps=15)


def test_real_frozen_four_model_source_still_not_live_or_independent_holdout():
    prices, sha = original.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    original_models = economics._all_paths(prices, 15)
    report = w.evaluate(original_models, switch_side_cost_bps=15)
    assert report["historical_universe_and_models_already_inspected"]
    assert not report["independent_out_of_sample_alpha_proven"]
    assert report["strategy_promoted_for_funded_trading"] is None
    assert report["paper_or_live_orders"] == 0
    assert report["comparison_windows"].keys() == w.START_WINDOWS.keys()
    assert sha == original.FROZEN_FILE_SHA256
    assert all(v["sessions"] >= 260 for v in report["comparison_windows"].values())
