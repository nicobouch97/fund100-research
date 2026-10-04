from __future__ import annotations

import inspect
import re
from pathlib import Path

import audit_fund100_live_boundary as root_audit
import audit_fund100_live_boundary_v1_11 as v111
import audit_fund100_live_boundary_v1_13 as v113

import fund100_alpaca_live_writer_candidate_v1_1 as candidate


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.14
# ============================================================
#
# Adds writer candidate v1.1.
#
# v1.1 remains HARD LOCKED and adds only:
#
# - explicit existing-order status semantics
# - terminal-failure rejection
# - unsafe/unknown-status rejection
# - submitted-response status validation
#
# Both connected-writer candidates remain non-runnable.
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


WORKFLOWS_DIR = (
    ROOT
    / ".github"
    / "workflows"
)


CANDIDATE_FILENAME = (
    "fund100_alpaca_live_writer_candidate_v1_1.py"
)


CANDIDATE_PATH = (
    ROOT
    / CANDIDATE_FILENAME
)


EXPECTED_SYMBOLS = {
    "ACWI",
    "SPY",
    "IWM",
    "EFA",
    "EEM",
    "VNQ",
    "XLK",
    "XLF",
    "XLI",
    "XLV",
    "XLP",
    "XLY",
    "XLE",
    "XLU",
}


EXPECTED_FILLED = {
    "filled",
}


EXPECTED_NO_RESUBMIT = {
    "accepted",
    "pending_new",
    "accepted_for_bidding",
    "new",
    "partially_filled",
    "pending_cancel",
    "stopped",
    "done_for_day",
    "calculated",
}


EXPECTED_TERMINAL_FAILURE = {
    "canceled",
    "expired",
    "rejected",
}


EXPECTED_UNSAFE = {
    "replaced",
    "pending_replace",
    "suspended",
    "held",
}


# ============================================================
# WORKFLOW INVOCATION
# ============================================================


def candidate_v1_1_workflow_invocations():

    patterns = [
        re.compile(
            r"""python(?:3)?\s+(?:\./)?fund100_alpaca_live_writer_candidate_v1_1\.py\b""",
            re.IGNORECASE,
        ),

        re.compile(
            r"""python(?:3)?\s+-m\s+fund100_alpaca_live_writer_candidate_v1_1\b""",
            re.IGNORECASE,
        ),

        re.compile(
            r"""\bimport\s+fund100_alpaca_live_writer_candidate_v1_1\b""",
            re.IGNORECASE,
        ),

        re.compile(
            r"""\bfrom\s+fund100_alpaca_live_writer_candidate_v1_1\s+import\b""",
            re.IGNORECASE,
        ),
    ]

    hits = []

    for path in sorted(
        [
            *WORKFLOWS_DIR.glob(
                "*.yml"
            ),

            *WORKFLOWS_DIR.glob(
                "*.yaml"
            ),
        ]
    ):

        source = (
            path.read_text(
                encoding="utf-8"
            )
        )

        if any(
            pattern.search(
                source
            )
            for pattern
            in patterns
        ):

            hits.append(
                str(
                    path.relative_to(
                        ROOT
                    )
                )
            )

    return hits


# ============================================================
# REPOSITORY WRITE-PATH SCAN
# ============================================================


def audit_live_python_files_v1_14(
    audit,
) -> None:

    write_files = []

    permitted_write_shape_files = {
        root_audit.WRITER_PATH.resolve(),
        v111.CANDIDATE_PATH.resolve(),
        CANDIDATE_PATH.resolve(),
    }

    for path in (
        root_audit.repository_python_files()
    ):

        resolved = (
            path.resolve()
        )

        if (
            resolved
            in permitted_write_shape_files
        ):

            continue

        source = (
            root_audit.read_text(
                path
            )
        )

        if not (
            root_audit.source_targets_live_environment(
                path=
                    path,

                source=
                    source,
            )
        ):

            continue

        mutations = (
            v111.executable_http_mutations(
                source
            )
        )

        if mutations:

            write_files.append(
                (
                    str(
                        path.relative_to(
                            ROOT
                        )
                    ),

                    mutations,
                )
            )

    if write_files:

        details = "; ".join(
            (
                filename
                + " -> "
                + ", ".join(
                    mutations
                )
            )
            for (
                filename,
                mutations,
            )
            in write_files
        )

        audit.failed(
            "LIVE executable Python HTTP mutation exists "
            "outside the reviewed writer boundary: "
            + details
        )

    else:

        audit.passed(
            "No LIVE Python module outside the "
            "reviewed disconnected/v1.0/v1.1 writer "
            "boundary contains executable HTTP mutation."
        )


# ============================================================
# v1.1 CANDIDATE AUDIT
# ============================================================


def verify_writer_candidate_v1_1():

    source = (
        inspect.getsource(
            candidate
        )
    )

    if (
        candidate.WRITER_CANDIDATE_VERSION
        != "1.1"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "unexpected candidate version."
        )

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "v1.1 candidate transport is released."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "v1.1 candidate public execution is enabled."
        )

    if hasattr(
        candidate,
        "main",
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "v1.1 candidate contains main()."
        )

    environment_hooks = (
        v111.detect_runtime_environment_hooks(
            source
        )
    )

    if environment_hooks:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "v1.1 candidate contains executable "
            "environment/credential hooks: "
            + ", ".join(
                environment_hooks
            )
        )

    request_methods = set(
        v111.request_methods_in_ast(
            source
        )
    )

    if (
        "GET"
        not in request_methods
        or
        "POST"
        not in request_methods
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "v1.1 candidate GET/POST transport "
            "shape is incomplete."
        )

    guarded_functions = {
        "_get_order_by_client_id":
            "require_transport_released",

        "_post_live_market_order":
            "require_transport_released",

        "submit_authorized_order_batch":
            "require_public_execution_released",
    }

    for (
        function_name,
        expected_guard,
    ) in guarded_functions.items():

        actual = (
            v111.function_first_call_name(
                source,
                function_name,
            )
        )

        if actual != expected_guard:

            raise RuntimeError(
                "LIVE STATIC AUDIT STOP: "
                f"{function_name} does not begin with "
                f"{expected_guard}()."
            )

    if (
        candidate.ALLOWED_SYMBOLS
        != EXPECTED_SYMBOLS
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "v1.1 candidate universe changed."
        )

    if (
        candidate.LIVE_BASE_URL
        != "https://api.alpaca.markets"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "v1.1 LIVE base URL changed."
        )

    if (
        candidate.EXPECTED_LIVE_HOST
        != "api.alpaca.markets"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "v1.1 LIVE host changed."
        )

    if (
        candidate.LIVE_ORDER_PATH
        != "/v2/orders"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "v1.1 order endpoint changed."
        )

    if (
        candidate.LIVE_ORDER_BY_CLIENT_ID_PATH
        != "/v2/orders:by_client_order_id"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "v1.1 idempotency endpoint changed."
        )

    if (
        candidate.FILLED_STATUSES
        != EXPECTED_FILLED
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "filled status semantics changed."
        )

    if (
        candidate.NO_RESUBMIT_STATUSES
        != EXPECTED_NO_RESUBMIT
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "no-resubmit status semantics changed."
        )

    if (
        candidate.TERMINAL_FAILURE_STATUSES
        != EXPECTED_TERMINAL_FAILURE
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "terminal-failure semantics changed."
        )

    if (
        candidate.AMBIGUOUS_UNSAFE_STATUSES
        != EXPECTED_UNSAFE
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "unsafe-status semantics changed."
        )

    groups = [
        candidate.FILLED_STATUSES,
        candidate.NO_RESUBMIT_STATUSES,
        candidate.TERMINAL_FAILURE_STATUSES,
        candidate.AMBIGUOUS_UNSAFE_STATUSES,
    ]

    for index, left in enumerate(
        groups
    ):

        for right in groups[
            index + 1:
        ]:

            if not left.isdisjoint(
                right
            ):

                raise RuntimeError(
                    "LIVE STATIC AUDIT STOP: "
                    "order-status categories overlap."
                )

    invocations = (
        candidate_v1_1_workflow_invocations()
    )

    if invocations:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "workflow invokes/imports v1.1 candidate: "
            + ", ".join(
                invocations
            )
        )

    print(
        "PASS: Writer candidate v1.1 is hard locked."
    )

    print(
        "PASS: Writer candidate v1.1 has no runtime "
        "environment activation hook."
    )

    print(
        "PASS: Writer candidate v1.1 GET/POST paths "
        "begin with hard release guards."
    )

    print(
        "PASS: Writer candidate v1.1 uses full frozen "
        "V5 universe."
    )

    print(
        "PASS: Filled order recovery is explicit."
    )

    print(
        "PASS: Active/partial orders are NO-RESUBMIT."
    )

    print(
        "PASS: Canceled/expired/rejected orders "
        "fail closed."
    )

    print(
        "PASS: Replaced/pending-replace/suspended/held "
        "orders fail closed."
    )

    print(
        "PASS: Unknown broker order status fails closed."
    )

    print(
        "PASS: No workflow invokes/imports "
        "writer candidate v1.1."
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "Fund-100 static audit safety layer: v1.14"
    )

    verify_writer_candidate_v1_1()

    # --------------------------------------------------------
    # v1.13 eventually calls v1.11.main().
    #
    # Patch only the repository-wide reviewed-write-boundary
    # scanner so it recognizes v1.1 as a reviewed, HARD-LOCKED
    # candidate alongside v1.0.
    # --------------------------------------------------------

    original_scan = (
        v111.audit_live_python_files_v1_11
    )

    v111.audit_live_python_files_v1_11 = (
        audit_live_python_files_v1_14
    )

    try:

        v113.main()

    finally:

        v111.audit_live_python_files_v1_11 = (
            original_scan
        )


if __name__ == "__main__":

    main()
