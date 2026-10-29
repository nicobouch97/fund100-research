"""Verify the real HTTP PUT adapter can never make an unqualified LIVE write."""
from base64 import b64decode
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError
import pytest

import fund100_v6_recurring_real_cas_transport_locked_v1_0 as mod
import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_recurring_private_cas_once_offline_v1_0 as offline
import fund100_v6_recurring_anchored_current_head_getonly_v1_0 as head
from test_fund100_v6_recurring_private_cas_once_offline_v1_0 import (
    AUTH, EVENT, CONTEXT, proposal, genesis, source, FakeGit,
)


@pytest.fixture(autouse=True)
def _pin_synthetic_genesis(monkeypatch):
    # Actual immutable public SHA is NEVER overwritten in production code.
    monkeypatch.setattr(head.source, "PINNED_INITIAL_BLOB_SHA", genesis()["sha"])


class Reply:
    def __init__(self, status, value):
        self.status=status
        self.buf=BytesIO(json.dumps(value).encode())
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self, n):return self.buf.read(n)


class FakeGitHttp:
    synthetic_only = True
    def __init__(self, old, new):
        self.calls=[]
        self.old=old
        self.new=new
        self.http_status=200
        self.bad_ack=False
        self.lost_ack=False
        self.conflict=False
        self.redirect=False
        self.unexpected_large=False
    def __call__(self, req, timeout):
        assert timeout==12
        assert req.get_method()=="PUT"
        assert req.full_url==mod.URL
        assert req.get_header("Authorization")=="Bearer fake-writer-personal-access"
        assert req.get_header("Content-type")=="application/json"
        payload=json.loads(req.data)
        assert set(payload)=={"sha","content","branch","message"}
        assert payload["branch"]=="main"
        assert payload["sha"]==self.old
        raw=b64decode(payload["content"],validate=True)
        assert journal.original.blob_sha(raw)==self.new
        self.calls.append(payload)
        if self.lost_ack:
            raise TimeoutError("remote accepted PUT but ack lost")
        if self.conflict:
            raise HTTPError(mod.URL,409,"old sha conflict",{},None)
        return Reply(
            self.http_status,{"content":{"path":journal.PATH,
                            "sha":("0"*40 if self.bad_ack else self.new)},
            "commit":{"sha":"f"*40}})


def test_exact_signed_first_reservation_http_put_single_ack_contract():
    plan=proposal()
    fake=FakeGitHttp(plan["old_blob_sha"],plan["new_blob_sha"])
    out=mod._one_conditional_put(
        writer_token="fake-writer-personal-access",
        expected_old=plan["old_blob_sha"],
        expected_new=plan["new_blob_sha"],
        commit=plan["commit"],genesis=AUTH["genesis_sha256"],account=AUTH["account_binding_sha256"],key=AUTH["key"],transport=fake)
    assert out==plan["new_blob_sha"]
    assert len(fake.calls)==1
    assert fake.calls[0]["sha"]==plan["old_blob_sha"]
    assert "ALPACA" not in str(fake.calls[0])


@pytest.mark.parametrize("failure",["lost_ack","conflict","bad_ack"])
def test_any_unknown_private_cas_ack_must_permanently_hold_no_second_put(failure):
    plan=proposal()
    fake=FakeGitHttp(plan["old_blob_sha"],plan["new_blob_sha"])
    setattr(fake,failure,True)
    with pytest.raises(mod.PrivateCasHold,match="NEVER RETRY"):
        mod._one_conditional_put(
            writer_token="fake-writer-personal-access",
            expected_old=plan["old_blob_sha"],
            expected_new=plan["new_blob_sha"],
            commit=plan["commit"],genesis=AUTH["genesis_sha256"],account=AUTH["account_binding_sha256"],key=AUTH["key"],transport=fake)
    assert len(fake.calls)==1


def test_injected_http_500_after_one_request_must_hold():
    plan=proposal()
    fake=FakeGitHttp(plan["old_blob_sha"],plan["new_blob_sha"])
    fake.http_status=500
    with pytest.raises(mod.PrivateCasHold, match="NEVER RETRY"):
        mod._one_conditional_put(
            writer_token="fake-writer-personal-access",
            expected_old=plan["old_blob_sha"],
            expected_new=plan["new_blob_sha"],
            commit=plan["commit"],genesis=AUTH["genesis_sha256"],account=AUTH["account_binding_sha256"],key=AUTH["key"],transport=fake)
    assert len(fake.calls)==1


@pytest.mark.parametrize("problem",["wrong_old","wrong_path","wrong_repo",
                                     "wrong_new","bad_base64","bad_token"])
def test_untrusted_private_put_is_rejected_before_network(problem):
    plan=proposal()
    original=dict(plan["commit"])
    token="fake-writer-personal-access"
    old=plan["old_blob_sha"]
    new=plan["new_blob_sha"]
    if problem=="wrong_old":old="0"*40
    if problem=="wrong_path":original["path"]="state/original_ACWI.json"
    if problem=="wrong_repo":original["repository"]="attacker/repository"
    if problem=="wrong_new":new="0"*40
    if problem=="bad_base64":original["content_base64"]="!not-base64!"
    if problem=="bad_token":token=""
    fake=FakeGitHttp(plan["old_blob_sha"],plan["new_blob_sha"])
    with pytest.raises(mod.PrivateCasHold):
        mod._one_conditional_put(
            writer_token=token,
            expected_old=old,expected_new=new,
            commit=original,genesis=AUTH["genesis_sha256"],account=AUTH["account_binding_sha256"],key=AUTH["key"],transport=fake)
    assert fake.calls==[]


def test_real_network_path_hard_locked_even_with_signed_fake_plan():
    plan=proposal()
    with pytest.raises(mod.PrivateCasHold,match="HARD LOCKED"):
        mod._one_conditional_put(
            writer_token="fake-writer-personal-access",
            expected_old=plan["old_blob_sha"],
            expected_new=plan["new_blob_sha"],
            commit=plan["commit"],genesis=AUTH["genesis_sha256"],account=AUTH["account_binding_sha256"],key=AUTH["key"],transport=None)


def test_original_signed_genesis_to_signed_reservation_one_injected_CAS(monkeypatch):
    old=genesis()
    plan=proposal()
    monkeypatch.setattr(head.source,"PINNED_INITIAL_BLOB_SHA",old["sha"])
    fake=FakeGit(old)
    writes=[]
    def one_put(req):
        assert set(req)=={"repository","path","branch","sha","content"}
        assert req["sha"]==old["sha"]
        assert req["repository"]==journal.REPOSITORY
        assert req["path"]==journal.PATH
        writes.append(req)
        new=source(b64decode(req["content"],validate=True))
        fake.current=new
        return new["sha"]
    result=mod.simulate_one_existing_genesis_transition(
        plan=plan,original_source=old,
        read_before=fake.preget,put_once=one_put,read_after=fake.postget,
        genesis=AUTH["genesis_sha256"],
        account=AUTH["account_binding_sha256"],key=AUTH["key"])
    assert result["status"]=="INJECTED_SIGNED_PRIVATE_FIRST_RESERVATION_CAS_NO_TRADING"
    assert result["signed_sequence"]==1
    assert result["synthetic_only"] is True
    assert result["live_orders_authorized"] is False
    assert result["new_head_provider_immutable"] is False
    assert len(writes)==1
    sha,doc=journal.read_github_source(fake.current,**AUTH)
    assert doc["events"][EVENT]["stage"]=="RESERVED_NO_ORDER"
    assert doc["events"][EVENT]["original_intent"]==CONTEXT["original_intent"]


def test_no_fake_or_duplicate_event_proposal_can_transition():
    old=genesis()
    plan=proposal()
    wrong=deepcopy(plan)
    wrong["status"]="LIVE_APPROVED_TRADE"
    with pytest.raises(mod.PrivateCasHold):
        mod._verify_plan(wrong,genesis=AUTH["genesis_sha256"],
                         account=AUTH["account_binding_sha256"],
                         key=AUTH["key"],expected_old=old["sha"])
    assert mod.ALLOWED_STAGE=="OFFLINE_NEW_EVENT_RESERVATION_CAS_ONLY"


@pytest.mark.parametrize("fault",["wrong_sha","different_preget","bad_put","lost_ack"])
def test_synthetic_cas_preserves_at_most_one_and_fail_closed(monkeypatch,fault):
    old=genesis()
    plan=proposal()
    monkeypatch.setattr(head.source,"PINNED_INITIAL_BLOB_SHA",old["sha"])
    pre=dict(old)
    if fault=="different_preget":pre["sha"]="f"*40
    calls=[]
    def preget():return pre
    def put(req):
        calls.append(req)
        if fault=="lost_ack":raise TimeoutError("lost")
        return ("0"*40 if fault=="bad_put" else plan["new_blob_sha"])
    def postget():
        return source(b64decode(plan["commit"]["content_base64"]))
    if fault=="wrong_sha":
        monkeypatch.setattr(head.source,"PINNED_INITIAL_BLOB_SHA","0"*40)
    with pytest.raises(mod.PrivateCasHold):
        mod.simulate_one_existing_genesis_transition(
            plan=plan,original_source=old,read_before=preget,
            put_once=put,read_after=postget,
            genesis=AUTH["genesis_sha256"],account=AUTH["account_binding_sha256"],
            key=AUTH["key"])
    assert len(calls)<=1
    if fault in ("wrong_sha","different_preget"):assert calls==[]


def test_no_production_writer_release_or_broker_ever_from_module():
    assert mod.PRODUCTION_EVENT_CAS_RELEASED is False
    assert mod.AUTOMATIC_IMMUTABLE_NEXT_HEAD_RELEASED is False
    assert mod.REAL_STRATEGY_EVENT_SOURCE_AUTHENTICATED is False
    assert mod.LIVE_BROKER_ORDER_RELEASED is False
    assert mod.NO_AUTOMATIC_CAS_RETRY is True
    assert mod.NEXT_HEAD_IMMUTABLE_BY_THIS_TRANSPORT is False
    assert "main" in mod.URL or mod.URL.endswith(journal.PATH)
    assert mod.READ_URL.endswith("?ref=main")
    module=Path(mod.__file__).read_text()
    assert 'method="PUT"' in module
    assert 'method="POST"' not in module
    assert "ALPACA_LIVE_KEY" not in module
    assert "ALPACA_LIVE_SECRET" not in module
    assert "  workflow_dispatch:" not in module
    assert "secrets.FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in module


def test_injected_non_test_http_transport_refused_before_any_put():
    plan=proposal()
    fake=FakeGitHttp(plan["old_blob_sha"],plan["new_blob_sha"])
    fake.synthetic_only=False
    with pytest.raises(mod.PrivateCasHold,match="synthetic fake"):
        mod._one_conditional_put(
            writer_token="fake-writer-personal-access",
            expected_old=plan["old_blob_sha"],expected_new=plan["new_blob_sha"],
            commit=plan["commit"],genesis=AUTH["genesis_sha256"],account=AUTH["account_binding_sha256"],key=AUTH["key"],transport=fake)
    assert fake.calls==[]


def test_http_adapter_hmac_tampering_refused_even_with_git_blob_consistent():
    plan=proposal()
    fake=FakeGitHttp(plan["old_blob_sha"],plan["new_blob_sha"])
    wrong_key=b"other-synthetic-only-key-"+b"x"*40
    with pytest.raises(mod.PrivateCasHold,match="HMAC"):
        mod._one_conditional_put(
            writer_token="fake-writer-personal-access",
            expected_old=plan["old_blob_sha"],expected_new=plan["new_blob_sha"],
            commit=plan["commit"],genesis=AUTH["genesis_sha256"],
            account=AUTH["account_binding_sha256"],key=wrong_key,transport=fake)
    assert fake.calls==[]
