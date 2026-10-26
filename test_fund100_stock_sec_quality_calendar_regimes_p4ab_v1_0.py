"""P4AB: exact original SEC matched-SPY 15bps calendar regime fragility.

Synthetic only: the full original source-authenticated 16-issuer 2026
survivor cohort is exercised automatically by P4N on protected main.
"""
from copy import deepcopy
from pathlib import Path

import pytest

import fund100_stock_sec_quality_calendar_regimes_p4ab_v1_0 as m
import fund100_stock_sec_quality_forward_p4r_v1_0 as p4r

def event(ticker,accession,available,entry,exitday,score,active):
    # Stock-minus-SPY has been charged the same 15bps per side on both.
    return {
        "ticker":ticker,
        "original_10k_accession":accession,
        "conservative_available_date":available,
        "entry_next_session_close":entry,
        "exit_126_sessions_later":exitday,
        "quality_score":score,
        "cost_scenarios":{
            k:{
                "stock_net_return_pct":active + 1.0,
                "spy_net_return_pct":1.0,
                "stock_minus_spy_pp":active,
            }
            for k in ("5","15","35")
        },
    }

def fixture():
    events=[
        event("AAPL","0000000001-19-000001","2019-01-31","2019-02-01","2019-08-02",3,2.0),
        event("AAPL","0000000001-20-000001","2020-01-31","2020-02-03","2020-08-03",2,-4.0),
        event("MSFT","0000000002-20-000001","2020-01-31","2020-02-03","2020-08-03",1,7.0),
        event("NVDA","0000000003-23-000001","2023-01-31","2023-02-01","2023-08-01",3,8.0),
        event("NVDA","0000000003-24-000001","2024-01-31","2024-02-01","2024-08-01",3,10.0),
    ]
    return {
        "schema":p4r.SCHEMA,
        "status":"HINDSIGHT_SURVIVOR_EVENT_STUDY_NOT_VALIDATED_ALPHA",
        "predeclared_forward_sessions":126,
        "cost_per_side_bps":[5,15,35],
        "retrospectively_selected_2026_survivors":True,
        "SEC_facts_retrieved_today_not_historical_vintages":True,
        "no_point_in_time_investable_backtest":True,
        "vendor_adjusted_prices_revisable_and_corporate_actions_not_independently_verified":True,
        "source_sec_manifest_sha256":"a"*64,
        "source_prices_canonical_csv_sha256":"b"*64,
        "live_authorized":False,"trading_authorized":False,"broker_orders":0,
        "event_returns":events,"completed_event_returns":len(events),
    }

def test_regime_by_actual_entry_date_exposes_hidden_concentration():
    out=m.inspect(fixture())
    assert out["status"]=="ORIGINAL_SEC_CALENDAR_REGIME_FRAGILITY_NO_LIVE_ALPHA"
    assert out["all_event_panel"]["events"]==5
    assert out["all_event_panel"]["distinct_issuers"]==3
    assert out["all_event_panel"]["distinct_entry_calendar_years"]==4
    assert out["all_event_panel"]["event_mean_stock_minus_matched_spy_pp"]==4.6
    assert out["all_event_panel"]["issuer_equal_mean_stock_minus_matched_spy_pp"]==pytest.approx(((-1)+7+9)/3)
    assert out["all_event_panel"]["calendar_year_equal_mean_stock_minus_matched_spy_pp"]==pytest.approx((2+1.5+8+10)/4)
    assert out["all_event_panel"]["issuer_event_dominance_fraction"]==.4
    assert out["calendar_year_mean_excess_pp"]=={"2019":2,"2020":1.5,"2023":8,"2024":10}
    assert out["calendar_years_with_positive_mean"]==4
    assert out["calendar_years_with_nonpositive_mean"]==0
    assert out["calendar_regime_panels"]["2017_2019"]["all_scored"]["events"]==1
    assert out["calendar_regime_panels"]["2020_2022"]["all_scored"]["events"]==2
    assert out["calendar_regime_panels"]["2023_2026"]["all_scored"]["events"]==2
    assert out["high_quality_panel"]["events"]==4
    assert out["low_quality_panel"]["events"]==1
    assert not out["live_order_authorized"] and not out["promotable_new_strategy"]
    assert out["broker_gets"]==out["broker_posts"]==0

def test_a_single_large_positive_issuer_does_not_hide_unfavorable_regime():
    d=fixture()
    d["event_returns"][2]["cost_scenarios"]["15"]["stock_minus_spy_pp"]=-10
    d["event_returns"][2]["cost_scenarios"]["15"]["stock_net_return_pct"]=-9
    z=m.inspect(d)
    assert z["calendar_years_with_nonpositive_mean"]==1
    assert z["calendar_year_mean_excess_pp"]["2020"]==-7
    assert z["calendar_regime_panels"]["2020_2022"]["all_scored"]["calendar_year_equal_mean_stock_minus_matched_spy_pp"]==-7

def test_zero_source_events_is_not_fake_positive_alpha():
    d=fixture()
    d["event_returns"]=[]
    d["completed_event_returns"]=0
    z=m.inspect(d)
    assert z["all_event_panel"]["events"]==0
    assert z["all_event_panel"]["event_mean_stock_minus_matched_spy_pp"] is None
    assert z["calendar_years_with_positive_mean"]==0
    assert z["calendar_years_with_eligible_events"]==0
    assert not z["live_order_authorized"]


def test_within_year_comparison_does_not_confuse_spy_outperformance_with_quality_skill():
    # All years with only one score group must abstain, even if the
    # retrospective high-quality event mean happens to be positive.
    out=m.inspect(fixture())["within_year_quality_discrimination"]
    assert out["calendar_years_with_both_quality_groups"]==1
    assert out["calendar_years_with_at_least_two_distinct_issuers_per_disjoint_group"]==0
    assert out["qualifying_year_equal_quality_gap_pp"] is None
    assert not out["per_entry_calendar_year"]["2020"]["eligible_for_descriptive_year_equal_mean"]
    assert not out["live_trading_authorized"]

def test_quality_gap_same_year_issuer_equal_exposes_negative_and_positive_years():
    d=fixture()
    additions=[
        ("NVDA","0000000003-20-000001","2020-02-10","2020-02-11","2020-08-11",2,3),
        ("TSM","0000000004-20-000001","2020-02-12","2020-02-13","2020-08-13",3,1),
        ("AMD","0000000005-20-000001","2020-02-14","2020-02-18","2020-08-18",1,-1),
        ("INTC","0000000006-20-000001","2020-02-20","2020-02-21","2020-08-21",0,-2),
        ("AAPL","0000000001-21-000001","2021-02-01","2021-02-02","2021-08-02",2,5),
        ("NVDA","0000000003-21-000001","2021-02-01","2021-02-02","2021-08-02",3,9),
        ("MSFT","0000000002-21-000001","2021-02-01","2021-02-02","2021-08-02",1,1),
        ("AMD","0000000005-21-000001","2021-02-01","2021-02-02","2021-08-02",0,-1),
    ]
    d["event_returns"].extend(event(*row) for row in additions)
    d["completed_event_returns"]=len(d["event_returns"])
    z=m.inspect(d)["within_year_quality_discrimination"]
    assert z["calendar_years_with_both_quality_groups"]==2
    assert z["calendar_years_with_at_least_two_distinct_issuers_per_disjoint_group"]==2
    assert z["qualifying_calendar_years_positive_gap"]==1
    assert z["qualifying_calendar_years_nonpositive_gap"]==1
    assert z["per_entry_calendar_year"]["2020"]["high_minus_low_issuer_equal_pp"]==pytest.approx(-4/3)
    assert z["per_entry_calendar_year"]["2021"]["high_minus_low_issuer_equal_pp"]==7
    assert z["qualifying_year_equal_quality_gap_pp"]==pytest.approx((-4/3+7)/2,abs=1e-5)
    assert z["sparse_years_excluded_not_backfilled"]
    assert z["historical_2026_survivor_selected_not_independent_alpha"]


def test_sparse_high_quality_returns_do_not_pass_yearwise_screen():
    out=m.inspect(fixture())["within_year_quality_discrimination"]
    assert out["descriptive_quality_screen"]=="ABSTAIN_INSUFFICIENT_COMPARABLE_YEARS_OR_REGIMES"
    assert out["predeclared_min_comparable_calendar_years_for_triage"]==m.MIN_YEAR_BREADTH
    assert out["qualifying_calendar_regimes_represented"]==[]
    assert out["screen_is_not_independent_alpha_or_trade_authorization"]

def _four_year_quality_panel(gaps):
    # Each original-calendar-year test uses two distinct high-score and
    # two distinct low-score issuers, each with one original event.
    d=fixture()
    d["event_returns"]=[]
    symbols=("AAPL","MSFT","NVDA","AMD")
    for i,(year,gap) in enumerate(zip((2018,2020,2022,2024),gaps)):
        for j,name in enumerate(symbols):
            side_high=j<2
            d["event_returns"].append(event(
                name,f"{j+1:010d}-{str(year)[2:]}-{i+1:06d}",
                f"{year}-01-10",f"{year}-01-11",f"{year}-07-11",
                3 if side_high else 1,gap if side_high else 0))
    d["completed_event_returns"]=len(d["event_returns"])
    return d

def test_predeclared_four_year_regime_breadth_can_show_descriptive_consistency_only():
    z=m.inspect(_four_year_quality_panel((2,1,4,3)))["within_year_quality_discrimination"]
    assert z["calendar_years_with_at_least_two_distinct_issuers_per_disjoint_group"]==4
    assert z["qualifying_calendar_regimes_represented"]==["2017_2019","2020_2022","2023_2026"]
    assert z["descriptive_quality_screen"]=="PERSISTENT_POSITIVE_DESCRIPTIVE_COMPARISON_NOT_VALIDATED_ALPHA"
    assert z["qualifying_year_equal_quality_gap_pp"]==2.5
    assert not z["live_trading_authorized"]

def test_mixed_or_unfavourable_quality_years_do_not_claim_persistent_alpha():
    mixed=m.inspect(_four_year_quality_panel((2,1,-1,3)))["within_year_quality_discrimination"]
    assert mixed["descriptive_quality_screen"]=="MIXED_DESCRIPTIVE_QUALITY_DISCRIMINATION"
    unfavourable=m.inspect(_four_year_quality_panel((2,-4,-1,-3)))["within_year_quality_discrimination"]
    assert unfavourable["descriptive_quality_screen"]=="UNFAVOURABLE_DESCRIPTIVE_QUALITY_DISCRIMINATION"

def test_positive_years_from_only_one_regime_still_abstain():
    d=_four_year_quality_panel((1,2,3,4))
    # Move all four original 2018/2020/2022/2024 events into
    # 2023-2026 with unique fiscal-year accession identities.
    for i,row in enumerate(d["event_returns"]):
        old=int(row["entry_next_session_close"][:4])
        year={2018:2023,2020:2024,2022:2025,2024:2026}[old]
        row["conservative_available_date"]=f"{year}-01-10"
        row["entry_next_session_close"]=f"{year}-01-11"
        row["exit_126_sessions_later"]=f"{year}-07-11"
        row["original_10k_accession"]=f"{i+1:010d}-{str(year)[2:]}-000001"
    z=m.inspect(d)["within_year_quality_discrimination"]
    assert z["qualifying_calendar_regimes_represented"]==["2023_2026"]
    assert z["descriptive_quality_screen"]=="ABSTAIN_INSUFFICIENT_COMPARABLE_YEARS_OR_REGIMES"

def test_same_issuer_on_both_sides_of_year_is_not_treated_as_independent():
    d=fixture()
    d["event_returns"].append(
        event("AAPL","0000000001-20-000002","2020-03-01","2020-03-02",
              "2020-09-02",0,12))
    d["completed_event_returns"]=len(d["event_returns"])
    year=m.inspect(d)["within_year_quality_discrimination"]["per_entry_calendar_year"]["2020"]
    assert year["issuers_appearing_in_both_quality_groups"]==["AAPL"]
    assert year["high_minus_low_issuer_equal_pp"] is not None
    assert not year["eligible_for_descriptive_year_equal_mean"]

@pytest.mark.parametrize("mutate",[
    lambda d:d.update(schema="UNVERIFIED"),
    lambda d:d.update(retrospectively_selected_2026_survivors=False),
    lambda d:d.update(no_point_in_time_investable_backtest=False),
    lambda d:d.update(SEC_facts_retrieved_today_not_historical_vintages=False),
    lambda d:d.update(live_authorized=True),
    lambda d:d.update(broker_orders=1),
    lambda d:d.update(completed_event_returns=100),
    lambda d:d["event_returns"].append(deepcopy(d["event_returns"][0])),
    lambda d:d["event_returns"][0].update(entry_next_session_close="2018-12-31"),
    lambda d:d["event_returns"][0].update(entry_next_session_close="2019-02-30"),
    lambda d:d["event_returns"][0].update(quality_score=4),
    lambda d:d["event_returns"][0].update(ticker="fake"),
    lambda d:d["event_returns"][0].update(original_10k_accession="fake"),
    lambda d:d["event_returns"][0]["cost_scenarios"]["15"].update(stock_minus_spy_pp=99),
    lambda d:d["event_returns"][0]["cost_scenarios"]["15"].update(stock_minus_spy_pp=float("nan")),
])
def test_false_alpha_or_broken_original_market_evidence_stops(mutate):
    d=fixture()
    mutate(d)
    with pytest.raises(m.RegimeStop):
        m.inspect(d)

def test_code_has_no_broker_or_live_signal_source():
    src=Path(m.__file__).read_text()
    assert m.TRADING_RELEASED is False
    assert m.BROKER_ORDERS==0
    for banned in ("import requests","import urllib","import socket",
                   "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                   "method=\"POST\"","git push"):
        assert banned not in src
