"""P4L deterministic broad-stock research-only source tests."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_stock_quality_momentum_p4g_v1_0 as p4g


def prices():
    idx = pd.bdate_range(end="2026-10-23", periods=150)
    t = np.arange(len(idx), dtype=float)
    data = {symbol: 100 * np.power(1.0005, t)
            for symbol in p4l.SECTORS}
    data["SPY"] = 100 * np.power(1.0002, t)
    data["SHY"] = 100 * np.power(1.00005, t)
    return pd.DataFrame(data, index=idx)


def evaluate(p):
    return p4l.evaluate(
        p, acquired_at_utc="2026-10-24T04:00:00Z",
        provider_reference="Synthetic fixture only, never original market data",
    )


def test_broad_roster_includes_original_eight_but_does_not_modify_p4g():
    assert len(p4l.SECTORS) == 24
    assert set(p4g.FROZEN_P4E_SCORES) < set(p4l.SECTORS)
    assert p4l.MAX_NAMES == 6 and p4l.MAX_PER_SECTOR == 2
    assert p4l.COHORT_START.isoformat() == "2026-10-24"


def test_current_momentum_snapshot_uses_broad_roster_and_sector_cap():
    p = prices()
    report = evaluate(p)
    assert report["cohort_size"] == 24
    assert len(report["members"]) == 24
    assert report["asof_completed_session"] == "2026-10-23"
    assert len(report["momentum_only_watchlist"]) == 6
    sectors = [p4l.SECTORS[s] for s in report["momentum_only_watchlist"]]
    assert max(sectors.count(s) for s in sectors) <= 2
    assert report["post_selection_forward_return_observations"] == 0
    assert not report["historical_stock_alpha_backtest_eligible"]
    assert not report["paper_authorized"] and not report["live_authorized"]
    assert report["broker_orders"] == 0


def test_stronger_relative_momentum_changes_rank_not_original_history():
    p = prices()
    p["NVDA"] = 100 * np.power(1.002, np.arange(len(p)))
    p["AVGO"] = 100 * np.power(1.0019, np.arange(len(p)))
    p["MSFT"] = 100 * np.power(1.0018, np.arange(len(p)))
    r = evaluate(p)
    assert r["momentum_only_watchlist"][:2] == ["NVDA", "AVGO"]
    assert "MSFT" not in r["momentum_only_watchlist"]  # third Technology name
    assert all(not x["current_fundamental_quality_independently_verified"]
               for x in r["members"])


def test_price_source_hash_is_stable_and_rejects_corrupt_bars():
    p = prices()
    r = evaluate(p)
    assert r["canonical_price_csv_sha256"] == evaluate(p[p.columns[::-1]])[
        "canonical_price_csv_sha256"
    ]
    q = p.copy()
    q.loc[q.index[-1], "NVDA"] = np.nan
    with pytest.raises(p4l.BroadStockStop, match="Missing"):
        evaluate(q)
    q = p.copy()
    q.loc[q.index[-1], "NVDA"] *= 2
    with pytest.raises(p4l.BroadStockStop, match="discontinuity"):
        evaluate(q)
    with pytest.raises(p4l.BroadStockStop, match="Exactly 24"):
        evaluate(p.drop(columns="NVDA"))


def test_future_or_stale_market_snapshot_rejected():
    p = prices()
    with pytest.raises(p4l.BroadStockStop, match="post-cohort"):
        p4l.evaluate(p, acquired_at_utc="2026-10-23T04:00:00Z",
                     provider_reference="Synthetic fixture")
    with pytest.raises(p4l.BroadStockStop, match="post-cohort"):
        p4l.evaluate(p, acquired_at_utc="2026-11-02T04:00:00Z",
                     provider_reference="Synthetic fixture")
    with pytest.raises(p4l.BroadStockStop, match="Canonical"):
        p4l.evaluate(p, acquired_at_utc="bad-date",
                     provider_reference="Synthetic fixture")


def test_future_price_revisions_cannot_rewrite_previous_frozen_snapshot():
    p = prices()
    original = evaluate(p)
    q = p.copy()
    q.loc[q.index[-1], "NVDA"] *= 1.05
    changed = evaluate(q)
    assert original["canonical_price_csv_sha256"] != changed["canonical_price_csv_sha256"]
    assert original["source_acquired_at_utc"] == changed["source_acquired_at_utc"]
    assert not changed["price_source_vintages_independently_authenticated"]
    assert not changed["company_delistings_and_corporate_actions_independently_verified"]


def _vendor_batch(p):
    """Yahoo's documented two-level Close/ticker output shape."""
    return pd.concat({"Close": p}, axis=1)


def test_transient_missing_price_retries_whole_source_batch(monkeypatch):
    import sys
    from types import SimpleNamespace

    complete = prices()
    incomplete = complete.copy()
    incomplete.loc[incomplete.index[-2], "NVDA"] = np.nan
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        return _vendor_batch(incomplete if len(calls) == 1 else complete)

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=download))
    monkeypatch.setattr(p4l, "sleep", lambda _: None)
    monkeypatch.setattr(p4g, "verify_original_nyse_source_sessions", lambda _: None)
    result = p4l.public_prices()
    assert len(calls) == 2
    assert all(call["tickers"] == sorted(set(p4l.SECTORS) | {"SPY", "SHY"})
               for call in calls)
    pd.testing.assert_frame_equal(result, p4l.validate_prices(complete))


def test_persistently_incomplete_vendor_batches_never_publish(monkeypatch):
    import sys
    from types import SimpleNamespace

    incomplete = prices()
    incomplete.loc[incomplete.index[-2], "NVDA"] = np.nan
    calls = []

    def download(**kwargs):
        calls.append(kwargs)
        return _vendor_batch(incomplete)

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=download))
    monkeypatch.setattr(p4l, "sleep", lambda _: None)
    monkeypatch.setattr(p4g, "verify_original_nyse_source_sessions", lambda _: None)
    with pytest.raises(p4l.BroadStockStop, match="No complete original 26-symbol.*Missing"):
        p4l.public_prices()
    assert len(calls) == p4l.SOURCE_ATTEMPTS == 3


def test_valid_original_batch_does_not_retry(monkeypatch):
    import sys
    from types import SimpleNamespace

    calls = []
    def download(**kwargs):
        calls.append(kwargs)
        return _vendor_batch(prices())

    monkeypatch.setitem(sys.modules, "yfinance", SimpleNamespace(download=download))
    monkeypatch.setattr(p4g, "verify_original_nyse_source_sessions", lambda _: None)
    assert len(p4l.public_prices()) == len(prices())
    assert len(calls) == 1
