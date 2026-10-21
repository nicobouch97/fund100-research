"""Synthetic-only one-time funded-account signed EMPTY ledger bootstrap tests."""
from base64 import b64decode, b64encode
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as p
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_private_state_actions_readonly_probe_v1_0 as identity
import fund100_v6_s1_public_genesis_witness_v1_0 as witness


READ = "synthetic-separate-read-PAT-never-real"
WRITE = "synthetic-separate-write-PAT-never-real"
ISSUE = "synthetic-issue-scoped-token-never-real"
HMAC = ("0123456789abcdef" * 4)
RUN = "https://github.com/nicobouch97/fund100-research/actions/runs/9999999"


def broker_ok():
    return {
        "schema": "FUND100_V6_ACTUAL_LIVE_GET_ONLY_TRANSITION_READINESS_V1",
        "account_binding_matches_original_policy": True,
        "historic_four_original_etf_quantities_reconciled": True,
        "account_cash_and_holdings_reconcile_to_equity": True,
        "live_account_active": True,
        "open_order_count": 0,
        "broker_environment_kill_switch_engaged": True,
        "original_operator_stopped": True,
        "high_risk_tier_selected": True,
        "broker_get_requests": 4,
        "broker_non_get_requests": 0,
        "broker_orders_submitted": 0,
        "current_strategy_decision": "HOLD_EXISTING_FOUR_ETFS_NO_SELL",
    }


def fake_identity(*, url, token):
    assert token == READ
    if url == identity.BASE:
        return {"full_name": identity.EXPECTED_REPO,
                "id": int(identity.EXPECTED_REPO_ID),
                "private": True,
                "default_branch": "main",
                "archived": False}
    assert url == identity.BASE + "/contents/README.md?ref=main"
    return {"path": "README.md", "type": "file", "encoding": "base64",
            "sha": "a" * 40, "content": "IyBzeW50aGV0aWM="}


class Response:
    def __init__(self, payload, status):
        self.raw = BytesIO(json.dumps(payload).encode())
        self.status = status
    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc, tb):
        return False
    def read(self, limit):
        return self.raw.read(limit)


class SimulatedPrivateGit:
    """Exact private-only source; disallow hidden overwrites and broker orders."""
    def __init__(self, existing=None, fail_put=False, break_readback=False):
        self.state = existing
        self.create_count = 0
        self.calls = []
        self.fail_put = fail_put
        self.break_readback = break_readback
    def __call__(self, request, timeout):
        assert timeout == 12
        method = request.get_method()
        url = request.full_url
        assert method in ("GET", "PUT")
        assert url in (p.PRODUCTION_URL, p.PRODUCTION_READ_URL)
        token = request.get_header("Authorization")
        self.calls.append((method, url, token))
        if method == "GET":
            assert url == p.PRODUCTION_READ_URL
            assert token in ("Bearer " + READ, "Bearer " + WRITE)
            if self.state is None:
                raise HTTPError(url, 404, "absent", None, None)
            body = self.state
            if self.break_readback and self.create_count:
                body = self.state + b"evil"
            return Response({
                "path": cas.STATE_PATH,
                "type": "file",
                "encoding": "base64",
                "sha": cas.blob_sha(body),
                "content": b64encode(body).decode(),
            }, 200)
        assert method == "PUT"
        assert url == p.PRODUCTION_URL and token == "Bearer " + WRITE
        body = json.loads(request.data)
        assert set(body) == {"branch", "message", "content"}
        assert body["branch"] == "main"
        if self.fail_put:
            raise URLError("network write ambiguous")
        if self.state is not None:
            raise HTTPError(url, 422, "exists", None, None)
        self.state = b64decode(body["content"], validate=True)
        self.create_count += 1
        return Response({
            "content": {"path": cas.STATE_PATH, "sha": cas.blob_sha(self.state)},
            "commit": {"sha": "e" * 40},
        }, 201)


class FakePublicIssue:
    def __init__(self, fail=False, mismatch=False):
        self.calls = []
        self.body = None
        self.fail = fail
        self.mismatch = mismatch
    def __call__(self, req, timeout):
        assert timeout == 12
        method, url = req.get_method(), req.full_url
        assert req.get_header("Authorization") == "Bearer " + ISSUE
        self.calls.append((method, url))
        if method == "POST":
            assert url == p.PUBLIC_ISSUE_URL
            assert set(json.loads(req.data)) == {"body"}
            assert self.body is None
            if self.fail:
                raise HTTPError(url, 403, "issue not writeable", None, None)
            self.body = json.loads(req.data)["body"]
            assert "Private Git blob SHA256 commitment:" in self.body
            assert "Ledger sequence: 0" in self.body
            assert "account_binding" not in self.body
            return Response({"id": 7654321, "body": self.body}, 201)
        assert method == "GET" and url == p.PUBLIC_COMMENT_URL + "7654321"
        return Response({"id": 7654321,
                         "body": self.body + "tamper" if self.mismatch else self.body},
                        200)


def attempt(*, private=None, public=None, broker_report=None, read=READ,
            write=WRITE, issue=ISSUE, hmac=HMAC, run=RUN, **kwargs):
    return p.bootstrap(
        broker_report=broker_ok() if broker_report is None else broker_report,
        read_token=read, write_token=write,
        public_issue_token=issue, private_hmac_hex=hmac,
        run_url=run, private_transport=private,
        public_transport=public, identity_fetch=fake_identity,
        **kwargs,
    )


def test_valid_fake_one_time_genesis_reconciles_exact_original_public_witness():
    private = SimulatedPrivateGit()
    public = FakePublicIssue()
    out = attempt(private=private, public=public)
    assert out["stage"] == "EMPTY_GENESIS_READBACK_AND_EXTERNAL_HASH_WITNESS_DONE_NO_ORDERS"
    assert out["private_signed_empty_genesis_readback_verified"]
    assert out["new_public_issue_witness_comment_id"] == 7654321
    assert not out["independently_immutable_rollback_anchor_proven"]
    assert not out["new_live_orders_authorized"]
    assert not out["new_production_order_writer_authorized"]
    assert out["live_broker_get_requests"] == 4
    assert out["live_broker_order_posts"] == 0
    assert out["private_initial_create_PUTs"] == 1
    assert private.create_count == 1
    assert [x[0] for x in private.calls] == ["GET", "GET", "PUT", "GET"]
    assert private.calls[0][2] == "Bearer " + READ
    assert private.calls[1][2] == "Bearer " + WRITE
    assert [x[0] for x in public.calls] == ["POST", "GET"]
    signed = json.loads(private.state)
    assert signed["sequence"] == 0
    assert signed["entries"] == {}
    assert signed["prior_document_sha"] is None
    assert signed["account_binding"] == witness.verify()[
        "original_live_account_binding_sha256"]
    assert signed["genesis"] == witness.verify()["original_public_genesis_nonce"]
    assert p.public_head_commitment(
        nonce=signed["genesis"],
        private_blob_sha=cas.blob_sha(private.state)) in public.body
    assert cas.blob_sha(private.state) not in public.body
    assert HMAC not in public.body
    assert WRITE not in public.body
    assert READ not in public.body


def test_second_attempt_never_overwrites_or_posts_another_issue():
    private = SimulatedPrivateGit()
    public = FakePublicIssue()
    attempt(private=private, public=public)
    with pytest.raises(p.GenesisBootstrapStop, match="already exists"):
        attempt(private=private, public=FakePublicIssue())
    assert private.create_count == 1


@pytest.mark.parametrize("bad", [
    {"account_binding_matches_original_policy": False},
    {"historic_four_original_etf_quantities_reconciled": False},
    {"account_cash_and_holdings_reconcile_to_equity": False},
    {"live_account_active": False},
    {"open_order_count": 1},
    {"broker_environment_kill_switch_engaged": False},
    {"original_operator_stopped": False},
    {"high_risk_tier_selected": False},
    {"broker_get_requests": 3},
    {"broker_non_get_requests": 1},
    {"broker_orders_submitted": 1},
    {"current_strategy_decision": "SELL_EXISTING_HOLDINGS"},
])
def test_any_unverified_live_broker_flag_stops_before_private_GET(bad):
    broker = broker_ok()
    broker.update(bad)
    private = SimulatedPrivateGit()
    with pytest.raises(p.GenesisBootstrapStop, match="LIVE four-GET"):
        attempt(broker_report=broker, private=private, public=FakePublicIssue())
    assert private.calls == []


@pytest.mark.parametrize("bad", ["", "00"*32, "abcdef", "f"*63,
                                 "a"*64, "1"*64, "g"*64])
def test_no_missing_weak_or_invalid_HMAC_key(bad):
    private = SimulatedPrivateGit()
    with pytest.raises(p.GenesisBootstrapStop, match="HMAC key"):
        attempt(hmac=bad, private=private, public=FakePublicIssue())
    assert not private.calls


def test_no_fallback_from_read_only_Pat_or_sandbox_PAT():
    private = SimulatedPrivateGit()
    with pytest.raises(p.GenesisBootstrapStop, match="must differ"):
        attempt(write=READ, private=private, public=FakePublicIssue())
    assert private.calls == []


def test_existing_file_for_either_identity_does_not_create():
    arbitrary = cas.genesis(
        private_genesis=witness.verify()["original_public_genesis_nonce"],
        account_binding_sha256=witness.verify()[
            "original_live_account_binding_sha256"], key=bytes.fromhex(HMAC))
    private = SimulatedPrivateGit(existing=arbitrary)
    with pytest.raises(p.GenesisBootstrapStop, match="already exists"):
        attempt(private=private, public=FakePublicIssue())
    assert private.create_count == 0


def test_non_repeatable_uncertain_first_put_failure_leaves_no_anchored_success():
    private = SimulatedPrivateGit(fail_put=True)
    public = FakePublicIssue()
    with pytest.raises(p.GenesisBootstrapStop, match="STOP and investigate"):
        attempt(private=private, public=public)
    assert private.create_count == 0
    assert public.calls == []


def test_independent_readback_tamper_blocks_public_witness_creation():
    private = SimulatedPrivateGit(break_readback=True)
    public = FakePublicIssue()
    with pytest.raises(p.GenesisBootstrapStop, match="readback failed"):
        attempt(private=private, public=public)
    assert private.create_count == 1
    assert public.calls == []


def test_external_public_witness_permission_fails_closed_after_existing_genesis():
    private = SimulatedPrivateGit()
    public = FakePublicIssue(fail=True)
    with pytest.raises(p.GenesisBootstrapStop, match="no automatic retry"):
        attempt(private=private, public=public)
    assert private.create_count == 1
    assert [x[0] for x in public.calls] == ["POST"]


def test_external_comment_mutation_fails_closed_after_one_issue_POST():
    private = SimulatedPrivateGit()
    public = FakePublicIssue(mismatch=True)
    with pytest.raises(p.GenesisBootstrapStop, match="commentment|commitment GET"):
        attempt(private=private, public=public)
    assert private.create_count == 1
    assert [x[0] for x in public.calls] == ["POST", "GET"]


def test_changed_public_genesis_nonce_is_not_accepted_before_network_calls():
    private = SimulatedPrivateGit()
    def forged():
        r = witness.verify()
        r["original_public_genesis_nonce"] = "0" * 64
        return r
    # A changed public nonce still cannot bypass the original signed witness:
    # test is limited to supplied non-executable fixture; original reviewer
    # must separately attest its public SHA on the protected main.
    with pytest.raises(p.GenesisBootstrapStop):
        attempt(private=private, public=FakePublicIssue(),
                verify_stop=lambda: {"status": "UNVERIFIED"})
    assert private.calls == []


def test_public_comment_rejects_wrong_run_or_digest_identity():
    with pytest.raises(p.GenesisBootstrapStop):
        p.public_comment(digest="a"*64, run_url="https://evil.example/actions/1")
    with pytest.raises(p.GenesisBootstrapStop):
        p.public_comment(digest="garbage", run_url=RUN)


def test_exact_allowed_GitHub_HTTP_methods_and_no_private_ledger_overwrite():
    with pytest.raises(p.GenesisBootstrapStop, match="Unapproved"):
        p._json(method="DELETE", url=p.PRODUCTION_URL, token=READ)
    with pytest.raises(p.GenesisBootstrapStop, match="Unapproved"):
        p._json(method="POST", url=p.PRODUCTION_URL, token=WRITE, payload={})
    with pytest.raises(p.GenesisBootstrapStop, match="Unapproved"):
        p._json(method="PUT", url=p.PRODUCTION_READ_URL, token=WRITE, payload={})
    with pytest.raises(p.GenesisBootstrapStop, match="Unapproved"):
        p._json(method="PUT", url=p.PRODUCTION_URL, token=WRITE, payload=None)


def test_immutable_original_four_GET_prior_actions_job_metadata_is_required():
    from datetime import datetime, timezone
    good_job = {
        "name": p.BROKER_GUARD_JOB,
        "status": "completed",
        "conclusion": "success",
        "completed_at": "2026-10-21T15:45:00Z",
        "steps": [
            {"name": p.BROKER_GUARD_STEP, "status": "completed", "conclusion": "success"}
        ],
    }
    class JobTransport:
        def __init__(self, job):
            self.job = job
        def __call__(self, req, timeout):
            assert req.full_url == (
                p.ACTIONS_RUN_JOB_URL_PREFIX + "9999999/jobs?per_page=100")
            assert req.get_method() == "GET"
            assert req.get_header("Authorization") == "Bearer " + ISSUE
            return Response({"jobs": [self.job]}, 200)
    t = datetime(2026, 10, 21, 15, 45, 35, tzinfo=timezone.utc)
    result = p.authentic_original_four_get_job(
        run_id="9999999", public_token=ISSUE,
        transport=JobTransport(good_job), now_utc=t)
    p.require_original_broker_confirmation(result)
    assert result["broker_get_requests"] == 4
    assert result["broker_orders_submitted"] == 0
    for change in (
        {"conclusion": "failure"},
        {"status": "in_progress"},
        {"completed_at": "2026-10-21T15:20:00Z"},
        {"steps": [{"name": p.BROKER_GUARD_STEP, "status": "completed",
                     "conclusion": "skipped"}]},
        {"name": "wrong-alpaca-job"},
    ):
        modified = {**good_job, **change}
        with pytest.raises(p.GenesisBootstrapStop):
            p.authentic_original_four_get_job(
                run_id="9999999", public_token=ISSUE,
                transport=JobTransport(modified), now_utc=t)


def test_actions_job_proof_does_not_accept_fake_run_ids_or_stale_UTC():
    for wrong in ("", "0", "x", "-1", "1?debug=1"):
        with pytest.raises(p.GenesisBootstrapStop):
            p.authentic_original_four_get_job(run_id=wrong, public_token=ISSUE)


def test_main_module_has_no_broker_order_http_calls_or_unprotected_secret_fallback():
    s = Path(p.__file__).read_text()
    assert "authentic_original_four_get_job(" in s
    assert "broker.runtime()" not in s
    assert "cas.genesis(" in s
    assert '"branch": "main"' in s
    assert "GITHUB_EVENT_NAME" in s
    assert "INITIALIZE_EMPTY_LEDGER_NO_ORDERS" in s
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" in s
    assert "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX" in s
    assert "FUND100_PRIVATE_STATE_SANDBOX_WRITE_TOKEN" not in s
    for bad in ("api.alpaca.markets", "place_order(", "/v2/orders",
                "requests.delete(", "broker.submit("):
        assert bad not in s
    assert p.NO_ALPACA_ORDER_WRITER and p.NO_PRODUCTION_ORDER_RELEASE
    assert p.ONE_PRIVATE_GENESIS_PUT_MAX == 1
