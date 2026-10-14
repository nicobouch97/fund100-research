"""Scheduled genuine V5-002 strategy -> Alpaca PAPER-only execution runner.

NO simulated events. No LIVE credentials or endpoints. The persisted shadow
strategy must have a genuine SCHEDULED pending target, and this run must be
its immediate next US trading session in the frozen near-close window.
Otherwise no trade is placed. Broker-restricted writes are delegated solely
to the reviewed PAPER adapter / two-phase bridge.

Only safe summary fields are printed; no balances, prices, orders or IDs.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import date, datetime, timezone
from pathlib import Path

import fund100_alpaca_paper_orchestrator_connected_v1_0 as paper_api
import fund100_v5_paper_broker_adapter_v1_0 as paper_adapter
import fund100_v5_paper_native_compiler_v1_0 as native
import fund100_v5_paper_execution_bridge_v1_0 as bridge
import fund100_v5_compiler_attestation_v1_0 as attestation

SHADOW_PATH = Path("shadow_outputs/v5_002/shadow_state.json")
POLICY_PATH = Path("live_activation_outputs/v5_002/live_micro_pilot_policy_v1_0.json")


class PaperRunnerStop(RuntimeError):
    pass


def validated_configuration(policy: object, *, risk_level: str) -> tuple[set[str], str]:
    """Enforce existing LIVE pilot's ceiling without ever reading LIVE keys."""
    if (
        not isinstance(policy, dict)
        or policy.get("deployment_mode") != "LIVE_MICRO_PILOT"
        or policy.get("strategy") != "V5-002_SHADOW"
        or policy.get("capital_ceiling_usd") != "130.30"
        or policy.get("crypto_allowed") is not False
        or policy.get("leverage_allowed") is not False
        or policy.get("shorting_allowed") is not False
    ):
        raise PaperRunnerStop("Frozen V5 micro-pilot policy mismatch.")
    universe = policy.get("execution_universe")
    if (
        not isinstance(universe, list)
        or len(universe) != 14
        or set(universe) != paper_adapter.FROZEN_V5_ETFS
    ):
        raise PaperRunnerStop("PAPER strategy ETF universe mismatch.")
    if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
        raise PaperRunnerStop("Risk profile must be LOW, MEDIUM or HIGH.")
    return set(universe), policy["capital_ceiling_usd"]


def run_once(*, state: dict, policy: dict, risk_level: str,
             broker=None, paper_api_client=None, data_source=None,
             written_ns: int | None = None,
             clock_reference_utc: datetime | None = None) -> dict:
    """Execute only if native compiler produces a genuine strategy signal.

    Optional injected dependencies support tests without any API calls.
    """
    universe, ceiling = validated_configuration(policy, risk_level=risk_level)

    # First examine the actual frozen strategy state, not a test event.
    # An ordinary day needs no credentials, account snapshot or market data.
    if state.get("pending_source") is None and state.get("pending_target") is None:
        package, manifest = native.build_paper_compiler(state=state)
        proof = attestation.attest_compiler_event(
            compiler_package=package, manifest_package=manifest,
            shadow_state=state,
            compiler_written_ns=time.time_ns(),
            now_ns=time.time_ns(),
        )
        if proof["genuine_event"] is not False:
            raise PaperRunnerStop("No-event path changed unexpectedly.")
        return {
            "status": "NO_GENUINE_STRATEGY_EVENT",
            "paper_post_count": 0, "live_post_count": 0,
            "paper_execution_attempted": False,
        }

    if broker is None:
        broker = paper_adapter.AlpacaPaperOnlyAdapter(approved_symbols=universe)
    if paper_api_client is None:
        paper_api_client = paper_api
    if data_source is None:
        data_source = native.frozen

    # Every external call is PAPER/market-data GET until the final
    # bridge has attested, sized and reconciled this same-run event.
    broker.require_paper_only_arm()
    clock = paper_api_client.get_clock()
    if not isinstance(clock, dict) or clock.get("is_open") is not True:
        raise PaperRunnerStop("PAPER market is not open.")
    current_time = native.frozen.parse_timestamp(clock.get("timestamp", ""))
    if current_time.tzinfo is None:
        raise PaperRunnerStop("Broker PAPER clock must be timezone aware.")
    wall_time = clock_reference_utc or datetime.now(timezone.utc)
    if wall_time.tzinfo is None or abs(
        (wall_time - current_time).total_seconds()
    ) > 120:
        raise PaperRunnerStop("PAPER exchange clock is stale or in the future.")
    day = current_time.date()
    start = date.fromisoformat(state["last_date"])
    calendar = paper_api_client.paper_request(
        method="GET",
        path=(
            "/v2/calendar?start=" + start.isoformat()
            + "&end=" + day.isoformat()
        ),
    )
    snapshot = broker.snapshot()
    if not isinstance(snapshot, dict):
        raise PaperRunnerStop("PAPER account state unavailable.")

    key, secret = (
        os.environ.get("ALPACA_PAPER_KEY"),
        os.environ.get("ALPACA_PAPER_SECRET"),
    )
    if not key or not secret:
        raise PaperRunnerStop("PAPER-only market-data credentials missing.")
    closes = data_source.load_signal_closes(
        signal_date=state["last_date"], key=key, secret=secret
    )
    latest = data_source.load_latest_bars(
        clock=clock, key=key, secret=secret
    )

    package, manifest = native.build_paper_compiler(
        state=state, paper_snapshot=snapshot,
        paper_clock=clock, paper_calendar=calendar,
        signal_closes=closes, latest_bars=latest,
    )
    created_ns = time.time_ns() if written_ns is None else written_ns
    now_ns = time.time_ns()
    proof = attestation.attest_compiler_event(
        compiler_package=package, manifest_package=manifest,
        shadow_state=state, compiler_written_ns=created_ns,
        now_ns=now_ns,
    )
    if proof.get("status") != "FRESH_GENUINE_COMPILER_EVENT":
        raise PaperRunnerStop("PAPER source was not a fresh genuine event.")

    result = bridge.execute_attested_paper_event(
        compiler_package=package, manifest_package=manifest,
        shadow_state=state, compiler_written_ns=created_ns,
        now_ns=time.time_ns(),
        broker=broker, execution_universe=universe,
        capital_ceiling=ceiling, risk_level=risk_level,
    )
    if result.get("live_post_count") != 0:
        raise PaperRunnerStop("Unexpected LIVE execution outcome.")
    # Only sanitized information leaves the broker runner.
    return {
        "status": result["status"],
        "paper_post_count": result["paper_post_count"],
        "live_post_count": 0,
        "paper_execution_attempted": True,
        "risk_level": risk_level,
        "reconciled": result.get("reconciled", False),
    }


def verify_github_runner() -> None:
    if (
        os.environ.get("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or os.environ.get("GITHUB_REF") != "refs/heads/main"
        or os.environ.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or os.environ.get("FUND100_GENUINE_PAPER_ARM")
        != paper_adapter.AlpacaPaperOnlyAdapter.ARM_VALUE
        or os.environ.get("ALPACA_LIVE_KEY")
        or os.environ.get("ALPACA_LIVE_SECRET")
    ):
        raise PaperRunnerStop("Unexpected PAPER workflow/repository boundary.")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    if not head or head != os.environ.get("GITHUB_SHA"):
        raise PaperRunnerStop("Workflow source is not the exact checkout commit.")


def main() -> None:
    verify_github_runner()
    try:
        state = json.loads(SHADOW_PATH.read_text(encoding="utf-8"))
        policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PaperRunnerStop("Frozen strategy/policy file missing.") from exc
    report = run_once(
        state=state, policy=policy,
        risk_level=os.environ.get("FUND100_RISK_LEVEL", ""),
    )
    print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
