"""Uncredentialed negative source authentication tests: fake GitHub metadata."""
from copy import deepcopy
import pytest
import fund100_v6_s1_two_principal_readonly_handoff_v1_0 as h

SHA="a"*40
def fx():
    original={
        "id":39807652211,
        "run_attempt":1,
        "repository":{"full_name":h.REPO},
        "head_repository":{"full_name":h.REPO},
        "workflow_id":h.BROKER_WORKFLOW_ID,
        "path":h.BROKER_WORKFLOW_PATH,
        "name":h.BROKER_WORKFLOW_NAME,
        "head_branch":"main",
        "head_sha":SHA,
        "event":"push",
        "status":"completed","conclusion":"success",
        "created_at":"2026-10-22T16:24:00Z",
        "updated_at":"2026-10-22T16:24:25Z",
    }
    broker={
        "name":h.BROKER_JOB,"status":"completed","conclusion":"success",
        "started_at":"2026-10-22T16:24:12Z",
        "completed_at":"2026-10-22T16:24:23Z",
        "steps":[{"name":n,"status":"completed","conclusion":"success",
                  "started_at":began,"completed_at":end}
                 for n,began,end in zip(h.REQUIRED_BROKER_STEPS,
                   ("2026-10-22T16:24:14Z","2026-10-22T16:24:17Z","2026-10-22T16:24:20Z"),
                   ("2026-10-22T16:24:16Z","2026-10-22T16:24:19Z","2026-10-22T16:24:22Z"))]
    }
    offline={"name":h.OFFLINE_JOB,"status":"completed","conclusion":"success",
             "steps":[]}
    return {"run":original,"jobs":{"total_count":2,"jobs":[offline,broker]},
            "checked_main_sha":SHA,"observed_at_utc":"2026-10-22T16:25:00Z"}

def test_exact_two_principal_source_and_redacted_status_only():
    x=h.verify(**fx())
    assert x["status"]=="TWO_PRINCIPAL_SOURCE_HANDOFF_READY_FOR_SEPARATE_SIGNED_READ"
    assert x["original_broker_redacted_three_404_condition_enforced_by_upstream_job"]
    assert x["separate_private_HMAC_GET_still_required"]
    assert x["actual_original_seven_GET_step_freshness_verified"]
    assert not x["orders_authorized"]
    assert not x["broker_404_never_POST_guarantee"]
    assert not x["external_witness_is_immutable_antirollback"]
    assert x["real_broker_POSTs"]==x["real_private_Git_PUTs"]==0
    assert x["private_head"] is x["account_ID"] is x["shares"] is None

@pytest.mark.parametrize("field,value",[
    ("workflow_id",123),("path","elsewhere.yml"),("name","impostor"),
    ("head_branch","feature"),("head_sha","b"*40),("event","pull_request"),
    ("status","in_progress"),("conclusion","failure"),
    ("repository",{"full_name":"attacker/project"}),
    ("head_repository",{"full_name":"attacker/project"}),
    ("run_attempt",0),("id",0),
])
def test_workflow_source_relabeling_and_pull_requests_fail(field,value):
    b=fx();b["run"][field]=value
    with pytest.raises(h.HandoffStop):h.verify(**b)

@pytest.mark.parametrize("status,conclusion",[
    ("completed","skipped"),("completed","failure"),
    ("in_progress",None),("queued",None),
])
def test_private_broker_job_skipped_failed_or_unfinished_is_not_evidence(status,conclusion):
    b=fx();b["jobs"]["jobs"][1].update(status=status,conclusion=conclusion)
    with pytest.raises(h.HandoffStop):h.verify(**b)

def test_privileged_job_required_get_script_and_stop_steps():
    for which in h.REQUIRED_BROKER_STEPS:
        b=fx()
        b["jobs"]["jobs"][1]["steps"]=[
            v for v in b["jobs"]["jobs"][1]["steps"] if v["name"]!=which]
        with pytest.raises(h.HandoffStop):h.verify(**b)
    b=fx()
    b["jobs"]["jobs"][1]["steps"][0]["conclusion"]="skipped"
    with pytest.raises(h.HandoffStop):h.verify(**b)

@pytest.mark.parametrize("value",[
    "2026-10-22T16:40:00Z", # too old
    "2026-10-22T16:24:24Z", # observed before GitHub completion
    "2026-10-22T16:25:00+00:00", # noncanonical format
])
def test_stale_future_or_noncanonical_observation_rejected(value):
    b=fx();b["observed_at_utc"]=value
    with pytest.raises(h.HandoffStop):h.verify(**b)

def test_missing_pagination_duplicate_jobs_and_unsuccessful_offline_test_rejected():
    b=fx();b["jobs"]["total_count"]=100
    with pytest.raises(h.HandoffStop):h.verify(**b)
    b=fx();b["jobs"]["jobs"][0]["name"]=h.BROKER_JOB
    with pytest.raises(h.HandoffStop):h.verify(**b)
    b=fx();b["jobs"]["jobs"][0]["conclusion"]="failure"
    with pytest.raises(h.HandoffStop):h.verify(**b)

def test_main_sha_must_be_source_bound_to_checked_out_commit():
    b=fx();b["checked_main_sha"]="b"*40
    with pytest.raises(h.HandoffStop):h.verify(**b)

def test_no_broker_or_github_network_writer_in_handoff_source():
    from pathlib import Path
    s=Path(h.__file__).read_text()
    for needle in ('urlopen(', 'requests.', 'urllib.', 'Request(',
                   'subprocess.', 'ALPACA_LIVE_KEY',
                   'FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN',
                   'FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX', 'writer.submit'):
        assert needle not in s
    assert h.ALPACA_CREDENTIALS_INCLUDED is False
    assert h.PRIVATE_GIT_WRITER_INCLUDED is False
    assert h.FUNDED_TRADING_ENABLED is False

def test_stale_actual_broker_GET_rejected_even_when_run_metadata_recent():
    b=fx()
    b["run"]["created_at"]="2026-10-22T16:10:00Z"
    broker=b["jobs"]["jobs"][1]
    broker["started_at"]="2026-10-22T16:10:03Z"
    broker["completed_at"]="2026-10-22T16:10:20Z"
    for i,step in enumerate(broker["steps"]):
        step["started_at"]=f"2026-10-22T16:10:{4+i*3:02d}Z"
        step["completed_at"]=f"2026-10-22T16:10:{5+i*3:02d}Z"
    # GitHub run summary updated recently, but actual GET was 15m ago.
    with pytest.raises(h.HandoffStop,match="Actual original seven-GET"):
        h.verify(**b)

@pytest.mark.parametrize("changed",[
    lambda b:b["jobs"]["jobs"][1]["steps"][1].update(completed_at=None),
    lambda b:b["jobs"]["jobs"][1]["steps"][1].update(started_at="2026-10-22T16:24:26Z"),
    lambda b:b["jobs"]["jobs"][1]["steps"][1].update(completed_at="2026-10-22T16:24:05Z"),
    lambda b:b["jobs"]["jobs"][1]["steps"][0].update(completed_at="2026-10-22T16:24:20Z"),
    lambda b:b["jobs"]["jobs"][1].update(started_at="2026-10-22T16:25:00Z"),
    lambda b:b["jobs"]["jobs"][1].update(completed_at="2026-10-22T16:25:05Z"),
])
def test_out_of_order_missing_or_future_true_GET_step_timestamps_fail(changed):
    b=fx()
    changed(b)
    with pytest.raises(h.HandoffStop):
        h.verify(**b)


def risk_fx():
    x=fx()
    run=x["run"]
    run["workflow_id"]=h.RISK_WORKFLOW_ID
    run["path"]=h.RISK_WORKFLOW_PATH
    run["name"]=h.RISK_WORKFLOW_NAME
    jobs=x["jobs"]["jobs"]
    jobs[0]["name"]=h.RISK_OFFLINE_JOB
    jobs[1]["name"]=h.RISK_JOB
    for item,name in zip(jobs[1]["steps"],h.REQUIRED_RISK_STEPS):
        item["name"]=name
    # The step is skipped on a source-risk HOLD; no numeric return leaks
    # from the original protected reader or GitHub log into this fixture.
    jobs[1]["steps"].insert(2,{
        "name":h.RISK_PASS_STEP,
        "status":"completed","conclusion":"skipped",
        "started_at":None,"completed_at":None,
    })
    return x


def signed_empty_genesis():
    return {
        "status":"GENESIS_CONTENT_AND_PUBLIC_HASH_WITNESS_RECONFIRMED_READONLY",
        "private_genesis_HMAC_signature_and_original_account_binding_verified":True,
        "independent_public_issue8_comment_digest_and_identity_verified":True,
        "private_ledger_sequence":0,
        "original_empty_entries_count":0,
        "private_git_writes":0,
        "broker_orders":0,
        "independently_immutable_rollback_anchor_proven":False,
    }


def test_current_main_risk_broker_and_independent_signed_genesis_join_stays_stopped():
    src=h.verify_any_source(**risk_fx())
    assert src["status"]=="CURRENT_RISK_SOURCE_STOP_READY_FOR_PRIVATE_HMAC_READ"
    assert src["same_main_SHA_and_fresh_GET_step_verified"]
    assert not src["cashflow_adjusted_1M_account_risk_approved"]
    result=h.join_current_risk_and_signed_genesis(
        source=src,genesis=signed_empty_genesis())
    assert result["status"]=="STOPPED_REAL_RISK_AND_SIGNED_EMPTY_LEDGER_READS_JOINED"
    assert result["source_and_signed_genesis_proven_in_same_protected_workflow"]
    assert not result["orders_authorized"]
    assert result["broker_POSTs"]==result["private_Git_PUTs"]==0
    assert result["private_account_data"] is result["private_signed_ledger"] is None


@pytest.mark.parametrize("field,value",[
    ("workflow_id",h.BROKER_WORKFLOW_ID),
    ("head_sha","b"*40),("event","pull_request"),
    ("head_branch","attacker-branch"),("conclusion","failure"),
    ("path","falsified-source.yml"),
])
def test_risk_source_rejects_other_run_provenance(field,value):
    x=risk_fx();x["run"][field]=value
    with pytest.raises(h.HandoffStop):
        h.verify_any_source(**x)


@pytest.mark.parametrize("bad",[
    "missing-step","failed-step","swapped-step","duplicate-job",
    "failed-offline","stale-step","extra-job",
])
def test_risk_handoff_requires_original_protected_step_evidence(bad):
    x=risk_fx()
    broker=x["jobs"]["jobs"][1]
    if bad=="missing-step":
        broker["steps"].pop(1)
    elif bad=="failed-step":
        broker["steps"][1]["conclusion"]="skipped"
    elif bad=="swapped-step":
        broker["steps"][1]["name"]="Submit Alpaca order"
    elif bad=="duplicate-job":
        x["jobs"]["jobs"][0]["name"]=h.RISK_JOB
    elif bad=="failed-offline":
        x["jobs"]["jobs"][0]["conclusion"]="failure"
    elif bad=="stale-step":
        broker["steps"][1]["completed_at"]="2026-10-22T16:17:19Z"
    elif bad=="extra-job":
        x["jobs"]["total_count"]=3
    with pytest.raises(h.HandoffStop):
        h.verify_any_source(**x)


@pytest.mark.parametrize("change",[
    {"private_ledger_sequence":1},
    {"original_empty_entries_count":1},
    {"private_genesis_HMAC_signature_and_original_account_binding_verified":False},
    {"independent_public_issue8_comment_digest_and_identity_verified":False},
    {"private_git_writes":1},
    {"broker_orders":1},
    {"independently_immutable_rollback_anchor_proven":True},
    {"status":"UNVERIFIED_SIGNATURE"},
])
def test_private_signed_ledger_or_anchor_unproved_blocks_risk_join(change):
    g=signed_empty_genesis();g.update(change)
    with pytest.raises(h.HandoffStop):
        h.join_current_risk_and_signed_genesis(
            source=h.verify_any_source(**risk_fx()),genesis=g)


def test_old_order_client_id_handoff_unchanged_and_cannot_fake_risk_join():
    original=h.verify_any_source(**fx())
    assert original["status"]=="TWO_PRINCIPAL_SOURCE_HANDOFF_READY_FOR_SEPARATE_SIGNED_READ"
    with pytest.raises(h.HandoffStop):
        h.join_current_risk_and_signed_genesis(
            source=original,genesis=signed_empty_genesis())


def test_original_one_workflow_handles_both_broker_sources_no_trading_release():
    from pathlib import Path
    s=Path(".github/workflows/fund100-v6-s1-two-principal-readonly-handoff.yml").read_text()
    assert h.RISK_WORKFLOW_NAME in s
    assert h.BROKER_WORKFLOW_NAME in s
    assert s.count("h.verify_any_source(")==2
    assert "h.join_current_risk_and_signed_genesis(" in s
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in s
    assert "ALPACA_LIVE_KEY" not in s
    assert "ALPACA_LIVE_SECRET" not in s


def test_protected_pass_marker_reaches_signed_genesis_join_without_trade_release():
    x=risk_fx()
    marker=next(z for z in x["jobs"]["jobs"][1]["steps"]
                if z["name"]==h.RISK_PASS_STEP)
    marker.update(status="completed",conclusion="success",
                  started_at="2026-10-22T16:24:19Z",
                  completed_at="2026-10-22T16:24:20Z")
    source=h.verify_any_source(**x)
    assert source["source_verified_postfunding_6_20_35"] is True
    joined=h.join_current_risk_and_signed_genesis(
        source=source,genesis=signed_empty_genesis())
    assert joined["postfunding_account_6_20_35_read_evidence"] is True
    assert joined["risk_source_approved_for_live_orders"] is False
    assert joined["orders_authorized"] is False


@pytest.mark.parametrize("tamper",[
    "missing","duplicate","failed","uncompleted",
    "before_source","after_stop","unknown_conclusion",
])
def test_untrusted_account_risk_pass_step_is_not_allowed_into_signed_handoff(tamper):
    x=risk_fx()
    steps=x["jobs"]["jobs"][1]["steps"]
    index=next(i for i,z in enumerate(steps) if z["name"]==h.RISK_PASS_STEP)
    marker=steps[index]
    if tamper=="missing":steps.pop(index)
    elif tamper=="duplicate":steps.append(dict(marker))
    elif tamper=="failed":marker["conclusion"]="failure"
    elif tamper=="uncompleted":marker["status"]="in_progress"
    elif tamper=="unknown_conclusion":marker["conclusion"]="neutral"
    elif tamper=="before_source":
        marker.update(conclusion="success",started_at="2026-10-22T16:24:15Z",
                      completed_at="2026-10-22T16:24:16Z")
    elif tamper=="after_stop":
        marker.update(conclusion="success",started_at="2026-10-22T16:24:23Z",
                      completed_at="2026-10-22T16:24:24Z")
    with pytest.raises(h.HandoffStop):
        h.verify_any_source(**x)


def test_skipped_real_risk_step_is_an_explicit_false_not_certification():
    result=h.verify_any_source(**risk_fx())
    assert result["source_verified_postfunding_6_20_35"] is False
    joined=h.join_current_risk_and_signed_genesis(
        source=result,genesis=signed_empty_genesis())
    assert joined["postfunding_account_6_20_35_read_evidence"] is False
    assert joined["orders_authorized"] is False


def signed_acwi_reservation_metadata():
    return {
        "status":"ORIGINAL_ACWI_SIGNED_SEQ1_AND_PUBLIC_HEAD_RECONFIRMED_READONLY",
        "private_genesis_HMAC_signature_and_original_account_binding_verified":True,
        "independent_public_issue8_comment_digest_and_identity_verified":True,
        "private_ledger_sequence":1,
        "first_reserved_symbol":"ACWI",
        "first_reservation_state":"RESERVED_NO_RETRY",
        "original_ACWI_qty_commitment_verified":True,
        "independent_first_successor_public_witness_verified":True,
        "independently_immutable_rollback_anchor_proven":False,
        "production_trade_order_submission_authorized":False,
        "private_git_writes":0,"broker_orders":0,
    }


def test_existing_broker_risk_join_accepts_realshape_verified_seq1_but_never_order():
    source=h.verify_any_source(**risk_fx())
    joined=h.join_current_risk_and_signed_first_reservation(
        source=source,reserved=signed_acwi_reservation_metadata())
    assert joined["status"]=="STOPPED_RISK_AND_FIRST_SIGNED_ACWI_RESERVATION_READS_JOINED"
    assert joined["first_original_signed_ACWI_intent_readback_verified"]
    assert joined["first_reservation_is_no_retry"]
    assert joined["postfunding_account_6_20_35_read_evidence"] is False
    assert joined["orders_authorized"] is False
    assert joined["broker_POSTs"]==joined["private_Git_PUTs"]==0


@pytest.mark.parametrize("change",[
    {"private_ledger_sequence":0},{"private_ledger_sequence":2},
    {"first_reserved_symbol":"EEM"},
    {"first_reservation_state":"POST_MAY_HAVE_BEEN_SENT"},
    {"original_ACWI_qty_commitment_verified":False},
    {"independent_first_successor_public_witness_verified":False},
    {"independently_immutable_rollback_anchor_proven":True},
    {"production_trade_order_submission_authorized":True},
    {"private_git_writes":1},{"broker_orders":1},
    {"status":"PRESENT_UNANCHORED_PRODUCTION_LEDGER_STOP"},
])
def test_private_seq1_recovery_must_be_authenticated_and_initial(change):
    reserved=signed_acwi_reservation_metadata()
    reserved.update(change)
    with pytest.raises(h.HandoffStop):
        h.join_current_risk_and_signed_first_reservation(
            source=h.verify_any_source(**risk_fx()),reserved=reserved)


def test_old_broker_order_id_flow_does_not_claim_new_seq1_risk_evidence():
    with pytest.raises(h.HandoffStop):
        h.join_current_risk_and_signed_first_reservation(
            source=h.verify_any_source(**fx()),
            reserved=signed_acwi_reservation_metadata())


def test_real_fence_single_original_READ_principal_404_is_not_a_GO():
    from urllib.error import HTTPError
    def missing(req,timeout):
        assert timeout==12
        assert req.get_method()=="GET"
        assert req.full_url==h.OWNER_FENCE_GET_URL
        assert req.get_header("Authorization")=="Bearer test-original-read-token-abc123"
        raise HTTPError(req.full_url,404,"missing",None,None)
    out=h.read_current_original_acwi_owner_fence_getonly(
        read_token="test-original-read-token-abc123",hmac_hex="01"*32,
        transport=missing)
    assert out["status"]=="OWNER_FENCE_NOT_VISIBLE_TO_ORIGINAL_READ_PRINCIPAL"
    assert out["read_principal_get_succeeded_as_404"] is True
    assert out["write_principal_absence_independently_verified"] is False
    assert out["owner_fence_signed_head_exists"] is False
    assert out["owner_claim_or_broker_POST_authorized"] is False
    assert out["real_private_Git_PUTs"]==out["broker_orders"]==0
    assert "test-original-read-token" not in str(out)


def test_existing_original_signed_owner_fence_observed_but_never_a_post_permit():
    from base64 import b64encode
    from io import BytesIO
    import json
    import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
    import fund100_v6_s1_public_genesis_witness_v1_0 as witness
    import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
    w=witness.verify()
    hexkey="12"*32
    key=bytes.fromhex(hexkey)
    raw=fence.synthetic_fence_genesis(
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=key)
    source={
        "type":"file","path":fence.PATH,"encoding":"base64",
        "sha":cas.blob_sha(raw),"content":b64encode(raw).decode("ascii")}
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def read(self,n):return BytesIO(json.dumps(source).encode("utf-8")).read(n)
    def got(req,timeout):
        assert req.full_url==h.OWNER_FENCE_GET_URL
        assert req.get_method()=="GET"
        return Response()
    status=h.read_current_original_acwi_owner_fence_getonly(
        read_token="test-original-read-token-abc123",hmac_hex=hexkey,
        transport=got)
    assert status["status"]=="SIGNED_UNCLAIMED_FIRST_ACWI_OWNER_FENCE_READONLY"
    assert status["owner_fence_signed_head_exists"] is True
    assert status["owner_claim_or_broker_POST_authorized"] is False
    assert not status["write_principal_absence_independently_verified"]
    assert status["real_private_Git_PUTs"]==status["broker_orders"]==0
    source["sha"]="0"*40
    with pytest.raises(h.HandoffStop):
        h.read_current_original_acwi_owner_fence_getonly(
            read_token="test-original-read-token-abc123",hmac_hex=hexkey,
            transport=got)


@pytest.mark.parametrize("failure",["forbidden","server","timeout","missing-token",
                                    "invalid-key","not-json","oversize","bad-host-404"])
def test_owner_fence_private_read_rejects_ambiguous_or_untrusted_results(failure):
    from urllib.error import HTTPError,URLError
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def read(self,n):
            return b"x"*26001 if failure=="oversize" else b"not-json"
    def failing(req,timeout):
        if failure=="forbidden":
            raise HTTPError(req.full_url,403,"forbidden",None,None)
        if failure=="server":
            raise HTTPError(req.full_url,500,"server",None,None)
        if failure=="bad-host-404":
            raise HTTPError("https://malicious.example/fake",404,"wrong host",None,None)
        if failure=="timeout":
            raise URLError("timeout")
        return Response()
    if failure=="missing-token":
        token=""
    else:
        token="test-original-read-token-abc123"
    hmac_hex="oops" if failure=="invalid-key" else "01"*32
    with pytest.raises(h.HandoffStop):
        h.read_current_original_acwi_owner_fence_getonly(
            read_token=token,hmac_hex=hmac_hex,transport=failing)


def test_existing_two_principal_handoff_one_private_fence_GET_no_write_secrets():
    from pathlib import Path
    wf=Path(".github/workflows/fund100-v6-s1-two-principal-readonly-handoff.yml").read_text()
    assert "Observe original first ACWI owner fence through ONE private GET principal (NO WRITE)" in wf
    step=wf.split("      - name: Observe original first ACWI owner fence",1)[1]
    step=step.split("      - name: Explicit no-order STOP",1)[0]
    assert "FUND100_PRIVATE_STATE_READ_TOKEN" in step
    assert "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX" in step
    assert "h.read_current_original_acwi_owner_fence_getonly(" in step
    assert "write_principal_absence_independently_verified" in step
    assert "owner_claim_or_broker_POST_authorized" in step
    for denied in ("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
                   "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                   "gh api -X POST","method='PUT'","issues: write",
                   "actions: write"):
        assert denied not in step
    assert not h.PRIVATE_GIT_WRITER_INCLUDED
    assert not h.ALPACA_CREDENTIALS_INCLUDED
    assert not h.FUNDED_TRADING_ENABLED
