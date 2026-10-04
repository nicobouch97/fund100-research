from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import audit_fund100_live_boundary as root_audit
import audit_fund100_live_boundary_v1_10 as v110

import fund100_alpaca_live_writer_candidate_v1_0 as candidate


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.11
# ============================================================
#
# Adds the first POST-shaped connected-writer candidate.
#
# The candidate may contain reviewed GET/POST transport code,
# but:
#
# - transport release is hard-coded FALSE
# - public execution release is hard-coded FALSE
# - no environment-variable activation exists
# - no credential-environment access exists
# - no main() exists
# - no workflow may invoke/import the candidate
# - GET/POST helpers must begin with hard release guards
#
# IMPORTANT:
#
# Both:
#
#   - environment-hook detection
#   - repository HTTP-mutation detection
#
# are AST-based.
#
# Comments, documentation and audit pattern strings therefore
# cannot masquerade as executable network/write capability.
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
    "fund100_alpaca_live_writer_candidate_v1_0.py"
)


CANDIDATE_PATH = (
    ROOT
    / CANDIDATE_FILENAME
)


WRITE_METHODS = {
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
}


# ============================================================
# AST HELPERS
# ============================================================


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

        prefix = (
            dotted_name(
                node.value
            )
        )

        if prefix:

            return (
                prefix
                + "."
                + node.attr
            )

        return node.attr

    return None


def function_first_call_name(
    source: str,
    function_name: str,
):

    tree = ast.parse(
        source
    )

    for node in tree.body:

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):

            continue

        if (
            node.name
            != function_name
        ):

            continue

        body = list(
            node.body
        )

        # ----------------------------------------------------
        # Skip a real function docstring if one exists.
        # ----------------------------------------------------

        if (
            body
            and isinstance(
                body[0],
                ast.Expr,
            )
            and isinstance(
                body[0].value,
                ast.Constant,
            )
            and isinstance(
                body[0].value.value,
                str,
            )
        ):

            body = (
                body[
                    1:
                ]
            )

        if not body:

            return None

        first = (
            body[
                0
            ]
        )

        if not isinstance(
            first,
            ast.Expr,
        ):

            return None

        call = (
            first.value
        )

        if not isinstance(
            call,
            ast.Call,
        ):

            return None

        return (
            dotted_name(
                call.func
            )
        )

    return None


# ============================================================
# AST REQUEST-METHOD DETECTION
# ============================================================


def request_methods_in_ast(
    source: str,
):

    tree = ast.parse(
        source
    )

    methods = []

    for node in ast.walk(
        tree
    ):

        if not isinstance(
            node,
            ast.Call,
        ):

            continue

        function_name = (
            dotted_name(
                node.func
            )
        )

        if not function_name:

            continue

        # ----------------------------------------------------
        # urllib.request.Request(..., method="GET/POST")
        #
        # Candidate imports Request directly, but support both
        # direct and dotted forms.
        # ----------------------------------------------------

        if (
            function_name
            == "Request"
            or function_name.endswith(
                ".Request"
            )
        ):

            for keyword in node.keywords:

                if (
                    keyword.arg
                    != "method"
                ):

                    continue

                if not isinstance(
                    keyword.value,
                    ast.Constant,
                ):

                    continue

                if not isinstance(
                    keyword.value.value,
                    str,
                ):

                    continue

                methods.append(
                    keyword.value.value.upper()
                )

    return methods


# ============================================================
# AST HTTP-MUTATION DETECTION
# ============================================================


def executable_http_mutations(
    source: str,
):

    tree = ast.parse(
        source
    )

    findings = []

    # --------------------------------------------------------
    # urllib Request(... method="POST"/PUT/PATCH/DELETE)
    # --------------------------------------------------------

    for method in (
        request_methods_in_ast(
            source
        )
    ):

        if (
            method
            in WRITE_METHODS
        ):

            findings.append(
                f"Request(method={method})"
            )

    # --------------------------------------------------------
    # requests.post(...)
    # httpx.post(...)
    # session.post(...)
    #
    # and corresponding PUT/PATCH/DELETE methods.
    # --------------------------------------------------------

    for node in ast.walk(
        tree
    ):

        if not isinstance(
            node,
            ast.Call,
        ):

            continue

        function_name = (
            dotted_name(
                node.func
            )
        )

        if not function_name:

            continue

        lowered = (
            function_name.lower()
        )

        explicit_mutators = {
            "requests.post",
            "requests.put",
            "requests.patch",
            "requests.delete",

            "httpx.post",
            "httpx.put",
            "httpx.patch",
            "httpx.delete",

            "session.post",
            "session.put",
            "session.patch",
            "session.delete",
        }

        if (
            lowered
            in explicit_mutators
        ):

            findings.append(
                function_name
            )

    return sorted(
        set(
            findings
        )
    )


# ============================================================
# AST ENVIRONMENT / ACTIVATION CHECK
# ============================================================


def detect_runtime_environment_hooks(
    source: str,
):

    tree = ast.parse(
        source
    )

    findings = []

    forbidden_environment_names = {
        "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET",
        "FUND100_LIVE_WRITE_MODE",
        "FUND100_ENABLE_LIVE_WRITER",
    }

    for node in ast.walk(
        tree
    ):

        # ----------------------------------------------------
        # import os
        # ----------------------------------------------------

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                if (
                    alias.name
                    == "os"
                ):

                    findings.append(
                        "import os"
                    )

        # ----------------------------------------------------
        # from os import ...
        # ----------------------------------------------------

        if isinstance(
            node,
            ast.ImportFrom,
        ):

            if (
                node.module
                == "os"
            ):

                findings.append(
                    "from os import ..."
                )

        # ----------------------------------------------------
        # os.environ / os.getenv
        # ----------------------------------------------------

        if isinstance(
            node,
            ast.Attribute,
        ):

            if (
                isinstance(
                    node.value,
                    ast.Name,
                )
                and
                node.value.id
                == "os"
                and
                node.attr
                in {
                    "environ",
                    "getenv",
                }
            ):

                findings.append(
                    f"os.{node.attr}"
                )

        # ----------------------------------------------------
        # getenv(...) imported directly.
        # ----------------------------------------------------

        if isinstance(
            node,
            ast.Call,
        ):

            if (
                isinstance(
                    node.func,
                    ast.Name,
                )
                and
                node.func.id
                == "getenv"
            ):

                findings.append(
                    "getenv(...)"
                )

        # ----------------------------------------------------
        # Credential/activation environment names appearing
        # in executable string constants.
        #
        # Comments are not represented in the AST.
        # ----------------------------------------------------

        if isinstance(
            node,
            ast.Constant,
        ):

            if not isinstance(
                node.value,
                str,
            ):

                continue

            for name in (
                forbidden_environment_names
            ):

                if (
                    name
                    in node.value
                ):

                    findings.append(
                        f"runtime string constant: {name}"
                    )

    return sorted(
        set(
            findings
        )
    )


# ============================================================
# WORKFLOW INVOCATION CHECK
# ============================================================


def candidate_workflow_invocations():

    patterns = [
        re.compile(
            r"""python(?:3)?\s+(?:\./)?fund100_alpaca_live_writer_candidate_v1_0\.py\b""",
            re.IGNORECASE,
        ),

        re.compile(
            r"""python(?:3)?\s+-m\s+fund100_alpaca_live_writer_candidate_v1_0\b""",
            re.IGNORECASE,
        ),

        re.compile(
            r"""\bimport\s+fund100_alpaca_live_writer_candidate_v1_0\b""",
            re.IGNORECASE,
        ),

        re.compile(
            r"""\bfrom\s+fund100_alpaca_live_writer_candidate_v1_0\s+import\b""",
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

        source = path.read_text(
            encoding="utf-8"
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
# PATCH ROOT LIVE WRITE SCAN
# ============================================================


def audit_live_python_files_v1_11(
    audit,
) -> None:

    write_files = []

    permitted_write_shape_files = {
        root_audit.WRITER_PATH.resolve(),
        CANDIDATE_PATH.resolve(),
    }

    for path in (
        root_audit.repository_python_files()
    ):

        resolved = (
            path.resolve()
        )

        # ----------------------------------------------------
        # These two write-shaped modules are reviewed
        # separately:
        #
        # 1. original disconnected writer
        # 2. hard-locked connected-writer candidate
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Do NOT use raw regex to detect HTTP mutation here.
        #
        # Audit files legitimately contain strings discussing
        # POST/PUT/PATCH/DELETE.
        #
        # Count only executable Python AST calls.
        # ----------------------------------------------------

        mutations = (
            executable_http_mutations(
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
            "reviewed disconnected/candidate writer "
            "boundary contains executable HTTP mutation."
        )


# ============================================================
# CANDIDATE AUDIT
# ============================================================


def verify_writer_candidate():

    source = (
        inspect.getsource(
            candidate
        )
    )

    # --------------------------------------------------------
    # HARD-CODED RELEASE STATE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # NO RUNNABLE ENTRYPOINT
    # --------------------------------------------------------

    if hasattr(
        candidate,
        "main",
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate contains main()."
        )

    # --------------------------------------------------------
    # NO ENVIRONMENT ACTIVATION
    # --------------------------------------------------------

    environment_hooks = (
        detect_runtime_environment_hooks(
            source
        )
    )

    if environment_hooks:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate contains executable runtime "
            "environment/credential hooks: "
            + ", ".join(
                environment_hooks
            )
        )

    # --------------------------------------------------------
    # REVIEWED GET / POST TRANSPORT SHAPE MUST EXIST
    #
    # AST-based, so comments/audit strings do not count.
    # --------------------------------------------------------

    request_methods = set(
        request_methods_in_ast(
            source
        )
    )

    if (
        "POST"
        not in request_methods
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate does not contain an executable "
            "reviewed POST Request transport shape."
        )

    if (
        "GET"
        not in request_methods
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate does not contain an executable "
            "reviewed GET idempotency transport shape."
        )

    # --------------------------------------------------------
    # NETWORK PATHS MUST BEGIN WITH HARD RELEASE GUARDS
    # --------------------------------------------------------

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
            function_first_call_name(
                source,
                function_name,
            )
        )

        if (
            actual
            != expected_guard
        ):

            raise RuntimeError(
                "LIVE STATIC AUDIT STOP: "
                f"{function_name} does not begin with "
                f"{expected_guard}(). "
                f"First call was {actual!r}."
            )

    # --------------------------------------------------------
    # NO WORKFLOW INVOCATION
    # --------------------------------------------------------

    invocations = (
        candidate_workflow_invocations()
    )

    if invocations:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "a workflow invokes/imports the "
            "connected-writer candidate: "
            + ", ".join(
                invocations
            )
        )

    # --------------------------------------------------------
    # FULL FROZEN V5 UNIVERSE
    # --------------------------------------------------------

    expected_symbols = {
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

    if (
        candidate.ALLOWED_SYMBOLS
        != expected_symbols
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate universe is not the "
            "full frozen V5 execution universe."
        )

    # --------------------------------------------------------
    # EXPECTED ALPACA LIVE HOST
    # --------------------------------------------------------

    if (
        candidate.EXPECTED_LIVE_HOST
        != "api.alpaca.markets"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate does not target the expected "
            "Alpaca LIVE host."
        )

    if (
        candidate.LIVE_BASE_URL
        != "https://api.alpaca.markets"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate LIVE base URL is unexpected."
        )

    # --------------------------------------------------------
    # EXPECTED ORDER ENDPOINTS
    # --------------------------------------------------------

    if (
        candidate.LIVE_ORDER_PATH
        != "/v2/orders"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate order endpoint is unexpected."
        )

    if (
        candidate.LIVE_ORDER_BY_CLIENT_ID_PATH
        != "/v2/orders:by_client_order_id"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "candidate idempotency endpoint is unexpected."
        )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    print(
        "PASS: Connected-writer candidate contains "
        "reviewed Alpaca GET/POST transport shape."
    )

    print(
        "PASS: Candidate transport release is "
        "hard-coded FALSE."
    )

    print(
        "PASS: Candidate public execution is "
        "hard-coded FALSE."
    )

    print(
        "PASS: Candidate executable AST has no "
        "environment activation hook."
    )

    print(
        "PASS: Candidate executable AST has no "
        "credential-environment hook."
    )

    print(
        "PASS: Candidate has no main()."
    )

    print(
        "PASS: Candidate GET begins with "
        "hard release guard."
    )

    print(
        "PASS: Candidate POST begins with "
        "hard release guard."
    )

    print(
        "PASS: Candidate public execution begins "
        "with hard release guard."
    )

    print(
        "PASS: No workflow invokes/imports "
        "the connected-writer candidate."
    )

    print(
        "PASS: Candidate uses the full frozen V5 universe."
    )

    print(
        "PASS: Candidate targets expected Alpaca LIVE host."
    )

    print(
        "PASS: Candidate uses expected Alpaca "
        "order endpoints."
    )

    print(
        "PASS: Repository LIVE write-path detection "
        "is executable-AST based."
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "Fund-100 static audit safety layer: v1.11"
    )

    # --------------------------------------------------------
    # Historical root audit allowed exactly one POST-shaped
    # file: the disconnected writer.
    #
    # v1.11 permits one additional reviewed candidate.
    #
    # The repository-wide scan is replaced with an AST-based
    # implementation so audit strings/comments cannot create
    # false positive write paths.
    # --------------------------------------------------------

    root_audit.audit_live_python_files = (
        audit_live_python_files_v1_11
    )

    verify_writer_candidate()

    v110.main()


if __name__ == "__main__":

    main()
