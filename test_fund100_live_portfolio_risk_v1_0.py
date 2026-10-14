"""Pure offline risk-profile tests; no broker or GitHub credentials."""

from decimal import Decimal

import pytest

import fund100_live_portfolio_risk_v1_0 as r


def history(values=None):
    if values is None:
        values = [100, 101, 100.5, 101.5, 102, 101.5, 102]
    return {
        "timeframe": "1D",
        "timestamp": [1700000000 + 86400 * i for i in range(len(values))],
        "equity": values,
    }


def sample_snapshot():
    return {
        "account": {"equity": "102", "last_equity": "101.5"},
        "equity": Decimal("102"),
        "positions": {
            "ACWI": {"market_value": Decimal("76")},
            "EEM": {"market_value": Decimal("8.2")},
            "XLE": {"market_value": Decimal("8.0")},
            "XLV": {"market_value": Decimal("8.0")},
        },
    }


def sample_targets():
    return {"ACWI": Decimal(".75"), "EEM": Decimal(".083"),
            "XLE": Decimal(".083"), "XLV": Decimal(".084")}


def test_high_risk_pilot_allocation_accepted():
    r.check_portfolio_risk(
        snapshot=sample_snapshot(), target_weights=sample_targets(),
        capital_ceiling="130.30", history=history(), level="HIGH"
    )


@pytest.mark.parametrize("level", ["LOW", "MEDIUM"])
def test_lower_risk_levels_enforce_total_exposure(level):
    with pytest.raises(r.PortfolioRiskStop):
        r.check_projected_allocation(
            target_weights=sample_targets(), profile=r.get_profile(level)
        )


def test_high_tier_still_limits_satellite_concentration():
    with pytest.raises(r.PortfolioRiskStop, match="concentration"):
        r.check_projected_allocation(
            target_weights={"ACWI": ".70", "XLK": ".30"},
            profile=r.get_profile("HIGH"),
        )


def test_core_acwi_exception_but_not_unlimited():
    r.check_projected_allocation(
        target_weights={"ACWI": ".75", "XLE": ".08"},
        profile=r.get_profile("HIGH"),
    )
    with pytest.raises(r.PortfolioRiskStop):
        r.check_projected_allocation(
            target_weights={"ACWI": ".81"}, profile=r.get_profile("HIGH")
        )


def test_existing_portfolio_exposure_and_concentration_enforced():
    snap = sample_snapshot()
    snap["positions"]["XLV"]["market_value"] = Decimal("35")
    with pytest.raises(r.PortfolioRiskStop):
        r.check_actual_exposure(
            positions=snap["positions"], equity=snap["equity"],
            capital_ceiling="130.30", profile=r.get_profile("HIGH")
        )


def test_daily_loss_stops_high_tier_at_seven_percent():
    with pytest.raises(r.PortfolioRiskStop, match="daily-loss"):
        r.check_account_performance(
            account={"equity": 93, "last_equity": 100},
            history=history([96, 95, 94, 94, 93.5, 93.5]),
            profile=r.get_profile("HIGH"),
        )


def test_rolling_drawdown_stops_even_if_daily_loss_small():
    with pytest.raises(r.PortfolioRiskStop, match="drawdown"):
        r.check_account_performance(
            account={"equity": "79", "last_equity": "79.5"},
            history=history([100, 95, 91, 87, 84, 80]),
            profile=r.get_profile("HIGH"),
        )


def test_volatility_guard_stops_unstable_portfolio():
    with pytest.raises(r.PortfolioRiskStop, match="volatility"):
        r.check_account_performance(
            account={"equity": 100, "last_equity": 99},
            history=history([100, 110, 100, 110, 100, 100]),
            profile=r.get_profile("HIGH"),
        )


@pytest.mark.parametrize("level", ["unknown", "OFF", "", None, 2])
def test_risk_tier_fail_closed(level):
    with pytest.raises(r.PortfolioRiskStop):
        r.get_profile(level)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1"])
def test_invalid_or_negative_market_value_denied(bad):
    with pytest.raises(r.PortfolioRiskStop):
        r.check_actual_exposure(
            positions={"ACWI": {"market_value": bad}},
            equity="100", capital_ceiling="130.30",
            profile=r.get_profile("HIGH"),
        )


def test_missing_history_blocks_trading():
    with pytest.raises(r.PortfolioRiskStop, match="Insufficient"):
        r.check_account_performance(
            account={"equity": 100, "last_equity": 100},
            history=history([100, 100]), profile=r.get_profile("HIGH"),
        )


def test_broker_history_shape_and_order_checked():
    for bad in [
        {"timeframe": "1Min", "timestamp": [1] * 6, "equity": [100] * 6},
        {"timeframe": "1D", "timestamp": [1] * 6, "equity": [100] * 6},
        {"timeframe": "1D", "timestamp": list(range(1, 7)), "equity": [100, None] * 3},
    ]:
        with pytest.raises(r.PortfolioRiskStop):
            r.validated_equity_history(bad)


def test_no_persisted_account_values_in_portfolio_risk_contract():
    assert r.get_profile("HIGH").max_rolling_drawdown == Decimal(".200")
    assert r.get_profile("HIGH").max_realized_volatility == Decimal(".35")
