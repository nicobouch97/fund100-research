"""Purged offline walk-forward research: no data download or broker code."""

from dataclasses import replace
from datetime import date, timedelta

import pytest

from fund100_v2.signals import (
    RESEARCH_FAMILIES,
    ResearchPanel,
)
from fund100_v2.walkforward import (
    ResearchCosts,
    WalkForwardPlan,
    evaluate_decision,
    walk_forward,
)


def research_panel(n=275, *, grow=1.002, fall=0.999, memberships=None,
                   price_overrides=None, spread=4.0):
    days = []
    day = date(2024, 1, 1)
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)

    up = [100.0 * grow ** i for i in range(n)]
    down = [100.0 * fall ** i for i in range(n)]
    for (sym, index), value in (price_overrides or {}).items():
        (up if sym == "UP" else down)[index] = value

    return ResearchPanel(
        sessions=tuple(days),
        adjusted_prices={"UP": up, "DOWN": down},
        spread_bps={
            "UP": [spread] * n,
            "DOWN": [spread] * n,
        },
        eligible_symbols=memberships if memberships is not None else tuple(
            frozenset({"UP", "DOWN"}) for _ in range(n)
        ),
    )


def test_decision_fill_is_next_close_and_return_ends_following_close():
    p = research_panel()
    t = 90
    out = evaluate_decision(
        p, "medium_momentum", t, ResearchCosts(0, 0),
        benchmark_symbol="UP",
    )
    assert out.signal_date == p.sessions[t].isoformat()
    assert out.assumed_entry_date == p.sessions[t+1].isoformat()
    assert out.assumed_exit_date == p.sessions[t+2].isoformat()
    assert out.hypothetical_symbol == "UP"
    assert out.gross_fraction == pytest.approx(
        p.adjusted_prices["UP"][t+2] / p.adjusted_prices["UP"][t+1] - 1
    )
    assert out.passive_benchmark_fraction == pytest.approx(out.gross_fraction)


def test_trade_cost_includes_both_fees_slippage_and_half_spreads():
    p = research_panel(spread=10)
    out = evaluate_decision(
        p, "medium_momentum", 100,
        ResearchCosts(fee_bps_per_side=1, slippage_bps_per_side=3),
    )
    assert out.cost_fraction == pytest.approx(
        (2*(1+3) + 0.5*(10+10))/10_000
    )
    assert out.net_fraction == pytest.approx(
        out.gross_fraction - out.cost_fraction
    )


def test_no_instant_fill_at_signal_close():
    p = research_panel()
    t = 100
    before = evaluate_decision(p, "medium_momentum", t, ResearchCosts(0, 0))
    data = {
        ("UP", t+1): p.adjusted_prices["UP"][t+1] * 2.0
    }
    later = research_panel(price_overrides=data)
    after = evaluate_decision(later, "medium_momentum", t,
                              ResearchCosts(0, 0))
    # Signal ranking is unchanged, but execution occurs at changed t+1 close.
    assert before.hypothetical_symbol == after.hypothetical_symbol
    assert before.gross_fraction != after.gross_fraction


def test_post_signal_membership_change_cannot_be_free_cancel():
    n = 275
    memberships = [frozenset({"UP","DOWN"}) for _ in range(n)]
    memberships[101] = frozenset({"DOWN"})
    p = research_panel(memberships=tuple(memberships))
    with pytest.raises(ValueError, match="Entry eligibility changed"):
        evaluate_decision(p, "medium_momentum", 100, ResearchCosts())


def test_cash_is_not_an_order_and_is_zero_return():
    out = evaluate_decision(research_panel(), "CASH", 110, ResearchCosts())
    assert out.hypothetical_symbol is None
    assert out.gross_fraction == out.cost_fraction == out.net_fraction == 0


def test_empty_research_membership_means_zero_return():
    groups = [frozenset({"UP", "DOWN"}) for _ in range(275)]
    groups[100] = frozenset()
    p = research_panel(memberships=tuple(groups))
    out = evaluate_decision(p, "medium_momentum", 100, ResearchCosts())
    assert out.hypothetical_symbol is None
    assert out.net_fraction == 0.0


def test_walk_forward_uses_purged_disjoint_test_windows():
    p = research_panel()
    plan = WalkForwardPlan(
        min_train_decisions=50,
        test_decisions_per_fold=12,
        embargo_sessions=3,
        benchmark_symbol="UP",
    )
    report = walk_forward(p, plan)
    assert len(report.folds) > 3
    assert len(report.out_of_sample) > 30
    assert len(report.audit_sha256) == 64
    first_oos = report.out_of_sample[0].signal_date
    assert first_oos == report.folds[0].test_first_signal_date
    assert all(
        row.family == "CASH" or row.family in RESEARCH_FAMILIES
        for row in report.out_of_sample
    )
    signal_dates = [row.signal_date for row in report.out_of_sample]
    assert signal_dates == sorted(set(signal_dates))
    for fold in report.folds:
        resolved = next(i for i, x in enumerate(p.sessions)
                        if x.isoformat() == fold.train_last_resolved_date)
        first = next(i for i, x in enumerate(p.sessions)
                     if x.isoformat() == fold.test_first_signal_date)
        assert first - resolved > plan.embargo_sessions
    for one, two in zip(report.folds, report.folds[1:]):
        assert one.test_last_signal_date < two.test_first_signal_date


def test_training_choice_does_not_use_future_test_returns():
    base = research_panel()
    plan = WalkForwardPlan(min_train_decisions=40,
                           test_decisions_per_fold=8, embargo_sessions=2)
    original = walk_forward(base, plan)
    first_test = next(i for i, x in enumerate(base.sessions)
                      if x.isoformat() == original.folds[0].test_first_signal_date)
    future_jump = {
        ("UP", index): base.adjusted_prices["UP"][index] * 0.2
        for index in range(first_test + 1, len(base.sessions))
    }
    mutated = research_panel(price_overrides=future_jump)
    later = walk_forward(mutated, plan)
    assert later.folds[0].chosen_family == original.folds[0].chosen_family
    assert later.folds[0].training_net_mean_fraction == pytest.approx(
        original.folds[0].training_net_mean_fraction
    )
    assert later.audit_sha256 != original.audit_sha256


def test_cost_stress_can_select_cash_baseline():
    report = walk_forward(
        research_panel(),
        WalkForwardPlan(min_train_decisions=25, test_decisions_per_fold=10),
        ResearchCosts(fee_bps_per_side=400, slippage_bps_per_side=400),
    )
    assert report.folds
    assert all(fold.chosen_family == "CASH" for fold in report.folds)
    assert all(out.hypothetical_symbol is None for out in report.out_of_sample)
    assert report.total_net_compound_fraction == 0.0


def test_deterministic_digest_independent_of_symbol_mapping_order():
    p = research_panel()
    swapped = ResearchPanel(
        sessions=p.sessions,
        adjusted_prices={"DOWN": p.adjusted_prices["DOWN"],
                         "UP": p.adjusted_prices["UP"]},
        spread_bps={"DOWN": p.spread_bps["DOWN"],
                    "UP": p.spread_bps["UP"]},
        eligible_symbols=p.eligible_symbols,
    )
    plan = WalkForwardPlan(min_train_decisions=20,
                           test_decisions_per_fold=15,
                           benchmark_symbol="UP")
    assert walk_forward(p, plan) == walk_forward(swapped, plan)


def test_report_is_not_execution_authorisation():
    r = walk_forward(
        research_panel(),
        WalkForwardPlan(min_train_decisions=15,
                        test_decisions_per_fold=8),
    )
    assert r.folds
    assert not hasattr(r, "orders")
    assert not hasattr(r, "positions")
    assert not hasattr(r, "target_weights")
    assert not hasattr(r, "live_execution_authorized")


@pytest.mark.parametrize(
    "bad,reason",
    [
        ({"min_train_decisions": 2}, "Invalid"),
        ({"test_decisions_per_fold": 0}, "Invalid"),
        ({"embargo_sessions": 0}, "Invalid"),
        ({"benchmark_symbol": 123}, "benchmark"),
    ],
)
def test_invalid_walkforward_settings_stop(bad, reason):
    with pytest.raises(ValueError, match=reason):
        WalkForwardPlan(**bad)


@pytest.mark.parametrize(
    "bad",
    [
        {"fee_bps_per_side": -0.01},
        {"slippage_bps_per_side": float("nan")},
        {"fee_bps_per_side": float("inf")},
    ],
)
def test_invalid_cost_settings_stop(bad):
    with pytest.raises(ValueError, match="cost"):
        ResearchCosts(**bad)


def test_missing_benchmark_stops_instead_of_silent_cash_comparison():
    with pytest.raises(ValueError, match="Benchmark"):
        walk_forward(
            research_panel(),
            WalkForwardPlan(benchmark_symbol="MISSING"),
        )


def test_insufficient_data_stops_instead_of_in_sample_report():
    with pytest.raises(ValueError, match="Not enough history"):
        walk_forward(
            research_panel(n=100),
            WalkForwardPlan(min_train_decisions=80),
        )


def test_missing_final_exit_close_cannot_be_reported():
    p = research_panel()
    with pytest.raises(ValueError, match="future holding period"):
        evaluate_decision(p, "medium_momentum", len(p.sessions)-2, ResearchCosts())
