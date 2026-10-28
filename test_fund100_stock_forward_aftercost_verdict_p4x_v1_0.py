"""P4X costed source-qualified forward evidence; no investment orders."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest
import exchange_calendars as xcals

import fund100_stock_forward_permanent_anchor_p4i_v1_0 as p4i
import fund100_stock_forward_corporate_action_bridge_p4v_v1_0 as p4v
import fund100_stock_forward_aftercost_verdict_p4x_v1_0 as p4x


def sourced(*,pg=False,observations=6,selected_gross=-0.3,spy_gross=0.2,
            six_gross=-0.4):
    costs={}
    for bp in p4x.SIDE_COST_BPS:
        s=round(p4x._net(selected_gross,bp),6)
        sp=round(p4x._net(spy_gross,bp),6)
        six=round(p4x._net(six_gross,bp),6)
        costs[str(bp)]={
            "cost_bps_each_side":bp,
            "selected_gross_return_pct":selected_gross,
            "selected_net_return_pct":s,
            "spy_net_return_pct":sp,
            "equal_six_net_return_pct":six,
            "selected_minus_spy_net_percentage_points":round(s-sp,6),
            "selected_minus_equal_six_net_percentage_points":round(s-six,6),
            "hypothetical_open_and_close_both_modelled":True,
        }
    x={
        "schema":p4v.SCHEMA if pg else p4i.SCHEMA,
        "frozen_baseline_session":"2026-10-16",
        "original_frozen_watchlist":["MSFT","KO","PG"],
        "selection_is_not_reranked_from_followup":True,
        "prior_history_used_for_strategy_pnl":False,
        "original_baseline_json_sha256":p4i.ORIGINAL_JSON_SHA,
        "original_baseline_price_csv_sha256":p4i.ORIGINAL_CSV_SHA,
        "post_freeze_entry_session":"2026-10-19",
        "post_freeze_exit_observation_session":"2026-10-27",
        "future_return_observations":observations,
        "observed_new_completed_sessions":observations+1,
        "costed_return_scenarios":costs,
        "period_cagr_or_statistical_alpha_inferred":False,
        "broker_orders":0,"live_authorized":False,
        "paper_authorized":False,"trading_authorized":False,
        "scheduled_research_source_selection":{
            "selection_method":(
                "KNOWN_PG_OCT23_DIVIDEND_BRIDGE_P4V"
                if pg else "STRICT_P4I_ORIGINAL_VINTAGE"),
            "broker_orders":0,
            "live_authorized":False,
            "later_vendor_revisions_permitted_unconditionally":False,
            "strict_p4i_original_vintage_accepted":not pg,
            "strict_p4i_revision_rejection":(
                "FAIL_CLOSED_SOURCE_REVISION: material historical vendor restatement; symbols=PG"
                if pg else None),
        },
    }
    if pg:
        x.update({
            "followup_source_sha256":"1"*64,
            "corporate_action_crosscheck":{
                "event":deepcopy(p4v.PG_EVENT),
                "frozen_original_price_rows_retained":True,
                "revised_pre_freeze_rows_used_for_returns":False,
                "independent_total_return_benchmark_verified":False,
                "cash_dividend_actually_settled_verified":False,
            }
        })
    else:
        x.update({
            "later_original_p4g_json_sha256":"a"*64,
            "original_17_oct_archive_verified_before_forward_calculation":True,
            "overlapping_original_adjusted_prices_sha_verified":True,
            "revised_overlap_prices_used_for_pnl":False,
        })
    return x


@pytest.mark.parametrize("qualified",[False,True])
def test_qualified_source_costed_verdict_is_research_only(qualified):
    r=p4x.analyze(sourced(pg=qualified))
    assert r["completed_forward_return_intervals"]==6
    assert r["research_sample_status"]=="VERY_SHORT_OBSERVATION_WINDOW"
    assert r["observed_spy_relative_verdict"]=="UNDERPERFORMED_OR_TIED_SPY_IN_ALL_MODELED_COST_SCENARIOS"
    assert r["after_both_side_costs"]["35"]["selected_minus_spy_net_pp"]<0
    assert r["after_both_side_costs"]["35"]["selected_minus_frozen_six_net_pp"]>0
    assert not r["strategy_approved_for_live"] and not r["live_authorized"]
    assert r["broker_post_requests"]==r["broker_orders"]==0
    assert r["no_estimated_CAGR_or_independent_statistical_alpha"]
    assert r["hypothetical_closing_prices_not_verified_broker_fills"]


def test_not_every_good_forward_window_is_promotable():
    x=sourced(observations=63,selected_gross=6.0,spy_gross=2.0)
    x["post_freeze_exit_observation_session"]=(
        xcals.get_calendar("XNYS")
        .sessions_in_range("2026-10-19","2027-06-30")[63]
        .date().isoformat())
    r=p4x.analyze(x)
    assert r["observed_spy_relative_verdict"]=="OUTPERFORMED_SPY_IN_ALL_MODELED_COST_SCENARIOS"
    assert r["research_sample_status"]=="LONGER_DESCRIPTIVE_OBSERVATION_NOT_INDEPENDENT_ALPHA"
    assert r["cannot_promote_strategies_or_change_existing_holdings"]
    assert not r["strategy_approved_for_live"]


@pytest.mark.parametrize("key,bad",[
    ("original_frozen_watchlist",["AAPL","MSFT","PG"]),
    ("original_baseline_json_sha256","f"*64),
    ("original_baseline_price_csv_sha256","f"*64),
    ("post_freeze_entry_session","2026-10-16"),
    ("future_return_observations",0),
    ("future_return_observations",True),
    ("observed_new_completed_sessions",5),
    ("live_authorized",True),
    ("broker_orders",1),
    ("trading_authorized",True),
    ("period_cagr_or_statistical_alpha_inferred",True),
    ("revised_overlap_prices_used_for_pnl",True),
    ("later_original_p4g_json_sha256","invalid"),
])
def test_false_source_and_trade_permits_are_rejected(key,bad):
    r=sourced()
    r[key]=bad
    with pytest.raises(p4x.ScorecardStop):
        p4x.analyze(r)


@pytest.mark.parametrize("cost,field,bad",[
    ("35","selected_net_return_pct",22.1),
    ("15","selected_minus_spy_net_percentage_points",8),
    ("5","selected_gross_return_pct",90),
    ("35","selected_minus_equal_six_net_percentage_points",3),
    ("35","cost_bps_each_side",0),
    ("5","hypothetical_open_and_close_both_modelled",False),
])
def test_costed_or_relative_performance_tampering_rejected(cost,field,bad):
    r=sourced()
    r["costed_return_scenarios"][cost][field]=bad
    with pytest.raises(p4x.ScorecardStop):
        p4x.analyze(r)


def test_reported_session_count_must_match_real_nyse_trading_dates():
    r=sourced()
    r["post_freeze_exit_observation_session"]="2026-10-26"
    with pytest.raises(p4x.ScorecardStop,match="NYSE"):
        p4x.analyze(r)


def test_missing_cost_scenario_cannot_hide_high_cost_failure():
    r=sourced()
    del r["costed_return_scenarios"]["35"]
    with pytest.raises(p4x.ScorecardStop):
        p4x.analyze(r)


def test_unverified_dividend_is_not_equity_alpha(monkeypatch):
    r=sourced(pg=True)
    r["corporate_action_crosscheck"]["independent_total_return_benchmark_verified"]=True
    with pytest.raises(p4x.ScorecardStop):
        p4x.analyze(r)


def test_unknown_dividend_or_bad_selection_fails():
    r=sourced(pg=True)
    r["corporate_action_crosscheck"]["event"]["cash_dividend_per_share_usd"]=0.1
    with pytest.raises(p4x.ScorecardStop):
        p4x.analyze(r)
    r=sourced()
    r["scheduled_research_source_selection"]["selection_method"]="ARBITRARY_ADJUSTMENT"
    with pytest.raises(p4x.ScorecardStop):
        p4x.analyze(r)


def test_no_broker_source_or_order_operation_in_scorecard():
    code=inspect.getsource(p4x)
    assert "urlopen(" not in code
    assert "requests.post" not in code
    assert "alpaca.markets" not in code
    assert p4x.LIVE_ORDERS==0
