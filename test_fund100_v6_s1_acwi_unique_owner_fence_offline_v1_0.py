"""Synthetic owner-unique original ACWI private Git Contents CAS fencing tests."""
from base64 import b64decode,b64encode
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as f
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import test_fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as fx

OWNER1="39812340001"
OWNER2="39812340002"
BROKER_RUN="39807652211"
SHA="a"*40
NONCE1="1"*64
NONCE2="2"*64

def as_fence(raw):
    return {"type":"file","path":f.PATH,"encoding":"base64",
            "sha":cas.blob_sha(raw),"content":b64encode(raw).decode("ascii")}

def setup():
    reserved,c0,c1=fx.start()
    w=witness.verify()
    raw=f.synthetic_fence_genesis(
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=fx.KEY)
    return {
        "fence_source":as_fence(raw),
        "reserved_source":reserved,
        "genesis_comment":c0,"first_comment":c1,
        "first_comment_id":fx.FIRST_COMMENT_ID,
        "first_run_id":fx.FIRST_RUN_ID,
        "original_qty":fx.QUANTITY,"key":fx.KEY,
        "owner_run_id":OWNER1,"owner_attempt":1,
        "owner_nonce":NONCE1,
        "current_main_sha":SHA,"source_broker_run_id":BROKER_RUN,
    }

class FakePrivateContents:
    def __init__(self,source):
        self.head=deepcopy(source)
        self.put_attempts=0
    def cas(self,plan):
        self.put_attempts+=1
        if self.head["sha"]!=plan["fake_only_commit"]["expected_current_sha"]:
            return 409
        payload=b64decode(plan["fake_only_commit"]["content_base64"],validate=True)
        self.head=as_fence(payload)
        assert self.head["sha"]==plan["proposed_blob_sha"]
        return 200

def verify_args(plan,db):
    p=deepcopy(plan)
    p["current_fence_source"]=db.head
    del p["fence_source"]
    return p

def test_signed_owner_specific_claims_are_distinct_from_same_original_private_seq2():
    p=setup()
    a=f.plan_unique_owner(**p)
    q={**p,"owner_run_id":OWNER2,"owner_nonce":NONCE2}
    b=f.plan_unique_owner(**q)
    assert a["expected_current_sha"]==b["expected_current_sha"]
    assert a["proposed_blob_sha"]!=b["proposed_blob_sha"]
    assert a["stage"]=="SYNTHETIC_UNIQUE_OWNER_CAS_PLAN_NOT_EXECUTABLE"
    assert not a["claim_is_a_LIVE_order_permit"] and not a["claim_is_a_restart_retry_permit"]
    assert a["real_private_Git_PUTs"]==a["broker_POSTs"]==0
    for raw in (a["fake_only_commit"]["content_base64"],b["fake_only_commit"]["content_base64"]):
        payload=b64decode(raw)
        assert fx.QUANTITY.encode() not in payload
        assert fx.KEY not in payload
        assert bytes.fromhex(NONCE1) not in payload
        assert bytes.fromhex(NONCE2) not in payload
    assert f.PRODUCTION_FENCE_CREATED is False
    assert f.FENCED_LIVE_ORDER_RELEASED is False

def test_concurrent_owners_only_one_git_CAS_wins_and_loser_never_claims():
    p=setup()
    a=f.plan_unique_owner(**p)
    q={**p,"owner_run_id":OWNER2,"owner_nonce":NONCE2}
    b=f.plan_unique_owner(**q)
    git=FakePrivateContents(p["fence_source"])
    assert git.cas(a)==200
    assert git.cas(b)==409
    result=f.verify_claimed_owner(**verify_args(p,git))
    assert result["stage"]=="OFFLINE_SIGNED_OWNER_MATCHES_ORIGINAL_ACWI_NO_ORDER_RELEASE"
    assert result["unique_original_workflow_owner_HMAC_recognized"]
    assert result["source_signed_reserved_and_prepost_HEADs_bound"]
    assert not result["claimed_fence_head_immutable_outside_GitHub"]
    assert not result["LIVE_order_released"]
    assert not result["restarted_same_owner_can_submit"]
    assert not result["different_owner_can_submit"]
    assert result["real_Git_writes"]==result["real_broker_POSTs"]==0
    assert result["fence_blob_sha"] is None
    assert result["owner_run_id"] is None
    with pytest.raises(f.FenceStop,match="Different original signed owner"):
        f.verify_claimed_owner(**verify_args(q,git))
    with pytest.raises(f.FenceStop,match="already claimed"):
        f.plan_unique_owner(**{**q,"fence_source":git.head})
    with pytest.raises(f.FenceStop,match="already claimed"):
        f.plan_unique_owner(**{**p,"fence_source":git.head})

def test_timeout_after_realistic_fake_CAS_re_read_only_no_new_post():
    p=setup()
    plan=f.plan_unique_owner(**p)
    fake=FakePrivateContents(p["fence_source"])
    assert fake.cas(plan)==200
    # The API response was LOST. A careful caller can identify the old
    # winning run/nonce on signed state; it still has NO right to resubmit.
    recovered=f.verify_claimed_owner(**verify_args(p,fake))
    assert recovered["timed_out_runner_may_resend"] is False
    with pytest.raises(f.FenceStop):
        f.plan_unique_owner(**{**p,"fence_source":fake.head})
    assert fake.put_attempts==1

@pytest.mark.parametrize("change",[
    lambda d:d.update(owner_run_id=OWNER2),
    lambda d:d.update(owner_nonce=NONCE2),
    lambda d:d.update(owner_attempt=2),
    lambda d:d.update(current_main_sha="b"*40),
    lambda d:d.update(source_broker_run_id="39807652212"),
    lambda d:d.update(original_qty="0.123456788"),
    lambda d:d["first_comment"].update(body="tampered public witness"),
    lambda d:d["reserved_source"].update(sha="f"*40),
])
def test_forged_rerun_other_main_broker_identity_shares_or_source_never_owns(change):
    p=setup();fake=FakePrivateContents(p["fence_source"])
    assert fake.cas(f.plan_unique_owner(**p))==200
    bad=verify_args(p,fake)
    change(bad)
    with pytest.raises(f.FenceStop):
        f.verify_claimed_owner(**bad)

@pytest.mark.parametrize("mutate",[
    lambda d:d.update(sha="0"*40),
    lambda d:d.update(content="invalid"),
    lambda d:d.update(path=cas.STATE_PATH),
    lambda d:d.update(encoding="utf-8"),
])
def test_head_tampering_must_not_pass_as_owner(mutate):
    p=setup();fake=FakePrivateContents(p["fence_source"])
    fake.cas(f.plan_unique_owner(**p))
    bad=verify_args(p,fake)
    mutate(bad["current_fence_source"])
    with pytest.raises(f.FenceStop):
        f.verify_claimed_owner(**bad)

def test_even_valid_HMAC_claim_cannot_extend_a_forged_old_fence_parent():
    from json import loads
    p=setup()
    fake=FakePrivateContents(p["fence_source"])
    fake.cas(f.plan_unique_owner(**p))
    old=loads(b64decode(fake.head["content"],validate=True))
    old.pop("signature")
    old["prior_document_sha"]="f"*40
    old["signature"]=f._seal(old,fx.KEY)
    fake.head=as_fence(f._canon(old))
    with pytest.raises(f.FenceStop,match="exact signed initial HEAD"):
        f.verify_claimed_owner(**verify_args(p,fake))

def test_absent_remote_fence_not_implicitly_initialised():
    p=setup()
    for bad in (None,{"status":404},{}):
        with pytest.raises(f.FenceStop):
            f.plan_unique_owner(**{**p,"fence_source":bad})
    with pytest.raises(f.FenceStop):
        f.verify_claimed_owner(**verify_args(p,FakePrivateContents(p["fence_source"])))

def test_nonce_and_owner_attempt_requires_distinct_valid_inputs():
    p=setup()
    for change in (
        {"owner_nonce":"0"*64},
        {"owner_nonce":"x"*64},
        {"owner_attempt":True},
        {"owner_attempt":0},
        {"owner_run_id":"abc"},
        {"source_broker_run_id":0},
    ):
        with pytest.raises(f.FenceStop):
            f.plan_unique_owner(**{**p,**change})

def test_signed_fence_cannot_be_treated_as_live_transport_or_external_immutable_anchor():
    source=Path(f.__file__).read_text()
    for blocked in ("urlopen(", "Request(", "requests.", "subprocess.",
                    "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
                    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"):
        assert blocked not in source
    assert f.NO_ALPACA_NETWORK and f.NO_PRIVATE_NETWORK
    assert not f.FENCED_LIVE_ORDER_RELEASED
    assert not f.PRODUCTION_FENCE_CREATED
