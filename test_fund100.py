import pandas as pd

from fund100 import (
    capped_proportional_weights,
    apply_trade_threshold,
)


def test_weight_cap_is_respected():

    raw = pd.Series({
        "A": 10.0,
        "B": 2.0,
        "C": 1.0,
        "D": 1.0,
        "E": 1.0,
    })

    weights = (
        capped_proportional_weights(
            raw_scores=raw,
            gross_target=1.0,
            maximum_weight=0.25,
        )
    )

    assert (
        weights.max()
        <= 0.2500001
    )

    assert (
        weights.sum()
        <= 1.0000001
    )


def test_three_assets_cannot_exceed_75_percent():

    raw = pd.Series({
        "A": 1.0,
        "B": 1.0,
        "C": 1.0,
    })

    weights = (
        capped_proportional_weights(
            raw_scores=raw,
            gross_target=1.0,
            maximum_weight=0.25,
        )
    )

    assert abs(
        weights.sum()
        - 0.75
    ) < 1e-9


def test_small_rebalance_is_suppressed():

    current = pd.Series({
        "A": 0.20,
        "B": 0.20,
    })

    desired = pd.Series({
        "A": 0.22,
        "B": 0.18,
    })

    result = (
        apply_trade_threshold(
            current=current,
            desired=desired,
            minimum_trade=0.05,
            maximum_weight=0.25,
            maximum_gross=1.0,
        )
    )

    assert (
        result["A"] == 0.20
    )

    assert (
        result["B"] == 0.20
    )


def test_exit_is_never_blocked_by_trade_threshold():

    current = pd.Series({
        "A": 0.03,
        "B": 0.20,
    })

    desired = pd.Series({
        "A": 0.00,
        "B": 0.20,
    })

    result = (
        apply_trade_threshold(
            current=current,
            desired=desired,
            minimum_trade=0.05,
            maximum_weight=0.25,
            maximum_gross=1.0,
        )
    )

    assert (
        result["A"] == 0.0
    )


def test_panic_gross_limit_overrides_threshold():

    current = pd.Series({
        "A": 0.25,
        "B": 0.25,
        "C": 0.20,
    })

    desired = current.copy()

    result = (
        apply_trade_threshold(
            current=current,
            desired=desired,
            minimum_trade=0.05,
            maximum_weight=0.25,
            maximum_gross=0.50,
        )
    )

    assert (
        result.sum()
        <= 0.5000001
    )


def test_no_negative_long_only_weights():

    raw = pd.Series({
        "A": 3.0,
        "B": 2.0,
        "C": 1.0,
        "D": 0.5,
    })

    weights = (
        capped_proportional_weights(
            raw_scores=raw,
            gross_target=1.0,
            maximum_weight=0.25,
        )
    )

    assert (
        weights >= 0.0
    ).all()
