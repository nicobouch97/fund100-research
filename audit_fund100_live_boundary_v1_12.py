from __future__ import annotations

import ast
import inspect
from pathlib import Path

import audit_fund100_live_boundary_v1_11 as v111

import fund100_alpaca_live_writer_candidate_v1_0 as candidate
import fund100_alpaca_live_writer_transport_rehearsal_v1_0 as rehearsal


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.12
# ============================================================
#
# Adds one explicit offline exception:
#
#   fund100_alpaca_live_writer_transport_rehearsal_v1_0.py
#
# may import and exercise the connected-writer candidate ONLY
# through fake in-memory transport.
#
# The dedicated workflow:
#
# - supplies NO Alpaca credentials
# - contains NO LIVE secrets
# - does NOT import the candidate directly
# - runs the offline rehearsal module
#
# All ordinary workflows remain prohibited from invoking or
# importing the writer candidate directly.
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


REHEARSAL_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_transport_rehearsal_v1_0.py"
)


WORKFLOW_PATH = (
    ROOT
    / ".github"
    / "workflows"
    / "fund100-live-writer-transport-rehearsal.yml"
)


# ============================================================
# IMPORT INSPECTION
# ============================================================


def imported_modules(
    source: str,
):

    tree = ast.parse(
        source
    )

    result = []

    for node in ast.walk(
        tree
    ):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                result.append(
                    alias.name
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            result.append(
                str(
                    node.module
                    or ""
                )
            )

    return set(
        result
    )


# ============================================================
# REHEARSAL AUDIT
# ============================================================


def verify_offline_transport_rehearsal():

    source = (
        inspect.getsource(
            rehearsal
        )
    )

    imports = (
        imported_modules(
            source
        )
    )

    if (
        "fund100_alpaca_live_writer_candidate_v1_0"
        not in imports
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "offline transport rehearsal does not "
            "exercise the reviewed writer candidate."
        )

    forbidden_network_modules = {
        "requests",
        "httpx",
        "socket",
        "aiohttp",
    }

    bad_imports = (
        imports
        & forbidden_network_modules
    )

    if bad_imports:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "offline rehearsal imports external "
            "network modules: "
            + ", ".join(
                sorted(
                    bad_imports
                )
            )
        )

    if (
        "urllib.request"
        in imports
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "offline rehearsal imports urllib.request."
        )

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate transport is released."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate public execution is enabled."
        )

    print(
        "PASS: Offline transport rehearsal imports "
        "the reviewed candidate."
    )

    print(
        "PASS: Offline rehearsal imports no real "
        "network client."
    )

    print(
        "PASS: Candidate transport remains hard-coded FALSE."
    )

    print(
        "PASS: Candidate public execution remains "
        "hard-coded FALSE."
    )


# ============================================================
# WORKFLOW AUDIT
# ============================================================


def verify_offline_rehearsal_workflow():

    if not WORKFLOW_PATH.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "offline transport rehearsal workflow missing."
        )

    source = (
        WORKFLOW_PATH.read_text(
            encoding="utf-8"
        )
    )

    forbidden_tokens = [
        "${{ secrets.",
        "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET",
        "FUND100_ENABLE_LIVE",
        "FUND100_LIVE_WRITE_MODE",
        "FUND100_LIVE_APPROVAL_TOKEN",
        "FUND100_LIVE_HARD_CAP_USD",
    ]

    detected = [
        token
        for token
        in forbidden_tokens
        if token
        in source
    ]

    if detected:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "offline rehearsal workflow contains "
            "credential/activation material: "
            + ", ".join(
                detected
            )
        )

    direct_candidate_tokens = [
        "python fund100_alpaca_live_writer_candidate_v1_0.py",
        "python3 fund100_alpaca_live_writer_candidate_v1_0.py",
        "import fund100_alpaca_live_writer_candidate_v1_0",
        "from fund100_alpaca_live_writer_candidate_v1_0 import",
    ]

    direct_hits = [
        token
        for token
        in direct_candidate_tokens
        if token
        in source
    ]

    if direct_hits:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "offline workflow accesses writer candidate "
            "directly instead of through rehearsal harness."
        )

    expected_command = (
        "python "
        "fund100_alpaca_live_writer_transport_rehearsal_v1_0.py"
    )

    if (
        expected_command
        not in source
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "offline rehearsal workflow does not execute "
            "the reviewed rehearsal harness."
        )

    print(
        "PASS: Dedicated transport-rehearsal workflow exists."
    )

    print(
        "PASS: Rehearsal workflow contains no Alpaca secrets."
    )

    print(
        "PASS: Rehearsal workflow contains no LIVE "
        "activation variables."
    )

    print(
        "PASS: Rehearsal workflow does not invoke "
        "writer candidate directly."
    )

    print(
        "PASS: Rehearsal workflow executes only the "
        "reviewed offline harness."
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "Fund-100 static audit safety layer: v1.12"
    )

    verify_offline_transport_rehearsal()

    verify_offline_rehearsal_workflow()

    v111.main()


if __name__ == "__main__":

    main()
