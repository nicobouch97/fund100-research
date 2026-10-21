"""Fake-only signed genesis post-bootstrap recovery and public witness proof."""
from base64 import b64encode
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as r
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as boot
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_private_state_actions_readonly_probe_v1_0 as identity
import fund100_v6_s1_public_genesis_witness_v1_0 as witness

COMMENT_ID = "987654321"
RUN_ID = "999999999"
KEY = "0123456789abcdef" * 4
READ_TOKEN = "test-private-read-PAT-not-real"
PUBLIC_TOKEN = "test-public-actions-GitHub-token-not-real"


def original():
    return witness.verify()


def signed_genesis(key=KEY):
    w = original()
    raw = cas.genesis(
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=bytes.fromhex(key))
    return {
        "path": cas.STATE_PATH, "type": "file",
        "encoding": "base64", "sha": cas.blob_sha(raw),
        "content": b64encode(raw).decode(),
    }


def public_comment(source):
    w = original()
    digest = boot.public_head_commitment(
        nonce=w["original_public_genesis_nonce"],
        private_blob_sha=source["sha"])
    return {
        "id": int(COMMENT_ID),
        "body": boot.public_comment(
            digest=digest,
            run_url=f"https://github.com/nicobouch97/fund100-research/actions/runs/{RUN_ID}"),
        "issue_url": r.ORIGINAL_PUBLIC_ISSUE_URL,
        "user": {"login": "github-actions[bot]"},
    }


def verify(src=None, comment=None, key=KEY):
    src = signed_genesis() if src is None else src
    comment = public_comment(src) if comment is None else comment
    return r.validate_sources(
        private_source=src, issue_comment=comment,
        public_comment_id=COMMENT_ID, bootstrap_run_id=RUN_ID,
        hmac_hex=key)


def test_exact_original_signed_git_blob_and_public_commitment_complete_readonly():
    x = verify()
    assert x["schema"] == r.SCHEMA
    assert x["status"] == "GENESIS_CONTENT_AND_PUBLIC_HASH_WITNESS_RECONFIRMED_READONLY"
    assert x["source_original_public_witness_proven"]
    assert x["private_genesis_HMAC_signature_and_original_account_binding_verified"]
    assert x["original_git_content_blob_SHA_matches_bytes"]
    assert x["independent_public_issue8_comment_digest_and_identity_verified"]
    assert x["private_ledger_sequence"] == 0
    assert x["original_empty_entries_count"] == 0
    assert not x["independently_immutable_rollback_anchor_proven"]
    assert not x["future_private_head_progression_recovery_authorized"]
    assert not x["production_trade_order_submission_authorized"]
    assert x["read_only_private_gets"] == 3
    assert x["read_only_public_gets"] == 1
    assert x["private_git_writes"] == x["broker_requests"] == x["broker_orders"] == 0
    assert x["private_raw_bytes"] is x["private_git_blob_sha"] is None
    assert x["hmac_key_or_signature"] is x["account_binding_or_account_id"] is None


@pytest.mark.parametrize("mutation", [
    {"id": 42}, {"body": "not same commitment"},
    {"issue_url": "https://api.github.com/repos/elsewhere/repo/issues/8"},
    {"user": {"login": "attacker"}}, {"user": {}},
    {"body": None}, {"id": "987654321"},
])
def test_public_audit_comment_tampering_or_wrong_issuer_fails_closed(mutation):
    source=signed_genesis()
    altered={**public_comment(source), **mutation}
    with pytest.raises(r.RecoveryStop, match="commitment"):
        verify(src=source,comment=altered)


def test_missing_public_comment_always_blocks():
    with pytest.raises(r.RecoveryStop):
        verify(comment={})


def test_missing_private_state_always_blocks_no_auto_bootstrap():
    with pytest.raises(r.RecoveryStop, match="signed Git genesis invalid"):
        verify(src={})


def test_original_PRIVATE_HMAC_wrong_key_and_wrong_signature_fail():
    source=signed_genesis()
    for key in ("10"*32, "", "a"*64):
        with pytest.raises(r.RecoveryStop):
            verify(src=source,key=key)


def test_sha_or_base64_tamper_rejected_even_if_public_comment_matches_forger():
    source=signed_genesis()
    bad={**source,"content":source["content"] + "AA"}
    with pytest.raises(r.RecoveryStop):
        verify(src=bad,comment=public_comment(bad))
    bad2={**source,"sha":"0"*40}
    with pytest.raises(r.RecoveryStop):
        verify(src=bad2,comment=public_comment(bad2))


def test_wrong_original_private_account_binding_fails_with_valid_alternate_HMAC():
    w=original()
    raw=cas.genesis(
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256="c"*64, key=bytes.fromhex(KEY))
    source={
        "path":cas.STATE_PATH, "type":"file", "encoding":"base64",
        "sha":cas.blob_sha(raw), "content":b64encode(raw).decode(),
    }
    with pytest.raises(r.RecoveryStop):
        verify(src=source,comment=public_comment(source))


def test_recovery_must_not_treat_later_sequence_as_covered_by_genesis_anchor():
    w=original()
    raw=cas.genesis(
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=bytes.fromhex(KEY))
    content=json.loads(raw)
    content.pop("signature")
    content["sequence"]=1
    content["prior_document_sha"]=cas.blob_sha(raw)
    future=cas._canon(dict(
        content, signature=cas._seal(content,bytes.fromhex(KEY))))
    source={
        "path":cas.STATE_PATH,"type":"file","encoding":"base64",
        "sha":cas.blob_sha(future),"content":b64encode(future).decode(),
    }
    with pytest.raises(r.RecoveryStop,match="no longer initial"):
        verify(src=source,comment=public_comment(source))


def test_public_issue8_commitment_from_different_signed_head_fails():
    original_source=signed_genesis()
    bad_comment=public_comment(original_source)
    bad_comment["body"]=bad_comment["body"].replace(
        "Private Git blob SHA256 commitment: ",
        "Private Git blob SHA256 commitment: f")
    with pytest.raises(r.RecoveryStop):
        verify(src=original_source,comment=bad_comment)


def test_incorrect_external_run_id_or_comment_id_fails():
    source=signed_genesis()
    good=public_comment(source)
    for number in ("","0","-1","evil","1/2","99999999999999999999"):
        with pytest.raises(r.RecoveryStop):
            r.validate_sources(private_source=source, issue_comment=good,
                               public_comment_id=number,
                               bootstrap_run_id=RUN_ID, hmac_hex=KEY)
    with pytest.raises(r.RecoveryStop):
        r.validate_sources(private_source=source, issue_comment=good,
                           public_comment_id=COMMENT_ID,
                           bootstrap_run_id="111111", hmac_hex=KEY)


class Response:
    status=200
    def __init__(self, obj):
        self.raw=BytesIO(json.dumps(obj).encode())
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def read(self,n):
        return self.raw.read(n)


def fake_identity(*,url,token):
    assert token==READ_TOKEN
    if url==identity.BASE:
        return {"full_name":identity.EXPECTED_REPO,
                "id":int(identity.EXPECTED_REPO_ID),
                "private":True,"default_branch":"main",
                "archived":False}
    assert url==identity.BASE+"/contents/README.md?ref=main"
    return {"path":"README.md","type":"file","encoding":"base64",
            "sha":"a"*40,"content":"IyB0ZXN0"}


def test_restart_runtime_reads_only_two_original_auth_gets_and_two_source_gets():
    src=signed_genesis()
    comm=public_comment(src)
    called=[]
    def private(req,timeout):
        called.append((req.get_method(),req.full_url,req.get_header("Authorization")))
        assert timeout==12
        return Response(src)
    def public(req,timeout):
        called.append((req.get_method(),req.full_url,req.get_header("Authorization")))
        assert timeout==12
        return Response(comm)
    x=r.runtime(public_comment_id=COMMENT_ID,bootstrap_run_id=RUN_ID,
                read_token=READ_TOKEN,hmac_hex=KEY,public_token=PUBLIC_TOKEN,
                private_transport=private,public_transport=public,
                identity_fetch=fake_identity)
    assert x["status"]=="GENESIS_CONTENT_AND_PUBLIC_HASH_WITNESS_RECONFIRMED_READONLY"
    assert called==[
        ("GET",r.ORIGINAL_PRIVATE_URL,"Bearer "+READ_TOKEN),
        ("GET",r.PUBLIC_COMMENT_PREFIX+COMMENT_ID,"Bearer "+PUBLIC_TOKEN),
    ]


def test_missing_keys_or_http_404_and_wrong_path_fail_without_write():
    with pytest.raises(r.RecoveryStop):
        r._get(url="https://api.github.com/repos/evil/repo",token=PUBLIC_TOKEN)
    def missing(req,timeout):
        raise HTTPError(req.full_url,404,"missing",None,None)
    with pytest.raises(r.RecoveryStop):
        r.runtime(public_comment_id=COMMENT_ID,bootstrap_run_id=RUN_ID,
                  read_token=READ_TOKEN,hmac_hex=KEY,public_token=PUBLIC_TOKEN,
                  private_transport=missing,identity_fetch=fake_identity)


def test_recovery_script_has_no_Git_MUTATION_or_alpaca_source():
    src=Path(r.__file__).read_text()
    for forbidden in (
        "FUND100_PRIVATE_STATE_SANDBOX_WRITE_TOKEN",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
        "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET", "/v2/orders",
        "place_order(", "method=\"PUT\"", "method='PUT'",
        "method=\"POST\"", "method='POST'",
    ):
        assert forbidden not in src
    assert r.NO_PRIVATE_GIT_WRITE and r.NO_ALPACA_NETWORK and r.NO_LIVE_ORDER_RELEASE
