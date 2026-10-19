"""Investor-guided research should be falsifiable and never claim order rights."""
import copy
import json
from pathlib import Path
import pytest
import fund100_v6_investment_thesis_gate_v1_0 as r

def full():
    return json.loads(r.REGISTER.read_text())

def checked(v=None,*,paths=True):
    return r.audit(full() if v is None else v,verify_paths=paths)

def test_all_six_market_families_have_original_grounded_hypotheses():
    x=checked()
    assert x["research_families"]==6
    assert x["candidate_count"]==7
    assert x["original_source_count"]==7
    assert x["source_documents_verified"]
    assert x["broker_post_requests"]==x["broker_get_requests"]==0
    assert x["new_proposed_trade_intents"]==0
    assert not x["new_live_instruments_authorized"]
    assert x["operator_stop_remains_required"]

def test_user_aggressive_capital_stop_and_short_profit_wait():
    x=full()
    assert x["approval_guard"]["max_original_capital_usd"]=="130.30"
    assert x["approval_guard"]["paper_pnl_wait_required"] is False
    assert x["approval_guard"]["independent_history_can_promote_to_live"] is False
    assert x["approval_guard"]["account_stop_must_remain_engaged"]

@pytest.mark.parametrize("field,bad",[
 ("allow_leverage",True),("may_issue_broker_orders",True),
 ("independent_history_can_promote_to_live",True),
 ("account_stop_must_remain_engaged",False),
 ("max_original_capital_usd","130.31"),
 ("allow_new_assets_without_explicit_versioned_release",True),
 ("rejected_models_automatically_revived",True)
])
def test_broker_security_cannot_be_circumvented(field,bad):
    x=full();x["approval_guard"][field]=bad
    with pytest.raises(r.PhilosophyStop):checked(x)

@pytest.mark.parametrize("field,value",[
 ("current_broker_live_approved",True),
 ("alpha_established",True),("may_issue_orders",True),
 ("status","LIVE_RELEASED")
])
def test_no_candidate_can_self_promote(field,value):
    x=full();x["candidates"][0][field]=value
    with pytest.raises(r.PhilosophyStop):checked(x)

def test_original_failed_s1_reserve_mechanics_stay_visible():
    x=full();s1=x["candidates"][0]
    assert s1["id"]=="V6-S1"
    assert "2,792" in " ".join(s1["failure_modes"])
    s1["failure_modes"]=["No risks"]
    with pytest.raises(r.PhilosophyStop):checked(x)

def test_all_candidates_have_genuine_original_evidence_and_limits():
    x=full()
    for item in x["candidates"]:
        assert (r.HERE/item["evidence"]).is_file()
        assert item["benchmarks"] and item["failure_modes"]
        assert item["required_next_sources"]
        assert not item["may_issue_orders"]
        assert not item["alpha_established"]

def test_references_do_not_confer_privileged_trading_status():
    x=full()
    x["candidates"][1]["foundation"].append("FAKE_CELEBRITY_STRATEGY")
    with pytest.raises(r.PhilosophyStop):checked(x)

def test_data_rights_and_unavailable_sources_remain_explicit():
    x=full()
    m={z["id"]:z for z in x["candidates"]}
    assert "owner" in m["V6-Q1"]["label"].lower()
    assert "delisting-aware" in " ".join(m["V6-Q1"]["required_next_sources"])
    assert "CME" in " ".join(m["V6-C10"]["failure_modes"])
    assert m["V6-FX1"]["status"]=="BROKER_ROUTE_UNAVAILABLE_RESEARCH_ONLY"

@pytest.mark.parametrize("change",["remove","duplicate","wrong_asset","wrong_priority","bad_path"])
def test_missing_families_or_forged_original_path_fails_closed(change):
    x=full()
    if change=="remove":x["candidates"].pop()
    elif change=="duplicate":x["candidates"][0]["id"]=x["candidates"][1]["id"]
    elif change=="wrong_asset":x["candidates"][0]["asset"]="derivatives"
    elif change=="wrong_priority":x["candidates"][0]["priority"]=x["candidates"][1]["priority"]
    elif change=="bad_path":x["candidates"][0]["evidence"]="../../../../.ssh/config"
    with pytest.raises(r.PhilosophyStop):checked(x)

def test_bad_reference_link_and_blank_failure_mode_block():
    x=full();x["references"][0]["url"]="http://untrusted"
    with pytest.raises(r.PhilosophyStop):checked(x)
    x=full();x["candidates"][0]["failure_modes"]=[]
    with pytest.raises(r.PhilosophyStop):checked(x)
