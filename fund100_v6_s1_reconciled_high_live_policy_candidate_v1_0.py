"""V6-S1 versioned HIGH LIVE policy CANDIDATE, no broker/order authority.

The original V5 $130.30 account binding is preserved and remains STOPPED.
This proves one internally consistent V6 HIGH economic candidate while
rejecting an incorrect XLE forced exit and a silent V5 25% override.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha1
import json
from pathlib import Path

import fund100_v6_s1_independent_high_exante_policy_v1_0 as high
import fund100_v6_s1_frac_live_sell_writer_candidate_v1_0 as sell
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas

ROOT = Path(__file__).resolve().parent
PROPOSAL = Path("research_lab/V6_S1_HIGH_RECONCILED_LIVE_EXECUTION_POLICY_CANDIDATE_2026_10_21.json")
ORIGINAL_MANIFEST = Path("research_lab/v6_s1_high_risk_micro_pilot_proposed_manifest.json")
ORIGINAL_V5_POLICY = Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")
ORIGINAL_OPERATOR = Path("fund100_live_operator_control.json")
HIGH_SOURCE = Path("fund100_v6_s1_independent_high_exante_policy_v1_0.py")
SELL_SOURCE = Path("fund100_v6_s1_frac_live_sell_writer_candidate_v1_0.py")
CAS_SOURCE = Path("fund100_v6_s1_private_git_cas_protocol_v1_0.py")
SCHEMA = "FUND100_V6_S1_RECONCILED_HIGH_LIVE_EXECUTION_POLICY_CANDIDATE_V1"
EXPECTED_LEGACY = ("ACWI", "EEM", "XLV")
EXPECTED_RETAIN = "XLE"
EXPECTED_BUYS = ("XLK", "XLE", "IWM")
EXPECTED_TARGETS = {
    "XLK": Decimal(".475"), "XLE": Decimal(".285"), "IWM": Decimal(".190")}
EXPECTED_CASH = Decimal(".05")
EXPECTED_GROSS = Decimal(".95")
EXPECTED_MAX_SYMBOL = Decimal(".50")
REAL_LIVE_ORDER_TRANSPORT_RELEASED = False


class PolicyReconciliationStop(ValueError):
    pass


def _sha(bytes_: bytes) -> str:
    return sha1(b"blob " + str(len(bytes_)).encode() + b"\x00" + bytes_).hexdigest()


def _json(root: Path, path: Path) -> dict:
    obj = json.loads((root / path).read_bytes())
    if type(obj) is not dict:
        raise PolicyReconciliationStop("Invalid policy JSON object")
    return obj


def _money(value: object) -> Decimal:
    if type(value) is not str:
        raise PolicyReconciliationStop("Currency/risk values require exact decimal strings")
    try:
        num = Decimal(value)
    except Exception:
        raise PolicyReconciliationStop("Malformed policy decimal") from None
    if not num.is_finite() or num < 0 or value.lower().find("e") >= 0:
        raise PolicyReconciliationStop("Noncanonical or invalid policy amount")
    return num


def contract(*, root: Path = ROOT) -> dict:
    if not isinstance(root, Path):
        raise PolicyReconciliationStop("Invalid independent policy repository")
    p = _json(root, PROPOSAL)
    v5 = _json(root, ORIGINAL_V5_POLICY)
    old = _json(root, ORIGINAL_MANIFEST)
    control = _json(root, ORIGINAL_OPERATOR)
    expected_schema = {
        "schema": SCHEMA,
        "status": "RECONCILED_PROPOSED_NOT_LIVE",
        "source_prior_live_v5_policy": str(ORIGINAL_V5_POLICY),
        "source_original_v6_exploratory_manifest": str(ORIGINAL_MANIFEST),
        "risk_tier": "HIGH",
        "original_live_pilot_capital_ceiling_usd": "130.30",
        "active_strategy_candidate": "V6_S1_FIXED_SECTOR_RISK_PREMIUM",
        "legacy_nonoverlap_etfs_to_sell_in_sequence": list(EXPECTED_LEGACY),
        "retained_original_overlap_symbol": EXPECTED_RETAIN,
        "retained_overlap_may_be_sold_automatically": False,
        "retained_overlap_above_target_requires_independent_review": True,
        "original_exploratory_manifest_lists_XLE_for_legacy_exit": True,
        "original_V5_HIGH_max_satellite_weight_fraction": "0.25",
        "requires_new_separate_V6_risk_policy_instead_of_silent_V5_override": True,
        "after_sells_require_independent_broker_fill_and_flat_reconciliation": True,
        "before_buys_require_independently_authenticated_settled_cash": True,
        "before_buys_require_5pct_cash_at_execution": True,
        "broker_order_idempotency_requires_pre_POST_signed_persistent_CAS": True,
        "future_signed_private_head_advances_independently_anchored": False,
        "real_live_full_broker_fill_history_reconciled": False,
        "execution_authorized": False,
        "broker_sell_authorized": False,
        "broker_buy_authorized": False,
        "production_ledger_future_state_advances_released": False,
        "separately_signed_live_release_present": False,
        "operator_trading_enabled": False,
        "environment_kill_switch": "ENGAGED",
        "V5_old_policy_mutated": False,
        "V6_exploratory_manifest_mutated": False,
        "original_private_signed_ledger_mutated": False,
        "trade_requests": 0,
        "evidence_original_four_get_run_id": 39636438731,
        "evidence_actual_empty_production_genesis_run_id": 39637082911,
        "evidence_independent_hmac_recovery_run_id": 39638576563,
    }
    for key, expected in expected_schema.items():
        if p.get(key) != expected or type(p.get(key)) is not type(expected):
            raise PolicyReconciliationStop("Proposed contract/STOP/source stage mismatch")
    sha_pairs = (
        ("source_prior_live_v5_policy_git_blob_sha1",
         ORIGINAL_V5_POLICY, "ff20cb4950243c64f4d34b68e6e3170ff6cc9421"),
        ("source_original_v6_exploratory_manifest_git_blob_sha1",
         ORIGINAL_MANIFEST, "4ea6af355283e68a16c2b6ec632337639894509c"),
        ("source_independent_v6_high_contract_git_blob_sha1",
         HIGH_SOURCE, "cb5c2ac943ba786a3c535715a6e0dcf3f7dc66b2"),
        ("source_existing_fractional_sell_adapter_git_blob_sha1",
         SELL_SOURCE, "b18d23664197ac791a129aef970921cd3c9efc01"),
        ("source_existing_signed_private_CAS_protocol_git_blob_sha1",
         CAS_SOURCE, "9b9f8917faa21b4157600ac642f80595445a7276"),
    )
    for field, source, expected in sha_pairs:
        if p.get(field) != expected or _sha((root/source).read_bytes()) != expected:
            raise PolicyReconciliationStop("Source-pinned original LIVE policy changed")
    if (v5.get("schema") != "FUND100_LIVE_MICRO_PILOT_POLICY_V1_1"
        or v5.get("capital_ceiling_usd") != "130.30"
        or v5.get("live_order_authorization_present") is not False
        or v5.get("strategy") != "V5-002_SHADOW"
        or old.get("status") != "PROPOSED_NOT_LIVE"
        or old.get("original_trial_max_capital_usd") != "130.30"
        or old.get("risk_tier") != "HIGH"
        or old.get("legacy_holdings_must_be_reconciled_and_exited_before_any_buy")
            != ["ACWI", "EEM", "XLE", "XLV"]
        or old.get("live_operator_trading_enabled") is not False
        or old.get("live_environment_kill_switch") != "ENGAGED"
        or old.get("live_order_execution_released") is not False
        or control.get("schema") != "FUND100_OPERATOR_CONTROL_V1"
        or control.get("trading_enabled") is not False):
        raise PolicyReconciliationStop("Original pinned LIVE account and STOP invalid")
    targets = p.get("proposed_target_weights")
    if (type(targets) is not dict or set(targets) != set(EXPECTED_TARGETS)
        or {s:_money(w) for s,w in targets.items()} != EXPECTED_TARGETS
        or {s:_money(w) for s,w in old["target_weights"].items()} != EXPECTED_TARGETS):
        raise PolicyReconciliationStop("V6 target weights are not original exploratory figures")
    cash = _money(p.get("order_time_cash_floor_fraction"))
    gross = _money(p.get("max_gross_exposure_fraction"))
    maximum = _money(p.get("maximum_single_symbol_fraction"))
    if (cash != EXPECTED_CASH or gross != EXPECTED_GROSS
        or maximum != EXPECTED_MAX_SYMBOL
        or sum(EXPECTED_TARGETS.values()) != gross
        or cash + gross != Decimal("1")
        or max(EXPECTED_TARGETS.values()) > maximum):
        raise PolicyReconciliationStop("V6 allocation/gross/cash impossible")
    limits = {
        "maximum_new_order_notional_usd": "65.00",
        "minimum_new_buy_notional_usd": "1.00",
        "maximum_daily_account_loss_fraction": "0.06",
        "maximum_peak_to_trough_drawdown_fraction": "0.20",
        "maximum_annual_realized_account_volatility": "0.35",
    }
    if any(p.get(key) != amount or type(p.get(key)) is not str
           for key, amount in limits.items()):
        raise PolicyReconciliationStop("Original V6 HIGH loss/order limits changed")
    if (high.SELL != EXPECTED_LEGACY
        or high.RETAIN != (EXPECTED_RETAIN,)
        or high.TARGET != EXPECTED_TARGETS
        or sell.LEGACY_TO_EXIT != EXPECTED_LEGACY
        or sell.PRESERVE_OVERLAP != EXPECTED_RETAIN
        or cas.LEGACY != EXPECTED_LEGACY
        or tuple(cas.CLIENT_IDS) != EXPECTED_LEGACY
        or cas.REMOTE_TRANSPORT_RELEASED is not False
        or cas.LIVE_ORDER_RELEASED is not False
        or high.RELEASE_LIVE_ORDER_EXECUTION is not False
        or sell.TRANSPORT_RELEASED is not False
        or sell.PUBLIC_EXECUTION_ENABLED is not False
        or REAL_LIVE_ORDER_TRANSPORT_RELEASED is not False):
        raise PolicyReconciliationStop("Source-locked signed ledger/order id or transport mismatch")
    return {
        "schema": SCHEMA,
        "stage": "RECONCILED_SEPARATE_V6_HIGH_PROPOSED_POLICY_NO_ORDERS",
        "legacy_sells_in_order": list(EXPECTED_LEGACY),
        "retains_original_XLE_subject_to_target": True,
        "new_V6_HIGH_strategy_uses_separate_50pct_symbol_limit": True,
        "V5_25pct_cap_remains_on_old_V5_only": True,
        "target_weights": dict(p["proposed_target_weights"]),
        "source_pinned_original_manifest_unchanged": True,
        "current_original_operator_stopped": True,
        "production_genesis_independent_HMAC_recovery_historical_run": 39638576563,
        "privileged_future_head_rollback_still_possible": True,
        "actual_broker_state_reauthenticated_by_this_module": False,
        "all_original_order_ids_and_settlement_reconciled": False,
        "orders_authorized": False,
        "separately_signed_release_present": False,
        "broker_GETs": 0,
        "broker_POSTs": 0,
        "private_Git_writes": 0,
    }


if __name__ == "__main__":
    answer = contract()
    print(json.dumps(answer, indent=2, sort_keys=True))
