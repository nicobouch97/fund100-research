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


def original_seq1_fixture():
    """Full original signed seq1 & public HEAD, not a made-up plain dict."""
    import test_fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as fx
    reserved,first_genesis,first_head=fx.start()
    data=fixture()
    data.update(original_source=reserved,genesis_comment=first_genesis,
                first_comment=first_head,
                first_comment_id=fx.FIRST_COMMENT_ID,
                first_run_id=fx.FIRST_RUN_ID,original_qty=fx.QUANTITY)
    return data


def initial_seq1(d):
    return m.assess_first_reserved_owner_fence_initialization(**{
        k:d[k] for k in (
           "original_source","genesis_comment","first_comment",
           "first_comment_id","first_run_id","original_qty","hmac_hex",
           "read_principal_fence_get","write_principal_fence_get")
    })


def unclaimed_seq1(d):
    return m.validate_first_reserved_unclaimed_owner_fence_readback(**{
        k:d[k] for k in (
           "original_source","genesis_comment","first_comment",
           "first_comment_id","first_run_id","original_qty","hmac_hex",
           "fence_source")
    })


def test_current_original_seq1_signed_ACWI_fence_bootstrap_preflight_is_quiescent():
    d=original_seq1_fixture()
    result=initial_seq1(d)
    assert result["stage"]=="SIGNED_ACWI_SEQ1_OWNER_FENCE_GENESIS_PREFLIGHT_ONLY_NO_WRITE"
    assert result["original_signed_order_ledger_sequence"]==1
    assert result["original_first_ACWI_signed_reservation_verified"]
    assert result["original_first_public_head_witness_verified"]
    assert result["two_independent_absence_assertions_structure_verified"]
    assert result["expected_distinct_initial_signed_HMAC_document_well_formed"]
    assert result["absence_assertions_authentic_GitHub_HTTP_proven"] is False
    assert result["owner_fence_created"] is False
    assert result["future_owner_fence_writer_released"] is False
    assert result["funded_order_authorized"] is False
    assert result["real_GitHub_PUTs"]==result["real_broker_POSTs"]==0


def test_current_seq1_initial_signed_empty_fence_readback_never_claims_order():
    d=original_seq1_fixture()
    report=unclaimed_seq1(d)
    assert report["original_signed_order_ledger_sequence"]==1
    assert report["signed_owner_fence_sequence"]==0
    assert report["original_first_ACWI_signed_reservation_verified"]
    assert report["original_owner_claim_exists"] is False
    assert report["external_immutable_HEAD_watermark_proven"] is False
    assert report["live_sell_released"] is False
    assert report["real_private_Git_PUTs"]==report["real_broker_POSTs"]==0


@pytest.mark.parametrize("fault",[
    "genesis_only","first_comment","first_id","first_run","original_shares",
    "private_sha","private_content","wrong_key","original_genesis_comment",
    "absent_read_is_200","absent_write_is_403","absent_write_is_POST",
])
def test_current_seq1_fence_init_rejects_ambiguous_sources_and_absence(fault):
    d=original_seq1_fixture()
    if fault=="genesis_only":d["original_source"]=fixture()["original_source"]
    elif fault=="first_comment":d["first_comment"]["body"]+="tamper"
    elif fault=="first_id":d["first_comment_id"]="1234567899"
    elif fault=="first_run":d["first_run_id"]="1234567888"
    elif fault=="original_shares":d["original_qty"]="0.123456788"
    elif fault=="private_sha":d["original_source"]["sha"]="0"*40
    elif fault=="private_content":d["original_source"]["content"]="bad"
    elif fault=="wrong_key":d["hmac_hex"]="ab"*32
    elif fault=="original_genesis_comment":d["genesis_comment"]["body"]="tamper"
    elif fault=="absent_read_is_200":d["read_principal_fence_get"]["status"]=200
    elif fault=="absent_write_is_403":d["write_principal_fence_get"]["status"]=403
    elif fault=="absent_write_is_POST":d["write_principal_fence_get"]["http_method"]="POST"
    with pytest.raises(m.OwnerFencePreflightStop):
        initial_seq1(d)


@pytest.mark.parametrize("fault",[
    "sha","content","path","claimed","reserve_changed","first_head_tamper",
])
def test_current_seq1_empty_fence_readback_rejects_mutations(fault):
    d=original_seq1_fixture()
    if fault=="sha":d["fence_source"]["sha"]="0"*40
    elif fault=="content":d["fence_source"]["content"]="bad"
    elif fault=="path":d["fence_source"]["path"]=cas.STATE_PATH
    elif fault=="claimed":
        import test_fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fake
        import test_fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as fx
        args=dict(
            fence_source=d["fence_source"],
            reserved_source=d["original_source"],
            genesis_comment=d["genesis_comment"],
            first_comment=d["first_comment"],
            first_comment_id=d["first_comment_id"],
            first_run_id=d["first_run_id"],
            original_qty=d["original_qty"],
            key=bytes.fromhex(d["hmac_hex"]),
            owner_run_id=fake.OWNER1,owner_attempt=1,
            owner_nonce=fake.NONCE1,current_main_sha=fake.SHA,
            source_broker_run_id=fake.BROKER_RUN)
        candidate=f.plan_unique_owner(**args)
        from base64 import b64decode
        d["fence_source"]=src(f.PATH,b64decode(
            candidate["fake_only_commit"]["content_base64"]))
    elif fault=="reserve_changed":d["original_source"]=fixture()["original_source"]
    elif fault=="first_head_tamper":d["first_comment"]["body"]+="tamper"
    with pytest.raises(m.OwnerFencePreflightStop):
        unclaimed_seq1(d)


def test_existing_exclusive_claim_proof_works_with_same_genuine_shape_seq1():
    import test_fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fx
    from base64 import b64decode
    d=original_seq1_fixture()
    assert initial_seq1(d)["original_signed_order_ledger_sequence"]==1
    both=dict(
        fence_source=d["fence_source"],
        reserved_source=d["original_source"],
        genesis_comment=d["genesis_comment"],
        first_comment=d["first_comment"],
        first_comment_id=d["first_comment_id"],first_run_id=d["first_run_id"],
        original_qty=d["original_qty"],key=bytes.fromhex(d["hmac_hex"]),
        owner_run_id=fx.OWNER1,owner_attempt=1,owner_nonce=fx.NONCE1,
        current_main_sha=fx.SHA,source_broker_run_id=fx.BROKER_RUN,
    )
    candidate=f.plan_unique_owner(**both)
    contender=f.plan_unique_owner(**dict(both,
        owner_run_id=fx.OWNER2,owner_nonce=fx.NONCE2))
    assert candidate["expected_current_sha"]==contender["expected_current_sha"]
    assert candidate["proposed_blob_sha"]!=contender["proposed_blob_sha"]
    winning=src(f.PATH,b64decode(candidate["fake_only_commit"]["content_base64"]))
    yes=f.verify_claimed_owner(**{k:v for k,v in both.items() if k!="fence_source"},
                               current_fence_source=winning)
    assert yes["unique_original_workflow_owner_HMAC_recognized"]
    assert yes["LIVE_order_released"] is False
    assert yes["restarted_same_owner_can_submit"] is False
    with pytest.raises(f.FenceStop):
        f.verify_claimed_owner(
            **{k:v for k,v in dict(both,owner_run_id=fx.OWNER2,
                owner_nonce=fx.NONCE2).items() if k!="fence_source"},
            current_fence_source=winning)
    assert candidate["real_private_Git_PUTs"]==candidate["broker_POSTs"]==0
