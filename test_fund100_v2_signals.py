"""Offline-only tests of V2 signal causality and research-panel provenance."""

from datetime import date, timedelta

import pytest

from fund100_v2.signals import (
    RESEARCH_FAMILIES,
    REQUIRED_LOOKBACK,
    ResearchPanel,
    score_on_close,
    top_research_candidate,
)


def weekdays(n=230):
    result = []
    d = date(2024, 1, 1)
    while len(result) < n:
        if d.weekday() < 5:
            result.append(d)
        d += timedelta(days=1)
    return tuple(result)


def sample_panel(n=230, *, eligibility=None):
    days = weekdays(n)
    one = tuple(100.0 * 1.002 ** t for t in range(n))
    two = tuple(200.0 * 0.999 ** t for t in range(n))
    return ResearchPanel(
        sessions=days,
        adjusted_prices={"UP": one, "DOWN": two},
        spread_bps={"UP": (2.0,) * n, "DOWN": (10.0,) * n},
        eligible_symbols=(
            eligibility if eligibility is not None
            else tuple(frozenset({"UP", "DOWN"}) for _ in range(n))
        ),
    )


def test_all_three_distinct_families_are_available():
    assert len(RESEARCH_FAMILIES) == 3
    p = sample_panel()
    i = 100
    assert score_on_close(p, "medium_momentum", i, "UP") > 0
    assert score_on_close(p, "short_reversal", i, "DOWN") > 0
    assert score_on_close(p, "risk_scaled_trend", i, "UP") > 0
    assert top_research_candidate(p, "medium_momentum", i) == "UP"
    assert top_research_candidate(p, "short_reversal", i) == "DOWN"
    assert top_research_candidate(p, "risk_scaled_trend", i) == "UP"


@pytest.mark.parametrize("family", RESEARCH_FAMILIES)
def test_signal_at_t_cannot_see_later_prices(family):
    base = sample_panel()
    end = 100
    prices = {key: list(values) for key, values in base.adjusted_prices.items()}
    prices["UP"][end + 1] *= 40.0
    prices["DOWN"][end + 2] *= 0.05
    altered = ResearchPanel(
        sessions=base.sessions,
        adjusted_prices=prices,
        spread_bps=base.spread_bps,
        eligible_symbols=base.eligible_symbols,
    )
    for ticker in base.adjusted_prices:
        assert score_on_close(base, family, end, ticker) == pytest.approx(
            score_on_close(altered, family, end, ticker)
        )


def test_only_same_day_historical_eligibility_controls_choice():
    eligibility = [frozenset({"UP", "DOWN"}) for _ in range(230)]
    eligibility[100] = frozenset({"DOWN"})
    p = sample_panel(eligibility=tuple(eligibility))
    assert top_research_candidate(p, "medium_momentum", 100) is None
    # DOWN is negative momentum, so cash is chosen without forwarding UP.
    assert top_research_candidate(p, "short_reversal", 100) == "DOWN"


def test_future_membership_change_does_not_change_past_signal():
    a = sample_panel()
    choices = [frozenset({"UP", "DOWN"}) for _ in range(230)]
    for t in range(101, 230):
        choices[t] = frozenset({"DOWN"})
    b = sample_panel(eligibility=tuple(choices))
    assert top_research_candidate(a, "medium_momentum", 100) == "UP"
    assert top_research_candidate(b, "medium_momentum", 100) == "UP"


@pytest.mark.parametrize("bad_family", ("", "breakout", "CASH", "live_orders"))
def test_unknown_signal_family_fails(bad_family):
    with pytest.raises(ValueError, match="Unknown"):
        score_on_close(sample_panel(), bad_family, REQUIRED_LOOKBACK, "UP")


def test_no_score_without_lookback():
    with pytest.raises(ValueError, match="60 past"):
        score_on_close(
            sample_panel(), RESEARCH_FAMILIES[0], REQUIRED_LOOKBACK - 1, "UP"
        )


@pytest.mark.parametrize(
    "change,error",
    [
        ({"adjusted_prices": {"UP": (100.0,) * 10}}, "identical"),
        ({"eligible_symbols": tuple()}, "eligibility"),
        ({"adjusted_prices": {"UP": (1.0,) * 230}}, "identical"),
        ({"adjusted_prices": {
            "UP": (float("nan"),) + (100.0,) * 229,
            "DOWN": (200.0,) * 230
        }}, "adjusted price"),
        ({"spread_bps": {
            "UP": (float("inf"),) + (2.0,) * 229,
            "DOWN": (10.0,) * 230
        }}, "quoted spread"),
        ({"eligible_symbols": tuple(
            frozenset({"NOT_IN_PANEL"}) for _ in range(230)
        )}, "unknown symbol"),
    ],
)
def test_bad_panel_data_fails_closed(change, error):
    p = sample_panel()
    fields = dict(
        sessions=p.sessions,
        adjusted_prices=p.adjusted_prices,
        spread_bps=p.spread_bps,
        eligible_symbols=p.eligible_symbols,
    )
    fields.update(change)
    with pytest.raises(ValueError, match=error):
        ResearchPanel(**fields)


def test_duplicate_or_unsorted_session_dates_rejected():
    p = sample_panel()
    with pytest.raises(ValueError, match="strictly increasing"):
        ResearchPanel(
            sessions=p.sessions[:10] + (p.sessions[9],) + p.sessions[11:],
            adjusted_prices=p.adjusted_prices,
            spread_bps=p.spread_bps,
            eligible_symbols=p.eligible_symbols,
        )


def test_price_and_membership_are_frozen_at_panel_creation():
    n = 230
    values = [100.0] * n
    permissions = [frozenset({"UP"}) for _ in range(n)]
    p = ResearchPanel(
        weekdays(n),
        {"UP": values},
        {"UP": [2.0] * n},
        tuple(permissions),
    )
    values[100] = 10_000.0
    permissions[100] = frozenset()
    assert p.adjusted_prices["UP"][100] == 100.0
    assert p.eligible_symbols[100] == frozenset({"UP"})
