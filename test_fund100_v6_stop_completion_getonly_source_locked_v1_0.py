"""Offline GET-only source projection tests; no real tokens, broker or writes."""
import base64
from datetime import datetime, timezone
from hashlib import sha1, sha256
import json
from pathlib import Path
from uuid import UUID

import pytest

import fund100_v6_stop_completion_getonly_source_locked_v1_0 as source
import fund100_v6_emergency_stop_completion_evidence_v1_0 as proof

SHA="a"*40
RUN_ID=123456789
ALARM="2026-11-13T16:00:00Z"
NOW=datetime(2026,11,13,16,1,50,tzinfo=timezone.utc)
ACCOUNT_ID="synthetic-account-never-live"
ACCOUNT_SHA=sha256(("FUND100-LIVE-ACCOUNT|"+ACCOUNT_ID).encode()).hexdigest()
STOP_V5={"schema":"FUND100_OPERATOR_CONTROL_V1","trading_enabled":False}
STOP_V6={
    "schema":"FUND100_V6_S1_OPERATOR_CONTROL_V2",
    "risk_level":"HIGH","pilot_capital_ceiling_usd":"130.30",
    "trading_enabled":False,"first_original_acwi_sell_enabled":False,
}


def run():
    return {
        "id":RUN_ID,"name":proof.WORKFLOW_NAME,"path":proof.WORKFLOW,
        "event":"workflow_dispatch","status":"completed","conclusion":"success",
        "head_branch":"main","head_sha":SHA,"run_attempt":1,
        "created_at":"2026-11-13T16:00:30Z",
        "run_started_at":"2026-11-13T16:00:35Z",
        "updated_at":"2026-11-13T16:01:30Z",
    }


def jobs():
    times=(
        ("2026-11-13T16:00:36Z","2026-11-13T16:01:00Z"),
        ("2026-11-13T16:01:02Z","2026-11-13T16:01:20Z"),
        ("2026-11-13T16:01:05Z","2026-11-13T16:01:25Z"),
    )
    out=[]
    for (name,required),(started,finished) in zip(
            proof.REQUIRED_JOBS.items(),times):
        out.append({
            "run_id":RUN_ID,"name":name,"status":"completed",
            "conclusion":"success","head_sha":SHA,
            "started_at":started,"completed_at":finished,
            "steps":[{"name":name,"status":"completed","conclusion":"success"}
                     for name in required],
        })
    return {"total_count":3,"jobs":out}


def control_blob(path, value):
    raw=(json.dumps(value,sort_keys=True)+"\n").encode()
    return {
        "path":path,"type":"file","encoding":"base64",
        "content":base64.b64encode(raw).decode(),
        "sha":sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest(),
    }


class FakeResponse:
    status=200
    wrong_url=None
    def __init__(self, body, url):
        self.body=json.dumps(body).encode()
        self.url=url
    def geturl(self):
        return self.wrong_url or self.url
    def read(self, n):
        return self.body[:n]
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False


class Fixture:
    def __init__(self):
        self.run=run()
        self.jobs=jobs()
        self.v5=dict(STOP_V5)
        self.v6=dict(STOP_V6)
        self.account={"id":ACCOUNT_ID,"status":"ACTIVE"}
        self.orders=[]
        self.github_reads=[]
        self.broker_reads=[]
        self.force_redirect=False
        self.force_status=None

    def opener(self, handler):
        assert isinstance(handler,source._NoRedirect)
        return self

    def open(self, request, timeout):
        assert request.get_method()=="GET"
        assert request.full_url.startswith(source.API+"/")
        assert timeout==8
        self.github_reads.append(request.full_url)
        assert request.get_header("Authorization")=="Bearer OFFLINE_ONLY_READ_TOKEN"
        url=request.full_url
        if url==source.RUN_PREFIX+str(RUN_ID):
            payload=self.run
        elif url==source.RUN_PREFIX+str(RUN_ID)+"/jobs?per_page=100":
            payload=self.jobs
        elif "/contents/"+source.V5_PATH+"?ref=main&nonce=" in url:
            payload=control_blob(source.V5_PATH,self.v5)
        elif "/contents/"+source.V6_PATH+"?ref=main&nonce=" in url:
            payload=control_blob(source.V6_PATH,self.v6)
        else:
            raise AssertionError("Untrusted GitHub URL")
        result=FakeResponse(payload,url)
        if self.force_redirect:
            result.wrong_url="https://attacker.invalid/redirect"
        if self.force_status is not None:
            result.status=self.force_status
        return result

    def broker_get(self, *, path, params, key, secret):
        assert key=="OFFLINE_ONLY_KEY" and secret=="OFFLINE_ONLY_SECRET"
        self.broker_reads.append((path,params))
        if path=="/v2/account":
            assert params is None
            return self.account
        if path=="/v2/orders":
            assert params==source.BROKER_OPEN_ORDER_PARAMS
            return self.orders
        raise AssertionError("Unapproved broker URL")


@pytest.fixture
def eligible_offline(monkeypatch):
    import os
    for name,value in {
        "GITHUB_ACTIONS":"true",
        "GITHUB_REPOSITORY":source.REPO,
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_TOKEN":"OFFLINE_ONLY_READ_TOKEN",
        "FUND100_RISK_LEVEL":"HIGH",
        "FUND100_ENABLE_LIVE_READONLY":"YES_READ_ONLY_LIVE",
        "FUND100_BROKER_KILL_SWITCH":"ENGAGED",
        "FUND100_LIVE_WRITE_MODE":"DISABLED",
    }.items():
        monkeypatch.setenv(name,value)
    monkeypatch.setattr(source,"SOURCE_RELEASED",True)
    monkeypatch.setattr(proof,"STOP_COMPLETION_SOURCE_RELEASED",True)
    monkeypatch.setattr(proof,"EXPECTED_BROKER_ACCOUNT_BINDING_SHA256",
                        ACCOUNT_SHA)
    class FixedUTC(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW
    monkeypatch.setattr(source,"datetime",FixedUTC)
    mock=Fixture()
    monkeypatch.setattr(source,"build_opener",mock.opener)
    monkeypatch.setattr(source.broker,"load_credentials",
                        lambda: ("OFFLINE_ONLY_KEY","OFFLINE_ONLY_SECRET"))
    monkeypatch.setattr(source.broker,"get_json",mock.broker_get)
    return mock


def complete():
    return source.confirm_stop_from_authenticated_gets(
        expected_dispatch_run_id=RUN_ID,alarm_detected_at_utc=ALARM)


def test_production_source_hard_locked_before_any_private_read(monkeypatch):
    assert source.SOURCE_RELEASED is False
    assert all((source.NO_GITHUB_WRITES,source.NO_BROKER_WRITES,
                source.NO_SIGNER_PRIVATE_KEY,source.NO_TRADE_RELEASE,
                source.NO_DISPATCH,source.NO_FILL_GUARANTEE,
                source.NO_STANDALONE_DISPATCH_PROOF))
    monkeypatch.setattr(source,"build_opener",
                        lambda handler: pytest.fail("No GitHub before release"))
    monkeypatch.setattr(source.broker,"load_credentials",
                        lambda: pytest.fail("No broker before release"))
    with pytest.raises(source.StopSourceHold,match="HARD LOCKED"):
        complete()


def test_completed_verified_stop_binds_three_jobs_fresh_main_and_broker_gets(
        eligible_offline):
    mock=eligible_offline
    result=complete()
    assert result["status"]=="CURRENT_STOP_AND_OPEN_ORDER_ABSENCE_OBSERVED"
    assert result["required_stop_and_cancel_jobs_completed"]==3
    assert result["current_main_v5_stop"] is True
    assert result["current_main_v6_stop"] is True
    assert result["broker_fills_or_settlement_verified"] is False
    assert result["no_possible_future_fill_guarantee"] is False
    assert result["new_trading_orders_authorized"] is False
    assert len(mock.github_reads)==4
    assert mock.broker_reads==[
        ("/v2/account",None),
        ("/v2/orders",{"status":"open","limit":500}),
    ]
    assert not any("DELETE" in url or "POST" in url for url in mock.github_reads)


@pytest.mark.parametrize("change", [
    {"status":"queued"},{"status":"in_progress"},{"conclusion":"failure"},
    {"conclusion":"cancelled"},{"event":"schedule"},{"path":"other"},
    {"run_attempt":2},{"run_attempt":True},{"head_branch":"dev"},
])
def test_unfinished_or_wrong_stop_never_reads_broker(
        eligible_offline,monkeypatch,change):
    mock=eligible_offline
    mock.run.update(change)
    monkeypatch.setattr(source.broker,"load_credentials",
                        lambda: pytest.fail("Unqualified STOP read broker"))
    with pytest.raises(source.StopSourceHold):
        complete()
    assert len(mock.github_reads)==2


@pytest.mark.parametrize("failure", [
    "missing","duplicate","skipped","failed","wrongrun",
])
def test_incomplete_jobs_never_reach_broker(
        eligible_offline,monkeypatch,failure):
    mock=eligible_offline
    if failure=="missing":
        mock.jobs["jobs"].pop()
        mock.jobs["total_count"]=2
    elif failure=="duplicate":
        mock.jobs["jobs"][1]["name"]=mock.jobs["jobs"][0]["name"]
    elif failure=="skipped":
        mock.jobs["jobs"][1]["status"]="skipped"
    elif failure=="failed":
        mock.jobs["jobs"][1]["conclusion"]="failure"
    elif failure=="wrongrun":
        mock.jobs["jobs"][1]["run_id"]=1
    monkeypatch.setattr(source.broker,"load_credentials",
                        lambda: pytest.fail("Missing STOP job cannot read Alpaca"))
    with pytest.raises(source.StopSourceHold):
        complete()
    assert len(mock.github_reads)==2


@pytest.mark.parametrize("field,value",[
    ("trading_enabled",True),("trading_enabled",1),
])
def test_active_or_malformed_v5_main_latch_blocks_broker(
        eligible_offline,monkeypatch,field,value):
    mock=eligible_offline
    mock.v5[field]=value
    monkeypatch.setattr(source.broker,"load_credentials",
                        lambda: pytest.fail("Not STOPPED"))
    with pytest.raises(source.StopSourceHold):
        complete()
    assert len(mock.github_reads)==3


@pytest.mark.parametrize("field,value",[
    ("trading_enabled",True),
    ("first_original_acwi_sell_enabled",True),
    ("trading_enabled","false"),
])
def test_v6_latch_requires_both_exact_stops(
        eligible_offline,monkeypatch,field,value):
    mock=eligible_offline
    mock.v6[field]=value
    monkeypatch.setattr(source.broker,"load_credentials",
                        lambda: pytest.fail("V6 not stopped"))
    with pytest.raises(source.StopSourceHold):
        complete()
    assert len(mock.github_reads)==4


def test_broker_account_changed_rejected_after_real_fresh_broker_reads(
        eligible_offline):
    mock=eligible_offline
    mock.account={"id":"another-account","status":"ACTIVE"}
    with pytest.raises(proof.StopCompletionStop,match="binding"):
        complete()
    assert len(mock.broker_reads)==2


def test_fund100_open_order_cannot_be_claimed_cancelled(
        eligible_offline):
    mock=eligible_offline
    mock.orders=[{"client_order_id":"f100live-aaaaaaaaaaaa-s-acwi",
                  "id":"33333333-3333-4333-8333-333333333333"}]
    with pytest.raises(proof.StopCompletionStop,match="remains OPEN"):
        complete()


def test_workflow_success_but_missing_step_still_fails(
        eligible_offline):
    mock=eligible_offline
    mock.jobs["jobs"][0]["steps"].pop()
    with pytest.raises(proof.StopCompletionStop,match="Missing"):
        complete()


def test_no_untrusted_redirect_or_http_status_before_broker_credentials(
        eligible_offline,monkeypatch):
    mock=eligible_offline
    mock.force_redirect=True
    monkeypatch.setattr(source.broker,"load_credentials",
                        lambda: pytest.fail("Redirect cannot access broker"))
    with pytest.raises(source.StopSourceHold,match="origin/status"):
        complete()
    mock.force_redirect=False
    mock.force_status=302
    with pytest.raises(source.StopSourceHold,match="origin/status"):
        complete()


def test_no_caller_chosen_github_endpoint_or_http_write(
        eligible_offline):
    with pytest.raises(source.StopSourceHold,match="Unapproved exact"):
        source._get("https://attacker.invalid/jobs",token="OFFLINE_ONLY_READ_TOKEN")
    with pytest.raises(source.StopSourceHold,match="Unapproved exact"):
        source._get(source.API+"/actions/workflows/x/dispatches",
                    token="OFFLINE_ONLY_READ_TOKEN")
    with pytest.raises(source.StopSourceHold,match="Unapproved exact"):
        source._get(source.API+"/contents/unrelated-key?ref=main",
                    token="OFFLINE_ONLY_READ_TOKEN")


def test_untrusted_dispatch_id_and_alarm_never_read_github(
        eligible_offline):
    mock=eligible_offline
    for value in (True,0,-1,"123456789",None):
        with pytest.raises(source.StopSourceHold):
            source.confirm_stop_from_authenticated_gets(
                expected_dispatch_run_id=value,alarm_detected_at_utc=ALARM)
    assert mock.github_reads==[]


def test_source_never_dispatches_cancels_rearms_or_logs_secrets():
    code=Path(source.__file__).read_text()
    assert "NO_DISPATCH = True" in code
    assert "NO_BROKER_WRITES = True" in code
    assert "SOURCE_RELEASED = False" in code
    assert "def do_POST" not in code
    assert "sign_reviewed_eight_get_result(" not in code
    assert "transport=None" not in code
    assert "http.client.HTTPSConnection" not in code
