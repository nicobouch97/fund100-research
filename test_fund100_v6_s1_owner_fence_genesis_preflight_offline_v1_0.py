"""Offline original HMAC genesis / absent fence / future readback tests."""
from base64 import b64encode
import pytest
import fund100_v6_s1_owner_fence_genesis_preflight_offline_v1_0 as m
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as f
import fund100_v6_s1_public_genesis_witness_v1_0 as w
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as b
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as rec

KEY="0123456789abcdef"*4
def src(path,raw):
    return {"type":"file","path":path,"encoding":"base64",
            "sha":cas.blob_sha(raw),"content":b64encode(raw).decode()}

def fixture():
    d=w.verify()
    original=src(cas.STATE_PATH,cas.genesis(
        private_genesis=d["original_public_genesis_nonce"],
        account_binding_sha256=d["original_live_account_binding_sha256"],
        key=bytes.fromhex(KEY)))
    comment={"id":int(m.GENESIS_COMMENT_ID),
      "body":b.public_comment(
        digest=b.public_head_commitment(
          nonce=d["original_public_genesis_nonce"],
          private_blob_sha=original["sha"]),
        run_url="https://github.com/nicobouch97/fund100-research/actions/runs/"+m.GENESIS_RUN_ID),
      "issue_url":rec.ORIGINAL_PUBLIC_ISSUE_URL,
      "user":{"login":"github-actions[bot]"}}
    def absent(principal):
        return {"principal":principal,"http_method":"GET",
                "fence_path":f.PATH,"status":404,"content":None}
    signed=src(f.PATH,f.synthetic_fence_genesis(
        private_genesis=d["original_public_genesis_nonce"],
        account_binding_sha256=d["original_live_account_binding_sha256"],
        key=bytes.fromhex(KEY)))
    return {"original_source":original,"genesis_comment":comment,
      "hmac_hex":KEY,"read_principal_fence_get":absent("READ"),
      "write_principal_fence_get":absent("WRITE"),"fence_source":signed}

def inspection(d):
    return m.assess_initialization(**{k:d[k] for k in (
        "original_source","genesis_comment","hmac_hex",
        "read_principal_fence_get","write_principal_fence_get")})

def readback(d):
    return m.validate_unclaimed_readback(**{k:d[k] for k in (
        "original_source","genesis_comment","hmac_hex","fence_source")})

def test_absence_and_original_signed_genesis_checked_without_creating():
    v=inspection(fixture())
    assert v["original_signed_order_ledger_sequence"]==0
    assert v["two_independent_absence_assertions_structure_verified"]
    assert not v["absence_assertions_authentic_GitHub_HTTP_proven"]
    assert not v["owner_fence_created"]
    assert v["real_GitHub_PUTs"]==v["real_broker_POSTs"]==0
    assert v["private_Git_sha"] is None

def test_valid_initial_signed_fence_readback_still_does_not_release():
    v=readback(fixture())
    assert v["signed_owner_fence_sequence"]==0
    assert not v["original_owner_claim_exists"]
    assert not v["live_sell_released"]
    assert not v["externally_immutable_rollback_anchor_proven"]

@pytest.mark.parametrize("principal",["READ","WRITE"])
@pytest.mark.parametrize("alter",[
    {"status":200},{"status":403},{"status":True},
    {"content":{}},{"principal":"FORGED"},{"http_method":"POST"},
    {"fence_path":cas.STATE_PATH},
])
def test_both_404_source_observations_are_strict(principal,alter):
    data=fixture()
    key=("read" if principal=="READ" else "write")+"_principal_fence_get"
    data[key].update(alter)
    with pytest.raises(m.OwnerFencePreflightStop):
        inspection(data)

@pytest.mark.parametrize("kind",["issue","sha","key","raw"])
def test_invalid_original_genesis_cannot_create_other_fence(kind):
    d=fixture()
    if kind=="issue": d["genesis_comment"]["body"]="forged"
    elif kind=="sha": d["original_source"]["sha"]="0"*40
    elif kind=="key": d["hmac_hex"]="ab"*32
    else: d["original_source"]["content"]="invalid"
    with pytest.raises(m.OwnerFencePreflightStop):
        inspection(d)

@pytest.mark.parametrize("kind",["sha","content","path"])
def test_unclaimed_fence_readback_fail_closed(kind):
    d=fixture()
    if kind=="sha":d["fence_source"]["sha"]="0"*40
    if kind=="content":d["fence_source"]["content"]="invalid"
    if kind=="path":d["fence_source"]["path"]=cas.STATE_PATH
    with pytest.raises(m.OwnerFencePreflightStop):
        readback(d)

def test_fence_public_digest_has_separate_domain():
    d=fixture();a=w.verify()
    nonce=a["original_public_genesis_nonce"];sha=d["fence_source"]["sha"]
    assert m._digest(nonce=nonce,sha=sha)!=b.public_head_commitment(
        nonce=nonce,private_blob_sha=sha)
    assert len(m._digest(nonce=nonce,sha=sha))==64

def test_entrypoint_is_pure_and_locked():
    assert m.NO_PRIVATE_NETWORK and m.NO_BROKER_NETWORK
    assert m.NO_PRIVATE_GIT_WRITE and m.NO_ORDER_RELEASE
