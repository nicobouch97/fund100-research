"""V6-S1: actual original read-only private production ledger preflight.

All source/identity tests fabricated. Never initializes or writes state.
"""
from base64 import b64encode
from copy import deepcopy
from pathlib import Path
from shutil import copy2

import pytest

import fund100_v6_s1_private_production_ledger_getonly_preflight_v1_0 as p
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_private_state_actions_readonly_probe_v1_0 as orig


TEST_KEY = b"unique-synthetic-hmac-key-only-do-not-use" + b"z" * 20
GENESIS = "a"*64
BINDING = "b"*64


def signed_source():
    raw = cas.genesis(
        private_genesis=GENESIS,
        account_binding_sha256=BINDING, key=TEST_KEY)
    return {
        "path": cas.STATE_PATH,
        "type": "file",
        "encoding": "base64",
        "sha": cas.blob_sha(raw),
        "content": b64encode(raw).decode(),
    }


def identity(*, url, token):
    assert token == "synthetic-read-only-token"
    if url == orig.BASE:
        return {
            "full_name": orig.EXPECTED_REPO,
            "id": int(orig.EXPECTED_REPO_ID),
            "private": True,
            "default_branch": "main",
            "archived": False,
        }
    assert url == orig.BASE + "/contents/README.md?ref=main"
    return {
        "path": "README.md", "type": "file",
        "encoding": "base64",
        "sha": "0" * 40,
        "content": "IyBzeW50aGV0aWM=",
    }


def probe(response):
    seen = []
    def fetch(*, token):
        seen.append(token)
        return response
    report = p.runtime(
        token="synthetic-read-only-token", identity_get=identity,
        contents_get=fetch)
    assert seen == ["synthetic-read-only-token"]
    return report


def test_original_public_stop_and_source_exact_three_GET_ceiling():
    assert p.stopped()
    assert p.NO_BROKER and p.NO_WRITE and p.NO_LIVE_RELEASE
    assert p.REPO == "nicobouch97/fund100-state-private"
    assert p.PATH == "state/v6_s1_original_legacy_sales.json"
    assert p.URL.endswith("/contents/state/v6_s1_original_legacy_sales.json?ref=main")


def test_real_missing_source_remains_hard_stop_without_bootstrap():
    r = probe(None)
    assert r["status"] == "MISSING_OR_UNAVAILABLE_PRODUCTION_LEDGER_STOP"
    assert r["protected_read_identity_and_README_verified"]
    assert r["production_ledger_hmac_and_external_genesis_anchor_verified"] is False
    assert not r["unexpected_missing_ledger_can_auto_initialize"]
    assert not r["new_broker_trade_authority"]
    assert r["github_get_requests"] == 3
    assert r["github_write_requests"] == r["alpaca_requests"] == r["live_orders"] == 0
    assert r["private_remote_state_content"] is None


def test_existing_signed_source_without_external_head_anchor_not_proven():
    r = probe(signed_source())
    assert r["status"] == "PRESENT_UNANCHORED_PRODUCTION_LEDGER_STOP"
    assert not r["production_ledger_hmac_and_external_genesis_anchor_verified"]
    assert r["remote_production_git_blob_sha"] is None


def test_explicit_supplied_hmac_head_and_sequence_but_no_live_promotion():
    s = signed_source()
    result = p.verify_with_explicit_anchor(
        source=s, expected_head_blob_sha=s["sha"],
        expected_sequence=0, private_genesis=GENESIS,
        account_binding_sha256=BINDING, key=TEST_KEY)
    assert result["status"] == "SUPPLIED_ANCHOR_AND_HMAC_AGREE_OFFLINE_ONLY"
    assert not result["supplied_anchor_independently_authenticated_by_this_module"]
    assert not result["live_order_authorized"]
    assert not result["remote_production_trading_transport_released"]
    assert result["production_writes"] == result["broker_requests"] == 0
    assert result["original_account_binding"] is None


@pytest.mark.parametrize("mutate", [
    {"expected_head_blob_sha": "0"*40},
    {"expected_head_blob_sha": "not-git-sha"},
    {"expected_sequence": 1},
    {"expected_sequence": -1},
    {"expected_sequence": True},
    {"private_genesis": "c"*64},
    {"account_binding_sha256": "d"*64},
    {"key": b"bad-key"},
])
def test_any_signature_account_binding_or_rollback_mismatch_blocks(mutate):
    s = signed_source()
    values = dict(
        source=s, expected_head_blob_sha=s["sha"],
        expected_sequence=0, private_genesis=GENESIS,
        account_binding_sha256=BINDING, key=TEST_KEY)
    values.update(mutate)
    with pytest.raises(p.PrivateLedgerReadStop):
        p.verify_with_explicit_anchor(**values)


def test_signed_source_payload_tamper_against_matching_git_sha_rejected():
    s = signed_source()
    import json
    from base64 import b64decode
    d = json.loads(b64decode(s["content"]))
    d["entries"]["ACWI"] = {"something": "forged"}
    raw = json.dumps(d).encode()
    s["content"] = b64encode(raw).decode()
    s["sha"] = cas.blob_sha(raw)
    with pytest.raises(p.PrivateLedgerReadStop, match="HMAC"):
        p.verify_with_explicit_anchor(
            source=s, expected_head_blob_sha=s["sha"],
            expected_sequence=0, private_genesis=GENESIS,
            account_binding_sha256=BINDING, key=TEST_KEY)


@pytest.mark.parametrize("wrong", [
    {"path": "sandbox/v6_s1_actions_cas_smoke_2026_10_21.json"},
    {"type": "dir"},
    {"encoding": "utf-8"},
    {"sha": "g"*40},
    {"content": None},
])
def test_unexpected_remote_source_shape_cannot_promote_to_present(wrong):
    s = signed_source()
    s.update(wrong)
    with pytest.raises(p.PrivateLedgerReadStop):
        probe(s)


def test_original_readonly_identity_mismatch_fails_even_if_state_exists():
    def impostor(*, url, token):
        x=identity(url=url, token=token)
        if url == orig.BASE:
            x["private"] = False
        return x
    with pytest.raises(p.PrivateLedgerReadStop, match="source authentication"):
        p.runtime(token="synthetic-read-only-token",
                  identity_get=impostor,
                  contents_get=lambda *,token: signed_source())


def test_missing_auth_token_fails_before_ledger_read():
    called=[]
    def invalid(*, url, token):
        called.append(url)
        raise orig.PrivateRepoProbeStop("No READ credentials")
    with pytest.raises(p.PrivateLedgerReadStop):
        p.runtime(token="", identity_get=invalid,
                  contents_get=lambda *,token: signed_source())
    assert called == [orig.BASE]


def test_mutated_original_stop_guard_refuses_any_private_fetch(tmp_path):
    for name in (
        "fund100_live_operator_control.json",
        "research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json",
    ):
        src=p.ROOT/name
        dst=tmp_path/name
        dst.parent.mkdir(parents=True, exist_ok=True)
        copy2(src,dst)
    assert p.stopped(tmp_path)
    control=tmp_path/"fund100_live_operator_control.json"
    content=control.read_text().replace('"trading_enabled": false',
                                        '"trading_enabled": true')
    control.write_text(content)
    calls=[]
    assert not p.stopped(tmp_path)
    with pytest.raises(p.PrivateLedgerReadStop, match="STOP"):
        p.runtime(token="synthetic",root=tmp_path,
                  identity_get=lambda **kw: calls.append(kw),
                  contents_get=lambda **kw: calls.append(kw))
    assert calls==[]


def test_module_has_only_original_readonly_private_GET_and_zero_broker_writes():
    src=Path(p.__file__).read_text()
    for forbidden in (
        "method=\"PUT\"", "method='PUT'", "method=\"POST\"",
        "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET", "place_order(",
        "api.alpaca.markets", "/v2/orders",
        "FUND100_PRIVATE_STATE_SANDBOX_WRITE_TOKEN",
        "FUND100_PRIVATE_STATE_WRITE_TOKEN",
    ):
        assert forbidden not in src
