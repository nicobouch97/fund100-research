from __future__ import annotations

import json
import sys
from pathlib import Path

import fund100_alpaca_live_permit_v2_issuer_v1_1 as issuer
import fund100_alpaca_live_writer_disconnected_v1_1 as writer


# ============================================================
# FUND-100 LIVE DISCONNECTED ACTIVATION REHEARSAL v1.1
# ============================================================
#
# COMPLETELY OFFLINE.
#
# NO Alpaca credentials.
# NO broker API access.
# NO HTTP.
# NO real order submission.
#
# PURPOSE
# =======
#
# Prove the final pre-connected-writer boundary:
#
# 1. Current issuer-aware release lock is valid.
#
# 2. A synthetic V2 permit can satisfy the writer's permit
#    validation contract.
#
# 3. Synthetic executable intents can satisfy the full
#    frozen V5 writer-universe contract.
#
# 4. Permit-cap enforcement rejects an oversized batch.
#
# 5. The writer's public execution entrypoint still stops at
#    the unconditional hard-disconnect guard.
#
# 6. Direct GET and POST writer network helpers also stop at
#    that guard before credentials/network access.
#
# CRITICAL:
#
# The synthetic writer-compatible permit and executable
# intents exist ONLY IN MEMORY.
#
# They are NEVER persisted.
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


RELEASE_LOCK_PATH = (
    ROOT
    / "release_outputs"
    / "v5_002"
    / "pre_live_release_lock.json"
)


OUTPUT_DIR = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
)


OUTPUT_PATH = (
    OUTPUT_DIR
    / "live_activation_rehearsal_v1_1.json"
)


REHEARSAL_SCHEMA = (
    "FUND100_LIVE_DISCONNECTED_ACTIVATION_REHEARSAL_V1_1"
)


EXPECTED_LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
)


EXPECTED_PERMIT_SCHEMA = (
    "FUND100_LIVE_EXECUTION_PERMIT_V2"
)


# ------------------------------------------------------------
# PURELY SYNTHETIC TEST CEILING.
#
# This amount is not a live capital decision.
# It exists only inside this offline rehearsal.
# ------------------------------------------------------------

SYNTHETIC_PERMIT_CAP_USD = 5.00


# ============================================================
# JSON / FILE HELPERS
# ============================================================


def load_json(
    path: Path,
):

    if not path.exists():

        raise RuntimeError(
            f"Required file is missing: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(
            handle
        )


def write_output(
    package: dict,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            package,
            handle,
            indent=2,
            sort_keys=True,
        )

        handle.write(
            "\n"
        )

    stored = load_json(
        OUTPUT_PATH
    )

    recorded = str(
        stored[
            "rehearsal_sha256"
        ]
    )

    calculated = (
        writer.sha256_json(
            stored[
                "rehearsal"
            ]
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            "Stored disconnected rehearsal "
            "SHA256 verification failed."
        )


# ============================================================
# RELEASE LOCK
# ============================================================


def load_and_verify_issuer_aware_lock():

    package = load_json(
        RELEASE_LOCK_PATH
    )

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            "Invalid release-lock package."
        )

    if (
        "release_lock"
        not in package
        or
        "release_lock_sha256"
        not in package
    ):

        raise RuntimeError(
            "Incomplete release-lock package."
        )

    body = (
        package[
            "release_lock"
        ]
    )

    recorded = str(
        package[
            "release_lock_sha256"
        ]
    )

    calculated = (
        issuer.base.sha256_json(
            body
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "release-lock SHA256 verification failed."
        )

    if (
        body.get(
            "schema"
        )
        != EXPECTED_LOCK_SCHEMA
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "unexpected release-lock schema."
        )

    if (
        body.get(
            "issuer_aware_release_lock"
        )
        is not True
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "release lock is not issuer-aware."
        )

    if (
        body.get(
            "position_aware_live_chain_verified"
        )
        is not True
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "position-aware chain is not locked."
        )

    if (
        body.get(
            "v2_issuer_v1_1_source_locked"
        )
        is not True
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "V2 issuer v1.1 source is not locked."
        )

    if (
        body.get(
            "static_audit_v1_9_source_locked"
        )
        is not True
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "Static Audit v1.9 source is not locked."
        )

    if (
        body.get(
            "v2_issuer_v1_1_compatibility_upgrade_required"
        )
        is not False
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "issuer compatibility requirement "
            "has not been cleared."
        )

    if (
        body.get(
            "final_activation_lock_required_after_issuer_upgrade"
        )
        is not False
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "issuer-aware lock requirement "
            "has not been cleared."
        )

    if (
        body.get(
            "automatic_activation_allowed"
        )
        is not False
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "automatic activation unexpectedly allowed."
        )

    if (
        body.get(
            "live_execution_authorized"
        )
        is not False
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "release lock unexpectedly authorizes execution."
        )

    if (
        body.get(
            "permit_issued"
        )
        is not False
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "release lock says a permit is already issued."
        )

    if abs(
        float(
            body.get(
                "max_live_execution_notional_usd",
                -1.0,
            )
        )
    ) > 1e-12:

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "release-lock live ceiling is not $0.00."
        )

    if (
        body.get(
            "network_write_capability"
        )
        is not False
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "release lock unexpectedly has "
            "network-write capability."
        )

    if (
        body.get(
            "writer_connected"
        )
        is not False
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "release lock says writer is connected."
        )

    if not issuer.final_lock_is_ready(
        body
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "V2 issuer does not recognize "
            "the release lock as final-ready."
        )

    return (
        package,
        body,
        recorded,
    )


# ============================================================
# SYNTHETIC WRITER-COMPATIBLE PERMIT
# ============================================================


def build_in_memory_permit(
    release_lock_sha256: str,
):

    permit = {
        "schema":
            EXPECTED_PERMIT_SCHEMA,

        "strategy":
            "V5-002_SHADOW",

        # ----------------------------------------------------
        # Synthetic positive-path state.
        #
        # These values exist only to exercise writer contract
        # validation and are never written to disk.
        # ----------------------------------------------------

        "permit_issued":
            True,

        "live_execution_authorized":
            True,

        "network_write_capability":
            True,

        "broker_write_mode":
            "ENABLED",

        "genuine_scheduled_event":
            True,

        "max_live_execution_notional_usd":
            SYNTHETIC_PERMIT_CAP_USD,

        # ----------------------------------------------------
        # Explicit rehearsal markers.
        # ----------------------------------------------------

        "offline_disconnected_rehearsal":
            True,

        "synthetic_only":
            True,

        "persist_this_permit":
            False,

        # ----------------------------------------------------
        # Bind the synthetic contract to the actual locked
        # engineering baseline.
        # ----------------------------------------------------

        "source_release_lock_sha256":
            release_lock_sha256,

        "source_release_lock_schema":
            EXPECTED_LOCK_SCHEMA,

        "issuer_compatibility_layer":
            "v1.1-position-aware",

        "source_manifest_schema":
            "FUND100_LIVE_DRYRUN_MANIFEST_V1_1",

        "source_compiler_schema":
            "FUND100_SCHEDULED_EXECUTION_COMPILER_V1_1",

        # ----------------------------------------------------
        # Writer remains disconnected.
        # ----------------------------------------------------

        "writer_connected_at_issuance":
            False,

        "orders_submitted_by_issuer":
            0,
    }

    return {
        "permit_sha256":
            writer.sha256_json(
                permit
            ),

        "permit":
            permit,
    }


# ============================================================
# SYNTHETIC EXECUTABLE INTENTS
# ============================================================


def build_in_memory_intents():

    # --------------------------------------------------------
    # SPY and VNQ are deliberately selected because they prove
    # the rehearsal is exercising the full V5 universe rather
    # than only the original four-symbol writer universe.
    #
    # These intents are never sent to a broker and never
    # persisted.
    # --------------------------------------------------------

    return [
        {
            "symbol":
                "SPY",

            "side":
                "buy",

            "notional_usd":
                2.00,

            "client_order_id":
                "f100live-rehearsal-v11-b-spy",

            "executable":
                True,
        },

        {
            "symbol":
                "VNQ",

            "side":
                "sell",

            "notional_usd":
                2.00,

            "client_order_id":
                "f100live-rehearsal-v11-s-vnq",

            "executable":
                True,
        },
    ]


# ============================================================
# POSITIVE CONTRACT VALIDATION
# ============================================================


def prove_writer_contract_accepts(
    permit_package: dict,
    intents: list,
):

    (
        permit,
        cap,
    ) = (
        writer.validate_permit_package(
            permit_package
        )
    )

    if (
        permit.get(
            "schema"
        )
        != EXPECTED_PERMIT_SCHEMA
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "writer accepted unexpected permit schema."
        )

    if abs(
        float(
            cap
        )
        - SYNTHETIC_PERMIT_CAP_USD
    ) > 1e-12:

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "writer returned unexpected permit cap."
        )

    (
        validated,
        gross_notional,
    ) = (
        writer.validate_order_batch(
            intents=
                intents,

            permit_cap=
                cap,
        )
    )

    if len(
        validated
    ) != len(
        intents
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "writer did not validate the complete batch."
        )

    if (
        gross_notional
        > cap
        + 1e-9
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "validated order batch exceeds permit cap."
        )

    return {
        "permit_schema_accepted":
            True,

        "full_v5_symbols_accepted":
            True,

        "order_batch_accepted":
            True,

        "synthetic_gross_notional_usd":
            gross_notional,

        "synthetic_permit_cap_usd":
            cap,
    }


# ============================================================
# CAP-ENFORCEMENT NEGATIVE TEST
# ============================================================


def prove_cap_enforcement():

    oversized = [
        {
            "symbol":
                "SPY",

            "side":
                "buy",

            "notional_usd":
                3.00,

            "client_order_id":
                "f100live-rehearsal-cap-b-spy",

            "executable":
                True,
        },

        {
            "symbol":
                "VNQ",

            "side":
                "buy",

            "notional_usd":
                3.00,

            "client_order_id":
                "f100live-rehearsal-cap-b-vnq",

            "executable":
                True,
        },
    ]

    try:

        writer.validate_order_batch(
            intents=
                oversized,

            permit_cap=
                SYNTHETIC_PERMIT_CAP_USD,
        )

    except writer.LiveIntentRejected as exc:

        message = str(
            exc
        )

        if (
            "exceeds the execution permit ceiling"
            not in message
        ):

            raise RuntimeError(
                "DISCONNECTED REHEARSAL STOP: "
                "oversized batch failed for "
                "an unexpected reason."
            ) from exc

        return {
            "oversized_batch_rejected":
                True,

            "permit_cap_enforcement":
                True,
        }

    raise RuntimeError(
        "CRITICAL SAFETY FAILURE: "
        "writer accepted an order batch "
        "above the permit ceiling."
    )


# ============================================================
# HARD-DISCONNECT TESTS
# ============================================================


def prove_public_batch_entrypoint_disconnected(
    permit_package: dict,
    intents: list,
):

    try:

        writer.submit_authorized_order_batch(
            intents=
                intents,

            permit_package=
                permit_package,

            key=
                "offline-rehearsal-key",

            secret=
                "offline-rehearsal-secret",
        )

    except writer.LiveWriterDisconnected as exc:

        return {
            "public_batch_entrypoint_disconnected":
                True,

            "disconnect_reason":
                str(
                    exc
                ),
        }

    raise RuntimeError(
        "CRITICAL SAFETY FAILURE: "
        "writer public batch entrypoint "
        "passed the hard-disconnect guard."
    )


def prove_direct_get_disconnected():

    try:

        writer._get_order_by_client_id(
            client_order_id=
                "f100live-rehearsal-get",

            key=
                "offline-rehearsal-key",

            secret=
                "offline-rehearsal-secret",
        )

    except writer.LiveWriterDisconnected as exc:

        return {
            "direct_get_disconnected":
                True,

            "disconnect_reason":
                str(
                    exc
                ),
        }

    raise RuntimeError(
        "CRITICAL SAFETY FAILURE: "
        "writer GET helper reached beyond "
        "the hard-disconnect guard."
    )


def prove_direct_post_disconnected(
    intent: dict,
):

    try:

        writer._post_live_market_order(
            intent=
                intent,

            key=
                "offline-rehearsal-key",

            secret=
                "offline-rehearsal-secret",
        )

    except writer.LiveWriterDisconnected as exc:

        return {
            "direct_post_disconnected":
                True,

            "disconnect_reason":
                str(
                    exc
                ),
        }

    raise RuntimeError(
        "CRITICAL SAFETY FAILURE: "
        "writer POST helper reached beyond "
        "the hard-disconnect guard."
    )


# ============================================================
# OUTPUT
# ============================================================


def build_safe_output(
    *,
    release_lock_sha256: str,
    contract_result: dict,
    cap_result: dict,
    batch_disconnect: dict,
    get_disconnect: dict,
    post_disconnect: dict,
):

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # No writer-compatible permit body is stored.
    #
    # No executable order intent is stored.
    #
    # Only boolean / structural rehearsal results are persisted.
    # --------------------------------------------------------

    body = {
        "schema":
            REHEARSAL_SCHEMA,

        "strategy":
            "V5-002_SHADOW",

        "mode":
            "OFFLINE_DISCONNECTED_REHEARSAL",

        "source_release_lock_schema":
            EXPECTED_LOCK_SCHEMA,

        "source_release_lock_sha256":
            release_lock_sha256,

        "issuer_aware_release_lock_verified":
            True,

        "issuer_final_lock_recognition":
            True,

        "writer_version":
            writer.WRITER_VERSION,

        "writer_required_permit_schema":
            writer.REQUIRED_PERMIT_SCHEMA,

        "full_frozen_v5_execution_universe_verified":
            True,

        "synthetic_writer_compatible_permit_constructed":
            True,

        "synthetic_writer_compatible_permit_persisted":
            False,

        "synthetic_executable_intents_constructed":
            True,

        "synthetic_executable_intents_persisted":
            False,

        "writer_permit_contract_validation":
            contract_result[
                "permit_schema_accepted"
            ],

        "writer_order_batch_validation":
            contract_result[
                "order_batch_accepted"
            ],

        "writer_full_v5_symbol_validation":
            contract_result[
                "full_v5_symbols_accepted"
            ],

        "permit_cap_enforcement":
            cap_result[
                "permit_cap_enforcement"
            ],

        "oversized_batch_rejected":
            cap_result[
                "oversized_batch_rejected"
            ],

        "public_batch_entrypoint_disconnected":
            batch_disconnect[
                "public_batch_entrypoint_disconnected"
            ],

        "direct_writer_get_disconnected":
            get_disconnect[
                "direct_get_disconnected"
            ],

        "direct_writer_post_disconnected":
            post_disconnect[
                "direct_post_disconnected"
            ],

        "broker_credentials_supplied":
            False,

        "broker_network_access":
            False,

        "broker_get_requests_sent":
            0,

        "broker_post_requests_sent":
            0,

        "broker_write_mode":
            "DISCONNECTED",

        "writer_connected":
            False,

        "permit_issued":
            False,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "orders_submitted":
            0,

        "activation_performed":
            False,

        "connected_writer_release_still_required":
            True,
    }

    return {
        "rehearsal_sha256":
            writer.sha256_json(
                body
            ),

        "rehearsal":
            body,
    }


# ============================================================
# HARD FINAL ASSERTIONS
# ============================================================


def assert_safe_output(
    body: dict,
):

    required_true = [
        "issuer_aware_release_lock_verified",
        "issuer_final_lock_recognition",
        "full_frozen_v5_execution_universe_verified",
        "synthetic_writer_compatible_permit_constructed",
        "writer_permit_contract_validation",
        "writer_order_batch_validation",
        "writer_full_v5_symbol_validation",
        "permit_cap_enforcement",
        "oversized_batch_rejected",
        "public_batch_entrypoint_disconnected",
        "direct_writer_get_disconnected",
        "direct_writer_post_disconnected",
        "connected_writer_release_still_required",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "DISCONNECTED REHEARSAL STOP: "
                f"required safety result "
                f"{field!r} is not TRUE."
            )

    required_false = [
        "synthetic_writer_compatible_permit_persisted",
        "synthetic_executable_intents_persisted",
        "broker_credentials_supplied",
        "broker_network_access",
        "writer_connected",
        "permit_issued",
        "live_execution_authorized",
        "network_write_capability",
        "activation_performed",
    ]

    for field in required_false:

        if (
            body.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "DISCONNECTED REHEARSAL STOP: "
                f"safety field {field!r} "
                "is not FALSE."
            )

    if (
        int(
            body.get(
                "broker_get_requests_sent",
                -1,
            )
        )
        != 0
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "broker GET request count is not zero."
        )

    if (
        int(
            body.get(
                "broker_post_requests_sent",
                -1,
            )
        )
        != 0
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "broker POST request count is not zero."
        )

    if (
        int(
            body.get(
                "orders_submitted",
                -1,
            )
        )
        != 0
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "order count is not zero."
        )

    if abs(
        float(
            body.get(
                "max_live_execution_notional_usd",
                -1.0,
            )
        )
    ) > 1e-12:

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "persisted live monetary ceiling "
            "is not $0.00."
        )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 LIVE DISCONNECTED "
        "ACTIVATION REHEARSAL v1.1"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: COMPLETELY OFFLINE"
    )

    print(
        "Broker credentials supplied: NO"
    )

    print(
        "Broker network access: NONE"
    )

    print(
        "Synthetic writer-compatible permit "
        "persistence: PROHIBITED"
    )

    print(
        "Synthetic executable-intent "
        "persistence: PROHIBITED"
    )

    # ========================================================
    # LOCK
    # ========================================================

    (
        _lock_package,
        lock_body,
        release_lock_sha256,
    ) = (
        load_and_verify_issuer_aware_lock()
    )

    print(
        "\nIssuer-aware release lock SHA256: PASS"
    )

    print(
        "Position-aware baseline lock: PASS"
    )

    print(
        "V2 issuer v1.1 source lock: PASS"
    )

    print(
        "Static Audit v1.9 source lock: PASS"
    )

    print(
        "Issuer final-lock recognition: PASS"
    )

    # ========================================================
    # WRITER UNIVERSE
    # ========================================================

    expected_symbols = {
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
    }

    if (
        writer.ALLOWED_SYMBOLS
        != expected_symbols
    ):

        raise RuntimeError(
            "DISCONNECTED REHEARSAL STOP: "
            "writer universe does not match "
            "full frozen V5 execution universe."
        )

    if (
        writer.LIVE_WRITER_CONNECTED
        is not False
    ):

        raise RuntimeError(
            "CRITICAL SAFETY FAILURE: "
            "writer reports connected."
        )

    print(
        "Full frozen V5 execution universe: PASS"
    )

    print(
        "Writer connection state: FALSE"
    )

    # ========================================================
    # IN-MEMORY POSITIVE CONTRACT
    # ========================================================

    permit_package = (
        build_in_memory_permit(
            release_lock_sha256=
                release_lock_sha256
        )
    )

    intents = (
        build_in_memory_intents()
    )

    contract_result = (
        prove_writer_contract_accepts(
            permit_package=
                permit_package,

            intents=
                intents,
        )
    )

    print(
        "\nWriter-compatible V2 permit "
        "validation: PASS"
    )

    print(
        "Full-V5 executable-intent "
        "validation: PASS"
    )

    print(
        "Synthetic permit cap "
        "within contract: PASS"
    )

    # ========================================================
    # NEGATIVE CONTRACT
    # ========================================================

    cap_result = (
        prove_cap_enforcement()
    )

    print(
        "Oversized order batch rejection: PASS"
    )

    print(
        "Permit-cap enforcement: PASS"
    )

    # ========================================================
    # HARD DISCONNECT
    # ========================================================

    batch_disconnect = (
        prove_public_batch_entrypoint_disconnected(
            permit_package=
                permit_package,

            intents=
                intents,
        )
    )

    get_disconnect = (
        prove_direct_get_disconnected()
    )

    post_disconnect = (
        prove_direct_post_disconnected(
            intents[
                0
            ]
        )
    )

    print(
        "\nPublic batch execution guard: PASS"
    )

    print(
        "Direct writer GET guard: PASS"
    )

    print(
        "Direct writer POST guard: PASS"
    )

    print(
        "Broker network requests sent: 0"
    )

    print(
        "Orders submitted: 0"
    )

    # ========================================================
    # SAFE PERSISTED RESULT
    # ========================================================

    package = (
        build_safe_output(
            release_lock_sha256=
                release_lock_sha256,

            contract_result=
                contract_result,

            cap_result=
                cap_result,

            batch_disconnect=
                batch_disconnect,

            get_disconnect=
                get_disconnect,

            post_disconnect=
                post_disconnect,
        )
    )

    assert_safe_output(
        package[
            "rehearsal"
        ]
    )

    write_output(
        package
    )

    # --------------------------------------------------------
    # Explicitly remove in-memory references before reporting.
    # --------------------------------------------------------

    permit_package = None
    intents = None

    print(
        "\nSynthetic writer-compatible permit "
        "persisted: NO"
    )

    print(
        "Synthetic executable intents "
        "persisted: NO"
    )

    print(
        f"Safe rehearsal SHA256: "
        f"{package['rehearsal_sha256']}"
    )

    print(
        "\n============================================"
    )

    print(
        "FUND-100 DISCONNECTED ACTIVATION "
        "REHEARSAL v1.1 COMPLETE"
    )

    print(
        "============================================"
    )

    print(
        "Issuer-aware lock: VERIFIED"
    )

    print(
        "Writer-compatible permit contract: PASS"
    )

    print(
        "Full V5 order-intent contract: PASS"
    )

    print(
        "Permit-cap enforcement: PASS"
    )

    print(
        "Writer hard disconnect: VERIFIED"
    )

    print(
        "Broker credentials supplied: NO"
    )

    print(
        "Broker network access: NONE"
    )

    print(
        "Writer-compatible permit persisted: NO"
    )

    print(
        "Executable intents persisted: NO"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Maximum live execution notional: $0.00"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        "Orders submitted: 0"
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
            "DISCONNECTED ACTIVATION "
            "REHEARSAL v1.1: FAILED",
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
