from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import fund100_alpaca_live_readonly_smoke as live
import fund100_alpaca_live_preflight as preflight

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 ALPACA LIVE EXECUTION BOUNDARY v1.0
# ============================================================
#
# LIVE ENVIRONMENT — WRITE CAPABILITY INTENTIONALLY ABSENT.
#
# This module establishes the boundary between:
#
#   READ-ONLY LIVE VALIDATION
#
# and any possible future:
#
#   LIVE ORDER EXECUTION
#
# There is deliberately NO HTTP POST implementation here.
# There is deliberately NO order-submission endpoint here.
#
# Any attempt to call submit_live_order() fails closed.
#
# ============================================================


STATE_PATH = Path(
    "shadow_outputs/v5_002/shadow_state.json"
)

EXPECTED_LIVE_HOST = (
    "api.alpaca.markets"
)

EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

BOUNDARY_ARM_VALUE = (
    "YES_READ_ONLY_LIVE_BOUNDARY"
)

LIVE_WRITE_MODE_ENV = (
    "FUND100_LIVE_WRITE_MODE"
)

LIVE_WRITE_MODE_DISABLED = (
    "DISABLED"
)


class LiveOrderSubmissionDisabled(
    RuntimeError
):
    pass


# ============================================================
# WRITE MODE
# ============================================================

def get_live_write_mode() -> str:

    value = (
        os.environ.get(
            LIVE_WRITE_MODE_ENV,
            "",
        )
        .strip()
        .upper()
    )

    # Missing configuration fails safe.
    if value == "":

        return LIVE_WRITE_MODE_DISABLED

    # v1.0 supports no state other than DISABLED.
    if value != LIVE_WRITE_MODE_DISABLED:

        return "INVALID"

    return LIVE_WRITE_MODE_DISABLED


def require_live_writes_disabled():

    mode = (
        get_live_write_mode()
    )

    if mode != LIVE_WRITE_MODE_DISABLED:

        raise RuntimeError(
            "LIVE SAFETY STOP: "
            "v1.0 accepts only "
            "FUND100_LIVE_WRITE_MODE=DISABLED."
        )


# ============================================================
# BOUNDARY ARM
# ============================================================

def require_boundary_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_LIVE_BOUNDARY_TEST",
            "",
        )
        .strip()
    )

    if value != BOUNDARY_ARM_VALUE:

        raise RuntimeError(
            "Live execution-boundary test "
            "is not explicitly armed."
        )


# ============================================================
# ENDPOINT VALIDATION
# ============================================================

def validate_live_endpoint():

    parsed = urlparse(
        live.LIVE_BASE_URL
    )

    if (
        parsed.scheme != "https"
        or parsed.hostname != EXPECTED_LIVE_HOST
    ):

        raise RuntimeError(
            "LIVE SAFETY STOP: "
            "unexpected live broker endpoint."
        )

    print(
        "Live broker hostname: PASS"
    )


# ============================================================
# SHADOW STATE
# ============================================================

def load_state():

    if not STATE_PATH.exists():

        raise RuntimeError(
            "V5-002 shadow state is missing."
        )

    with STATE_PATH.open(
        "r"
    ) as f:

        state = json.load(
            f
        )

    if (
        state.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
    ):

        raise RuntimeError(
            "Unexpected V5-002 strategy identity."
        )

    if not state.get(
        "last_date"
    ):

        raise RuntimeError(
            "V5-002 state has no last_date."
        )

    return state


# ============================================================
# LIVE WRITE BOUNDARY
# ============================================================

def submit_live_order():

    # --------------------------------------------------------
    # IMPORTANT
    #
    # There is intentionally no implementation behind this
    # interface.
    #
    # Future live execution work must replace this boundary
    # explicitly rather than accidentally inheriting paper
    # execution behavior.
    # --------------------------------------------------------

    raise LiveOrderSubmissionDisabled(
        "LIVE ORDER SUBMISSION DISABLED: "
        "Fund-100 v1.0 contains no live write path."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE EXECUTION BOUNDARY"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA LIVE"
    )

    print(
        f"Broker endpoint: "
        f"{live.LIVE_BASE_URL}"
    )

    print(
        "\nMode: READ ONLY"
    )

    print(
        "Live order submission implementation: ABSENT"
    )

    print(
        "Live cancellation implementation: ABSENT"
    )

    print(
        "Live replacement implementation: ABSENT"
    )

    # ========================================================
    # FUND-100 KILL SWITCH
    # ========================================================

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"\nFund-100 broker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE BOUNDARY SAFETY STOP: "
            "broker kill switch must be ENGAGED."
        )

    print(
        "Kill-switch safety state: PASS"
    )

    # ========================================================
    # LIVE WRITE MODE
    # ========================================================

    require_live_writes_disabled()

    print(
        f"Live write mode: "
        f"{get_live_write_mode()}"
    )

    print(
        "Live-write configuration: PASS"
    )

    # ========================================================
    # TEST ARM
    # ========================================================

    require_boundary_arm()

    print(
        "Boundary-test arm: PASS"
    )

    validate_live_endpoint()

    # ========================================================
    # READ-ONLY CREDENTIALS
    # ========================================================

    live.require_readonly_arm()

    key, secret = (
        live.load_credentials()
    )

    print(
        "Live credential presence: PASS"
    )

    # ========================================================
    # ACCOUNT
    # ========================================================

    account = (
        live.get_json(
            path="/v2/account",
            key=key,
            secret=secret,
        )
    )

    preflight.validate_account(
        account
    )

    # ========================================================
    # POSITIONS
    # ========================================================

    positions = (
        live.get_json(
            path="/v2/positions",
            key=key,
            secret=secret,
        )
    )

    if not isinstance(
        positions,
        list,
    ):

        raise RuntimeError(
            "Invalid live positions response."
        )

    print(
        f"\nLive positions visible: "
        f"{len(positions)}"
    )

    # ========================================================
    # OPEN ORDERS
    # ========================================================

    open_orders = (
        live.get_json(
            path="/v2/orders",
            key=key,
            secret=secret,
            params={
                "status":
                    "open",

                "limit":
                    100,
            },
        )
    )

    if not isinstance(
        open_orders,
        list,
    ):

        raise RuntimeError(
            "Invalid live open-order response."
        )

    print(
        f"Live open orders visible: "
        f"{len(open_orders)}"
    )

    # ========================================================
    # ASSETS
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "LIVE ASSET RECHECK"
    )

    print(
        "============================================"
    )

    for symbol in (
        preflight.REQUIRED_SYMBOLS
    ):

        asset = (
            live.get_json(
                path=(
                    "/v2/assets/"
                    + symbol
                ),
                key=key,
                secret=secret,
            )
        )

        preflight.validate_asset(
            symbol=
                symbol,

            asset=
                asset,
        )

    # ========================================================
    # V5-002 STATE
    # ========================================================

    state = (
        load_state()
    )

    print(
        "\n============================================"
    )

    print(
        "STRATEGY EXECUTION CONTEXT"
    )

    print(
        "============================================"
    )

    print(
        f"\nV5-002 state date: "
        f"{state['last_date']}"
    )

    pending = (
        state.get(
            "pending_target"
        )
    )

    if pending is None:

        print(
            "Genuine V5-002 pending event: NO"
        )

    else:

        source = str(
            state.get(
                "pending_source",
                "UNKNOWN",
            )
        )

        if source not in {
            "SCHEDULED",
            "EMERGENCY",
        }:

            raise RuntimeError(
                "Unexpected V5-002 pending source."
            )

        print(
            "Genuine V5-002 pending event: YES"
        )

        print(
            f"Event source: {source}"
        )

        print(
            "Live execution still disabled."
        )

    # ========================================================
    # DELIBERATELY TEST WRITE BOUNDARY
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "LIVE WRITE-BLOCK TEST"
    )

    print(
        "============================================"
    )

    try:

        submit_live_order()

    except LiveOrderSubmissionDisabled as exc:

        print(
            f"\n{exc}"
        )

        print(
            "Attempted live write blocked: PASS"
        )

    else:

        raise RuntimeError(
            "LIVE SAFETY FAILURE: "
            "write boundary did not block."
        )

    # ========================================================
    # FINAL
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "LIVE EXECUTION BOUNDARY: PASS"
    )

    print(
        "============================================"
    )

    print(
        "\nLive API authentication: PASS"
    )

    print(
        "Live environment inspection: PASS"
    )

    print(
        "Live order-write boundary: PASS"
    )

    print(
        "Live order implementation present: NO"
    )

    print(
        "Orders submitted: 0"
    )

    print(
        "Orders replaced: 0"
    )

    print(
        "Orders cancelled: 0"
    )

    print(
        "Broker state modified: NO"
    )

    print(
        "Fund-100 kill switch remained: ENGAGED"
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
            "LIVE EXECUTION BOUNDARY: FAILED",
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
