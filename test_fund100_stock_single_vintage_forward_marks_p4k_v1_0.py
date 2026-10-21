"""P4K synthetic chronology, revisions, costs, zero-order assertions."""
from copy import deepcopy
from pathlib import Path
import json

import pandas as pd
import pytest

import fund100_stock_single_vintage_forward_marks_p4k_v1_0 as k
import fund100_stock_original_price_vintage_diff_p4j_v1_0 as j
import fund100_stock_forward_permanent_anchor_p4i_v1_0 as i
from test_fund100_stock_forward_permanent_anchor_p4i_v1_0 import (
    artificial_price_data, anchor_for_synthetic,
)

def newer(end="2026-10-20", capture="2026-10-21T08:00:00Z"):
    prices=artificial_price_data(end)
    original=prices.loc[:i.FIRST_CUTOFF]
    a=anchor_for_synthetic(prices)
    later={
        "schema": "FUND100_P4G_PROSPECTIVE_QUALITY_MOMENTUM_OBSERVER_V1",
        "status": "FORWARD_RESEARCH_SIGNAL_NOT_INVESTMENT_ALPHA",
        "source_acquired_at_utc":capture,
        "asof_completed_session":prices.index[-1].date().isoformat(),
        "future_performance_observations":0,
        "broker_orders":0,"paper_authorized":False,
        "live_authorized":False,"trading_authorized":False,
    }
    revision=j.classify(
        original, prices,
        original_anchor_digest=a["original_p4g_canonical_price_csv_sha256"],
        source_original_digest=a["original_p4g_canonical_price_csv_sha256"])
    return a,later,prices,revision


def test_original_selection_locked_and_zero_broker_calls():
    a,d,p,v=newer()
    out=k.window_mark(anchor=a,later_doc=d,later_prices=p,revision=v)
    assert out["status"]=="OBSERVED_SAME_VINTAGE_ADJUSTED_CLOSE_WINDOW"
    assert out["original_watchlist"]==["MSFT","KO","PG"]
    assert out["post_selection_entry_close_session"]=="2026-10-19"
    assert out["post_selection_exit_mark_session"]=="2026-10-20"
    assert out["actual_new_sessions_in_later_source"]==2
    assert out["forward_observations"]==1
    assert not out["independent_alpha_or_expected_profit_proven"]
    assert out["source_vintage_confirmed_identical_within_entry_exit"]
    assert out["price_only_or_total_return_independently_verified"] is False
    assert out["broker_requests"]==out["paper_orders"]==out["live_orders"]==0
    assert not out["trading_authorized"] and not k.RELEASED_TO_TRADE


def test_old_adjusted_prefix_change_does_not_splice_or_change_signal():
    a,d,p,_=newer()
    old=p.loc[:i.FIRST_CUTOFF].copy()
    p.loc["2026-07-01","MSFT"]*=1.005
    revise=j.classify(
        old,p,
        original_anchor_digest=a["original_p4g_canonical_price_csv_sha256"],
        source_original_digest=a["original_p4g_canonical_price_csv_sha256"])
    assert revise["comparison_status"]=="DIFFERING_ORIGINAL_PRICE_CELLS"
    out=k.window_mark(anchor=a,later_doc=d,later_prices=p,revision=revise)
    assert out["status"]=="OBSERVED_SAME_VINTAGE_ADJUSTED_CLOSE_WINDOW"
    assert out["original_watchlist"]==i.FROZEN_WATCHLIST
    assert out["historical_source_prefix_status"]=="DIFFERING_ORIGINAL_PRICE_CELLS"
    original_output=k.window_mark(anchor=a,later_doc=d,later_prices=newer()[2],
                                  revision=newer()[3])
    assert out["costed_mark_percent"]==original_output["costed_mark_percent"]


def test_two_sides_friction_is_monotone_and_comparators_costed():
    a,d,p,v=newer()
    x=k.window_mark(anchor=a,later_doc=d,later_prices=p,revision=v)
    cost=x["costed_mark_percent"]
    assert set(cost)=={"5","15","35"}
    for name in ("frozen_three_net_mark_pct","spy_net_mark_pct",
                 "frozen_equal_six_net_mark_pct"):
        assert cost["5"][name]>cost["15"][name]>cost["35"][name]
    assert all(x["modelled_entry_and_exit_costs_no_fills"]
               for x in cost.values())


def test_first_new_close_is_entry_without_earned_return():
    a,d,p,v=newer("2026-10-19",capture="2026-10-20T08:00:00Z")
    out=k.window_mark(anchor=a,later_doc=d,later_prices=p,revision=v)
    assert out["status"]=="ENTRY_OBSERVED_NO_EXIT_MARK"
    assert out["forward_observations"]==0
    assert out["costed_mark_percent"] is None


def test_no_postfreeze_market_session_is_no_return():
    a,d,p,v=newer("2026-10-16",capture="2026-10-18T08:00:00Z")
    # The source P4J classifier requires at least one new session; create
    # explicit canonical metadata for a synthetic no-session outcome.
    v={"comparison_status":"EXACT_PREFIX_PRESERVED",
       "missing_original_sessions":0,"extra_baseline_sessions":0,
       "no_forward_return_calculated":True}
    out=k.window_mark(anchor=a,later_doc=d,later_prices=p,revision=v)
    assert out["status"]=="NO_ELIGIBLE_ENTRY_SESSION"
    assert out["costed_mark_percent"] is None


def test_missing_first_eligible_session_fails_closed():
    a,d,p,v=newer()
    p=p.drop(pd.Timestamp("2026-10-19"))
    d["asof_completed_session"]=p.index[-1].date().isoformat()
    with pytest.raises(k.SingleVintageStop,match="entry session"):
        k.window_mark(anchor=a,later_doc=d,later_prices=p,revision=v)


def test_tampered_original_frozen_signal_cannot_change_selection():
    a,d,p,v=newer()
    a["original_preselected_watchlist"]=["AAPL","MSFT","KO"]
    with pytest.raises(k.SingleVintageStop,match="selection"):
        k.window_mark(anchor=a,later_doc=d,later_prices=p,revision=v)


def test_later_cannot_claim_trade_authority_or_future_signal():
    a,d,p,v=newer()
    for field,value in (("trading_authorized",True),("live_authorized",True),
                        ("broker_orders",1),("future_performance_observations",3)):
        changed=deepcopy(d);changed[field]=value
        with pytest.raises(k.SingleVintageStop,match="flags"):
            k.window_mark(anchor=a,later_doc=changed,later_prices=p,revision=v)


def test_source_missing_baseline_sessions_cannot_be_waived():
    a,d,p,v=newer()
    v["comparison_status"]="MISSING_OR_REORDERED_BASELINE_SESSIONS"
    with pytest.raises(k.SingleVintageStop,match="historical sessions"):
        k.window_mark(anchor=a,later_doc=d,later_prices=p,revision=v)


def test_source_capture_not_from_future_or_stale():
    for stamp in ("2026-10-20T08:00:00Z","2026-10-28T08:00:00Z",
                  "2026-10-21 08:00:00", "not-an-observation"):
        a,d,p,v=newer(capture=stamp)
        with pytest.raises(k.SingleVintageStop):
            k.window_mark(anchor=a,later_doc=d,later_prices=p,revision=v)


def test_code_never_has_network_or_private_order_transport():
    code=Path(k.__file__).read_text()
    for forbidden in ("requests.post(", "requests.get(", "urlopen(",
                      "/v2/orders", "FUND100_PRIVATE_STATE_READ_TOKEN",
                      "ALPACA_LIVE_KEY", "place_order(", "GH_TOKEN"):
        assert forbidden not in code
