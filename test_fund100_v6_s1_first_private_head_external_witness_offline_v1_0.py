"""Original 0 -> 1 HMAC/signed private Git CAS with synthetic public witness.

No remote production writes, real brokerage, order or secret usage.
"""
from base64 import b64decode,b64encode
from copy import deepcopy
import json
from pathlib import Path
import pytest

import fund100_v6_s1_first_private_head_external_witness_offline_v1_0 as m
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as bootstrap

KEY=bytes.fromhex("0123456789abcdef"*4)  # exactly 32 fake test bytes
QTY="0.123456789"
RUN="9876543210"
COMMENT="1234567890"


def initial():
    w=witness.verify()
    return cas.genesis(
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=KEY)


def as_contents(raw):
    return {
        "path":cas.STATE_PATH,"type":"file","encoding":"base64",
        "sha":cas.blob_sha(raw),"content":b64encode(raw).decode()}


def genesis_comment(src):
    digest=bootstrap.public_head_commitment(
        nonce=witness.verify()["original_public_genesis_nonce"],
        private_blob_sha=src["sha"])
    body=bootstrap.public_comment(
        digest=digest,
        run_url="https://github.com/nicobouch97/fund100-research/actions/runs/39637082911")
    return {"id":m.PARENT_COMMENT_ID,"body":body,
        "issue_url":m.ISSUE_URL,"user":{"login":m.PUBLIC_BOT}}


def future_comment(before,after,run=RUN):
    return {"id":int(COMMENT),"issue_url":m.ISSUE_URL,
        "user":{"login":m.PUBLIC_BOT},
        "body":m.first_next_comment(
            original_nonce=witness.verify()["original_public_genesis_nonce"],
            old_private_sha=before["sha"],new_private_sha=after["sha"],
            run_id=run)}


def pair():
    original=as_contents(initial())
    old_comment=genesis_comment(original)
    plan=m.plan_first_reservation(
        private_source=original,genesis_comment=old_comment,
        synthetic_original_qty=QTY,synthetic_hmac_key=KEY)
    proposal=plan["private_commit_proposal_FOR_FAKE_GIT_ONLY"]
    new=as_contents(b64decode(proposal["commit"]["content_base64"]))
    return original,old_comment,plan,new,future_comment(original,new)


def verify(orig,old,next_,newcomment,key=KEY):
    return m.validate_first_head_pair(
        original_private_source=orig,original_public_comment=old,
        next_private_source=next_,new_public_comment=newcomment,
        new_public_comment_id=COMMENT,new_simulated_run_id=RUN,
        synthetic_hmac_key=key)


def test_original_proposed_first_reservation_and_witnessed_pair_are_NOT_live():
    old,origin,p,new,comment=pair()
    proposal=p["private_commit_proposal_FOR_FAKE_GIT_ONLY"]
    assert p["mode"]==m.MODE
    assert p["simulation_only"] is True
    assert p["live_order_authorized"] is False
    assert p["broker_orders"]==p["actual_private_Git_writes"]==0
    assert proposal["commit"]["expected_current_sha"]==old["sha"]
    assert proposal["new_blob_sha"]==new["sha"]
    assert proposal["stage"]=="NEW_RESERVATION_CAS_PROPOSED_NOT_EXECUTABLE"
    v=verify(old,origin,new,comment)
    assert v["status"]=="SYNTHETIC_FIRST_SIGNED_HEAD_AND_PUBLIC_CHAIN_VERIFIED_NO_LIVE_RELEASE"
    assert v["signed_next_sequence"]==1
    assert v["first_reserved_symbol"]=="ACWI"
    assert v["first_ledger_state"]=="RESERVED_NO_RETRY"
    assert v["independent_public_successor_digest_and_parent_comment_matched"] is True
    assert not v["real_live_original_quantity_authenticated"]
    assert not v["actual_private_head_PUT_performed"]
    assert not v["independently_immutable_rollback_anchor_proven"]
    assert not v["live_order_authorized"]
    assert v["real_private_Git_writes"]==v["real_broker_POSTs"]==v["real_broker_orders"]==0
    assert v["private_raw_quantity"] is v["private_head_git_sha"] is v["private_commit_payload"] is None
    for banned in (QTY,old["sha"],new["sha"],str(KEY),"f100v6s1-"):
        assert banned not in comment["body"]


def test_second_concurrent_fake_git_reservation_race_accepts_one_expected_sha():
    old,origin,p,new,comment=pair()
    fake_private=old
    stale=deepcopy(p["private_commit_proposal_FOR_FAKE_GIT_ONLY"])
    def fake_put_once(plan):
        nonlocal fake_private
        if plan["commit"]["expected_current_sha"]!=fake_private["sha"]:
            return 409
        fake_private=as_contents(b64decode(plan["commit"]["content_base64"]))
        return 200
    assert fake_put_once(stale)==200
    assert fake_put_once(stale)==409
    assert fake_private["sha"]==new["sha"]
    assert verify(old,origin,fake_private,comment)["signed_next_sequence"]==1
    # Already-reserved result is fail closed and never proposes another SELL.
    second=cas.plan_reserve(fake_private,symbol="ACWI",original_qty=QTY,
        private_genesis=witness.verify()["original_public_genesis_nonce"],
        account_binding_sha256=witness.verify()["original_live_account_binding_sha256"],
        key=KEY)
    assert second["stage"]=="ALREADY_RESERVED_NO_REPEAT"
    assert second["commit"] is None
    assert not second["live_order_authorized"]


@pytest.mark.parametrize("changed",[
    {"id":12345},
    {"issue_url":"https://api.github.com/repos/evil/repo/issues/8"},
    {"user":{"login":"not-the-bot"}},
    {"body":"edited to look successful"},
    {"body":None},
])
def test_changed_public_next_witness_is_rejected(changed):
    old,origin,p,new,comment=pair()
    comment.update(changed)
    with pytest.raises(m.FirstHeadStop,match="public witness"):
        verify(old,origin,new,comment)


def test_genesis_comment_must_be_original_bot_issue_exact_digest():
    old,origin,p,new,comment=pair()
    for changed in (
        {"id":5},{"user":{"login":"fake"}},
        {"issue_url":"https://github.com/not-original"},
        {"body":origin["body"]+"tamper"},
    ):
        wrong={**origin,**changed}
        with pytest.raises(m.FirstHeadStop,match="Initial private"):
            verify(old,wrong,new,comment)


@pytest.mark.parametrize("bad",[
    {"sha":"0"*40},
    {"content":"wrong-base64"},
    {"path":"sandbox/not-production-state.json"},
])
def test_private_signed_first_successor_sha_contents_or_path_must_match(bad):
    old,origin,p,new,comment=pair()
    new.update(bad)
    with pytest.raises(m.FirstHeadStop):
        verify(old,origin,new,comment)


def mutated_head(changes):
    old,origin,p,new,comment=pair()
    doc=json.loads(b64decode(new["content"]))
    doc.pop("signature")
    doc.update(changes)
    key=KEY
    raw=cas._canon({**doc,"signature":cas._seal(doc,key)})
    changed=as_contents(raw)
    return old,origin,changed,future_comment(old,changed)


@pytest.mark.parametrize("changes",[
    {"sequence":2},
    {"sequence":0},
    {"prior_document_sha":"0"*40},
    {"entries":{}},
    {"entries":{"XLE":{"state":"RESERVED_NO_RETRY",
                       "client_order_id":"fake","qty_commitment":"f"*64}}},
])
def test_even_valid_HMAC_cannot_replay_wrong_sequence_parent_or_XLE(changes):
    old,origin,next_,newcomment=mutated_head(changes)
    with pytest.raises(m.FirstHeadStop):
        verify(old,origin,next_,newcomment)


def test_wrong_key_cannot_recover_private_original_or_head():
    old,origin,p,new,comment=pair()
    with pytest.raises(m.FirstHeadStop):
        verify(old,origin,new,comment,key=b"totally-different-fake-secret-with-32-byte-length")


def test_missing_private_file_is_never_implicit_genesis():
    old,origin,p,new,comment=pair()
    with pytest.raises(m.FirstHeadStop):
        m.plan_first_reservation(
            private_source=None,genesis_comment=origin,
            synthetic_original_qty=QTY,synthetic_hmac_key=KEY)
    with pytest.raises(m.FirstHeadStop):
        verify(None,origin,new,comment)


def test_proposal_rejects_non_integer_dangerous_qty_and_never_XLE_order():
    old,origin,p,new,comment=pair()
    for qty in (None,-1,0,"0","NaN","0.1234567891","1e12",0.5):
        with pytest.raises(m.FirstHeadStop):
            m.plan_first_reservation(
                private_source=old,genesis_comment=origin,
                synthetic_original_qty=qty,synthetic_hmac_key=KEY)
    assert m.cas.LEGACY==("ACWI","EEM","XLV")
    assert "XLE" not in m.cas.LEGACY


def test_public_head_witness_never_trusts_invalid_nonce_sha_or_run_id():
    old,origin,p,new,comment=pair()
    w=witness.verify()
    for attrs in [
        {"original_nonce":"NaN"},{"old_private_sha":"bad"},
        {"new_private_sha":old["sha"]},{"run_id":"abc"},
    ]:
        values={
            "original_nonce":w["original_public_genesis_nonce"],
            "old_private_sha":old["sha"],
            "new_private_sha":new["sha"],"run_id":RUN,
        }
        values.update(attrs)
        with pytest.raises(m.FirstHeadStop):
            m.first_next_comment(**values)


def test_source_contract_has_zero_network_secrets_alpaca_or_true_release():
    src=Path(m.__file__).read_text()
    for forbidden in ("urlopen(", "requests.post(", "requests.put(",
                      "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                      "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
                      "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
                      "os.getenv(", "/v2/orders", "submit_order("):
        assert forbidden not in src
    assert m.NO_GITHUB_HTTP and m.NO_BROKER_HTTP
    assert not m.LIVE_ORDER_RELEASED and not m.ACTUAL_PRIVATE_HEAD_ADVANCE_RELEASED
