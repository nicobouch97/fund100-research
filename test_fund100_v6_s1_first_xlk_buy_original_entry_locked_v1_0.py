"""Credentialless hard-stop and one-process routing tests; NO broker/Git I/O."""
import os

import pytest

import fund100_v6_s1_first_xlk_buy_original_entry_locked_v1_0 as entry
import fund100_v6_s1_first_xlk_buy_atomic_writer_locked_v1_0 as writer
import fund100_v6_s1_first_xlk_buy_autoreserve_locked_v1_0 as reserve
import fund100_v6_s1_first_xlk_buy_source_workflow_scope_locked_v1_0 as scope

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
