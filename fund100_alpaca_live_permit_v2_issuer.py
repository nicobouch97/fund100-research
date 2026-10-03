from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

import fund100_alpaca_live_execution_boundary as boundary
import fund100_alpaca_live_preflight as preflight
import fund100_alpaca_live_readonly_smoke as live
import fund100_alpaca_live_writer_disconnected as writer

from fund100_broker_safety import (
    get_kill_switch_state,
)


# ============================================================
# FUND-100 ALPACA LIVE PERMIT V2 ISSUER v1.0
# ============================================================
#
# LIVE ENVIRONMENT — READ ONLY.
#
# THIS FILE SUBMITS NO ORDERS.
#
# It can evaluate and, only under explicit conditions, create
# a writer-compatible:
#
#     FUND100_LIVE_EXECUTION_PERMIT_V2
#
# Important separation:
#
# - permit issuer: may create an authorization artifact
# - live writer: remains HARD DISCONNECTED
# - broker mutations: NONE
#
# v1.0 refuses to issue unless:
#
# - safe pre-live baseline lock verifies
# - locked research/code subset is unchanged
# - genuine CURRENT V5-002 scheduled event exists
# - manifest/compiler/state hashes all agree
# - compiler is inside execution window
# - every candidate symbol is supported by current writer
# - live account binding matches locked account binding
# - account is active/unblocked
# - no live open orders exist
# - market is open
# - compiler market snapshot remains fresh
# - event has never received a V2 permit
# - requested cap is positive
# - independent hard cap exists and is not exceeded
# - exact two-step approval token matches
# - kill switch remains ENGAGED
# - live write mode remains DISABLED
# - live writer remains disconnected
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

BASELINE_ACCOUNT_SNAPSHOT_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "live_execution_permit_v2_simulation.json"
)

SHADOW_STATE_PATH = (
    ROOT
    / "shadow_outputs"
    / "v5_002"
    / "shadow_state.json"
)

LIVE_MANIFEST_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "live_execution_manifest.json"
)

SCHEDULED_COMPILER_PATH = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
    / "scheduled_execution_time.json"
)

OUTPUT_DIR = (
    ROOT
    / "live_activation_outputs"
    / "v5_002"
)

PERMIT_PATH = (
    OUTPUT_DIR
    / "live_execution_permit_v2.json"
)

ISSUE_LEDGER_PATH = (
    OUTPUT_DIR
    / "live_permit_issue_ledger.json"
)


RELEASE_LOCK_SCHEMA = (
    "FUND100_PRE_LIVE_RELEASE_LOCK_V1"
)

PERMIT_SCHEMA = (
    "FUND100_LIVE_EXECUTION_PERMIT_V2"
)

COMPILER_SCHEMA = (
    "FUND100_SCHEDULED_EXECUTION_COMPILER_V1"
)

MANIFEST_SCHEMA = (
    "FUND100_LIVE_DRYRUN_MANIFEST_V1"
)

ISSUE_LEDGER_SCHEMA = (
    "FUND100_LIVE_PERMIT_ISSUE_LEDGER_V1"
)

EXPECTED_STRATEGY = (
    "V5-002_SHADOW"
)

ISSUER_ARM_VALUE = (
    "YES_EVALUATE_REAL_V2_PERMIT"
)

ACTION_CHECK = "check"
ACTION_PREVIEW = "preview"
ACTION_ISSUE = "issue"

ALLOWED_ACTIONS = {
    ACTION_CHECK,
    ACTION_PREVIEW,
    ACTION_ISSUE,
}

MIN_MINUTES_TO_CLOSE = 5.0
MAX_MINUTES_TO_CLOSE = 45.0

MAX_COMPILER_SNAPSHOT_AGE_MINUTES = 30.0


# ============================================================
# STATIC BASELINE SUBSET
# ============================================================
#
# These files must remain byte-identical to the frozen safe
# baseline.
#
# Dynamic shadow/live-event artifacts are intentionally not
# included because a genuine future session must change them.
#
# ============================================================


LOCKED_STATIC_FILES = [
    "research_lab/frozen_history_v2.csv",
    "research_lab/frozen_history_v2_manifest.json",
    "research_lab/challengers/V5-002.json",
    "research_lab/results/V5-002.json",

    "fund100_v5_002_shadow.py",
    "fund100_v5_002_shadow_v1_1.py",
    "audit_v5_002_engine.py",

    "shadow_outputs/v5_002/shadow_manifest.json",

    "fund100_broker_safety.py",

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

    "audit_fund100_live_boundary.py",
    "audit_fund100_live_boundary_v1_2.py",

    "fund100_pre_live_release_gate.py",

    # Used as the locked live-account identity source.
    "live_dryrun_outputs/v5_002/"
    "live_execution_permit_v2_simulation.json",
]


# ============================================================
# EXCEPTIONS
# ============================================================


class PermitIssuerStop(
    RuntimeError
):
    pass


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


def sha256_text(
    value: str,
) -> str:

    return hashlib.sha256(
        value.encode(
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


# ============================================================
# FILE HELPERS
# ============================================================


def load_json(
    path: Path,
):

    if not path.exists():

        raise PermitIssuerStop(
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

    if (
        body_key not in package
        or hash_key not in package
    ):

        raise PermitIssuerStop(
            f"{path.name}: incomplete hashed package."
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

        raise PermitIssuerStop(
            f"{path.name}: SHA256 verification failed."
        )

    return (
        package,
        body,
        recorded,
    )


def atomic_write_json(
    path: Path,
    obj: dict,
):

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary = (
        path.with_suffix(
            path.suffix
            + ".tmp"
        )
    )

    with temporary.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            obj,
            handle,
            indent=2,
            sort_keys=True,
        )

        handle.write(
            "\n"
        )

    temporary.replace(
        path
    )


# ============================================================
# ENVIRONMENT
# ============================================================


def require_issuer_arm():

    value = (
        os.environ.get(
            "FUND100_ENABLE_REAL_V2_PERMIT_ISSUER",
            "",
        )
        .strip()
    )

    if value != ISSUER_ARM_VALUE:

        raise PermitIssuerStop(
            "Real V2 permit issuer is not explicitly armed."
        )


def get_action():

    action = (
        os.environ.get(
            "FUND100_LIVE_PERMIT_ACTION",
            ACTION_CHECK,
        )
        .strip()
        .lower()
    )

    if action not in ALLOWED_ACTIONS:

        raise PermitIssuerStop(
            "FUND100_LIVE_PERMIT_ACTION must be "
            "check, preview, or issue."
        )

    return action


# ============================================================
# MONEY
# ============================================================


def parse_money(
    raw,
    field_name: str,
) -> Decimal:

    text = str(
        raw or ""
    ).strip()

    if not text:

        return Decimal(
            "0.00"
        )

    try:

        value = Decimal(
            text
        )

    except InvalidOperation as exc:

        raise PermitIssuerStop(
            f"{field_name}: invalid monetary value."
        ) from exc

    if not value.is_finite():

        raise PermitIssuerStop(
            f"{field_name}: monetary value must be finite."
        )

    if value < 0:

        raise PermitIssuerStop(
            f"{field_name}: monetary value cannot be negative."
        )

    cents = value.quantize(
        Decimal(
            "0.01"
        )
    )

    if value != cents:

        raise PermitIssuerStop(
            f"{field_name}: use no more than two decimals."
        )

    return cents


def money_string(
    value: Decimal,
) -> str:

    return format(
        value,
        ".2f",
    )


# ============================================================
# RELEASE LOCK
# ============================================================


def load_release_lock():

    (
        package,
        body,
        recorded_hash,
    ) = verify_package(
        path=
            RELEASE_LOCK_PATH,

        body_key=
            "release_lock",

        hash_key=
            "release_lock_sha256",
    )

    if (
        body.get(
            "schema"
        )
        != RELEASE_LOCK_SCHEMA
    ):

        raise PermitIssuerStop(
            "Unexpected release-lock schema."
        )

    required_false = [
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

            raise PermitIssuerStop(
                "Release-lock safety field "
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

        raise PermitIssuerStop(
            "Release-lock baseline cap is not $0.00."
        )

    if (
        body.get(
            "engineering_evidence_status"
        )
        != "PASS"
    ):

        raise PermitIssuerStop(
            "Release-lock engineering evidence "
            "is not PASS."
        )

    return (
        package,
        body,
        recorded_hash,
    )


def verify_locked_static_files(
    lock_body: dict,
):

    expected = (
        lock_body.get(
            "critical_file_sha256",
            {}
        )
    )

    mismatches = []

    for relative in LOCKED_STATIC_FILES:

        if relative not in expected:

            mismatches.append({
                "file":
                    relative,

                "reason":
                    "NOT_PRESENT_IN_RELEASE_LOCK",
            })

            continue

        path = (
            ROOT
            / relative
        )

        if not path.exists():

            mismatches.append({
                "file":
                    relative,

                "reason":
                    "MISSING",
            })

            continue

        actual = (
            sha256_file(
                path
            )
        )

        if actual != expected[
            relative
        ]:

            mismatches.append({
                "file":
                    relative,

                "expected":
                    expected[
                        relative
                    ],

                "actual":
                    actual,
            })

    if mismatches:

        raise PermitIssuerStop(
            "STATIC BASELINE STOP:\n"
            + json.dumps(
                mismatches,
                indent=2,
            )
        )

    return {
        relative:
            expected[
                relative
            ]
        for relative
        in LOCKED_STATIC_FILES
    }


# ============================================================
# LOCKED LIVE ACCOUNT IDENTITY
# ============================================================


def load_locked_account_binding():

    (
        _package,
        body,
        _recorded,
    ) = verify_package(
        path=
            BASELINE_ACCOUNT_SNAPSHOT_PATH,

        body_key=
            "permit_v2_simulation",

        hash_key=
            "permit_v2_simulation_sha256",
    )

    binding = str(
        body.get(
            "live_account_binding_sha256",
            "",
        )
    ).strip()

    if not binding:

        raise PermitIssuerStop(
            "Locked live-account binding is missing."
        )

    return binding


def build_account_binding(
    account: dict,
):

    account_id = str(
        account.get(
            "id",
            "",
        )
    ).strip()

    if not account_id:

        raise PermitIssuerStop(
            "Live account ID is missing."
        )

    return sha256_text(
        "FUND100_ALPACA_LIVE_ACCOUNT_V1:"
        + account_id
    )


# ============================================================
# CURRENT STATE / MANIFEST / COMPILER
# ============================================================


def load_current_event_chain():

    state = (
        load_json(
            SHADOW_STATE_PATH
        )
    )

    state_hash = (
        sha256_json(
            state
        )
    )

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

    if (
        manifest.get(
            "schema"
        )
        != MANIFEST_SCHEMA
    ):

        raise PermitIssuerStop(
            "Unexpected live manifest schema."
        )

    if (
        compiler.get(
            "schema"
        )
        != COMPILER_SCHEMA
    ):

        raise PermitIssuerStop(
            "Unexpected scheduled compiler schema."
        )

    if (
        state.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
    ):

        raise PermitIssuerStop(
            "Unexpected shadow strategy."
        )

    if (
        manifest.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
        or
        compiler.get(
            "strategy"
        )
        != EXPECTED_STRATEGY
    ):

        raise PermitIssuerStop(
            "Strategy identity mismatch."
        )

    intents = (
        compiler.get(
            "candidate_intents",
            []
        )
    )

    if not isinstance(
        intents,
        list,
    ):

        raise PermitIssuerStop(
            "Compiler candidate_intents is invalid."
        )

    candidate_symbols = {
        str(
            item.get(
                "symbol",
                "",
            )
        ).upper()
        for item
        in intents
        if isinstance(
            item,
            dict,
        )
    }

    source_intents_non_executable = all(
        (
            item.get(
                "executable"
            )
            is False
            and
            item.get(
                "notional_usd"
            )
            is None
        )
        for item
        in intents
        if isinstance(
            item,
            dict,
        )
    )

    conditions = {
        "manifest_bound_to_current_state":
            (
                manifest.get(
                    "strategy_state_sha256"
                )
                == state_hash
            ),

        "manifest_date_matches_current_state":
            (
                str(
                    manifest.get(
                        "strategy_state_date"
                    )
                )
                == str(
                    state.get(
                        "last_date"
                    )
                )
            ),

        "manifest_is_pending_scheduled_event":
            (
                manifest.get(
                    "manifest_type"
                )
                == "PENDING_STRATEGY_EVENT"
                and
                manifest.get(
                    "strategy_event_present"
                )
                is True
                and
                manifest.get(
                    "event_source"
                )
                == "SCHEDULED"
            ),

        "compiler_bound_to_current_state":
            (
                compiler.get(
                    "strategy_state_sha256"
                )
                == state_hash
            ),

        "compiler_date_matches_current_state":
            (
                str(
                    compiler.get(
                        "strategy_state_date"
                    )
                )
                == str(
                    state.get(
                        "last_date"
                    )
                )
            ),

        "compiler_bound_to_current_manifest":
            (
                compiler.get(
                    "source_manifest_id"
                )
                == manifest_package.get(
                    "manifest_id"
                )
                and
                compiler.get(
                    "source_manifest_sha256"
                )
                == manifest_hash
            ),

        "compiler_mode_is_current":
            (
                compiler.get(
                    "compiler_mode"
                )
                == "current"
            ),

        "compiler_status_is_genuine":
            (
                compiler.get(
                    "status"
                )
                == "GENUINE_SCHEDULED_EVENT"
            ),

        "compiler_genuine_event_flag":
            (
                compiler.get(
                    "genuine_scheduled_event"
                )
                is True
            ),

        "compiler_execution_window_eligible":
            (
                compiler.get(
                    "execution_window_eligible"
                )
                is True
            ),

        "compiler_has_candidate_intents":
            (
                len(
                    intents
                )
                > 0
            ),

        "compiler_source_is_non_executable":
            (
                compiler.get(
                    "live_execution_authorized"
                )
                is False
                and
                abs(
                    float(
                        compiler.get(
                            "max_live_execution_notional_usd",
                            -1.0,
                        )
                    )
                )
                <= 1e-12
                and
                compiler.get(
                    "network_write_capability"
                )
                is False
                and
                compiler.get(
                    "broker_write_mode"
                )
                == "DISABLED"
            ),

        "compiler_intents_are_non_executable":
            source_intents_non_executable,

        "candidate_symbols_supported_by_writer":
            (
                bool(
                    candidate_symbols
                )
                and
                candidate_symbols.issubset(
                    writer.ALLOWED_SYMBOLS
                )
            ),
    }

    event_material = {
        "strategy":
            EXPECTED_STRATEGY,

        "strategy_state_sha256":
            state_hash,

        "manifest_id":
            manifest_package.get(
                "manifest_id"
            ),

        "manifest_sha256":
            manifest_hash,

        "compiler_sha256":
            compiler_hash,

        "market_snapshot_sha256":
            compiler.get(
                "market_snapshot_sha256"
            ),

        "candidate_intents":
            intents,
    }

    event_binding_sha256 = (
        sha256_json(
            event_material
        )
    )

    event_id = (
        "f100-live-event-"
        + event_binding_sha256[
            :20
        ]
    )

    return {
        "state":
            state,

        "state_sha256":
            state_hash,

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

        "candidate_intents":
            intents,

        "candidate_symbols":
            sorted(
                candidate_symbols
            ),

        "event_id":
            event_id,

        "event_binding_sha256":
            event_binding_sha256,

        "conditions":
            conditions,
    }


# ============================================================
# MARKET SESSION
# ============================================================


def parse_timestamp(
    value,
):

    text = str(
        value or ""
    ).strip()

    if not text:

        raise PermitIssuerStop(
            "Missing timestamp."
        )

    return datetime.fromisoformat(
        text.replace(
            "Z",
            "+00:00",
        )
    )


def build_session(
    clock: dict,
):

    now = (
        parse_timestamp(
            clock.get(
                "timestamp"
            )
        )
    )

    close = (
        parse_timestamp(
            clock.get(
                "next_close"
            )
        )
    )

    minutes_to_close = (
        (
            close
            - now
        ).total_seconds()
        / 60.0
    )

    body = {
        "clock_timestamp":
            str(
                clock.get(
                    "timestamp"
                )
            ),

        "candidate_expiry":
            str(
                clock.get(
                    "next_close"
                )
            ),

        "market_is_open":
            bool(
                clock.get(
                    "is_open",
                    False,
                )
            ),
    }

    return {
        **body,

        "expiry_is_future":
            close > now,

        "minutes_to_close":
            minutes_to_close,

        "session_binding_sha256":
            sha256_json(
                body
            ),
    }


def compiler_snapshot_age_minutes(
    compiler: dict,
    clock: dict,
):

    snapshot = (
        compiler.get(
            "market_snapshot"
        )
    )

    if not isinstance(
        snapshot,
        dict,
    ):

        return None

    now = (
        parse_timestamp(
            clock.get(
                "timestamp"
            )
        )
    )

    ages = []

    for item in snapshot.values():

        if not isinstance(
            item,
            dict,
        ):

            return None

        raw = (
            item.get(
                "latest_bar_timestamp"
            )
        )

        if not raw:

            return None

        bar_time = (
            parse_timestamp(
                raw
            )
        )

        ages.append(
            (
                now
                - bar_time
            ).total_seconds()
            / 60.0
        )

    if not ages:

        return None

    return max(
        ages
    )


# ============================================================
# WRITER DISCONNECTION
# ============================================================


def writer_is_hard_disconnected():

    if (
        writer.LIVE_WRITER_CONNECTED
        is not False
    ):

        return False

    try:

        writer.require_adapter_connected()

    except writer.LiveWriterDisconnected:

        return True

    return False


# ============================================================
# PERMIT ISSUE LEDGER
# ============================================================


def empty_issue_ledger():

    body = {
        "schema":
            ISSUE_LEDGER_SCHEMA,

        "issued_events":
            [],
    }

    return {
        "ledger_sha256":
            sha256_json(
                body
            ),

        "ledger":
            body,
    }


def load_issue_ledger():

    if not ISSUE_LEDGER_PATH.exists():

        return empty_issue_ledger()

    (
        package,
        body,
        _recorded,
    ) = verify_package(
        path=
            ISSUE_LEDGER_PATH,

        body_key=
            "ledger",

        hash_key=
            "ledger_sha256",
    )

    if (
        body.get(
            "schema"
        )
        != ISSUE_LEDGER_SCHEMA
    ):

        raise PermitIssuerStop(
            "Unexpected permit-issue ledger schema."
        )

    if not isinstance(
        body.get(
            "issued_events",
            []
        ),
        list,
    ):

        raise PermitIssuerStop(
            "Invalid permit-issue ledger."
        )

    return package


def event_already_permitted(
    ledger_package: dict,
    event_id: str,
):

    return any(
        str(
            item.get(
                "event_id",
                "",
            )
        )
        == event_id
        for item
        in ledger_package[
            "ledger"
        ][
            "issued_events"
        ]
        if isinstance(
            item,
            dict,
        )
    )


def append_ledger_record(
    ledger_package: dict,
    record: dict,
):

    body = json.loads(
        json.dumps(
            ledger_package[
                "ledger"
            ]
        )
    )

    body[
        "issued_events"
    ].append(
        record
    )

    return {
        "ledger_sha256":
            sha256_json(
                body
            ),

        "ledger":
            body,
    }


# ============================================================
# APPROVAL TOKEN
# ============================================================


def build_approval_token(
    release_lock_id: str,
    event_id: str,
    compiler_sha256: str,
    account_binding_sha256: str,
    candidate_expiry: str,
    requested_cap: Decimal,
):

    material = {
        "release_lock_id":
            release_lock_id,

        "event_id":
            event_id,

        "compiler_sha256":
            compiler_sha256,

        "account_binding_sha256":
            account_binding_sha256,

        "candidate_expiry":
            candidate_expiry,

        "max_live_execution_notional_usd":
            money_string(
                requested_cap
            ),
    }

    digest = (
        sha256_json(
            material
        )
    )

    return (
        "F100-APPROVE-"
        + digest[
            :32
        ]
    )


# ============================================================
# REAL PERMIT PACKAGE
# ============================================================


def build_real_permit(
    release_lock_body: dict,
    release_lock_sha256: str,
    event: dict,
    account_binding_sha256: str,
    session: dict,
    requested_cap: Decimal,
    approval_token: str,
    previous_issue_ledger_sha256: str,
):

    issued_utc = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    issuer_source_sha256 = (
        sha256_file(
            Path(
                __file__
            )
        )
    )

    approval_hash = (
        sha256_text(
            approval_token
        )
    )

    permit_id = (
        "f100-v2permit-"
        + event[
            "event_binding_sha256"
        ][
            :12
        ]
        + "-"
        + approval_hash[
            :12
        ]
    )

    body = {
        "schema":
            PERMIT_SCHEMA,

        "permit_id":
            permit_id,

        "permit_issued":
            True,

        "permit_issued_utc":
            issued_utc,

        "strategy":
            EXPECTED_STRATEGY,

        "strategy_state_date":
            str(
                event[
                    "state"
                ].get(
                    "last_date"
                )
            ),

        "strategy_state_sha256":
            event[
                "state_sha256"
            ],

        "genuine_scheduled_event":
            True,

        "event_id":
            event[
                "event_id"
            ],

        "event_binding_sha256":
            event[
                "event_binding_sha256"
            ],

        "source_release_lock_id":
            release_lock_body[
                "release_lock_id"
            ],

        "source_release_lock_sha256":
            release_lock_sha256,

        "source_manifest_id":
            event[
                "manifest_package"
            ][
                "manifest_id"
            ],

        "source_manifest_sha256":
            event[
                "manifest_sha256"
            ],

        "source_compiler_sha256":
            event[
                "compiler_sha256"
            ],

        "market_snapshot_sha256":
            event[
                "compiler"
            ].get(
                "market_snapshot_sha256"
            ),

        "live_account_binding_sha256":
            account_binding_sha256,

        "session_binding_sha256":
            session[
                "session_binding_sha256"
            ],

        "candidate_expiry":
            session[
                "candidate_expiry"
            ],

        "manual_authorization_sha256":
            approval_hash,

        "max_live_execution_notional_usd":
            float(
                requested_cap
            ),

        # ----------------------------------------------------
        # Writer-compatible authorization state.
        # ----------------------------------------------------

        "live_execution_authorized":
            True,

        "network_write_capability":
            True,

        "broker_write_mode":
            "ENABLED",

        # ----------------------------------------------------
        # Additional boundaries.
        # ----------------------------------------------------

        "single_use":
            True,

        "event_previously_permitted":
            False,

        "kill_switch_state_at_issuance":
            "ENGAGED",

        "execution_requires_separate_kill_switch_transition":
            True,

        "writer_connected_at_issuance":
            False,

        "issuer_broker_write_capability":
            False,

        "issuer_http_methods":
            [
                "GET"
            ],

        "orders_submitted_by_issuer":
            0,

        "candidate_symbols":
            event[
                "candidate_symbols"
            ],

        "previous_issue_ledger_sha256":
            previous_issue_ledger_sha256,

        "issuer_source_sha256":
            issuer_source_sha256,
    }

    return {
        "permit_sha256":
            sha256_json(
                body
            ),

        "permit":
            body,
    }


# ============================================================
# CONDITION HELPERS
# ============================================================


def all_true(
    conditions: dict,
):

    return all(
        value is True
        for value
        in conditions.values()
    )


def failed_condition_names(
    conditions: dict,
):

    return [
        name
        for name, value
        in conditions.items()
        if value is not True
    ]


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 ALPACA LIVE V2 PERMIT ISSUER"
    )

    print(
        "============================================"
    )

    print(
        "\nBroker environment: ALPACA LIVE"
    )

    print(
        "Issuer broker methods: GET ONLY"
    )

    print(
        "Order submission implementation: NONE"
    )

    require_issuer_arm()

    action = (
        get_action()
    )

    print(
        f"Action: {action.upper()}"
    )

    # ========================================================
    # BASELINE LOCK
    # ========================================================

    (
        _lock_package,
        lock_body,
        lock_hash,
    ) = (
        load_release_lock()
    )

    locked_hashes = (
        verify_locked_static_files(
            lock_body
        )
    )

    expected_account_binding = (
        load_locked_account_binding()
    )

    print(
        "\nSafe baseline lock: PASS"
    )

    print(
        f"Release lock ID: "
        f"{lock_body['release_lock_id']}"
    )

    print(
        f"Release lock SHA256: "
        f"{lock_hash}"
    )

    print(
        f"Locked static files verified: "
        f"{len(locked_hashes)}"
    )

    # ========================================================
    # GLOBAL SAFETY
    # ========================================================

    kill_state = (
        get_kill_switch_state()
    )

    if kill_state != "ENGAGED":

        raise PermitIssuerStop(
            "V2 PERMIT STOP: "
            "broker kill switch must remain ENGAGED."
        )

    live.require_readonly_arm()

    boundary.require_live_writes_disabled()

    writer_disconnected = (
        writer_is_hard_disconnected()
    )

    if not writer_disconnected:

        raise PermitIssuerStop(
            "V2 PERMIT STOP: "
            "writer is no longer hard disconnected."
        )

    print(
        "\nBroker kill switch: ENGAGED — PASS"
    )

    print(
        "Live write mode: DISABLED — PASS"
    )

    print(
        "Writer hard-disconnect: PASS"
    )

    # ========================================================
    # EVENT CHAIN
    # ========================================================

    event = (
        load_current_event_chain()
    )

    # ========================================================
    # LIVE GET-ONLY ACCOUNT CHECK
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

    current_account_binding = (
        build_account_binding(
            account
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

    if not isinstance(
        open_orders,
        list,
    ):

        raise PermitIssuerStop(
            "Invalid live open-order response."
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

        raise PermitIssuerStop(
            "Invalid live market-clock response."
        )

    session = (
        build_session(
            clock
        )
    )

    snapshot_age = (
        compiler_snapshot_age_minutes(
            compiler=
                event[
                    "compiler"
                ],

            clock=
                clock,
        )
    )

    # ========================================================
    # REPLAY / DUPLICATE PERMIT
    # ========================================================

    issue_ledger = (
        load_issue_ledger()
    )

    already_permitted = (
        event_already_permitted(
            ledger_package=
                issue_ledger,

            event_id=
                event[
                    "event_id"
                ],
        )
    )

    # ========================================================
    # MONETARY CONTROLS
    # ========================================================

    requested_cap = (
        parse_money(
            os.environ.get(
                "FUND100_LIVE_MAX_NOTIONAL_USD",
                "",
            ),
            "FUND100_LIVE_MAX_NOTIONAL_USD",
        )
    )

    hard_cap = (
        parse_money(
            os.environ.get(
                "FUND100_LIVE_HARD_CAP_USD",
                "",
            ),
            "FUND100_LIVE_HARD_CAP_USD",
        )
    )

    # ========================================================
    # CONDITIONS
    # ========================================================

    conditions = {
        **event[
            "conditions"
        ],

        "kill_switch_engaged":
            (
                kill_state
                == "ENGAGED"
            ),

        "writer_hard_disconnected":
            writer_disconnected,

        "live_account_binding_matches_locked_account":
            (
                current_account_binding
                == expected_account_binding
            ),

        "account_status_active":
            (
                str(
                    account.get(
                        "status",
                        "",
                    )
                ).upper()
                == "ACTIVE"
            ),

        "account_not_blocked":
            (
                not bool(
                    account.get(
                        "account_blocked",
                        False,
                    )
                )
            ),

        "trading_not_blocked":
            (
                not bool(
                    account.get(
                        "trading_blocked",
                        False,
                    )
                )
            ),

        "transfers_not_blocked":
            (
                not bool(
                    account.get(
                        "transfers_blocked",
                        False,
                    )
                )
            ),

        "no_live_open_orders":
            (
                len(
                    open_orders
                )
                == 0
            ),

        "market_is_open":
            session[
                "market_is_open"
            ],

        "permit_expiry_is_future":
            session[
                "expiry_is_future"
            ],

        "inside_permit_execution_window":
            (
                MIN_MINUTES_TO_CLOSE
                <= session[
                    "minutes_to_close"
                ]
                <= MAX_MINUTES_TO_CLOSE
            ),

        "compiler_snapshot_is_fresh":
            (
                snapshot_age
                is not None
                and
                -2.0
                <= snapshot_age
                <= MAX_COMPILER_SNAPSHOT_AGE_MINUTES
            ),

        "event_not_previously_permitted":
            (
                not already_permitted
            ),
    }

    # Preview/issue additionally require positive independent
    # monetary controls.
    if action in {
        ACTION_PREVIEW,
        ACTION_ISSUE,
    }:

        conditions[
            "requested_execution_ceiling_positive"
        ] = (
            requested_cap
            > 0
        )

        conditions[
            "independent_hard_cap_positive"
        ] = (
            hard_cap
            > 0
        )

        conditions[
            "requested_ceiling_within_hard_cap"
        ] = (
            requested_cap
            > 0
            and
            hard_cap
            > 0
            and
            requested_cap
            <= hard_cap
        )

    # ========================================================
    # REPORT CONDITIONS
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "REAL V2 PERMIT CONDITIONS"
    )

    print(
        "============================================"
    )

    for name, passed in (
        conditions.items()
    ):

        print(
            (
                "PASS"
                if passed
                else "FAIL"
            )
            + ": "
            + name
        )

    failures = (
        failed_condition_names(
            conditions
        )
    )

    print(
        f"\nEvent ID: "
        f"{event['event_id']}"
    )

    print(
        f"Candidate symbols: "
        f"{event['candidate_symbols']}"
    )

    print(
        f"Minutes to close: "
        f"{session['minutes_to_close']:.2f}"
    )

    print(
        f"Compiler snapshot max age: "
        + (
            "UNAVAILABLE"
            if snapshot_age
            is None
            else
            f"{snapshot_age:.2f} minutes"
        )
    )

    # ========================================================
    # CHECK MODE
    # ========================================================

    if action == ACTION_CHECK:

        eligible = (
            len(
                failures
            )
            == 0
        )

        print(
            "\n============================================"
        )

        print(
            "REAL V2 PERMIT CHECK"
        )

        print(
            "============================================"
        )

        print(
            f"\nCurrent event structurally eligible: "
            f"{eligible}"
        )

        if failures:

            print(
                "Failed conditions:"
            )

            for name in failures:

                print(
                    f"  - {name}"
                )

        print(
            "\nPermit issued: FALSE"
        )

        print(
            "Writer connected: FALSE"
        )

        print(
            "Orders submitted: 0"
        )

        print(
            "\nREAL V2 PERMIT CHECK: PASS"
        )

        return

    # ========================================================
    # PREVIEW / ISSUE REQUIRE EVENT ELIGIBILITY
    # ========================================================

    if failures:

        raise PermitIssuerStop(
            "V2 PERMIT STOP: "
            "permit conditions failed: "
            + ", ".join(
                failures
            )
        )

    approval_token = (
        build_approval_token(
            release_lock_id=
                lock_body[
                    "release_lock_id"
                ],

            event_id=
                event[
                    "event_id"
                ],

            compiler_sha256=
                event[
                    "compiler_sha256"
                ],

            account_binding_sha256=
                current_account_binding,

            candidate_expiry=
                session[
                    "candidate_expiry"
                ],

            requested_cap=
                requested_cap,
        )
    )

    # ========================================================
    # PREVIEW
    # ========================================================

    if action == ACTION_PREVIEW:

        print(
            "\n============================================"
        )

        print(
            "REAL V2 PERMIT PREVIEW"
        )

        print(
            "============================================"
        )

        print(
            f"\nEvent ID: "
            f"{event['event_id']}"
        )

        print(
            f"Requested execution ceiling: "
            f"${money_string(requested_cap)}"
        )

        print(
            f"Independent hard ceiling: "
            f"${money_string(hard_cap)}"
        )

        print(
            f"Candidate expiry: "
            f"{session['candidate_expiry']}"
        )

        print(
            "\nManual approval token:"
        )

        print(
            approval_token
        )

        print(
            "\nPermit issued: FALSE"
        )

        print(
            "Writer connected: FALSE"
        )

        print(
            "Orders submitted: 0"
        )

        print(
            "\nREAL V2 PERMIT PREVIEW: PASS"
        )

        return

    # ========================================================
    # ISSUE
    # ========================================================

    supplied_token = (
        os.environ.get(
            "FUND100_LIVE_APPROVAL_TOKEN",
            "",
        )
        .strip()
    )

    if not supplied_token:

        raise PermitIssuerStop(
            "V2 PERMIT STOP: "
            "manual approval token is missing."
        )

    if not hmac.compare_digest(
        supplied_token,
        approval_token,
    ):

        raise PermitIssuerStop(
            "V2 PERMIT STOP: "
            "manual approval token does not match "
            "this event/cap/session."
        )

    previous_ledger_hash = (
        issue_ledger[
            "ledger_sha256"
        ]
    )

    permit_package = (
        build_real_permit(
            release_lock_body=
                lock_body,

            release_lock_sha256=
                lock_hash,

            event=
                event,

            account_binding_sha256=
                current_account_binding,

            session=
                session,

            requested_cap=
                requested_cap,

            approval_token=
                supplied_token,

            previous_issue_ledger_sha256=
                previous_ledger_hash,
        )
    )

    # --------------------------------------------------------
    # Prove that this is writer-compatible.
    #
    # This validates the artifact only.
    # submit_authorized_order_batch() is NOT called.
    # --------------------------------------------------------

    validated_permit, validated_cap = (
        writer.validate_permit_package(
            permit_package
        )
    )

    if (
        validated_permit.get(
            "permit_id"
        )
        != permit_package[
            "permit"
        ][
            "permit_id"
        ]
    ):

        raise PermitIssuerStop(
            "Writer permit validation identity mismatch."
        )

    if abs(
        float(
            validated_cap
        )
        - float(
            requested_cap
        )
    ) > 1e-9:

        raise PermitIssuerStop(
            "Writer permit validation cap mismatch."
        )

    # Writer must STILL remain disconnected after accepting
    # the permit schema.
    if not writer_is_hard_disconnected():

        raise PermitIssuerStop(
            "CRITICAL SAFETY STOP: "
            "writer became connected during permit issuance."
        )

    permit = (
        permit_package[
            "permit"
        ]
    )

    ledger_record = {
        "event_id":
            event[
                "event_id"
            ],

        "permit_id":
            permit[
                "permit_id"
            ],

        "permit_sha256":
            permit_package[
                "permit_sha256"
            ],

        "source_compiler_sha256":
            event[
                "compiler_sha256"
            ],

        "issued_utc":
            permit[
                "permit_issued_utc"
            ],
    }

    next_ledger = (
        append_ledger_record(
            ledger_package=
                issue_ledger,

            record=
                ledger_record,
        )
    )

    # Fail-safe write order:
    #
    # 1. ledger first
    # 2. permit second
    #
    # A crash between the two blocks duplicate issuance rather
    # than allowing the same event to be issued twice.
    atomic_write_json(
        ISSUE_LEDGER_PATH,
        next_ledger,
    )

    atomic_write_json(
        PERMIT_PATH,
        permit_package,
    )

    print(
        "\n============================================"
    )

    print(
        "REAL V2 PERMIT ISSUED"
    )

    print(
        "============================================"
    )

    print(
        f"\nPermit ID: "
        f"{permit['permit_id']}"
    )

    print(
        f"Permit SHA256: "
        f"{permit_package['permit_sha256']}"
    )

    print(
        f"Event ID: "
        f"{permit['event_id']}"
    )

    print(
        f"Maximum live execution notional: "
        f"${money_string(requested_cap)}"
    )

    print(
        "Permit issued: TRUE"
    )

    print(
        "Writer-compatible schema: TRUE"
    )

    print(
        "Writer connected: FALSE"
    )

    print(
        "Issuer broker writes: NONE"
    )

    print(
        "Orders submitted: 0"
    )

    print(
        "\nREAL V2 PERMIT ISSUER: PASS"
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
            "REAL V2 PERMIT ISSUER: FAILED",
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
