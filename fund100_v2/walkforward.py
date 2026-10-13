"""Offline V2 expanding-window, purged walk-forward *research evaluation*.

A signal is observed at date t CLOSE; the illustrative fill is next
session CLOSE t+1, and the measured outcome ends at t+2 CLOSE.
The filled trade pays per-side fees, modeled slippage and half the
dated quoted spread at entry and exit. These fill assumptions are
simplifications, not verified execution performance.

Training uses only outcomes fully resolved before test signals, with
an explicit number of blank embargo sessions. Candidate families
are selected solely on training results; test labels never select the
model. Cash is a predeclared model-selection baseline.
No account, broker, order, or LIVE permission exists in this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math

from fund100_v2.signals import (
    RESEARCH_FAMILIES,
    REQUIRED_LOOKBACK,
    ResearchPanel,
    top_research_candidate,
)

SESSIONS_PER_YEAR = 252


@dataclass(frozen=True)
class ResearchCosts:
    """Illustrative *per side*, not validated market-impact assumptions."""

    fee_bps_per_side: float = 1.0
    slippage_bps_per_side: float = 3.0

    def __post_init__(self) -> None:
        for value in (self.fee_bps_per_side, self.slippage_bps_per_side):
            if not _nonnegative_finite(value):
                raise ValueError("Research cost assumptions must be finite and >=0")


@dataclass(frozen=True)
class WalkForwardPlan:
    min_train_decisions: int = 80
    test_decisions_per_fold: int = 20
    embargo_sessions: int = 1
    benchmark_symbol: str | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.min_train_decisions, int)
            or isinstance(self.min_train_decisions, bool)
            or self.min_train_decisions < 10
            or not isinstance(self.test_decisions_per_fold, int)
            or isinstance(self.test_decisions_per_fold, bool)
            or self.test_decisions_per_fold < 1
            or not isinstance(self.embargo_sessions, int)
            or isinstance(self.embargo_sessions, bool)
            or self.embargo_sessions < 1
        ):
            raise ValueError("Invalid purged walk-forward split plan")
        if self.benchmark_symbol is not None and not isinstance(
            self.benchmark_symbol, str
        ):
            raise ValueError("Invalid benchmark symbol")


@dataclass(frozen=True)
class ResearchOutcome:
    """Hypothetical, one-day independent diagnostic; NOT an order."""

    signal_date: str
    assumed_entry_date: str
    assumed_exit_date: str
    family: str
    hypothetical_symbol: str | None
    gross_fraction: float
    cost_fraction: float
    net_fraction: float
    passive_benchmark_fraction: float


@dataclass(frozen=True)
class ResearchFold:
    train_last_resolved_date: str
    test_first_signal_date: str
    test_last_signal_date: str
    chosen_family: str
    training_net_mean_fraction: float
    test_net_mean_fraction: float
    test_benchmark_mean_fraction: float
    test_non_cash_count: int


@dataclass(frozen=True)
class WalkForwardReport:
    folds: tuple[ResearchFold, ...]
    out_of_sample: tuple[ResearchOutcome, ...]
    total_net_compound_fraction: float
    benchmark_compound_fraction: float
    mean_net_fraction_per_decision: float
    mean_benchmark_fraction_per_decision: float
    audit_sha256: str


def _nonnegative_finite(value: object) -> bool:
    try:
        val = float(value)
    except (ValueError, TypeError, OverflowError):
        return False
    return math.isfinite(val) and val >= 0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def evaluate_decision(
    panel: ResearchPanel,
    family: str,
    signal_index: int,
    costs: ResearchCosts,
    *,
    benchmark_symbol: str | None = None,
) -> ResearchOutcome:
    """Evaluate the one-day outcome after a *lagged* hypothetical fill."""
    if family not in RESEARCH_FAMILIES + ("CASH",):
        raise ValueError("Unknown V2 evaluation family")
    if signal_index < REQUIRED_LOOKBACK or signal_index + 2 >= len(panel.sessions):
        raise ValueError("No full future holding period for evaluation")
    if benchmark_symbol is not None and benchmark_symbol not in panel.adjusted_prices:
        raise ValueError("Benchmark price series not in research panel")

    p = panel.adjusted_prices
    t = signal_index
    if benchmark_symbol is not None and (
        p[benchmark_symbol][t + 1] is None
        or p[benchmark_symbol][t + 2] is None
    ):
        raise ValueError(
            "Missing benchmark entry/exit price; cannot invent benchmark return"
        )
    benchmark = (
        p[benchmark_symbol][t + 2] / p[benchmark_symbol][t + 1] - 1.0
        if benchmark_symbol is not None else 0.0
    )

    name = None if family == "CASH" else top_research_candidate(panel, family, t)
    # Research eligibility can change after the signal. At the simulated
    # entry close, a now-disallowed asset is skipped, not magically traded.
    if name is not None and name not in panel.eligible_symbols[t + 1]:
        name = None

    gross = 0.0
    cost = 0.0
    if name is not None:
        # Never treat a delisting/terminal missing price as 0% return
        # or silently switch the researched position into cash. Verified
        # settlement proceeds are a future, separate data requirement.
        if (
            p[name][t + 1] is None
            or p[name][t + 2] is None
            or panel.spread_bps[name][t + 1] is None
            or panel.spread_bps[name][t + 2] is None
        ):
            raise ValueError(
                "Missing hypothetical exit/entry price or spread; "
                "delisting/exit settlement evidence required"
            )
        gross = p[name][t + 2] / p[name][t + 1] - 1.0
        quoted = panel.spread_bps[name]
        round_trip_bps = (
            2.0 * (costs.fee_bps_per_side + costs.slippage_bps_per_side)
            + 0.5 * (quoted[t + 1] + quoted[t + 2])
        )
        cost = round_trip_bps / 10_000.0

    return ResearchOutcome(
        signal_date=panel.sessions[t].isoformat(),
        assumed_entry_date=panel.sessions[t + 1].isoformat(),
        assumed_exit_date=panel.sessions[t + 2].isoformat(),
        family=family,
        hypothetical_symbol=name,
        gross_fraction=gross,
        cost_fraction=cost,
        net_fraction=gross - cost,
        passive_benchmark_fraction=benchmark,
    )


def walk_forward(
    panel: ResearchPanel,
    plan: WalkForwardPlan = WalkForwardPlan(),
    costs: ResearchCosts = ResearchCosts(),
) -> WalkForwardReport:
    """Expanding in-sample choice, disjoint forward test windows.

    Each training decision's t+2 outcome is known strictly before
    the next test signal after an embargo. Previous test outcomes may
    later enter the expanding training set only once resolved.
    """
    if not isinstance(panel, ResearchPanel) or not isinstance(
        plan, WalkForwardPlan
    ) or not isinstance(costs, ResearchCosts):
        raise TypeError("Validated research panel/plan/costs required")

    if (
        plan.benchmark_symbol is not None
        and plan.benchmark_symbol not in panel.adjusted_prices
    ):
        raise ValueError("Benchmark is missing from the research panel")

    first_test = (
        REQUIRED_LOOKBACK + plan.min_train_decisions
        + plan.embargo_sessions + 2
    )
    last_signal = len(panel.sessions) - 3
    if first_test > last_signal:
        raise ValueError("Not enough history for any honest OOS fold")

    outcomes: list[ResearchOutcome] = []
    folds: list[ResearchFold] = []
    test_first = first_test

    while test_first <= last_signal:
        test_last = min(
            test_first + plan.test_decisions_per_fold - 1, last_signal
        )
        last_train_signal = test_first - plan.embargo_sessions - 3
        if last_train_signal < REQUIRED_LOOKBACK:
            raise ValueError("Training outcomes cannot precede history")

        train_results: dict[str, float] = {}
        for family in RESEARCH_FAMILIES:
            training = [
                evaluate_decision(
                    panel, family, i, costs,
                    benchmark_symbol=plan.benchmark_symbol,
                ).net_fraction
                for i in range(REQUIRED_LOOKBACK, last_train_signal + 1)
            ]
            if len(training) < plan.min_train_decisions:
                raise ValueError("Insufficient purged training decisions")
            train_results[family] = _mean(training)

        # A predeclared cash comparator prevents chasing negative IS results.
        best_mean = max(train_results.values())
        chosen = (
            min(family for family, score in train_results.items()
                if score == best_mean)
            if best_mean > 0 else "CASH"
        )
        chosen_mean = max(0.0, best_mean)
        forward = [
            evaluate_decision(
                panel, chosen, i, costs,
                benchmark_symbol=plan.benchmark_symbol,
            )
            for i in range(test_first, test_last + 1)
        ]
        outcomes.extend(forward)
        folds.append(ResearchFold(
            train_last_resolved_date=(
                panel.sessions[last_train_signal + 2].isoformat()
            ),
            test_first_signal_date=panel.sessions[test_first].isoformat(),
            test_last_signal_date=panel.sessions[test_last].isoformat(),
            chosen_family=chosen,
            training_net_mean_fraction=chosen_mean,
            test_net_mean_fraction=_mean([row.net_fraction for row in forward]),
            test_benchmark_mean_fraction=_mean(
                [row.passive_benchmark_fraction for row in forward]
            ),
            test_non_cash_count=sum(
                row.hypothetical_symbol is not None for row in forward
            ),
        ))
        test_first = test_last + 1

    compound = 1.0
    benchmark_compound = 1.0
    for row in outcomes:
        compound *= 1.0 + row.net_fraction
        benchmark_compound *= 1.0 + row.passive_benchmark_fraction

    # This provenance digest intentionally depends on *all* supplied
    # histories; even unused future data changes the dataset fingerprint.
    inputs = {
        "dates": [d.isoformat() for d in panel.sessions],
        "prices": {k: panel.adjusted_prices[k]
                   for k in sorted(panel.adjusted_prices)},
        "spreads": {k: panel.spread_bps[k]
                    for k in sorted(panel.spread_bps)},
        "membership": [sorted(x) for x in panel.eligible_symbols],
        "plan": vars(plan),
        "costs": vars(costs),
        "families": RESEARCH_FAMILIES,
        "folds": [vars(f) for f in folds],
        "outcomes": [vars(o) for o in outcomes],
    }
    digest = sha256(json.dumps(
        inputs, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")).hexdigest()

    return WalkForwardReport(
        folds=tuple(folds),
        out_of_sample=tuple(outcomes),
        total_net_compound_fraction=compound - 1.0,
        benchmark_compound_fraction=benchmark_compound - 1.0,
        mean_net_fraction_per_decision=_mean(
            [row.net_fraction for row in outcomes]
        ),
        mean_benchmark_fraction_per_decision=_mean(
            [row.passive_benchmark_fraction for row in outcomes]
        ),
        audit_sha256=digest,
    )
