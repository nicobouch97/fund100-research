"""No broker, live or private-state operations: fixed historical study regressions."""
import numpy as np
import pandas as pd
import pytest

import fund100_v7_r1_listed_real_assets_v1_0 as r

def fixture():
    days = r.sessions(r.FIRST, r.ASOF)
    i = np.arange(len(days), dtype=float)
    return pd.DataFrame({
        "VNQ": 70 * np.exp(.00029*i + .04*np.sin(i/70)),
        "IGF": 80 * np.exp(.00026*i - .04*np.sin(i/90)),
        "SPY": 100 * np.exp(.00034*i),
        "ACWI": 90 * np.exp(.00027*i),
    }, index=days)

def test_complete_source_and_frozen_eras_no_trade():
    p = fixture()
    out = r.evaluate(p, captured_utc="2026-10-27T09:00:00Z",
                     source_id="YFINANCE_ADJUSTED_ETF_CLOSE_RETRIEVAL_VINTAGE")
    assert out["source_csv_sha256"]
    assert set(out["results"]) == {"5", "15", "35"}
    assert out["fixed_eras"] == ["2013_2016", "2017_2020", "2021_2025"]
    assert out["2026_ytd_excluded_from_verdict"]
    assert out["allocation"].startswith("47.5pct_SPY")
    assert out["broker_gets"] == out["broker_posts"] == out["broker_orders"] == 0
    assert not out["live_authorized"] and not out["trading_authorized"]
    assert out["current_live_cap_usd"] == "130.30"
    for cost in ("5", "15", "35"):
        assert set(out["results"][cost]["eras"]) == set(out["fixed_eras"]) | {
            "2026_YTD_DIAGNOSTIC"}
        assert len(out["results"][cost]["execution"]["decisions"]) > 100

def test_signal_uses_only_preexecution_closes_and_skips_recent_month():
    p = fixture()
    t = int(p.index.get_loc(pd.Timestamp("2021-04-01")))
    before = r.signal(p, t)
    changed = p.copy()
    changed.iloc[t:, changed.columns.get_loc("VNQ")] *= 5
    changed.iloc[t-20:t, changed.columns.get_loc("IGF")] *= 10
    assert r.signal(changed, t) == before
    changed.iloc[t-22, changed.columns.get_loc("VNQ")] *= 1.5
    # The signal is permitted to change ONLY when an included prior bar changes.
    assert r.signal(changed, t) in r.SATELLITES
    with pytest.raises(r.RealAssetStop):
        r.signal(p, 100)

def test_costed_buy_sell_conserves_nav_and_cash_without_leverage():
    p = fixture()
    holdings = {s: 0. for s in r.TICKERS}
    targets = {"SPY": .475, "VNQ": .475, "IGF": 0., "ACWI": 0.}
    for bps in r.COSTS:
        after, cash, fee = r.rebalance(holdings, 100., targets, bps)
        nav = cash + sum(after.values())
        assert nav == pytest.approx(100-fee)
        assert cash == pytest.approx(nav*.05)
        assert after["SPY"] == pytest.approx(nav*.475)
        assert fee > 0
    with pytest.raises(r.RealAssetStop):
        r.rebalance(holdings, 100., {**targets, "VNQ": .9}, 15)

def test_rotation_is_costed_against_same_core_passive_real_assets():
    p = fixture()
    low, lowledger = r.simulate(p, 5)
    high, highledger = r.simulate(p, 35)
    assert low.index.equals(high.index)
    assert low.iloc[0]["rotation"] > high.iloc[0]["rotation"]
    assert low.iloc[-1]["rotation"] > high.iloc[-1]["rotation"]
    assert highledger["costs_per_100_initial_units"]["rotation"] > (
        lowledger["costs_per_100_initial_units"]["rotation"])
    assert highledger["passive_comparators_bought_once"]
    assert lowledger["same_5pct_initial_cash_for_all"]
    assert lowledger["rotation_daily_observations_over_50pct_single_asset"] >= 0
    for d in lowledger["decisions"]:
        assert d["signal_last_used_close"] < d["execution_close"]
        assert d["signal_first_used_close"] < d["signal_last_used_close"]

def test_missing_source_session_nonfinite_or_future_source_fails_closed():
    p = fixture()
    for bad in (p.drop(p.index[400]), p.assign(VNQ=np.nan),
                p.rename(columns={"IGF":"FAKE"})):
        with pytest.raises(r.RealAssetStop):
            r.validate_prices(bad)
    for stamp in ("2026-10-23T12:00:00Z", "2026-11-15T09:00:00Z",
                  "2026-10-27T09:00:00+00:00"):
        with pytest.raises(r.RealAssetStop):
            r.evaluate(p, captured_utc=stamp,
                       source_id="YFINANCE_ADJUSTED_ETF_CLOSE_RETRIEVAL_VINTAGE")
    with pytest.raises(r.RealAssetStop):
        r.evaluate(p, captured_utc="2026-10-27T09:00:00Z", source_id="UNKNOWN")

def test_not_a_self_promoting_research_signal():
    assert r.TRADING_AUTHORIZED is False
    assert (r.BROKER_GETS, r.BROKER_POSTS, r.BROKER_ORDERS) == (0, 0, 0)
    assert r.SATELLITES == ("VNQ", "IGF")
    assert r.ASOF == "2026-10-23"
    assert r.COSTS == (5, 15, 35)
