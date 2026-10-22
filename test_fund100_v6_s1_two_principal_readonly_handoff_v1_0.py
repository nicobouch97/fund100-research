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
        "steps":[{"name":n,"status":"completed","conclusion":"success"}
                 for n in h.REQUIRED_BROKER_STEPS]
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
