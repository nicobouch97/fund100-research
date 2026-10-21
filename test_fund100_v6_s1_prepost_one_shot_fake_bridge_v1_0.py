"""Mock-only V6-S1 signed seq1 -> seq2 PRE-POST send-once acceptance tests."""
from base64 import b64decode,b64encode
from copy import deepcopy
import json
from pathlib import Path

import pytest

import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as m
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as boot
import fund100_v6_s1_first_private_head_external_witness_offline_v1_0 as first
import fund100_v6_s1_public_genesis_witness_v1_0 as witness

KEY=bytes.fromhex("0123456789abcdef"*4)
QUANTITY="0.123456789"
FIRST_COMMENT_ID="1234567890"
FIRST_RUN_ID="9876543210"
SIM_RUN_ID="9876543211"
SECOND_COMMENT_ID=2345678901


def as_source(raw:bytes)->dict:
    return {"type":"file","path":cas.STATE_PATH,"encoding":"base64",
            "sha":cas.blob_sha(raw),"content":b64encode(raw).decode("ascii")}


def start():
    w=witness.verify()
    genesis=cas.genesis(private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],key=KEY)
    genesis_source=as_source(genesis)
    plan=cas.plan_reserve(genesis_source,symbol="ACWI",original_qty=QUANTITY,
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],key=KEY)
    assert plan["stage"]=="NEW_RESERVATION_CAS_PROPOSED_NOT_EXECUTABLE"
    original=as_source(b64decode(plan["commit"]["content_base64"]))
    c0={
        "id":int(m.ORIGINAL_GENESIS_COMMENT),
        "body":boot.public_comment(
            digest=boot.public_head_commitment(
                nonce=w["original_public_genesis_nonce"],
                private_blob_sha=genesis_source["sha"]),
            run_url="https://github.com/nicobouch97/fund100-research/actions/runs/39637082911"),
        "issue_url":m.ORIGINAL_ISSUE_URL,
        "user":{"login":m.EXPECTED_BOT}}
    c1={
        "id":int(FIRST_COMMENT_ID),
        "body":first.first_next_comment(
            original_nonce=w["original_public_genesis_nonce"],
            old_private_sha=genesis_source["sha"],
            new_private_sha=original["sha"],run_id=FIRST_RUN_ID),
        "issue_url":m.ORIGINAL_ISSUE_URL,
        "user":{"login":m.EXPECTED_BOT}}
    return original,c0,c1


class FakeTransports:
    def __init__(self,source):
        self.source=deepcopy(source)
        self.puts=0
        self.gets=0
        self.posts=0
        self.external_gets=0
        self.broker_calls=0
        self.inject=""
        self.comment=None
        self.last_broker_payload=None
    def private_put(self,*,expected_sha,content_base64):
        self.puts+=1
        if self.inject=="git_timeout":
            raise TimeoutError("fake network unknown")
        if self.inject=="stale_409":
            return {"status":409,"sha":None}
        if expected_sha!=self.source["sha"]:
            return {"status":409,"sha":None}
        self.source=as_source(b64decode(content_base64,validate=True))
        return {"status":200,"sha":self.source["sha"]}
    def private_get(self):
        self.gets+=1
        if self.inject=="bad_private_read":
            d=deepcopy(self.source)
            d["sha"]="0"*40
            return d
        return deepcopy(self.source)
    def public_post(self,body):
        self.posts+=1
        if self.inject=="public_timeout":
            raise TimeoutError("fake external unsure")
        self.comment={
            "id":SECOND_COMMENT_ID,
            "body":body,
            "issue_url":m.ORIGINAL_ISSUE_URL,
            "user":{"login":m.EXPECTED_BOT}}
        return deepcopy(self.comment)
    def public_get(self,ident):
        self.external_gets+=1
        assert ident==SECOND_COMMENT_ID
        d=deepcopy(self.comment)
        if self.inject=="bad_public_read":
            d["body"]+="tampered"
        return d
    def fake_broker(self,payload):
        self.broker_calls+=1
        self.last_broker_payload=dict(payload)
        if self.inject=="broker_timeout":
            raise TimeoutError("fake order may have been received")
        if self.inject=="broker_terminal":
            return {**payload,"status":"rejected"}
        return {**payload,"status":"accepted"}


def operate(source,c0,c1,backend,bridge=None,quantity=QUANTITY,first_id=FIRST_COMMENT_ID):
    obj=m.FakeSendOnce() if bridge is None else bridge
    return obj.run(
        original_source=source,genesis_public_comment=c0,
        first_public_comment=c1,first_comment_id=first_id,
        first_run_id=FIRST_RUN_ID,original_qty=quantity,synthetic_key=KEY,
        synthetic_run_id=SIM_RUN_ID,
        fake_git_put_once=backend.private_put,
        fake_git_get=backend.private_get,
        fake_issue_post_once=backend.public_post,
        fake_issue_get=backend.public_get,
        fake_broker_send_once=backend.fake_broker)


def test_one_proper_mock_first_head_to_second_head_and_single_fake_send():
    s,c0,c1=start()
    transport=FakeTransports(s)
    obj=m.FakeSendOnce()
    result=operate(s,c0,c1,transport,bridge=obj)
    assert result["stage"]=="SIMULATED_POSTBOUNDARY_SEND_ONCE_NO_REAL_ORDERS"
    assert result["signed_state_sequence"]==2
    assert result["signed_seq2_POST_MAY_HAVE_BEEN_SENT_confirmed"]
    assert result["external_public_sha256_head_chain_verified"]
    assert result["fake_broker_send_calls"]==1
    assert transport.puts==transport.gets==transport.posts==transport.external_gets==transport.broker_calls==1
    assert result["real_private_git_writes"]==0
    assert result["real_broker_post_requests"]==result["real_broker_orders"]==0
    assert result["new_live_order_authorized"] is False
    assert result["private_head_sha"] is None
    assert result["private_order_payload"] is None
    assert transport.last_broker_payload["qty"]==QUANTITY
    assert transport.last_broker_payload["symbol"]=="ACWI"
    assert transport.last_broker_payload["client_order_id"]==cas.CLIENT_IDS["ACWI"]
    signed=json.loads(b64decode(transport.source["content"]))
    assert signed["entries"]["ACWI"]["state"]=="POST_MAY_HAVE_BEEN_SENT"
    assert signed["sequence"]==2
    assert QUANTITY not in transport.comment["body"]
    assert transport.source["sha"] not in transport.comment["body"]
    with pytest.raises(m.OneShotStop,match="consumed"):
        operate(s,c0,c1,transport,bridge=obj)
    assert transport.broker_calls==1


def test_after_restart_already_possible_post_state_never_reissues():
    s,c0,c1=start()
    t=FakeTransports(s)
    operate(s,c0,c1,t)
    postsource=t.source
    other=FakeTransports(postsource)
    with pytest.raises(m.OneShotStop):
        operate(postsource,c0,c1,other)
    assert other.puts==other.broker_calls==0


@pytest.mark.parametrize("failure",[
    "git_timeout","stale_409","bad_private_read",
    "public_timeout","bad_public_read","broker_timeout","broker_terminal",
])
def test_irreversible_failures_never_retry_and_nobody_sends_early(failure):
    s,c0,c1=start()
    t=FakeTransports(s)
    t.inject=failure
    obj=m.FakeSendOnce()
    with pytest.raises(m.OneShotStop):
        operate(s,c0,c1,t,bridge=obj)
    assert t.puts==1
    assert t.broker_calls==(1 if failure.startswith("broker_") else 0)
    assert t.posts==(0 if failure in ("git_timeout","stale_409","bad_private_read") else 1)
    with pytest.raises(m.OneShotStop,match="consumed"):
        operate(s,c0,c1,t,bridge=obj)
    assert t.puts==1
    assert t.broker_calls<=1


@pytest.mark.parametrize("change",[
    {"body":"tampered"},
    {"id":55},
    {"issue_url":"https://example.invalid/not-original"},
    {"user":{"login":"forger"}},
])
def test_original_public_first_intent_comment_must_be_exact(change):
    s,c0,c1=start()
    t=FakeTransports(s)
    c1.update(change)
    with pytest.raises(m.OneShotStop):
        operate(s,c0,c1,t)
    assert t.puts==t.posts==t.broker_calls==0


def test_original_public_initial_genesis_cannot_be_edited():
    s,c0,c1=start()
    t=FakeTransports(s)
    c0["body"]+="edited"
    with pytest.raises(m.OneShotStop):
        operate(s,c0,c1,t)
    assert t.puts==t.broker_calls==0


def test_original_share_commitment_not_equivalent_to_other_quantity():
    s,c0,c1=start()
    t=FakeTransports(s)
    with pytest.raises(m.OneShotStop):
        operate(s,c0,c1,t,quantity="0.123456788")
    assert t.puts==t.broker_calls==0


@pytest.mark.parametrize("change",[
    {"sha":"0"*40},
    {"path":"sandbox/fake.json"},
    {"content":"not-base64"},
])
def test_original_private_signed_source_does_not_accept_tampering(change):
    s,c0,c1=start()
    s.update(change)
    t=FakeTransports(s)
    with pytest.raises(m.OneShotStop):
        operate(s,c0,c1,t)
    assert t.puts==t.broker_calls==0


def test_original_seq0_is_not_reserved_and_must_never_progress_to_prepost():
    s,c0,c1=start()
    w=witness.verify()
    genesis=cas.genesis(private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],key=KEY)
    original=as_source(genesis)
    t=FakeTransports(original)
    with pytest.raises(m.OneShotStop):
        operate(original,c0,c1,t)
    assert t.puts==t.broker_calls==0


def test_missing_git_private_source_is_not_permission_to_reserve():
    s,c0,c1=start()
    t=FakeTransports(s)
    with pytest.raises(m.OneShotStop):
        operate(None,c0,c1,t)
    assert t.puts==t.broker_calls==0


def test_wrong_first_public_comment_id_not_sufficient_to_use_a_matching_digest():
    s,c0,c1=start()
    t=FakeTransports(s)
    with pytest.raises(m.OneShotStop):
        operate(s,c0,c1,t,first_id="999999999")
    assert t.puts==t.broker_calls==0


def test_all_http_and_actual_broker_authorities_are_absent():
    code=Path(m.__file__).read_text()
    for forbidden in (
        "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET","api.alpaca.markets",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
        "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
        "urlopen(", "requests.post(", "requests.put(", "alpaca_trade_api",
        "method=\"POST\"", "method=\"PUT\""):
        assert forbidden not in code
    assert m.NO_GITHUB_OR_ALPACA_NETWORK
    assert not m.PRODUCTION_PRIVATE_CAS_WRITER_RELEASED
    assert not m.LIVE_BROKER_TRANSPORT_RELEASED
    assert not m.LIVE_TRADING_RELEASED
