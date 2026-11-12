"""No-network STOP completion evidence from independently projected observations."""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
import fund100_v6_emergency_stop_completion_evidence_v1_0 as proof

SHA="a"*40
ACCOUNT_ID="synthetic-account-never-live"
ACCOUNT_SHA=sha256(("FUND100-LIVE-ACCOUNT|"+ACCOUNT_ID).encode()).hexdigest()
ALARM="2026-11-12T16:00:00Z"
OBS_CONTROL="2026-11-12T16:01:40Z"
OBS_BROKER="2026-11-12T16:01:45Z"
NOW=datetime(2026,11,12,16,1,50,tzinfo=timezone.utc)


def run():
    return {
        "id": 123456789,
        "name":proof.WORKFLOW_NAME,
        "path":proof.WORKFLOW,
        "event":"workflow_dispatch",
        "status":"completed",
        "conclusion":"success",
        "head_branch":"main",
        "head_sha":SHA,
        "run_attempt":1,
        "created_at":"2026-11-12T16:00:30Z",
        "run_started_at":"2026-11-12T16:00:35Z",
        "updated_at":"2026-11-12T16:01:30Z",
    }


def jobs():
    times=(
        ("2026-11-12T16:00:36Z","2026-11-12T16:01:00Z"),
        ("2026-11-12T16:01:02Z","2026-11-12T16:01:20Z"),
        ("2026-11-12T16:01:05Z","2026-11-12T16:01:25Z"),
    )
    result=[]
    for (name, required),(started,finished) in zip(
            proof.REQUIRED_JOBS.items(),times):
        result.append({
            "run_id":123456789,"name":name,"status":"completed",
            "conclusion":"success","head_sha":SHA,
            "started_at":started,"completed_at":finished,
            "steps":[{"name":s,"status":"completed","conclusion":"success"}
                     for s in required],
        })
    return result


def v5():
    return {"schema":"FUND100_OPERATOR_CONTROL_V1",
            "trading_enabled":False}


def v6():
    return {"schema":"FUND100_V6_S1_OPERATOR_CONTROL_V2",
            "risk_level":"HIGH","pilot_capital_ceiling_usd":"130.30",
            "trading_enabled":False,
            "first_original_acwi_sell_enabled":False}


def evidence():
    return {
        "run":run(),"jobs":jobs(),"expected_dispatch_run_id":123456789,
        "v5_control":v5(),"v6_control":v6(),
        "broker_account":{"id":ACCOUNT_ID,"status":"ACTIVE"},
        "broker_open_orders":[],
        "alarm_detected_at_utc":ALARM,
        "controls_observed_at_utc":OBS_CONTROL,
        "broker_observed_at_utc":OBS_BROKER,
        "now_utc":NOW,
    }


@pytest.fixture
def released_only_in_offline_mock(monkeypatch):
    monkeypatch.setattr(proof,"STOP_COMPLETION_SOURCE_RELEASED",True)
    monkeypatch.setattr(proof,"EXPECTED_BROKER_ACCOUNT_BINDING_SHA256",
                        ACCOUNT_SHA)


def verify(**changes):
    data=evidence()
    data.update(changes)
    return proof.verify_emergency_stop_completion(**data)


def test_production_source_is_hard_locked_before_any_get_or_write():
    assert proof.STOP_COMPLETION_SOURCE_RELEASED is False
    assert proof.EXPECTED_BROKER_ACCOUNT_BINDING_SHA256 is None
    assert all((proof.NO_NETWORK,proof.NO_BROKER_WRITE,
                proof.NO_GITHUB_WRITE,proof.NO_ORDER_RELEASE,
                proof.NO_CLAIM_ABOUT_BROKER_FILLS))
    with pytest.raises(proof.StopCompletionStop,match="HARD LOCKED"):
        verify()


def test_synthetic_all_three_jobs_and_current_stops_without_open_orders(
        released_only_in_offline_mock):
    actual=verify()
    assert actual=={
        "schema":proof.SCHEMA,
        "status":"CURRENT_STOP_AND_OPEN_ORDER_ABSENCE_OBSERVED",
        "current_main_v5_stop":True,
        "current_main_v6_stop":True,
        "required_stop_and_cancel_jobs_completed":3,
        "open_fund100_orders_at_observation":0,
        "new_trading_orders_authorized":False,
        "broker_fills_or_settlement_verified":False,
        "no_possible_future_fill_guarantee":False,
        "dispatch_http_200_alone_is_stop_proof":False,
    }


@pytest.mark.parametrize("field,bad", [
    ("id",0),("id",True),("name","Unrelated workflow"),
    ("path",".github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml"),
    ("event","schedule"),("event","push"),
    ("event","repository_dispatch"),
    ("status","queued"),("status","in_progress"),
    ("conclusion","failure"),("conclusion",None),("conclusion","cancelled"),
    ("head_branch","feature/attack"),("head_sha","b"*39),
    ("run_attempt",2),("run_attempt",True),
    ("created_at","2026-11-12T15:59:59Z"),
    ("created_at","2026-11-12T16:01:31Z"),
    ("run_started_at","2026-11-12T16:00:28Z"),
    ("updated_at","2026-11-12T16:03:03Z"),
])
def test_never_accept_wrong_replayed_or_delayed_workflow_run(
        released_only_in_offline_mock,field,bad):
    r=run()
    r[field]=bad
    with pytest.raises(proof.StopCompletionStop):
        verify(run=r)


@pytest.mark.parametrize("failure",[
    "missing_stop","missing_legacy_cancel","missing_signed_cancel",
    "duplicate","extra","job_failure","job_skipped","wrong_run_id",
    "wrong_sha","job_too_late","job_before_start","missing_step",
    "skipped_step","duplicate_step","failed_step","in_progress_step",
    "extra_field","unrecognized_step_job",
])
def test_any_missing_or_unverified_required_job_refuses_stop_claim(
        released_only_in_offline_mock,failure):
    j=jobs()
    if failure=="missing_stop": j.pop(0)
    elif failure=="missing_legacy_cancel": j.pop(1)
    elif failure=="missing_signed_cancel": j.pop(2)
    elif failure=="duplicate": j[1]=deepcopy(j[0])
    elif failure=="extra": j.append(deepcopy(j[2]))
    elif failure=="job_failure": j[0]["conclusion"]="failure"
    elif failure=="job_skipped": j[2]["conclusion"]="skipped"
    elif failure=="wrong_run_id": j[0]["run_id"]=1
    elif failure=="wrong_sha": j[0]["head_sha"]="b"*40
    elif failure=="job_too_late": j[2]["completed_at"]="2026-11-12T16:01:31Z"
    elif failure=="job_before_start": j[0]["started_at"]="2026-11-12T16:00:30Z"
    elif failure=="missing_step": j[0]["steps"].pop(0)
    elif failure=="skipped_step": j[0]["steps"][0]["conclusion"]="skipped"
    elif failure=="duplicate_step": j[0]["steps"].append(deepcopy(j[0]["steps"][0]))
    elif failure=="failed_step": j[1]["steps"][0]["conclusion"]="failure"
    elif failure=="in_progress_step": j[2]["steps"][0]["status"]="in_progress"
    elif failure=="extra_field": j[0]["untrusted_extra"]="untrusted"
    elif failure=="unrecognized_step_job": j[1]["steps"][0]["name"]="Any other job"
    with pytest.raises(proof.StopCompletionStop):
        verify(jobs=j)


@pytest.mark.parametrize("bad",[
    {"schema":"FUND100_OPERATOR_CONTROL_V1","trading_enabled":True},
    {"schema":"FUND100_OPERATOR_CONTROL_V1","trading_enabled":0},
    {"schema":"FUND100_OPERATOR_CONTROL_V1","trading_enabled":"false"},
    {"schema":"WRONG","trading_enabled":False},
    {"schema":"FUND100_OPERATOR_CONTROL_V1"},
    {},
])
def test_v5_stop_must_be_literal_current_boolean_false(
        released_only_in_offline_mock,bad):
    with pytest.raises(proof.StopCompletionStop):
        verify(v5_control=bad)


@pytest.mark.parametrize("key,bad",[
    ("trading_enabled",True),
    ("first_original_acwi_sell_enabled",True),
    ("trading_enabled",0),
    ("first_original_acwi_sell_enabled",0),
    ("pilot_capital_ceiling_usd","1000000"),
    ("risk_level","LOW"),
    ("schema","WRONG"),
])
def test_v6_stop_and_current_risk_mandate_are_exact(
        released_only_in_offline_mock,key,bad):
    state=v6()
    state[key]=bad
    with pytest.raises(proof.StopCompletionStop):
        verify(v6_control=state)


@pytest.mark.parametrize("field,ts",[
    ("controls_observed_at_utc","2026-11-12T16:00:59Z"),
    ("broker_observed_at_utc","2026-11-12T16:00:59Z"),
    ("controls_observed_at_utc","2026-11-12T16:01:19Z"),
    ("broker_observed_at_utc","2026-11-12T16:01:19Z"),
    ("broker_observed_at_utc","2026-11-12T16:01:51Z"),
    ("controls_observed_at_utc","2026-11-12T16:01:59Z"),
    ("broker_observed_at_utc","2026-11-12T16:01:45+00:00"),
])
def test_stale_premature_forged_or_noncanonical_current_observation_fails(
        released_only_in_offline_mock,field,ts):
    with pytest.raises(proof.StopCompletionStop):
        verify(**{field:ts})


@pytest.mark.parametrize("account",[
    {},{"id":""},{"id":None},{"id":"other-account"},
    {"id":9876},None,True,
])
def test_wrong_broker_account_binding_never_claims_stop(
        released_only_in_offline_mock,account):
    with pytest.raises(proof.StopCompletionStop):
        verify(broker_account=account)


@pytest.mark.parametrize("orders",[
    None,{},[None],[{}]*500,
    [{"id":str(uuid4()),"client_order_id":
      "f100live-prod-0123456789abcdef-b-acwi",
      "symbol":"ACWI","side":"buy"}],
    [{"id":str(uuid4()),"client_order_id":
      proof.signed_cancel.SIGNED_FIRST_ACWI_CLIENT_ID,
      "symbol":"ACWI","side":"sell"}],
    [{"id":"non-uuid","client_order_id":
      proof.signed_cancel.SIGNED_FIRST_ACWI_CLIENT_ID,
      "symbol":"ACWI","side":"sell"}],
    [{"id":str(uuid4()),"client_order_id":
      proof.signed_cancel.SIGNED_FIRST_ACWI_CLIENT_ID,
      "symbol":"EEM","side":"sell"}],
])
def test_any_open_fund100_order_truncation_or_unknown_shape_forces_hold(
        released_only_in_offline_mock,orders):
    with pytest.raises(proof.StopCompletionStop):
        verify(broker_open_orders=orders)


def test_unrelated_manually_placed_open_orders_not_targeted(
        released_only_in_offline_mock):
    r=verify(broker_open_orders=[
        {"id":"none-required-for-unrelated","client_order_id":"personal-manual"},
    ])
    assert r["open_fund100_orders_at_observation"]==0
    assert r["broker_fills_or_settlement_verified"] is False


def test_policy_pin_must_be_independent_and_exact(released_only_in_offline_mock,
                                                  monkeypatch):
    monkeypatch.setattr(proof,"EXPECTED_BROKER_ACCOUNT_BINDING_SHA256",None)
    with pytest.raises(proof.StopCompletionStop,match="account/policy"):
        verify()
    monkeypatch.setattr(proof,"EXPECTED_BROKER_ACCOUNT_BINDING_SHA256","a"*64)
    with pytest.raises(proof.StopCompletionStop,match="account binding"):
        verify()



@pytest.mark.parametrize("run_id", [None, 0, -1, True, 123456788, "123456789"])
def test_completion_must_match_exact_run_id_from_authenticated_dispatch(
        released_only_in_offline_mock, run_id):
    with pytest.raises(proof.StopCompletionStop):
        verify(expected_dispatch_run_id=run_id)


def test_github_200_with_run_id_is_still_only_dispatch_not_stop(
        released_only_in_offline_mock):
    # The exact dispatched run can queue, fail or skip cancellation.
    r=run()
    r["status"]="queued"
    with pytest.raises(proof.StopCompletionStop):
        verify(run=r)
    # Even if GitHub reports success, current-main STOP must be observed.
    control=v5()
    control["trading_enabled"]=True
    with pytest.raises(proof.StopCompletionStop):
        verify(v5_control=control)

def test_source_never_dispatches_writes_or_appears_in_live_railway():
    src=Path(proof.__file__).read_text()
    assert "STOP_COMPLETION_SOURCE_RELEASED = False" in src
    assert "EXPECTED_BROKER_ACCOUNT_BINDING_SHA256 = None" in src
    for term in ('method="POST"','method="DELETE"','method="PUT"',
                 "urlopen(","Request(","requests.post(","ALPACA_LIVE_SECRET",
                 "ALPACA_LIVE_KEY","GITHUB_TOKEN"):
        assert term not in src
    docker=Path("Dockerfile").read_text()
    assert "fund100_v6_emergency_stop_completion_evidence_v1_0.py" not in docker
    stop=Path("fund100_v6_external_emergency_stop_dispatch_intent_v1_0.py").read_text()
    assert "STOP_DISPATCH_PLANNING_RELEASED = False" in stop
    assert "HTTP_DISPATCH_TRANSPORT_RELEASED = False" in stop
    assert proof.NO_ORDER_RELEASE and proof.NO_BROKER_WRITE
    assert proof.NO_GITHUB_WRITE and proof.NO_NETWORK


def test_required_job_names_match_actual_protected_manual_stop_workflow():
    workflow=Path(".github/workflows/fund100-live-emergency-stop.yml").read_text()
    assert "on:\n  workflow_dispatch:" in workflow
    for jobname,requiredsteps in proof.REQUIRED_JOBS.items():
        assert "name: "+jobname in workflow
        for s in requiredsteps:
            assert "name: "+s in workflow
    assert "environment: fund100-live-broker" in workflow
