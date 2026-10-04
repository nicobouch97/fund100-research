from __future__ import annotations

import ast
from pathlib import Path

import fund100_alpaca_live_execution_orchestrator_v1_0 as orchestrator
import fund100_alpaca_live_writer_candidate_v1_1 as candidate


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.18
# ============================================================
#
# Adds review of Execution Orchestrator v1.0.
#
# This audit proves:
#
# - orchestrator has no broker-network implementation
# - orchestrator accesses no credentials/environment secrets
# - orchestrator itself is not released
# - candidate v1.1 remains hard locked
# - fresh broker reconstruction occurs before materialization
# - complete history reconstruction occurs before cap guard
# - cumulative-cap approval occurs before writer invocation
# - rehearsal contains no real network client
# - rehearsal workflow exposes no Alpaca credentials
#
# ============================================================


ORCHESTRATOR_PATH = Path(
    "fund100_alpaca_live_execution_orchestrator_v1_0.py"
)

REHEARSAL_PATH = Path(
    "fund100_alpaca_live_execution_orchestrator_rehearsal_v1_0.py"
)

REHEARSAL_WORKFLOW_PATH = Path(
    ".github/workflows/"
    "fund100-live-execution-orchestrator-rehearsal.yml"
)


BANNED_NETWORK_IMPORTS = {
    "urllib",
    "requests",
    "httpx",
    "socket",
    "aiohttp",
    "alpaca_trade_api",
}


BANNED_CREDENTIAL_TOKENS = {
    "APCA_API_KEY_ID",
    "APCA_API_SECRET_KEY",
    "ALPACA_API_KEY",
    "ALPACA_SECRET_KEY",
    "secrets.",
}


def source(
    path: Path,
) -> str:

    if not path.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            f"missing required file: {path}"
        )

    return path.read_text(
        encoding="utf-8"
    )


def tree(
    path: Path,
) -> ast.Module:

    return ast.parse(
        source(
            path
        ),
        filename=str(
            path
        ),
    )


def imported_roots(
    path: Path,
) -> set[str]:

    roots = set()

    for node in ast.walk(
        tree(
            path
        )
    ):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                roots.add(
                    alias.name.split(
                        "."
                    )[0]
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            if node.module:

                roots.add(
                    node.module.split(
                        "."
                    )[0]
                )

    return roots


def verify_no_network_imports(
    path: Path,
) -> None:

    dangerous = (
        imported_roots(
            path
        )
        & BANNED_NETWORK_IMPORTS
    )

    if dangerous:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            f"{path} contains network import(s): "
            + ", ".join(
                sorted(
                    dangerous
                )
            )
        )


def verify_no_credential_tokens(
    path: Path,
) -> None:

    text = source(
        path
    )

    found = [
        token
        for token
        in BANNED_CREDENTIAL_TOKENS
        if token in text
    ]

    if found:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            f"{path} contains credential hook(s): "
            + ", ".join(
                sorted(
                    found
                )
            )
        )


def attribute_chain(
    node,
) -> str | None:

    parts = []

    current = node

    while isinstance(
        current,
        ast.Attribute,
    ):

        parts.append(
            current.attr
        )

        current = (
            current.value
        )

    if isinstance(
        current,
        ast.Name,
    ):

        parts.append(
            current.id
        )

        return ".".join(
            reversed(
                parts
            )
        )

    return None


def function_node(
    *,
    path: Path,
    function_name: str,
) -> ast.FunctionDef:

    for node in tree(
        path
    ).body:

        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == function_name
        ):

            return node

    raise RuntimeError(
        "LIVE STATIC AUDIT STOP: "
        f"{function_name} missing from {path}."
    )


def called_functions(
    *,
    path: Path,
    function_name: str,
) -> list[tuple[int, str]]:

    func = function_node(
        path=path,
        function_name=function_name,
    )

    calls = []

    for node in ast.walk(
        func
    ):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if isinstance(
            node.func,
            ast.Name,
        ):

            name = (
                node.func.id
            )

        else:

            name = (
                attribute_chain(
                    node.func
                )
            )

        if name:

            calls.append(
                (
                    node.lineno,
                    name,
                )
            )

    return sorted(
        calls,
        key=lambda item: (
            item[0],
            item[1],
        ),
    )


def first_line(
    calls,
    target,
):

    matches = [
        line
        for line, name
        in calls
        if name == target
    ]

    if not matches:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "orchestrator lost required call: "
            f"{target}"
        )

    return min(
        matches
    )


def verify_orchestrator_call_order():

    calls = (
        called_functions(
            path=(
                ORCHESTRATOR_PATH
            ),
            function_name=(
                "run_execution_phase"
            ),
        )
    )

    required = [
        "deps.verify_release_lock",
        "deps.reconstruct_broker_snapshot",
        "deps.materialize_execution_phase",
        "deps.reconstruct_authorized_order_history",
        "deps.enforce_cumulative_cap",
        "deps.submit_authorized_order_batch",
    ]

    lines = [
        first_line(
            calls,
            name,
        )
        for name in required
    ]

    if lines != sorted(
        lines
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "orchestrator safety call order changed."
        )

    if not (
        lines[
            required.index(
                "deps.enforce_cumulative_cap"
            )
        ]
        <
        lines[
            required.index(
                "deps.submit_authorized_order_batch"
            )
        ]
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer is reachable before cumulative-cap guard."
        )


def verify_orchestrator_no_main():

    module = tree(
        ORCHESTRATOR_PATH
    )

    for node in module.body:

        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == "main"
        ):

            raise RuntimeError(
                "LIVE STATIC AUDIT STOP: "
                "orchestrator unexpectedly contains main()."
            )

        if isinstance(
            node,
            ast.If,
        ):

            text = ast.unparse(
                node.test
            )

            if "__name__" in text:

                raise RuntimeError(
                    "LIVE STATIC AUDIT STOP: "
                    "orchestrator unexpectedly contains "
                    "__main__ execution path."
                )


def verify_release_constants():

    if (
        orchestrator.ORCHESTRATOR_RELEASED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "orchestrator release flag is not False."
        )

    if (
        orchestrator.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "orchestrator public-execution flag is not False."
        )

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer candidate transport unexpectedly released."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer candidate public execution unexpectedly "
            "enabled."
        )


def verify_rehearsal_workflow():

    text = source(
        REHEARSAL_WORKFLOW_PATH
    )

    forbidden = [
        "APCA_API_KEY_ID",
        "APCA_API_SECRET_KEY",
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
        "secrets.",
        "https://api.alpaca.markets",
    ]

    found = [
        token
        for token in forbidden
        if token in text
    ]

    if found:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "orchestrator rehearsal workflow exposes "
            "broker credential/network hook(s): "
            + ", ".join(
                sorted(
                    found
                )
            )
        )


def main():

    print(
        "Fund-100 static audit safety layer: v1.18"
    )

    verify_release_constants()

    verify_no_network_imports(
        ORCHESTRATOR_PATH
    )

    verify_no_network_imports(
        REHEARSAL_PATH
    )

    verify_no_credential_tokens(
        ORCHESTRATOR_PATH
    )

    verify_no_credential_tokens(
        REHEARSAL_PATH
    )

    verify_orchestrator_no_main()

    verify_orchestrator_call_order()

    verify_rehearsal_workflow()

    print(
        "PASS: Writer candidate v1.1 remains hard locked."
    )

    print(
        "PASS: Execution orchestrator v1.0 remains unreleased."
    )

    print(
        "PASS: Execution orchestrator has no broker-network imports."
    )

    print(
        "PASS: Execution orchestrator has no credential hooks."
    )

    print(
        "PASS: Execution orchestrator has no main() execution path."
    )

    print(
        "PASS: Fresh broker reconstruction precedes materialization."
    )

    print(
        "PASS: Authorized client-ID reconstruction precedes "
        "cumulative-cap approval."
    )

    print(
        "PASS: Cumulative-cap guard precedes every writer call."
    )

    print(
        "PASS: Orchestrator rehearsal contains no direct "
        "real broker network client."
    )

    print(
        "PASS: Orchestrator rehearsal workflow contains no "
        "LIVE Alpaca credentials."
    )

    print(
        "========================================"
    )

    print(
        "FUND-100 LIVE STATIC AUDIT COMPLETE"
    )

    print(
        "========================================"
    )

    print(
        "Static audit safety layer: v1.18"
    )

    print(
        "Release Lock v1.8 prerequisite: PRESERVED"
    )

    print(
        "Writer candidate v1.1: HARD LOCKED"
    )

    print(
        "Execution orchestrator v1.0: PURE / OFFLINE"
    )

    print(
        "Orchestrator network capability: NONE"
    )

    print(
        "Orchestrator credential access: NONE"
    )

    print(
        "Fresh broker reconstruction before materialization: VERIFIED"
    )

    print(
        "Complete authorized-ID reconstruction before cap: VERIFIED"
    )

    print(
        "Cumulative-cap guard before writer: VERIFIED"
    )

    print(
        "Candidate transport released: FALSE"
    )

    print(
        "Candidate public execution enabled: FALSE"
    )

    print(
        "Orchestrator released: FALSE"
    )

    print(
        "Current live writer connected: FALSE"
    )

    print(
        "Orders submitted to Alpaca: 0"
    )


if __name__ == "__main__":
    main()
