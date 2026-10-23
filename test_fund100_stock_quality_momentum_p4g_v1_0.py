"""P4G offline-only synthetic market-price fixtures. Not real returns."""
from __future__ import annotations
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest
import exchange_calendars as xcals

import fund100_stock_quality_momentum_p4g_v1_0 as p4g

CAPTURE = "2026-10-16T03:30:00Z"


def nyse_sessions(end, periods):
    calendar = xcals.get_calendar("XNYS")
    start = pd.Timestamp(end) - pd.Timedelta(days=periods * 3)
    return calendar.sessions_in_range(start, pd.Timestamp(end))[-periods:].tz_localize(None)


def prices():
    idx = nyse_sessions("2026-10-15", 160)
    t = np.arange(len(idx), dtype=float)
    # Completely synthetic deterministic varied positive series.
    growth = {
        "AAPL": .0028, "MSFT": .0020, "GOOGL": .0018,
        "AMZN": .0016, "XOM": -.0012, "JNJ": .0036,
        "PG": .0003, "KO": -.0005, "SPY": .0010, "SHY": .0001,
    }
    return pd.DataFrame(
        {s: 100 * (1.0 + step) ** t for s, step in growth.items()},
        index=idx,
    )


def run(frame=None, acquired=CAPTURE, source="SYNTHETIC-TEST-PRICE-BARS"):
    return p4g.evaluate(prices=prices() if frame is None else frame,
                        acquired_at_utc=acquired, provider_reference=source)


def test_frozen_six_score_context_and_descriptive_momentum_only():
    r=run()
    assert r["asof_completed_session"]=="2026-10-15"
    assert r["quality_known_count"]==6 and r["quality_missing_count"]==2
    assert r["research_watchlist"]==["AAPL","MSFT","GOOGL"]
    assert r["comparison_cohort_equal_weight"]==["AAPL","AMZN","GOOGL","KO","MSFT","PG"]
    assert r["future_performance_observations"]==0
    assert not r["historical_survivorship_delisting_safe"]
    assert r["original_sec_quality_source_manifest_sha256"]==p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256
    assert not r["trading_authorized"] and not r["paper_authorized"]
    assert not r["live_authorized"] and r["broker_orders"]==0


def test_missing_quality_never_upgrades_momentum_winner_to_approved():
    r=run()
    j={x["ticker"]:x for x in r["members"]}
    assert j["JNJ"]["momentum_126_session_return"] > j["AAPL"]["momentum_126_session_return"]
    assert j["JNJ"]["p4e_issuer_quality_score"] is None
    assert j["JNJ"]["qualifies_for_research_watchlist"] is False


def test_refuse_pre_cohort_research_and_same_day_bars():
    f=prices()
    older=f.copy()
    older.index=nyse_sessions("2026-10-14",len(older))
    with pytest.raises(p4g.P4GStop,match="post-freeze"):
        run(older)
    with pytest.raises(p4g.P4GStop,match="post-freeze"):
        run(f,acquired="2026-10-15T21:00:00Z")


def test_refuse_stale_or_future_bar_series():
    with pytest.raises(p4g.P4GStop,match="stale"):
        run(prices(),acquired="2026-10-26T03:30:00Z")
    f=prices()
    f.index=nyse_sessions("2026-10-19",len(f))
    with pytest.raises(p4g.P4GStop):
        run(f)


def test_reject_incorrect_cohort_even_if_prices_seem_reasonable():
    f=prices()
    with pytest.raises(p4g.P4GStop,match="Exactly eight"):
        run(f.drop(columns=["JNJ"]))
    with pytest.raises(p4g.P4GStop,match="Exactly eight"):
        run(f.rename(columns={"AAPL":"TSLA"}))


@pytest.mark.parametrize("which",["nan","zero","negative","infinity","object","huge","jump"])
def test_no_fake_or_unverified_split_adjusted_prices(which):
    f=prices()
    if which=="nan": f.loc[f.index[-5],"AAPL"]=float("nan")
    if which=="zero": f.loc[f.index[-5],"AAPL"]=0
    if which=="negative": f.loc[f.index[-5],"AAPL"]=-2
    if which=="infinity": f.loc[f.index[-5],"AAPL"]=float("inf")
    if which=="object": f["AAPL"]=f["AAPL"].map(str)
    if which=="huge": f.loc[f.index[-5],"AAPL"]=2e6
    if which=="jump": f.loc[f.index[-5],"AAPL"]*=3
    with pytest.raises(p4g.P4GStop):
        run(f)


def test_no_partial_or_short_historical_window():
    with pytest.raises(p4g.P4GStop):
        run(prices().iloc[-126:])
    f=prices()
    f.index=f.index[::-1]
    with pytest.raises(p4g.P4GStop):
        run(f)
    f=prices()
    f.index=pd.DatetimeIndex([f.index[0], *f.index[0:-1]])
    with pytest.raises(p4g.P4GStop):
        run(f)


def test_no_forged_acquisition_time_or_reference():
    for clock in ["2026-10-16", "2026-10-16T03:30:00+00:00", "2026-02-30T10:00:00Z", "junk"]:
        with pytest.raises(p4g.P4GStop):
            run(acquired=clock)
    with pytest.raises(p4g.P4GStop):
        run(source="")


def test_hash_deterministic_and_changes_with_original_bars():
    f=prices()
    before=run(f)
    assert len(before["canonical_price_csv_sha256"])==64
    assert before["canonical_price_csv_sha256"]==run(f)["canonical_price_csv_sha256"]
    change=f.copy()
    change.loc[change.index[-1],"AAPL"]*=1.0001
    after=run(change)
    assert before["canonical_price_csv_sha256"]!=after["canonical_price_csv_sha256"]


def test_empty_research_watchlist_fails_to_cash_rather_than_fabricated_alpha():
    f=prices()
    for s in p4g.FROZEN_P4E_SCORES:
        f[s]=100*(1-.002)**np.arange(len(f))
    r=run(f)
    assert r["research_watchlist"]==[]
    assert r["future_performance_observations"]==0
    assert r["broker_orders"]==0


def test_synthetic_source_not_authenticated_or_future_utility():
    r=run()
    assert not r["original_retrieval_independently_authenticated"]
    assert not r["price_vintages_independently_verified"]
    assert not r["corporate_action_total_return_independently_verified"]
    assert r["unavailable_analyst_revision_feed"] is True
    assert r["source_class"]=="REVISABLE_PUBLIC_YFINANCE_ADJUSTED_CLOSE"


def test_refuse_missing_interior_nyse_session_even_with_sufficient_history():
    f = prices()
    # This used to silently stretch both lookback horizons by one session.
    f = f.drop(index=f.index[-75])
    assert len(f) > p4g.LOOKBACK
    with pytest.raises(p4g.P4GStop, match="Missing or extra XNYS"):
        run(f)


@pytest.mark.parametrize("unexpected", ["2026-10-10", "2026-09-07"])
def test_refuse_extra_weekend_or_exchange_holiday_row(unexpected):
    f = prices()
    # A vendor row on Saturday or Labor Day cannot count as an NYSE session.
    f.loc[pd.Timestamp(unexpected)] = f.iloc[-10]
    f = f.sort_index()
    with pytest.raises(p4g.P4GStop, match="Missing or extra XNYS"):
        run(f)


def test_real_exchange_holidays_are_not_required_as_price_bars():
    f = prices()
    assert pd.Timestamp("2026-09-07") not in f.index
    assert run(f)["price_source_sessions"] == len(f)
