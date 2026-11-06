"""Research-only, exposure-matched comparator. Never modifies the forward ledger.

All inputs are pre-session observations: equity_weight[t] must be fixed before
session t, and cash_return[t] must be a verified point-in-time session return.
This function does not source rates or infer missing values.
"""
from __future__ import annotations

import math
from collections.abc import Sequence


def exposure_matched_benchmark(
    acwi_returns: Sequence[float],
    cash_returns: Sequence[float],
    pre_session_equity_weights: Sequence[float],
    *,
    one_way_cost_bps: float = 15.0,
    initial_equity_weight: float | None = None,
) -> list[float]:
    """Return daily net comparator returns for ACWI/cash with matched equity weight.

    Each session uses the strategy's *pre-session* aggregate equity exposure.
    At session boundaries, the comparator rebalances to that exposure and
    pays one-way costs on notional traded. The first session charges no
    rebalance cost unless an explicit initial comparator weight is supplied.
    Cash and ACWI returns must be independently qualified and aligned.
    """
    n = len(acwi_returns)
    if n == 0 or len(cash_returns) != n or len(pre_session_equity_weights) != n:
        raise ValueError("nonempty, equally sized aligned inputs required")
    if not math.isfinite(one_way_cost_bps) or one_way_cost_bps < 0:
        raise ValueError("invalid cost")
    if initial_equity_weight is not None and (
        not math.isfinite(initial_equity_weight)
        or not 0 <= initial_equity_weight <= 1
    ):
        raise ValueError("invalid initial weight")

    output: list[float] = []
    previous_end_weight = initial_equity_weight
    for equity_r, cash_r, weight in zip(
        acwi_returns, cash_returns, pre_session_equity_weights
    ):
        if not all(math.isfinite(x) for x in (equity_r, cash_r, weight)):
            raise ValueError("missing or nonfinite session input")
        if equity_r <= -1 or cash_r <= -1:
            raise ValueError("invalid total return")
        if not 0 <= weight <= 1:
            raise ValueError("equity weight outside [0,1]")
        turnover = 0.0 if previous_end_weight is None else abs(weight - previous_end_weight)
        gross = weight * equity_r + (1 - weight) * cash_r
        net = gross - turnover * one_way_cost_bps / 10000
        if not math.isfinite(gross) or not math.isfinite(net) or net <= -1:
            raise ValueError("invalid or nonfinite net comparator return")
        output.append(net)
        # End-of-session weight drifts after returns; next day's target
        # rebalances from this actual comparator weight, not yesterday's target.
        previous_end_weight = weight * (1 + equity_r) / (1 + gross)
    return output


def compounded_nav(returns: Sequence[float], start_nav: float = 100.0) -> float:
    if not math.isfinite(start_nav) or start_nav <= 0:
        raise ValueError("invalid starting NAV")
    if not returns:
        raise ValueError("nonempty return history required")
    nav = start_nav
    for value in returns:
        if not math.isfinite(value) or value <= -1:
            raise ValueError("invalid return")
        nav *= 1 + value
        if not math.isfinite(nav) or nav <= 0:
            raise ValueError("nonfinite or underflowed compounded NAV")
    return nav


def dated_exposure_matched_benchmark(
    acwi_observations: Sequence[tuple[str, float]],
    cash_observations: Sequence[tuple[str, float]],
    exposure_observations: Sequence[tuple[str, str, float]],
    *,
    one_way_cost_bps: float = 15.0,
    initial_equity_weight: float | None = None,
    max_exposure_age_days: float = 7.0,
) -> list[tuple[str, float]]:
    """Fail closed unless all session keys match and exposure was known beforehand.

    Each exposure tuple is (session_date, observed_at_utc, equity_weight).
    observed_at_utc is an ISO timestamp with explicit UTC offset. It must
    precede the session date at 00:00 UTC (conservative cutoff); no forward
    filling, implicit sorting, or synthetic cash yields are permitted.
    Reject exposure snapshots older than max_exposure_age_days before the
    conservative session cutoff; this checks freshness, not source provenance.
    """
    from datetime import date, datetime, time, timezone

    if not math.isfinite(max_exposure_age_days) or max_exposure_age_days <= 0:
        raise ValueError("invalid maximum exposure age")

    n = len(acwi_observations)
    if not n or len(cash_observations) != n or len(exposure_observations) != n:
        raise ValueError("nonempty equal-length dated observations required")
    sessions: list[str] = []
    for (a_date, _), (c_date, _), (w_date, observed_at, _) in zip(
        acwi_observations, cash_observations, exposure_observations
    ):
        try:
            session = date.fromisoformat(a_date)
            if session.isoformat() != a_date or a_date != c_date or a_date != w_date:
                raise ValueError("misaligned session dates")
            stamp = datetime.fromisoformat(observed_at)
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError("exposure timestamp must be timezone aware")
            cutoff = datetime.combine(session, time.min, tzinfo=timezone.utc)
            age_days = (cutoff - stamp.astimezone(timezone.utc)).total_seconds() / 86400
            if age_days <= 0:
                raise ValueError("exposure was not observed before session")
            if age_days > max_exposure_age_days:
                raise ValueError("stale pre-session exposure observation")
            if sessions and a_date <= sessions[-1]:
                raise ValueError("sessions must be strictly increasing")
        except (TypeError, AttributeError) as exc:
            raise ValueError("invalid dated observation") from exc
        sessions.append(a_date)
    returns = exposure_matched_benchmark(
        [v for _, v in acwi_observations],
        [v for _, v in cash_observations],
        [v for _, _, v in exposure_observations],
        one_way_cost_bps=one_way_cost_bps,
        initial_equity_weight=initial_equity_weight,
    )
    return list(zip(sessions, returns))
