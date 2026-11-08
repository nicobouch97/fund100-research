"""Credentialless hard-stop and one-process routing tests; NO broker/Git I/O."""
import os

import pytest

import fund100_v6_s1_first_xlk_buy_original_entry_locked_v1_0 as entry
import fund100_v6_s1_first_xlk_buy_atomic_writer_locked_v1_0 as writer
import fund100_v6_s1_first_xlk_buy_autoreserve_locked_v1_0 as reserve
import fund100_v6_s1_first_xlk_buy_source_workflow_scope_locked_v1_0 as scope
import fund100_v6_s1_first_xlk_asof_opportunity_getonly_locked_v1_0 as opp

def test_current_main_first_buy_entry_hard_locks_before_sources(monkeypatch):
    called=[]
    monkeypatch.setattr(writer,"_locked",lambda:called.append("writer_network_scope"))
    monkeypatch.setattr(writer,"_op_go",lambda:called.append("operator"))
    monkeypatch.setattr(reserve,"autoreserve",
                        lambda **kwargs:called.append("private_Git_CAS"))
    monkeypatch.setattr(writer,"submit_one_original_xlk_buy",
                        lambda **kwargs:called.append("broker_POST"))
    assert entry.FIRST_XLK_BUY_ENTRY_RELEASED is False
    assert reserve.AUTORESERVE_RUNTIME_RELEASED is False
    assert writer.RUNTIME_RELEASED is False
    assert writer.BROKER_BUY_POST_RELEASED is False
    assert scope.FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED is False
    assert entry.RETRY_ON_AMBIGUOUS_CAS_OR_BROKER_RESULT is False
    assert entry.MAX_FUNDED_BUY_POSTS==1
    with pytest.raises(entry.FirstBuyEntryStop,match="HARD LOCKED"):
        entry.execute_first_xlk_original_once()
    assert called==[]

def pretend_current_market_buy(*,monkeypatch,changes=None):
    # ONLY synthetic fixture: the actual market source stays hard locked.
    proof={
        "schema":opp.SCHEMA,"model":opp.MODEL,
        "decision":"BUY_XLK_ASOF_AFTER_COST_HEURISTIC",
        "source_is_market_api_authenticated":True,
        "first_xlk_exact_amount_usd":"29.40",
        "first_xlk_exact_cost_usd":"0.10",
        "all_source_sessions_identical":True,
        "observed_completed_sessions":opp.MIN_SESSIONS,
        "asof_source_sha256":"c"*64,
        "authenticated_market_data_GET_count":len(opp.SYMBOLS),
        "alpha_or_forward_outperformance_proven":False,
        "live_buy_sell_authorized":False,
        "private_git_writes":0,"broker_orders_submitted":0,
    }
    if changes:proof.update(changes)
    calls=[]
    def inspect(**kwargs):
        assert kwargs=={
            "broker_key":creds()["ALPACA_LIVE_KEY"],
            "broker_secret":creds()["ALPACA_LIVE_SECRET"],
            "amount_usd":entry.FIXED_FIRST_BUY_NOTIONAL_USD,
            "cost_usd":entry.FIXED_FIRST_BUY_WORST_CASE_COST_USD}
        calls.append("opportunity_GETonly")
        return proof
    monkeypatch.setattr(opp,"inspect",inspect)
    return calls


def creds():
    return {
        "FUND100_PRIVATE_STATE_READ_TOKEN":"fake-only-private-reader-unique",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN":"fake-only-private-writer-unique",
        "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX":"a"*64,
        "GITHUB_TOKEN":"fake-only-public-reader-unique",
        "ALPACA_LIVE_KEY":"fake-only-broker-key-unique",
        "ALPACA_LIVE_SECRET":"fake-only-broker-secret-unique",
    }

def test_fake_only_entry_routes_signed_reservation_then_atomic_writer(monkeypatch):
    # Replacing our own top-level guard with synthetic values is allowed in
    # this test only. Both underlying networking functions are fully replaced
    # too: no live identity or real source ever passes.
    called=[]
    monkeypatch.setattr(entry,"_preflight",creds)
    market_proofs=pretend_current_market_buy(monkeypatch=monkeypatch)
    def reservation(**kwargs):
        called.append(("reservation",kwargs))
        return {
            "schema":reserve.SCHEMA,
            "status":"FIRST_BUY_SIGNED_SEQ1_RESERVED_READY_FOR_SEPARATE_WRITER",
            "first_buy_private_state_sequence":1,
            "buyer_post_authorized":False,
            "broker_POSTs":0,
        }
    def fake_writer(**kwargs):
        called.append(("writer",kwargs))
        return {
            "schema":writer.SCHEMA,
            "status":"FIRST_XLK_BUY_POST_ATTEMPTED_NEVER_RETRY",
            "first_buy_order_submissions_in_this_process":1,
            "repeat_allowed":False,
            "actual_broker_fill_and_settlement_verified":False,
        }
    monkeypatch.setattr(reserve,"autoreserve",reservation)
    monkeypatch.setattr(writer,"submit_one_original_xlk_buy",fake_writer)
    result=entry.execute_first_xlk_original_once()
    assert result["status"]=="FIRST_ORIGINAL_XLK_BUY_SINGLE_POST_ATTEMPT_NO_RETRY"
    assert result["eligible_to_repeat"] is False
    assert result["fully_filled"] is False
    assert len(called)==2
    assert market_proofs==["opportunity_GETonly"]
    assert [v[0] for v in called]==["reservation","writer"]
    a,b=called[0][1],called[1][1]
    assert a==b
    assert a["amount_usd"]==entry.FIXED_FIRST_BUY_NOTIONAL_USD=="29.40"
    assert a["cost_usd"]==entry.FIXED_FIRST_BUY_WORST_CASE_COST_USD=="0.10"
    assert a["hmac_key"]==bytes.fromhex("a"*64)
    assert not ("private_transport" in a or "broker_transport" in a)
    assert not ("fake_account_get" in a["source_kwargs"]
                or "fake_postorder_kwargs" in a["source_kwargs"]
                or "now_utc" in a["source_kwargs"])
    assert a["source_kwargs"]["broker_secret"]==creds()["ALPACA_LIVE_SECRET"]

@pytest.mark.parametrize("stage",["reserved_bad","reserved_existing","writer_uncertain"])
def test_ambiguous_provisional_first_buy_never_attempts_a_second_writer(monkeypatch,stage):
    monkeypatch.setattr(entry,"_preflight",creds)
    pretend_current_market_buy(monkeypatch=monkeypatch)
    times={"reserve":0,"writer":0}
    def fake_reserve(**kwargs):
        times["reserve"]+=1
        if stage=="reserved_bad":
            raise RuntimeError("Private CAS maybe committed")
        return {
            "schema":reserve.SCHEMA,
            "status":("EXISTING_SIGNED_FIRST_BUY_RESERVED_NO_NEW_WRITE"
                      if stage=="reserved_existing" else
                      "FIRST_BUY_SIGNED_SEQ1_RESERVED_READY_FOR_SEPARATE_WRITER"),
            "first_buy_private_state_sequence":1,
            "buyer_post_authorized":False,
            "broker_POSTs":0,
        }
    def fake_writer(**kwargs):
        times["writer"]+=1
        if stage=="writer_uncertain":
            raise RuntimeError("One possible broker POST timed out")
        return {
            "schema":writer.SCHEMA,
            "status":"FIRST_XLK_BUY_POST_ATTEMPTED_NEVER_RETRY",
            "first_buy_order_submissions_in_this_process":1,
            "repeat_allowed":False,
            "actual_broker_fill_and_settlement_verified":False,
        }
    monkeypatch.setattr(reserve,"autoreserve",fake_reserve)
    monkeypatch.setattr(writer,"submit_one_original_xlk_buy",fake_writer)
    if stage=="reserved_bad" or stage=="writer_uncertain":
        with pytest.raises(entry.FirstBuyEntryStop,match="NEVER RETRY"):
            entry.execute_first_xlk_original_once()
    else:
        assert entry.execute_first_xlk_original_once()["eligible_to_repeat"] is False
    assert times["reserve"]==1
    assert times["writer"]==(0 if stage=="reserved_bad" else 1)

def test_entry_requires_exact_source_and_no_external_amounts():
    assert entry.EXPECTED_WORKFLOW_REF==scope.FIRST_XLK_FUNDED_BUY_WORKFLOW_REF
    assert entry.EXPECTED_WORKFLOW_REF==writer.EXPECTED_REF
    assert "fund100-v6-s1-first-xlk-buy-funded-once.yml@refs/heads/main" in entry.EXPECTED_WORKFLOW_REF
    assert set(entry.REQUIRED_ENV)==set(creds())
    assert entry.FIRST_XLK_BUY_ENTRY_RELEASED is False



@pytest.mark.parametrize("bad",[
    {"decision":"NO_BUY_UNQUALIFIED_COSTED_RELATIVE_STRENGTH"},
    {"source_is_market_api_authenticated":False},
    {"asof_source_sha256":None},
    {"first_xlk_exact_amount_usd":"29.41"},
    {"observed_completed_sessions":62},
    {"authenticated_market_data_GET_count":2},
    {"live_buy_sell_authorized":True},
    {"alpha_or_forward_outperformance_proven":True},
    {"broker_orders_submitted":1},
    {"private_git_writes":1},
])
def test_unqualified_market_opportunity_never_reaches_first_buy_signed_cas_or_order(
        monkeypatch,bad):
    monkeypatch.setattr(entry,"_preflight",creds)
    evidence=pretend_current_market_buy(monkeypatch=monkeypatch,changes=bad)
    events=[]
    monkeypatch.setattr(reserve,"autoreserve",
                        lambda **kw:events.append("private_BUY_genesis_or_CAS"))
    monkeypatch.setattr(writer,"submit_one_original_xlk_buy",
                        lambda **kw:events.append("broker_BUY_POST"))
    with pytest.raises(entry.FirstBuyEntryStop,match="NEVER RETRY"):
        entry.execute_first_xlk_original_once()
    assert evidence==["opportunity_GETonly"]
    assert events==[]
    assert entry.FIRST_XLK_BUY_ENTRY_RELEASED is False


def test_unknown_market_source_error_is_no_private_write_and_no_broker_buy(monkeypatch):
    monkeypatch.setattr(entry,"_preflight",creds)
    events=[]
    def unavailable(**kwargs):
        events.append("market_read")
        raise opp.OpportunityStop("Stale or unavailable IEX bars")
    monkeypatch.setattr(opp,"inspect",unavailable)
    monkeypatch.setattr(reserve,"autoreserve",
                        lambda **kw:events.append("private_BUY_genesis"))
    monkeypatch.setattr(writer,"submit_one_original_xlk_buy",
                        lambda **kw:events.append("broker_POST"))
    with pytest.raises(entry.FirstBuyEntryStop,match="NEVER RETRY"):
        entry.execute_first_xlk_original_once()
    assert events==["market_read"]

def test_source_is_separately_hard_locked_on_original_main():
    assert opp.SOURCE_RELEASED is False
    assert opp.NO_BROKER_POST and opp.NO_PRIVATE_GIT_WRITE
