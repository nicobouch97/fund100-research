"""Deterministic offline event-source and future-vintage tests, NO network."""
import copy
from datetime import timedelta
import pandas as pd
import pytest

import fund100_v7_e5_event_forward_ledger_v1_0 as e5
import fund100_v7_e4_sec_event_capture_v1_0 as e4
import fund100_stock_quality_momentum_p4g_v1_0 as p4g

def fixtures():
    dates=pd.bdate_range("2025-10-01","2026-10-23")
    cols=sorted(set(p4g.FROZEN_P4E_SCORES)|{"SPY","SHY"})
    data=pd.DataFrame({c:100. for c in cols},index=dates)
    data.loc["2026-10-21","MSFT"]=103.
    data.loc["2026-10-22","MSFT"]=105.
    data.loc["2026-10-23","MSFT"]=106.
    sec={"schema":e4.SCHEMA,"source_count":8,"all_frozen_issuers_acquired":True,
         "broker_orders":0,"trading_authorized":False,
         "capture_complete_utc":"2026-10-22T09:00:00Z",
         "observed_filings_not_necessarily_new_today":[{
             "ticker":"MSFT","original_sec_accession":"0000000000-26-000001",
             "filing_date":"2026-10-19",
             "sec_submissions_observed_at_utc":"2026-10-22T09:00:00Z",
             "issuer_event_type":"8-K ITEM 2.02","orders_authorized":False}]}
    base={"schema":p4g.SCHEMA,"asof_completed_session":"2026-10-21",
          "source_acquired_at_utc":"2026-10-22T09:01:00Z",
          "trading_authorized":False,"paper_authorized":False,
          "live_authorized":False,"future_performance_observations":0,
          "broker_orders":0}
    later={"schema":p4g.SCHEMA,"asof_completed_session":"2026-10-23",
          "source_acquired_at_utc":"2026-10-24T09:01:00Z",
          "trading_authorized":False,"paper_authorized":False,
          "live_authorized":False,"future_performance_observations":0,
          "broker_orders":0}
    return sec,base,data.loc[:"2026-10-21"].copy(deep=True),later,data.copy(deep=True)

def evalx(fields=None):
    s,b,initial,later,full=fixtures()
    if fields:
        fields(s,b,initial,later,full)
    return e5.evaluate(sec_source=s,baseline=b,baseline_prices=initial,
                       follow=later,follow_prices=full)

def test_frozen_positive_event_uses_first_two_later_rows_only():
    out=evalx()
    assert out["pre_entry_qualified_original_events"]==1
    assert out["status"]=="ONE_INTERVAL_ALTERNATE_OR_MATCHED_VENDOR_RESEARCH_MARKS_NO_FILLS"
    assert out["model_entry_first_later_session"]=="2026-10-22"
    assert out["model_exit_second_later_session"]=="2026-10-23"
    assert out["hypothetical_marks"][0]["one_completed_session_net_stock_minus_gross_SPY"]["35"] < out["hypothetical_marks"][0]["one_completed_session_net_stock_minus_gross_SPY"]["5"]
    assert not out["trading_authorized"] and not out["actual_live_account_pnl_measured"]

def test_revised_pre_entry_history_cannot_change_frozen_signal():
    def revise(s,b,initial,later,full):
        full.loc["2026-10-21","MSFT"]=97.
    out=evalx(revise)
    assert not out["original_vendor_historical_rows_unchanged"]
    assert out["pre_entry_qualified_original_events"]==1
    assert out["hypothetical_marks"][0]["pre_entry_reaction_original_source"]==.03

def test_original_empty_event_source_stays_no_signal():
    def remove(s,b,initial,later,full):
        s["observed_filings_not_necessarily_new_today"]=[]
    out=evalx(remove)
    assert out["status"]=="NO_GENUINE_PRE_ENTRY_EARNINGS_SIGNALS"
    assert not out["hypothetical_marks"]

def test_only_one_new_completed_session_cannot_mark_returns():
    s,b,initial,later,full=fixtures()
    full=full.loc[:"2026-10-22"]
    later["asof_completed_session"]="2026-10-22"
    later["source_acquired_at_utc"]="2026-10-23T09:00:00Z"
    out=e5.evaluate(sec_source=s,baseline=b,baseline_prices=initial,
                    follow=later,follow_prices=full)
    assert out["status"]=="WAITING_FOR_TWO_COMPLETED_POST_SIGNAL_SESSIONS"
    assert out["hypothetical_marks"][0]["one_completed_session_net_stock_minus_gross_SPY"] is None

def test_backdated_followup_source_fails_closed():
    def forged(s,b,initial,later,full):
        later["source_acquired_at_utc"]="2026-10-22T09:00:00Z"
    with pytest.raises(e5.ForwardStop):
        evalx(forged)

def test_future_snapshot_cannot_omit_old_sessions_or_enable_trading():
    s,b,initial,later,full=fixtures()
    with pytest.raises(e5.ForwardStop):
        e5.evaluate(sec_source=s,baseline=b,baseline_prices=initial,
                    follow=later,follow_prices=full.iloc[15:])
    later["trading_authorized"]=True
    with pytest.raises(e5.ForwardStop):
        e5.evaluate(sec_source=s,baseline=b,baseline_prices=initial,
                    follow=later,follow_prices=full)

def test_round_trip_costs_compound_exactly_on_actual_one_session_stock_return():
    out=evalx()
    row=out["hypothetical_marks"][0]
    gross_stock=106/105-1
    gross_spy=0
    for bps in e5.COSTS_BPS:
        expected=(1+gross_stock)*(1-bps/10000)**2-1-gross_spy
        actual=row["one_completed_session_net_stock_minus_gross_SPY"][str(bps)]
        assert actual==pytest.approx(round(expected,10),abs=1e-11)
    assert out["stock_entry_and_exit_costs_compounded_exactly"]
    assert out["SPY_is_untraded_gross_benchmark"]
    assert out["broker_orders"]==0 and out["live_authorized"] is False


def test_exact_cost_on_negative_stock_return_with_positive_spy_benchmark():
    def fall(s,b,initial,later,full):
        full.loc["2026-10-23","MSFT"]=104.
        full.loc["2026-10-23","SPY"]=101.
    out=evalx(fall)
    gross_stock=104/105-1
    gross_spy=0.01
    for bps in e5.COSTS_BPS:
        actual=out["hypothetical_marks"][0]["one_completed_session_net_stock_minus_gross_SPY"][str(bps)]
        assert actual==pytest.approx(round((1+gross_stock)*(1-bps/10000)**2-1-gross_spy,10))


@pytest.mark.parametrize("source,key,value",[
    ("baseline","paper_authorized",True),
    ("baseline","live_authorized",True),
    ("baseline","future_performance_observations",1),
    ("later","future_performance_observations",1),
    ("later","source_acquired_at_utc","2026-10-23T22:00:00Z"),
    ("later","source_acquired_at_utc","2026-11-10T09:01:00Z"),
])
def test_source_provenance_flags_and_capture_window_fail_closed(source,key,value):
    def tamper(s,b,initial,later,full):
        (b if source=="baseline" else later)[key]=value
    with pytest.raises(e5.ForwardStop):
        evalx(tamper)


def _source_pinned_report(*,source="a",price="b",later="c"):
    report=evalx()
    report.update({
        "SEC_manifest_file_SHA256":source*64,
        "original_price_report_SHA256":price*64,
        "later_price_report_SHA256":later*64,
        "original_price_csv_SHA256":"d"*64,
        "later_price_csv_SHA256":"e"*64,
    })
    return report


def test_all_eligible_original_captures_are_counted_and_repeated_filing_deduped():
    first=_source_pinned_report()
    second=_source_pinned_report(source="f",price="1")
    out=e5.aggregate_reports([first,second])
    assert out["original_captures_evaluated"]==2
    assert out["unique_original_filing_entry_events"]==1
    assert out["duplicate_event_rows_removed"]==1
    assert out["modelled_one_session_stock_minus_untraded_SPY_by_one_way_cost_bps"]["15"]["observations"]==1
    assert out["no_cross_event_independence_or_multiple_testing_claim"]
    assert not out["statistically_significant_alpha_proven"]
    assert not out["trading_authorized"]


def test_distinct_original_event_identity_increases_cohort_sample_size():
    first=_source_pinned_report()
    second=_source_pinned_report(source="f",price="1")
    second["hypothetical_marks"][0]["original_sec_accession"]="0000000000-26-000002"
    out=e5.aggregate_reports([first,second])
    assert out["unique_original_filing_entry_events"]==2
    assert out["duplicate_event_rows_removed"]==0
    assert out["modelled_one_session_stock_minus_untraded_SPY_by_one_way_cost_bps"]["5"]["observations"]==2


def test_all_no_signal_captures_produce_empty_descriptive_cohort():
    report=_source_pinned_report()
    report["hypothetical_marks"]=[]
    report["pre_entry_qualified_original_events"]=0
    report["status"]="NO_GENUINE_PRE_ENTRY_EARNINGS_SIGNALS"
    out=e5.aggregate_reports([report])
    assert out["status"]=="NO_SOURCE_QUALIFIED_FORWARD_EVENTS"
    assert out["unique_original_filing_entry_events"]==0
    assert out["modelled_one_session_stock_minus_untraded_SPY_by_one_way_cost_bps"]["35"]["descriptive_mean_excess_pct"] is None


@pytest.mark.parametrize("tamper",[
    lambda reports:reports[1].__setitem__("later_price_report_SHA256","9"*64),
    lambda reports:reports[1]["hypothetical_marks"][0]["one_completed_session_net_stock_minus_gross_SPY"].__setitem__("15",0.25),
    lambda reports:reports[0].__setitem__("trading_authorized",True),
    lambda reports:reports[0].__setitem__("original_price_report_SHA256","not-a-digest"),
    lambda reports:reports[1].update({"SEC_manifest_file_SHA256":reports[0]["SEC_manifest_file_SHA256"],"original_price_report_SHA256":reports[0]["original_price_report_SHA256"]}),
])
def test_cohort_rejects_mixed_vintage_conflicting_event_or_untrusted_source(tamper):
    reports=[_source_pinned_report(),_source_pinned_report(source="f",price="1")]
    tamper(reports)
    with pytest.raises(e5.ForwardStop):
        e5.aggregate_reports(reports)
