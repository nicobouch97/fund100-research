from __future__ import annotations

import ast
from pathlib import Path

import audit_fund100_live_boundary_v1_14 as v114

import fund100_alpaca_live_writer_candidate_v1_1 as candidate


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.15
# ============================================================
#
# Adds review of the dedicated v1.1 status/restart rehearsal.
#
# The rehearsal must:
#
# - import candidate v1.1
# - contain no direct real network client
# - contain no broker credential hooks
# - contain no environment activation
# - patch candidate.urlopen before guard bypass
# - run only through its dedicated credential-free workflow
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


REHEARSAL_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_status_rehearsal_v1_0.py"
)


TEST_PATH = (
    ROOT
    / "test_fund100_alpaca_live_writer_status_rehearsal_v1_0.py"
)


WORKFLOW_PATH = (
    ROOT
    / ".github"
    / "workflows"
    / "fund100-live-writer-status-rehearsal.yml"
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


def verify_status_rehearsal_source():

    if not REHEARSAL_PATH.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "status rehearsal source missing."
        )

    if not TEST_PATH.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "status rehearsal tests missing."
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
    }

    detected = (
        prohibited_network_modules
        .intersection(
            modules
        )
    )

    if detected:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "status rehearsal imports direct "
            "network client(s): "
            + ", ".join(
                sorted(
                    detected
                )
            )
        )

    prohibited_tokens = [
        "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET",
        "ALPACA_PAPER_KEY",
        "ALPACA_PAPER_SECRET",
    ]

    hits = [
        token
        for token
        in prohibited_tokens
        if token in source
    ]

    if hits:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "status rehearsal contains broker "
            "credential hook(s): "
            + ", ".join(
                hits
            )
        )

    if (
        "import fund100_alpaca_live_writer_candidate_v1_1 "
        "as candidate"
        not in source
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "status rehearsal does not use "
            "writer candidate v1.1."
        )

    transport_patch = (
        source.find(
            "candidate.urlopen = ("
        )
    )

    transport_guard_patch = (
        source.find(
            "candidate.require_transport_released = ("
        )
    )

    public_guard_patch = (
        source.find(
            "candidate.require_public_execution_released = ("
        )
    )

    if (
        transport_patch
        < 0
        or
        transport_guard_patch
        < 0
        or
        public_guard_patch
        < 0
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "offline transport patch sequence missing."
        )

    if not (
        transport_patch
        <
        transport_guard_patch
        <
        public_guard_patch
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "fake transport is not installed "
            "before release-guard bypass."
        )

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate v1.1 transport released."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate v1.1 public execution enabled."
        )

    print(
        "PASS: Status rehearsal imports candidate v1.1."
    )

    print(
        "PASS: Status rehearsal imports no direct "
        "real network client."
    )

    print(
        "PASS: Status rehearsal contains no broker "
        "credential hook."
    )

    print(
        "PASS: Fake transport is installed before "
        "release-guard bypass."
    )

    print(
        "PASS: Candidate v1.1 remains hard locked."
    )


def verify_status_rehearsal_workflow():

    if not WORKFLOW_PATH.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "status rehearsal workflow missing."
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
            "status rehearsal workflow contains "
            "prohibited material: "
            + ", ".join(
                hits
            )
        )

    required = [
        "python fund100_alpaca_live_writer_status_rehearsal_v1_0.py",
        "python audit_fund100_live_boundary_v1_15.py",
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
            "status rehearsal workflow missing "
            "required command(s): "
            + ", ".join(
                missing
            )
        )

    print(
        "PASS: Dedicated status-rehearsal workflow exists."
    )

    print(
        "PASS: Status-rehearsal workflow contains "
        "no Alpaca credentials."
    )

    print(
        "PASS: Status-rehearsal workflow contains "
        "no LIVE activation variables."
    )

    print(
        "PASS: Workflow invokes only the reviewed "
        "status rehearsal, not candidate v1.1 directly."
    )


def main():

    print(
        "Fund-100 static audit safety layer: v1.15"
    )

    verify_status_rehearsal_source()

    verify_status_rehearsal_workflow()

    v114.main()


if __name__ == "__main__":

    main()
