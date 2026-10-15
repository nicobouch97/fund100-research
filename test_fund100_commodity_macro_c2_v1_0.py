"""C2 commodity macro hypothesis tests: invented data only, NOT returns."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fund100_commodity_macro_c2_v1_0 as c2
import fund100_commodity_macro_c2_source_v1_0 as source


def fixture(n=900):
    date = pd.bdate_range("2014-01-02", periods=n)
    t = np.arange(n, dtype=float)
    prices = pd.DataFrame({
        "GLD": 100*np.exp(.00020*t + .009*np.sin(t/25)),
        "DBC": 100*np.exp(.00016*t + .019*np.sin(t/32)),
        "SHY": 100*np.exp(.00008*t),
        "SPY": 100*np.exp(.00027*t + .011*np.sin(t/21)),
    }, index=date)
    macro = pd.DataFrame({
        "observation_date": date,
        "available_date": date + pd.offsets.BDay(2),
        "DFII10": 1.10+.25*np.sin(t/33),
        "T10YIE": 2.00+.22*np.sin(t/46),
        "BAA10Y": 2.40+.30*np.sin(t/42),
    })
    return prices, macro


def test_research_contract_never_allows_broker_or_live():
    prices, macro = fixture()
    report = c2.analyze(prices, macro)
    assert report["status"] == "EXPLORATORY_HISTORICAL_ONLY_NO_PROMOTION"
    assert report["paper_authorized"] is False
    assert report["live_authorized"] is False
    assert report["broker_orders"] == 0
    assert report["historical_vintage_authentication_established"] is False
    assert report["holdout_is_independent"] is False
    assert report["futures_term_structure_or_carry_observed"] is False
    assert set(report["results"]) == {"5", "15", "35"}
    assert report["rules"]["gold_base"] == 0.10


def test_asof_never_uses_publication_after_prior_market_close():
    prices, macro = fixture()
    table = c2.asof_available(prices, macro)
    assert pd.isna(table.iloc[0]["available_date"])
    for t in (10, 70, 400, 800):
        row = table.iloc[t]
        assert row["available_date"] <= prices.index[t-1]
        assert row["observation_date"] <= row["available_date"]


def test_future_prices_and_macro_do_not_change_current_reference_weights():
    prices, macro = fixture()
    t = 420
    first = c2.reference_weights(prices, c2.asof_available(prices, macro), t)
    different_prices = prices.copy()
    different_prices.loc[prices.index[t]:, "DBC"] *= 1.2
    different_prices.loc[prices.index[t]:, "GLD"] *= .8
    changed = macro.copy()
    changed.loc[changed["observation_date"] >= prices.index[t], "DFII10"] = 5.0
    second = c2.reference_weights(
        different_prices, c2.asof_available(different_prices, changed), t
    )
    assert first == second


def test_glass_box_macro_regime_decisions_differ_by_commodity_type():
    prices, macro = fixture()
    known = c2.asof_available(prices, macro)
    t = 320
    prev = t - c2.MACRO_WINDOW_SESSIONS
    # Construct a positive real-yield fall and a separate inflation-breakeven
    # rise without using raw future data.
    old = known.iloc[prev].copy()
    cur = known.iloc[t].copy()
    known.loc[known.index[prev], "DFII10"] = 1.4
    known.loc[known.index[t], "DFII10"] = 1.1
    known.loc[known.index[prev], "BAA10Y"] = 2.5
    known.loc[known.index[t], "BAA10Y"] = 2.5
    known.loc[known.index[prev], "T10YIE"] = 2.0
    known.loc[known.index[t], "T10YIE"] = 2.2
    w = c2.reference_weights(prices, known, t)
    assert w["GLD"] == 0.2
    assert w["DBC"] in (0.0, 0.15)
    assert abs(sum(w.values())-1) < 1e-10


def test_credit_stress_pauses_futures_linked_dbc_even_on_inflation():
    prices, macro = fixture()
    known = c2.asof_available(prices, macro)
    t = 350
    prev = t-c2.MACRO_WINDOW_SESSIONS
    known.loc[known.index[prev], ["DFII10", "T10YIE", "BAA10Y"]] = [1.5, 2.0, 2.0]
    known.loc[known.index[t], ["DFII10", "T10YIE", "BAA10Y"]] = [1.2, 2.3, 2.4]
    w = c2.reference_weights(prices, known, t)
    assert w == {"GLD": 0.2, "DBC": 0.0, "SHY": 0.8}


def test_stale_or_unavailable_macro_defaults_to_permanent_gold_only():
    prices, macro = fixture()
    outdated = macro.iloc[:250]
    known = c2.asof_available(prices, outdated)
    w = c2.reference_weights(prices, known, 450)
    assert w == {"GLD": 0.1, "DBC": 0.0, "SHY": 0.9}


def test_missing_and_impossible_macro_values_stop():
    _, macro = fixture()
    for alter in (
        lambda x: x.drop(columns=["DFII10"]),
        lambda x: x.assign(BAA10Y=np.nan),
        lambda x: x.assign(DFII10=26.0),
        lambda x: x.assign(BAA10Y=-1.0),
        lambda x: x.iloc[::-1],
        lambda x: pd.concat([x, x.iloc[-1:]], ignore_index=True),
    ):
        with pytest.raises(c2.CommodityRegimeStop):
            c2.validate_macro(alter(macro))
    x = macro.copy()
    x.loc[1, "available_date"] = x.loc[1, "observation_date"] - pd.Timedelta(days=1)
    with pytest.raises(c2.CommodityRegimeStop):
        c2.validate_macro(x)


def test_monthly_rebalance_unlevered_research_targets_and_positive_nav():
    prices, macro = fixture()
    r = c2.backtest(prices, macro, cost_bps=15)
    assert np.allclose(r.close_weights.sum(axis=1), 1.0)
    assert (r.close_weights >= 0).all().all()
    dates = [prices.index[i] for i in range(1, len(prices))
             if prices.index[i-1].month != prices.index[i].month]
    targets = r.close_weights.loc[dates]
    assert (targets["GLD"] >= .10-1e-10).all()
    assert (targets["GLD"] <= .20+1e-10).all()
    assert (targets["DBC"] <= .15+1e-10).all()
    assert (targets["SHY"] >= .65-1e-10).all()
    assert (r.nav > 0).all()


def test_higher_trading_cost_lowers_net_value_no_double_roll_penalty():
    prices, macro = fixture()
    lo = c2.backtest(prices, macro, 5)
    hi = c2.backtest(prices, macro, 35)
    assert lo.nav.iloc[-1] >= hi.nav.iloc[-1]
    assert lo.turnover.equals(hi.turnover)
    assert lo.spy.equals(hi.spy)
    assert lo.shy.equals(hi.shy)


def test_public_source_rejects_unapproved_series_and_missing_publish_dates():
    with pytest.raises(c2.CommodityRegimeStop):
        source.parse_public_fred(b"DATE,DFII10\n2020-01-01,1.2\n", "DOGE")
    with pytest.raises(c2.CommodityRegimeStop):
        source.parse_public_fred(b"DATE,NONMATCH\n2020-01-01,1.2\n", "DFII10")
    with pytest.raises(c2.CommodityRegimeStop):
        source.fetch_public("BTCCAD")


def test_public_history_assumes_delay_not_true_vintage():
    prices, _ = fixture()
    series = {s: pd.Series(1.2 if s != "BAA10Y" else 2.2,
                           index=prices.index) for s in c2.MACRO_COLUMNS}
    result = source.combine_public_history(
        series, end_exclusive="2028-01-01"
    )
    assert (result["available_date"] > result["observation_date"]).all()
    assert c2.AVAILABILITY_CLAIM == "ASSUMED_TWO_WEEKDAYS_NOT_VERIFIED_POINT_IN_TIME"


def test_research_inputs_never_mutated_by_backtest():
    prices, macro = fixture()
    p, m = prices.copy(), macro.copy()
    c2.backtest(prices, macro, 5)
    pd.testing.assert_frame_equal(prices, p)
    pd.testing.assert_frame_equal(macro, m)


def test_sha_changes_with_source_and_cannot_claim_realtime():
    _, macro = fixture()
    original = c2.macro_hash(macro)
    changed = macro.copy()
    changed.loc[70, "BAA10Y"] += .015
    assert c2.macro_hash(changed) != original
    assert c2.AVAILABILITY_CLAIM.endswith("NOT_VERIFIED_POINT_IN_TIME")
