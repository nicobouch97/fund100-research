"""Offline risk-aware sizing regression; never creates orders."""

from decimal import Decimal

import pytest

from fund100_live_portfolio_risk_v1_0 import PortfolioRiskStop
from fund100_live_risk_sizing_v1_0 import (
    size_strategy_targets, verify_existing_strategy_authorizations,
)

STRATEGY = {
    "ACWI": Decimal(".750782845351"),
    "EEM": Decimal(".083904220419"),
    "XLE": Decimal(".082538899495"),
    "XLV": Decimal(".082774034735"),
}


@pytest.mark.parametrize(
    "level,gross",
    [("LOW", Decimal(".8")), ("MEDIUM", Decimal(".9")),
     ("HIGH", Decimal("1"))],
)
def test_risk_level_scales_gross_and_leaves_cash(level, gross):
    plan = size_strategy_targets(
        strategy_targets=STRATEGY, risk_level=level,
        observed_annualized_volatility=Decimal("0.05"),
    )
    actual = sum(plan.weights.values())
    assert actual <= gross
    assert plan.uninvested_weight == Decimal("1") - actual
    assert all(plan.weights[k] <= STRATEGY[k] for k in STRATEGY)
    assert plan.profile == level


def test_high_risk_keeps_strategy_at_low_vol():
    plan = size_strategy_targets(
        strategy_targets=STRATEGY, risk_level="HIGH",
        observed_annualized_volatility="0.10",
    )
    assert plan.weights == STRATEGY
    assert plan.uninvested_weight == 0


def test_volatility_shrinks_high_risk_exposure():
    plan = size_strategy_targets(
        strategy_targets={"ACWI": ".75", "EEM": ".25"},
        risk_level="HIGH", observed_annualized_volatility=".56",
    )
    assert plan.scale_factor == Decimal(".50")
    assert plan.weights["ACWI"] == Decimal(".375")
    assert plan.uninvested_weight == Decimal(".50")


def test_satellite_concentration_capped_by_common_scale():
    plan = size_strategy_targets(
        strategy_targets={"ACWI": ".55", "XLK": ".45"},
        risk_level="HIGH", observed_annualized_volatility=".10",
    )
    assert plan.weights["XLK"] <= Decimal(".25")
    assert plan.weights["ACWI"] < Decimal(".55")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", None, "oops"])
def test_invalid_observed_volatility_blocks(value):
    with pytest.raises(PortfolioRiskStop):
        size_strategy_targets(
            strategy_targets=STRATEGY, risk_level="HIGH",
            observed_annualized_volatility=value,
        )


def test_no_short_no_unmanaged_symbols():
    with pytest.raises(PortfolioRiskStop):
        size_strategy_targets(
            strategy_targets={"ACWI": ".90", "XLK": "-.1"},
            risk_level="HIGH", observed_annualized_volatility=".10",
        )
    with pytest.raises(PortfolioRiskStop):
        size_strategy_targets(
            strategy_targets={"ACWI": ".90", "XLK": ".2"},
            risk_level="HIGH", observed_annualized_volatility=".10",
        )


def test_signed_candidate_must_cover_risk_adjusted_direction():
    sized = {"ACWI": Decimal(".60")}
    positions = {"ACWI": {"market_value": Decimal("75")}}
    with pytest.raises(PortfolioRiskStop, match="unsigned"):
        verify_existing_strategy_authorizations(
            sized_weights=sized, positions=positions,
            deployable_nav=Decimal("100"), compiler_candidates={},
        )
    with pytest.raises(PortfolioRiskStop, match="unsigned"):
        verify_existing_strategy_authorizations(
            sized_weights=sized, positions=positions,
            deployable_nav=Decimal("100"),
            compiler_candidates={
                "ACWI": {"side": "buy", "client_order_id": "f100-compiled"}
            },
        )
    verify_existing_strategy_authorizations(
        sized_weights=sized, positions=positions,
        deployable_nav=Decimal("100"),
        compiler_candidates={
            "ACWI": {"side": "sell", "client_order_id": "f100-compiled"}
        },
    )
