"""No-network independent external receipt ingress, with synthetic Ed25519."""
from copy import deepcopy
from datetime import timedelta
from io import BytesIO
import json
from pathlib import Path
from urllib.error import URLError

import pytest
import fund100_v6_s1_external_signed_risk_receipt_ingress_v1_0 as ingress
import fund100_v6_external_signed_risk_receipt_getonly_v1_0 as verifier
from test_fund100_v6_external_signed_risk_receipt_getonly_v1_0 import (
    SHA, ACCOUNT, POLICY, PUB, NOW, good_receipt, sign,
)

TOKEN = "synthetic-external-receipt-READONLY-token-123456789"
ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_REPOSITORY": "nicobouch97/fund100-research",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_EVENT_NAME": "schedule",
    "GITHUB_WORKFLOW_REF": ingress.EXPECTED_WORKFLOW_REF,
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_SHA": SHA,
}


class Result:
    def __init__(self, content, *, status=200,
                 content_type="application/json", url=ingress.URL):
        self.data = BytesIO(content)
        self.status = status
        self.headers = type("FakeHeaders", (), {
            "get_content_type": lambda self: content_type,
        })()
        self.url = url

    def geturl(self):
        return self.url

    def read(self, n):
        return self.data.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture(autouse=True)
def no_production_secrets(monkeypatch):
    for key, val in ENV.items():
        monkeypatch.setenv(key, val)


def released_fake(monkeypatch):
    monkeypatch.setattr(ingress, "RECEIPT_INGRESS_RELEASED", True)
    monkeypatch.setattr(ingress, "EXPECTED_ACCOUNT_BINDING_SHA256", ACCOUNT)
    monkeypatch.setattr(ingress, "EXPECTED_RISK_POLICY_SHA256", POLICY)
    monkeypatch.setattr(verifier, "RECEIPT_VERIFICATION_RELEASED", True)
    monkeypatch.setattr(verifier, "APPROVED_SIGNER_PUBLIC_KEY_HEX", PUB)


def reply(receipt=None):
    return json.dumps(sign(good_receipt() if receipt is None else receipt),
                      sort_keys=True).encode()


def mock_sender(raw=None, status=200, content_type="application/json",
                url=ingress.URL):
    events = []
    def send(request, timeout):
        events.append(request)
        assert request.full_url == ingress.URL
        assert request.get_method() == "GET"
        assert request.get_header("Authorization") == "Bearer " + TOKEN
        assert request.get_header("Accept") == "application/json"
        assert timeout == ingress.TIMEOUT_SECONDS
        return Result(reply() if raw is None else raw, status=status,
                      content_type=content_type, url=url)
    return send, events


def run(sender, *, token=TOKEN, sha=SHA, now=NOW):
    return ingress.require_fresh_signed_external_risk_pass(
        main_sha=sha, readonly_token=token,
        now_utc=now, transport=sender,
    )


def test_literal_source_gates_block_before_any_request():
    assert ingress.RECEIPT_INGRESS_RELEASED is False
    assert ingress.EXPECTED_ACCOUNT_BINDING_SHA256 is None
    assert ingress.EXPECTED_RISK_POLICY_SHA256 is None
    assert verifier.RECEIPT_VERIFICATION_RELEASED is False
    assert verifier.APPROVED_SIGNER_PUBLIC_KEY_HEX is None
    assert all((ingress.NO_BROKER_REQUEST, ingress.NO_GITHUB_WRITE,
                ingress.NO_RAILWAY_WRITE, ingress.NO_TRADE_RELEASE))
    sender, events = mock_sender()
    with pytest.raises(ingress.ExternalReceiptIngressStop, match="HARD LOCKED"):
        run(sender)
    assert not events


def test_valid_synthetic_signed_eight_get_receipt_only_returns_boolean(monkeypatch):
    released_fake(monkeypatch)
    sender, events = mock_sender()
    assert run(sender) is True
    assert len(events) == 1
    assert ingress.NO_TRADE_RELEASE is True


@pytest.mark.parametrize("field,bad", [
    ("GITHUB_ACTIONS", "false"),
    ("GITHUB_REPOSITORY", "evil/research"),
    ("GITHUB_REF", "refs/heads/feature"),
    ("GITHUB_EVENT_NAME", "workflow_dispatch"),
    ("GITHUB_EVENT_NAME", "push"),
    ("GITHUB_WORKFLOW_REF", "evil"),
    ("GITHUB_RUN_ATTEMPT", "2"),
    ("GITHUB_SHA", "f" * 40),
])
def test_untrusted_job_cannot_get_risk_evidence(monkeypatch, field, bad):
    released_fake(monkeypatch)
    monkeypatch.setenv(field, bad)
    sender, events = mock_sender()
    with pytest.raises(ingress.ExternalReceiptIngressStop,
                       match="workflow context"):
        run(sender)
    assert events == []


@pytest.mark.parametrize("token", [
    "short", "x"*31, "y"*513, "not a secret\n", TOKEN+" ",
    TOKEN+"\r", None, 33, True,
])
def test_bad_read_token_never_sent(monkeypatch, token):
    released_fake(monkeypatch)
    sender, events = mock_sender()
    with pytest.raises(ingress.ExternalReceiptIngressStop,
                       match="credential"):
        run(sender, token=token)
    assert events == []


@pytest.mark.parametrize("pin", ["account", "policy"])
def test_missing_pinned_binding_stops_before_get(monkeypatch, pin):
    released_fake(monkeypatch)
    name = ("EXPECTED_ACCOUNT_BINDING_SHA256" if pin=="account" else
            "EXPECTED_RISK_POLICY_SHA256")
    monkeypatch.setattr(ingress, name, None)
    sender, events = mock_sender()
    with pytest.raises(ingress.ExternalReceiptIngressStop, match="binding"):
        run(sender)
    assert events == []


@pytest.mark.parametrize("status,content_type,url", [
    (401,"application/json",ingress.URL),
    (503,"application/json",ingress.URL),
    (200,"text/html",ingress.URL),
    (200,"application/json","https://evil.example/risk"),
])
def test_wrong_http_status_content_or_redirect_denied(monkeypatch,status,content_type,url):
    released_fake(monkeypatch)
    sender, events = mock_sender(status=status,
                                 content_type=content_type,url=url)
    with pytest.raises(ingress.ExternalReceiptIngressStop,
                       match="not trusted"):
        run(sender)
    assert len(events) == 1


@pytest.mark.parametrize("content", [
    b"", b"not json", b"{}",
    b'{"receipt":{},"receipt":{}}',
    b'{"ed25519_signature_hex":"a","ed25519_signature_hex":"b"}',
    b"x" * (ingress.MAX_BODY_BYTES + 1),
])
def test_malformed_duplicate_or_oversized_evidence_is_never_pass(monkeypatch,content):
    released_fake(monkeypatch)
    sender, _ = mock_sender(raw=content)
    with pytest.raises(ingress.ExternalReceiptIngressStop):
        run(sender)


def test_missing_real_signer_key_denied_even_if_fake_transport_works(monkeypatch):
    released_fake(monkeypatch)
    monkeypatch.setattr(verifier, "APPROVED_SIGNER_PUBLIC_KEY_HEX", None)
    sender, _ = mock_sender()
    with pytest.raises(ingress.ExternalReceiptIngressStop, match="signature"):
        run(sender)


@pytest.mark.parametrize("badfield,bad", [
    ("risk_outcome", "ALREADY_STOPPED"),
    ("broker_get_count", 7),
    ("broker_write_count", 1),
    ("account_binding_sha256", "a" * 64),
    ("risk_policy_sha256", "d" * 64),
    ("head_sha", "f" * 40),
    ("trade_authorized", True),
])
def test_signed_but_wrong_broker_receipt_never_passes(monkeypatch,badfield,bad):
    released_fake(monkeypatch)
    r = good_receipt()
    r[badfield] = bad
    sender, _ = mock_sender(raw=reply(r))
    with pytest.raises(ingress.ExternalReceiptIngressStop, match="signature"):
        run(sender)


def test_replayed_stale_receipt_denied_after_120_seconds(monkeypatch):
    released_fake(monkeypatch)
    sender, _ = mock_sender()
    with pytest.raises(ingress.ExternalReceiptIngressStop, match="signature"):
        run(sender, now=NOW+timedelta(seconds=91))


def test_network_failure_does_not_leak_read_token(monkeypatch):
    released_fake(monkeypatch)
    def offline(_request,timeout):
        raise URLError("bad token is " + TOKEN)
    with pytest.raises(ingress.ExternalReceiptIngressStop) as exc:
        run(offline)
    assert TOKEN not in str(exc.value)


def test_fake_http_health_success_is_not_risk_pass(monkeypatch):
    released_fake(monkeypatch)
    health = b'{"broker_risk_pass":false,"trading_authorized":false}'
    sender, _ = mock_sender(raw=health)
    with pytest.raises(ingress.ExternalReceiptIngressStop):
        run(sender)


def test_unreleased_reader_mandatory_for_locked_entry_but_not_deployed_on_railway():
    code = Path(ingress.__file__).read_text()
    assert "RECEIPT_INGRESS_RELEASED = False" in code
    assert "EXPECTED_ACCOUNT_BINDING_SHA256 = None" in code
    assert "EXPECTED_RISK_POLICY_SHA256 = None" in code
    assert "NO_TRADE_RELEASE = True" in code
    assert "method=\"GET\"" in code
    assert "method=\"POST\"" not in code and "method=\"DELETE\"" not in code
    assert "/v2/orders" not in code
    assert "ALPACA_LIVE_KEY" not in code
    assert "ALPACA_LIVE_SECRET" not in code
    entry=Path("fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py").read_text()
    # The first trading entry now REQUIRES an independently signed risk
    # receipt. This source wiring does not release the hard-locked GET or
    # establish an approved signing key, policy or retail account.
    assert "import fund100_v6_s1_external_signed_risk_receipt_ingress_v1_0 as external_risk" in entry
    assert "external_risk.require_fresh_signed_external_risk_pass(" in entry
    assert "ORIGINAL_ACWI_ENTRYPOINT_RELEASED=False" in entry
    assert entry.index("external_risk.require_fresh_signed_external_risk_pass(") < entry.index(
        "live_watch.require_recent_scheduled_risk_pass(") < entry.index(
        "chain.prepare_original_acwi_context_getonly(")
    docker=Path("Dockerfile").read_text()
    assert "fund100_v6_s1_external_signed_risk_receipt_ingress_v1_0" not in docker
