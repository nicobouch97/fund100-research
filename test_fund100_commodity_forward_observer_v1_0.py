"""Offline deterministic tests of the prospective commodity shadow ledger.

Fixtures are entirely synthetic. This module never downloads data,
reads the real ledger or accesses Alpaca/any brokerage API.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

import fund100_commodity_forward_observer_v1_0 as f


NOW = datetime(2026, 10, 15, 15, 0, tzinfo=timezone.utc)


def fixture(n=950):
    idx = pd.bdate_range("2014-01-02", periods=n)
    t = np.arange(n, dtype=float)
    prices = pd.DataFrame({
        "GLD": 100*np.exp(.00022*t + .009*np.sin(t/23)),
        "DBC": 100*np.exp(.00017*t + .008*np.sin(t/31)),
        "SHY": 100*np.exp(.00008*t),
        "SPY": 100*np.exp(.00033*t + .011*np.sin(t/27)),
    }, index=idx)
    macro = pd.DataFrame({
        "observation_date": idx,
        "available_date": idx + pd.offsets.BDay(2),
        "DFII10": 1.1+.18*np.sin(t/46),
        "T10YIE": 2.0+.12*np.sin(t/39),
        "BAA10Y": 2.4+.20*np.sin(t/48),
    })
    return prices, macro


def new(prices, macro, rows):
    return f.make_record(
        prices=prices, macro=macro, existing=rows,
        observed_at=NOW, github_run_id="12345",
    )


def test_initial_reference_is_not_historical_backfill():
    p, m = fixture()
    a = new(p.iloc[:900], m, [])
    assert a["period_return_observed"] is False
    assert a["shy_nav"] == 100
    assert a["models"]["static"]["nav"] == 100
    assert a["models"]["C1_trend"]["nav"] == 100
    assert a["models"]["C2_regime"]["nav"] == 100
    assert a["model_start_session"] == p.index[899].date().isoformat()
    assert all(a["models"][name]["weights"]["SHY"] == 1.0 for name in f.MODELS)
    assert a["paper_promoted"] is False and a["live_promoted"] is False
    assert a["broker_order_count"] == 0
    assert f.validate_ledger([a]) == [a]


def test_next_session_observed_from_committed_closes_and_chain():
    p, m = fixture()
    a = new(p.iloc[:900], m, [])
    b = new(p.iloc[:901], m, [a])
    assert b["asof_session"] == p.index[900].date().isoformat()
    assert b["period_return_observed"] is True
    assert b["previous_record_sha256"] == a["record_sha256"]
    assert b["models"]["static"]["nav"] > 0
    assert b["shy_nav"] > 100
    assert b["model_start_session"] == a["asof_session"]
    assert f.validate_ledger([a, b]) == [a, b]


def test_replay_is_idempotent_and_not_mutating_prior_state():
    p, m = fixture()
    a = new(p.iloc[:900], m, [])
    prior = deepcopy(a)
    assert new(p.iloc[:900], m, [a]) is None
    assert a == prior


def test_missing_trading_session_fails_no_retroactive_filling():
    p, m = fixture()
    a = new(p.iloc[:900], m, [])
    with pytest.raises(f.ForwardObservationStop, match="Missing intervening"):
        new(p.iloc[:902], m, [a])


def test_new_month_rebalances_static_and_not_intra_month():
    p, m = fixture()
    i = next(k for k in range(850, 900) if p.index[k].month != p.index[k-1].month)
    first = new(p.iloc[:i], m, [])
    second = new(p.iloc[:i+1], m, [first])
    assert second["models"]["static"]["rebalance_one_way_turnover"] > 0
    assert second["models"]["static"]["weights"] == {
        "GLD": 0.2, "DBC": 0.15, "SHY": 0.65
    }
    assert second["models"]["static"]["nav"] < second["shy_nav"]


def test_adjustment_revision_cannot_rewrite_committed_prior_close():
    p, m = fixture()
    a = new(p.iloc[:900], m, [])
    normal = new(p.iloc[:901], m, [a])
    revised = p.iloc[:901].copy()
    revised.iloc[-2, revised.columns.get_loc("GLD")] *= 1.001
    second = new(revised, m, [a])
    assert normal["models"]["C1_trend"]["nav"] == second["models"]["C1_trend"]["nav"]
    assert normal["shy_nav"] == second["shy_nav"]
    assert normal["price_source_sha256"] != second["price_source_sha256"]


def test_hash_chain_refuses_tampered_report():
    p, m = fixture()
    first = new(p.iloc[:900], m, [])
    edited = deepcopy(first)
    edited["models"]["static"]["nav"] = 1000
    with pytest.raises(f.ForwardObservationStop, match="has changed"):
        f.validate_ledger([edited])
    other = new(p.iloc[:901], m, [first])
    other["previous_record_sha256"] = "broken"
    with pytest.raises(f.ForwardObservationStop):
        f.validate_ledger([first, other])


def test_future_session_or_naive_time_fails():
    p, m = fixture()
    with pytest.raises(f.ForwardObservationStop):
        f.make_record(
            prices=p.iloc[:900], macro=m, existing=[],
            observed_at=datetime(2017, 6, 1), github_run_id="99"
        )
    date = p.index[899]
    with pytest.raises(f.ForwardObservationStop, match="may still be open"):
        f.make_record(
            prices=p.iloc[:900], macro=m, existing=[],
            observed_at=date.to_pydatetime().replace(tzinfo=timezone.utc),
            github_run_id="99",
        )


def test_vendor_day_jump_blocks_unreviewed_prospective_accounting():
    p, m = fixture()
    first = new(p.iloc[:900], m, [])
    changed = p.iloc[:901].copy()
    changed.iloc[-1, changed.columns.get_loc("DBC")] *= 1.30
    with pytest.raises(f.ForwardObservationStop, match="Suspicious"):
        new(changed, m, [first])


def test_prospective_risk_fields_frozen_and_no_authorization():
    p, m = fixture()
    a = new(p.iloc[:900], m, [])
    a["trading_authorized"] = True
    a["record_sha256"] = f.sha256({
        k: v for k, v in a.items() if k != "record_sha256"
    })
    with pytest.raises(f.ForwardObservationStop, match="cannot authorize"):
        f.validate_ledger([a])


def test_research_does_not_modify_source_dataframe():
    p, m = fixture()
    prices_original, macro_original = p.copy(), m.copy()
    a = new(p.iloc[:900], m, [])
    new(p.iloc[:901], m, [a])
    pd.testing.assert_frame_equal(p, prices_original)
    pd.testing.assert_frame_equal(m, macro_original)
