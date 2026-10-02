from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import fund100_alpaca_live_readonly_smoke as live
import fund100_alpaca_live_preflight as preflight
import fund100_alpaca_live_execution_boundary as boundary

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 ALPACA LIVE DRY-RUN MANIFEST v1.0
# ============================================================
#
# LIVE ACCOUNT — READ ONLY.
#
# PURPOSE:
#
#   Convert the current V5-002 strategy state into a
#   deterministic live execution manifest.
#
# IMPORTANT:
#
#   LIVE_EXECUTION_AUTHORIZED = FALSE
#   MAX_LIVE_EXECUTION_NOTIONAL_USD = 0.00
#
# This file contains no order POST implementation.
#
# ============================================================


STATE_PATH = Path(
    "shadow_outputs/v5_002/shadow_state.json"
)

OUTPUT_DIR = Path(
    "live_dryrun_outputs/v5_002"
)

MANIFEST_PATH = (
    OUTPUT_DIR
    / "live_execution_manifest.json"
)

EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

CORE_SYMBOL = "ACWI"

MANIFEST_ARM_VALUE = (
    "YES_READ_ONLY_LIVE_MANIFEST"
)

LIVE_EXECUTION_AUTHORIZED = False

MAX_LIVE_EXECUTION_NOTIONAL_USD = 0.00


# ============================================================
# CANONICAL HASHING
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
# SAFETY ARM
# ============================================================

def require_manifest_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_LIVE_MANIFEST",
            "",
        )
        .strip()
    )

    if value != MANIFEST_ARM_VALUE:

        raise RuntimeError(
            "Live dry-run manifest compiler "
            "is not explicitly armed."
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
# TARGET NORMALISATION
# ============================================================

def normalise_satellite_target(
    satellites: dict,
):

    target = {}

    satellite_total = 0.0

    for symbol, raw_weight in (
        satellites.items()
    ):

        symbol = str(
            symbol
        ).upper()

        weight = float(
            raw_weight
        )

        if weight < -1e-12:

            raise RuntimeError(
                f"{symbol}: negative target weight."
            )

        if weight <= 1e-12:

            continue

        target[
            symbol
        ] = weight

        satellite_total += weight

    if satellite_total > 1.0 + 1e-10:

        raise RuntimeError(
            "Satellite weights exceed 100%."
        )

    core_weight = (
        1.0
        - satellite_total
    )

    if core_weight < -1e-10:

        raise RuntimeError(
            "Negative ACWI core target."
        )

    target[
        CORE_SYMBOL
    ] = core_weight

    total = sum(
        target.values()
    )

    if abs(
        total
        - 1.0
    ) > 1e-8:

        raise RuntimeError(
            "Normalised target does not sum "
            "to 100%."
        )

    return {
        symbol:
            round(
                float(
                    weight
                ),
                12,
            )
        for symbol, weight
        in sorted(
            target.items()
        )
    }


# ============================================================
# BUILD STRATEGY CONTEXT
# ============================================================

def build_strategy_context(
    state: dict,
):

    pending = (
        state.get(
            "pending_target"
        )
    )

    if pending is None:

        target = (
            normalise_satellite_target(
                state.get(
                    "satellite_weights",
                    {},
                )
            )
        )

        return {
            "manifest_type":
                "NO_EVENT_SNAPSHOT",

            "event_source":
                "NONE",

            "strategy_event_present":
                False,

            "target_weights":
                target,
        }

    source = str(
        state.get(
            "pending_source",
            "",
        )
    )

    if source not in {
        "SCHEDULED",
        "EMERGENCY",
    }:

        raise RuntimeError(
            "Unexpected V5-002 pending source."
        )

    target = (
        normalise_satellite_target(
            pending
        )
    )

    return {
        "manifest_type":
            "PENDING_STRATEGY_EVENT",

        "event_source":
            source,

        "strategy_event_present":
            True,

        "target_weights":
            target,
    }


# ============================================================
# LIVE READ-ONLY VALIDATION
# ============================================================

def validate_live_environment():

    kill_state = (
        get_kill_switch_state()
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE MANIFEST SAFETY STOP: "
            "broker kill switch must be ENGAGED."
        )

    boundary.require_live_writes_disabled()

    live.require_readonly_arm()

    key, secret = (
        live.load_credentials()
    )

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

    if len(
        positions
    ) != 0:

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "live account is no longer empty."
        )

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

    if len(
        open_orders
    ) != 0:

        raise RuntimeError(
            "LIVE MANIFEST STOP: "
            "live account contains open orders."
        )

    return (
        key,
        secret,
    )


# ============================================================
# ASSET VALIDATION
# ============================================================

def validate_target_assets(
    target: dict,
    key: str,
    secret: str,
):

    for symbol in sorted(
        target.keys()
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


# ============================================================
# MANIFEST
# ============================================================

def build_manifest(
    state: dict,
    strategy_context: dict,
):

    state_hash = (
        sha256_json(
            state
        )
    )

    manifest_body = {
        "schema":
            "FUND100_LIVE_DRYRUN_MANIFEST_V1",

        "strategy":
            EXPECTED_STRATEGY,

        "strategy_state_date":
            str(
                state[
                    "last_date"
                ]
            ),

        "strategy_state_sha256":
            state_hash,

        "manifest_type":
            strategy_context[
                "manifest_type"
            ],

        "event_source":
            strategy_context[
                "event_source"
            ],

        "strategy_event_present":
            strategy_context[
                "strategy_event_present"
            ],

        "target_weights":
            strategy_context[
                "target_weights"
            ],

        "live_execution_authorized":
            LIVE_EXECUTION_AUTHORIZED,

        "max_live_execution_notional_usd":
            MAX_LIVE_EXECUTION_NOTIONAL_USD,

        # No live dollar allocation has been chosen.
        # Therefore no order notionals exist.
        "proposed_orders":
            [],

        "broker_environment":
            "ALPACA_LIVE",

        "broker_write_mode":
            "DISABLED",

        "kill_switch_required":
            "ENGAGED",
    }

    manifest_hash = (
        sha256_json(
            manifest_body
        )
    )

    manifest_id = (
        "f100-live-"
        + str(
            state[
                "last_date"
            ]
        ).replace(
            "-",
            "",
        )
        + "-"
        + manifest_hash[
            :16
        ]
    )

    return {
        "manifest_id":
            manifest_id,

        "manifest_sha256":
            manifest_hash,

        "manifest":
            manifest_body,
    }


# ============================================================
# WRITE DETERMINISTIC OUTPUT
# ============================================================

def write_manifest(
    manifest: dict,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with MANIFEST_PATH.open(
        "w"
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2,
            sort_keys=True,
        )

        f.write(
            "\n"
        )

    # Reload and prove the stored body hashes back to
    # the exact recorded hash.

    with MANIFEST_PATH.open(
        "r"
    ) as f:

        stored = json.load(
            f
        )

    recorded_hash = str(
        stored[
            "manifest_sha256"
        ]
    )

    recalculated_hash = (
        sha256_json(
            stored[
                "manifest"
            ]
        )
    )

    if recorded_hash != recalculated_hash:

        raise RuntimeError(
            "Stored live manifest hash verification "
            "failed."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE DRY-RUN MANIFEST"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA LIVE"
    )

    print(
        "Mode: READ ONLY"
    )

    print(
        "HTTP live-write implementation: ABSENT"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    # ========================================================
    # SAFETY CONFIG
    # ========================================================

    require_manifest_arm()

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"\nBroker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE MANIFEST SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    print(
        "Kill-switch safety state: PASS"
    )

    boundary.require_live_writes_disabled()

    print(
        "Live write mode: DISABLED — PASS"
    )

    # ========================================================
    # STRATEGY
    # ========================================================

    state = (
        load_state()
    )

    context = (
        build_strategy_context(
            state
        )
    )

    print(
        f"\nV5-002 state date: "
        f"{state['last_date']}"
    )

    print(
        f"Manifest type: "
        f"{context['manifest_type']}"
    )

    print(
        f"Genuine strategy event present: "
        f"{context['strategy_event_present']}"
    )

    # ========================================================
    # LIVE READ-ONLY VALIDATION
    # ========================================================

    key, secret = (
        validate_live_environment()
    )

    print(
        "\nLive account validation: PASS"
    )

    print(
        "Live positions: 0 — PASS"
    )

    print(
        "Live open orders: 0 — PASS"
    )

    # ========================================================
    # TARGET ASSETS
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "TARGET ASSET VALIDATION"
    )

    print(
        "============================================"
    )

    validate_target_assets(
        target=
            context[
                "target_weights"
            ],

        key=
            key,

        secret=
            secret,
    )

    # ========================================================
    # BUILD / STORE MANIFEST
    # ========================================================

    manifest = (
        build_manifest(
            state=
                state,

            strategy_context=
                context,
        )
    )

    write_manifest(
        manifest
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE DRY-RUN MANIFEST"
    )

    print(
        "============================================"
    )

    print(
        f"\nManifest ID: "
        f"{manifest['manifest_id']}"
    )

    print(
        f"Manifest SHA256: "
        f"{manifest['manifest_sha256']}"
    )

    print(
        "\nTarget weights:"
    )

    for symbol, weight in (
        manifest[
            "manifest"
        ][
            "target_weights"
        ].items()
    ):

        print(
            f"  {symbol}: "
            f"{float(weight):.3%}"
        )

    print(
        "\nProposed live orders: 0"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    print(
        "Orders submitted: 0"
    )

    print(
        "Broker state modified: NO"
    )

    print(
        "Manifest hash verification: PASS"
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE MANIFEST GATE: PASS"
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
            "LIVE MANIFEST GATE: FAILED",
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
