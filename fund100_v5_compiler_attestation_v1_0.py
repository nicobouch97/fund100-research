"""Fail-closed freshness/provenance evidence for V5-002 genuine signals.

READ-ONLY. Never accesses credentials, the broker, a live order endpoint
or any order writer. Proves internal hash/manifest consistency and
recentness, not independently the honesty of the source system.
Only valid for a genuine v1.1 CURRENT event. No-event is not an error
and must never be converted into an order.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import fund100_live_production_controller_v1_0 as production

COMPILER_PATH = Path(
    "live_dryrun_outputs/v5_002/scheduled_execution_time.json"
)
MANIFEST_PATH = Path(
    "live_dryrun_outputs/v5_002/live_execution_manifest.json"
)
SHADOW_STATE_PATH = Path(
    "shadow_outputs/v5_002/shadow_state.json"
)
MAX_SIGNAL_AGE_SECONDS = 600
MAX_CLOCK_LEAD_SECONDS = 3
MINUTES_TO_CLOSE_MIN = 5
MINUTES_TO_CLOSE_MAX = 45


class CompilerAttestationStop(RuntimeError):
    """Compiler event has no supported trusted/fresh execution evidence."""


def require_mapping(value, label: str) -> dict:
    if not isinstance(value, dict):
        raise CompilerAttestationStop("Missing/malformed " + label)
    return value


def require_digest(value, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise CompilerAttestationStop("Missing " + label + " SHA256 digest.")
    if any(ch not in "0123456789abcdef" for ch in value):
        raise CompilerAttestationStop("Malformed " + label + " SHA256 digest.")
    return value


def attest_compiler_event(
    *, compiler_package: dict, manifest_package: dict, shadow_state: dict,
    compiler_written_ns: int, now_ns: int,
) -> dict:
    """Validate a separately supplied compiler package and local source chain.

    In a real workflow the caller must additionally guarantee that file
    metadata comes from the very compiler invocation being attested,
    not an old artifact whose filesystem timestamp was refreshed.
    """
    compiler_package = require_mapping(compiler_package, "compiler package")
    manifest_package = require_mapping(manifest_package, "manifest package")
    shadow_state = require_mapping(shadow_state, "shadow strategy state")

    if type(compiler_written_ns) is not int or type(now_ns) is not int:
        raise CompilerAttestationStop("Invalid compiler file timestamps.")
    if compiler_written_ns <= 0 or now_ns <= 0:
        raise CompilerAttestationStop("Invalid compiler clock.")
    age_ns = now_ns - compiler_written_ns
    if age_ns < -MAX_CLOCK_LEAD_SECONDS * 10**9:
        raise CompilerAttestationStop("Compiler artifact has a future timestamp.")
    if age_ns > MAX_SIGNAL_AGE_SECONDS * 10**9:
        raise CompilerAttestationStop("Compiler artifact is too old.")

    compiler_body = require_mapping(
        compiler_package.get("compiler"), "compiler body"
    )
    compiler_sha = require_digest(
        compiler_package.get("compiler_sha256"), "compiler"
    )
    if compiler_sha != production.canonical_sha256(compiler_body):
        raise CompilerAttestationStop("Compiler body SHA256 mismatch.")

    try:
        event = production.extract_compiler_view(
            compiler_body, compiler_sha256=compiler_sha,
        )
    except production.ProductionStop as exc:
        raise CompilerAttestationStop("Compiler event contract failed.") from exc

    if not event["genuine"]:
        if event["status"] != "NO_SCHEDULED_EVENT":
            raise CompilerAttestationStop("Non-genuine event status ambiguous.")
        return {
            "status": "NO_GENUINE_EVENT",
            "genuine_event": False,
            "compiler_sha256": compiler_sha,
            "event_sha256": None,
            "freshness_seconds": round(age_ns / 10**9, 3),
        }

    manifest_body = require_mapping(
        manifest_package.get("manifest"), "source manifest"
    )
    manifest_sha = require_digest(
        manifest_package.get("manifest_sha256"), "source manifest"
    )
    if manifest_sha != production.canonical_sha256(manifest_body):
        raise CompilerAttestationStop("Source manifest SHA256 mismatch.")
    if (
        compiler_body.get("source_manifest_sha256") != manifest_sha
        or compiler_body.get("source_manifest_id")
        != manifest_package.get("manifest_id")
    ):
        raise CompilerAttestationStop("Compiler/manifest source mismatch.")

    if (
        manifest_body.get("strategy") != "V5-002_SHADOW"
        or manifest_body.get("manifest_type") != "PENDING_STRATEGY_EVENT"
        or manifest_body.get("event_source") != "SCHEDULED"
        or manifest_body.get("strategy_event_present") is not True
    ):
        raise CompilerAttestationStop("No genuine SCHEDULED manifest event.")

    state_sha = production.canonical_sha256(shadow_state)
    if (
        shadow_state.get("strategy") != "V5-002_SHADOW"
        or manifest_body.get("strategy_state_sha256") != state_sha
        or compiler_body.get("strategy_state_sha256") != state_sha
    ):
        raise CompilerAttestationStop("Strategy state/manifest SHA256 mismatch.")
    state_date = shadow_state.get("last_date")
    if (
        not isinstance(state_date, str)
        or compiler_body.get("strategy_state_date") != state_date
        or manifest_body.get("strategy_state_date") != state_date
    ):
        raise CompilerAttestationStop("Compiler strategy-date mismatch.")

    if (
        compiler_body.get("execution_window_eligible") is not True
        or compiler_body.get("market_data_feed") != "iex"
        or compiler_body.get("broker_delta_source")
        != "FRESH_EPHEMERAL_RECONCILIATION"
    ):
        raise CompilerAttestationStop("No fresh market/session reconciliation.")
    mins = compiler_body.get("minutes_to_close")
    if type(mins) not in (int, float) or not (
        MINUTES_TO_CLOSE_MIN <= mins <= MINUTES_TO_CLOSE_MAX
    ):
        raise CompilerAttestationStop("Compiler outside near-close window.")
    if not isinstance(compiler_body.get("market_snapshot_sha256"), str):
        raise CompilerAttestationStop("Missing market snapshot hash.")
    if require_digest(
        compiler_body.get("market_snapshot_sha256"), "market snapshot"
    ) != production.canonical_sha256(
        require_mapping(compiler_body.get("market_snapshot"), "market snapshot")
    ):
        raise CompilerAttestationStop("Market snapshot SHA256 mismatch.")

    # Compiler is a signal source ONLY: absolutely no write grants.
    if (
        compiler_body.get("live_execution_authorized") is not False
        or compiler_body.get("network_write_capability") is not False
        or compiler_body.get("broker_write_mode") != "DISABLED"
        or compiler_body.get("orders_submitted") != 0
        or str(compiler_body.get("max_live_execution_notional_usd"))
        not in {"0.0", "0", "0.00"}
    ):
        raise CompilerAttestationStop("Compiler source unexpectedly executable.")
    if (
        compiler_body.get("broker_current_weights_persisted") is not False
        or compiler_body.get("broker_dollar_values_persisted") is not False
    ):
        raise CompilerAttestationStop("Compiler has persisted broker values.")
    if not event["candidates"]:
        return {
            "status": "GENUINE_NO_BROKER_CANDIDATES",
            "genuine_event": True,
            "compiler_sha256": compiler_sha,
            "event_sha256": event["event_sha256"],
            "freshness_seconds": round(age_ns / 10**9, 3),
        }

    # The compiler's stored candidate client IDs are from LIVE broker
    # reconciliation and MUST NOT be reused as PAPER broker orders.
    production.extract_target_weights(compiler_body)
    return {
        "status": "FRESH_GENUINE_COMPILER_EVENT",
        "genuine_event": True,
        "compiler_sha256": compiler_sha,
        "event_sha256": event["event_sha256"],
        "freshness_seconds": round(age_ns / 10**9, 3),
        "compiler_candidate_count": len(event["candidates"]),
    }


def attest_current_files(
    *, compiler_path: Path = COMPILER_PATH,
    manifest_path: Path = MANIFEST_PATH,
    state_path: Path = SHADOW_STATE_PATH,
    invocation_started_ns: int | None = None,
) -> dict:
    """Use EXACT compiler output and demand creation AFTER invoking compiler."""
    if invocation_started_ns is None:
        raise CompilerAttestationStop(
            "Compiler invocation start timestamp is mandatory."
        )
    if type(invocation_started_ns) is not int or invocation_started_ns <= 0:
        raise CompilerAttestationStop("Compiler invocation start is invalid.")
    try:
        stat = compiler_path.stat()
        compiler_package = json.loads(compiler_path.read_text(encoding="utf-8"))
        manifest_package = json.loads(manifest_path.read_text(encoding="utf-8"))
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CompilerAttestationStop("Required current compiler files unavailable.") from exc

    if stat.st_mtime_ns < invocation_started_ns:
        raise CompilerAttestationStop(
            "Compiler output predates THIS compiler invocation."
        )
    return attest_compiler_event(
        compiler_package=compiler_package,
        manifest_package=manifest_package,
        shadow_state=state,
        compiler_written_ns=stat.st_mtime_ns,
        now_ns=time.time_ns(),
    )
