"""P4H uses SYNTHETIC time series to falsify date/lookahead/cost claims.

Actual prospective source comparison must use original P4G GitHub Actions
artifacts, never this artificial data. No broker secrets or orders.
"""
from __future__ import annotations
from datetime import datetime,timedelta
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

import fund100_stock_forward_return_ledger_p4h_v1_0 as p4h
import fund100_stock_quality_momentum_p4g_v1_0 as p4g


def data(last):
    idx=pd.bdate_range("2025-10-01",last)
    t=np.arange(len(idx),dtype=float)
    slopes={"AAPL":.004,"MSFT":.003,"GOOGL":.0026,
            "AMZN":.0013,"XOM":.0012,"JNJ":.0008,
            "PG":.0005,"KO":.0004,"SPY":.0009,"SHY":.0001}
    return pd.DataFrame({k:100*np.exp(v*t) for k,v in slopes.items()},index=idx)


def original_files(tmp_path,stem,last,capture):
    d=data(last)
    r=p4g.evaluate(prices=d,acquired_at_utc=capture,
                   provider_reference="SYNTHETIC_ONLY test fixture original marker")
    json_path=tmp_path/(stem+".json")
    csv_path=tmp_path/(stem+".csv")
    json_path.write_text(json.dumps(r,sort_keys=True))
    csv_path.write_text(p4g.canonical_price_csv(d))
    return json_path,csv_path


def two(tmp_path,last="2026-10-20",capture="2026-10-21T07:00:00Z"):
    b,bc=original_files(tmp_path,"baseline","2026-10-16","2026-10-17T07:57:28Z")
    f,fc=original_files(tmp_path,"followup",last,capture)
    return b,bc,f,fc


def test_prior_oct16_session_not_a_hypothetical_trade_entry(tmp_path):
    a=two(tmp_path)
    v=p4h.evaluate(*a)
    assert v["schema"]==p4h.SCHEMA
    assert v["frozen_baseline_session"]=="2026-10-16"
    assert v["post_freeze_entry_session"]=="2026-10-19"
    assert v["post_freeze_exit_observation_session"]=="2026-10-20"
    assert v["observed_new_completed_sessions"]==2
    assert v["future_return_observations"]==1
    assert v["status"]=="GENUINE_POST_FREEZE_PRICE_COMPARISON_RESEARCH_ONLY"
    assert v["selection_is_not_reranked_from_followup"]
    assert not v["prior_history_used_for_strategy_pnl"]
    assert v["broker_orders"]==0
    assert not v["paper_authorized"] and not v["live_authorized"] and not v["trading_authorized"]


def test_earliest_eligible_entry_one_following_session_is_not_earned_return(tmp_path):
    v=p4h.evaluate(*two(tmp_path,last="2026-10-19",capture="2026-10-20T04:00:00Z"))
    assert v["status"]=="ENTRY_SESSION_OBSERVED_NO_FORWARD_RETURN"
    assert v["future_return_observations"]==0
    assert v["costed_return_scenarios"] is None


def test_same_original_session_cannot_invent_forward_returns(tmp_path):
    v=p4h.evaluate(*two(tmp_path,last="2026-10-16",capture="2026-10-18T07:00:00Z"))
    assert v["status"]=="NO_POST_FREEZE_ENTRY_SESSION"
    assert v["future_return_observations"]==0
    assert v["post_freeze_entry_session"] is None
    assert v["costed_return_scenarios"] is None


def test_5_15_35bp_per_side_friction_lowers_all_hypothetical_returns(tmp_path):
    r=p4h.evaluate(*two(tmp_path))
    a=r["costed_return_scenarios"]
    assert set(a)=={"5","15","35"}
    for field in ("selected_net_return_pct","spy_net_return_pct","equal_six_net_return_pct"):
        assert a["5"][field]>a["15"][field]>a["35"][field]
    assert a["15"]["hypothetical_open_and_close_both_modelled"]
    assert not r["period_cagr_or_statistical_alpha_inferred"]
    assert not r["provider_price_vintage_immutable_independently_verified"]
    assert not r["authentic_licensed_analyst_revisions_available"]


def test_later_p4g_watchlist_reordering_is_ignored(tmp_path):
    b,bc,f,fc=two(tmp_path)
    before=p4h.evaluate(b,bc,f,fc)
    follow=json.loads(f.read_text())
    follow["research_watchlist"]=list(reversed(follow["research_watchlist"]))
    f.write_text(json.dumps(follow))
    after=p4h.evaluate(b,bc,f,fc)
    assert after["original_frozen_watchlist"]==before["original_frozen_watchlist"]
    assert after["costed_return_scenarios"]==before["costed_return_scenarios"]


def test_price_vendor_rewriting_past_bar_is_rejected_even_with_new_sha(tmp_path):
    b,bc,f,fc=two(tmp_path)
    frame=pd.read_csv(fc,parse_dates=["Date"]).set_index("Date")
    frame.loc["2026-07-01","AAPL"]*=1.005
    fc.write_text(p4g.canonical_price_csv(frame))
    follow=json.loads(f.read_text())
    from hashlib import sha256
    follow["canonical_price_csv_sha256"]=sha256(fc.read_bytes()).hexdigest()
    f.write_text(json.dumps(follow))
    with pytest.raises(p4h.ForwardStop,match="revisited original prices"):
        p4h.evaluate(b,bc,f,fc)


def test_canonical_csv_sha_mismatch_rejected(tmp_path):
    b,bc,f,fc=two(tmp_path)
    f.write_text(f.read_text().replace('"canonical_price_csv_sha256": "', '"canonical_price_csv_sha256": "not'))
    with pytest.raises(p4h.ForwardStop):
        p4h.evaluate(b,bc,f,fc)


def test_baseline_must_be_oct16_not_an_optimised_new_date(tmp_path):
    b,bc,f,fc=two(tmp_path)
    doc=json.loads(b.read_text())
    doc["asof_completed_session"]="2026-10-15"
    b.write_text(json.dumps(doc))
    with pytest.raises(p4h.ForwardStop):
        p4h.evaluate(b,bc,f,fc)


def test_followup_must_be_capture_after_original(tmp_path):
    b,bc,f,fc=two(tmp_path)
    doc=json.loads(f.read_text())
    doc["source_acquired_at_utc"]="2026-10-16T00:00:00Z"
    f.write_text(json.dumps(doc))
    with pytest.raises(p4h.ForwardStop):
        p4h.evaluate(b,bc,f,fc)


def test_baseline_cannot_claim_future_trades_or_live_permission(tmp_path):
    b,bc,f,fc=two(tmp_path)
    doc=json.loads(b.read_text())
    doc["broker_orders"]=1
    b.write_text(json.dumps(doc))
    with pytest.raises(p4h.ForwardStop):
        p4h.evaluate(b,bc,f,fc)


def test_original_watchlist_cannot_be_3_unauthorised_names(tmp_path):
    b,bc,f,fc=two(tmp_path)
    doc=json.loads(b.read_text())
    doc["research_watchlist"]=["XOM","JNJ"]
    b.write_text(json.dumps(doc))
    with pytest.raises(p4h.ForwardStop):
        p4h.evaluate(b,bc,f,fc)


def test_source_with_missing_earlier_session_fails_closed(tmp_path):
    b,bc,f,fc=two(tmp_path)
    frame=pd.read_csv(fc,parse_dates=["Date"]).set_index("Date")
    frame=frame.drop(pd.Timestamp("2026-07-01"))
    from hashlib import sha256
    fc.write_text(p4g.canonical_price_csv(frame))
    doc=json.loads(f.read_text())
    doc["canonical_price_csv_sha256"]=sha256(fc.read_bytes()).hexdigest()
    f.write_text(json.dumps(doc))
    with pytest.raises(p4h.ForwardStop,match="lost original"):
        p4h.evaluate(b,bc,f,fc)


def test_empty_watchlist_really_holds_cash_without_entry_exit_cost(tmp_path):
    b,bc,f,fc=two(tmp_path)
    doc=json.loads(b.read_text())
    doc["research_watchlist"]=[]
    b.write_text(json.dumps(doc))
    v=p4h.evaluate(b,bc,f,fc)
    for x in v["costed_return_scenarios"].values():
        assert x["selected_net_return_pct"]==0
        assert x["selected_gross_return_pct"]==0
    assert v["original_frozen_watchlist"]==[]
    assert v["broker_orders"]==0
