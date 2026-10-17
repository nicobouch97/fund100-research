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
