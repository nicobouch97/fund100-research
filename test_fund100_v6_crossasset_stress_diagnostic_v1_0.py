"""Offline deterministic and adversarial cross-asset stress regression."""
import numpy as np
import pandas as pd
import pytest

import fund100_v6_crossasset_stress_diagnostic_v1_0 as mod


def prices():
    dates = pd.bdate_range("2013-12-02", "2024-12-31")
    n = len(dates)
    idx = np.arange(n)
    spy = .0003 + .007 * np.sin(idx * .13)
    spy[np.where(dates == "2020-03-23")[0]] = -.07
    spy[np.where(dates == "2022-10-14")[0]] = -.04
    arr = {}
    for symbol, mult, bias in (("XLK", 1.5, .0001), ("XLE", 1.2, -.0001),
                               ("IWM", 1.1, 0), ("GLD", -.1, .0003),
                               ("SHY", .01, .00002), ("SPY", 1, 0)):
        arr[symbol] = 100 * np.cumprod(1 + mult * spy + bias)
    return pd.DataFrame(arr, index=dates)


def cash_rates():
    dates = pd.date_range("2013-11-01", "2025-01-01", freq="D")
    return pd.DataFrame({"DFF": np.full(len(dates), 5.)}, index=dates)


def test_complete_costed_stress_report_no_broker():
    result = mod.evaluate(prices(), acquired_at_utc="2025-01-02T12:00:00Z",
                          cash_rates=cash_rates())
    assert result["common_sessions"] > 2000
    assert result["costed_historical_diagnostics"]["15"]["S1_95_EQUITY_5_CASH"]["spy_down_2pct_sessions"] == 2
    assert result["broker_requests"] == result["live_orders"] == result["private_state_writes"] == 0
    assert result["costed_historical_diagnostics"]["15"]["MATCHED_75_EQUITY_25_CASH"]["same_session_spy_beta"] < 1
    assert result["shy_is_risky_bond_etf_not_cash"]


def test_no_future_data_leaks_into_prior_daily_nav():
    frame = prices()
    first = mod.simulate(frame, mod.WEIGHTS["S1_95_EQUITY_5_CASH"], 15)["nav"]
    edited = frame.copy()
    edited.loc[edited.index[-1], "XLK"] *= 1.10
    second = mod.simulate(edited, mod.WEIGHTS["S1_95_EQUITY_5_CASH"], 15)["nav"]
    pd.testing.assert_series_equal(first.iloc[:-1], second.iloc[:-1])
    assert first.iloc[-1] != second.iloc[-1]


def test_equal_equity_exposure_controls_and_diversifier_impact():
    a = mod.WEIGHTS["MATCHED_75_EQUITY_25_CASH"]
    b = mod.WEIGHTS["MATCHED_75_EQUITY_10_GOLD_10_SHY_5_CASH"]
    assert a[:3] == b[:3] and sum(a[:3]) == .75
    frame = prices()
    frame["GLD"] = 100 * np.power(1.001, np.arange(len(frame)))
    frame["SHY"] = 100 * np.power(1.0005, np.arange(len(frame)))
    cash = mod.simulate(frame, a, 15)["nav"]
    div = mod.simulate(frame, b, 15)["nav"]
    assert div.iloc[-1] > cash.iloc[-1]


def test_costs_charge_both_sides_and_never_improve_fixed_basket():
    frame = prices()
    for w in mod.WEIGHTS.values():
        lo = mod.simulate(frame, w, 5)
        hi = mod.simulate(frame, w, 35)
        assert hi["nav"].iloc[-1] < lo["nav"].iloc[-1]
        assert hi["turnover"].sum() > sum(w[:-1])


def test_month_end_cash_transfer_is_not_a_second_traded_etf_leg():
    frame = prices()
    frame.loc[:, :] = 100.0
    frame.loc["2014-01-31":, "GLD"] = 110.0
    weights = (0., 0., 0., .5, 0., .5)
    result = mod.simulate(frame, weights, 15)
    # GLD appreciates by 10% while cash is flat; rebalance sells only
    # 0.0238095 of NAV in GLD. The cash receipt is NOT a second ETF sale.
    etf_sale = .55 / 1.05 - .5
    assert result["turnover"].loc["2014-01-31"] == pytest.approx(etf_sale)
    expected = (1 - .0015 * .5) * 1.05 * (1 - .0015 * etf_sale)
    assert result["nav"].loc["2014-01-31"] == pytest.approx(expected)
    assert result["nav"].loc["2014-01-31"] > (1 - .0015 * .5) * 1.05 * (1 - .0015 * 2 * etf_sale)


def test_month_end_etf_to_etf_switch_charges_both_real_security_legs():
    frame = prices()
    frame.loc[:, :] = 100.0
    frame.loc["2014-01-31":, "XLK"] = 110.0
    weights = (.5, .5, 0., 0., 0., 0.)
    result = mod.simulate(frame, weights, 15)
    one_side = .55 / 1.05 - .5
    assert result["turnover"].loc["2014-01-31"] == pytest.approx(2 * one_side)
    assert result["nav"].loc["2014-01-31"] == pytest.approx(
        (1 - .0015) * 1.05 * (1 - .0015 * 2 * one_side))


def test_cost_accounting_version_and_no_trading_authority():
    report = mod.evaluate(prices(), acquired_at_utc="2025-01-02T12:00:00Z",
                          cash_rates=cash_rates())
    assert report["schema"].endswith("_V3")
    assert report["original_zero_cash_baseline_preserved"]
    assert report["cash_rate_source"] == "FRED_DFF_REVISABLE_OVERNIGHT_INTERBANK_PROXY"
    assert report["rebalance_turnover_definition"] == "SUM_ABS_ETF_WEIGHT_CHANGES_EXCLUDING_CASH"
    assert report["prior_c13_v1_cash_leg_cost_overstatement_corrected"]
    assert not report["funded_trading_or_rebalance_authorized"]


def test_cash_carry_raises_cash_control_and_reduces_apparent_diversification_advantage():
    report = mod.evaluate(prices(), acquired_at_utc="2025-01-02T12:00:00Z",
                          cash_rates=cash_rates())
    variants = report["interest_bearing_cash_sensitivity"]["15"]
    control = "MATCHED_75_EQUITY_25_CASH"
    assert (variants["DFF_GROSS"]["by_basket"][control]["net_cagr_pct"]
            > variants["DFF_MINUS_50BP"]["by_basket"][control]["net_cagr_pct"]
            > variants["ZERO"]["by_basket"][control]["net_cagr_pct"])
    assert (variants["DFF_GROSS"]["diversified_minus_cash_control_cagr_pp"]
            < variants["ZERO"]["diversified_minus_cash_control_cagr_pp"])
    assert variants["ZERO"]["by_basket"][control]["net_cagr_pct"] == (
        report["costed_historical_diagnostics"]["15"][control]["net_cagr_pct"])


def test_cash_accrues_weekends_at_prior_lagged_rate_without_lookahead():
    frame = prices()
    rate = pd.Series(5., index=mod.validate_prices(frame).index)
    weights = (0., 0., 0., 0., 0., 1.)
    result = mod.simulate(frame, weights, 15, cash_annual_rate=rate)["nav"]
    assert result.iloc[0] == 1.
    assert result.iloc[1] == pytest.approx(np.exp(.05 / 365.25))
    friday = pd.Timestamp("2014-01-03")
    monday = pd.Timestamp("2014-01-06")
    assert result.loc[monday] / result.loc[friday] == pytest.approx(
        np.exp(.05 * 3 / 365.25))


def test_cash_rate_last_observation_cannot_affect_earlier_results():
    frame = prices()
    original = cash_rates()
    a = mod.evaluate(frame, acquired_at_utc="2025-01-02T12:00:00Z",
                     cash_rates=original)
    changed = original.copy()
    changed.loc["2024-12-31", "DFF"] = 20.
    b = mod.evaluate(frame, acquired_at_utc="2025-01-02T12:00:00Z",
                     cash_rates=changed)
    assert a["interest_bearing_cash_sensitivity"] == b["interest_bearing_cash_sensitivity"]
    assert a["cash_rate_sha256"] != b["cash_rate_sha256"]


@pytest.mark.parametrize("kind", ["duplicate", "missing", "stale", "nonnumeric", "negative"])
def test_reject_bad_cash_rate_source(kind):
    raw = cash_rates()
    if kind == "duplicate":
        raw = pd.concat([raw, raw.iloc[[-1]]])
    elif kind == "missing":
        raw.loc["2024-06-01", "DFF"] = np.nan
    elif kind == "stale":
        raw = raw.loc[:"2024-11-01"]
    elif kind == "nonnumeric":
        raw["DFF"] = "invalid"
    else:
        raw.loc["2024-06-01", "DFF"] = -1.
    with pytest.raises(mod.CrossAssetStop):
        mod.validate_cash_rates(raw, mod.validate_prices(prices()).index)


@pytest.mark.parametrize("corruption", ["duplicate", "missing", "gap", "future", "nonnumeric"])
def test_reject_invalid_source(corruption):
    frame = prices()
    if corruption == "duplicate":
        frame = pd.concat([frame, frame.iloc[[-1]]])
    elif corruption == "missing":
        frame.iloc[200, 1] = np.nan
    elif corruption == "gap":
        frame.iloc[200, 1] *= 2
    elif corruption == "future":
        with pytest.raises(mod.CrossAssetStop, match="incomplete"):
            mod.evaluate(frame, acquired_at_utc="2024-01-01T00:00:00Z")
        return
    else:
        frame["SHY"] = "oops"
    with pytest.raises(mod.CrossAssetStop):
        mod.validate_prices(frame)


def test_no_trade_imports_or_live_policy_changes():
    from pathlib import Path
    src = Path(mod.__file__).read_text()
    for term in ("alpaca", "api.alpaca.markets", "/v2/orders", "requests.post(",
                 "urlopen(", "FUND100_PRIVATE_STATE", "FUND100_LIVE_KEY"):
        assert term not in src.lower() if term == "alpaca" else term not in src
    assert mod.NO_BROKER_OR_PRIVATE_STATE_ACCESS and mod.NO_LIVE_OR_PAPER_AUTHORITY
    assert mod.WEIGHTS["S1_95_EQUITY_5_CASH"] == (.475, .285, .19, 0., 0., .05)
