"""One genuinely later-vintage frozen selection vs cost-matched SPY (fixtures)."""
from copy import deepcopy
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import pytest
import exchange_calendars as xcals

import fund100_stock_broad_momentum_p4l_v1_0 as p4l
import fund100_v7_m1_original_24stock_momentum_forward_v1_0 as m

def price_panel(end):
    days=xcals.get_calendar("XNYS").sessions_in_range(
        pd.Timestamp("2025-10-01"),pd.Timestamp(end)
    ).tz_localize(None).normalize()
    t=np.arange(len(days),dtype=float)
    rows={}
    for i,s in enumerate(sorted(p4l.SECTORS)):
        rows[s]=100.*(1+.0001+.00008*i)**t
    rows[p4l.BENCHMARK]=100.*(1+.00018)**t
    rows[p4l.CASH_REFERENCE]=100.*(1+.00005)**t
    return pd.DataFrame(rows,index=days)

def fixtures(end,capture=None):
    first=price_panel("2026-10-23")
    base=p4l.evaluate(first,acquired_at_utc="2026-10-26T17:28:44Z",
                      provider_reference="original captured static upstream")
    later=price_panel(end)
    stamp=capture or (pd.Timestamp(end)+pd.Timedelta(days=1)).strftime("%Y-%m-%dT09:30:00Z")
    # On Fri end, next Saturday acquisition is permitted. This is a
    # data-vintage timestamp, never an order time.
    return base,first,later,stamp

def run(end,capture=None):
    original,first,later,ts=fixtures(end,capture)
    return m.evaluate(original_manifest=original,original_prices=first,
                      later_prices=later,captured_utc=ts)

def test_original_frozen_selection_gives_no_same_day_hindsight():
    r=run("2026-10-26",capture="2026-10-27T09:30:00Z")
    assert r["status"]=="WAITING_FOR_FROZEN_ENTRY_CLOSE"
    assert r["observed_holding_intervals"]==0
    assert not r["costed_95pct_stocks_versus_95pct_spy"]
    assert r["frozen_entry_close_session"]=="2026-10-27"
    assert r["original_fixed_run_id"]==40368883430
    assert not r["trading_authorized"]

def test_first_true_interim_bar_has_zero_full_period_alpha_claim():
    r=run("2026-10-28",capture="2026-10-29T09:30:00Z")
    assert r["status"]=="INTERIM_FOR_INFORMATION_NOT_QUALIFICATION"
    assert r["observed_holding_intervals"]==1
    assert r["final_result_completed"] is False
    assert r["signal_predictive_alpha_proven"] is False
    assert set(r["costed_95pct_stocks_versus_95pct_spy"])=={"5","15","35"}

def test_prespecified_final_price_is_not_extended_to_later_winning_date():
    exit_=m._calendar(m.ENTRY_SESSION,"2026-12-15")[m.HOLD_SESSIONS]
    fixed=run(exit_.date().isoformat())
    later=run((exit_+pd.Timedelta(days=8)).date().isoformat())
    assert fixed["status"]=="COMPLETED_FROZEN_21_SESSION_FORWARD_MARK_NOT_ALPHA"
    assert fixed["observed_holding_intervals"]==21
    assert later["observed_holding_intervals"]==21
    assert later["costed_95pct_stocks_versus_95pct_spy"]==fixed["costed_95pct_stocks_versus_95pct_spy"]
    assert fixed["broker_gets"]==fixed["broker_posts"]==fixed["broker_orders"]==0
    assert fixed["eligible_to_rank_real_live_orders"] is False

def test_source_tampering_or_backdated_acquisition_cannot_change_winners():
    original,first,later,ts=fixtures("2026-10-28")
    original["momentum_only_watchlist"]=list(reversed(original["momentum_only_watchlist"]))
    with pytest.raises(m.ForwardStop):
        m.evaluate(original_manifest=original,original_prices=first,
                   later_prices=later,captured_utc=ts)
    original,first,later,ts=fixtures("2026-10-28")
    first.loc[first.index[0],"AAPL"]*=1.001
    with pytest.raises(m.ForwardStop):
        m.evaluate(original_manifest=original,original_prices=first,
                   later_prices=later,captured_utc=ts)
    original,first,later,ts=fixtures("2026-10-28")
    original["source_acquired_at_utc"]="2026-10-28T17:28:44Z"
    with pytest.raises(m.ForwardStop):
        m.evaluate(original_manifest=original,original_prices=first,
                   later_prices=later,captured_utc=ts)

def test_missing_interior_nyse_bar_does_not_imply_shorter_interval():
    original,first,later,ts=fixtures("2026-11-03")
    later=later.drop(pd.Timestamp("2026-10-29"))
    with pytest.raises(m.ForwardStop):
        m.evaluate(original_manifest=original,original_prices=first,
                   later_prices=later,captured_utc=ts)

def test_incomplete_or_stale_forward_price_receipts_fail_closed():
    original,first,later,ts=fixtures("2026-10-28")
    for stamp in ("2026-10-28T10:00:00Z","2026-11-15T10:00:00Z","2026-10-25T09:00:00Z"):
        with pytest.raises(m.ForwardStop):
            m.evaluate(original_manifest=original,original_prices=first,
                       later_prices=later,captured_utc=stamp)

def test_comparator_same_cash_fees_and_permanently_research_only():
    r=run("2026-10-28",capture="2026-10-29T09:30:00Z")
    for cost in ("5","15","35"):
        item=r["costed_95pct_stocks_versus_95pct_spy"][cost]
        assert item["equal_95pct_initial_cash_and_round_trip_costs"]
        assert item["entry_purchase_cost_usd"]>0
        assert item["final_risky_exit_is_modeled_only"]
    assert r["not_a_survivorship_safe_universe"]
    assert not r["stock_total_returns_or_tradable_fills_verified"]
