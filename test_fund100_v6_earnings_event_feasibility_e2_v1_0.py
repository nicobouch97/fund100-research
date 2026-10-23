"""Synthetic-only V6-E2 chronological historical event feasibility checks."""
from __future__ import annotations
import hashlib
import json

import pandas as pd

import fund100_stock_quality_momentum_p4g_v1_0 as p4g
import fund100_v6_sec_earnings_catalyst_e1_v1_0 as e1
import fund100_v6_earnings_event_feasibility_e2_v1_0 as e2
from test_fund100_v6_sec_earnings_catalyst_e1_v1_0 import sec_fixture,price_fixture


def setup(tmp_path, event_date="2026-06-16", with_shock=True):
    src=sec_fixture(tmp_path,event_date=event_date)
    report,csv=price_fixture(tmp_path)
    if with_shock:
        prices=pd.read_csv(csv,parse_dates=["Date"]).set_index("Date")
        prices.loc[prices.index>=pd.Timestamp("2026-06-17"),"AAPL"]*=1.08
        # Recanonicalize original synthetic source and update its byte commitment.
        contents=p4g.canonical_price_csv(prices)
        csv.write_text(contents)
        snapshot=json.loads(report.read_text())
        snapshot["canonical_price_csv_sha256"]=hashlib.sha256(contents.encode()).hexdigest()
        report.write_text(json.dumps(snapshot))
    m,s=e1.original_sec_sources(src)
    r,data=e1.original_price_source(report,csv)
    return e2.event_study(m,s,r,data)


def test_historical_events_not_independent_alpha_and_new_stocks_not_permitted(tmp_path):
    result=setup(tmp_path)
    assert result["schema"]==e2.SCHEMA
    assert result["individual_original_sec_earnings_events_checked"]==8
    assert result["positive_reaction_events"]==1
    assert result["positive_reaction_issuers"]==1
    assert result["all_qualified_event_observations"][0]["ticker"]=="AAPL"
    assert result["measured_real_money_live_returns"] is False
    assert result["cohort_eight_known_2026_survivors"]
    assert result["no_historical_point_in_time_quality_scores"]
    assert not result["minimal_candidate_evidence_check_passed"]
    assert result["economic_status"]=="REJECT_FOR_LIVE_TOO_WEAK_OR_INSUFFICIENT"
    assert result["broker_orders"]==0 and not result["old_live_positions_sold"]
    assert not result["paper_authorized"] and not result["live_authorized"]


def test_cost_drag_strictly_increases_and_same_spy_reference(tmp_path):
    result=setup(tmp_path)
    row=result["all_qualified_event_observations"][0]
    n=row["net_spy_relative_percentage_points_by_one_way_cost_bps"]
    assert n["5"]>n["15"]>n["35"]
    assert row["hypothetical_entry_third_close"]>row["second_post_filing_close"]
    assert row["hypothetical_exit_after_ten_sessions"]>row["hypothetical_entry_third_close"]
    assert result["simulated_ten_session_holding_period"]==10
    assert result["intraday_executable_entry_price_verified"] is False
    assert "cagr" in " ".join(result.keys()).lower()  # explicitly NOT a strategy CAGR


def test_no_eligible_earnings_event_is_not_fake_profitable_signal(tmp_path):
    result=setup(tmp_path,event_date="2026-10-15",with_shock=False)
    assert result["individual_original_sec_earnings_events_checked"]==0
    assert result["positive_reaction_events"]==0
    assert result["results_by_one_way_transaction_cost_bps"]["35"]["median_net_excess_percentage_points"] is None
    assert result["economic_status"]=="REJECT_FOR_LIVE_TOO_WEAK_OR_INSUFFICIENT"


def test_reacting_stock_can_lose_further_from_entry_with_transaction_cost(tmp_path):
    # A stock may jump at earnings, then immediately fade after the delayed entry.
    # The analysis must measure FROM entry, not credit the already elapsed jump.
    result=setup(tmp_path,with_shock=True)
    row=result["all_qualified_event_observations"][0]
    assert row["prior_two_session_reaction_stock_minus_spy_pct"]>2
    # No claim that the 8% price jump itself was an achievable post-entry gain.
    assert row["ten_session_stock_gross_pct"]<2
    assert result["economic_status"]!="LIVE_APPROVED"


def test_same_event_window_controls_expose_incremental_signal_economics(tmp_path):
    result=setup(tmp_path)
    controls=result["matched_event_controls_by_cost_bps"]
    assert result["real_xnys_event_horizons_verified"]
    assert result["controls_added_post_hoc_not_independent_holdout"]
    for bps in ("5","15","35"):
        selected=result["results_by_one_way_transaction_cost_bps"][bps]
        below=controls[bps]["below_threshold_filing_control"]
        all_filings=controls[bps]["all_filing_unconditional_control"]
        assert selected["event_count"]==1
        assert below["event_count"]==7
        assert all_filings["event_count"]==8
        # In this synthetic fixture the signal jump happens before entry.
        # It must not manufacture an advantage over otherwise identical names.
        assert abs(controls[bps]["selected_minus_below_threshold_mean_pp"])<0.001
    assert not result["live_authorized"] and not result["paper_authorized"]


def test_missing_real_exchange_session_excludes_entire_event_window(tmp_path):
    source=sec_fixture(tmp_path,event_date="2026-06-16")
    report,csv=price_fixture(tmp_path)
    prices=pd.read_csv(csv,parse_dates=["Date"]).set_index("Date")
    # 18 June 2026 is a genuine NYSE session; 19 June is Juneteenth.
    assert pd.Timestamp("2026-06-18") in prices.index
    assert pd.Timestamp("2026-06-19") not in prices.index
    prices=prices.drop(pd.Timestamp("2026-06-18"))
    contents=p4g.canonical_price_csv(prices)
    csv.write_text(contents)
    snapshot=json.loads(report.read_text())
    snapshot["canonical_price_csv_sha256"]=hashlib.sha256(contents.encode()).hexdigest()
    report.write_text(json.dumps(snapshot))
    m,s=e1.original_sec_sources(source)
    r,data=e1.original_price_source(report,csv)
    result=e2.event_study(m,s,r,data)
    assert result["events_excluded_lack_coverage"]["NONCONSECUTIVE_XNYS_EVENT_WINDOW"]==8
    assert result["individual_original_sec_earnings_events_checked"]==0
    assert result["positive_reaction_events"]==0


def test_missing_pre_filing_market_session_is_not_treated_as_valid_base(tmp_path):
    source=sec_fixture(tmp_path,event_date="2026-06-16")
    report,csv=price_fixture(tmp_path)
    prices=pd.read_csv(csv,parse_dates=["Date"]).set_index("Date")
    assert pd.Timestamp("2026-06-15") in prices.index
    prices=prices.drop(pd.Timestamp("2026-06-15"))
    contents=p4g.canonical_price_csv(prices)
    csv.write_text(contents)
    snapshot=json.loads(report.read_text())
    snapshot["canonical_price_csv_sha256"]=hashlib.sha256(contents.encode()).hexdigest()
    report.write_text(json.dumps(snapshot))
    m,s=e1.original_sec_sources(source)
    r,data=e1.original_price_source(report,csv)
    result=e2.event_study(m,s,r,data)
    assert result["events_excluded_lack_coverage"]["NONCONSECUTIVE_XNYS_EVENT_WINDOW"]==8
    assert result["positive_reaction_events"]==0


def test_same_cash_account_event_economics_are_not_sum_of_independent_bets(tmp_path):
    result=setup(tmp_path)
    portfolios=result["shared_cash_portfolio_by_cost_bps"]
    assert result["portfolio_uses_first_come_25pct_entry_budget_four_slots"]
    assert result["portfolio_is_retrospective_close_fill_optimistic_not_alpha"]
    assert set(portfolios)=={"5","15","35"}
    for p in portfolios.values():
        assert p["selected_events"]==1
        assert p["accepted_entries"]==p["closed_exits"]==1
        assert p["max_concurrent_names"]==1
        assert 0<p["max_entry_budget_fraction"]<=.25
        # Price drift can increase exposure after a compliant 25% entry.
        assert p["max_drifted_name_fraction"]>=p["max_entry_budget_fraction"]
        assert p["max_gross_fraction"]<=1.000001
        assert p["min_cash_fraction"]>=0
        assert p["all_positions_flat_at_final_close"]
        assert p["matched_spy_control_accepted_entries"]==p["accepted_entries"]
        assert p["matched_spy_control_closed_exits"]==p["closed_exits"]
        assert p["matched_spy_control_max_gross_fraction"]<=1.000001
        assert p["net_spy_matched_schedule_return_pct"] is not None
        assert p["first_hypothetical_entry"]>result["all_qualified_event_observations"][0]["second_post_filing_close"]
        assert p["last_hypothetical_exit"]>p["first_hypothetical_entry"]
    # The portfolio owns only 25% of a selected issuer, not a fictional
    # fully-invested position for every observed earnings event.
    assert (portfolios["5"]["net_portfolio_return_pct"]
            >portfolios["15"]["net_portfolio_return_pct"]
            >portfolios["35"]["net_portfolio_return_pct"])
    assert result["broker_orders"]==0 and not result["live_authorized"]


def test_cash_capacity_and_same_issuer_overlap_never_create_leverage(tmp_path):
    _,csv=price_fixture(tmp_path)
    prices=pd.read_csv(csv,parse_dates=["Date"]).set_index("Date")
    # Synthetic five simultaneous valid signals compete for four 25% slots.
    entry="2026-06-22"
    exit_day="2026-07-07"
    assert pd.Timestamp(entry) in prices.index
    assert pd.Timestamp(exit_day) in prices.index
    events=[{
        "ticker":ticker,
        "original_sec_accession":f"0000000000-26-{i:06d}",
        "hypothetical_entry_third_close":entry,
        "hypothetical_exit_after_ten_sessions":exit_day,
    } for i,ticker in enumerate(("AAPL","MSFT","GOOGL","AMZN","PG"))]
    result=e2._portfolio_path(events,prices,15)
    assert result["selected_events"]==5
    assert result["accepted_entries"]==result["closed_exits"]==4
    assert result["capacity_skipped"]==1
    assert result["duplicate_issuer_skipped"]==0
    assert result["max_concurrent_names"]==4
    assert result["max_entry_budget_fraction"]<=.25
    assert result["max_gross_fraction"]<=1.000001
    assert result["min_cash_fraction"]>=0
    assert result["matched_spy_control_accepted_entries"]==4
    assert result["matched_spy_control_closed_exits"]==4
    assert result["matched_spy_control_max_gross_fraction"]<=1.000001
    assert result["all_positions_flat_at_final_close"]
    same=events[:1]+[{**events[0],"original_sec_accession":"0000000000-26-999999"}]
    overlap=e2._portfolio_path(same,prices,15)
    assert overlap["accepted_entries"]==1
    assert overlap["duplicate_issuer_skipped"]==1


def test_zero_signals_have_no_fabricated_portfolio_return(tmp_path):
    result=setup(tmp_path,event_date="2026-10-15",with_shock=False)
    for p in result["shared_cash_portfolio_by_cost_bps"].values():
        assert p["accepted_entries"]==0
        assert p["net_portfolio_return_pct"] is None
        assert p["net_spy_buy_hold_return_pct"] is None
        assert p["net_spy_matched_schedule_return_pct"] is None
        assert p["portfolio_minus_matched_spy_net_percentage_points"] is None
        assert p["matched_spy_control_accepted_entries"]==0
        assert p["all_positions_flat_at_final_close"]


def test_spy_matched_schedule_removes_idle_cash_false_alpha():
    # Identical stock and SPY prices: a 25%-invested stock portfolio
    # cannot be called a losing stock picker merely because SPY is 100% invested.
    dates=pd.to_datetime(["2026-10-19","2026-10-20","2026-10-21","2026-10-22"])
    bars=pd.DataFrame({"AAPL":[100,105,110,115],
                       "SPY":[100,105,110,115]},index=dates)
    event={"ticker":"AAPL","original_sec_accession":"0000000000-26-000001",
           "hypothetical_entry_third_close":"2026-10-19",
           "hypothetical_exit_after_ten_sessions":"2026-10-22"}
    r=e2._portfolio_path([event],bars,15)
    assert r["matched_spy_control_accepted_entries"]==1
    assert r["matched_spy_control_closed_exits"]==1
    assert r["matched_spy_control_cash_limited_entries"]==0
    assert r["portfolio_minus_matched_spy_net_percentage_points"]==0
    assert r["net_spy_matched_schedule_return_pct"]==r["net_portfolio_return_pct"]
    assert r["net_spy_buy_hold_return_pct"]>r["net_portfolio_return_pct"]


def test_spy_matched_schedule_detects_real_stock_selection_loss():
    dates=pd.to_datetime(["2026-10-19","2026-10-20","2026-10-21","2026-10-22"])
    bars=pd.DataFrame({"AAPL":[100,99,98,95],
                       "SPY":[100,101,102,105]},index=dates)
    event={"ticker":"AAPL","original_sec_accession":"0000000000-26-000001",
           "hypothetical_entry_third_close":"2026-10-19",
           "hypothetical_exit_after_ten_sessions":"2026-10-22"}
    r=e2._portfolio_path([event],bars,15)
    assert r["portfolio_minus_matched_spy_net_percentage_points"]<0
    # Initial 25% allocation can drift above 25% as SPY rises; no leverage.
    assert .25<r["matched_spy_control_max_gross_fraction"]<1
    assert r["matched_spy_control_accepted_entries"]==r["matched_spy_control_closed_exits"]==1
