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
# IMPORTANT
# =========
#
# Function/call verification is AST based.
#
# We deliberately do NOT require exact source formatting such
# as:
#
#     module.function(...)
#
# because valid Python may format the same attribute call as:
#
#     module
#     .function(...)
#
# The AST representation is identical.
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


# ============================================================
# AST HELPERS
# ============================================================


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


def dotted_name(
    node,
):

    if isinstance(
        node,
        ast.Name,
    ):

        return node.id

    if isinstance(
        node,
        ast.Attribute,
    ):

        parent = (
            dotted_name(
                node.value
            )
        )

        if parent:

            return (
                parent
                + "."
                + node.attr
            )

        return node.attr

    return None


def called_functions(
    source: str,
):

    tree = ast.parse(
        source
    )

    result = set()

    for node in ast.walk(
        tree
    ):

        if not isinstance(
            node,
            ast.Call,
        ):

            continue

        name = (
            dotted_name(
                node.func
            )
        )

        if name:

            result.add(
                name
            )

    return result


def defined_functions(
    source: str,
):

    tree = ast.parse(
        source
    )

    return {
        node.name
        for node in ast.walk(
            tree
        )
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        )
    }


# ============================================================
# SOURCE VERIFICATION
# ============================================================


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

    calls = (
        called_functions(
            source
        )
    )

    functions = (
        defined_functions(
            source
        )
    )

    # --------------------------------------------------------
    # NO DIRECT NETWORK CLIENTS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # NO ENVIRONMENT ACTIVATION
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # NO CREDENTIAL / DIRECT NETWORK HOOKS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # EXACT REVIEWED MODULE DEPENDENCIES
    # --------------------------------------------------------

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

        missing_modules = sorted(
            required_modules
            - modules
        )

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal dependency "
            "binding is incomplete: "
            + ", ".join(
                missing_modules
            )
        )

    # --------------------------------------------------------
    # AST-BASED CALL VERIFICATION
    #
    # This replaces the old raw-string requirement for:
    #
    # status_rehearsal.offline_candidate_transport
    #
    # so formatting/line breaks cannot create false failures.
    # --------------------------------------------------------

    required_calls = {
        "status_rehearsal.offline_candidate_transport",
        "candidate._get_order_by_client_id",
        "candidate.submit_authorized_order_batch",
        "cap_guard.evaluate_cumulative_cap",
        "cap_guard.reconstruct_consumed_state",
        "cap_guard.build_authorized_index",
        "lookup_all_authorized",
        "submit_phase",
    }

    missing_calls = sorted(
        required_calls
        - calls
    )

    if missing_calls:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal lost "
            "required executable call(s): "
            + ", ".join(
                missing_calls
            )
        )

    # --------------------------------------------------------
    # REQUIRED REHEARSAL SCENARIOS
    # --------------------------------------------------------

    required_functions = {
        "rehearse_exact_cap_across_phases",
        "rehearse_over_cap_block",
        "rehearse_lost_response_recovery",
        "rehearse_partial_fill_consumption",
        "rehearse_terminal_failure_history",
        "rehearse_unsafe_history",
        "rehearse_incomplete_lookup",
        "rehearse_historical_over_cap",
    }

    missing_functions = sorted(
        required_functions
        - functions
    )

    if missing_functions:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal lost "
            "required scenario function(s): "
            + ", ".join(
                missing_functions
            )
        )

    # --------------------------------------------------------
    # REQUIRED SCENARIO VALUES / STATES
    #
    # These are deliberately simple source-presence checks for
    # the synthetic scenario constants/states themselves.
    # Executable dependency verification above is AST based.
    # --------------------------------------------------------

    required_scenario_tokens = [
        "40.01",
        "partially_filled",
        "canceled",
        "expired",
        "rejected",
        "held",
        "lose_first_post_response",
        "100.01",
    ]

    missing_tokens = [
        token
        for token
        in required_scenario_tokens
        if token not in source
    ]

    if missing_tokens:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap rehearsal lost "
            "required scenario value/state(s): "
            + ", ".join(
                missing_tokens
            )
        )

    # --------------------------------------------------------
    # RELEASE FLAGS MUST STILL BE HARD LOCKED
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # CAP GUARD MUST REMAIN EPHEMERAL
    # --------------------------------------------------------

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
        "PASS: Fake-broker transport usage is "
        "verified by AST."
    )

    print(
        "PASS: Candidate GET reconstruction call "
        "is verified by AST."
    )

    print(
        "PASS: Candidate submission call "
        "is verified by AST."
    )

    print(
        "PASS: Cumulative-cap evaluator call "
        "is verified by AST."
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
        "PASS: Unsafe-history scenario present."
    )

    print(
        "PASS: Incomplete-reconstruction scenario present."
    )

    print(
        "PASS: Historical-over-cap scenario present."
    )

    print(
        "PASS: Writer candidate v1.1 remains hard locked."
    )


# ============================================================
# WORKFLOW VERIFICATION
# ============================================================


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


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "Fund-100 static audit safety layer: v1.17"
    )

    verify_cumulative_cap_rehearsal_source()

    verify_cumulative_cap_rehearsal_workflow()

    v116.main()


if __name__ == "__main__":

    main()
