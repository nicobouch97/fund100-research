"""All-public-release HTTP operations synthetic: never invoke live publisher in pytest."""
from base64 import b64encode
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import json
from urllib.error import HTTPError
from urllib.request import Request

import pytest

import fund100_v6_recurring_immutable_genesis_v2_once_v1_0 as mod
import fund100_v6_recurring_event_signed_journal_v1_0 as journal
import fund100_v6_recurring_private_protected_getonly_v1_0 as private
import fund100_v6_s1_private_git_cas_protocol_v1_0 as gitblob
from test_fund100_v6_recurring_protected_genesis_transport_candidate_v1_0 import (
    READ, WRITE, KEY, NONCE, ACCOUNT, WITNESS, ENV as OLD,
)

ENV = dict(
    OLD, GITHUB_SHA="c"*40, GITHUB_WORKFLOW_REF=mod.WORKFLOW_REF,
    FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN="fake-immutable-admin-token",
    FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN="fake-release-publisher-token",
)


def original_sources(monkeypatch):
    genesis = private._recurring_genesis_candidate(NONCE, ACCOUNT)
    raw = journal.initial_bytes(
        genesis_sha256=genesis, account_binding_sha256=ACCOUNT, key=KEY)
    blob = gitblob.blob_sha(raw)
    monkeypatch.setattr(mod, "PINNED_INITIAL_BLOB_SHA", blob)
    source = {
        "type":"file", "path":journal.PATH, "encoding":"base64",
        "sha":blob, "content":b64encode(raw).decode("ascii"),
    }
    return source, blob


def inspect(env):
    assert env["GITHUB_REPOSITORY"] == mod.PUBLIC_REPO
    return {
        "status":"HMAC_VERIFIED_CANDIDATE_RECURRING_HEAD_STILL_NO_IMMUTABLE_ANCHOR",
        "original_signed_legacy_seq1_verified_with_both_principals":True,
        "recurring_signed_head_verified":True,
        "broker_posts":0,
    }


class Response:
    status = 200
    def __init__(self, status, data):
        self.status = status
        self.io = BytesIO(json.dumps(data).encode())
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size): return self.io.read(size)


class FakeGitHubRelease:
    def __init__(self):
        self.calls = []
        self.asset = b""
        self.draft = None
        self.published = None
        self.invalid_setting = False
        self.invalid_uploaded_digest = False
        self.invalid_published_immutable = False
        self.lost_draft_ack = False
        self.present_tag = False
        self.err_status = None
        self.extra_asset = False
        self.id = 841

    def __call__(self, req, timeout):
        assert timeout == 12
        method = req.get_method()
        url = req.full_url
        self.calls.append((method, url))
        if self.err_status is not None and method != "GET":
            raise HTTPError(url, self.err_status, "fake", {}, None)
        if method == "GET" and url == mod.SETTING_URL:
            return Response(200, {"enabled":not self.invalid_setting,
                                  "enforced_by_owner":False})
        if method == "GET" and url == mod.TAG_URL:
            if self.published is not None:
                return Response(200, self.published)
            if self.present_tag:
                return Response(200, {"id":1,"tag_name":mod.TAG})
            raise HTTPError(url, 404, "fake", {}, None)
        if method == "POST" and url == mod.RELEASE_URL:
            payload = json.loads(req.data)
            assert payload["draft"] is True and payload["tag_name"] == mod.TAG
            if type(payload.get("make_latest")) is not str or payload["make_latest"] != "false":
                raise HTTPError(url, 422, "Invalid enum", {}, None)
            assert payload["target_commitish"] == ENV["GITHUB_SHA"]
            # GitHub REST Create Release: make_latest is a STRING enum,
            # not a JSON boolean. A real 422 can otherwise be masked by
            # a permissive fake transport.
            if (type(payload.get("make_latest")) is not str
                or payload["make_latest"] not in ("true", "false", "legacy")):
                raise HTTPError(url, 422, "invalid make_latest type", {}, None)
            assert payload["make_latest"] == "false"
            self.draft = {
                "id":self.id, "draft":True, "tag_name":mod.TAG,
                "target_commitish":ENV["GITHUB_SHA"], "assets":[],
            }
            if self.lost_draft_ack:
                raise TimeoutError("fake draft created, acknowledgement lost")
            return Response(201, self.draft)
        if method == "POST" and url.endswith("/assets?name=" + mod.ASSET):
            assert self.draft is not None and not self.published
            self.asset = req.data
            self.uploaded = {
                "name":mod.ASSET, "size":len(self.asset), "state":"uploaded",
                "digest":("sha256:" + ("0"*64 if self.invalid_uploaded_digest
                                       else sha256(self.asset).hexdigest())),
                "browser_download_url":mod.DOWNLOAD_URL,
            }
            return Response(201, self.uploaded)
        if method == "PATCH" and url == mod.RELEASE_URL + "/" + str(self.id):
            assert json.loads(req.data) == {"draft":False}
            self.published = {
                "id":self.id, "draft":False, "tag_name":mod.TAG,
                "immutable":not self.invalid_published_immutable,
                "assets":[self.uploaded] + ([{}] if self.extra_asset else []),
            }
            return Response(200, self.published)
        raise AssertionError("Unexpected remote GitHub operation")


def run(fake, monkeypatch, env=None, source=None):
    fixture, blob = original_sources(monkeypatch)
    if source is not None: fixture = source
    calls = []
    def get_fn(*, token):
        assert token in (READ, WRITE)
        calls.append(token)
        return fixture
    report = mod.publish_once(
        environ=ENV if env is None else env, transport=fake,
        witness_doc=WITNESS, inspect_fn=inspect, get_fn=get_fn)
    return report, calls, blob


def test_fake_rejects_boolean_make_latest_as_real_github_schema_requires():
    # Offline proof that the fake would reject the payload used by the
    # failed production attempt; this never invokes the retired publisher.
    fake = FakeGitHubRelease()
    payload = {
        "tag_name": mod.TAG, "target_commitish": ENV["GITHUB_SHA"],
        "draft": True, "make_latest": False,
    }
    request = Request(
        mod.RELEASE_URL, data=json.dumps(payload).encode(),
        method="POST")
    with pytest.raises(HTTPError) as exc:
        fake(request, timeout=12)
    assert exc.value.code == 422
    assert fake.draft is None


def test_signed_production_seq0_public_immutable_genesis_anchor_once(monkeypatch):
    fake = FakeGitHubRelease()
    output, reads, sha = run(fake, monkeypatch)
    assert reads == [READ, WRITE]*3
    assert output["private_genesis_blob_sha"] == sha
    assert output["provider_immutable"] is True
    assert output["future_sequence_heads_anchored"] is False
    assert output["live_broker_orders_authorized"] is False
    assert fake.published["immutable"] is True
    assert fake.published["assets"] == [fake.uploaded]
    body = json.loads(fake.asset)
    assert body["private_signed_genesis_git_blob_sha1"] == sha
    assert body["signed_sequence"] == 0
    assert body["broker_orders_authorized"] is False
    assert body["future_signed_heads_anchored"] is False
    assert "signature" not in body and "key" not in body
    assert [m for m,_ in fake.calls] == [
        "GET","GET","POST","POST","PATCH","GET"]
    assert "application/octet-stream" not in str(body)


@pytest.mark.parametrize("change", [
    {"GITHUB_EVENT_NAME":"workflow_dispatch"},
    {"GITHUB_EVENT_NAME":"pull_request"},
    {"GITHUB_REF":"refs/heads/other"},
    {"GITHUB_RUN_ATTEMPT":"2"},
    {"GITHUB_WORKFLOW_REF":"foreign"},
    {"FUND100_BROKER_KILL_SWITCH":"DISENGAGED"},
    {"FUND100_RISK_LEVEL":"MEDIUM"},
    {"FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN":READ},
])
def test_protected_environment_failure_no_http_mutation(change,monkeypatch):
    fake = FakeGitHubRelease()
    with pytest.raises(mod.AnchorStop):
        run(fake, monkeypatch, env=dict(ENV, **change))
    assert fake.calls == []


@pytest.mark.parametrize("condition", ["disabled","prior_tag"])
def test_provider_immutability_or_existing_tag_blocks_without_mutation(condition,monkeypatch):
    fake = FakeGitHubRelease()
    fake.invalid_setting = condition=="disabled"
    fake.present_tag = condition=="prior_tag"
    with pytest.raises(mod.AnchorStop):
        run(fake, monkeypatch)
    assert not any(m in ("POST","PATCH") for m,_ in fake.calls)


@pytest.mark.parametrize("fault", ["lost_ack","bad_asset_digest","not_immutable","extra_asset","http_403"])
def test_ambiguous_public_mutation_no_retry_no_trade(fault,monkeypatch):
    fake = FakeGitHubRelease()
    fake.lost_draft_ack = fault=="lost_ack"
    fake.invalid_uploaded_digest = fault=="bad_asset_digest"
    fake.invalid_published_immutable = fault=="not_immutable"
    fake.extra_asset = fault=="extra_asset"
    fake.err_status = 403 if fault=="http_403" else None
    with pytest.raises(mod.AnchorStop):
        run(fake, monkeypatch)
    assert sum(m=="POST" and u==mod.RELEASE_URL for m,u in fake.calls) <= 1
    assert sum(m=="PATCH" for m,_ in fake.calls) <= 1


def test_rejects_private_signed_blob_drift_despite_valid_hmac(monkeypatch):
    fixture, _ = original_sources(monkeypatch)
    monkeypatch.setattr(mod, "PINNED_INITIAL_BLOB_SHA", "0"*40)
    fake = FakeGitHubRelease()
    with pytest.raises(mod.AnchorStop):
        mod.publish_once(
            environ=ENV, transport=fake, witness_doc=WITNESS,
            inspect_fn=inspect,
            get_fn=lambda *,token:fixture)
    assert fake.calls == []


def test_disallow_any_private_write_broker_or_shared_original_acwi_release():
    from pathlib import Path
    source = Path(mod.__file__).read_text()
    assert mod.NO_PRIVATE_MUTATIONS
    assert mod.NO_BROKER_NETWORK_OR_TRADING
    assert mod.NO_RETRY_AFTER_ANY_PUBLIC_MUTATION
    assert "ALPACA_LIVE_KEY" not in source
    assert "ALPACA_LIVE_SECRET" not in source
    assert "method=\"PUT\"" not in source
    assert mod.TAG != __import__(
        "fund100_v6_s1_immutable_release_anchor_v1_0").TAG



def test_original_v1_release_remains_permanently_retired():
    import fund100_v6_recurring_immutable_genesis_anchor_once_v1_0 as old
    assert old.TAG != mod.TAG and old.ASSET != mod.ASSET
    assert mod.TAG.endswith("-v2-20261029")
    assert mod.ORIGINAL_V1_RELEASE_POST_PERMANENTLY_RETIRED
    assert mod.V2_DISTINCT_TAG_FROM_CONSUMED_V1
    assert mod.RELEASE_PUBLISHER_IS_SCOPED_MAIN_GITHUB_TOKEN
    with pytest.raises(old.AnchorStop, match="production RETIRED"):
        old.publish_once(environ=ENV)


def test_v2_workflow_is_main_only_for_realtime_publisher():
    workflow = Path(".github/workflows/fund100-v6-recurring-immutable-genesis-v2-once.yml").read_text()
    assert "  push:" in workflow and "  pull_request:" in workflow
    assert "  schedule:" not in workflow and "  workflow_dispatch:" not in workflow
    assert "environment: fund100-live-broker" in workflow
    assert "secrets.ALPACA_LIVE_KEY" not in workflow
    assert ("permissions:" + chr(10) + "  contents: write") in workflow
    assert ("FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN: " + chr(36) + "{{ github.token }}") in workflow
    assert "secrets.FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN" not in workflow
    assert "GITHUB_EVENT_NAME" in workflow
    assert "fund100_v6_recurring_immutable_genesis_v2_once_v1_0.py" in workflow


def test_v2_release_payload_has_correct_string_enum_and_unique_tag(monkeypatch):
    fake = FakeGitHubRelease()
    report, _, _ = run(fake, monkeypatch)
    assert report["provider_immutable"] is True
    assert report["future_sequence_heads_anchored"] is False
    assert fake.draft is not None
    assert fake.published is not None


def test_v2_module_paths_run_full_live_pr_audit():
    audit = Path(".github/workflows/fund100-live-static-audit.yml").read_text()
    pr_paths = audit.split("  pull_request:" + chr(10) + "    paths:" + chr(10), 1)[1]
    assert '      - "fund100_v6_recurring_immutable_genesis_v2_once_v1_0.py"' in pr_paths
    assert '      - "test_fund100_v6_recurring_immutable_genesis_v2_once_v1_0.py"' in pr_paths
    assert '      - ".github/workflows/fund100-v6-recurring-immutable-genesis-v2-once.yml"' in pr_paths
