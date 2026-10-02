from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import fund100_alpaca_live_readonly_smoke as live
import fund100_alpaca_live_preflight as preflight
import fund100_alpaca_live_execution_boundary as boundary
import fund100_alpaca_live_manifest as manifest_v1

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 ALPACA LIVE ORDER-INTENT VALIDATOR v1.0
# ============================================================
#
# LIVE ACCOUNT — READ ONLY.
#
# This module validates the deterministic live manifest and
# converts a genuine strategy event into NON-EXECUTABLE
# order intents.
#
# IMPORTANT:
#
# - NO POST
# - NO PATCH
# - NO PUT
# - NO DELETE
# - NO LIVE ORDER SUBMISSION
#
# Current safety state required:
#
#   live_execution_authorized = FALSE
#   max_live_execution_notional_usd = 0.00
#   FUND100_BROKER_KILL_SWITCH = ENGAGED
#   FUND100_LIVE_WRITE_MODE = DISABLED
#
# ============================================================


STATE_PATH = Path(
    "shadow_outputs/v5_002/shadow_state.json"
)

MANIFEST_PATH = Path(
    "live_dryrun_outputs/v5_002/live_execution_manifest.json"
)

OUTPUT_DIR = Path(
    "live_dryrun_outputs/v5_002"
)

INTENT_PATH = (
    OUTPUT_DIR
    / "live_order_intents.json"
)

EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

INTENT_ARM_VALUE = (
    "YES_READ_ONLY_LIVE_INTENTS"
)

CORE_SYMBOL = "ACWI"

WEIGHT_EPSILON = 1e-8


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
# SAFETY ARM
# ============================================================

def require_intent_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_LIVE_INTENT_VALIDATION",
            "",
        )
        .strip()
    )

    if value != INTENT_ARM_VALUE:

        raise RuntimeError(
            "Live order-intent validator "
            "is not explicitly armed."
        )


# ============================================================
# LOAD / VERIFY MANIFEST
# ============================================================

def load_manifest():

    if not MANIFEST_PATH.exists():

        raise RuntimeError(
            "Live dry-run manifest is missing."
        )

    with MANIFEST_PATH.open(
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
            "Invalid live manifest package."
        )

    if "manifest" not in package:

        raise RuntimeError(
            "Live manifest body is missing."
        )

    body = (
        package[
            "manifest"
        ]
    )

    recorded_hash = str(
        package.get(
            "manifest_sha256",
            "",
        )
    )

    calculated_hash = (
        sha256_json(
            body
        )
    )

    if recorded_hash != calculated_hash:

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "manifest SHA256 verification failed."
        )

    manifest_id = str(
        package.get(
            "manifest_id",
            "",
        )
    )

    if not manifest_id:

        raise RuntimeError(
            "Live manifest ID is missing."
        )

    if (
        body.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
    ):

        raise RuntimeError(
            "Unexpected strategy in live manifest."
        )

    if bool(
        body.get(
            "live_execution_authorized",
            True,
        )
    ):

        raise RuntimeError(
            "LIVE INTENT SAFETY STOP: "
            "v1.0 requires live authorization FALSE."
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
            "LIVE INTENT SAFETY STOP: "
            "v1.0 requires live monetary cap $0.00."
        )

    if (
        body.get(
            "broker_write_mode"
        )
        != "DISABLED"
    ):

        raise RuntimeError(
            "Live manifest write mode is not DISABLED."
        )

    return package


# ============================================================
# VERIFY CURRENT STRATEGY STATE
# ============================================================

def load_and_verify_state(
    manifest_body: dict,
):

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
            "Unexpected V5-002 strategy state."
        )

    state_hash = (
        sha256_json(
            state
        )
    )

    expected_hash = str(
        manifest_body.get(
            "strategy_state_sha256",
            "",
        )
    )

    if state_hash != expected_hash:

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "strategy state has changed since "
            "the live manifest was compiled. "
            "Regenerate the manifest first."
        )

    manifest_date = str(
        manifest_body.get(
            "strategy_state_date",
            "",
        )
    )

    state_date = str(
        state.get(
            "last_date",
            "",
        )
    )

    if manifest_date != state_date:

        raise RuntimeError(
            "LIVE INTENT STOP: "
            "manifest/state dates disagree."
        )

    return state


# ============================================================
# LIVE POSITIONS — GET ONLY
# ============================================================

def load_live_positions(
    key: str,
    secret: str,
):

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

    allowed = set(
        preflight.REQUIRED_SYMBOLS
    )

    output = {}

    for position in positions:

        symbol = str(
            position.get(
                "symbol",
                "",
            )
        ).upper()

        if not symbol:

            raise RuntimeError(
                "Live position missing symbol."
            )

        if symbol not in allowed:

            raise RuntimeError(
                "LIVE INTENT SECURITY STOP: "
                f"unexpected live position {symbol}."
            )

        if symbol in output:

            raise RuntimeError(
                f"Duplicate live position {symbol}."
            )

        side = str(
            position.get(
                "side",
                "",
            )
        ).lower()

        if (
            side
            and side != "long"
        ):

            raise RuntimeError(
                f"{symbol}: non-long live position."
            )

        market_value = float(
            position.get(
                "market_value",
                0.0,
            )
        )

        if market_value < 0:

            raise RuntimeError(
                f"{symbol}: negative live market value."
            )

        output[
            symbol
        ] = market_value

    return output


# ============================================================
# CURRENT WEIGHTS
# ============================================================

def current_weights(
    positions: dict,
):

    total = sum(
        positions.values()
    )

    if total <= 0:

        return {
            symbol: 0.0
            for symbol
            in preflight.REQUIRED_SYMBOLS
        }

    return {
        symbol:
            float(
                positions.get(
                    symbol,
                    0.0,
                )
            )
            / total
        for symbol
        in preflight.REQUIRED_SYMBOLS
    }


# ============================================================
# DETERMINISTIC CLIENT IDS
# ============================================================

def build_client_order_id(
    manifest_id: str,
    side: str,
    symbol: str,
):

    if side not in {
        "buy",
        "sell",
    }:

        raise RuntimeError(
            f"Invalid intent side {side!r}."
        )

    manifest_tag = (
        hashlib.sha256(
            manifest_id.encode(
                "utf-8"
            )
        )
        .hexdigest()[
            :12
        ]
    )

    client_id = (
        "f100live-"
        + manifest_tag
        + "-"
        + side[
            0
        ]
        + "-"
        + symbol.lower()
    )

    if len(
        client_id
    ) > 128:

        raise RuntimeError(
            "Generated client_order_id "
            "exceeds broker limit."
        )

    return client_id


# ============================================================
# COMPILE NON-EXECUTABLE INTENTS
# ============================================================

def compile_intents(
    manifest_id: str,
    body: dict,
    positions: dict,
):

    event_present = bool(
        body.get(
            "strategy_event_present",
            False,
        )
    )

    if not event_present:

        return []

    source = str(
        body.get(
            "event_source",
            "",
        )
    )

    # --------------------------------------------------------
    # IMPORTANT SCHEDULED-EVENT SAFETY RULE
    #
    # A scheduled V5-002 pending target is a desired target,
    # not yet the final execution-time target.
    #
    # The strategy's frozen minimum-trade rule is applied only
    # after next-session drift. Therefore the raw pending
    # target must NOT be turned directly into live orders.
    #
    # Until an execution-time parity calculation exists,
    # scheduled live intents fail closed.
    # --------------------------------------------------------

    if source == "SCHEDULED":

        raise RuntimeError(
            "SCHEDULED LIVE INTENT SAFETY STOP: "
            "the pending target cannot be converted "
            "directly into live orders before the "
            "execution-time threshold/parity calculation."
        )

    if source != "EMERGENCY":

        raise RuntimeError(
            "Unexpected live event source."
        )

    target = (
        body.get(
            "target_weights",
            {}
        )
    )

    if not isinstance(
        target,
        dict,
    ):

        raise RuntimeError(
            "Invalid target_weights in manifest."
        )

    current = (
        current_weights(
            positions
        )
    )

    symbols = sorted(
        set(
            target.keys()
        )
        | set(
            current.keys()
        )
    )

    intents = []

    for symbol in symbols:

        target_weight = float(
            target.get(
                symbol,
                0.0,
            )
        )

        current_weight = float(
            current.get(
                symbol,
                0.0,
            )
        )

        delta_weight = (
            target_weight
            - current_weight
        )

        if abs(
            delta_weight
        ) <= WEIGHT_EPSILON:

            continue

        side = (
            "buy"
            if delta_weight > 0
            else "sell"
        )

        cid = (
            build_client_order_id(
                manifest_id=
                    manifest_id,

                side=
                    side,

                symbol=
                    symbol,
            )
        )

        intents.append({
            "symbol":
                symbol,

            "side":
                side,

            "current_weight":
                round(
                    current_weight,
                    12,
                ),

            "target_weight":
                round(
                    target_weight,
                    12,
                ),

            "delta_weight":
                round(
                    delta_weight,
                    12,
                ),

            # Intentionally unavailable because the live
            # monetary ceiling remains zero.
            "notional_usd":
                None,

            "client_order_id":
                cid,

            "executable":
                False,
        })

    return intents


# ============================================================
# OUTPUT PACKAGE
# ============================================================

def build_intent_package(
    manifest_package: dict,
    intents: list,
):

    body = (
        manifest_package[
            "manifest"
        ]
    )

    intent_body = {
        "schema":
            "FUND100_LIVE_ORDER_INTENTS_V1",

        "manifest_id":
            manifest_package[
                "manifest_id"
            ],

        "manifest_sha256":
            manifest_package[
                "manifest_sha256"
            ],

        "strategy":
            EXPECTED_STRATEGY,

        "strategy_state_date":
            body[
                "strategy_state_date"
            ],

        "manifest_type":
            body[
                "manifest_type"
            ],

        "event_source":
            body[
                "event_source"
            ],

        "strategy_event_present":
            body[
                "strategy_event_present"
            ],

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "broker_write_mode":
            "DISABLED",

        "candidate_intents":
            intents,

        "network_write_capability":
            False,
    }

    bundle_hash = (
        sha256_json(
            intent_body
        )
    )

    return {
        "intent_bundle_sha256":
            bundle_hash,

        "intent_bundle":
            intent_body,
    }


def write_intent_package(
    package: dict,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with INTENT_PATH.open(
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

    with INTENT_PATH.open(
        "r"
    ) as f:

        stored = json.load(
            f
        )

    calculated = (
        sha256_json(
            stored[
                "intent_bundle"
            ]
        )
    )

    recorded = str(
        stored[
            "intent_bundle_sha256"
        ]
    )

    if calculated != recorded:

        raise RuntimeError(
            "Stored live intent bundle "
            "failed hash verification."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE ORDER-INTENT VALIDATOR"
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
        "Network write capability: ABSENT"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    # ========================================================
    # SAFETY CONFIGURATION
    # ========================================================

    require_intent_arm()

    kill_state = (
        get_kill_switch_state()
    )

    print(
        f"\nBroker kill switch: "
        f"{kill_state}"
    )

    if kill_state != "ENGAGED":

        raise RuntimeError(
            "LIVE INTENT SAFETY STOP: "
            "kill switch must remain ENGAGED."
        )

    print(
        "Kill-switch safety state: PASS"
    )

    boundary.require_live_writes_disabled()

    print(
        "Live write mode: DISABLED — PASS"
    )

    live.require_readonly_arm()

    # ========================================================
    # MANIFEST / STATE
    # ========================================================

    package = (
        load_manifest()
    )

    body = (
        package[
            "manifest"
        ]
    )

    print(
        "\nManifest SHA256 verification: PASS"
    )

    print(
        f"Manifest ID: "
        f"{package['manifest_id']}"
    )

    state = (
        load_and_verify_state(
            body
        )
    )

    print(
        "Strategy-state hash match: PASS"
    )

    print(
        f"V5-002 state date: "
        f"{state['last_date']}"
    )

    # ========================================================
    # LIVE GET-ONLY VALIDATION
    # ========================================================

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
            "LIVE INTENT STOP: "
            "live account contains open orders."
        )

    positions = (
        load_live_positions(
            key=
                key,

            secret=
                secret,
        )
    )

    print(
        f"\nLive positions visible: "
        f"{len(positions)}"
    )

    print(
        "Live open orders: 0 — PASS"
    )

    # ========================================================
    # INTENTS
    # ========================================================

    intents = (
        compile_intents(
            manifest_id=
                package[
                    "manifest_id"
                ],

            body=
                body,

            positions=
                positions,
        )
    )

    intent_package = (
        build_intent_package(
            manifest_package=
                package,

            intents=
                intents,
        )
    )

    write_intent_package(
        intent_package
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE ORDER INTENTS"
    )

    print(
        "============================================"
    )

    print(
        f"\nManifest type: "
        f"{body['manifest_type']}"
    )

    print(
        f"Genuine strategy event present: "
        f"{body['strategy_event_present']}"
    )

    print(
        f"Candidate intents: "
        f"{len(intents)}"
    )

    for intent in intents:

        print(
            f"\n{intent['symbol']}: "
            f"{intent['side'].upper()}"
        )

        print(
            f"  Weight delta: "
            f"{intent['delta_weight']:.3%}"
        )

        print(
            f"  Client order ID: "
            f"{intent['client_order_id']}"
        )

        print(
            "  Notional USD: UNASSIGNED"
        )

        print(
            "  Executable: FALSE"
        )

    print(
        f"\nIntent bundle SHA256: "
        f"{intent_package['intent_bundle_sha256']}"
    )

    print(
        "\nLive execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
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
        "Intent bundle hash verification: PASS"
    )

    print(
        "\n============================================"
    )

    print(
        "LIVE ORDER-INTENT GATE: PASS"
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
            "LIVE ORDER-INTENT GATE: FAILED",
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
