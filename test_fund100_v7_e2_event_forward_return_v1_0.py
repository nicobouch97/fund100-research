import pytest
from fund100_v7_e2_event_forward_return_v1_0 import evaluate, EvidenceStop

def sample():
    rows=[]
    for d,s,b in [
        ("2026-10-12",100,100),("2026-10-13",100,100),
        ("2026-10-15",101,100),("2026-10-16",104,100),
        ("2026-10-19",106,101),("2026-10-20",105,102)]:
        rows.append({"session":d,"stock_close":s,"benchmark_close":b,
                     "completed_at_utc":d+"T21:00:00Z"})
    event={"source_kind":"SEC_8K_ITEM_2_02","sec_accession":"TEST_ONLY",
           "filing_date":"2026-10-14","sec_acquired_at_utc":"2026-10-15T11:00:00Z",
           "price_acquired_at_utc":"2026-10-16T22:00:00Z",
           "future_prices_acquired_at_utc":"2026-10-20T22:00:00Z"}
    return event,rows

def test_forward_net_is_only_after_confirmation_and_costs():
    e,r=sample()
    out=evaluate(e,r)
    assert out["status"]=="HYPOTHETICAL_FORWARD_CLOSE_MARK_NOT_FILL"
    assert out["entry_session"]=="2026-10-19"
    assert out["exit_session"]=="2026-10-20"
    assert out["benchmark_relative_net_two_sided_cost"]["35"] < out["benchmark_relative_net_two_sided_cost"]["5"]
    assert not out["alpha_proven"] and not out["orders_authorized"]

def test_no_lookahead_entry_if_price_not_acquired_before_entry_completion():
    e,r=sample()
    e["price_acquired_at_utc"]="2026-10-20T22:00:00Z"
    with pytest.raises(EvidenceStop): evaluate(e,r)

def test_future_mark_must_have_been_acquired_after_exit():
    e,r=sample()
    e["future_prices_acquired_at_utc"]="2026-10-19T22:00:00Z"
    with pytest.raises(EvidenceStop): evaluate(e,r)

def test_does_not_turn_pre_entry_rally_into_forward_profit():
    e,r=sample()
    r[-1]["stock_close"]=106
    out=evaluate(e,r)
    assert out["gross_stock_return"]==0
    assert out["benchmark_relative_net_two_sided_cost"]["15"] < 0

def test_source_and_price_integrity_fail_closed():
    e,r=sample()
    e["source_kind"]="UNVERIFIED_HEADLINE"
    with pytest.raises(EvidenceStop): evaluate(e,r)
    e,r=sample()
    r[3]["stock_close"]=0
    with pytest.raises(EvidenceStop): evaluate(e,r)

def test_weak_signal_is_not_a_trade():
    e,r=sample()
    r[3]["stock_close"]=100
    out=evaluate(e,r)
    assert out["status"]=="NO_SIGNAL" and not out["orders_authorized"]
