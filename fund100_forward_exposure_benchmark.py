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
        if net <= -1:
            raise ValueError("net return below -100%")
        output.append(net)
        # End-of-session weight drifts after returns; next day's target
        # rebalances from this actual comparator weight, not yesterday's target.
        previous_end_weight = weight * (1 + equity_r) / (1 + gross)
    return output


def compounded_nav(returns: Sequence[float], start_nav: float = 100.0) -> float:
    if not math.isfinite(start_nav) or start_nav <= 0:
        raise ValueError("invalid starting NAV")
    nav = start_nav
    for value in returns:
        if not math.isfinite(value) or value <= -1:
            raise ValueError("invalid return")
        nav *= 1 + value
    return nav
