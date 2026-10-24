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


def test_complete_costed_stress_report_no_broker():
    result = mod.evaluate(prices(), acquired_at_utc="2025-01-02T12:00:00Z")
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
