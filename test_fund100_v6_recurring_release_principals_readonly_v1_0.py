"""Credentialless protected release GET diagnostic; zero HTTP mutations."""
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

import fund100_v6_recurring_release_principals_readonly_v1_0 as mod

ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_REPOSITORY": "nicobouch97/fund100-research",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_EVENT_NAME": "push",
    "GITHUB_WORKFLOW_REF": mod.WORKFLOW_REF,
    "FUND100_BROKER_KILL_SWITCH": "ENGAGED",
    "FUND100_RISK_LEVEL": "HIGH",
    "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN": "synthetic-immutable-admin-only",
    "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN": "synthetic-publisher-readonly-only",
}


class Reply:
    status = 200
    def __init__(self, data):
        self.reader = BytesIO(json.dumps(data).encode())
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, n): return self.reader.read(n)


class Fake:
    def __init__(self):
        self.calls = []
        self.repo_push = True
        self.draft = False
        self.published = False
        self.git_tag = False
        self.reject = None
        self.bad_immutable = False
        self.list_full = False

    def __call__(self, req, timeout):
        assert timeout == 12
        assert req.get_method() == "GET"
        assert req.data is None
        assert req.full_url in mod.PATHS
        url = req.full_url
        assert req.get_header("Authorization") in (
            "Bearer " + ENV["FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN"],
            "Bearer " + ENV["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"])
        self.calls.append(url)
        if self.reject == url:
            raise HTTPError(url, 403, "fake", {}, None)
        if url == mod.SELF:
            return Reply({"login": "synthetic-owner"})
        if url == mod.REPO:
            return Reply({"full_name": mod.PUBLIC_REPO if hasattr(mod, "PUBLIC_REPO")
                          else "nicobouch97/fund100-research",
                          "permissions": {"push":self.repo_push}})
        if url == mod.SETTING:
            return Reply({"enabled":not self.bad_immutable,"enforced_by_owner":False})
        if url == mod.DRAFTS:
            items = ([{"tag_name":mod.anchor.TAG,"draft":not self.published}]
                     if self.draft or self.published else [])
            if self.list_full:
                items = [{"tag_name":f"test-{i}","draft":False}
                         for i in range(100)]
            return Reply(items)
        if url == mod.TAG:
            if self.published:
                return Reply({"tag_name":mod.anchor.TAG,"draft":False})
            raise HTTPError(url, 404, "fake", {}, None)
        if url == mod.GIT_TAG:
            if self.git_tag:
                return Reply({"ref":"refs/tags/"+mod.anchor.TAG})
            raise HTTPError(url, 404, "fake", {}, None)
        raise AssertionError("Unknown GET source")


def test_private_original_public_releases_empty_is_not_retry_permission():
    fake = Fake()
    result = mod.inspect(environ=ENV, transport=fake)
    assert fake.calls == [mod.SELF, mod.REPO, mod.SETTING, mod.DRAFTS,
                          mod.TAG, mod.GIT_TAG]
    assert result["status"] == "ORIGINAL_RELEASE_NOT_VISIBLE_BUT_POST_CONSUMED_HOLD"
    assert result["release_publisher_authenticated"]
    assert result["provider_immutable_setting_get_confirmed"]
    assert result["original_tag_draft_visible"] is False
    assert result["new_original_release_retry_authorized"] is False
    assert result["absence_of_hidden_draft_proven"] is False
    assert result["github_release_write_permission_proven"] is False
    assert result["original_release_post_rejection_http_code_proven"] is False
    assert result["old_make_latest_boolean_schema_invalid"] is True
    assert result["private_mutations"] == result["public_mutations"] == 0
    assert result["broker_orders"] == 0 and result["trading_still_stopped"]


def test_hidden_existing_draft_causes_hold_not_publish():
    fake = Fake()
    fake.draft = True
    result = mod.inspect(environ=ENV, transport=fake)
    assert result["status"] == "ORIGINAL_RELEASE_DRAFT_VISIBLE_HOLD"
    assert result["original_tag_draft_visible"] is True
    assert result["new_original_release_retry_authorized"] is False


def test_published_original_release_cannot_be_recreated():
    fake = Fake()
    fake.published = True
    fake.git_tag = True
    result = mod.inspect(environ=ENV, transport=fake)
    assert result["status"] == "ORIGINAL_RELEASE_VISIBLE_HOLD"
    assert result["original_git_tag_ref_visible"] is True
    assert result["new_original_release_retry_authorized"] is False


@pytest.mark.parametrize("change", [
    {"GITHUB_REPOSITORY": "other/repo"},
    {"GITHUB_REF": "refs/heads/danger"},
    {"GITHUB_RUN_ATTEMPT": "2"},
    {"GITHUB_EVENT_NAME": "workflow_dispatch"},
    {"GITHUB_WORKFLOW_REF": "other"},
    {"FUND100_BROKER_KILL_SWITCH": "DISENGAGED"},
    {"FUND100_RISK_LEVEL": "LOW"},
    {"FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN":
        ENV["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"]},
    {"FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN": ""},
])
def test_no_wrong_principal_context_can_even_query_private_or_public(change):
    fake = Fake()
    with pytest.raises(mod.ReadOnlyStop):
        mod.inspect(environ=dict(ENV, **change), transport=fake)
    assert fake.calls == []


@pytest.mark.parametrize("endpoint", [
    mod.SELF, mod.REPO, mod.SETTING, mod.DRAFTS, mod.TAG, mod.GIT_TAG])
def test_broken_provider_get_is_a_hold(endpoint):
    fake = Fake()
    fake.reject = endpoint
    with pytest.raises(mod.ReadOnlyStop):
        mod.inspect(environ=ENV, transport=fake)
    assert all(url in mod.PATHS for url in fake.calls)
    assert not any(url.endswith("/contents") for url in fake.calls)


def test_provider_immutability_disabled_holds():
    fake = Fake()
    fake.bad_immutable = True
    with pytest.raises(mod.ReadOnlyStop, match="setting"):
        mod.inspect(environ=ENV, transport=fake)


def test_pagination_full_holds_not_false_no_draft():
    fake = Fake()
    fake.list_full = True
    with pytest.raises(mod.ReadOnlyStop, match="paginated"):
        mod.inspect(environ=ENV, transport=fake)


def test_coarse_push_negative_is_not_positive_release_write_proof():
    fake = Fake()
    fake.repo_push = False
    report = mod.inspect(environ=ENV, transport=fake)
    assert report["publisher_coarse_push_metadata"] == "DENIED"
    assert report["github_release_write_permission_proven"] is False


def test_http_helper_refuses_post_and_non_allowlisted_paths():
    fake = Fake()
    with pytest.raises(mod.ReadOnlyStop, match="Unapproved"):
        mod._get_only(url=mod.BASE+"/releases/1", token="synthetic-pub",transport=fake)
    assert fake.calls == []


def test_no_mutation_code_and_readonly_workflow():
    assert mod.NO_HTTP_MUTATION and mod.NO_BROKER_NETWORK
    assert mod.NO_PRIVATE_STATE_ACCESS and mod.NO_SECRET_LOGGING
    assert mod.RELEASE_WRITE_PROVEN is False
    assert mod.ORIGINAL_RELEASE_RETRY_ALLOWED is False
    src = Path(mod.__file__).read_text()
    assert 'method="POST"' not in src
    assert 'method="PATCH"' not in src
    assert 'method="PUT"' not in src
    assert "ALPACA_LIVE_KEY" not in src
    wf = Path(".github/workflows/fund100-v6-recurring-release-principals-readonly.yml").read_text()
    assert "  workflow_dispatch:" not in wf and "  schedule:" not in wf
    assert "  push:" in wf and "  pull_request:" in wf
    assert "environment: fund100-live-broker" in wf
    assert "secrets.ALPACA_LIVE_KEY" not in wf
    assert "secrets.FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in wf
    assert "secrets.FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX" not in wf
    assert "contents: read" in wf and "contents: write" not in wf
