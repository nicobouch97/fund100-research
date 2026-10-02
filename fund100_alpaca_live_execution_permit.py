from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 LIVE EXECUTION PERMIT GATE v1.0
# ============================================================
#
# THIS VERSION CAN NEVER ISSUE A LIVE PERMIT.
#
# Its purpose is to prove that:
#
# - synthetic compiler output is rejected
# - stale / corrupt compiler output is rejected
# - no-event output is rejected
# - any source claiming live authorization is rejected
# - any non-zero live monetary cap is rejected
# - any source claiming network write capability is rejected
#
# Output:
#
#   permit_issued = FALSE
#
# There is NO broker network access in this file.
# ============================================================


COMPILER_PATH = Path(
    "live_dryrun_outputs/v5_002/"
    "scheduled_execution_time.json"
)

OUTPUT_DIR = Path(
    "live_dryrun_outputs/v5_002"
)

PERMIT_PATH = (
    OUTPUT_DIR
    / "live_execution_permit.json"
)

PERMIT_ARM_VALUE = (
    "YES_VALIDATE_LIVE_PERMIT_BOUNDARY"
)

EXPECTED_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1"
)


# ============================================================
# HASHING
# ============================================================

def canonical_json(
    obj,
) -> str:

    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def sha256_json(
    obj,
) -> str:

    return hashlib.sha256(
        canonical_json(
            obj
        ).encode(
            "utf-8"
        )
    ).hexdigest()


# ============================================================
# ARM
# ============================================================

def require_permit_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_LIVE_PERMIT_VALIDATION",
            "",
        )
        .strip()
    )

    if value != PERMIT_ARM_VALUE:

        raise RuntimeError(
            "Live permit-boundary validation "
            "is not explicitly armed."
        )


# ============================================================
# LOAD / VERIFY COMPILER OUTPUT
# ============================================================

def load_compiler_package():

    if not COMPILER_PATH.exists():

        raise RuntimeError(
            "Scheduled compiler output is missing."
        )

    with COMPILER_PATH.open(
        "r"
    ) as f:

        package = json.load(
            f
        )

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            "Invalid scheduled compiler package."
        )

    if (
        "compiler" not in package
        or "compiler_sha256" not in package
    ):

        raise RuntimeError(
            "Scheduled compiler package "
            "is incomplete."
        )

    body = (
        package[
            "compiler"
        ]
    )

    recorded_hash = str(
        package[
            "compiler_sha256"
        ]
    )

    calculated_hash = (
        sha256_json(
            body
        )
    )

    if recorded_hash != calculated_hash:

        raise RuntimeError(
            "LIVE PERMIT STOP: "
            "scheduled compiler SHA256 "
            "verification failed."
        )

    if (
        body.get(
            "schema"
        )
        != EXPECTED_SCHEMA
    ):

        raise RuntimeError(
            "Unexpected scheduled-compiler schema."
        )

    return package


# ============================================================
# FAIL-CLOSED VALIDATION
# ============================================================

def determine_denial_reason(
    body: dict,
) -> str:

    # --------------------------------------------------------
    # v1.0 is deliberately incapable of authorization.
    #
    # We still classify WHY the artifact must not execute.
    # --------------------------------------------------------

    if bool(
        body.get(
            "network_write_capability",
            True,
        )
    ):

        raise RuntimeError(
            "LIVE PERMIT SAFETY STOP: "
            "source artifact unexpectedly claims "
            "network write capability."
        )

    if bool(
        body.get(
            "live_execution_authorized",
            True,
        )
    ):

        raise RuntimeError(
            "LIVE PERMIT SAFETY STOP: "
            "source artifact unexpectedly claims "
            "live execution authorization."
        )

    cap = float(
        body.get(
            "max_live_execution_notional_usd",
            -1.0,
        )
    )

    if abs(
        cap
    ) > 1e-12:

        raise RuntimeError(
            "LIVE PERMIT SAFETY STOP: "
            "source artifact has a non-zero "
            "live execution ceiling."
        )

    if (
        body.get(
            "broker_write_mode"
        )
        != "DISABLED"
    ):

        raise RuntimeError(
            "LIVE PERMIT SAFETY STOP: "
            "broker write mode is not DISABLED."
        )

    mode = str(
        body.get(
            "compiler_mode",
            "",
        )
    ).lower()

    status = str(
        body.get(
            "status",
            "",
        )
    )

    genuine = bool(
        body.get(
            "genuine_scheduled_event",
            False,
        )
    )

    if mode == "synthetic":

        return (
            "SYNTHETIC_ARTIFACT_NEVER_EXECUTABLE"
        )

    if status == "NO_SCHEDULED_EVENT":

        return (
            "NO_GENUINE_STRATEGY_EVENT"
        )

    if not genuine:

        return (
            "GENUINE_EVENT_FLAG_FALSE"
        )

    # Even a genuine event remains denied in v1.0.
    return (
        "LIVE_AUTHORIZATION_NOT_IMPLEMENTED"
    )


# ============================================================
# BUILD DENIED PERMIT
# ============================================================

def build_permit(
    compiler_package: dict,
    denial_reason: str,
):

    body = (
        compiler_package[
            "compiler"
        ]
    )

    permit_body = {
        "schema":
            "FUND100_LIVE_EXECUTION_PERMIT_V1",

        "strategy":
            body.get(
                "strategy"
            ),

        "strategy_state_date":
            body.get(
                "strategy_state_date"
            ),

        "source_compiler_sha256":
            compiler_package[
                "compiler_sha256"
            ],

        "source_compiler_mode":
            body.get(
                "compiler_mode"
            ),

        "source_compiler_status":
            body.get(
                "status"
            ),

        "genuine_scheduled_event":
            bool(
                body.get(
                    "genuine_scheduled_event",
                    False,
                )
            ),

        # ----------------------------------------------------
        # HARD SAFETY STATE
        # ----------------------------------------------------

        "permit_issued":
            False,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "broker_write_mode":
            "DISABLED",

        "denial_reason":
            denial_reason,
    }

    permit_hash = (
        sha256_json(
            permit_body
        )
    )

    return {
        "permit_sha256":
            permit_hash,

        "permit":
            permit_body,
    }


# ============================================================
# WRITE / VERIFY
# ============================================================

def write_permit(
    package: dict,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with PERMIT_PATH.open(
        "w"
    ) as f:

        json.dump(
            package,
            f,
            indent=2,
            sort_keys=True,
        )

        f.write(
            "\n"
        )

    with PERMIT_PATH.open(
        "r"
    ) as f:

        stored = json.load(
            f
        )

    recorded = str(
        stored[
            "permit_sha256"
        ]
    )

    calculated = (
        sha256_json(
            stored[
                "permit"
            ]
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            "Stored permit hash verification failed."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 LIVE EXECUTION PERMIT GATE"
    )

    print(
        "============================================"
    )

    print(
        "\nPermit implementation: DENY ONLY"
    )

    print(
        "Live broker access: NONE"
    )

    print(
        "Live order submission: IMPOSSIBLE"
    )

    # ========================================================
    # SAFETY CONFIG
    # ========================================================

    require_permit_arm()

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"\nBroker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE PERMIT SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    print(
        "Kill-switch safety state: PASS"
    )

    # ========================================================
    # COMPILER OUTPUT
    # ========================================================

    package = (
        load_compiler_package()
    )

    body = (
        package[
            "compiler"
        ]
    )

    print(
        "Scheduled compiler SHA256: PASS"
    )

    print(
        f"Compiler mode: "
        f"{body.get('compiler_mode')}"
    )

    print(
        f"Compiler status: "
        f"{body.get('status')}"
    )

    print(
        f"Genuine scheduled event: "
        f"{bool(body.get('genuine_scheduled_event', False))}"
    )

    # ========================================================
    # DENIAL
    # ========================================================

    denial_reason = (
        determine_denial_reason(
            body
        )
    )

    permit = (
        build_permit(
            compiler_package=
                package,

            denial_reason=
                denial_reason,
        )
    )

    write_permit(
        permit
    )

    # ========================================================
    # PROVE IT CANNOT AUTHORIZE
    # ========================================================

    stored = (
        permit[
            "permit"
        ]
    )

    if bool(
        stored[
            "permit_issued"
        ]
    ):

        raise RuntimeError(
            "CRITICAL SAFETY FAILURE: "
            "v1.0 issued a live permit."
        )

    if bool(
        stored[
            "live_execution_authorized"
        ]
    ):

        raise RuntimeError(
            "CRITICAL SAFETY FAILURE: "
            "live execution became authorized."
        )

    if abs(
        float(
            stored[
                "max_live_execution_notional_usd"
            ]
        )
    ) > 1e-12:

        raise RuntimeError(
            "CRITICAL SAFETY FAILURE: "
            "live execution ceiling is non-zero."
        )

    # ========================================================
    # REPORT
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "LIVE EXECUTION PERMIT"
    )

    print(
        "============================================"
    )

    print(
        "\nPermit issued: FALSE"
    )

    print(
        f"Denial reason: "
        f"{denial_reason}"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    print(
        "Network write capability: ABSENT"
    )

    print(
        f"Permit SHA256: "
        f"{permit['permit_sha256']}"
    )

    print(
        "Permit hash verification: PASS"
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE PERMIT DENIAL GATE: PASS"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print(
            "\n============================================",
            file=sys.stderr,
        )

        print(
            "LIVE PERMIT GATE: FAILED",
            file=sys.stderr,
        )

        print(
            "============================================",
            file=sys.stderr,
        )

        print(
            str(
                exc
            ),
            file=sys.stderr,
        )

        raise
