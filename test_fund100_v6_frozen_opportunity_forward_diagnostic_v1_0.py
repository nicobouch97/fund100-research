"""Non-overlapping realized ETF forecasts, no retrospective alpha promotion."""
from pathlib import Path
import numpy as np
import pytest

import fund100_v6_frozen_opportunity_forward_diagnostic_v1_0 as study
import fund100_v6_frozen_signal_to_opportunity_v1_0 as signals
from test_fund100_v6_frozen_signal_to_opportunity_v1_0 import fake_prices


def run(f=None,begin=None):
    return study.evaluate(
        history=fake_prices() if f is None else f,
        source_sha256=study.SOURCE_SHA256,
        start_index=begin)

def test_disjoint_forward_windows_and_clear_calibration_limitation():
    result=run()
    rows=result["nonoverlapping_episodes"]
    assert result["schema"]==study.SCHEMA
    assert len(rows)>=20
    assert result["overall"]["evaluated_decision_windows"]==len(rows)
    assert result["immutable_source_file_verified_by_this_function"] is False
    assert result["source_frozen_price_history_previously_studied"] is True
    assert result["independent_future_holdout_validated"] is False
    assert result["forecast_model_not_calibrated"] is True
    assert result["retrospective_results_do_not_authorize_live_trading"] is True
    assert result["broker_orders"]==0
    assert result["operator_release_changed"] is False
    assert result["horizon_sessions"]==21
    assert result["hypothetical_portfolio"]==(
        "EACH_NONOVERLAPPING_EPISODE_STARTS_ACWI_50_CASH_50_USD_100")
    assert all(row["decision_session"]<row["outcome_last_session"] for row in rows)
    assert all(a["outcome_last_session"]<=b["decision_session"]
               for a,b in zip(rows,rows[1:]))
    assert result["first_evaluated_decision"]==rows[0]["decision_session"]
    assert result["last_forward_outcome_session"]==rows[-1]["outcome_last_session"]
    assert sum(result["calendar_windows"][s]["evaluated_decision_windows"]
               for s in study.SCENARIOS)==len(rows)
    assert len(rows[0]["forecast_errors_bps"])==len(signals.UNIVERSE)
    assert len(rows[0]["zero_return_baseline_errors_bps"])==len(signals.UNIVERSE)
    assert result["overall"]["all_windows_mean_absolute_forecast_error_bps"] is not None
    assert result["overall"]["all_windows_zero_return_naive_mae_bps"] is not None
    assert "all_candidate_windows_mean_excess_vs_95pct_acwi_after_cost_bps" in result["overall"]
    assert "hurdle_pass_mean_excess_vs_95pct_acwi_after_cost_bps" in result["overall"]
    assert result["overall"]["hypothetical_trade_candidate_windows"]==sum(
        row["proposed_switch_has_trade"] for row in rows)
    assert result["overall"]["forecast_mae_improvement_vs_zero_naive_bps"]==pytest.approx(
        round(result["overall"]["all_windows_zero_return_naive_mae_bps"]
              -result["overall"]["all_windows_mean_absolute_forecast_error_bps"],4))
    assert result["retrospective_disposition_never_promotes_or_unlocks_live"] is True
    assert all(row["selection_excess_vs_95pct_acwi_after_cost_bps"] is not None
               for row in rows if row["proposed_switch_has_trade"])

def test_frozen_original_file_is_actually_hash_verified_not_caller_asserted():
    result=study.evaluate_original()
    assert result["immutable_source_file_verified_by_this_function"] is True
    assert result["source_sha256_caller_asserted"]==study.SOURCE_SHA256
    assert result["overall"]["evaluated_decision_windows"]>=50
    assert result["overall"]["hurdle_pass_total_realized_edge_after_two_side_cost_bps"] is None or isinstance(
        result["overall"]["hurdle_pass_total_realized_edge_after_two_side_cost_bps"],float)
    assert result["broker_orders"]==0
    assert result["source_frozen_price_history_previously_studied"] is True
    assert result["overall"]["evaluated_decision_windows"]==151
    assert result["overall"]["hypothetical_hurdle_pass_windows"]==0
    assert result["retrospective_evidence_disposition"]==(
        "REJECT_NO_SWITCH_CLEARED_COST_AND_UNCERTAINTY_HURDLE")
    assert result["overall"]["all_candidate_windows_mean_excess_vs_95pct_acwi_after_cost_bps"]<0

def test_signal_uses_past_bars_outcome_uses_next_tradable_close():
    f=fake_prices()
    a=run(f=f)
    f2=f.copy()
    # Change a future price. Historical events whose outcomes already ended
    # before that session must retain the exact same outcomes and decisions.
    future=680
    f2.iloc[future:,f2.columns.get_loc("XLK")]*=1.01
    b=run(f=f2)
    cutoff=f.index[future].date().isoformat()
    untouched_a=[x for x in a["nonoverlapping_episodes"]
                 if x["outcome_last_session"]<cutoff]
    untouched_b=[x for x in b["nonoverlapping_episodes"]
                 if x["outcome_last_session"]<cutoff]
    assert len(untouched_a)>=10
    assert untouched_a==untouched_b

def test_calibration_counts_profitable_and_unprofitable_events_without_promoting():
    z=run()
    rows=z["nonoverlapping_episodes"]
    for cohort in study.SCENARIOS:
        panel=[x for x in rows if x["cohort"]==cohort]
        summary=z["calendar_windows"][cohort]
        assert summary["evaluated_decision_windows"]==len(panel)
        assert summary["hypothetical_hurdle_pass_windows"]==sum(
            row["hypothetical_hurdle_pass"] for row in panel)
        assert summary["actual_forward_returns_are_out_of_sample"] is False
    good=sum(x["realized_edge_after_two_side_cost_bps"]>0
             for x in rows if x["hypothetical_hurdle_pass"])
    eligible=z["overall"]["hypothetical_hurdle_pass_windows"]
    if eligible:
        assert z["overall"]["hurdle_pass_win_rate_pct"]==pytest.approx(
            round(100*good/eligible,4))
    else:
        assert z["overall"]["hurdle_pass_win_rate_pct"] is None
    assert z["retrospective_results_do_not_authorize_live_trading"]

@pytest.mark.parametrize("begin",[-1,0,1,252,253,True,"400",900])
def test_bad_decision_range_rejected(begin):
    with pytest.raises(study.CalibrationStop,match="Invalid causal study"):
        run(begin=begin)

def test_false_sha_or_tampered_historical_file_cannot_claim_verified_evidence(tmp_path):
    with pytest.raises(study.CalibrationStop,match="SHA256"):
        study.evaluate(history=fake_prices(),source_sha256="f"*64)
    altered=tmp_path/"tampered.csv"
    fake_prices().to_csv(altered,index_label="date")
    with pytest.raises(study.CalibrationStop,match="verification failed"):
        study.evaluate_original(file=altered)

def test_weak_all_negative_trends_are_hold_not_fabricated_switch():
    f=fake_prices()
    k=np.arange(len(f),dtype=float)
    for col in f:
        f[col]=100*(1-.0002)**k
    z=run(f=f)
    assert z["overall"]["hypothetical_hurdle_pass_windows"]==0
    assert all(not row["proposed_switch_has_trade"] for row in z["nonoverlapping_episodes"])
    assert all(row["realized_edge_after_two_side_cost_bps"]==0
               for row in z["nonoverlapping_episodes"])

def test_diagnostic_never_changes_execution_path_or_original_acwi_first_fence():
    src=Path(study.__file__).read_text()
    assert study.LIVE_TRADING_RELEASED is False
    assert study.REAL_ORDERS_SUBMITTED==0
    for banned in ("import requests","import urllib","import socket",
                   "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                   "FUND100_PRIVATE_STATE_READ_TOKEN",
                   "method=\"POST\"","git push","import os"):
        assert banned not in src


def test_retrospective_disposition_rejects_weak_evidence_and_never_promotes():
    base={
        "hypothetical_hurdle_pass_windows":0,
        "hurdle_pass_mean_excess_vs_95pct_acwi_after_cost_bps":None,
        "forecast_mae_improvement_vs_zero_naive_bps":None,
    }
    assert study._retrospective_disposition(base).startswith("REJECT_NO_SWITCH")
    base["hypothetical_hurdle_pass_windows"]=3
    base["hurdle_pass_mean_excess_vs_95pct_acwi_after_cost_bps"]=-1.0
    assert study._retrospective_disposition(base).startswith("REJECT_NO_POSITIVE")
    base["hurdle_pass_mean_excess_vs_95pct_acwi_after_cost_bps"]=5.0
    base["forecast_mae_improvement_vs_zero_naive_bps"]=-0.1
    assert study._retrospective_disposition(base).startswith("REJECT_NO_NAIVE")
    base["forecast_mae_improvement_vs_zero_naive_bps"]=0.1
    assert study._retrospective_disposition(base)==(
        "UNPROVEN_HISTORICAL_SCREEN_ONLY_REQUIRES_INDEPENDENT_VALIDATION")
