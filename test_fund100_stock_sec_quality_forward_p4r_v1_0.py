"""P4R deterministic SYNTHETIC event-study tests; no performance claims."""
import hashlib

import numpy as np
import pandas as pd
import pytest

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_broad_sec_annual_replay_p4q_v1_0 as p4q
import fund100_stock_broad_sec_coverage_p4n_v1_0 as p4n
import fund100_stock_sec_quality_forward_p4r_v1_0 as p4r
import fund100_stock_quality_momentum_p4g_v1_0 as p4g


def annual():
    observations = []
    for ticker in sorted(set(p4l.SECTORS) - set(p4g.FROZEN_P4E_SCORES)):
        events = []
        if ticker in ("CAT", "AVGO"):
            events = [{
                "asof_conservative_available_date": "2025-02-18",
                "source_10k_available_date": "2025-02-18",
                "source_10k_accession": "0000000001-25-000001",
                "state": "SOURCE_MATCHED_LATEST_10K_DESCRIPTIVE_ONLY",
                "score": 3 if ticker == "CAT" else 0,
                "same_accession_comparative": True,
            }]
        observations.append({
            "ticker": ticker, "annual_events": events,
            "annual_filing_dates_reviewed": len(events),
            "available_score_count": len(events),
        })
    return {
        "schema": p4q.SCHEMA, "source_acquisition_utc": "2026-10-24T12:00:00Z",
        "original_p4n_manifest_sha256": "a" * 64,
        "new_issuers_verified": 16, "industrial_issuer_chronologies": 12,
        "industrial_annual_scores_available": 2,
        "industrial_annual_filing_dates_reviewed": 2,
        "original_accession_and_filed_day_used": True,
        "today_retrieved_companyfacts_not_original_historical_capture": True,
        "issuer_roster_selected_with_2026_knowledge": True,
        "historical_investable_backtest_eligible": False,
        "independent_alpha_validated": False,
        "trading_authorized": False, "paper_authorized": False,
        "live_authorized": False, "broker_orders": 0,
        "observations": observations,
    }


def prices():
    index = pd.bdate_range("2017-01-02", "2026-10-23")
    data = pd.DataFrame(100.0, index=index,
                        columns=sorted(set(p4l.SECTORS) | {"SPY", "SHY"}))
    entry = index.searchsorted(pd.Timestamp("2025-02-18"), side="right")
    for t in range(entry + 1, len(index)):
        data.iloc[t, data.columns.get_loc("CAT")] = 100 * 1.001 ** (t - entry)
        data.iloc[t, data.columns.get_loc("AVGO")] = 100 * .999 ** (t - entry)
    return data


def run(a=None, p=None, digest=None, rates=None):
    p = prices() if p is None else p
    a = annual() if a is None else a
    digest = hashlib.sha256(p4l.canonical_csv(p).encode()).hexdigest() if digest is None else digest
    return p4r.analyze(a, p, acquired_at_utc="2026-10-24T13:00:00Z",
                       source_sha256=digest, cash_rates=rates)


def test_score_groups_use_only_next_close_and_same_126_session_spy_window():
    out = run()
    assert out["completed_event_returns"] == 2
    assert out["missing_original_annual_scores"] == 0
    assert out["right_censored_eligible_scores"] == 0
    assert out["predeclared_forward_sessions"] == 126
    rows = {r["ticker"]: r for r in out["event_returns"]}
    assert rows["CAT"]["entry_next_session_close"] == "2025-02-19"
    assert rows["CAT"]["conservative_available_date"] == "2025-02-18"
    assert rows["CAT"]["exit_126_sessions_later"] == rows["AVGO"]["exit_126_sessions_later"]
    assert rows["CAT"]["stock_gross_return_pct"] > 0
    assert rows["AVGO"]["stock_gross_return_pct"] < 0
    assert out["summary"]["15"]["score_2_or_3"]["events"] == 1
    assert out["summary"]["15"]["score_0_or_1"]["events"] == 1
    assert out["summary"]["15"]["score_2_or_3"]["mean_stock_minus_spy_pp"] > 0
    assert out["summary"]["15"]["score_0_or_1"]["mean_stock_minus_spy_pp"] < 0
    assert not out["trading_authorized"] and not out["paper_authorized"]
    assert not out["live_authorized"] and out["broker_orders"] == 0
    assert out["no_point_in_time_investable_backtest"]


def test_roundtrip_costs_reduce_absolute_returns_not_invent_alpha():
    out = run()
    cat = next(x for x in out["event_returns"] if x["ticker"] == "CAT")
    assert cat["cost_scenarios"]["5"]["stock_net_return_pct"] > cat["cost_scenarios"]["15"]["stock_net_return_pct"]
    assert cat["cost_scenarios"]["15"]["stock_net_return_pct"] > cat["cost_scenarios"]["35"]["stock_net_return_pct"]
    assert out["event_returns_are_overlapping_and_not_independent"]
    assert out["retrospectively_selected_2026_survivors"]


def test_missing_scores_not_backfilled_and_right_censored_not_treated_as_losses():
    a = annual()
    cat = next(x for x in a["observations"] if x["ticker"] == "CAT")
    cat["annual_events"].append({
        "asof_conservative_available_date": "2026-09-01",
        "source_10k_available_date": "2026-09-01",
        "source_10k_accession": "0000000001-26-000001",
        "state": "SOURCE_MATCHED_LATEST_10K_DESCRIPTIVE_ONLY",
        "score": 2, "same_accession_comparative": True,
    })
    cat["annual_filing_dates_reviewed"] = 2
    cat["available_score_count"] = 2
    a["industrial_annual_filing_dates_reviewed"] = 3
    a["industrial_annual_scores_available"] = 3
    out = run(a=a)
    assert out["completed_event_returns"] == 2
    assert out["right_censored_eligible_scores"] == 1
    cat["annual_events"][0]["score"] = None
    cat["available_score_count"] = 1
    a["industrial_annual_scores_available"] = 2
    out = run(a=a)
    assert out["missing_original_annual_scores"] == 1
    assert out["completed_event_returns"] == 1


def test_reject_price_hash_tampering_and_executable_sec_replay():
    p = prices()
    digest = hashlib.sha256(p4l.canonical_csv(p).encode()).hexdigest()
    p.loc[p.index[-1], "CAT"] *= 1.01
    with pytest.raises(p4r.EventStudyStop, match="fingerprint"):
        run(p=p, digest=digest)
    a = annual()
    a["live_authorized"] = True
    with pytest.raises(p4r.EventStudyStop, match="executable"):
        run(a=a)


def test_reject_filing_day_hindsight_and_missing_original_comparative():
    a = annual()
    cat = next(x for x in a["observations"] if x["ticker"] == "CAT")
    cat["annual_events"][0]["source_10k_available_date"] = "2025-02-17"
    # A valid older accession is NOT a new filing-day signal.
    out = run(a=a)
    assert out["nonnew_or_unavailable_source_accession_events"] == 1
    assert out["completed_event_returns"] == 1
    a = annual()
    cat = next(x for x in a["observations"] if x["ticker"] == "CAT")
    cat["annual_events"][0]["same_accession_comparative"] = False
    with pytest.raises(p4r.EventStudyStop, match="quality"):
        run(a=a)


def test_reject_missing_issuer_and_corrupt_event_counts():
    a = annual()
    a["observations"].pop()
    with pytest.raises(p4r.EventStudyStop, match="roster"):
        run(a=a)
    a = annual()
    a["industrial_annual_scores_available"] = 99
    with pytest.raises(p4r.EventStudyStop, match="accounting"):
        run(a=a)


def test_price_source_default_unchanged_and_earlier_research_date_frozen():
    assert p4r.HISTORICAL_PRICE_START == "2017-01-01"
    assert p4r.HORIZON == 126
    assert p4r.SIDE_COSTS_BPS == (5, 15, 35)
    assert p4l.public_prices.__defaults__ == ("2025-10-01",)


def test_existing_older_accession_not_reused_as_a_new_filing_signal():
    a = annual()
    cat = next(x for x in a["observations"] if x["ticker"] == "CAT")
    cat["annual_events"].append({
        "asof_conservative_available_date": "2025-04-01",
        "source_10k_available_date": "2025-02-18",
        "source_10k_accession": "0000000001-25-000001",
        "state": "SOURCE_MATCHED_LATEST_10K_DESCRIPTIVE_ONLY",
        "score": 3, "same_accession_comparative": True,
    })
    cat["annual_filing_dates_reviewed"] = 2
    cat["available_score_count"] = 2
    a["industrial_annual_filing_dates_reviewed"] = 3
    a["industrial_annual_scores_available"] = 3
    out = run(a=a)
    assert out["completed_event_returns"] == 2
    assert out["nonnew_or_unavailable_source_accession_events"] == 1
    assert len([r for r in out["event_returns"] if r["ticker"] == "CAT"]) == 1


def test_future_source_accession_is_rejected_not_forward_filled():
    a = annual()
    cat = next(x for x in a["observations"] if x["ticker"] == "CAT")
    cat["annual_events"][0]["source_10k_available_date"] = "2025-03-01"
    with pytest.raises(p4r.EventStudyStop, match="Future SEC accession"):
        run(a=a)


def _outcome(ticker, score, pp):
    return {"ticker": ticker, "quality_score": score,
            "cost_scenarios": {str(bps): {"stock_minus_spy_pp": pp}
                               for bps in p4r.SIDE_COSTS_BPS}}


def test_issuer_balancing_does_not_treat_repeat_annual_events_as_independent():
    rows = [
        _outcome("AAA", 3, 10), _outcome("AAA", 3, 10),
        _outcome("BBB", 2, -10),
        _outcome("CCC", 0, -5), _outcome("DDD", 1, -5),
    ]
    assert p4r._summarize(rows[:3], 15)["mean_stock_minus_spy_pp"] == 3.333333
    report = p4r._issuer_balanced_sensitivity(rows, 15)
    assert report["score_2_or_3"]["distinct_issuers"] == 2
    assert report["score_2_or_3"]["issuer_equal_weight_mean_stock_minus_spy_pp"] == 0
    assert report["score_0_or_1"]["issuer_equal_weight_mean_stock_minus_spy_pp"] == -5
    assert report["high_minus_low_issuer_balanced_pp"] == 5
    assert report["leave_one_issuer_out_gap_range_pp"] == [-5, 15]
    assert report["leave_one_issuer_out_evaluable_exclusions"] == 4
    assert report["deletion_range_is_not_a_confidence_interval"]


def test_issuer_changing_quality_groups_is_deleted_from_both_sides():
    rows = [
        _outcome("AAA", 3, 10), _outcome("BBB", 3, 0),
        _outcome("AAA", 0, -20), _outcome("CCC", 0, 0),
    ]
    report = p4r._issuer_balanced_sensitivity(rows, 15)
    assert report["issuers_appearing_in_both_groups"] == ["AAA"]
    assert report["high_minus_low_issuer_balanced_pp"] == 15
    assert report["leave_one_issuer_out_gap_pp"]["AAA"] == 0
    assert report["leave_one_issuer_out_gap_range_pp"] == [0, 25]
    assert report["survivorship_and_overlapping_outcomes_preclude_alpha_inference"]


def test_issuer_balance_missing_comparison_group_is_explicitly_unavailable():
    report = p4r._issuer_balanced_sensitivity([_outcome("AAA", 3, 10)], 35)
    assert report["score_0_or_1"]["distinct_issuers"] == 0
    assert report["score_0_or_1"]["issuer_equal_weight_mean_stock_minus_spy_pp"] is None
    assert report["high_minus_low_issuer_balanced_pp"] is None
    assert report["leave_one_issuer_out_gap_range_pp"] is None
    assert report["leave_one_issuer_out_evaluable_exclusions"] == 0


def test_issuer_balance_is_integrated_at_all_cost_levels_without_trading():
    out = run()
    assert set(out["issuer_balanced_sensitivity"]) == {"5", "15", "35"}
    for bps in p4r.SIDE_COSTS_BPS:
        diag = out["issuer_balanced_sensitivity"][str(bps)]
        assert diag["score_2_or_3"]["distinct_issuers"] == 1
        assert diag["score_0_or_1"]["distinct_issuers"] == 1
        assert diag["high_minus_low_issuer_balanced_pp"] > 0
        assert diag["leave_one_issuer_out_gap_range_pp"] is None
    assert out["broker_requests"] == out["broker_orders"] == 0
    assert not out["live_authorized"]


def test_fixed_pre_filing_momentum_excludes_filing_and_forward_closes():
    baseline = run()
    rows = {r["ticker"]: r for r in baseline["event_returns"]}
    assert baseline["predeclared_pre_filing_momentum_sessions"] == 126
    assert baseline["pre_filing_momentum_threshold_pp"] == 0
    assert rows["CAT"]["pre_filing_momentum_last_close"] == "2025-02-17"
    assert rows["CAT"]["pre_filing_momentum_last_close"] < rows["CAT"]["conservative_available_date"]
    assert rows["CAT"]["pre_filing_relative_momentum_positive"] is False
    assert rows["CAT"]["pre_filing_126_session_stock_minus_spy_pp"] == 0
    assert baseline["quality_by_pre_filing_relative_momentum"]["15"]["nonpositive_relative_momentum"]["events"] == 2

    p = prices()
    # Only a completed pre-filing close changes the fixed relative signal.
    p.loc[pd.Timestamp("2025-02-17"), "CAT"] = 110.0
    changed = run(p=p)
    cat = next(r for r in changed["event_returns"] if r["ticker"] == "CAT")
    assert cat["pre_filing_relative_momentum_positive"] is True
    assert cat["pre_filing_126_session_stock_minus_spy_pp"] == 10
    assert cat["stock_gross_return_pct"] == rows["CAT"]["stock_gross_return_pct"]
    for bps in p4r.SIDE_COSTS_BPS:
        study = changed["quality_by_pre_filing_relative_momentum"][str(bps)]
        assert study["positive_relative_momentum"]["score_2_or_3"]["events"] == 1
        assert study["nonpositive_relative_momentum"]["score_0_or_1"]["events"] == 1
        assert study["all_completed_events_accounted"]
        assert study["no_independent_alpha_or_statistical_significance_claim"]


def test_missing_prior_126_session_lookback_is_explicit_not_backfilled():
    a = annual()
    cat = next(r for r in a["observations"] if r["ticker"] == "CAT")
    cat["annual_events"][0]["asof_conservative_available_date"] = "2017-02-15"
    cat["annual_events"][0]["source_10k_available_date"] = "2017-02-15"
    result = run(a=a)
    assert result["completed_event_returns"] == 2
    assert result["missing_pre_filing_momentum_lookback_events"] == 1
    cat_result = next(r for r in result["event_returns"] if r["ticker"] == "CAT")
    assert cat_result["pre_filing_relative_momentum_positive"] is None
    assert cat_result["pre_filing_126_session_stock_minus_spy_pp"] is None
    assert cat_result["pre_filing_momentum_last_close"] is None
    for bps in p4r.SIDE_COSTS_BPS:
        diag = result["quality_by_pre_filing_relative_momentum"][str(bps)]
        assert diag["unavailable_lookback_events"] == 1
        assert diag["nonpositive_relative_momentum"]["events"] == 1
        assert diag["all_completed_events_accounted"]


def test_momentum_cells_remain_descriptive_and_not_an_investable_strategy():
    report = run()
    assert set(report["quality_by_pre_filing_relative_momentum"]) == {"5", "15", "35"}
    for bps, cells in report["quality_by_pre_filing_relative_momentum"].items():
        assert cells["method"] == "FIXED_126_SESSION_PRE_FILING_STOCK_MINUS_SPY_SIGN_X_SEC_QUALITY"
        assert cells["momentum_uses_only_closes_strictly_before_filing_day"]
        assert cells["no_threshold_search_or_fitted_allocation"]
        assert cells["zero_relative_momentum_classified_nonpositive"]
        for name in ("positive_relative_momentum", "nonpositive_relative_momentum"):
            diag = cells[name]
            assert diag["issuer_balanced_sensitivity"]["method"] == "ISSUER_EQUAL_WEIGHT_WITH_WHOLE_ISSUER_DELETION"
            assert diag["score_0_or_1"]["events"] + diag["score_2_or_3"]["events"] == diag["events"]
    assert report["broker_requests"] == report["broker_orders"] == 0
    assert not report["trading_authorized"] and not report["live_authorized"]


def test_prefiling_market_beta_and_linearized_risk_proxy_use_only_past_prices():
    p = prices()
    index = p.index
    pre_i = int(index.searchsorted(pd.Timestamp("2025-02-18"), side="left")) - 1
    first_i = pre_i - p4r.MOMENTUM_LOOKBACK
    for i in range(first_i + 1, pre_i + 1):
        market_r = .002 if i % 2 else -.001
        p.loc[index[i], "SPY"] = p.loc[index[i - 1], "SPY"] * (1 + market_r)
        p.loc[index[i], "CAT"] = p.loc[index[i - 1], "CAT"] * (1 + 2 * market_r)
    entry_i = int(index.searchsorted(pd.Timestamp("2025-02-18"), side="right"))
    for i in range(entry_i + 1, len(index)):
        p.loc[index[i], "SPY"] = 100 * 1.0001 ** (i - entry_i)
    result = run(p=p)
    cat = next(r for r in result["event_returns"] if r["ticker"] == "CAT")
    assert cat["prefiling_market_beta_status"] == "IDENTIFIABLE_PREFILING_126_SESSION_BETA"
    assert 1.99 < cat["prefiling_126_session_spy_beta"] < 2.01
    assert cat["beta_adjusted_15bps_proxy_pp"] < cat["cost_scenarios"]["15"]["stock_net_return_pct"]
    cells = result["prefiling_market_beta_risk_diagnostic"]
    assert cells["pre_filing_beta_uses_no_filing_day_or_forward_prices"]
    assert cells["no_shorting_or_leverage_or_executable_hedge_implied"]
    assert cells["no_significance_or_investable_alpha_inference"]
    assert result["beta_adjusted_proxy_is_not_a_hedged_trade_or_alpha"]
    # Alter future SPY and stock prices only: beta MUST remain unchanged.
    p.loc[index[entry_i + 10], "CAT"] *= 1.15
    p.loc[index[entry_i + 11], "SPY"] *= 1.20
    later = run(p=p)
    new_cat = next(r for r in later["event_returns"] if r["ticker"] == "CAT")
    assert new_cat["prefiling_126_session_spy_beta"] == cat["prefiling_126_session_spy_beta"]


def test_beta_unidentifiable_for_constant_market_or_missing_lookback():
    out = run()
    for row in out["event_returns"]:
        assert row["prefiling_market_beta_status"] == "PREFILING_MARKET_VARIANCE_UNIDENTIFIABLE"
        assert row["prefiling_126_session_spy_beta"] is None
        assert row["beta_adjusted_15bps_proxy_pp"] is None
    cells = out["prefiling_market_beta_risk_diagnostic"]["by_quality_and_prior_momentum"]
    assert all(v["beta_identifiable_events"] == 0 for v in cells.values())
    assert all(v["issuer_equal_mean_beta_adjusted_15bps_proxy_pp"] is None
               for v in cells.values())
    a = annual()
    cat = next(r for r in a["observations"] if r["ticker"] == "CAT")
    cat["annual_events"][0]["asof_conservative_available_date"] = "2017-02-15"
    cat["annual_events"][0]["source_10k_available_date"] = "2017-02-15"
    result = run(a=a)
    early = next(r for r in result["event_returns"] if r["ticker"] == "CAT")
    assert early["prefiling_market_beta_status"] == "INSUFFICIENT_PREFILING_SESSIONS"
    assert early["prefiling_126_session_spy_beta"] is None
    assert not result["live_authorized"] and result["broker_orders"] == 0


def test_six_slot_overlap_replay_is_costed_paired_and_stays_research_only():
    baseline = run()
    assert baseline["schema"].endswith("_V4")
    assert baseline["capacity_replay_is_hindsight_survivor_stress_not_alpha"]
    assert set(baseline["costed_six_slot_overlap_replay"]) == {"5", "15", "35"}
    assert baseline["costed_six_slot_overlap_replay"]["15"]["admitted_events"] == 0
    assert baseline["costed_six_slot_overlap_replay"]["15"]["stock"]["terminal_nav"] == 1
    p = prices()
    p.loc["2025-02-17", "CAT"] = 110.
    report = run(p=p)
    for bps in p4r.SIDE_COSTS_BPS:
        row = report["costed_six_slot_overlap_replay"][str(bps)]
        assert row["eligible_high_quality_positive_prior_momentum_events"] == 1
        assert row["admitted_events"] == 1
        assert row["peak_concurrent_positions"] == 1
        assert row["stock_minus_paired_spy_cagr_pp"] > 0
        assert row["paired_control_uses_identical_admissions_and_dollar_entries"]
        assert row["maturity_buffer_sessions"] == p4r.HORIZON
        assert row["2026_survivor_universe_and_revisable_prices_not_investable_alpha"]
        assert row["no_broker_or_trading_authority"]
    assert (report["costed_six_slot_overlap_replay"]["5"]["stock"]["terminal_nav"]
            > report["costed_six_slot_overlap_replay"]["35"]["stock"]["terminal_nav"])
    assert not report["live_authorized"] and report["broker_orders"] == 0


def test_paired_spy_control_has_identical_return_when_selected_stock_matches_spy():
    p = prices()
    p.loc["2025-02-17", "CAT"] = 110.
    p.loc["2025-02-19":, "CAT"] = 100.
    report = run(p=p)["costed_six_slot_overlap_replay"]["15"]
    assert report["admitted_events"] == 1
    assert report["stock"]["terminal_nav"] == report["same_entry_dollar_matched_spy"]["terminal_nav"]
    assert report["stock_minus_paired_spy_terminal_wealth_pp"] == 0
    assert report["stock_minus_paired_spy_cagr_pp"] == 0


def _synthetic_replay_event(ticker, entry_i, frame, accession):
    return {
        "ticker": ticker, "original_10k_accession": accession,
        "quality_score": 3,
        "pre_filing_relative_momentum_positive": True,
        "pre_filing_126_session_stock_minus_spy_pp": 5.0,
        "entry_next_session_close": frame.index[entry_i].date().isoformat(),
        "exit_126_sessions_later": frame.index[entry_i + p4r.HORIZON].date().isoformat(),
    }


def test_six_slot_capacity_rejects_seventh_concurrent_signal_without_leverage():
    p = prices()
    symbols = sorted(p4n.SOURCE_MATCHED_TAGS)[:7]
    i = int(p.index.get_loc(pd.Timestamp("2025-02-19")))
    rows = [_synthetic_replay_event(ticker, i, p, str(n))
            for n, ticker in enumerate(symbols)]
    result = p4r._capacity_constrained_replay(rows, p, 15)
    assert result["eligible_high_quality_positive_prior_momentum_events"] == 7
    assert result["admitted_events"] == 6
    assert result["blocked_by_six_slot_capacity"] == 1
    assert result["peak_concurrent_positions"] == 6
    assert result["stock"]["terminal_nav"] > 0
    assert result["same_entry_dollar_matched_spy"]["terminal_nav"] > 0
    assert 0 < result["average_gross_stock_exposure_fraction"] <= 1


def test_replay_censor_guard_ignores_future_source_changes_and_liquidates_open_positions():
    p = prices()
    cutoff = len(p) - p4r.HORIZON - 1
    i = cutoff - 10
    row = _synthetic_replay_event("CAT", i, p, "terminal")
    a = p4r._capacity_constrained_replay([row], p, 15)
    assert a["admitted_events"] == 1
    assert a["forced_terminal_liquidations"] == 1
    assert a["last_session_maturity_cutoff"] == p.index[cutoff].date().isoformat()
    altered = p.copy()
    altered.loc[p.index[cutoff + 1]:, "CAT"] *= 1.1
    b = p4r._capacity_constrained_replay([row], altered, 15)
    assert a == b
    # A later event is excluded rather than accepted only if its outcome matured.
    late = _synthetic_replay_event("CAT", cutoff, p, "late")
    assert p4r._capacity_constrained_replay([late], p, 15)["admitted_events"] == 0


def test_replay_rejects_mismatched_event_horizon_and_duplicate_accession():
    p = prices()
    i = int(p.index.get_loc(pd.Timestamp("2025-02-19")))
    row = _synthetic_replay_event("CAT", i, p, "same")
    invalid = dict(row, exit_126_sessions_later=p.index[i + 125].date().isoformat())
    with pytest.raises(p4r.EventStudyStop, match="contract"):
        p4r._capacity_constrained_replay([invalid], p, 15)
    with pytest.raises(p4r.EventStudyStop, match="Duplicate"):
        p4r._capacity_constrained_replay([row, row], p, 15)
    with pytest.raises(p4r.EventStudyStop, match="cost"):
        p4r._capacity_constrained_replay([row], p, 0)


def synthetic_irx(percent=4.0):
    # Vendor-style observed quote dates; not an actual account cash return.
    ix = pd.bdate_range("2013-12-02", "2026-10-23")
    return pd.DataFrame({"IRX": float(percent)}, index=ix)


def test_original_zero_cash_portfolio_replay_unchanged_when_rates_are_supplied():
    p = prices()
    p.loc["2025-02-17", "CAT"] = 110.
    original = run(p=p)
    adjusted = run(p=p, rates=synthetic_irx())
    assert adjusted["costed_six_slot_overlap_replay"] == original["costed_six_slot_overlap_replay"]
    assert original["costed_six_slot_cash_carry_sensitivity"] == {}
    assert adjusted["cash_rate_source"] == "YAHOO_IRX_13W_BILL_DISCOUNT_PROXY"
    assert len(adjusted["cash_rate_source_canonical_sha256"]) == 64
    assert adjusted["cash_rate_lag_weekdays"] == 3
    assert adjusted["zero_cash_baseline_preserved"]
    assert adjusted["cash_rate_not_actual_broker_interest_or_executable_rolled_bill"]
    for bps in p4r.SIDE_COSTS_BPS:
        rows = adjusted["costed_six_slot_cash_carry_sensitivity"][str(bps)]
        assert set(rows) == {"IRX_GROSS", "IRX_MINUS_50BP"}
        baseline = original["costed_six_slot_overlap_replay"][str(bps)]
        for label, row in rows.items():
            assert row["admitted_events"] == baseline["admitted_events"] == 1
            assert row["cash_accrual_uses_prior_session_rate_and_actual_calendar_days"]
            assert not row["cash_yield_assumed_zero_not_a_historical_bill_benchmark"]
            assert row["stock"]["net_cagr_pct"] > baseline["stock"]["net_cagr_pct"]
            assert (row["same_entry_dollar_matched_spy"]["net_cagr_pct"] >
                    baseline["same_entry_dollar_matched_spy"]["net_cagr_pct"])
            assert row["stock_cagr_minus_zero_cash_pp"] > 0
            assert row["matched_spy_cagr_minus_zero_cash_pp"] > 0
            assert abs(row["stock_minus_spy_cagr_change_from_zero_cash_pp"]) < 1


def test_cash_compounds_actual_weekend_days_and_prior_session_rate_without_trades():
    p = prices()
    constant = pd.Series(4., index=p.index)
    replay = p4r._capacity_constrained_replay([], p, 15, cash_annual_rate=constant)
    cutoff = len(p) - p4r.HORIZON - 1
    elapsed = (p.index[cutoff] - p.index[0]).days
    expected = np.exp(.04 * elapsed / 365.25)
    assert replay["stock"]["terminal_nav"] == round(expected, 6)
    assert replay["same_entry_dollar_matched_spy"]["terminal_nav"] == round(expected, 6)
    assert replay["stock_minus_paired_spy_cagr_pp"] == 0
    # The last session's rate cannot affect cash that has already accrued.
    changed = constant.copy()
    changed.iloc[cutoff - 1:] = 20.
    assert (p4r._capacity_constrained_replay([], p, 15, cash_annual_rate=changed)
            ["stock"]["terminal_nav"] >
            replay["stock"]["terminal_nav"])
    changed = constant.copy()
    changed.iloc[cutoff:] = 20.
    assert (p4r._capacity_constrained_replay([], p, 15, cash_annual_rate=changed)
            ["stock"]["terminal_nav"] == replay["stock"]["terminal_nav"])


def test_cash_proxy_is_symmetric_and_rejects_misaligned_or_invalid_rates():
    p = prices()
    p.loc["2025-02-17", "CAT"] = 110.
    i = int(p.index.get_loc(pd.Timestamp("2025-02-19")))
    row = _synthetic_replay_event("CAT", i, p, "symmetric")
    # Identical stock and SPY prices must produce exactly equal wealth
    # even when both sides receive the same cash interest.
    p["CAT"] = p["SPY"]
    rate = pd.Series(5., index=p.index)
    out = p4r._capacity_constrained_replay([row], p, 15, cash_annual_rate=rate)
    assert out["stock"] == out["same_entry_dollar_matched_spy"]
    for invalid in (rate.iloc[:-1], rate.rename_axis("other").set_axis(
                    pd.date_range("2017-01-01", periods=len(rate))),
                    rate.astype(object), rate.mask(rate.index == rate.index[3], np.nan),
                    pd.Series(26., index=p.index),
                    pd.Series(-1., index=p.index)):
        with pytest.raises(p4r.EventStudyStop, match="Cash-rate|cash-rate"):
            p4r._capacity_constrained_replay([row], p, 15, cash_annual_rate=invalid)


def test_cash_rate_original_vendor_source_fails_closed_on_missing_or_stale_quotes():
    rates = synthetic_irx()
    with pytest.raises(p4r.EventStudyStop, match="cash-rate"):
        run(rates=rates.loc["2018-01-01":])
    with pytest.raises(p4r.EventStudyStop, match="cash-rate"):
        run(rates=rates.loc[:"2026-09-01"])
    broken = rates.copy()
    broken.iloc[0, 0] = np.nan
    with pytest.raises(p4r.EventStudyStop, match="cash-rate"):
        run(rates=broken)
    with pytest.raises(p4r.EventStudyStop, match="Cash-rate"):
        run(rates=pd.Series(4., index=rates.index))


def test_spy_funded_overlay_no_events_equals_passive_after_two_sided_costs():
    p = prices()
    for bps in p4r.SIDE_COSTS_BPS:
        out = p4r._spy_idle_capital_overlay([], p, bps)
        assert out["admitted_events"] == 0
        assert out["no_signals_equals_identical_passive_spy"]
        assert out["stock_replacement_plus_spy_core"] == out["passive_buy_and_hold_spy"]
        assert out["replacement_minus_passive_cagr_pp"] == 0
        assert out["overlay_stock_traded_notional_per_initial_nav"] == 0
        assert out["average_stock_exposure_fraction"] == 0
        assert out["research_only_no_broker_or_live_authority"]


def test_spy_funded_overlay_reuses_existing_causal_admissions_and_costs_churn():
    p = prices()
    p.loc["2025-02-17", "CAT"] = 110.
    out = run(p=p)
    for bps in p4r.SIDE_COSTS_BPS:
        key = str(bps)
        baseline = out["costed_six_slot_overlap_replay"][key]
        overlay = out["costed_six_slot_spy_idle_capital_overlay"][key]
        assert overlay["admitted_events"] == baseline["admitted_events"] == 1
        assert overlay["peak_concurrent_positions"] == baseline["peak_concurrent_positions"]
        assert overlay["average_stock_exposure_fraction"] > 0
        assert overlay["average_stock_exposure_fraction"] < 1
        assert overlay["stock_replacement_plus_spy_core"]["terminal_nav"] > 0
        assert overlay["passive_buy_and_hold_spy"]["terminal_nav"] > 0
        assert overlay["overlay_spy_traded_notional_per_initial_nav"] > 0
        assert overlay["overlay_stock_traded_notional_per_initial_nav"] > 0
        assert overlay["all_spy_to_stock_and_stock_to_spy_switches_costed"]
        assert overlay["original_admissions_reused_without_refitting_thresholds"]
        assert overlay["not_a_validated_point_in_time_survivorship_free_strategy"]
        assert overlay["not_risk_matched_to_low_equity_cash_portfolio"]
    assert not out["live_authorized"] and out["broker_orders"] == 0


def test_spy_funded_overlay_identical_stock_and_spy_loses_only_extra_switch_cost():
    p = prices()
    p["CAT"] = p["SPY"]
    i = int(p.index.get_loc(pd.Timestamp("2025-02-19")))
    row = _synthetic_replay_event("CAT", i, p, "same-spy")
    baseline = p4r._capacity_constrained_replay([row], p, 15)
    overlay = p4r._spy_idle_capital_overlay(baseline["admission_schedule"], p, 15)
    assert overlay["admitted_events"] == 1
    assert overlay["replacement_minus_passive_cagr_pp"] < 0
    assert overlay["replacement_minus_passive_terminal_wealth_pp"] < 0
    assert overlay["passive_and_overlay_pay_same_initial_and_final_spy_fees"]


def test_spy_funded_overlay_stock_excess_return_can_offset_switching_costs():
    p = prices()
    i = int(p.index.get_loc(pd.Timestamp("2025-02-19")))
    for j in range(i + 1, len(p)):
        p.iloc[j, p.columns.get_loc("CAT")] = 100 * 1.002 ** (j - i)
    row = _synthetic_replay_event("CAT", i, p, "outperform")
    admissions = p4r._capacity_constrained_replay([row], p, 15)["admission_schedule"]
    result = p4r._spy_idle_capital_overlay(admissions, p, 15)
    assert result["replacement_minus_passive_cagr_pp"] > 0
    assert result["average_stock_exposure_fraction"] > 0


def test_spy_funded_overlay_censoring_and_rejects_invalid_admissions():
    p = prices()
    cutoff = len(p) - p4r.HORIZON - 1
    i = cutoff - 10
    row = _synthetic_replay_event("CAT", i, p, "terminal")
    schedule = p4r._capacity_constrained_replay([row], p, 15)["admission_schedule"]
    before = p4r._spy_idle_capital_overlay(schedule, p, 15)
    assert before["forced_terminal_stock_exits"] == 1
    changed = p.copy()
    changed.loc[p.index[cutoff + 1]:, "CAT"] *= 1.5
    changed.loc[p.index[cutoff + 1]:, "SPY"] *= 1.2
    assert before == p4r._spy_idle_capital_overlay(schedule, changed, 15)
    with pytest.raises(p4r.EventStudyStop, match="chronology"):
        p4r._spy_idle_capital_overlay(
            [dict(schedule[0], exit_close=p.index[i + 125].date().isoformat())], p, 15)
    with pytest.raises(p4r.EventStudyStop, match="chronology"):
        p4r._spy_idle_capital_overlay(schedule + schedule, p, 15)
    with pytest.raises(p4r.EventStudyStop, match="cost"):
        p4r._spy_idle_capital_overlay(schedule, p, 0)
