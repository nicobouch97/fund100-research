from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import fund100_alpaca_live_writer_disconnected as writer

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 PRE-LIVE RELEASE EVIDENCE GATE v1.0
# ============================================================
#
# OFFLINE.
#
# NO ALPACA CREDENTIALS.
# NO BROKER NETWORK ACCESS.
# NO ORDER SUBMISSION.
#
# This gate does NOT authorize live execution.
#
# It verifies the committed engineering evidence chain:
#
#   frozen research data
#       ↓
#   V5-002 preregistration/result
#       ↓
#   shadow manifest/state
#       ↓
#   paper-execution architecture
#       ↓
#   live dry-run manifest
#       ↓
#   live intent bundle
#       ↓
#   scheduled compiler
#       ↓
#   deny-only V1 permit
#       ↓
#   V2 negative simulation
#       ↓
#   V2 positive-path rehearsal
#       ↓
#   disconnected live writer
#
# Successful output means:
#
#   EVIDENCE CHAIN = PASS
#
# It does NOT mean:
#
#   LIVE EXECUTION = AUTHORIZED
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


# ============================================================
# EXPECTED FROZEN LINEAGE
# ============================================================


EXPECTED_EXPERIMENT = "V5-002"

EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

EXPECTED_HISTORICAL_CUTOFF = (
    "2026-09-16"
)

EXPECTED_RESEARCH_FILE_SHA256 = (
    "acc2c8c08953b895ca5062b3cfba287"
    "efb97143b10e108e8ce4bd8b82ffb0d28"
)

EXPECTED_RESEARCH_DATA_SHA256 = (
    "ec48258afa8698716f4d7c42b758822"
    "f732a425b10d2d3ebcfcf3ddedcbc21f9"
)

EXPECTED_SPEC_SHA256 = (
    "345748517b44798c2581af062264c78d"
    "6c9ffa39b4a9b534e5ff21c0a5a674ba"
)

EXPECTED_RESULT_SHA256 = (
    "db3a423160eadfaa194a87da600e9ee5"
    "b23d0a21ef018c07e85fc1803e5c000f"
)

EXPECTED_SHADOW_MANIFEST_SHA256 = (
    "852a1563f236b964974b44c4cea0895c"
    "50e880bb304ae62ae5c650c61f483c10"
)


# ============================================================
# INPUT FILES
# ============================================================


FROZEN_HISTORY_PATH = (
    ROOT
    / "research_lab"
    / "frozen_history_v2.csv"
)

FROZEN_HISTORY_MANIFEST_PATH = (
    ROOT
    / "research_lab"
    / "frozen_history_v2_manifest.json"
)

SPEC_PATH = (
    ROOT
    / "research_lab"
    / "challengers"
    / "V5-002.json"
)

RESULT_PATH = (
    ROOT
    / "research_lab"
    / "results"
    / "V5-002.json"
)

SHADOW_MANIFEST_PATH = (
    ROOT
    / "shadow_outputs"
    / "v5_002"
    / "shadow_manifest.json"
)

SHADOW_STATE_PATH = (
    ROOT
    / "shadow_outputs"
    / "v5_002"
    / "shadow_state.json"
)

SHADOW_LEDGER_PATH = (
    ROOT
    / "shadow_outputs"
    / "v5_002"
    / "shadow_ledger.csv"
)

LIVE_DIR = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
)

LIVE_MANIFEST_PATH = (
    LIVE_DIR
    / "live_execution_manifest.json"
)

LIVE_INTENTS_PATH = (
    LIVE_DIR
    / "live_order_intents.json"
)

SCHEDULED_COMPILER_PATH = (
    LIVE_DIR
    / "scheduled_execution_time.json"
)

V1_PERMIT_PATH = (
    LIVE_DIR
    / "live_execution_permit.json"
)

V2_SIMULATION_PATH = (
    LIVE_DIR
    / "live_execution_permit_v2_simulation.json"
)

ACTIVATION_REHEARSAL_PATH = (
    LIVE_DIR
    / "live_activation_rehearsal.json"
)

PAPER_EVENT_LEDGER_PATH = (
    ROOT
    / "broker_outputs"
    / "v5_002_paper"
    / "execution_events.csv"
)

OUTPUT_DIR = (
    ROOT
    / "release_outputs"
    / "v5_002"
)

JSON_OUTPUT_PATH = (
    OUTPUT_DIR
    / "pre_live_release_evidence.json"
)

MARKDOWN_OUTPUT_PATH = (
    OUTPUT_DIR
    / "pre_live_release_evidence.md"
)


# ============================================================
# REQUIRED COMPONENT FILES
# ============================================================


PAPER_COMPONENTS = [
    "fund100_alpaca_paper_smoke.py",
    "fund100_alpaca_paper_reconcile.py",
    "fund100_alpaca_paper_execute_bootstrap.py",
    "fund100_alpaca_paper_fill_reconcile.py",
    "fund100_alpaca_paper_execute_guarded.py",
    "fund100_alpaca_paper_twosided_rehearsal.py",
    "fund100_alpaca_paper_restart_resume_v1_1.py",
    "fund100_alpaca_paper_event_executor.py",
    "fund100_alpaca_paper_event_executor_v1_1.py",
]

LIVE_COMPONENTS = [
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_alpaca_live_preflight.py",
    "fund100_alpaca_live_execution_boundary.py",
    "fund100_alpaca_live_manifest.py",
    "fund100_alpaca_live_intent_validator.py",
    "fund100_alpaca_live_scheduled_compiler.py",
    "fund100_alpaca_live_execution_permit.py",
    "fund100_alpaca_live_permit_v2_simulator.py",
    "fund100_alpaca_live_activation_rehearsal.py",
    "fund100_alpaca_live_writer_disconnected.py",
]

EXPECTED_PRECONDITIONS = [
    "FUND100_PRECHECK_TESTS",
    "FUND100_PRECHECK_ENGINE_PARITY",
    "FUND100_PRECHECK_STATIC_AUDIT",
]


# ============================================================
# AUDIT RESULT
# ============================================================


class EvidenceGate:

    def __init__(
        self,
    ):

        self.checks: list[dict] = []

        self.evidence: dict = {}

    def check(
        self,
        name: str,
        passed: bool,
        detail,
    ) -> None:

        self.checks.append({
            "name":
                name,

            "passed":
                bool(
                    passed
                ),

            "detail":
                detail,
        })

    def require(
        self,
        name: str,
        condition: bool,
        detail,
    ) -> None:

        self.check(
            name=
                name,

            passed=
                condition,

            detail=
                detail,
        )

    @property
    def failures(
        self,
    ):

        return [
            item
            for item
            in self.checks
            if not item[
                "passed"
            ]
        ]

    @property
    def passes(
        self,
    ):

        return [
            item
            for item
            in self.checks
            if item[
                "passed"
            ]
        ]


# ============================================================
# HASHING / JSON
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


def load_json(
    path: Path,
):

    if not path.exists():

        raise RuntimeError(
            "Required file missing: "
            + str(
                path.relative_to(
                    ROOT
                )
            )
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        return json.load(
            handle
        )


def verify_package(
    path: Path,
    body_key: str,
    hash_key: str,
):

    package = (
        load_json(
            path
        )
    )

    if body_key not in package:

        raise RuntimeError(
            f"{path.name}: missing {body_key}"
        )

    if hash_key not in package:

        raise RuntimeError(
            f"{path.name}: missing {hash_key}"
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
            f"{path.name}: SHA256 verification failed."
        )

    return (
        package,
        body,
        recorded,
    )


# ============================================================
# GIT CONTEXT
# ============================================================


def git_value(
    *args,
):

    try:

        value = subprocess.check_output(
            [
                "git",
                *args,
            ],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )

        return value.strip()

    except Exception:

        return None


# ============================================================
# WORKFLOW PRECONDITIONS
# ============================================================


def verify_preconditions(
    gate: EvidenceGate,
):

    results = {}

    for variable in (
        EXPECTED_PRECONDITIONS
    ):

        value = (
            os.environ.get(
                variable,
                "",
            )
            .strip()
            .upper()
        )

        passed = (
            value == "PASS"
        )

        gate.require(
            name=(
                "workflow_precondition:"
                + variable
            ),
            condition=
                passed,
            detail=
                value or "MISSING",
        )

        results[
            variable
        ] = value

    gate.evidence[
        "workflow_preconditions"
    ] = results


# ============================================================
# KILL SWITCH
# ============================================================


def verify_kill_switch(
    gate: EvidenceGate,
):

    state = (
        get_kill_switch_state()
    )

    gate.require(
        name=
            "broker_kill_switch_engaged",

        condition=
            state == "ENGAGED",

        detail=
            state,
    )

    gate.evidence[
        "broker_kill_switch"
    ] = state


# ============================================================
# RESEARCH LINEAGE
# ============================================================


def verify_research_lineage(
    gate: EvidenceGate,
):

    required = [
        FROZEN_HISTORY_PATH,
        FROZEN_HISTORY_MANIFEST_PATH,
        SPEC_PATH,
        RESULT_PATH,
    ]

    for path in required:

        gate.require(
            name=(
                "file_exists:"
                + str(
                    path.relative_to(
                        ROOT
                    )
                )
            ),
            condition=
                path.exists(),
            detail=
                path.exists(),
        )

    manifest = (
        load_json(
            FROZEN_HISTORY_MANIFEST_PATH
        )
    )

    frozen_file_hash = (
        sha256_file(
            FROZEN_HISTORY_PATH
        )
    )

    gate.require(
        name=
            "frozen_history_file_sha256",

        condition=(
            frozen_file_hash
            == EXPECTED_RESEARCH_FILE_SHA256
            == manifest.get(
                "file_sha256"
            )
        ),

        detail={
            "calculated":
                frozen_file_hash,

            "manifest":
                manifest.get(
                    "file_sha256"
                ),

            "expected":
                EXPECTED_RESEARCH_FILE_SHA256,
        },
    )

    gate.require(
        name=
            "frozen_research_data_sha256",

        condition=(
            manifest.get(
                "research_data_sha256"
            )
            == EXPECTED_RESEARCH_DATA_SHA256
        ),

        detail=
            manifest.get(
                "research_data_sha256"
            ),
    )

    gate.require(
        name=
            "historical_cutoff_frozen",

        condition=(
            manifest.get(
                "historical_cutoff"
            )
            == EXPECTED_HISTORICAL_CUTOFF
            and
            manifest.get(
                "last_date"
            )
            == EXPECTED_HISTORICAL_CUTOFF
        ),

        detail={
            "historical_cutoff":
                manifest.get(
                    "historical_cutoff"
                ),

            "last_date":
                manifest.get(
                    "last_date"
                ),
        },
    )

    spec = (
        load_json(
            SPEC_PATH
        )
    )

    result = (
        load_json(
            RESULT_PATH
        )
    )

    spec_hash = (
        sha256_json(
            spec
        )
    )

    result_hash = (
        sha256_json(
            result
        )
    )

    gate.require(
        name=
            "v5_002_spec_sha256",

        condition=(
            spec_hash
            == EXPECTED_SPEC_SHA256
            == result.get(
                "spec_hash"
            )
        ),

        detail={
            "calculated":
                spec_hash,

            "result_spec_hash":
                result.get(
                    "spec_hash"
                ),
        },
    )

    gate.require(
        name=
            "v5_002_result_sha256",

        condition=(
            result_hash
            == EXPECTED_RESULT_SHA256
        ),

        detail=
            result_hash,
    )

    gate.require(
        name=
            "v5_002_result_identity",

        condition=(
            spec.get(
                "experiment_id"
            )
            == EXPECTED_EXPERIMENT
            and
            result.get(
                "experiment_id"
            )
            == EXPECTED_EXPERIMENT
        ),

        detail={
            "spec":
                spec.get(
                    "experiment_id"
                ),

            "result":
                result.get(
                    "experiment_id"
                ),
        },
    )

    gate.require(
        name=
            "research_result_recorded_survivor",

        condition=(
            result.get(
                "status"
            )
            == "RESEARCH_SURVIVOR"
        ),

        detail=
            result.get(
                "status"
            ),
    )

    gate.require(
        name=
            "research_result_data_hash_matches_frozen_data",

        condition=(
            result.get(
                "data_hash"
            )
            == EXPECTED_RESEARCH_DATA_SHA256
        ),

        detail=
            result.get(
                "data_hash"
            ),
    )

    gate.require(
        name=
            "research_result_cutoff_matches_frozen_cutoff",

        condition=(
            result.get(
                "historical_cutoff"
            )
            == EXPECTED_HISTORICAL_CUTOFF
        ),

        detail=
            result.get(
                "historical_cutoff"
            ),
    )

    criteria = (
        result.get(
            "criterion_results",
            {}
        )
    )

    all_criteria_passed = (
        bool(
            criteria
        )
        and all(
            bool(
                value.get(
                    "passed",
                    False,
                )
            )
            for value
            in criteria.values()
        )
    )

    gate.require(
        name=
            "recorded_research_acceptance_criteria",

        condition=
            all_criteria_passed,

        detail={
            key:
                value.get(
                    "passed"
                )
            for key, value
            in criteria.items()
        },
    )

    warning = str(
        result.get(
            "research_warning",
            "",
        )
    )

    gate.require(
        name=
            "research_warning_preserved",

        condition=(
            "not proof of alpha"
            in warning.lower()
        ),

        detail=
            warning,
    )

    gate.evidence[
        "research"
    ] = {
        "experiment_id":
            EXPECTED_EXPERIMENT,

        "status":
            result.get(
                "status"
            ),

        "historical_cutoff":
            result.get(
                "historical_cutoff"
            ),

        "evaluation_start":
            result.get(
                "evaluation_start"
            ),

        "frozen_file_sha256":
            frozen_file_hash,

        "research_data_sha256":
            EXPECTED_RESEARCH_DATA_SHA256,

        "spec_sha256":
            spec_hash,

        "result_sha256":
            result_hash,

        "research_warning":
            warning,

        "automatic_live_approval":
            False,
    }


# ============================================================
# SHADOW LINEAGE
# ============================================================


def verify_shadow(
    gate: EvidenceGate,
):

    shadow_manifest = (
        load_json(
            SHADOW_MANIFEST_PATH
        )
    )

    shadow_state = (
        load_json(
            SHADOW_STATE_PATH
        )
    )

    definition = {
        key:
            value
        for key, value
        in shadow_manifest.items()
        if key not in {
            "manifest_hash",
            "created_utc",
        }
    }

    calculated_manifest_hash = (
        sha256_json(
            definition
        )
    )

    recorded_manifest_hash = str(
        shadow_manifest.get(
            "manifest_hash",
            "",
        )
    )

    gate.require(
        name=
            "shadow_manifest_sha256",

        condition=(
            calculated_manifest_hash
            == recorded_manifest_hash
            == EXPECTED_SHADOW_MANIFEST_SHA256
        ),

        detail={
            "calculated":
                calculated_manifest_hash,

            "recorded":
                recorded_manifest_hash,
        },
    )

    gate.require(
        name=
            "shadow_research_hash_chain",

        condition=(
            shadow_manifest.get(
                "research_spec_hash"
            )
            == EXPECTED_SPEC_SHA256
            and
            shadow_manifest.get(
                "research_result_hash"
            )
            == EXPECTED_RESULT_SHA256
            and
            shadow_manifest.get(
                "research_data_hash"
            )
            == EXPECTED_RESEARCH_DATA_SHA256
        ),

        detail={
            "spec":
                shadow_manifest.get(
                    "research_spec_hash"
                ),

            "result":
                shadow_manifest.get(
                    "research_result_hash"
                ),

            "data":
                shadow_manifest.get(
                    "research_data_hash"
                ),
        },
    )

    gate.require(
        name=
            "shadow_state_strategy",

        condition=(
            shadow_state.get(
                "strategy"
            )
            == EXPECTED_STRATEGY
        ),

        detail=
            shadow_state.get(
                "strategy"
            ),
    )

    gate.require(
        name=
            "shadow_state_manifest_binding",

        condition=(
            shadow_state.get(
                "manifest_hash"
            )
            == EXPECTED_SHADOW_MANIFEST_SHA256
        ),

        detail=
            shadow_state.get(
                "manifest_hash"
            ),
    )

    weights = (
        shadow_state.get(
            "satellite_weights",
            {}
        )
    )

    satellite_total = sum(
        float(
            value
        )
        for value
        in weights.values()
    )

    maximum_position = max(
        [
            float(
                value
            )
            for value
            in weights.values()
        ]
        or [
            0.0
        ]
    )

    gate.require(
        name=
            "shadow_total_risk_within_hard_limit",

        condition=(
            satellite_total
            <= 0.275 + 1e-12
        ),

        detail=
            satellite_total,
    )

    gate.require(
        name=
            "shadow_position_risk_within_hard_limit",

        condition=(
            maximum_position
            <= 0.15 + 1e-12
        ),

        detail=
            maximum_position,
    )

    gate.require(
        name=
            "baseline_release_has_no_pending_event",

        condition=(
            shadow_state.get(
                "pending_target"
            )
            is None
            and
            shadow_state.get(
                "pending_source"
            )
            is None
        ),

        detail={
            "pending_target":
                shadow_state.get(
                    "pending_target"
                ),

            "pending_source":
                shadow_state.get(
                    "pending_source"
                ),
        },
    )

    gate.require(
        name=
            "shadow_ledger_present",

        condition=
            SHADOW_LEDGER_PATH.exists(),

        detail=
            SHADOW_LEDGER_PATH.exists(),
    )

    gate.evidence[
        "shadow"
    ] = {
        "strategy":
            shadow_state.get(
                "strategy"
            ),

        "state_date":
            shadow_state.get(
                "last_date"
            ),

        "state_updated_utc":
            shadow_state.get(
                "updated_utc"
            ),

        "nav":
            shadow_state.get(
                "nav"
            ),

        "benchmark_nav":
            shadow_state.get(
                "benchmark_nav"
            ),

        "satellite_total":
            satellite_total,

        "maximum_satellite_position":
            maximum_position,

        "pending_event":
            False,

        "shadow_manifest_sha256":
            recorded_manifest_hash,
    }

    return shadow_state


# ============================================================
# PAPER ARCHITECTURE EVIDENCE
# ============================================================


def verify_paper_architecture(
    gate: EvidenceGate,
):

    exact_live_url = re.compile(
        r"https://api\.alpaca\.markets"
    )

    missing = []

    contaminated = []

    for filename in (
        PAPER_COMPONENTS
    ):

        path = (
            ROOT
            / filename
        )

        if not path.exists():

            missing.append(
                filename
            )

            continue

        text = (
            path.read_text(
                encoding="utf-8"
            )
        )

        if exact_live_url.search(
            text
        ):

            contaminated.append(
                filename
            )

    gate.require(
        name=
            "paper_components_present",

        condition=(
            len(
                missing
            )
            == 0
        ),

        detail={
            "missing":
                missing,
        },
    )

    gate.require(
        name=
            "paper_components_do_not_target_live_endpoint",

        condition=(
            len(
                contaminated
            )
            == 0
        ),

        detail={
            "live_endpoint_matches":
                contaminated,
        },
    )

    paper_executor_text = (
        (
            ROOT
            / "fund100_alpaca_paper_event_executor.py"
        )
        .read_text(
            encoding="utf-8"
        )
    )

    gate.require(
        name=
            "paper_executor_targets_paper_host",

        condition=(
            "https://paper-api.alpaca.markets"
            in paper_executor_text
        ),

        detail=
            "https://paper-api.alpaca.markets",
    )

    ledger_summary = {
        "present":
            PAPER_EVENT_LEDGER_PATH.exists(),

        "rows":
            0,

        "duplicate_event_ids":
            False,

        "statuses":
            [],
    }

    if PAPER_EVENT_LEDGER_PATH.exists():

        with PAPER_EVENT_LEDGER_PATH.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:

            rows = list(
                csv.DictReader(
                    handle
                )
            )

        ids = [
            str(
                row.get(
                    "event_id",
                    "",
                )
            )
            for row
            in rows
            if row.get(
                "event_id"
            )
        ]

        duplicate_ids = (
            len(
                ids
            )
            != len(
                set(
                    ids
                )
            )
        )

        statuses = sorted({
            str(
                row.get(
                    "status",
                    "",
                )
            )
            for row
            in rows
            if row.get(
                "status"
            )
        })

        ledger_summary = {
            "present":
                True,

            "rows":
                len(
                    rows
                ),

            "duplicate_event_ids":
                duplicate_ids,

            "statuses":
                statuses,
        }

        gate.require(
            name=
                "paper_event_ledger_has_unique_event_ids",

            condition=
                not duplicate_ids,

            detail=
                ledger_summary,
        )

    gate.evidence[
        "paper_architecture"
    ] = {
        "components_present":
            len(
                missing
            )
            == 0,

        "paper_endpoint_only":
            len(
                contaminated
            )
            == 0,

        "production_event_executor":
            "fund100_alpaca_paper_event_executor_v1_1.py",

        "event_ledger":
            ledger_summary,

        "note": (
            "This release gate verifies committed paper "
            "architecture. Historical GitHub Actions fill/"
            "restart logs remain separate CI evidence."
        ),
    }


# ============================================================
# LIVE DRY-RUN CHAIN
# ============================================================


def require_disabled(
    gate: EvidenceGate,
    prefix: str,
    body: dict,
):

    gate.require(
        name=
            prefix
            + ":live_execution_authorized_false",

        condition=(
            body.get(
                "live_execution_authorized"
            )
            is False
        ),

        detail=
            body.get(
                "live_execution_authorized"
            ),
    )

    gate.require(
        name=
            prefix
            + ":max_live_notional_zero",

        condition=(
            abs(
                float(
                    body.get(
                        "max_live_execution_notional_usd",
                        -1.0,
                    )
                )
            )
            <= 1e-12
        ),

        detail=
            body.get(
                "max_live_execution_notional_usd"
            ),
    )

    gate.require(
        name=
            prefix
            + ":broker_write_mode_disabled",

        condition=(
            body.get(
                "broker_write_mode"
            )
            == "DISABLED"
        ),

        detail=
            body.get(
                "broker_write_mode"
            ),
    )


def verify_live_chain(
    gate: EvidenceGate,
    shadow_state: dict,
):

    (
        manifest_package,
        manifest,
        manifest_hash,
    ) = verify_package(
        path=
            LIVE_MANIFEST_PATH,

        body_key=
            "manifest",

        hash_key=
            "manifest_sha256",
    )

    require_disabled(
        gate=
            gate,

        prefix=
            "live_manifest",

        body=
            manifest,
    )

    state_hash = (
        sha256_json(
            shadow_state
        )
    )

    gate.require(
        name=
            "live_manifest_bound_to_current_shadow_state",

        condition=(
            manifest.get(
                "strategy_state_sha256"
            )
            == state_hash
            and
            manifest.get(
                "strategy_state_date"
            )
            == shadow_state.get(
                "last_date"
            )
        ),

        detail={
            "manifest_state_sha256":
                manifest.get(
                    "strategy_state_sha256"
                ),

            "current_state_sha256":
                state_hash,

            "manifest_date":
                manifest.get(
                    "strategy_state_date"
                ),

            "state_date":
                shadow_state.get(
                    "last_date"
                ),
        },
    )

    gate.require(
        name=
            "baseline_live_manifest_has_no_event",

        condition=(
            manifest.get(
                "manifest_type"
            )
            == "NO_EVENT_SNAPSHOT"
            and
            manifest.get(
                "strategy_event_present"
            )
            is False
            and
            manifest.get(
                "proposed_orders"
            )
            == []
        ),

        detail={
            "manifest_type":
                manifest.get(
                    "manifest_type"
                ),

            "strategy_event_present":
                manifest.get(
                    "strategy_event_present"
                ),

            "proposed_orders":
                manifest.get(
                    "proposed_orders"
                ),
        },
    )

    (
        intents_package,
        intents,
        intents_hash,
    ) = verify_package(
        path=
            LIVE_INTENTS_PATH,

        body_key=
            "intent_bundle",

        hash_key=
            "intent_bundle_sha256",
    )

    require_disabled(
        gate=
            gate,

        prefix=
            "live_intents",

        body=
            intents,
    )

    gate.require(
        name=
            "live_intents_network_write_false",

        condition=(
            intents.get(
                "network_write_capability"
            )
            is False
        ),

        detail=
            intents.get(
                "network_write_capability"
            ),
    )

    gate.require(
        name=
            "live_intents_bound_to_manifest",

        condition=(
            intents.get(
                "manifest_id"
            )
            == manifest_package.get(
                "manifest_id"
            )
            and
            intents.get(
                "manifest_sha256"
            )
            == manifest_hash
        ),

        detail={
            "intent_manifest_id":
                intents.get(
                    "manifest_id"
                ),

            "manifest_id":
                manifest_package.get(
                    "manifest_id"
                ),

            "intent_manifest_sha256":
                intents.get(
                    "manifest_sha256"
                ),

            "manifest_sha256":
                manifest_hash,
        },
    )

    gate.require(
        name=
            "baseline_live_intents_empty",

        condition=(
            intents.get(
                "candidate_intents"
            )
            == []
        ),

        detail=
            intents.get(
                "candidate_intents"
            ),
    )

    (
        compiler_package,
        compiler,
        compiler_hash,
    ) = verify_package(
        path=
            SCHEDULED_COMPILER_PATH,

        body_key=
            "compiler",

        hash_key=
            "compiler_sha256",
    )

    require_disabled(
        gate=
            gate,

        prefix=
            "scheduled_compiler",

        body=
            compiler,
    )

    gate.require(
        name=
            "scheduled_compiler_network_write_false",

        condition=(
            compiler.get(
                "network_write_capability"
            )
            is False
        ),

        detail=
            compiler.get(
                "network_write_capability"
            ),
    )

    gate.require(
        name=
            "current_compiler_artifact_is_non_genuine_test",

        condition=(
            compiler.get(
                "compiler_mode"
            )
            == "synthetic"
            and
            compiler.get(
                "genuine_scheduled_event"
            )
            is False
        ),

        detail={
            "compiler_mode":
                compiler.get(
                    "compiler_mode"
                ),

            "genuine_scheduled_event":
                compiler.get(
                    "genuine_scheduled_event"
                ),
        },
    )

    (
        v1_package,
        v1_permit,
        v1_hash,
    ) = verify_package(
        path=
            V1_PERMIT_PATH,

        body_key=
            "permit",

        hash_key=
            "permit_sha256",
    )

    require_disabled(
        gate=
            gate,

        prefix=
            "v1_permit",

        body=
            v1_permit,
    )

    gate.require(
        name=
            "v1_permit_not_issued",

        condition=(
            v1_permit.get(
                "permit_issued"
            )
            is False
            and
            v1_permit.get(
                "network_write_capability"
            )
            is False
        ),

        detail={
            "permit_issued":
                v1_permit.get(
                    "permit_issued"
                ),

            "network_write_capability":
                v1_permit.get(
                    "network_write_capability"
                ),

            "denial_reason":
                v1_permit.get(
                    "denial_reason"
                ),
        },
    )

    gate.require(
        name=
            "v1_permit_bound_to_compiler",

        condition=(
            v1_permit.get(
                "source_compiler_sha256"
            )
            == compiler_hash
        ),

        detail={
            "permit":
                v1_permit.get(
                    "source_compiler_sha256"
                ),

            "compiler":
                compiler_hash,
        },
    )

    (
        v2_package,
        v2,
        v2_hash,
    ) = verify_package(
        path=
            V2_SIMULATION_PATH,

        body_key=
            "permit_v2_simulation",

        hash_key=
            "permit_v2_simulation_sha256",
    )

    require_disabled(
        gate=
            gate,

        prefix=
            "v2_simulation",

        body=
            v2,
    )

    gate.require(
        name=
            "v2_simulation_is_simulation_only",

        condition=(
            v2.get(
                "simulation_only"
            )
            is True
            and
            v2.get(
                "permit_issued"
            )
            is False
            and
            v2.get(
                "network_write_capability"
            )
            is False
            and
            v2.get(
                "writer_connected"
            )
            is False
        ),

        detail={
            "simulation_only":
                v2.get(
                    "simulation_only"
                ),

            "permit_issued":
                v2.get(
                    "permit_issued"
                ),

            "writer_connected":
                v2.get(
                    "writer_connected"
                ),
        },
    )

    live_snapshot_conditions = (
        v2.get(
            "conditions",
            {}
        )
    )

    required_live_snapshot_conditions = [
        "account_status_active",
        "account_not_blocked",
        "trading_not_blocked",
        "no_open_orders",
        "permit_built_while_kill_switch_engaged",
    ]

    snapshot_ok = all(
        live_snapshot_conditions.get(
            key
        )
        is True
        for key
        in required_live_snapshot_conditions
    )

    gate.require(
        name=
            "committed_live_readonly_snapshot_account_checks",

        condition=
            snapshot_ok,

        detail={
            key:
                live_snapshot_conditions.get(
                    key
                )
            for key
            in required_live_snapshot_conditions
        },
    )

    gate.require(
        name=
            "v2_simulation_schema_incompatible_with_writer",

        condition=(
            v2.get(
                "schema"
            )
            != writer.REQUIRED_PERMIT_SCHEMA
            and
            v2.get(
                "future_writer_required_schema"
            )
            == writer.REQUIRED_PERMIT_SCHEMA
        ),

        detail={
            "simulation_schema":
                v2.get(
                    "schema"
                ),

            "writer_required":
                writer.REQUIRED_PERMIT_SCHEMA,
        },
    )

    (
        rehearsal_package,
        rehearsal,
        rehearsal_hash,
    ) = verify_package(
        path=
            ACTIVATION_REHEARSAL_PATH,

        body_key=
            "rehearsal",

        hash_key=
            "rehearsal_sha256",
    )

    require_disabled(
        gate=
            gate,

        prefix=
            "positive_rehearsal",

        body=
            rehearsal,
    )

    replay = (
        rehearsal.get(
            "replay_rehearsal",
            {}
        )
    )

    gate.require(
        name=
            "positive_rehearsal_contract_conditions_pass",

        condition=(
            rehearsal.get(
                "all_contract_conditions_satisfied"
            )
            is True
            and
            rehearsal.get(
                "offline_rehearsal"
            )
            is True
            and
            rehearsal.get(
                "simulation_only"
            )
            is True
        ),

        detail={
            "all_contract_conditions_satisfied":
                rehearsal.get(
                    "all_contract_conditions_satisfied"
                ),

            "offline_rehearsal":
                rehearsal.get(
                    "offline_rehearsal"
                ),

            "simulation_only":
                rehearsal.get(
                    "simulation_only"
                ),
        },
    )

    gate.require(
        name=
            "positive_rehearsal_replay_protection",

        condition=(
            replay.get(
                "first_attempt_all_conditions_pass"
            )
            is True
            and
            replay.get(
                "event_marked_consumed"
            )
            is True
            and
            replay.get(
                "second_attempt_all_conditions_pass"
            )
            is False
            and
            replay.get(
                "second_attempt_replay_condition"
            )
            is False
        ),

        detail=
            replay,
    )

    writer_rejection = (
        rehearsal.get(
            "writer_rejection_proof",
            {}
        )
    )

    writer_disconnect = (
        rehearsal.get(
            "writer_disconnect_proof",
            {}
        )
    )

    gate.require(
        name=
            "positive_rehearsal_writer_rejection",

        condition=(
            writer_rejection.get(
                "writer_rejected"
            )
            is True
        ),

        detail=
            writer_rejection,
    )

    gate.require(
        name=
            "positive_rehearsal_writer_disconnect",

        condition=(
            writer_disconnect.get(
                "writer_disconnected"
            )
            is True
        ),

        detail=
            writer_disconnect,
    )

    gate.evidence[
        "live_artifacts"
    ] = {
        "manifest_id":
            manifest_package.get(
                "manifest_id"
            ),

        "manifest_sha256":
            manifest_hash,

        "intent_bundle_sha256":
            intents_hash,

        "scheduled_compiler_sha256":
            compiler_hash,

        "v1_permit_sha256":
            v1_hash,

        "v2_simulation_sha256":
            v2_hash,

        "positive_rehearsal_sha256":
            rehearsal_hash,

        "committed_live_account_binding_sha256":
            v2.get(
                "live_account_binding_sha256"
            ),

        "live_snapshot_candidate_expiry":
            v2.get(
                "candidate_expiry"
            ),

        "live_snapshot_market_session_open":
            live_snapshot_conditions.get(
                "market_session_open"
            ),

        "permit_issued":
            False,

        "live_execution_authorized":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,
    }


# ============================================================
# WRITER DISCONNECTION
# ============================================================


def verify_writer(
    gate: EvidenceGate,
):

    gate.require(
        name=
            "writer_declared_disconnected",

        condition=(
            writer.LIVE_WRITER_CONNECTED
            is False
        ),

        detail=
            writer.LIVE_WRITER_CONNECTED,
    )

    gate.require(
        name=
            "writer_requires_future_v2_schema",

        condition=(
            writer.REQUIRED_PERMIT_SCHEMA
            == "FUND100_LIVE_EXECUTION_PERMIT_V2"
        ),

        detail=
            writer.REQUIRED_PERMIT_SCHEMA,
    )

    disconnected = False

    disconnect_reason = ""

    try:

        writer.require_adapter_connected()

    except writer.LiveWriterDisconnected as exc:

        disconnected = True

        disconnect_reason = str(
            exc
        )

    gate.require(
        name=
            "writer_hard_disconnect_guard",

        condition=
            disconnected,

        detail=
            disconnect_reason,
    )

    gate.evidence[
        "writer"
    ] = {
        "source_present":
            True,

        "connected":
            False,

        "required_permit_schema":
            writer.REQUIRED_PERMIT_SCHEMA,

        "hard_disconnect_verified":
            disconnected,

        "disconnect_reason":
            disconnect_reason,

        "runnable_live_workflow":
            False,
    }


# ============================================================
# COMPONENT INVENTORY
# ============================================================


def verify_live_components(
    gate: EvidenceGate,
):

    missing = [
        filename
        for filename
        in LIVE_COMPONENTS
        if not (
            ROOT
            / filename
        ).exists()
    ]

    gate.require(
        name=
            "live_safety_components_present",

        condition=(
            len(
                missing
            )
            == 0
        ),

        detail={
            "missing":
                missing,
        },
    )


# ============================================================
# REPORT
# ============================================================


def build_report(
    gate: EvidenceGate,
):

    git_sha = (
        os.environ.get(
            "GITHUB_SHA"
        )
        or
        git_value(
            "rev-parse",
            "HEAD",
        )
    )

    git_branch = (
        os.environ.get(
            "GITHUB_REF_NAME"
        )
        or
        git_value(
            "branch",
            "--show-current",
        )
    )

    body = {
        "schema":
            "FUND100_PRE_LIVE_RELEASE_EVIDENCE_V1",

        "generated_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "repository":
            os.environ.get(
                "GITHUB_REPOSITORY",
                "nicobouch97/fund100-research",
            ),

        "git_sha":
            git_sha,

        "git_branch":
            git_branch,

        "github_run_id":
            os.environ.get(
                "GITHUB_RUN_ID"
            ),

        "github_run_attempt":
            os.environ.get(
                "GITHUB_RUN_ATTEMPT"
            ),

        "strategy":
            EXPECTED_STRATEGY,

        "experiment":
            EXPECTED_EXPERIMENT,

        # ----------------------------------------------------
        # This is an ENGINEERING evidence status only.
        # ----------------------------------------------------

        "engineering_evidence_status":
            (
                "PASS"
                if not gate.failures
                else "FAIL"
            ),

        # ----------------------------------------------------
        # No live-deployment decision is made here.
        # ----------------------------------------------------

        "live_activation_decision":
            "NOT_MADE",

        "live_execution_authorized":
            False,

        "permit_issued":
            False,

        "max_live_execution_notional_usd":
            0.0,

        "network_write_capability":
            False,

        "writer_connected":
            False,

        "automatic_promotion_allowed":
            False,

        "research_survivor_is_live_approval":
            False,

        "checks":
            gate.checks,

        "evidence":
            gate.evidence,
    }

    return {
        "evidence_sha256":
            sha256_json(
                body
            ),

        "evidence":
            body,
    }


def write_json_report(
    package: dict,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with JSON_OUTPUT_PATH.open(
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
            JSON_OUTPUT_PATH
        )
    )

    calculated = (
        sha256_json(
            stored[
                "evidence"
            ]
        )
    )

    recorded = str(
        stored[
            "evidence_sha256"
        ]
    )

    if calculated != recorded:

        raise RuntimeError(
            "Release evidence JSON hash verification failed."
        )


def write_markdown_report(
    package: dict,
):

    body = (
        package[
            "evidence"
        ]
    )

    evidence = (
        body[
            "evidence"
        ]
    )

    research = (
        evidence.get(
            "research",
            {}
        )
    )

    shadow = (
        evidence.get(
            "shadow",
            {}
        )
    )

    live_artifacts = (
        evidence.get(
            "live_artifacts",
            {}
        )
    )

    writer_evidence = (
        evidence.get(
            "writer",
            {}
        )
    )

    lines = [
        "# Fund-100 Pre-Live Release Evidence",
        "",
        (
            "**Engineering evidence status:** "
            + body[
                "engineering_evidence_status"
            ]
        ),
        "",
        (
            "**Live activation decision:** "
            + body[
                "live_activation_decision"
            ]
        ),
        "",
        (
            "**Evidence SHA256:** `"
            + package[
                "evidence_sha256"
            ]
            + "`"
        ),
        "",
        "## Safety state",
        "",
        "- Live execution authorized: **FALSE**",
        "- Permit issued: **FALSE**",
        "- Maximum live execution notional: **$0.00**",
        "- Network write capability: **FALSE**",
        "- Writer connected: **FALSE**",
        "- Automatic promotion allowed: **FALSE**",
        "",
        "## Research lineage",
        "",
        (
            "- Experiment: `"
            + str(
                research.get(
                    "experiment_id"
                )
            )
            + "`"
        ),
        (
            "- Recorded research status: `"
            + str(
                research.get(
                    "status"
                )
            )
            + "`"
        ),
        (
            "- Historical cutoff: `"
            + str(
                research.get(
                    "historical_cutoff"
                )
            )
            + "`"
        ),
        (
            "- Frozen data SHA256: `"
            + str(
                research.get(
                    "research_data_sha256"
                )
            )
            + "`"
        ),
        (
            "- Research result SHA256: `"
            + str(
                research.get(
                    "result_sha256"
                )
            )
            + "`"
        ),
        "",
        "> "
        + str(
            research.get(
                "research_warning",
                "",
            )
        ),
        "",
        "## Shadow state",
        "",
        (
            "- State date: `"
            + str(
                shadow.get(
                    "state_date"
                )
            )
            + "`"
        ),
        (
            "- Pending strategy event: `"
            + str(
                shadow.get(
                    "pending_event"
                )
            )
            + "`"
        ),
        (
            "- Satellite total: `"
            + str(
                shadow.get(
                    "satellite_total"
                )
            )
            + "`"
        ),
        "",
        "## Live evidence",
        "",
        (
            "- Manifest SHA256: `"
            + str(
                live_artifacts.get(
                    "manifest_sha256"
                )
            )
            + "`"
        ),
        (
            "- V1 permit SHA256: `"
            + str(
                live_artifacts.get(
                    "v1_permit_sha256"
                )
            )
            + "`"
        ),
        (
            "- V2 simulation SHA256: `"
            + str(
                live_artifacts.get(
                    "v2_simulation_sha256"
                )
            )
            + "`"
        ),
        (
            "- Positive rehearsal SHA256: `"
            + str(
                live_artifacts.get(
                    "positive_rehearsal_sha256"
                )
            )
            + "`"
        ),
        (
            "- Committed live account binding: `"
            + str(
                live_artifacts.get(
                    "committed_live_account_binding_sha256"
                )
            )
            + "`"
        ),
        "",
        "## Writer boundary",
        "",
        (
            "- Connected: `"
            + str(
                writer_evidence.get(
                    "connected"
                )
            )
            + "`"
        ),
        (
            "- Required permit schema: `"
            + str(
                writer_evidence.get(
                    "required_permit_schema"
                )
            )
            + "`"
        ),
        (
            "- Hard disconnect verified: `"
            + str(
                writer_evidence.get(
                    "hard_disconnect_verified"
                )
            )
            + "`"
        ),
        "",
        "## Checks",
        "",
    ]

    for check in (
        body[
            "checks"
        ]
    ):

        marker = (
            "PASS"
            if check[
                "passed"
            ]
            else "FAIL"
        )

        lines.append(
            "- **"
            + marker
            + "** — `"
            + check[
                "name"
            ]
            + "`"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        (
            "A PASS means the committed engineering evidence "
            "chain is internally consistent at this repository "
            "revision. It does not authorize live execution, "
            "select a live capital amount, or convert the "
            "research result into an investment recommendation."
        ),
        "",
    ])

    MARKDOWN_OUTPUT_PATH.write_text(
        "\n".join(
            lines
        ),
        encoding="utf-8",
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 PRE-LIVE RELEASE EVIDENCE GATE"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: OFFLINE EVIDENCE VERIFICATION"
    )

    print(
        "Alpaca credentials required: NO"
    )

    print(
        "Broker network access: NONE"
    )

    print(
        "Order submission capability: NONE"
    )

    gate = (
        EvidenceGate()
    )

    verify_preconditions(
        gate
    )

    verify_kill_switch(
        gate
    )

    verify_research_lineage(
        gate
    )

    shadow_state = (
        verify_shadow(
            gate
        )
    )

    verify_paper_architecture(
        gate
    )

    verify_live_components(
        gate
    )

    verify_live_chain(
        gate=
            gate,

        shadow_state=
            shadow_state,
    )

    verify_writer(
        gate
    )

    print(
        "\n============================================"
    )

    print(
        "EVIDENCE CHECKS"
    )

    print(
        "============================================"
    )

    for check in (
        gate.checks
    ):

        status = (
            "PASS"
            if check[
                "passed"
            ]
            else "FAIL"
        )

        print(
            f"{status}: {check['name']}"
        )

    if gate.failures:

        print(
            "\n============================================"
        )

        print(
            "PRE-LIVE RELEASE EVIDENCE: FAILED"
        )

        print(
            "============================================"
        )

        print(
            f"\nFailures: "
            f"{len(gate.failures)}"
        )

        for failure in (
            gate.failures
        ):

            print(
                f"\nFAIL: "
                f"{failure['name']}"
            )

            print(
                json.dumps(
                    failure[
                        "detail"
                    ],
                    indent=2,
                    default=str,
                )
            )

        raise RuntimeError(
            "Pre-live evidence gate failed."
        )

    package = (
        build_report(
            gate
        )
    )

    write_json_report(
        package
    )

    write_markdown_report(
        package
    )

    print(
        "\n============================================"
    )

    print(
        "PRE-LIVE RELEASE EVIDENCE PACKAGE"
    )

    print(
        "============================================"
    )

    print(
        f"\nChecks passed: "
        f"{len(gate.passes)}"
    )

    print(
        "Checks failed: 0"
    )

    print(
        f"\nEvidence SHA256: "
        f"{package['evidence_sha256']}"
    )

    print(
        f"JSON report: "
        f"{JSON_OUTPUT_PATH.relative_to(ROOT)}"
    )

    print(
        f"Markdown report: "
        f"{MARKDOWN_OUTPUT_PATH.relative_to(ROOT)}"
    )

    print(
        "\nEngineering evidence status: PASS"
    )

    print(
        "Live activation decision: NOT MADE"
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
        "Network write capability: ABSENT"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        "\n============================================"
    )

    print(
        "PRE-LIVE RELEASE EVIDENCE GATE: PASS"
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
            "PRE-LIVE RELEASE EVIDENCE GATE: FAILED",
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
