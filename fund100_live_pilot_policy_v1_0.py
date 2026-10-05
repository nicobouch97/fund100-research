from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


# ============================================================
# FUND-100 LIVE MICRO-PILOT POLICY v1.0
# ============================================================
#
# PURPOSE
# -------
#
# Create the standing authorization envelope for the Fund-100
# V5-002 real-money micro-pilot.
#
# THIS MODULE:
#
# - does NOT access broker credentials
# - does NOT contact Alpaca
# - does NOT submit orders
# - does NOT change V5-002
# - does NOT itself activate trading
#
# It defines:
#
# 1. exact strategy identity
# 2. explicit externally chosen capital ceiling
# 3. long-only / no-leverage operation
# 4. permitted V5-002 universe
# 5. one-time bootstrap authorization
# 6. genuine-event-only autonomous operation afterwards
# 7. fail-closed source/hash binding
#
# ============================================================


POLICY_SCHEMA = (
    "FUND100_LIVE_MICRO_PILOT_POLICY_V1"
)

POLICY_VERSION = "1.0"

STRATEGY_ID = "V5-002_SHADOW"

RELEASE_LOCK_VERSION = "1.9"

EXECUTION_UNIVERSE = (
    "ACWI",
    "SPY",
    "IWM",
    "EFA",
    "EEM",
    "VNQ",
    "XLK",
    "XLF",
    "XLI",
    "XLV",
    "XLP",
    "XLY",
    "XLE",
    "XLU",
)

REQUIRED_SOURCE_FILES = (
    "fund100_alpaca_live_writer_candidate_v1_1.py",
    "fund100_alpaca_live_execution_orchestrator_v1_0.py",
    "fund100_alpaca_live_execution_materializer.py",
    "fund100_alpaca_live_cumulative_cap_guard_v1_0.py",
    "fund100_alpaca_live_position_reconcile.py",
    "fund100_alpaca_live_scheduled_compiler_v1_1.py",
    "fund100_v5_002_shadow.py",
    "fund100_v5_002_shadow_v1_1.py",
    "fund100_pre_live_release_lock_v1_9.py",
)

OUTPUT_DIR = Path(
    "live_activation_outputs/v5_002"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "live_micro_pilot_policy_v1_0.json"
)


class PilotPolicyStop(RuntimeError):
    pass


def sha256_file(
    path: Path,
) -> str:

    if not path.exists():

        raise PilotPolicyStop(
            "LIVE PILOT POLICY STOP: "
            f"required source missing: {path}"
        )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def decimal_money(
    value: Any,
    *,
    field_name: str,
) -> Decimal:

    try:

        result = Decimal(
            str(
                value
            )
        )

    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ) as exc:

        raise PilotPolicyStop(
            "LIVE PILOT POLICY STOP: "
            f"{field_name} is invalid."
        ) from exc

    if not result.is_finite():

        raise PilotPolicyStop(
            "LIVE PILOT POLICY STOP: "
            f"{field_name} must be finite."
        )

    return result


def validate_capital_ceiling(
    value: Any,
) -> Decimal:

    cap = decimal_money(
        value,
        field_name="pilot capital ceiling",
    )

    if cap <= Decimal("0"):

        raise PilotPolicyStop(
            "LIVE PILOT POLICY STOP: "
            "pilot capital ceiling must be positive."
        )

    # Monetary authorization is intentionally restricted
    # to cents.
    cap = cap.quantize(
        Decimal("0.01")
    )

    return cap


def build_policy(
    *,
    capital_ceiling_usd: Any,
    account_binding_sha256: str,
    shadow_state_sha256: str,
    source_hashes: dict[str, str],
    authorization_reference: str,
) -> dict:

    capital_ceiling = (
        validate_capital_ceiling(
            capital_ceiling_usd
        )
    )

    if (
        not isinstance(
            account_binding_sha256,
            str,
        )
        or len(
            account_binding_sha256
        )
        != 64
    ):

        raise PilotPolicyStop(
            "LIVE PILOT POLICY STOP: "
            "invalid account binding."
        )

    if (
        not isinstance(
            shadow_state_sha256,
            str,
        )
        or len(
            shadow_state_sha256
        )
        != 64
    ):

        raise PilotPolicyStop(
            "LIVE PILOT POLICY STOP: "
            "invalid shadow-state binding."
        )

    expected_sources = set(
        REQUIRED_SOURCE_FILES
    )

    actual_sources = set(
        source_hashes
    )

    if actual_sources != expected_sources:

        raise PilotPolicyStop(
            "LIVE PILOT POLICY STOP: "
            "source-hash set mismatch."
        )

    for filename, digest in (
        source_hashes.items()
    ):

        if (
            not isinstance(
                digest,
                str,
            )
            or len(
                digest
            )
            != 64
        ):

            raise PilotPolicyStop(
                "LIVE PILOT POLICY STOP: "
                f"invalid SHA256 for {filename}."
            )

    authorization_reference = (
        str(
            authorization_reference
        )
        .strip()
    )

    if not authorization_reference:

        raise PilotPolicyStop(
            "LIVE PILOT POLICY STOP: "
            "authorization reference is empty."
        )

    return {
        "schema":
            POLICY_SCHEMA,

        "policy_version":
            POLICY_VERSION,

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "strategy":
            STRATEGY_ID,

        "release_lock_version":
            RELEASE_LOCK_VERSION,

        "deployment_mode":
            "LIVE_MICRO_PILOT",

        "capital_ceiling_currency":
            "USD",

        "capital_ceiling_usd":
            str(
                capital_ceiling
            ),

        "capital_ceiling_is_standing_upper_bound":
            True,

        "broker_equity_above_ceiling_is_usable":
            False,

        "additional_deposits_automatically_authorized":
            False,

        "leverage_allowed":
            False,

        "shorting_allowed":
            False,

        "options_allowed":
            False,

        "crypto_allowed":
            False,

        "margin_expansion_allowed":
            False,

        "execution_universe":
            list(
                EXECUTION_UNIVERSE
            ),

        # One-time initial alignment.
        "bootstrap_alignment_allowed":
            True,

        # Once bootstrap is completed, ordinary trading must
        # be generated by a real frozen V5-002 event.
        "post_bootstrap_genuine_strategy_event_required":
            True,

        "ordinary_drift_rebalancing_allowed":
            False,

        "strategy_parameter_changes_allowed":
            False,

        "research_agent_can_change_live_strategy":
            False,

        "sell_before_buy_required":
            True,

        "fresh_broker_reconstruction_between_phases_required":
            True,

        "complete_client_id_reconstruction_required":
            True,

        "single_cumulative_event_cap_required":
            True,

        "deterministic_client_order_ids_required":
            True,

        "broker_reconciliation_after_execution_required":
            True,

        "fail_closed_on_unknown_broker_state":
            True,

        "account_binding_sha256":
            account_binding_sha256,

        "activation_shadow_state_sha256":
            shadow_state_sha256,

        "authorization_reference":
            authorization_reference,

        "source_sha256":
            dict(
                sorted(
                    source_hashes.items()
                )
            ),

        # This policy is standing authority, not an order.
        "order_authorization_present":
            False,

        "orders_submitted":
            0,
    }


def source_hashes() -> dict[str, str]:

    return {
        filename:
            sha256_file(
                Path(
                    filename
                )
            )
        for filename
        in REQUIRED_SOURCE_FILES
    }


def write_policy(
    policy: dict,
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            policy,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
