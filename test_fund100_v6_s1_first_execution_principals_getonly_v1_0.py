"""Synthetic-only proof that first execution principals GET cannot mutate."""
from copy import deepcopy
from pathlib import Path
import pytest
import fund100_v6_s1_first_execution_principals_getonly_v1_0 as scope

PATH=Path(".github/workflows/fund100-v6-s1-first-execution-principals-getonly.yml")

@pytest.fixture
def e():
    return {
        "GITHUB_ACTIONS":"true",
        "GITHUB_REPOSITORY":"nicobouch97/fund100-research",
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_RUN_ATTEMPT":"1",
        "GITHUB_EVENT_NAME":"push",
        "FUND100_BROKER_KILL_SWITCH":"ENGAGED",
        "FUND100_RISK_LEVEL":"HIGH",
        "FUND100_PRIVATE_STATE_READ_TOKEN":"dummy-private-read-credential",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN":"dummy-private-write-credential",
        "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN":"dummy-admin-read-credential",
        "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN":"dummy-release-write-credential",
        "GITHUB_TOKEN":"dummy-public-issue-token",
        "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX":"a"*64,
    }

@pytest.fixture
def source(monkeypatch):
    events=[]
    owner={"path":"state/v6_s1_first_acwi_execution_owner_fence.json",
           "sha":"a"*40,"encoding":"base64","content":"fake-owner"}
    ledger={"path":"state/v6_s1_order_attempt_ledger.json",
            "sha":"b"*40,"encoding":"base64","content":"fake-ledger"}
    def owner_get(**kwargs):
        events.append(("owner",kwargs["token"]))
        assert kwargs["transport"] is None
        return deepcopy(owner)
    def order_get(**kwargs):
        events.append(("ledger",kwargs["token"]))
        assert kwargs["transport"] is None
        assert kwargs["url"]==scope.owner.ORIGINAL_ORDER_LEDGER_URL+"?ref=main"
        return deepcopy(ledger)
    def setting_get(**kwargs):
        events.append(("public",kwargs["url"]))
        assert kwargs["method"]=="GET"
        if kwargs["url"]==scope.publication.IMMUTABLE_SETTING_URL:
            return {"enabled":True,"enforced_by_owner":False}
        assert kwargs["url"]==scope.publication.anchor.RELEASE_URL
        assert kwargs["allow_missing"] is True
        return None
    monkeypatch.setattr(scope.owner,"_get_signed_source",owner_get)
    monkeypatch.setattr(scope.owner,"_get_bounded_json",order_get)
    monkeypatch.setattr(scope.fence,"_read",
        lambda *args,**kwargs:(owner["sha"],{"sequence":0,"claim":None}))
    monkeypatch.setattr(scope.cas,"_read_source",
        lambda *args,**kwargs:(ledger["sha"],{"sequence":1,"entries":{"ACWI":{}}}))
    monkeypatch.setattr(scope.witness,"verify",lambda:{
        "original_public_genesis_nonce":"synthetic-genesis",
        "original_live_account_binding_sha256":"c"*64})
    monkeypatch.setattr(scope.publication,"_request",setting_get)
    monkeypatch.setattr(scope,"_release_token_authenticated",
        lambda **kwargs:events.append(("self",kwargs["token"])) or True)
    monkeypatch.setattr(scope,"_public_issue_get",
        lambda **kwargs:events.append(("issue",kwargs["token"])) or True)
    monkeypatch.setattr(scope,"_repository_push_metadata",
        lambda **kwargs:events.append(("repo_permission",kwargs["expected_name"])) or
            "PUSH_INDICATED_NOT_ENDPOINT_WRITE_PROOF")
    return events

def test_five_original_distinct_principals_authenticated_get_no_writes(e,source):
    result=scope.inspect(environ=e)
    assert result["status"]=="FIVE_DISTINCT_GITHUB_PRINCIPALS_AUTHENTICATED_READ_ONLY_NO_WRITE_PROOF"
    assert result["original_private_signed_seq1_and_owner_seq0_verified"]
    assert result["github_provider_immutable_releases_enabled"]
    assert result["private_write_permission_confirmed"] is False
    assert result["public_issue_write_permission_confirmed"] is False
    assert result["public_release_write_permission_confirmed"] is False
    assert result["private_candidate_repository_push_metadata"]=="PUSH_INDICATED_NOT_ENDPOINT_WRITE_PROOF"
    assert result["release_candidate_repository_push_metadata"]=="PUSH_INDICATED_NOT_ENDPOINT_WRITE_PROOF"
    assert result["positive_push_metadata_is_proof_of_release_or_git_contents_write"] is False
    assert result["funded_order_authorized"] is False
    assert (result["signed_state_mutations"]==result["public_release_mutations"]==
            result["public_issue_mutations"]==result["broker_orders"]==0)
    assert [kind for kind,_ in source]==[
        "owner","owner","ledger","ledger",
        "public","self","public","issue","repo_permission","repo_permission"]

@pytest.mark.parametrize("key,bad",[
    ("GITHUB_EVENT_NAME","pull_request"),
    ("GITHUB_REF","refs/heads/unreviewed"),
    ("GITHUB_RUN_ATTEMPT","2"),
    ("FUND100_BROKER_KILL_SWITCH","DISENGAGED"),
    ("FUND100_RISK_LEVEL","LOW"),
    ("GITHUB_REPOSITORY","attacker/repo"),
])
def test_scope_fails_before_source_reads(e,source,key,bad):
    e[key]=bad
    with pytest.raises(scope.PrincipalStop,match="protected main STOP"):
        scope.inspect(environ=e)
    assert source==[]

@pytest.mark.parametrize("missing",scope.REQUIRED)
def test_missing_secret_is_targeted_and_never_reads_original_state(e,source,missing):
    del e[missing]
    with pytest.raises(scope.PrincipalStop,match="MISSING_OR_MALFORMED_"+missing):
        scope.inspect(environ=e)
    assert source==[]


def test_manual_recheck_uses_same_no_mutation_principal_contract(e,source):
    e["GITHUB_EVENT_NAME"]="workflow_dispatch"
    result=scope.inspect(environ=e)
    assert result["funded_order_authorized"] is False
    assert result["broker_orders"]==0
    assert len(source)==10


def test_reports_every_missing_secret_name_in_single_protected_attempt(e,source):
    del e["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"]
    del e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"]
    with pytest.raises(scope.PrincipalStop) as error:
        scope.inspect(environ=e)
    msg=str(error.value)
    assert "MISSING_OR_MALFORMED_" in msg
    assert "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN" in msg
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" in msg
    assert source==[]


@pytest.mark.parametrize("duplicate",[
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
    "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN",
    "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN",
    "GITHUB_TOKEN",
])
def test_shared_principal_rejected_before_source_read(e,source,duplicate):
    e[duplicate]=e["FUND100_PRIVATE_STATE_READ_TOKEN"]
    with pytest.raises(scope.PrincipalStop,match="DISTINCT_GITHUB_PRINCIPALS"):
        scope.inspect(environ=e)
    assert source==[]

@pytest.mark.parametrize("error",["owner_claimed","ledger_advanced","release_exists","admin_disabled"])
def test_first_acwi_change_blocks_original_principal_admission(e,source,monkeypatch,error):
    if error=="owner_claimed":
        monkeypatch.setattr(scope.fence,"_read",
            lambda *args,**kwargs:("a"*40,{"sequence":1,"claim":{}}))
    elif error=="ledger_advanced":
        monkeypatch.setattr(scope.cas,"_read_source",
            lambda *args,**kwargs:("b"*40,{"sequence":2,"entries":{"ACWI":{}}}))
    else:
        def altered(**kwargs):
            source.append(("public",kwargs["url"]))
            assert kwargs["method"]=="GET"
            if kwargs["url"]==scope.publication.IMMUTABLE_SETTING_URL:
                return {"enabled":error!="admin_disabled","enforced_by_owner":False}
            return {"id":5} if error=="release_exists" else None
        monkeypatch.setattr(scope.publication,"_request",altered)
    with pytest.raises(scope.PrincipalStop):
        scope.inspect(environ=e)
    assert all(t[0] in ("owner","ledger","public","self","issue","repo_permission") for t in source)


def test_coarse_github_repository_push_denial_fails_closed_but_is_not_mutation(e,source,monkeypatch):
    for denied in ("nicobouch97/fund100-state-private","nicobouch97/fund100-research"):
        def permission(**kwargs):
            return "PUSH_DENIED" if kwargs["expected_name"]==denied else "UNDETERMINED"
        monkeypatch.setattr(scope,"_repository_push_metadata",permission)
        with pytest.raises(scope.PrincipalStop,match="PUSH_DENIED"):
            scope.inspect(environ=e)


def test_unreported_repository_permission_is_unknown_never_write_proof(e,source,monkeypatch):
    monkeypatch.setattr(scope,"_repository_push_metadata",lambda **kwargs:"UNDETERMINED")
    report=scope.inspect(environ=e)
    assert report["private_candidate_repository_push_metadata"]=="UNDETERMINED"
    assert report["release_candidate_repository_push_metadata"]=="UNDETERMINED"
    assert report["private_write_permission_confirmed"] is False
    assert report["public_release_write_permission_confirmed"] is False
    assert report["funded_order_authorized"] is False


def test_repository_permission_GET_is_read_only_bounded_and_not_write_certification(e):
    from io import BytesIO
    import json
    class Response:
        status=200
        def __init__(self,body):self.raw=BytesIO(body)
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def read(self,*args):return self.raw.read(*args)
    captured=[]
    def t(req,timeout):
        captured.append(req)
        assert timeout==12
        assert req.get_method()=="GET"
        assert req.full_url==scope.PRIVATE_REPO_URL
        return Response(json.dumps({
            "full_name":"nicobouch97/fund100-state-private",
            "permissions":{"push":True}}).encode())
    a=scope._repository_push_metadata(
        url=scope.PRIVATE_REPO_URL,
        expected_name="nicobouch97/fund100-state-private",
        token=e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],transport=t)
    assert a=="PUSH_INDICATED_NOT_ENDPOINT_WRITE_PROOF"
    assert len(captured)==1
    # No token, account value or actual permission claim appears in the returned report.
    assert e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"] not in a
    def denied(req,timeout):
        return Response(json.dumps({
            "full_name":"nicobouch97/fund100-state-private",
            "permissions":{"push":False}}).encode())
    assert scope._repository_push_metadata(
        url=scope.PRIVATE_REPO_URL,
        expected_name="nicobouch97/fund100-state-private",
        token=e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
        transport=denied)=="PUSH_DENIED"
    def omitted(req,timeout):
        return Response(json.dumps({
            "full_name":"nicobouch97/fund100-state-private"}).encode())
    assert scope._repository_push_metadata(
        url=scope.PRIVATE_REPO_URL,
        expected_name="nicobouch97/fund100-state-private",
        token=e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
        transport=omitted)=="UNDETERMINED"
    with pytest.raises(scope.PrincipalStop):
        scope._repository_push_metadata(
            url="https://api.github.com/repos/attacker/repo",
            expected_name="nicobouch97/fund100-state-private",
            token=e["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
            transport=t)

def test_source_has_no_http_mutation_and_no_alpaca_credentials():
    s=Path(scope.__file__).read_text()
    assert "method=\"GET\"" in s
    assert 'method="POST"' not in s
    assert 'method="PUT"' not in s
    assert 'method="PATCH"' not in s
    assert "ALPACA_LIVE_KEY" not in s and "ALPACA_LIVE_SECRET" not in s
    assert "NO_HTTP_MUTATIONS=True" in s
    assert "NO_WRITE_PERMISSION_PROOF=True" in s

def test_protected_capability_workflow_push_or_manual_recheck_with_no_broker_secrets():
    w=PATH.read_text()
    assert w.count("    branches: [main]")==1
    assert w.count("  workflow_dispatch:")==1
    assert "github.event_name == 'push'" in w
    assert "github.event_name == 'workflow_dispatch'" in w
    assert "github.ref == 'refs/heads/main'" in w
    assert "GITHUB_RUN_ATTEMPT\" = '1'" in w
    assert "  schedule:" not in w
    assert "  pull_request:" not in w
    assert w.count("environment: fund100-live-broker")==1
    assert "persist-credentials: false" in w
    assert "FUND100_BROKER_KILL_SWITCH: ${{ vars.FUND100_BROKER_KILL_SWITCH }}" in w
    assert "test \"$FUND100_BROKER_KILL_SWITCH\" = 'ENGAGED'" in w
    assert "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN: ${{ secrets.FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN }}" in w
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN: ${{ secrets.FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN }}" in w
    assert "ALPACA_LIVE_KEY" not in w
    assert "ALPACA_LIVE_SECRET" not in w
    assert "contents: write" not in w and "issues: write" not in w
    assert "python fund100_v6_s1_first_execution_principals_getonly_v1_0.py" in w
    assert "run_protected_first_acwi_once()" not in w
