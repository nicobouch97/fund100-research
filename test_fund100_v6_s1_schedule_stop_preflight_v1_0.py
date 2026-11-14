"""New real V6 scheduled STOP preflight must never masquerade as broker PASS."""
from pathlib import Path
import ast
import textwrap
import pytest

import fund100_live_risk_watch_admission_getonly_v1_0 as admission
import fund100_v6_s1_independent_risk_watch_v1_0 as real_watch


WORKFLOW = Path(".github/workflows/fund100-v6-s1-independent-risk-watch.yml")


def _source():
    return WORKFLOW.read_text(encoding="utf-8")


def test_exact_watch_path_exists_and_is_scheduled_main_only():
    text = _source()
    assert str(WORKFLOW) == admission.WATCH_PATH
    assert "name: Fund-100 V6-S1 Independent First ACWI Risk Watch (NO TRADE)" in text
    assert 'cron: "11,26,41,56 13-22 * * 1-5"' in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "persist-credentials: false" in text
    assert "contents: read" in text
    assert "contents: write" not in text


def test_no_live_alpaca_secrets_no_broker_network_no_trade_signal():
    text = _source()
    # The entire job is a real stopped-latch/schedule check, NEVER the
    # separate broker-aware PASS step expected by the first-sell gate.
    for forbidden in (
        "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
        "FUND100_BROKER_KILL_SWITCH", "ALPACA_API_KEY",
        "alpaca.markets", "/v2/orders",
        "fund100_v6_s1_independent_risk_watch_v1_0.py",
        "fund100_v6_s1_active_high_acwi_sell_risk_v2_0.py",
        "fund100_live_emergency_stop_v1_0.py",
        "Attest independent V6 original ACWI broker risk PASS",
        "Check V6 first ACWI independent LIVE broker risk or STOP",
        "verified_v6_original_acwi_risk=YES",
        "GITHUB_OUTPUT", "commit_stop_signal",
        "python fund100_live_risk_monitor_v1_0.py",
    ):
        assert forbidden not in text
    assert admission.WATCH_JOB_NAME not in text
    assert admission.PASS_STEP not in text
    assert real_watch.SCHEDULED_RUNTIME_RELEASED is False
    assert real_watch.NO_TRADE_RELEASE is True


def test_inline_python_only_reads_current_v5_v6_stop():
    text = _source()
    start = "          python - <<'PY'\n"
    finish = "\n          PY\n"
    # Two isolated jobs: preflight is GET-only; separate failed-only
    # job can request the previously reviewed emergency workflow.
    preflight, relay = text.split("\n  stop-on-unverified-controls:\n", 1)
    assert preflight.count(start) == preflight.count(finish) == 1
    assert relay.count(start) == relay.count(finish) == 1
    source = preflight.split(start, 1)[1].split(finish, 1)[0]
    source = textwrap.dedent(source)
    tree = ast.parse(source)
    called = {
        ast.unparse(n.func)
        for n in ast.walk(tree) if isinstance(n, ast.Call)
    }
    assert {
        "v5.validate_control", "v5.read_current_control",
        "v6.read_current_control",
    }.issubset(called)
    assert not any(
        "request" in name or "commit" in name or "submit" in name
        or "cancel" in name or "get_json" in name
        for name in called
    )
    assert "V5_STOP_UNVERIFIED" in source
    assert "V6_ACTIVE_REQUIRES_UNRELEASED_BROKER_WATCH_HOLD" in source
    assert "NO_BROKER_NO_RISK_PASS" in source


def test_positive_broker_pass_remains_unavailable_when_schedule_probe_runs():
    assert real_watch.SCHEDULED_RUNTIME_RELEASED is False
    # Even a successful scheduled preflight has no exact positive job/step,
    # and the preexisting admission gate demands both for any SELL release.
    assert "V6 stopped-state schedule check (NO BROKER, NO PASS)" in _source()
    assert admission.PASS_STEP not in _source()
    assert admission.WATCH_JOB_NAME not in _source()
    assert admission.NO_TRADE_RELEASE is True


def test_only_failed_preflight_can_dispatch_existing_emergency_stop():
    preflight, relay = _source().split("\n  stop-on-unverified-controls:\n", 1)
    assert "actions: write" not in preflight
    assert "contents: write" not in preflight
    assert "actions: write" in relay
    assert relay.count("actions: write") == 1
    assert "contents: read" not in relay
    assert "contents: write" not in relay
    assert "needs: stopped-preflight" in relay
    assert ("needs.stopped-preflight.result == 'failure'"
            " && github.ref == 'refs/heads/main'") in relay
    assert "uses: actions/checkout" not in relay
    assert "ALPACA_LIVE_KEY" not in relay
    assert "ALPACA_LIVE_SECRET" not in relay
    assert "python fund100_v6_s1_independent_risk_watch_v1_0.py" not in relay
    assert "Attest independent V6 original ACWI broker risk PASS" not in relay
    assert "verified_v6_original_acwi_risk=YES" not in relay


def test_relay_fixed_stop_endpoint_no_unsafe_ack_success_or_retry():
    _, relay = _source().split("\n  stop-on-unverified-controls:\n", 1)
    start = "          python - <<'PY'\n"
    finish = "\n          PY\n"
    assert relay.count(start) == relay.count(finish) == 1
    py = textwrap.dedent(relay.split(start, 1)[1].split(finish, 1)[0])
    tree = ast.parse(py)
    assert "fund100-live-emergency-stop.yml/dispatches" in py
    assert """data=b'{"ref":"main","return_run_details":true}'""" in py
    assert 'method="POST"' in py
    assert '"X-GitHub-Api-Version": "2026-03-10"' in py
    assert "response.status != 200" in py
    assert "workflow_run_id" in py
    assert "STOP_DISPATCH_RUN_ID=" in py
    assert py.index("STOP_DISPATCH_ACK_UNTRUSTED") < py.index("STOP_DISPATCH_RUN_ID=")
    assert "STOP_DISPATCH_ACCEPTED_NOT_CONFIRMED" in py
    assert "STOP_CONFIRMED" not in py
    assert "with build_opener(NoRedirect()).open(req, timeout=12)" in py
    assert "if response.status != 200 or response.geturl() != URL" in py
    assert "GITHUB_WORKFLOW_REF" in py
    assert "GITHUB_RUN_ATTEMPT" in py
    assert "GITHUB_TOKEN" in py
    assert "V6_SCHEDULE_HEARTBEAT" not in relay
    # A broker cancel, GitHub contents update, or direct trade must be
    # executed by the existing emergency workflow, never this relay.
    # Check dangerous literals/calls in parsed source; explanatory comments
    # mentioning a broker DELETE are not executable operations.
    for forbidden in ("api.alpaca.markets", "/v2/orders",
                      "ALPACA_LIVE", "contents: write", "commit_stop_signal",
                      "NO_BROKER_NO_RISK_PASS", "requests.post"):
        assert forbidden not in py
    assert not any(
        isinstance(node, ast.Constant) and node.value == "DELETE"
        for node in ast.walk(tree)
    )
    requests = [
        n for n in ast.walk(tree) if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name) and n.func.id == "Request"
    ]
    assert len(requests) == 1



def _relay_py():
    _, relay = _source().split("\n  stop-on-unverified-controls:\n", 1)
    return textwrap.dedent(relay.split("          python - <<'PY'\n", 1)[1]
                           .split("\n          PY\n", 1)[0])


def _mock_relay(monkeypatch, *, ack=None, status=200, wrong_event=False):
    """Execute the exact inline job under a mock GitHub HTTP transport."""
    import json
    import urllib.request
    expected_repo = "nicobouch97/fund100-research"
    expected_url = ("https://api.github.com/repos/" + expected_repo
                    + "/actions/workflows/fund100-live-emergency-stop.yml/dispatches")
    run_id = 1234567
    valid = {
        "workflow_run_id":run_id,
        "run_url":"https://api.github.com/repos/"+expected_repo+
                  "/actions/runs/"+str(run_id),
        "html_url":"https://github.com/"+expected_repo+
                   "/actions/runs/"+str(run_id),
    }
    calls = []
    token="synthetic-test-github-token-never-real-123456789"
    for key,value in {
        "GITHUB_ACTIONS":"true",
        "GITHUB_REPOSITORY":expected_repo,
        "GITHUB_REF":"refs/heads/main",
        "GITHUB_EVENT_NAME":"pull_request" if wrong_event else "schedule",
        "GITHUB_WORKFLOW_REF":expected_repo+
            "/.github/workflows/fund100-v6-s1-independent-risk-watch.yml@refs/heads/main",
        "GITHUB_RUN_ATTEMPT":"1",
        "GITHUB_SHA":"a"*40,
        "GITHUB_TOKEN":token,
    }.items():
        monkeypatch.setenv(key,value)

    class FakeResponse:
        def __init__(self,request):
            self.req=request
            self.status=status
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def geturl(self):return self.req.full_url
        def read(self,n):
            body=json.dumps(valid if ack is None else ack).encode()
            return body[:n]

    class FakeOpener:
        def open(self,request,timeout):
            assert timeout==12
            calls.append(request)
            assert request.full_url==expected_url
            assert request.get_method()=="POST"
            assert request.data==b'{"ref":"main","return_run_details":true}'
            assert request.get_header("Authorization")=="Bearer "+token
            assert request.get_header("X-github-api-version")=="2026-03-10"
            return FakeResponse(request)

    monkeypatch.setattr(urllib.request,"build_opener",
                        lambda *args:FakeOpener())
    return calls,token


def test_relay_one_fixed_dispatch_with_safe_run_id_but_no_stop_claim(
        monkeypatch,capsys):
    calls,token=_mock_relay(monkeypatch)
    exec(compile(_relay_py(),"<mocked-fund100-stop-relay>","exec"),
         {"__name__":"__main__"})
    output=capsys.readouterr().out
    assert len(calls)==1
    assert "STOP_DISPATCH_RUN_ID=1234567" in output
    assert "STOP_DISPATCH_ACCEPTED_NOT_CONFIRMED" in output
    assert token not in output
    assert "STOP_COMPLETED" not in output


def test_relay_rejects_wrong_source_event_without_dispatch(
        monkeypatch,capsys):
    calls,token=_mock_relay(monkeypatch,wrong_event=True)
    with pytest.raises(SystemExit,match="STOP_DISPATCH_SCOPE_INVALID"):
        exec(compile(_relay_py(),"<mocked-fund100-stop-relay>","exec"),
             {"__name__":"__main__"})
    assert calls==[]
    assert token not in capsys.readouterr().out


@pytest.mark.parametrize("bad",[
    {"workflow_run_id":"1234567"},
    {"workflow_run_id":1234567,
     "run_url":"https://evil.invalid/other",
     "html_url":"https://github.com/nicobouch97/fund100-research/actions/runs/1234567"},
])
def test_relay_forged_ack_never_reports_stop_success(
        monkeypatch,capsys,bad):
    calls,token=_mock_relay(monkeypatch,ack=bad)
    with pytest.raises(RuntimeError,match="STOP_DISPATCH_ACK_UNTRUSTED"):
        exec(compile(_relay_py(),"<mocked-fund100-stop-relay>","exec"),
             {"__name__":"__main__"})
    assert len(calls)==1
    assert "STOP_DISPATCH_RUN_ID=" not in capsys.readouterr().out
