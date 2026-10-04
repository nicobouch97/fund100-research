from __future__ import annotations

import ast
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ============================================================
# FUND-100 PRE-LIVE RELEASE LOCK BUILDER v1.9
# ============================================================
#
# FINAL PURE-OFFLINE ORCHESTRATOR INTEGRATION LOCK.
#
# NO broker credentials.
# NO broker network access.
# NO order submission.
# NO LIVE authorization.
#
# Purpose:
#
# Freeze the successful Execution Orchestrator v1.0 evidence
# on top of Release Lock v1.8.
#
# This marks the OFFLINE execution-orchestration requirement
# COMPLETE.
#
# It does NOT:
#
# - release the writer
# - release the orchestrator
# - issue a permit
# - create a positive LIVE notional ceiling
# - authorize LIVE execution
# - contact Alpaca
#
# The next engineering stage after this lock is:
#
# CONNECTED ALPACA PAPER END-TO-END ORCHESTRATION
#
# ============================================================


LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1_9"
)

LOCK_VERSION = "1.9"

OUTPUT_DIR = Path(
    "live_activation_outputs/v5_002"
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "pre_live_release_lock_v1_9.json"
)

ORCHESTRATOR_EVIDENCE_PATH = (
    OUTPUT_DIR
    / "execution_orchestrator_rehearsal_v1_0.json"
)

PRIOR_LOCK_SOURCE = Path(
    "fund100_pre_live_release_lock_v1_8.py"
)

WRITER_CANDIDATE_PATH = Path(
    "fund100_alpaca_live_writer_candidate_v1_1.py"
)

ORCHESTRATOR_PATH = Path(
    "fund100_alpaca_live_execution_orchestrator_v1_0.py"
)


CRITICAL_FILES = [
    "fund100_pre_live_release_lock_v1_8.py",

    "fund100_alpaca_live_writer_candidate_v1_1.py",

    "fund100_alpaca_live_cumulative_cap_guard_v1_0.py",

    "fund100_alpaca_live_cumulative_cap_rehearsal_v1_0.py",

    "fund100_alpaca_live_execution_orchestrator_v1_0.py",

    "fund100_alpaca_live_execution_orchestrator_rehearsal_v1_0.py",

    "audit_fund100_live_boundary_v1_18.py",

    ".github/workflows/"
    "fund100-live-execution-orchestrator-rehearsal.yml",

    ".github/workflows/"
    "fund100-live-static-audit.yml",
]


REQUIRED_TRUE_EVIDENCE_FIELDS = [
    "release_lock_v1_8_source_present",

    "exact_cap_across_sell_restart_buy",

    "over_cap_blocked_before_writer",

    "lost_response_restart_reconstruction",

    "restart_duplicate_post_prevention",

    "partial_fill_full_notional_accounting",

    "unsafe_terminal_history_blocked",

    "incomplete_history_blocked",
]


class ReleaseLockStop(RuntimeError):
    pass


def sha256_file(
    path: Path,
) -> str:

    if not path.exists():

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            f"required file missing: {path}"
        )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

        while True:

            block = handle.read(
                1024 * 1024
            )

            if not block:
                break

            digest.update(
                block
            )

    return digest.hexdigest()


def load_json(
    path: Path,
) -> dict:

    if not path.exists():

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            f"required evidence missing: {path}"
        )

    try:

        body = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            f"invalid JSON: {path}"
        ) from exc

    if not isinstance(
        body,
        dict,
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            f"{path} is not a JSON object."
        )

    return body


def literal_bool_assignment(
    path: Path,
    variable_name: str,
) -> bool:

    if not path.exists():

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            f"source missing: {path}"
        )

    module = ast.parse(
        path.read_text(
            encoding="utf-8"
        ),
        filename=str(
            path
        ),
    )

    for node in module.body:

        if isinstance(
            node,
            ast.Assign,
        ):

            targets = (
                node.targets
            )

        elif isinstance(
            node,
            ast.AnnAssign,
        ):

            targets = [
                node.target
            ]

        else:
            continue

        for target in targets:

            if not isinstance(
                target,
                ast.Name,
            ):
                continue

            if (
                target.id
                != variable_name
            ):
                continue

            value = (
                node.value
            )

            if (
                isinstance(
                    value,
                    ast.Constant,
                )
                and isinstance(
                    value.value,
                    bool,
                )
            ):

                return value.value

            raise ReleaseLockStop(
                "RELEASE LOCK STOP: "
                f"{variable_name} is not a literal bool "
                f"in {path}."
            )

    raise ReleaseLockStop(
        "RELEASE LOCK STOP: "
        f"{variable_name} not found in {path}."
    )


def validate_orchestrator_evidence(
    evidence: dict,
) -> None:

    for field in (
        REQUIRED_TRUE_EVIDENCE_FIELDS
    ):

        if (
            evidence.get(
                field
            )
            is not True
        ):

            raise ReleaseLockStop(
                "RELEASE LOCK STOP: "
                "orchestrator evidence field "
                f"{field!r} is not true."
            )

    if (
        evidence.get(
            "broker_mode"
        )
        != "COMPLETELY_OFFLINE"
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "orchestrator rehearsal was not "
            "COMPLETELY_OFFLINE."
        )

    if (
        evidence.get(
            "real_broker_network_access"
        )
        != "NONE"
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "orchestrator rehearsal reports "
            "broker network access."
        )

    if (
        evidence.get(
            "broker_credentials_accessed"
        )
        is not False
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "orchestrator rehearsal reports "
            "credential access."
        )

    if (
        evidence.get(
            "writer_candidate_v1_1_transport_released"
        )
        is not False
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "writer transport was released."
        )

    if (
        evidence.get(
            "writer_candidate_v1_1_public_execution_enabled"
        )
        is not False
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "writer public execution was enabled."
        )

    if (
        evidence.get(
            "orchestrator_released"
        )
        is not False
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "orchestrator was released."
        )

    if (
        evidence.get(
            "orders_submitted_to_alpaca"
        )
        != 0
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "orchestrator rehearsal reports "
            "Alpaca order submission."
        )


def build_lock(
    *,
    evidence: dict,
    critical_hashes: dict[str, str],
    writer_transport_released: bool,
    writer_public_execution_enabled: bool,
    orchestrator_released: bool,
    orchestrator_public_execution_enabled: bool,
    kill_switch_state: str,
) -> dict:

    validate_orchestrator_evidence(
        evidence
    )

    if (
        kill_switch_state
        != "ENGAGED"
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "broker kill switch is not ENGAGED."
        )

    if (
        writer_transport_released
        is not False
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "writer transport is released."
        )

    if (
        writer_public_execution_enabled
        is not False
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "writer public execution is enabled."
        )

    if (
        orchestrator_released
        is not False
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "orchestrator is released."
        )

    if (
        orchestrator_public_execution_enabled
        is not False
    ):

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "orchestrator public execution is enabled."
        )

    expected_files = set(
        CRITICAL_FILES
    )

    actual_files = set(
        critical_hashes
    )

    if (
        actual_files
        != expected_files
    ):

        missing = (
            expected_files
            - actual_files
        )

        extra = (
            actual_files
            - expected_files
        )

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "critical hash set mismatch. "
            f"missing={sorted(missing)} "
            f"extra={sorted(extra)}"
        )

    for name, digest in (
        critical_hashes.items()
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

            raise ReleaseLockStop(
                "RELEASE LOCK STOP: "
                f"invalid SHA256 for {name}."
            )

    return {
        "schema":
            LOCK_SCHEMA,

        "release_lock_version":
            LOCK_VERSION,

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "prior_release_lock":
            "v1.8",

        "prior_release_lock_source":
            str(
                PRIOR_LOCK_SOURCE
            ),

        "engineering_status":
            "PASS",

        "broker_kill_switch":
            "ENGAGED",

        "broker_credentials_supplied":
            False,

        "broker_network_access":
            "NONE",

        "writer_candidate":
            "v1.1",

        "writer_candidate_locked":
            True,

        "writer_transport_released":
            False,

        "writer_public_execution_enabled":
            False,

        "execution_orchestrator":
            "v1.0",

        "execution_orchestrator_locked":
            True,

        "execution_orchestrator_released":
            False,

        "execution_orchestrator_public_execution_enabled":
            False,

        "execution_orchestrator_integration_required":
            False,

        "execution_orchestrator_integration_completed":
            True,

        "execution_orchestrator_release_blocker":
            False,

        "fresh_broker_reconstruction_before_each_phase":
            "LOCKED",

        "complete_authorized_client_id_reconstruction":
            "LOCKED",

        "cumulative_cap_guard_before_every_writer_call":
            "LOCKED",

        "single_permit_ceiling_across_sell_buy_phases":
            "LOCKED",

        "restart_safe_sell_buy_orchestration":
            "LOCKED",

        "lost_response_duplicate_suppression":
            "LOCKED",

        "partial_fill_full_notional_accounting":
            "LOCKED",

        "unsafe_terminal_history_fail_closed":
            "LOCKED",

        "incomplete_history_fail_closed":
            "LOCKED",

        # ----------------------------------------------------
        # NEXT REAL ENGINEERING BOUNDARY.
        # ----------------------------------------------------

        "connected_alpaca_paper_end_to_end_required":
            True,

        "connected_alpaca_paper_end_to_end_completed":
            False,

        "next_stage":
            (
                "CONNECTED_ALPACA_PAPER_"
                "END_TO_END_ORCHESTRATOR"
            ),

        # ----------------------------------------------------
        # LIVE REMAINS COMPLETELY LOCKED.
        # ----------------------------------------------------

        "connected_live_writer_release_required":
            True,

        "automatic_live_activation_allowed":
            False,

        "live_execution_authorized":
            False,

        "permit_issued":
            False,

        "maximum_live_execution_notional_usd":
            "0.00",

        "writer_connected":
            False,

        "live_orders_submitted":
            0,

        "critical_file_sha256":
            dict(
                sorted(
                    critical_hashes.items()
                )
            ),

        "orchestrator_evidence":
            {
                key:
                    evidence.get(
                        key
                    )
                for key in sorted(
                    evidence
                )
            },
    }


def main() -> None:

    print(
        "========================================"
    )

    print(
        "FUND-100 RELEASE LOCK v1.9"
    )

    print(
        "========================================"
    )

    if not PRIOR_LOCK_SOURCE.exists():

        raise ReleaseLockStop(
            "RELEASE LOCK STOP: "
            "Release Lock v1.8 source is missing."
        )

    evidence = load_json(
        ORCHESTRATOR_EVIDENCE_PATH
    )

    writer_transport_released = (
        literal_bool_assignment(
            WRITER_CANDIDATE_PATH,
            "TRANSPORT_RELEASED",
        )
    )

    writer_public_execution_enabled = (
        literal_bool_assignment(
            WRITER_CANDIDATE_PATH,
            "PUBLIC_EXECUTION_ENABLED",
        )
    )

    orchestrator_released = (
        literal_bool_assignment(
            ORCHESTRATOR_PATH,
            "ORCHESTRATOR_RELEASED",
        )
    )

    orchestrator_public_execution_enabled = (
        literal_bool_assignment(
            ORCHESTRATOR_PATH,
            "PUBLIC_EXECUTION_ENABLED",
        )
    )

    hashes = {
        filename:
            sha256_file(
                Path(
                    filename
                )
            )
        for filename in (
            CRITICAL_FILES
        )
    }

    lock = build_lock(
        evidence=evidence,
        critical_hashes=hashes,
        writer_transport_released=(
            writer_transport_released
        ),
        writer_public_execution_enabled=(
            writer_public_execution_enabled
        ),
        orchestrator_released=(
            orchestrator_released
        ),
        orchestrator_public_execution_enabled=(
            orchestrator_public_execution_enabled
        ),
        kill_switch_state=(
            os.environ.get(
                "FUND100_BROKER_KILL_SWITCH",
                "",
            )
            .strip()
            .upper()
        ),
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(
            lock,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "Prior Release Lock v1.8: VERIFIED"
    )

    print(
        "Execution orchestrator v1.0: LOCKED"
    )

    print(
        "Orchestrator rehearsal evidence: LOCKED"
    )

    print(
        "Fresh broker reconstruction before each phase: LOCKED"
    )

    print(
        "Complete authorized-ID reconstruction: LOCKED"
    )

    print(
        "Cumulative-cap guard before every writer call: LOCKED"
    )

    print(
        "Single permit ceiling across SELL + BUY: LOCKED"
    )

    print(
        "Restart-safe orchestration: LOCKED"
    )

    print(
        "Execution orchestrator integration: COMPLETE"
    )

    print(
        "Execution orchestrator release blocker: NO"
    )

    print(
        "Connected Alpaca PAPER end-to-end required: YES"
    )

    print(
        "Connected LIVE writer release still required: YES"
    )

    print(
        "Automatic LIVE activation allowed: FALSE"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Permit issued: FALSE"
    )

    print(
        "Maximum LIVE execution notional: $0.00"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        "LIVE orders submitted: 0"
    )

    print(
        "Evidence written: "
        + str(
            OUTPUT_PATH
        )
    )

    print(
        "========================================"
    )

    print(
        "FUND-100 ORCHESTRATOR BASELINE "
        "LOCK v1.9 COMPLETE"
    )

    print(
        "========================================"
    )


if __name__ == "__main__":
    main()
