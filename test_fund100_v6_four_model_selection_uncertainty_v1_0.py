"""Selection correction on four original historical costed NAV paths."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fund100_v6_four_model_selection_uncertainty_v1_0 as s
import fund100_v6_existing_four_model_economics_v1_0 as e
import fund100_v6_aggressive_rotation_research_v1_0 as r1


def identical_paths(n=400):
    index=pd.bdate_range("2020-01-02",periods=n)
    t=np.arange(n,dtype=float)
    ref=100*np.exp(.0002*t)
    nav=ref.copy()
    return {model:pd.DataFrame({"nav":nav,"benchmark":ref},index=index)
            for model in s.MODELS}


def test_zero_active_return_cannot_be_statistically_promoted():
    report=s.evaluate(identical_paths(),"2020-01-01",replications=199)
    assert report["historical_best_mean_active_annual_pp"]==0
    assert report["familywise_four_model_one_sided_p_for_best"]==1
    assert report["historical_best_mean_active_model"]==s.MODELS[0]
    assert report["no_independent_holdout_or_predictive_alpha_proven"]
    assert report["strategy_selected_for_live"] is None
    assert not report["live_trading_authorized"]
    assert report["funded_orders"]==0
    for model in s.MODELS:
        assert report["by_original_model"][model][
            "four_model_familywise_adjusted_one_sided_p"]==1


def test_positive_deterministic_active_return_is_not_live_release():
    paths=identical_paths()
    t=np.arange(400,dtype=float)
    paths[s.MODELS[0]]["nav"]=100*np.exp(.0007*t)
    result=s.evaluate(paths,"2020-01-01",replications=199)
    assert result["historical_best_mean_active_model"]==s.MODELS[0]
    assert result["historical_best_mean_active_annual_pp"]>0
    assert result["familywise_four_model_one_sided_p_for_best"]<=.01
    assert result["multiple_windows_costs_and_prior_selection_NOT_adjusted"]
    assert result["strategy_selected_for_live"] is None


def test_common_block_draws_and_seed_are_reproducible():
    paths=identical_paths()
    n=len(paths[s.MODELS[0]])
    x=np.arange(n,dtype=float)
    paths[s.MODELS[0]]["nav"]=100*np.exp(.0003*x+.003*np.sin(x/9))
    paths[s.MODELS[1]]["nav"]=paths[s.MODELS[0]]["nav"].copy()
    a=s.evaluate(paths,"2020-01-01",replications=199)
    b=s.evaluate(paths,"2020-01-01",replications=199)
    assert a==b
    assert a["by_original_model"][s.MODELS[0]]==a["by_original_model"][s.MODELS[1]]
    assert a["same_session_common_benchmark"]


@pytest.mark.parametrize("mutator",[
    lambda p:p.pop(s.MODELS[2]),
    lambda p:p[s.MODELS[0]].__setitem__("benchmark",
                                          p[s.MODELS[0]]["benchmark"]*1.01+
                                          np.arange(len(p[s.MODELS[0]]))),
    lambda p:p[s.MODELS[1]].__setitem__("nav",np.full(len(p[s.MODELS[1]]),float("nan"))),
    lambda p:p[s.MODELS[2]].__setitem__("nav",np.zeros(len(p[s.MODELS[2]]))),
    lambda p:p[s.MODELS[3]].drop(p[s.MODELS[3]].index[3],inplace=True),
])
def test_bad_original_model_or_benchmark_evidence_stops(mutator):
    p=identical_paths()
    mutator(p)
    with pytest.raises(s.SelectionStop):
        s.evaluate(p,"2020-01-01",replications=199)


def test_reversed_dates_and_unreviewed_bootstrap_parameters_stop():
    p=identical_paths()
    p[s.MODELS[0]]=p[s.MODELS[0]].iloc[::-1]
    with pytest.raises(s.SelectionStop):
        s.evaluate(p,"2020-01-01",replications=199)
    for kw in ({"replications":0},{"replications":2001},
               {"block_mean":1},{"block_mean":200},{"seed":True}):
        with pytest.raises(s.SelectionStop):
            s.evaluate(identical_paths(),"2020-01-01",**dict({"replications":199},**kw))


def test_original_real_frozen_models_all_costs_15bps_reuse_without_new_signals():
    prices,digest=r1.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    assert digest==r1.FROZEN_FILE_SHA256
    paths=e._all_paths(prices,15)
    result=s.evaluate(paths,"2020-01-01",replications=199)
    assert result["daily_return_observations"]>1000
    assert set(result["by_original_model"])==set(e.MODELS)
    assert result["method"]=="CIRCULAR_STATIONARY_BLOCK_BOOTSTRAP_SHARED_DRAWS_CENTERED_MAX_MEAN"
    assert 0<result["familywise_four_model_one_sided_p_for_best"]<=1
    assert result["four_model_adjustment_not_entire_strategy_search"]
    assert result["no_independent_holdout_or_predictive_alpha_proven"]
    assert result["strategy_selected_for_live"] is None


def test_four_model_economics_integration_keeps_all_research_only_flags():
    prices,digest=r1.load_frozen(Path("research_lab/frozen_history_v2.csv"))
    result=e.evaluate(prices,source_sha=digest)
    assert result["selection_adjustment_only_within_four_original_models"]
    assert result["selection_bootstrap_does_not_correct_prior_strategy_search"]
    assert result["strategy_promoted_for_funded_trading"] is None
    assert result["real_broker_orders"]==0
    sections=result["joint_four_model_selection_uncertainty"]
    assert set(sections)=={"5","15","35"}
    assert all(set(w)==set(e.WINDOWS) for w in sections.values())
    for cost,windows in sections.items():
        for period,report in windows.items():
            assert report["seed"]==s.SEED
            assert report["replications"]==s.REPLICATIONS
            assert report["expected_block_sessions"]==s.BLOCK_MEAN_SESSIONS
            assert set(report["by_original_model"])==set(e.MODELS)
            assert not report["live_trading_authorized"]


def test_new_module_cannot_request_funded_orders_or_modify_original_models():
    source=Path(s.__file__).read_text()
    assert s.MODELS==e.MODELS
    assert s.NO_BROKER_ACCESS and s.NO_STRATEGY_PROMOTION
    for forbidden in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                      "requests.post(","urlopen(","broker.submit_order(",
                      "def main(","/v2/orders","fund100_live_operator_control.json"):
        assert forbidden not in source
