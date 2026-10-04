from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
from pathlib import Path

import fund100_alpaca_live_execution_boundary as boundary
import fund100_alpaca_live_manifest as strategy
import fund100_alpaca_live_position_reconcile as reconcile
import fund100_alpaca_live_preflight as preflight
import fund100_alpaca_live_readonly_smoke as live

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 ALPACA LIVE PRE-CONNECT RUNTIME CHECK v1.0
# ============================================================
#
# LIVE ACCOUNT — GET ONLY.
#
# NO POST.
# NO PUT.
# NO PATCH.
# NO DELETE.
#
# PURPOSE
# =======
#
# Verify the real LIVE account still matches the hash-locked
# Fund-100 pre-connect engineering state before any future
# writer release is considered.
#
# This checker:
#
# - verifies release lock v1.4
# - verifies the writer candidate source hash
# - inspects writer release constants via AST
# - DOES NOT import the POST-capable writer candidate
# - verifies locked manifest/compiler artifacts
# - GETs live account
# - GETs live positions
# - GETs live open orders
# - GETs live market clock
# - performs fresh position-aware reconciliation
# - verifies fresh broker structure still matches the
#   locked manifest/compiler structure
#
# It persists only structural evidence.
#
# It DOES NOT persist:
#
# - live balances
# - live position quantities
# - live market values
# - live prices
# - broker snapshot hash
# - executable intents
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


LOCK_PATH = (
    ROOT
    / "release_outputs"
    / "v5_002"
    / "pre_live_release_lock.json"
)


MANIFEST_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "live_execution_manifest.json"
)


COMPILER_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "scheduled_execution_time.json"
)


CANDIDATE_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_candidate_v1_0.py"
)


OUTPUT_DIR = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
)


OUTPUT_PATH = (
    OUTPUT_DIR
    / "live_preconnect_runtime_check.json"
)


SCHEMA = (
    "FUND100_LIVE_PRECONNECT_RUNTIME_CHECK_V1"
)


ARM_ENV = (
    "FUND100_ENABLE_LIVE_PRECONNECT_CHECK"
)


ARM_VALUE = (
    "YES_GET_ONLY_PRECONNECT"
)


EXPECTED_LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1_1"
)


EXPECTED_LOCK_BUILDER_VERSION = "1.4"


EXPECTED_MANIFEST_SCHEMA = (
    "FUND100_LIVE_DRYRUN_MANIFEST_V1_1"
)


EXPECTED_COMPILER_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1_1"
)


EXPECTED_RECONCILIATION_POLICY = (
    "EPHEMERAL_POSITION_AWARE_V1"
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


def sha256_file(
    path: Path,
) -> str:

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


# ============================================================
# FILE HELPERS
# ============================================================


def load_json(
    path: Path,
):

    if not path.exists():

        raise RuntimeError(
            f"PRE-CONNECT STOP: "
            f"required file is missing: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(
            handle
        )


def verify_hashed_package(
    package: dict,
    *,
    body_key: str,
    hash_key: str,
):

    if not isinstance(
        package,
        dict,
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "invalid hashed package."
        )

    if (
        body_key
        not in package
        or
        hash_key
        not in package
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "incomplete hashed package."
        )

    body = (
        package[
            body_key
        ]
    )

    recorded = str(
        package[
            hash_key
        ]
    )

    calculated = (
        sha256_json(
            body
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            f"{body_key} SHA256 verification failed."
        )

    return (
        body,
        recorded,
    )


# ============================================================
# ARM
# ============================================================


def require_preconnect_arm():

    value = (
        os.environ.get(
            ARM_ENV,
            "",
        )
        .strip()
    )

    if value != ARM_VALUE:

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "GET-only runtime check is not explicitly armed."
        )


# ============================================================
# RELEASE LOCK
# ============================================================


def load_and_verify_release_lock():

    package = (
        load_json(
            LOCK_PATH
        )
    )

    (
        body,
        recorded_hash,
    ) = (
        verify_hashed_package(
            package,
            body_key=
                "release_lock",
            hash_key=
                "release_lock_sha256",
        )
    )

    if (
        body.get(
            "schema"
        )
        != EXPECTED_LOCK_SCHEMA
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "unexpected release-lock schema."
        )

    if (
        str(
            body.get(
                "release_lock_builder_version",
                "",
            )
        )
        != EXPECTED_LOCK_BUILDER_VERSION
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "release lock is not v1.4."
        )

    required_true = [
        "position_aware_live_chain_verified",
        "issuer_aware_release_lock",
        "execution_materializer_source_locked",
        "connected_writer_candidate_source_locked",
        "offline_connected_writer_rehearsal_completed",
        "offline_connected_writer_rehearsal_verified",
        "connected_writer_release_still_required",
        "live_preconnect_runtime_check_required",
    ]

    for field in required_true:

        if (
            body.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"release-lock field "
                f"{field!r} is not TRUE."
            )

    if (
        body.get(
            "offline_connected_writer_rehearsal_required"
        )
        is not False
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "offline writer rehearsal is still required."
        )

    if (
        body.get(
            "live_preconnect_runtime_check_completed"
        )
        is not False
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "release lock unexpectedly says "
            "runtime check is already complete."
        )

    required_false = [
        "connected_writer_candidate_transport_released",
        "connected_writer_candidate_public_execution_enabled",
        "connected_writer_candidate_workflow_exposed",
        "live_writer_transport_released",
        "live_writer_public_execution_enabled",
        "automatic_activation_allowed",
        "live_execution_authorized",
        "permit_issued",
        "network_write_capability",
        "writer_connected",
    ]

    for field in required_false:

        if (
            body.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"release-lock field "
                f"{field!r} is not FALSE."
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
            "PRE-CONNECT STOP: "
            "release-lock live ceiling is not $0.00."
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
            "PRE-CONNECT STOP: "
            "release lock reports submitted orders."
        )

    return (
        package,
        body,
        recorded_hash,
    )


# ============================================================
# LOCKED FILE VERIFICATION
# ============================================================


def verify_locked_file(
    lock_body: dict,
    relative_path: str,
):

    hashes = (
        lock_body.get(
            "critical_file_sha256",
            {},
        )
    )

    if not isinstance(
        hashes,
        dict,
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "critical-file hash map is invalid."
        )

    expected = str(
        hashes.get(
            relative_path,
            "",
        )
    )

    if not expected:

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            f"{relative_path!r} is not release-lock bound."
        )

    path = (
        ROOT
        / relative_path
    )

    if not path.exists():

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            f"locked file is missing: {relative_path}"
        )

    actual = (
        sha256_file(
            path
        )
    )

    if actual != expected:

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            f"{relative_path!r} changed after release lock."
        )

    return actual


# ============================================================
# WRITER CANDIDATE — SOURCE INSPECTION ONLY
# ============================================================


def extract_candidate_release_constants():

    source = (
        CANDIDATE_PATH.read_text(
            encoding="utf-8"
        )
    )

    tree = ast.parse(
        source
    )

    values = {}

    names = {
        "TRANSPORT_RELEASED",
        "PUBLIC_EXECUTION_ENABLED",
    }

    for node in tree.body:

        if not isinstance(
            node,
            ast.Assign,
        ):

            continue

        if (
            len(
                node.targets
            )
            != 1
        ):

            continue

        target = (
            node.targets[
                0
            ]
        )

        if not isinstance(
            target,
            ast.Name,
        ):

            continue

        if target.id not in names:

            continue

        if not isinstance(
            node.value,
            ast.Constant,
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"{target.id} is not a literal constant."
            )

        values[
            target.id
        ] = (
            node.value.value
        )

    if set(
        values
    ) != names:

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "writer candidate release constants are missing."
        )

    return values


def verify_candidate_source_unreleased(
    lock_body: dict,
):

    candidate_hash = (
        verify_locked_file(
            lock_body,
            "fund100_alpaca_live_writer_candidate_v1_0.py",
        )
    )

    constants = (
        extract_candidate_release_constants()
    )

    if (
        constants[
            "TRANSPORT_RELEASED"
        ]
        is not False
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "writer candidate transport is released."
        )

    if (
        constants[
            "PUBLIC_EXECUTION_ENABLED"
        ]
        is not False
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "writer candidate public execution is enabled."
        )

    return {
        "candidate_sha256":
            candidate_hash,

        "transport_released":
            False,

        "public_execution_enabled":
            False,
    }


# ============================================================
# POSITION STRUCTURAL PROOF
# ============================================================


def verify_structural_proof(
    structure,
    *,
    require_schema: bool,
):

    if not isinstance(
        structure,
        dict,
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "position structural proof is missing."
        )

    if require_schema:

        if (
            structure.get(
                "schema"
            )
            != reconcile.SCHEMA
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                "unexpected reconciliation schema."
            )

    if (
        structure.get(
            "policy"
        )
        != EXPECTED_RECONCILIATION_POLICY
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "unexpected reconciliation policy."
        )

    required_true = [
        "frozen_execution_universe_verified",
        "long_only_verified",
        "no_unmanaged_positions_verified",
        "no_open_orders_verified",
    ]

    for field in required_true:

        if (
            structure.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"structural field {field!r} "
                "is not TRUE."
            )

    if (
        int(
            structure.get(
                "open_order_count",
                -1,
            )
        )
        != 0
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "structural proof contains open orders."
        )

    required_false = [
        "live_holdings_persisted",
        "live_dollar_values_persisted",
        "volatile_broker_snapshot_persisted",
    ]

    for field in required_false:

        if (
            structure.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"structural field {field!r} "
                "is not FALSE."
            )

    if not str(
        structure.get(
            "live_account_binding_sha256",
            "",
        )
    ).strip():

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "account binding is missing."
        )

    position_count = int(
        structure.get(
            "position_count",
            -1,
        )
    )

    if position_count < 0:

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "invalid position count."
        )

    if (
        structure.get(
            "reconciliation_status"
        )
        not in {
            "EMPTY_ZERO_EQUITY",
            "POSITION_AWARE",
        }
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "unexpected reconciliation status."
        )

    return structure


def structural_binding_matches(
    left: dict,
    right: dict,
) -> bool:

    fields = [
        "policy",
        "live_account_binding_sha256",
        "reconciliation_status",
        "position_count",
        "open_order_count",
        "frozen_execution_universe_verified",
        "long_only_verified",
        "no_unmanaged_positions_verified",
        "no_open_orders_verified",
        "live_holdings_persisted",
        "live_dollar_values_persisted",
        "volatile_broker_snapshot_persisted",
    ]

    return all(
        left.get(
            field
        )
        == right.get(
            field
        )
        for field
        in fields
    )


# ============================================================
# LOCKED MANIFEST / COMPILER
# ============================================================


def verify_locked_execution_chain(
    lock_body: dict,
):

    verify_locked_file(
        lock_body,
        "live_dryrun_outputs/v5_002/"
        "live_execution_manifest.json",
    )

    verify_locked_file(
        lock_body,
        "live_dryrun_outputs/v5_002/"
        "scheduled_execution_time.json",
    )

    manifest_package = (
        load_json(
            MANIFEST_PATH
        )
    )

    (
        manifest,
        manifest_hash,
    ) = (
        verify_hashed_package(
            manifest_package,
            body_key=
                "manifest",
            hash_key=
                "manifest_sha256",
        )
    )

    compiler_package = (
        load_json(
            COMPILER_PATH
        )
    )

    (
        compiler,
        compiler_hash,
    ) = (
        verify_hashed_package(
            compiler_package,
            body_key=
                "compiler",
            hash_key=
                "compiler_sha256",
        )
    )

    if (
        manifest.get(
            "schema"
        )
        != EXPECTED_MANIFEST_SCHEMA
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "unexpected manifest schema."
        )

    if (
        compiler.get(
            "schema"
        )
        != EXPECTED_COMPILER_SCHEMA
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "unexpected compiler schema."
        )

    if (
        manifest.get(
            "strategy"
        )
        != "V5-002_SHADOW"
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "unexpected manifest strategy."
        )

    if (
        compiler.get(
            "strategy"
        )
        != "V5-002_SHADOW"
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "unexpected compiler strategy."
        )

    if (
        compiler.get(
            "source_manifest_id"
        )
        != manifest_package.get(
            "manifest_id"
        )
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "compiler manifest-ID binding failed."
        )

    if (
        compiler.get(
            "source_manifest_sha256"
        )
        != manifest_hash
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "compiler manifest SHA256 binding failed."
        )

    for body_name, body in [
        (
            "manifest",
            manifest,
        ),
        (
            "compiler",
            compiler,
        ),
    ]:

        if (
            body.get(
                "live_execution_authorized"
            )
            is not False
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"{body_name} unexpectedly "
                "authorizes live execution."
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
                "PRE-CONNECT STOP: "
                f"{body_name} live ceiling "
                "is not $0.00."
            )

        if (
            body.get(
                "network_write_capability"
            )
            is not False
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"{body_name} unexpectedly has "
                "network-write capability."
            )

        if (
            body.get(
                "broker_write_mode"
            )
            != "DISABLED"
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"{body_name} broker write mode "
                "is not DISABLED."
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
                "PRE-CONNECT STOP: "
                f"{body_name} reports submitted orders."
            )

    manifest_structure = (
        verify_structural_proof(
            manifest.get(
                "position_reconciliation"
            ),
            require_schema=True,
        )
    )

    compiler_structure = (
        verify_structural_proof(
            compiler.get(
                "position_reconciliation"
            ),
            require_schema=False,
        )
    )

    if not structural_binding_matches(
        manifest_structure,
        compiler_structure,
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "manifest/compiler position structures differ."
        )

    if (
        compiler.get(
            "compiler_mode"
        )
        != "current"
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "compiler is not CURRENT."
        )

    if (
        compiler.get(
            "status"
        )
        not in {
            "NO_SCHEDULED_EVENT",
            "GENUINE_SCHEDULED_EVENT",
        }
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "compiler status is not an allowed "
            "current-runtime status."
        )

    candidate_intents = (
        compiler.get(
            "candidate_intents",
            []
        )
    )

    if not isinstance(
        candidate_intents,
        list,
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "compiler candidate intents are invalid."
        )

    for intent in candidate_intents:

        if not isinstance(
            intent,
            dict,
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                "invalid compiler intent."
            )

        if (
            intent.get(
                "executable"
            )
            is not False
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                "compiler contains executable intent."
            )

        if (
            intent.get(
                "notional_usd"
            )
            is not None
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                "compiler intent contains "
                "executable dollar notional."
            )

    return {
        "manifest_package":
            manifest_package,

        "manifest":
            manifest,

        "manifest_sha256":
            manifest_hash,

        "compiler_package":
            compiler_package,

        "compiler":
            compiler,

        "compiler_sha256":
            compiler_hash,

        "manifest_structure":
            manifest_structure,

        "compiler_structure":
            compiler_structure,
    }


# ============================================================
# FRESH RUNTIME BINDING
# ============================================================


def verify_fresh_runtime_binding(
    *,
    fresh: dict,
    manifest: dict,
    compiler: dict,
    manifest_structure: dict,
    compiler_structure: dict,
):

    required_true = [
        "frozen_execution_universe_verified",
        "long_only_verified",
        "no_unmanaged_positions_verified",
        "no_open_orders_verified",
    ]

    for field in required_true:

        if (
            fresh.get(
                field
            )
            is not True
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"fresh reconciliation field "
                f"{field!r} is not TRUE."
            )

    if (
        int(
            fresh.get(
                "open_order_count",
                -1,
            )
        )
        != 0
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "fresh live account contains open orders."
        )

    if (
        fresh.get(
            "live_execution_authorized"
        )
        is not False
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "fresh reconciliation authorizes execution."
        )

    if (
        fresh.get(
            "network_write_capability"
        )
        is not False
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "fresh reconciliation has write capability."
        )

    if (
        fresh.get(
            "broker_write_mode"
        )
        != "DISABLED"
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "fresh reconciliation write mode "
            "is not DISABLED."
        )

    if (
        fresh.get(
            "persistence_policy"
        )
        != "EPHEMERAL_NOT_COMMITTED"
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "fresh reconciliation persistence policy changed."
        )

    if (
        fresh.get(
            "strategy_state_sha256"
        )
        != manifest.get(
            "strategy_state_sha256"
        )
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "fresh state hash does not match manifest."
        )

    if (
        fresh.get(
            "strategy_state_sha256"
        )
        != compiler.get(
            "strategy_state_sha256"
        )
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "fresh state hash does not match compiler."
        )

    if (
        str(
            fresh.get(
                "strategy_state_date"
            )
        )
        != str(
            manifest.get(
                "strategy_state_date"
            )
        )
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "fresh state date does not match manifest."
        )

    binding = (
        fresh.get(
            "live_account_binding_sha256"
        )
    )

    if (
        binding
        != manifest_structure.get(
            "live_account_binding_sha256"
        )
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "live account binding changed since manifest."
        )

    if (
        binding
        != compiler_structure.get(
            "live_account_binding_sha256"
        )
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "live account binding changed since compiler."
        )

    for structure_name, structure in [
        (
            "manifest",
            manifest_structure,
        ),
        (
            "compiler",
            compiler_structure,
        ),
    ]:

        if (
            fresh.get(
                "reconciliation_status"
            )
            != structure.get(
                "reconciliation_status"
            )
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"live reconciliation status changed "
                f"since {structure_name}."
            )

        if (
            int(
                fresh.get(
                    "position_count",
                    -1,
                )
            )
            != int(
                structure.get(
                    "position_count",
                    -2,
                )
            )
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"live position count changed "
                f"since {structure_name}."
            )

    return True


# ============================================================
# SAFE OUTPUT
# ============================================================


def build_safe_output(
    *,
    release_lock_sha256: str,
    candidate_sha256: str,
    manifest_sha256: str,
    compiler_sha256: str,
    fresh: dict,
):

    body = {
        "schema":
            SCHEMA,

        "mode":
            "LIVE_GET_ONLY_PRECONNECT",

        "source_release_lock_builder_version":
            EXPECTED_LOCK_BUILDER_VERSION,

        "source_release_lock_sha256":
            release_lock_sha256,

        "writer_candidate_source_sha256":
            candidate_sha256,

        "source_manifest_sha256":
            manifest_sha256,

        "source_compiler_sha256":
            compiler_sha256,

        "candidate_module_imported":
            False,

        "candidate_transport_released":
            False,

        "candidate_public_execution_enabled":
            False,

        "release_lock_verified":
            True,

        "locked_manifest_verified":
            True,

        "locked_compiler_verified":
            True,

        "runtime_binding_matches_locked_chain":
            True,

        "live_account_binding_sha256":
            fresh[
                "live_account_binding_sha256"
            ],

        "reconciliation_status":
            fresh[
                "reconciliation_status"
            ],

        "position_count":
            int(
                fresh[
                    "position_count"
                ]
            ),

        "open_order_count":
            0,

        "frozen_execution_universe_verified":
            True,

        "long_only_verified":
            True,

        "no_unmanaged_positions_verified":
            True,

        "no_open_orders_verified":
            True,

        "market_clock_checked":
            True,

        "market_clock_value_persisted":
            False,

        "live_credentials_supplied":
            True,

        "live_credentials_persisted":
            False,

        "live_holdings_persisted":
            False,

        "live_dollar_values_persisted":
            False,

        "volatile_broker_snapshot_persisted":
            False,

        "broker_snapshot_hash_persisted":
            False,

        "broker_http_methods":
            "GET_ONLY",

        "broker_get_request_count":
            4,

        "broker_post_request_count":
            0,

        "broker_put_request_count":
            0,

        "broker_patch_request_count":
            0,

        "broker_delete_request_count":
            0,

        "executable_intents_persisted":
            False,

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

        "writer_connected":
            False,

        "orders_submitted":
            0,

        "preconnect_runtime_check_passed":
            True,

        "connected_writer_release_still_required":
            True,
    }

    return {
        "runtime_check":
            body,

        "runtime_check_sha256":
            sha256_json(
                body
            ),
    }


def assert_safe_output(
    body: dict,
):

    required_true = [
        "release_lock_verified",
        "locked_manifest_verified",
        "locked_compiler_verified",
        "runtime_binding_matches_locked_chain",
        "frozen_execution_universe_verified",
        "long_only_verified",
        "no_unmanaged_positions_verified",
        "no_open_orders_verified",
        "market_clock_checked",
        "live_credentials_supplied",
        "preconnect_runtime_check_passed",
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
                "PRE-CONNECT STOP: "
                f"safe-output field {field!r} "
                "is not TRUE."
            )

    required_false = [
        "candidate_module_imported",
        "candidate_transport_released",
        "candidate_public_execution_enabled",
        "market_clock_value_persisted",
        "live_credentials_persisted",
        "live_holdings_persisted",
        "live_dollar_values_persisted",
        "volatile_broker_snapshot_persisted",
        "broker_snapshot_hash_persisted",
        "executable_intents_persisted",
        "permit_issued",
        "live_execution_authorized",
        "network_write_capability",
        "writer_connected",
    ]

    for field in required_false:

        if (
            body.get(
                field
            )
            is not False
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"safe-output field {field!r} "
                "is not FALSE."
            )

    zero_fields = [
        "open_order_count",
        "broker_post_request_count",
        "broker_put_request_count",
        "broker_patch_request_count",
        "broker_delete_request_count",
        "orders_submitted",
    ]

    for field in zero_fields:

        if (
            int(
                body.get(
                    field,
                    -1,
                )
            )
            != 0
        ):

            raise RuntimeError(
                "PRE-CONNECT STOP: "
                f"safe-output field {field!r} "
                "is not zero."
            )

    if (
        body.get(
            "broker_http_methods"
        )
        != "GET_ONLY"
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "broker HTTP mode is not GET_ONLY."
        )

    if (
        body.get(
            "broker_write_mode"
        )
        != "DISABLED"
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "broker write mode is not DISABLED."
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
            "PRE-CONNECT STOP: "
            "persisted live ceiling is not $0.00."
        )


def write_safe_output(
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

    stored = (
        load_json(
            OUTPUT_PATH
        )
    )

    if (
        sha256_json(
            stored[
                "runtime_check"
            ]
        )
        != stored[
            "runtime_check_sha256"
        ]
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "stored runtime-check SHA256 failed."
        )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE "
        "PRE-CONNECT RUNTIME CHECK"
    )

    print(
        "============================================"
    )

    print(
        "\nEnvironment: ALPACA LIVE"
    )

    print(
        "Mode: GET ONLY"
    )

    print(
        "POST capability: ABSENT"
    )

    print(
        "Writer candidate import: PROHIBITED"
    )

    print(
        "Live holdings persistence: NONE"
    )

    print(
        "Live dollar-value persistence: NONE"
    )

    # ========================================================
    # ARM / KILL SWITCH / WRITE MODE
    # ========================================================

    require_preconnect_arm()

    if (
        get_kill_switch_state()
        != "ENGAGED"
    ):

        raise RuntimeError(
            "PRE-CONNECT SAFETY STOP: "
            "broker kill switch must remain ENGAGED."
        )

    boundary.require_live_writes_disabled()

    live.require_readonly_arm()

    print(
        "\nPre-connect GET-only arm: PASS"
    )

    print(
        "Broker kill switch: ENGAGED — PASS"
    )

    print(
        "Live write mode: DISABLED — PASS"
    )

    # ========================================================
    # LOCK / CANDIDATE / ARTIFACTS
    # ========================================================

    (
        _lock_package,
        lock_body,
        lock_hash,
    ) = (
        load_and_verify_release_lock()
    )

    candidate_result = (
        verify_candidate_source_unreleased(
            lock_body
        )
    )

    chain = (
        verify_locked_execution_chain(
            lock_body
        )
    )

    print(
        "\nRelease lock v1.4: PASS"
    )

    print(
        "Writer candidate source hash: PASS"
    )

    print(
        "Writer candidate imported: NO"
    )

    print(
        "Candidate transport released: FALSE"
    )

    print(
        "Candidate public execution enabled: FALSE"
    )

    print(
        "Locked manifest/compiler chain: PASS"
    )

    # ========================================================
    # LIVE GET-ONLY INSPECTION
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

    positions = (
        live.get_json(
            path="/v2/positions",
            key=key,
            secret=secret,
        )
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

    clock = (
        live.get_json(
            path="/v2/clock",
            key=key,
            secret=secret,
        )
    )

    if not isinstance(
        clock,
        dict,
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "invalid live market-clock response."
        )

    if (
        "is_open"
        not in clock
        or
        not isinstance(
            clock[
                "is_open"
            ],
            bool,
        )
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "market-clock response has "
            "unexpected structure."
        )

    # ========================================================
    # FRESH POSITION-AWARE RECONCILIATION
    # ========================================================

    state = (
        strategy.load_state()
    )

    fresh_package = (
        reconcile.build_reconciliation(
            state=
                state,

            account=
                account,

            positions=
                positions,

            open_orders=
                open_orders,
        )
    )

    fresh = (
        fresh_package[
            "reconciliation"
        ]
    )

    if (
        reconcile.sha256_json(
            fresh
        )
        != fresh_package[
            "reconciliation_sha256"
        ]
    ):

        raise RuntimeError(
            "PRE-CONNECT STOP: "
            "fresh reconciliation SHA256 failed."
        )

    verify_fresh_runtime_binding(
        fresh=
            fresh,

        manifest=
            chain[
                "manifest"
            ],

        compiler=
            chain[
                "compiler"
            ],

        manifest_structure=
            chain[
                "manifest_structure"
            ],

        compiler_structure=
            chain[
                "compiler_structure"
            ],
    )

    print(
        "\nLive account authentication: PASS"
    )

    print(
        "Live account structural validation: PASS"
    )

    print(
        "Fresh position-aware reconciliation: PASS"
    )

    print(
        "Frozen V5 execution universe: PASS"
    )

    print(
        "Long-only structure: PASS"
    )

    print(
        "Unmanaged positions: NONE"
    )

    print(
        "Open orders: 0 — PASS"
    )

    print(
        "Live account binding to locked chain: PASS"
    )

    print(
        "Live position structure to locked chain: PASS"
    )

    print(
        "Market clock GET: PASS"
    )

    # ========================================================
    # SAFE STRUCTURAL ARTIFACT
    # ========================================================

    package = (
        build_safe_output(
            release_lock_sha256=
                lock_hash,

            candidate_sha256=
                candidate_result[
                    "candidate_sha256"
                ],

            manifest_sha256=
                chain[
                    "manifest_sha256"
                ],

            compiler_sha256=
                chain[
                    "compiler_sha256"
                ],

            fresh=
                fresh,
        )
    )

    assert_safe_output(
        package[
            "runtime_check"
        ]
    )

    write_safe_output(
        package
    )

    # Remove credential references before final reporting.
    key = None
    secret = None

    print(
        "\nLive credentials persisted: NO"
    )

    print(
        "Live holdings persisted: NO"
    )

    print(
        "Live dollar values persisted: NO"
    )

    print(
        "Broker snapshot hash persisted: NO"
    )

    print(
        "Executable intents persisted: NO"
    )

    print(
        "Broker GET requests: 4"
    )

    print(
        "Broker POST requests: 0"
    )

    print(
        "\n============================================"
    )

    print(
        "FUND-100 LIVE PRE-CONNECT "
        "RUNTIME CHECK COMPLETE"
    )

    print(
        "============================================"
    )

    print(
        "Release lock v1.4: VERIFIED"
    )

    print(
        "Writer candidate source: VERIFIED"
    )

    print(
        "Writer candidate imported: NO"
    )

    print(
        "Candidate transport released: FALSE"
    )

    print(
        "Candidate public execution enabled: FALSE"
    )

    print(
        "Locked execution chain: VERIFIED"
    )

    print(
        "Fresh LIVE account reconciliation: PASS"
    )

    print(
        "Live account binding: PASS"
    )

    print(
        "Open orders: 0"
    )

    print(
        "Broker HTTP methods: GET ONLY"
    )

    print(
        "Broker POST requests: 0"
    )

    print(
        "Live execution authorized: FALSE"
    )

    print(
        "Permit issued: FALSE"
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
            "LIVE PRE-CONNECT RUNTIME CHECK: FAILED",
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
