"""Original public 2026-10-21 genesis witness for FUTURE private signed ledger.

One independent public nonce+source commitment after genuine protected LIVE
4-GET broker verification. No state write, private key, Alpaca or LIVE release.
"""
from __future__ import annotations

import json
import re
from hashlib import sha1
from pathlib import Path

import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas

ROOT = Path(__file__).resolve().parent
WITNESS = Path("research_lab/V6_S1_INITIAL_PUBLIC_LEDGER_GENESIS_WITNESS_2026_10_21.json")
WITNESS_BLOB_SHA1 = "b6fd44c4bb0b17bcd906e97c7ca8d6a50cc00a99"
POLICY = Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
MANIFEST = Path("research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json")
CONTROL = Path("fund100_live_operator_control.json")
CAS_MODULE = Path("fund100_v6_s1_private_git_cas_protocol_v1_0.py")
SCHEMA = "FUND100_V6_S1_PUBLIC_EXTERNAL_INITIAL_GENESIS_WITNESS_V1"
NO_PRIVATE_REPOSITORY_HTTP = True
NO_LEDGER_INITIALIZATION = True
NO_BROKER_ORDERS = True
NO_LIVE_RELEASE = True


class WitnessStop(ValueError):
    pass


def blob(content: bytes) -> str:
    return sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def verify(*, root: Path = ROOT) -> dict:
    if not isinstance(root, Path):
        raise WitnessStop("Invalid external genesis witness root")
    source = (root / WITNESS).read_bytes()
    if blob(source) != WITNESS_BLOB_SHA1:
        raise WitnessStop("Original independently committed public genesis changed")
    witness = json.loads(source)
    if (type(witness) is not dict
        or witness.get("schema") != SCHEMA
        or witness.get("purpose") != "ONE_TIME_PUBLIC_GENESIS_COMMITMENT_FOR_SEPARATE_PRIVATE_HMAC_LEDGER"
        or not isinstance(witness.get("public_genesis_nonce_hex"), str)
        or re.fullmatch(r"[a-f0-9]{64}", witness["public_genesis_nonce_hex"]) is None
        or witness.get("private_repo") != cas.STATE_REPO
        or witness.get("private_repo_id") != "1426833955"
        or witness.get("private_production_ledger_path") != cas.STATE_PATH
        or witness.get("original_live_broker_account_check_run_id") != 39621888269
        or witness.get("original_live_broker_account_check_utc") != "2026-10-21T15:01:08Z"
        or witness.get("private_repo_actions_read_proof_run_id") != 39600082142
        or witness.get("private_repo_sandbox_write_proof_run_id") != 39618444064
        or witness.get("private_production_missing_ledger_check_run_id") != 39620212136
        or witness.get("original_pilot_max_capital_usd") != "130.30"
        or witness.get("risk_tier") != "HIGH"
        or witness.get("original_s1_gross_entry_target") != "0.95"
        or witness.get("initial_production_ledger_head_blob_sha1") is not None
        or witness.get("initial_private_ledger_hmac_authenticated") is not False
        or witness.get("initial_production_state_created") is not False
        or witness.get("external_anchor_proves_future_private_HEAD_or_rollback_protection") is not False
        or witness.get("genesis_ledger_creation_authorized") is not False
        or witness.get("original_live_orders_authorized") is not False
        or witness.get("broker_orders") != 0):
        raise WitnessStop("Witness cannot promote a private ledger or order")
    if (witness.get("original_live_policy_path") != str(POLICY)
        or witness.get("original_live_policy_git_blob_sha1") != "ff20cb4950243c64f4d34b68e6e3170ff6cc9421"
        or witness.get("original_v6_s1_manifest_git_blob_sha1") != "4ea6af355283e68a16c2b6ec632337639894509c"
        or witness.get("original_cas_source_git_blob_sha1") != "9b9f8917faa21b4157600ac642f80595445a7276"):
        raise WitnessStop("Pinned original LIVE policy or private CAS source changed")
    if any((
        blob((root / POLICY).read_bytes()) != witness["original_live_policy_git_blob_sha1"],
        blob((root / MANIFEST).read_bytes()) != witness["original_v6_s1_manifest_git_blob_sha1"],
        blob((root / CAS_MODULE).read_bytes()) != witness["original_cas_source_git_blob_sha1"],
    )):
        raise WitnessStop("Actual original Git source content does not match genesis witness")
    policy = json.loads((root / POLICY).read_text())
    manifest = json.loads((root / MANIFEST).read_text())
    control = json.loads((root / CONTROL).read_text())
    account_binding = policy.get("account_binding_sha256")
    if (not isinstance(account_binding, str)
        or re.fullmatch(r"[a-f0-9]{64}", account_binding) is None
        or policy.get("capital_ceiling_usd") != "130.30"
        or policy.get("live_order_authorization_present") is not False
        or control.get("schema") != "FUND100_OPERATOR_CONTROL_V1"
        or control.get("trading_enabled") is not False
        or manifest.get("original_trial_max_capital_usd") != "130.30"
        or manifest.get("risk_tier") != "HIGH"
        or manifest.get("investable_gross_fraction") != "0.95"
        or manifest.get("live_operator_trading_enabled") is not False
        or manifest.get("live_environment_kill_switch") != "ENGAGED"
        or manifest.get("live_order_execution_released") is not False
        or cas.REMOTE_TRANSPORT_RELEASED is not False
        or cas.LIVE_ORDER_RELEASED is not False):
        raise WitnessStop("Original bound LIVE account/pilot/operator STOP changed")
    return {
        "status": "PUBLIC_INDEPENDENT_INITIAL_GENESIS_NONCE_COMMITTED_NO_PRIVATE_LEDGER",
        "original_public_genesis_nonce": witness["public_genesis_nonce_hex"],
        "original_live_account_binding_sha256": account_binding,
        "original_live_four_get_run": 39621888269,
        "public_initial_witness_git_blob_sha1": WITNESS_BLOB_SHA1,
        "original_cas_genesis_synthetic_function_available": True,
        "private_ledger_head_sha1_known": False,
        "original_live_broker_four_GET_reperformed_by_this_module": False,
        "private_state_genesis_created": False,
        "independent_continuity_head_anchor_complete": False,
        "private_write_credential_authorized": False,
        "live_orders_authorized": False,
        "broker_requests": 0,
        "github_write_requests": 0,
    }


def test_synthetic_genesis_compatibility(*, invented_key: bytes,
                                         root: Path = ROOT) -> dict:
    """Only a fake HMAC fixture; NEVER create a remote production ledger."""
    record = verify(root=root)
    raw = cas.genesis(
        private_genesis=record["original_public_genesis_nonce"],
        account_binding_sha256=record["original_live_account_binding_sha256"],
        key=invented_key)
    doc = json.loads(raw)
    if doc["sequence"] != 0 or doc["entries"] or doc["prior_document_sha"] is not None:
        raise WitnessStop("Original genesis encoding changed")
    return {
        "status": "SYNTHETIC_HMAC_GENESIS_FORMAT_COMPATIBLE_ONLY",
        "signed_original_genesis_verified_in_memory": True,
        "private_genesis_document_persisted": False,
        "actual_private_HMAC_key_present": False,
        "independent_genesis_head_verified": False,
        "new_live_order_authorized": False,
        "broker_requests": 0,
        "github_write_requests": 0,
        "private_genesis_bytes": None,
        "account_binding_sha256": None,
    }


def main() -> None:
    import sys
    result = verify()
    safe = {
        "status": result["status"],
        "original_live_four_get_run": result["original_live_four_get_run"],
        "original_cas_genesis_synthetic_function_available":
            result["original_cas_genesis_synthetic_function_available"],
        "private_state_genesis_created": result["private_state_genesis_created"],
        "independent_continuity_head_anchor_complete":
            result["independent_continuity_head_anchor_complete"],
        "live_orders_authorized": result["live_orders_authorized"],
        "broker_requests": result["broker_requests"],
        "github_write_requests": result["github_write_requests"],
    }
    sys.stdout.write(json.dumps(safe, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()
