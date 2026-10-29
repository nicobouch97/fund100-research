"""Credentialless, secret-safe GET-only provenance probe tests."""
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
import json
import pytest

import fund100_v6_private_writer_candidate_get_diagnostic_v1_0 as probe

READ = "test-private-reader-token"
WRITE = "test-private-writer-token"
ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_REPOSITORY": "nicobouch97/fund100-research",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_EVENT_NAME": "push",
    "FUND100_BROKER_KILL_SWITCH": "ENGAGED",
    "FUND100_RISK_LEVEL": "HIGH",
    "FUND100_PRIVATE_STATE_READ_TOKEN": READ,
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN": WRITE,
}


class Response:
    def __init__(self, body=b"{}", remaining=None):
        self.status = 200
        self.headers = {"X-RateLimit-Remaining": remaining} if remaining else {}
        self.body = BytesIO(body)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return self.body.read(size)


class FakeGit:
    def __init__(self, *, auth_code=200, owner_code=404, baseline_code=200,
                 remaining=None, malformed_user=False):
        self.auth_code = auth_code
        self.owner_code = owner_code
        self.baseline_code = baseline_code
        self.remaining = remaining
        self.malformed_user = malformed_user
        self.calls = []

    def __call__(self, req, timeout):
        assert timeout == 12
        assert req.get_method() == "GET"
        assert req.full_url in probe.URL_ALLOWLIST
        assert req.get_header("User-agent") == "fund100-private-writer-candidate-get-diagnostic"
        tok = req.get_header("Authorization").removeprefix("Bearer ")
        assert tok in (READ, WRITE)
        self.calls.append((tok, req.full_url))
        if tok == READ:
            assert req.full_url == probe.OWNER_URL
            status = self.baseline_code
        elif req.full_url == probe.USER_URL:
            status = self.auth_code
        else:
            status = self.owner_code
        if status != 200:
            raise HTTPError(
                req.full_url, status, "fake response includes secret",
                {"X-RateLimit-Remaining": self.remaining or "400"}, None)
        if req.full_url == probe.USER_URL:
            body = b"{}" if self.malformed_user else json.dumps(
                {"login": "never-print-identity"}).encode()
            return Response(body)
        return Response(b'{"sensitive":"never-print-private-source"}')


def test_verified_user_but_private_owner_404_reveals_scope_not_write_proof():
    fake = FakeGit()
    report = probe.diagnose(environ=ENV, transport=fake)
    assert fake.calls == [
        (READ, probe.OWNER_URL), (WRITE, probe.USER_URL),
        (WRITE, probe.OWNER_URL),
    ]
    assert report["assessment"] == "CANDIDATE_AUTHENTICATED_BUT_PRIVATE_OWNER_NOT_VISIBLE_HOLD"
    assert report["write_candidate_user_auth_get"] == "HTTP_200"
    assert report["write_candidate_owner_get"] == "HTTP_404_RESOURCE_NOT_VISIBLE_TO_THIS_PRINCIPAL"
    assert report["candidate_github_contents_write_permission_verified"] is False
    assert report["production_private_git_puts"] == report["broker_posts"] == 0
    assert report["live_orders_authorized"] is False
    assert "never-print" not in repr(report)


def test_200_from_candidate_owner_does_not_claim_contents_write():
    r = probe.diagnose(environ=ENV, transport=FakeGit(owner_code=200))
    assert r["assessment"] == "CANDIDATE_OWNER_GET_HTTP_200_NOT_WRITE_PROOF"
    assert r["candidate_github_contents_write_permission_verified"] is False
    assert r["live_orders_authorized"] is False


@pytest.mark.parametrize("status,expected", [
    (401, "HTTP_401_TOKEN_NOT_AUTHENTICATED"),
    (403, "HTTP_403_ACCESS_DENIED_OR_RATE_LIMIT_UNPROVEN"),
    (404, "HTTP_404_RESOURCE_NOT_VISIBLE_TO_THIS_PRINCIPAL"),
    (429, "HTTP_429_RATE_LIMITED"),
    (500, "HTTP_5XX_GITHUB_UNAVAILABLE"),
])
def test_auth_failure_suppresses_cannot_trust_owner_get(status, expected):
    fake = FakeGit(auth_code=status)
    r = probe.diagnose(environ=ENV, transport=fake)
    assert r["write_candidate_user_auth_get"] == expected
    assert r["write_candidate_owner_get"] == "SKIPPED_CANDIDATE_USER_NOT_AUTHENTICATED"
    assert r["assessment"] == "CANDIDATE_AUTHENTICATION_UNAVAILABLE_HOLD"
    assert fake.calls == [
        (READ, probe.OWNER_URL), (WRITE, probe.USER_URL)]
    assert not r["live_orders_authorized"]


def test_rate_limited_status_is_not_mislabeled_as_missing_permission():
    fake = FakeGit(owner_code=403, remaining="0")
    result = probe.diagnose(environ=ENV, transport=fake)
    assert result["write_candidate_owner_get"] == "HTTP_403_RATE_LIMIT_INDICATED"
    assert result["assessment"] == "CANDIDATE_PRIVATE_OWNER_GET_NOT_VERIFIED_HOLD"


def test_403_without_verified_limit_remains_access_or_rate_ambiguous():
    r = probe.diagnose(environ=ENV, transport=FakeGit(owner_code=403))
    assert r["write_candidate_owner_get"] == "HTTP_403_ACCESS_DENIED_OR_RATE_LIMIT_UNPROVEN"


def test_malformed_identity_must_not_count_as_authenticated():
    fake = FakeGit(malformed_user=True)
    r = probe.diagnose(environ=ENV, transport=fake)
    assert r["write_candidate_user_auth_get"] == "HTTP_200_BUT_AUTH_IDENTITY_INVALID"
    assert r["write_candidate_owner_get"] == "SKIPPED_CANDIDATE_USER_NOT_AUTHENTICATED"
    assert len(fake.calls) == 2


@pytest.mark.parametrize("bad", [401, 403, 404, 429, 503])
def test_unverified_original_reader_cannot_probe_candidate(bad):
    fake = FakeGit(baseline_code=bad)
    with pytest.raises(probe.DiagnosticStop, match="baseline"):
        probe.diagnose(environ=ENV, transport=fake)
    assert fake.calls == [(READ, probe.OWNER_URL)]


@pytest.mark.parametrize("change", [
    {"GITHUB_REF":"refs/heads/dev"},
    {"GITHUB_REPOSITORY":"attacker/repository"},
    {"GITHUB_RUN_ATTEMPT":"2"},
    {"GITHUB_EVENT_NAME":"pull_request"},
    {"FUND100_BROKER_KILL_SWITCH":"DISENGAGED"},
    {"FUND100_RISK_LEVEL":"LOW"},
    {"FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN":READ},
    {"FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN":""},
])
def test_rejects_invalid_protected_context_before_any_get(change):
    fake=FakeGit()
    with pytest.raises(probe.DiagnosticStop):
        probe.diagnose(environ=dict(ENV,**change),transport=fake)
    assert fake.calls == []


def test_never_attempt_any_url_outside_exact_private_owner_and_user_endpoints():
    with pytest.raises(probe.DiagnosticStop):
        probe._get_status(
            url="https://api.github.com/repos/attacker/other",
            token=READ, transport=FakeGit())
    with pytest.raises(probe.DiagnosticStop):
        probe._get_status(
            url=probe.OWNER_URL, token=WRITE,
            transport=FakeGit(),authenticate_user=True)


def test_module_has_no_mutation_client_and_never_leaks_token_or_private_document():
    code=Path(probe.__file__).read_text()
    assert probe.NO_GIT_WRITES and probe.NO_BROKER_CALLS
    assert probe.PRIVATE_PUTS == probe.BROKER_POSTS == 0
    assert probe.WRITER_PERMISSION_ESTABLISHED is False
    assert probe.LIVE_TRADE_AUTHORIZED is False
    for forbidden in (
        'method="PUT"', 'method="POST"', 'method="PATCH"',
        "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET", "contents: write",
    ):
        assert forbidden not in code


def test_credential_scope_workflow_still_has_mandatory_original_five_principal_failure():
    workflow=Path(
        ".github/workflows/fund100-v6-s1-first-execution-principals-getonly.yml"
    ).read_text()
    status=workflow.index("Diagnose write-candidate GitHub GET failure category (READ ONLY)")
    strict=workflow.index(
        "Verify existing 5 independent GitHub principals by ORIGINAL authenticated READ")
    assert status < strict
    segment=workflow[status:strict]
    assert "FUND100_PRIVATE_STATE_READ_TOKEN" in segment
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" in segment
    assert "ALPACA_LIVE_KEY" not in workflow
    assert "ALPACA_LIVE_SECRET" not in workflow
    assert "contents: write" not in workflow
    assert "python -B fund100_v6_private_writer_candidate_get_diagnostic_v1_0.py" in segment
    assert "python fund100_v6_s1_first_execution_principals_getonly_v1_0.py" in workflow
