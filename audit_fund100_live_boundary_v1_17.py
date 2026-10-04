from __future__ import annotations

import ast
from pathlib import Path

import audit_fund100_live_boundary_v1_16 as v116

import fund100_alpaca_live_cumulative_cap_guard_v1_0 as cap_guard
import fund100_alpaca_live_writer_candidate_v1_1 as candidate


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.17
# ============================================================
#
# Adds review of the completely-offline cumulative-cap /
# restart rehearsal.
#
# The rehearsal may exercise candidate v1.1 only through the
# previously reviewed in-memory fake broker transport.
#
# NO credentials.
# NO direct network client.
# NO LIVE workflow activation.
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


REHEARSAL_PATH = (
    ROOT
    / "fund100_alpaca_live_cumulative_cap_rehearsal_v1_0.py"
)


TEST_PATH = (
    ROOT
    / "test_fund100_alpaca_live_cumulative_cap_rehearsal_v1_0.py"
)


WORKFLOW_PATH = (
    ROOT
    / ".github"
    / "workflows"
    / "fund100-live-cumulative-cap-rehearsal.yml"
)


def imported_modules(
    source: str,
):

    tree = ast.parse(
        source
    )

    result = set()

    for node in ast.walk(
        tree
    ):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                result.add(
                    alias.name
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            if node.module:

                result.add(
                    node.module
                )

    return result


def verify_cumulative_cap_rehearsal_source():

    if not REHEARSAL_PATH.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal source missing."
        )

    if not TEST_PATH.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal tests missing."
        )

    source = (
        REHEARSAL_PATH.read_text(
            encoding="utf-8"
        )
    )

    modules = (
        imported_modules(
            source
        )
    )

    prohibited_network_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "socket",
        "urllib.request",
        "urllib3",
    }

    hits = (
        prohibited_network_modules
        .intersection(
            modules
        )
    )

    if hits:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal imports "
            "direct network client(s): "
            + ", ".join(
                sorted(
                    hits
                )
            )
        )

    prohibited_runtime_modules = {
        "os",
        "subprocess",
    }

    runtime_hits = (
        prohibited_runtime_modules
        .intersection(
            modules
        )
    )

    if runtime_hits:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal imports "
            "runtime activation module(s): "
            + ", ".join(
                sorted(
                    runtime_hits
                )
            )
        )

    prohibited_tokens = [
        "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET",
        "ALPACA_PAPER_KEY",
        "ALPACA_PAPER_SECRET",
        "os.environ",
        "getenv(",
        "Request(",
        "urlopen(",
    ]

    token_hits = [
        token
        for token
        in prohibited_tokens
        if token in source
    ]

    if token_hits:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal contains "
            "prohibited network/credential hook(s): "
            + ", ".join(
                token_hits
            )
        )

    required_modules = {
        "fund100_alpaca_live_cumulative_cap_guard_v1_0",
        "fund100_alpaca_live_writer_candidate_v1_1",
        "fund100_alpaca_live_writer_status_rehearsal_v1_0",
    }

    if not (
        required_modules
        .issubset(
            modules
        )
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal dependency "
            "binding is incomplete."
        )

    required_tokens = [
        "status_rehearsal.offline_candidate_transport",
        "cap_guard.evaluate_cumulative_cap",
        "cap_guard.reconstruct_consumed_state",
        "lookup_all_authorized",
        "submit_phase",
        "40.01",
        "partially_filled",
        "canceled",
        "expired",
        "rejected",
        "lose_first_post_response",
    ]

    missing = [
        token
        for token
        in required_tokens
        if token not in source
    ]

    if missing:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal lost "
            "required scenario/control(s): "
            + ", ".join(
                missing
            )
        )

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer candidate transport released."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer candidate public execution enabled."
        )

    if (
        cap_guard.PERSISTENCE_POLICY
        != "EPHEMERAL_DO_NOT_COMMIT"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap guard persistence "
            "policy changed."
        )

    print(
        "PASS: Cumulative-cap rehearsal imports "
        "no direct network client."
    )

    print(
        "PASS: Cumulative-cap rehearsal contains "
        "no broker credential hook."
    )

    print(
        "PASS: Cumulative-cap rehearsal contains "
        "no environment activation hook."
    )

    print(
        "PASS: Rehearsal uses reviewed fake-broker transport."
    )

    print(
        "PASS: SELL/restart/BUY exact-cap scenario present."
    )

    print(
        "PASS: Over-cap-before-writer scenario present."
    )

    print(
        "PASS: Lost-response reconstruction scenario present."
    )

    print(
        "PASS: Partial-fill full-notional scenario present."
    )

    print(
        "PASS: Terminal-failure history scenarios present."
    )

    print(
        "PASS: Writer candidate v1.1 remains hard locked."
    )


def verify_cumulative_cap_rehearsal_workflow():

    if not WORKFLOW_PATH.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal workflow missing."
        )

    source = (
        WORKFLOW_PATH.read_text(
            encoding="utf-8"
        )
    )

    prohibited = [
        "${{ secrets.",
        "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET",
        "ALPACA_PAPER_KEY",
        "ALPACA_PAPER_SECRET",
        "FUND100_LIVE_APPROVAL_TOKEN",
        "FUND100_LIVE_HARD_CAP_USD",
        "FUND100_LIVE_WRITE_MODE: ENABLED",
        "python fund100_alpaca_live_writer_candidate_v1_1.py",
    ]

    hits = [
        token
        for token
        in prohibited
        if token in source
    ]

    if hits:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal workflow "
            "contains prohibited material: "
            + ", ".join(
                hits
            )
        )

    required = [
        "python audit_fund100_live_boundary_v1_17.py",
        "python fund100_alpaca_live_cumulative_cap_rehearsal_v1_0.py",
    ]

    missing = [
        token
        for token
        in required
        if token not in source
    ]

    if missing:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal workflow "
            "missing required command(s): "
            + ", ".join(
                missing
            )
        )

    print(
        "PASS: Dedicated cumulative-cap rehearsal "
        "workflow exists."
    )

    print(
        "PASS: Cumulative-cap rehearsal workflow "
        "contains no Alpaca credentials."
    )

    print(
        "PASS: Cumulative-cap rehearsal workflow "
        "contains no LIVE activation variables."
    )

    print(
        "PASS: Workflow does not invoke "
        "writer candidate v1.1 directly."
    )


def main():

    print(
        "Fund-100 static audit safety layer: v1.17"
    )

    verify_cumulative_cap_rehearsal_source()

    verify_cumulative_cap_rehearsal_workflow()

    v116.main()


if __name__ == "__main__":

    main()
