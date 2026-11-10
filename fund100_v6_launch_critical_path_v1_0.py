"""Read-only Fund-100 V6 launch dependency audit.

Local code/config inspection ONLY. No broker, private Git, network, secrets,
trading authority, or environment-variable activation. Runtime evidence must
be separately authenticated before any legitimate production release.
"""
from __future__ import annotations
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCHEMA = "FUND100_V6_OFFLINE_LIVE_CRITICAL_PATH_V1"
STAGES = {
    "first_acwi_sell": {
        "fund100_v6_s1_original_first_acwi_entry_locked_v1_0.py": ["ORIGINAL_ACWI_ENTRYPOINT_RELEASED"],
        "fund100_v6_s1_original_one_attempt_chain_locked_v1_0.py": ["ONE_ATTEMPT_EXECUTION_RELEASED"],
        "fund100_v6_s1_one_time_owner_claim_cas_v1_0.py": [
            "SIGNED_OWNER_CLAIM_TRANSPORT_RELEASED", "PREPOST_PRIVATE_CAS_RELEASED",
            "PREPOST_PUBLIC_WITNESS_RELEASED"],
        "fund100_v6_s1_immutable_release_publish_locked_v1_0.py": ["PUBLISH_SIGNED_HEAD_RELEASED"],
        "fund100_v6_s1_active_high_acwi_sell_risk_v2_0.py": ["ACTIVE_HIGH_SELL_SOURCE_RELEASED"],
        "fund100_alpaca_live_writer_candidate_v1_1.py": [
            "V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED",
            "V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED",
            "V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED",
            "V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED"],
    },
    "first_xlk_buy": {
        "fund100_v6_s1_first_xlk_buy_original_entry_locked_v1_0.py": ["FIRST_XLK_BUY_ENTRY_RELEASED"],
        "fund100_v6_s1_first_xlk_buy_autoreserve_locked_v1_0.py": ["AUTORESERVE_RUNTIME_RELEASED"],
        "fund100_v6_s1_first_xlk_buy_atomic_writer_locked_v1_0.py": ["RUNTIME_RELEASED", "BROKER_BUY_POST_RELEASED"],
        "fund100_v6_s1_first_xlk_buy_source_workflow_scope_locked_v1_0.py": [
            "FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED"],
        "fund100_v6_s1_first_xlk_asof_opportunity_getonly_locked_v1_0.py": ["SOURCE_RELEASED"],
        "fund100_v6_s1_first_acwi_buy_liquidity_getonly_locked_v1_0.py": ["SOURCE_RELEASED"],
    },
    "recurring_automation": {
        "fund100_v6_s1_recurring_rebalance_core_v1_0.py": ["LIVE_RECURRING_EXECUTION_RELEASED"],
        "fund100_v6_recurring_seq1_immutable_release_recovery_locked_v1_0.py": [
            "PRODUCTION_PUBLIC_MUTATION_RELEASED", "AUTHENTICATED_SEQ1_REMOTE_HEAD_RELEASED",
            "DURABLE_PERSISTENT_ATTEMPT_FENCE_RELEASED"],
        "fund100_v6_recurring_seq1_durable_release_attempt_fence_offline_v1_0.py": [
            "PRODUCTION_FENCE_INITIALIZATION_RELEASED",
            "PRODUCTION_SIGNED_CAS_FENCE_WRITES_RELEASED",
            "PRODUCTION_RECOVERY_SOURCE_AUTHENTICATED"],
    },
}
SCHEDULES = {
    ".github/workflows/fund100-v6-s1-original-first-acwi-funded-once.yml": "FUND100_V6_S1_FIRST_ACWI_LIVE_DEPLOYED",
    ".github/workflows/fund100-v6-s1-first-xlk-buy-funded-once.yml": "FUND100_V6_S1_FIRST_XLK_BUY_LIVE_DEPLOYED",
}

class LaunchHold(ValueError):
    pass

def source_paths():
    return sorted({p for s in STAGES.values() for p in s} |
                  set(SCHEDULES) |
                  {"fund100_live_operator_control.json", "fund100_v6_s1_operator_control.json"})

def _read(root, path):
    try:
        return (root / path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise LaunchHold("Missing launch source: " + path) from None

def _flags(root, path, expected):
    try:
        nodes = ast.parse(_read(root, path), filename=path).body
    except SyntaxError:
        raise LaunchHold("Unparseable release module: " + path) from None
    found = {}
    for n in nodes:
        if isinstance(n, ast.Assign):
            pairs = [(x.id, n.value) for x in n.targets if isinstance(x, ast.Name)]
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            pairs = [(n.target.id, n.value)]
        else:
            pairs = []
        for name, value in pairs:
            if name in expected:
                if name in found or not isinstance(value, ast.Constant) or type(value.value) is not bool:
                    raise LaunchHold("Dynamic or duplicate release flag: " + path + ":" + name)
                found[name] = value.value
    if set(found) != set(expected):
        raise LaunchHold("Missing release flag: " + path)
    return found

def _control(root, path):
    try:
        doc = json.loads(_read(root, path))
    except json.JSONDecodeError:
        raise LaunchHold("Invalid operator control: " + path) from None
    if type(doc) is not dict or type(doc.get("trading_enabled")) is not bool:
        raise LaunchHold("Unqualified operator STOP/GO: " + path)
    return doc

def snapshot(root=ROOT):
    v5 = _control(root, "fund100_live_operator_control.json")
    v6 = _control(root, "fund100_v6_s1_operator_control.json")
    if (type(v6.get("first_original_acwi_sell_enabled")) is not bool
        or v6.get("risk_level") not in ("LOW", "MEDIUM", "HIGH")
        or type(v6.get("pilot_capital_ceiling_usd")) is not str):
        raise LaunchHold("V6 source risk or sell control invalid")
    stages = {}
    for name, sources in STAGES.items():
        flags = []
        for path, keys in sources.items():
            for key, enabled in _flags(root, path, keys).items():
                flags.append({"source": path, "flag": key, "enabled": enabled})
        stages[name] = {
            "code_status": ("CODE_LOCKED" if any(not v["enabled"] for v in flags)
                            else "CODE_ENABLED_RUNTIME_UNVERIFIED"),
            "locked_flags": [v["flag"] for v in flags if not v["enabled"]],
            "flags": flags, "live_runtime_verified": False,
        }
    workflows = {}
    for path, variable in SCHEDULES.items():
        data = _read(root, path)
        for marker in (variable, "fund100-alpaca-live-account-writer",
                       "refs/heads/main", "FUND100_BROKER_KILL_SWITCH"):
            if marker not in data:
                raise LaunchHold("Dormant workflow launch contract changed: " + path)
        workflows[path] = {
            "code_contains_single_writer_and_deployment_checks": True,
            "actual_environment_deployment_or_kill_state_verified": False,
            "order_authorized": False,
        }
    return {
        "schema": SCHEMA,
        "status": "NOT_LIVE_AUTHORIZATION",
        "source_scope": "CHECKED_IN_FILES_ONLY",
        "broker_requests": 0, "private_git_requests": 0,
        "live_order_authorized": False, "capital_increase_authorized": False,
        "per_trade_user_approval_added": False,
        "checked_in_controls": {
            "v5_trading_enabled": v5["trading_enabled"],
            "v6_trading_enabled": v6["trading_enabled"],
            "v6_first_acwi_sell_enabled": v6["first_original_acwi_sell_enabled"],
            "v6_risk_level": v6["risk_level"],
            "v6_pilot_capital_ceiling_usd": v6["pilot_capital_ceiling_usd"],
        },
        "stages": stages, "dormant_schedules": workflows,
        "current_broker_private_head_immutable_and_environment_state": "NOT_VERIFIED_OFFLINE",
        "critical_path": [
            "VERIFY_FRESH_PROTECTED_SIGNED_BROKER_AND_OPERATOR_SOURCE",
            "REVIEW_AND_RELEASE_AT_MOST_ONE_ORIGINAL_ACWI_SELL",
            "RECONCILE_ACTUAL_FILL_AND_SETTLED_CASH",
            "REVIEW_AND_RELEASE_AT_MOST_ONE_ORIGINAL_XLK_BUY",
            "RELEASE_DURABLE_AUTHENTICATED_RECURRING_AUTOMATION",
        ],
        "note": "A green CI run or changed code flag cannot attest to a broker order permit. "
                "Do not flip locked flags merely to make this report pass.",
    }

if __name__ == "__main__":
    print(json.dumps(snapshot(), sort_keys=True, indent=2))
