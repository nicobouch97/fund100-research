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


def test_preentry_volatility_match_never_levers_or_changes_original_selection():
    original,first,later,ts=fixtures("2026-10-28")
    # Add a smooth nonconstant return pattern in the original source
    # and regenerate the pinned source receipt, BEFORE the fixed entry.
    days=np.arange(len(first),dtype=float)
    for symbol in first.columns:
        first[symbol]*=np.exp(.0015*np.sin(days/8. + len(symbol)))
    original=p4l.evaluate(first,acquired_at_utc=original["source_acquired_at_utc"],
                          provider_reference=original["source_reference"])
    result=m.evaluate(original_manifest=original,original_prices=first,
                      later_prices=later,captured_utc=ts)
    risk=result["secondary_frozen_preentry_volatility_match"]
    assert risk["status"]=="PREENTRY_RISK_MATCHED_NO_LEVERAGE_RESEARCH_ONLY"
    assert risk["pinned_through"]=="2026-10-23"
    assert risk["lookback_completed_returns"]==126
    assert 0<risk["stock_risky_fraction"]<=.95
    assert 0<risk["spy_risky_fraction"]<=.95
    assert max(risk["stock_risky_fraction"],risk["spy_risky_fraction"])==.95
    assert abs(risk["stock_risky_weight_times_volatility"]-
               risk["spy_risky_weight_times_volatility"])<1e-10
    assert result["original_pretrade_selection"]==original["momentum_only_watchlist"]
    for bps in ("5","15","35"):
        item=result["costed_95pct_stocks_versus_95pct_spy"][bps]
        matched=item["secondary_preentry_volatility_matched"]
        fee=int(bps)/10000
        entry=later.loc["2026-10-27"]
        end=later.loc["2026-10-28"]
        growth=np.mean([end[s]/entry[s] for s in result["original_pretrade_selection"]])
        sw=risk["stock_risky_fraction"]
        expected=100*(1-sw)+100*sw/(1+fee)*growth*(1-fee)
        assert matched["stock_final_after_costs_usd"]==pytest.approx(expected,abs=1e-8)
        assert item["equal_95pct_initial_cash_and_round_trip_costs"]
        assert matched["preentry_only_no_future_risk_fit"]


def test_preentry_risk_is_frozen_even_if_later_returns_change():
    original,first,later,ts=fixtures("2026-10-28")
    days=np.arange(len(first),dtype=float)
    for symbol in first.columns:
        first[symbol]*=np.exp(.001*np.sin(days/7. + len(symbol)))
    original=p4l.evaluate(first,acquired_at_utc=original["source_acquired_at_utc"],
                          provider_reference=original["source_reference"])
    before=m.evaluate(original_manifest=original,original_prices=first,
                      later_prices=later,captured_utc=ts)
    later=later.copy()
    later.loc["2026-10-28","SPY"]*=1.1
    after=m.evaluate(original_manifest=original,original_prices=first,
                     later_prices=later,captured_utc=ts)
    assert (before["secondary_frozen_preentry_volatility_match"]==
            after["secondary_frozen_preentry_volatility_match"])
    assert (before["costed_95pct_stocks_versus_95pct_spy"]["15"]
            ["stock_minus_spy_net_percentage_points"] !=
            after["costed_95pct_stocks_versus_95pct_spy"]["15"]
            ["stock_minus_spy_net_percentage_points"])


def test_flat_preentry_risk_does_not_fabricate_risk_matched_alpha():
    original,first,later,ts=fixtures("2026-10-28")
    # Flat original stock and SPY prices make the volatility target
    # undefined; preserve the original primary forward comparison.
    first.loc[:,list(p4l.SECTORS)+["SPY"]]=100.
    original=p4l.evaluate(first,acquired_at_utc=original["source_acquired_at_utc"],
                          provider_reference=original["source_reference"])
    # P4L may select no names when all pre-entry signals are flat;
    # the prospective evaluator must fail closed rather than invent picks.
    with pytest.raises(m.ForwardStop):
        m.evaluate(original_manifest=original,original_prices=first,
                   later_prices=later,captured_utc=ts)


def test_sector_control_preserves_frozen_selected_sector_exposures():
    original,first,later,ts=fixtures("2026-10-28")
    result=m.evaluate(original_manifest=original,original_prices=first,
                      later_prices=later,captured_utc=ts)
    weights=result["secondary_frozen_sector_control_weights"]
    selected=result["original_pretrade_selection"]
    assert result["secondary_frozen_sector_control_known_before_entry"]
    assert result["secondary_sector_control_contains_selected_names"]
    assert set(weights)<=set(p4l.SECTORS)
    assert sum(weights.values())==pytest.approx(1.,abs=1e-10)
    for sector in set(p4l.SECTORS.values()):
        expected=sum(p4l.SECTORS[s]==sector for s in selected)/len(selected)
        observed=sum(w for s,w in weights.items() if p4l.SECTORS[s]==sector)
        assert observed==pytest.approx(expected,abs=1e-10)
    # Even a single-member sector cannot introduce a new instrument.
    assert m._frozen_sector_control(["NEE"])=={"NEE":1.}
    assert m._frozen_sector_control(["XOM","CVX"])=={"CVX":.5,"XOM":.5}


def test_same_sector_control_costs_and_entry_exit_match_original_picks():
    original,first,later,ts=fixtures("2026-10-28")
    result=m.evaluate(original_manifest=original,original_prices=first,
                      later_prices=later,captured_utc=ts)
    entry=later.loc[m.ENTRY_SESSION]
    end=later.loc["2026-10-28"]
    weights=result["secondary_frozen_sector_control_weights"]
    growth=sum(w*end[s]/entry[s] for s,w in weights.items())
    for bps in ("5","15","35"):
        item=result["costed_95pct_stocks_versus_95pct_spy"][bps]
        sector=item["secondary_same_sector_original_cohort"]
        fee=int(bps)/10000.
        expected=5+95/(1+fee)*growth*(1-fee)
        assert sector["sector_control_terminal_after_exit_fee_usd"]==pytest.approx(
            expected,abs=1e-8)
        assert sector["selected_minus_same_sector_net_percentage_points"]==pytest.approx(
            item["theoretical_stock_terminal_after_exit_fee_usd"]-expected,abs=1e-8)
        assert sector["same_95pct_initial_gross_and_both_sides_costed"]
        assert sector["includes_original_selected_stocks_in_control"]
        assert sector["not_independent_or_factor_neutral_alpha"]


def test_sector_control_cannot_reselect_using_future_returns():
    original,first,later,ts=fixtures("2026-10-28")
    before=m.evaluate(original_manifest=original,original_prices=first,
                      later_prices=later,captured_utc=ts)
    changed=later.copy()
    # An unselected stock in the same sector as a picked stock moves
    # the comparator, but cannot change the original picks or weights.
    selected=before["original_pretrade_selection"]
    peer=next(s for s in p4l.SECTORS
              if s not in selected and any(
                  p4l.SECTORS[s]==p4l.SECTORS[p] for p in selected))
    changed.loc["2026-10-28",peer]*=1.03
    after=m.evaluate(original_manifest=original,original_prices=first,
                     later_prices=changed,captured_utc=ts)
    assert before["original_pretrade_selection"]==after["original_pretrade_selection"]
    assert (before["secondary_frozen_sector_control_weights"]==
            after["secondary_frozen_sector_control_weights"])
    assert (before["costed_95pct_stocks_versus_95pct_spy"]["15"]
            ["stock_minus_spy_net_percentage_points"]==
            after["costed_95pct_stocks_versus_95pct_spy"]["15"]
            ["stock_minus_spy_net_percentage_points"])
    assert (before["costed_95pct_stocks_versus_95pct_spy"]["15"]
            ["secondary_same_sector_original_cohort"] !=
            after["costed_95pct_stocks_versus_95pct_spy"]["15"]
            ["secondary_same_sector_original_cohort"])


def test_exact_sector_conditioned_rank_has_no_replacement_or_hindsight():
    entry=pd.Series({symbol:100. for symbol in p4l.SECTORS})
    exit_=entry.copy()
    # Four technology names, choose two without replacement = six distinct
    # sector-matched portfolios. The chosen pair is strictly strongest.
    exit_["AAPL"]=120.
    exit_["MSFT"]=110.
    exit_["AVGO"]=90.
    exit_["NVDA"]=80.
    selected=["MSFT","AAPL"]
    rank=m._sector_conditional_rank(selected,entry,exit_)
    assert rank["selected_slots_by_sector"]=={"Technology":2}
    assert rank["distinct_equal_weight_sector_matched_portfolios"]==6
    assert rank["selected_portfolio_in_reference"]
    assert rank["number_at_or_above_selected_including_ties"]==1
    assert rank["number_strictly_above_selected"]==0
    assert rank["upper_tail_fraction_including_ties"]==pytest.approx(1/6)
    assert rank["not_an_independent_or_factor_neutral_significance_test"]
    assert rank==m._sector_conditional_rank(list(reversed(selected)),entry,exit_)
    # If every peer is tied, the upper-tail fraction must be ONE, not
    # a misleading small p-value from arbitrary tie breaking.
    ties=m._sector_conditional_rank(selected,entry,entry)
    assert ties["number_at_or_above_selected_including_ties"]==6
    assert ties["number_strictly_above_selected"]==0
    assert ties["upper_tail_fraction_including_ties"]==1.


def test_exact_sector_conditioned_rank_preserves_cross_sector_slot_counts():
    entry=pd.Series({symbol:100. for symbol in p4l.SECTORS})
    exit_=entry.copy()
    rank=m._sector_conditional_rank(["AAPL","XOM"],entry,exit_)
    # Technology has four companies, energy two. Both get one slot.
    assert rank["selected_slots_by_sector"]=={"Energy":1,"Technology":1}
    assert rank["distinct_equal_weight_sector_matched_portfolios"]==8
    assert rank["upper_tail_fraction_including_ties"]==1.
    with pytest.raises(m.ForwardStop):
        m._sector_conditional_rank(["AAPL","AAPL"],entry,exit_)
    with pytest.raises(m.ForwardStop):
        m._sector_conditional_rank(["AAPL"],entry.drop("NVDA"),exit_)


def test_sector_conditional_rank_is_preentry_fixed_and_never_a_live_signal():
    waiting=run("2026-10-26",capture="2026-10-27T09:30:00Z")
    assert waiting["secondary_exact_sector_conditional_selection_rank"] is None
    first=run("2026-10-28",capture="2026-10-29T09:30:00Z")
    rank=first["secondary_exact_sector_conditional_selection_rank"]
    assert first["sector_conditional_rank_predeclared_before_entry"]
    assert rank["membership_frozen_before_entry"]
    assert rank["same_vintage_prices_for_all_reference_portfolios"]
    assert rank["selected_portfolio_in_reference"]
    assert 0<rank["upper_tail_fraction_including_ties"]<=1
    assert rank["distinct_equal_weight_sector_matched_portfolios"]>=1
    assert not first["eligible_to_rank_real_live_orders"]
    assert first["broker_orders"]==0
    original,old,later,ts=fixtures("2026-10-28")
    base=m.evaluate(original_manifest=original,original_prices=old,
                    later_prices=later,captured_utc=ts)
    # Future returns may change the RANK but never the original choices,
    # sector slot counts, or enumerated reference membership.
    changed=later.copy()
    unselected=next(s for s in p4l.SECTORS
                    if s not in base["original_pretrade_selection"])
    changed.loc["2026-10-28",unselected]*=1.10
    after=m.evaluate(original_manifest=original,original_prices=old,
                     later_prices=changed,captured_utc=ts)
    assert base["original_pretrade_selection"]==after["original_pretrade_selection"]
    a=base["secondary_exact_sector_conditional_selection_rank"]
    b=after["secondary_exact_sector_conditional_selection_rank"]
    assert a["selected_slots_by_sector"]==b["selected_slots_by_sector"]
    assert a["distinct_equal_weight_sector_matched_portfolios"]==b[
        "distinct_equal_weight_sector_matched_portfolios"]
