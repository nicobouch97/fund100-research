"""One original public nonce witnessed after authentic LIVE four-GET, no ledger."""
import json
from pathlib import Path
from shutil import copy2

import pytest

import fund100_v6_s1_public_genesis_witness_v1_0 as w
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas


def test_real_public_nonce_pinned_to_existing_live_policy():
    r = w.verify()
    assert r["status"] == "PUBLIC_INDEPENDENT_INITIAL_GENESIS_NONCE_COMMITTED_NO_PRIVATE_LEDGER"
    assert len(r["original_public_genesis_nonce"]) == 64
    assert r["original_live_four_get_run"] == 39621888269
    assert r["original_live_account_binding_sha256"] == (
        "1739bb3720c916ccfc6732ecd24236ab0cdbbbc1915879e0296d15fb055f49bf")
    assert r["public_initial_witness_git_blob_sha1"] == w.WITNESS_BLOB_SHA1
    assert not r["private_state_genesis_created"]
    assert not r["independent_continuity_head_anchor_complete"]
    assert not r["live_orders_authorized"]
    assert not r["private_write_credential_authorized"]
    assert r["broker_requests"] == r["github_write_requests"] == 0


def test_original_hmac_cas_compatible_only_for_fake_key():
    synthetic = b"fixed-synthetic-not-a-real-hmac-key!!" + b"x" * 30
    result = w.test_synthetic_genesis_compatibility(invented_key=synthetic)
    assert result["status"] == "SYNTHETIC_HMAC_GENESIS_FORMAT_COMPATIBLE_ONLY"
    assert result["signed_original_genesis_verified_in_memory"]
    assert not result["private_genesis_document_persisted"]
    assert not result["actual_private_HMAC_key_present"]
    assert not result["independent_genesis_head_verified"]
    assert not result["new_live_order_authorized"]
    assert result["private_genesis_bytes"] is None
    assert result["account_binding_sha256"] is None


def test_short_or_wrong_key_blocked_without_state_creation():
    for key in (b"short", b"", "wrong-type", None):
        with pytest.raises(cas.CasStop):
            w.test_synthetic_genesis_compatibility(invented_key=key)


def copy_sources(dst: Path):
    for f in (w.WITNESS, w.POLICY, w.MANIFEST, w.CONTROL, w.CAS_MODULE):
        (dst / f).parent.mkdir(parents=True, exist_ok=True)
        copy2(w.ROOT / f, dst / f)


def test_witness_public_nonce_tamper_rejected(tmp_path):
    copy_sources(tmp_path)
    assert w.verify(root=tmp_path)
    path = tmp_path / w.WITNESS
    doc = json.loads(path.read_text())
    doc["public_genesis_nonce_hex"] = "f" * 64
    path.write_text(json.dumps(doc))
    with pytest.raises(w.WitnessStop, match="witness changed"):
        w.verify(root=tmp_path)


def test_public_initial_witness_does_not_pretend_external_HEAD_anchor(tmp_path):
    copy_sources(tmp_path)
    path = tmp_path / w.WITNESS
    doc = json.loads(path.read_text())
    doc["initial_production_ledger_head_blob_sha1"] = "0" * 40
    doc["genesis_ledger_creation_authorized"] = True
    path.write_text(json.dumps(doc, indent=2))
    with pytest.raises(w.WitnessStop):
        w.verify(root=tmp_path)


def test_source_policy_or_HMAC_algorithm_change_refuses_previous_witness(tmp_path):
    copy_sources(tmp_path)
    original = tmp_path / w.POLICY
    original.write_bytes(original.read_bytes() + b" ")
    with pytest.raises(w.WitnessStop, match="Actual original Git source"):
        w.verify(root=tmp_path)
    copy_sources(tmp_path)
    original = tmp_path / w.CAS_MODULE
    original.write_bytes(original.read_bytes() + b" ")
    with pytest.raises(w.WitnessStop, match="Actual original Git source"):
        w.verify(root=tmp_path)


def test_operator_stop_cannot_be_overridden_by_public_nonce(tmp_path):
    copy_sources(tmp_path)
    path=tmp_path / w.CONTROL
    obj=json.loads(path.read_text())
    obj["trading_enabled"] = True
    path.write_text(json.dumps(obj))
    with pytest.raises(w.WitnessStop, match="operator STOP"):
        w.verify(root=tmp_path)


def test_source_code_never_reads_real_pat_or_writes_private_ledger():
    s=Path(w.__file__).read_text()
    for forbidden in (
        "FUND100_PRIVATE_STATE_SANDBOX_WRITE_TOKEN",
        "FUND100_PRIVATE_STATE_WRITE_TOKEN",
        "FUND100_PRIVATE_STATE_READ_TOKEN",
        "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET",
        "urlopen(",
        "requests.post(",
        "requests.put(",
        "method=\"PUT\"",
        "/v2/orders",
        "place_order(",
    ):
        assert forbidden not in s
    assert w.NO_PRIVATE_REPOSITORY_HTTP
    assert w.NO_LEDGER_INITIALIZATION
    assert w.NO_BROKER_ORDERS
    assert w.NO_LIVE_RELEASE
