from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.0
# ============================================================
#
# OFFLINE ONLY.
#
# This audit performs NO network requests and needs NO broker
# credentials.
#
# It fails if the repository introduces an obvious reachable
# live-write path, including:
#
# - workflow invocation of the disconnected writer
# - FUND100_LIVE_WRITE_MODE=ENABLED
# - another live Python module containing POST/PATCH/PUT/DELETE
# - current live artifacts becoming executable
# - disconnected writer losing its hard connection guard
# - current V1 permit becoming compatible with the writer
# - obvious hard-coded Alpaca live credentials
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

WRITER_PATH = (
    ROOT
    / "fund100_alpaca_live_writer_disconnected.py"
)

WRITER_TEST_PATH = (
    ROOT
    / "test_fund100_alpaca_live_writer_disconnected.py"
)

LIVE_OUTPUT_DIR = (
    ROOT
    / "live_dryrun_outputs"
    / "v5_002"
)

MANIFEST_PATH = (
    LIVE_OUTPUT_DIR
    / "live_execution_manifest.json"
)

INTENTS_PATH = (
    LIVE_OUTPUT_DIR
    / "live_order_intents.json"
)

SCHEDULED_PATH = (
    LIVE_OUTPUT_DIR
    / "scheduled_execution_time.json"
)

PERMIT_PATH = (
    LIVE_OUTPUT_DIR
    / "live_execution_permit.json"
)

LIVE_HOST = (
    "api.alpaca.markets"
)

DISCONNECTED_WRITER_MODULE = (
    "fund100_alpaca_live_writer_disconnected"
)

DISCONNECTED_WRITER_FILENAME = (
    DISCONNECTED_WRITER_MODULE
    + ".py"
)

# These are the only scripts currently allowed to receive
# ALPACA_LIVE_KEY / ALPACA_LIVE_SECRET from GitHub Actions.
#
# They are read-only safety / compilation layers.
ALLOWED_LIVE_CREDENTIAL_SCRIPTS = {
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_alpaca_live_preflight.py",
    "fund100_alpaca_live_execution_boundary.py",
    "fund100_alpaca_live_manifest.py",
    "fund100_alpaca_live_intent_validator.py",
    "fund100_alpaca_live_scheduled_compiler.py",
}

LIVE_WRITE_PATTERNS = [
    re.compile(
        r"""method\s*=\s*["'](?:POST|PUT|PATCH|DELETE)["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""\brequests\.(?:post|put|patch|delete)\s*\(""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""\bhttpx\.(?:post|put|patch|delete)\s*\(""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""\bsession\.(?:post|put|patch|delete)\s*\(""",
        re.IGNORECASE,
    ),
]

WORKFLOW_WRITE_PATTERNS = [
    re.compile(
        r"""\bcurl\b[^\n]*(?:-X|--request)\s*(?:POST|PUT|PATCH|DELETE)""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""\b(?:POST|PUT|PATCH|DELETE)\b[^\n]*api\.alpaca\.markets""",
        re.IGNORECASE,
    ),
]

PYTHON_SCRIPT_PATTERN = re.compile(
    r"""(?:^|\s)python(?:3)?\s+([A-Za-z0-9_./-]+\.py)(?:\s|$)""",
    re.IGNORECASE,
)

HARDCODED_LIVE_SECRET_PATTERNS = [
    re.compile(
        r"""ALPACA_LIVE_KEY\s*=\s*["'][^"'\n]{6,}["']"""
    ),
    re.compile(
        r"""ALPACA_LIVE_SECRET\s*=\s*["'][^"'\n]{6,}["']"""
    ),
    re.compile(
        r"""["']APCA-API-KEY-ID["']\s*:\s*["'][^"'\n]{6,}["']"""
    ),
    re.compile(
        r"""["']APCA-API-SECRET-KEY["']\s*:\s*["'][^"'\n]{6,}["']"""
    ),
]


# ============================================================
# AUDIT RESULT COLLECTION
# ============================================================


class Audit:
    def __init__(self):

        self.passes: list[str] = []
        self.failures: list[str] = []
        self.notes: list[str] = []

    def passed(
        self,
        message: str,
    ) -> None:

        self.passes.append(
            message
        )

    def failed(
        self,
        message: str,
    ) -> None:

        self.failures.append(
            message
        )

    def note(
        self,
        message: str,
    ) -> None:

        self.notes.append(
            message
        )


# ============================================================
# FILE HELPERS
# ============================================================


def read_text(
    path: Path,
) -> str:

    try:

        return path.read_text(
            encoding="utf-8"
        )

    except UnicodeDecodeError:

        return ""


def repository_python_files():

    for path in ROOT.rglob(
        "*.py"
    ):

        if ".git" in path.parts:

            continue

        yield path


def repository_text_files():

    allowed_suffixes = {
        ".py",
        ".yml",
        ".yaml",
        ".json",
        ".txt",
        ".md",
        ".toml",
        ".ini",
        ".cfg",
    }

    for path in ROOT.rglob(
        "*"
    ):

        if not path.is_file():

            continue

        if ".git" in path.parts:

            continue

        if (
            path.suffix.lower()
            in allowed_suffixes
        ):

            yield path


def workflow_files():

    if not WORKFLOWS_DIR.exists():

        return []

    return sorted(
        [
            *WORKFLOWS_DIR.glob(
                "*.yml"
            ),
            *WORKFLOWS_DIR.glob(
                "*.yaml"
            ),
        ]
    )


# ============================================================
# AST HELPERS
# ============================================================


def parse_python(
    path: Path,
):

    source = read_text(
        path
    )

    try:

        tree = ast.parse(
            source,
            filename=str(
                path
            ),
        )

    except SyntaxError as exc:

        raise RuntimeError(
            f"Cannot parse {path.name}: {exc}"
        ) from exc

    return (
        source,
        tree,
    )


def find_function(
    tree: ast.AST,
    name: str,
):

    for node in ast.walk(
        tree
    ):

        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name == name
        ):

            return node

    return None


def first_executable_statement(
    function: ast.FunctionDef,
):

    body = list(
        function.body
    )

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

        body = body[
            1:
        ]

    if not body:

        return None

    return body[
        0
    ]


def is_named_call_statement(
    statement,
    function_name: str,
) -> bool:

    if not isinstance(
        statement,
        ast.Expr,
    ):

        return False

    call = (
        statement.value
    )

    if not isinstance(
        call,
        ast.Call,
    ):

        return False

    return (
        isinstance(
            call.func,
            ast.Name,
        )
        and call.func.id
        == function_name
    )


def simple_assignment(
    tree: ast.AST,
    name: str,
):

    for node in ast.walk(
        tree
    ):

        if not isinstance(
            node,
            ast.Assign,
        ):

            continue

        for target in node.targets:

            if (
                isinstance(
                    target,
                    ast.Name,
                )
                and target.id
                == name
            ):

                if isinstance(
                    node.value,
                    ast.Constant,
                ):

                    return (
                        node.value.value
                    )

    return None


# ============================================================
# WRITER HARD-DISCONNECT AUDIT
# ============================================================


def audit_writer(
    audit: Audit,
) -> None:

    if not WRITER_PATH.exists():

        audit.failed(
            "Disconnected live writer file is missing."
        )

        return

    source, tree = (
        parse_python(
            WRITER_PATH
        )
    )

    connected = (
        simple_assignment(
            tree,
            "LIVE_WRITER_CONNECTED",
        )
    )

    if connected is False:

        audit.passed(
            "LIVE_WRITER_CONNECTED is False."
        )

    else:

        audit.failed(
            "LIVE_WRITER_CONNECTED is not statically False."
        )

    permit_schema = (
        simple_assignment(
            tree,
            "REQUIRED_PERMIT_SCHEMA",
        )
    )

    if (
        permit_schema
        == "FUND100_LIVE_EXECUTION_PERMIT_V2"
    ):

        audit.passed(
            "Writer requires future V2 permit schema."
        )

    else:

        audit.failed(
            "Writer no longer requires the expected "
            "future V2 permit schema."
        )

    guard = (
        find_function(
            tree,
            "require_adapter_connected",
        )
    )

    if guard is None:

        audit.failed(
            "require_adapter_connected() is missing."
        )

    else:

        first = (
            first_executable_statement(
                guard
            )
        )

        if isinstance(
            first,
            ast.Raise,
        ):

            audit.passed(
                "require_adapter_connected() "
                "fails immediately with raise."
            )

        else:

            audit.failed(
                "require_adapter_connected() "
                "does not fail immediately."
            )

    network_functions = [
        "_get_order_by_client_id",
        "_post_live_market_order",
        "submit_authorized_order_batch",
    ]

    for name in network_functions:

        function = (
            find_function(
                tree,
                name,
            )
        )

        if function is None:

            audit.failed(
                f"{name}() is missing from writer."
            )

            continue

        first = (
            first_executable_statement(
                function
            )
        )

        if is_named_call_statement(
            first,
            "require_adapter_connected",
        ):

            audit.passed(
                f"{name}() hits disconnect "
                "guard before other executable code."
            )

        else:

            audit.failed(
                f"{name}() no longer begins with "
                "require_adapter_connected()."
            )

    main_function = (
        find_function(
            tree,
            "main",
        )
    )

    if main_function is None:

        audit.passed(
            "Disconnected writer has no main() function."
        )

    else:

        audit.failed(
            "Disconnected writer unexpectedly "
            "contains main()."
        )

    if (
        '__name__ == "__main__"'
        in source
        or "__name__ == '__main__'"
        in source
    ):

        audit.failed(
            "Disconnected writer contains an "
            "__main__ execution guard."
        )

    else:

        audit.passed(
            "Disconnected writer has no "
            "__main__ execution guard."
        )


# ============================================================
# WORKFLOW AUDIT
# ============================================================


def audit_workflows(
    audit: Audit,
) -> None:

    workflows = (
        workflow_files()
    )

    if not workflows:

        audit.failed(
            "No GitHub Actions workflows found."
        )

        return

    direct_writer_refs = []

    enabled_write_modes = []

    direct_live_api_refs = []

    unauthorized_credential_scripts = []

    dangerous_symbols = []

    for workflow in workflows:

        source = (
            read_text(
                workflow
            )
        )

        lower = (
            source.lower()
        )

        relative = str(
            workflow.relative_to(
                ROOT
            )
        )

        if (
            DISCONNECTED_WRITER_MODULE.lower()
            in lower
            or DISCONNECTED_WRITER_FILENAME.lower()
            in lower
        ):

            direct_writer_refs.append(
                relative
            )

        if (
            "submit_authorized_order_batch"
            in source
            or "livewriterdisconnected"
            in source.replace(
                "_",
                "",
            ).lower()
        ):

            dangerous_symbols.append(
                relative
            )

        if re.search(
            r"""FUND100_LIVE_WRITE_MODE\s*:\s*["']?ENABLED["']?""",
            source,
            flags=re.IGNORECASE,
        ):

            enabled_write_modes.append(
                relative
            )

        if (
            "LIVE_WRITER_CONNECTED"
            in source
        ):

            dangerous_symbols.append(
                relative
            )

        if LIVE_HOST in lower:

            direct_live_api_refs.append(
                relative
            )

        for pattern in (
            WORKFLOW_WRITE_PATTERNS
        ):

            if pattern.search(
                source
            ):

                dangerous_symbols.append(
                    relative
                )

        exposes_live_credentials = (
            "ALPACA_LIVE_KEY"
            in source
            or
            "ALPACA_LIVE_SECRET"
            in source
        )

        if exposes_live_credentials:

            for match in (
                PYTHON_SCRIPT_PATTERN.finditer(
                    source
                )
            ):

                script = Path(
                    match.group(
                        1
                    )
                ).name

                if (
                    script
                    not in
                    ALLOWED_LIVE_CREDENTIAL_SCRIPTS
                ):

                    unauthorized_credential_scripts.append(
                        (
                            relative,
                            script,
                        )
                    )

            if re.search(
                r"""python(?:3)?\s+-c\b""",
                source,
                flags=re.IGNORECASE,
            ):

                unauthorized_credential_scripts.append(
                    (
                        relative,
                        "python -c",
                    )
                )

            if re.search(
                r"""\bcurl\b""",
                source,
                flags=re.IGNORECASE,
            ):

                unauthorized_credential_scripts.append(
                    (
                        relative,
                        "curl",
                    )
                )

    if direct_writer_refs:

        audit.failed(
            "Runnable workflow references disconnected writer: "
            + ", ".join(
                sorted(
                    set(
                        direct_writer_refs
                    )
                )
            )
        )

    else:

        audit.passed(
            "No workflow directly invokes/imports "
            "the disconnected live writer."
        )

    if enabled_write_modes:

        audit.failed(
            "Workflow enables FUND100_LIVE_WRITE_MODE: "
            + ", ".join(
                sorted(
                    set(
                        enabled_write_modes
                    )
                )
            )
        )

    else:

        audit.passed(
            "No workflow sets "
            "FUND100_LIVE_WRITE_MODE=ENABLED."
        )

    if direct_live_api_refs:

        audit.failed(
            "Workflow directly contains live broker hostname: "
            + ", ".join(
                sorted(
                    set(
                        direct_live_api_refs
                    )
                )
            )
        )

    else:

        audit.passed(
            "No workflow directly calls "
            "api.alpaca.markets."
        )

    if dangerous_symbols:

        audit.failed(
            "Potential live-write workflow symbol detected: "
            + ", ".join(
                sorted(
                    set(
                        dangerous_symbols
                    )
                )
            )
        )

    else:

        audit.passed(
            "No workflow contains known live-writer "
            "activation/write symbols."
        )

    if unauthorized_credential_scripts:

        details = "; ".join(
            (
                f"{workflow} -> {script}"
            )
            for (
                workflow,
                script,
            )
            in unauthorized_credential_scripts
        )

        audit.failed(
            "Live credentials are exposed to a "
            "non-allowlisted command: "
            + details
        )

    else:

        audit.passed(
            "Live credentials are exposed only to "
            "allowlisted read-only/compile scripts."
        )


# ============================================================
# LIVE PYTHON WRITE-PATH AUDIT
# ============================================================


def audit_live_python_files(
    audit: Audit,
) -> None:

    write_files = []

    for path in (
        repository_python_files()
    ):

        if path == WRITER_PATH:

            continue

        source = (
            read_text(
                path
            )
        )

        lower = (
            source.lower()
        )

        looks_live = (
            "alpaca_live"
            in path.name.lower()
            or
            "alpaca_live"
            in lower
            or
            "alpaca_live_key"
            in lower
            or
            LIVE_HOST
            in lower
        )

        if not looks_live:

            continue

        for pattern in (
            LIVE_WRITE_PATTERNS
        ):

            if pattern.search(
                source
            ):

                write_files.append(
                    str(
                        path.relative_to(
                            ROOT
                        )
                    )
                )

                break

    if write_files:

        audit.failed(
            "Live Python write method exists outside "
            "the disconnected writer: "
            + ", ".join(
                sorted(
                    set(
                        write_files
                    )
                )
            )
        )

    else:

        audit.passed(
            "No live Python module outside the "
            "disconnected writer contains an HTTP "
            "POST/PUT/PATCH/DELETE path."
        )


# ============================================================
# SECRET-HYGIENE AUDIT
# ============================================================


def audit_secret_hygiene(
    audit: Audit,
) -> None:

    suspicious = []

    for path in (
        repository_text_files()
    ):

        source = (
            read_text(
                path
            )
        )

        for pattern in (
            HARDCODED_LIVE_SECRET_PATTERNS
        ):

            if pattern.search(
                source
            ):

                suspicious.append(
                    str(
                        path.relative_to(
                            ROOT
                        )
                    )
                )

                break

    forbidden_file_names = []

    for path in ROOT.rglob(
        "*"
    ):

        if not path.is_file():

            continue

        if ".git" in path.parts:

            continue

        name = (
            path.name.lower()
        )

        if (
            name == ".env"
            or name.endswith(
                ".pem"
            )
            or name.endswith(
                ".p12"
            )
            or name.endswith(
                ".pfx"
            )
        ):

            forbidden_file_names.append(
                str(
                    path.relative_to(
                        ROOT
                    )
                )
            )

    if suspicious:

        audit.failed(
            "Possible hard-coded live credential "
            "assignment found in: "
            + ", ".join(
                sorted(
                    set(
                        suspicious
                    )
                )
            )
        )

    else:

        audit.passed(
            "No obvious hard-coded Alpaca live "
            "credentials detected."
        )

    if forbidden_file_names:

        audit.failed(
            "Potential secret-bearing file committed: "
            + ", ".join(
                sorted(
                    set(
                        forbidden_file_names
                    )
                )
            )
        )

    else:

        audit.passed(
            "No .env / PEM / P12 / PFX secret file "
            "is present in the repository tree."
        )


# ============================================================
# JSON ARTIFACT HELPERS
# ============================================================


def load_json(
    path: Path,
):

    if not path.exists():

        raise RuntimeError(
            f"Required artifact missing: "
            f"{path.relative_to(ROOT)}"
        )

    with path.open(
        "r"
    ) as f:

        return json.load(
            f
        )


def require_false(
    audit: Audit,
    obj: dict,
    key: str,
    label: str,
):

    if obj.get(
        key
    ) is False:

        audit.passed(
            f"{label}: {key}=FALSE."
        )

    else:

        audit.failed(
            f"{label}: {key} is not FALSE."
        )


def require_zero(
    audit: Audit,
    obj: dict,
    key: str,
    label: str,
):

    try:

        value = float(
            obj.get(
                key
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        audit.failed(
            f"{label}: {key} is not numeric."
        )

        return

    if abs(
        value
    ) <= 1e-12:

        audit.passed(
            f"{label}: {key}=$0.00."
        )

    else:

        audit.failed(
            f"{label}: {key} is non-zero."
        )


# ============================================================
# ARTIFACT AUDIT
# ============================================================


def audit_live_artifacts(
    audit: Audit,
) -> None:

    try:

        manifest_package = (
            load_json(
                MANIFEST_PATH
            )
        )

        manifest = (
            manifest_package[
                "manifest"
            ]
        )

        require_false(
            audit,
            manifest,
            "live_execution_authorized",
            "Live manifest",
        )

        require_zero(
            audit,
            manifest,
            "max_live_execution_notional_usd",
            "Live manifest",
        )

        if (
            manifest.get(
                "broker_write_mode"
            )
            == "DISABLED"
        ):

            audit.passed(
                "Live manifest broker_write_mode=DISABLED."
            )

        else:

            audit.failed(
                "Live manifest broker_write_mode "
                "is not DISABLED."
            )

    except Exception as exc:

        audit.failed(
            f"Live manifest validation failed: {exc}"
        )

    try:

        intents_package = (
            load_json(
                INTENTS_PATH
            )
        )

        intents = (
            intents_package[
                "intent_bundle"
            ]
        )

        require_false(
            audit,
            intents,
            "live_execution_authorized",
            "Live intent bundle",
        )

        require_false(
            audit,
            intents,
            "network_write_capability",
            "Live intent bundle",
        )

        require_zero(
            audit,
            intents,
            "max_live_execution_notional_usd",
            "Live intent bundle",
        )

        executable_intents = [
            item
            for item
            in intents.get(
                "candidate_intents",
                []
            )
            if bool(
                item.get(
                    "executable",
                    False,
                )
            )
        ]

        if executable_intents:

            audit.failed(
                "Live intent bundle contains "
                "executable candidate intents."
            )

        else:

            audit.passed(
                "Live intent bundle contains no "
                "executable candidate intents."
            )

    except Exception as exc:

        audit.failed(
            f"Live intent validation failed: {exc}"
        )

    try:

        scheduled_package = (
            load_json(
                SCHEDULED_PATH
            )
        )

        scheduled = (
            scheduled_package[
                "compiler"
            ]
        )

        require_false(
            audit,
            scheduled,
            "live_execution_authorized",
            "Scheduled compiler",
        )

        require_false(
            audit,
            scheduled,
            "network_write_capability",
            "Scheduled compiler",
        )

        require_zero(
            audit,
            scheduled,
            "max_live_execution_notional_usd",
            "Scheduled compiler",
        )

        if (
            str(
                scheduled.get(
                    "compiler_mode",
                    ""
                )
            ).lower()
            == "synthetic"
        ):

            if (
                scheduled.get(
                    "genuine_scheduled_event"
                )
                is False
            ):

                audit.passed(
                    "Synthetic scheduled artifact is "
                    "explicitly non-genuine."
                )

            else:

                audit.failed(
                    "Synthetic scheduled artifact is "
                    "incorrectly marked genuine."
                )

    except Exception as exc:

        audit.failed(
            f"Scheduled compiler validation failed: {exc}"
        )

    try:

        permit_package = (
            load_json(
                PERMIT_PATH
            )
        )

        permit = (
            permit_package[
                "permit"
            ]
        )

        require_false(
            audit,
            permit,
            "permit_issued",
            "Live execution permit",
        )

        require_false(
            audit,
            permit,
            "live_execution_authorized",
            "Live execution permit",
        )

        require_false(
            audit,
            permit,
            "network_write_capability",
            "Live execution permit",
        )

        require_zero(
            audit,
            permit,
            "max_live_execution_notional_usd",
            "Live execution permit",
        )

        if (
            permit.get(
                "broker_write_mode"
            )
            == "DISABLED"
        ):

            audit.passed(
                "Live execution permit "
                "broker_write_mode=DISABLED."
            )

        else:

            audit.failed(
                "Live execution permit "
                "broker_write_mode is not DISABLED."
            )

        if (
            permit.get(
                "schema"
            )
            == "FUND100_LIVE_EXECUTION_PERMIT_V1"
        ):

            audit.passed(
                "Current permit remains deny-only V1 schema."
            )

        else:

            audit.failed(
                "Current live permit schema is no longer V1."
            )

    except Exception as exc:

        audit.failed(
            f"Live permit validation failed: {exc}"
        )


# ============================================================
# WRITER TEST AUDIT
# ============================================================


def audit_writer_tests(
    audit: Audit,
) -> None:

    if not WRITER_TEST_PATH.exists():

        audit.failed(
            "Disconnected-writer safety test file is missing."
        )

        return

    source = (
        read_text(
            WRITER_TEST_PATH
        )
    )

    required_tests = [
        "test_live_writer_is_declared_disconnected",
        "test_connection_gate_always_blocks",
        "test_public_submit_blocks_before_any_network",
        "test_private_post_blocks_before_any_network",
        "test_current_v1_permit_can_never_authorize",
    ]

    missing = [
        name
        for name
        in required_tests
        if name not in source
    ]

    if missing:

        audit.failed(
            "Disconnected-writer tests missing: "
            + ", ".join(
                missing
            )
        )

    else:

        audit.passed(
            "Disconnected-writer offline safety "
            "tests are present."
        )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 LIVE BOUNDARY STATIC AUDIT"
    )

    print(
        "============================================"
    )

    print(
        "\nMode: OFFLINE STATIC ANALYSIS"
    )

    print(
        "Broker credentials required: NO"
    )

    print(
        "Broker network access: NONE"
    )

    audit = (
        Audit()
    )

    audit_writer(
        audit
    )

    audit_workflows(
        audit
    )

    audit_live_python_files(
        audit
    )

    audit_secret_hygiene(
        audit
    )

    audit_live_artifacts(
        audit
    )

    audit_writer_tests(
        audit
    )

    print(
        "\n============================================"
    )

    print(
        "AUDIT PASSES"
    )

    print(
        "============================================"
    )

    for message in (
        audit.passes
    ):

        print(
            f"PASS: {message}"
        )

    if audit.notes:

        print(
            "\n============================================"
        )

        print(
            "AUDIT NOTES"
        )

        print(
            "============================================"
        )

        for message in (
            audit.notes
        ):

            print(
                f"NOTE: {message}"
            )

    if audit.failures:

        print(
            "\n============================================"
        )

        print(
            "AUDIT FAILURES"
        )

        print(
            "============================================"
        )

        for message in (
            audit.failures
        ):

            print(
                f"FAIL: {message}"
            )

        print(
            "\n============================================"
        )

        print(
            "LIVE BOUNDARY STATIC AUDIT: FAILED"
        )

        print(
            "============================================"
        )

        print(
            f"\nFailure count: "
            f"{len(audit.failures)}"
        )

        sys.exit(
            1
        )

    print(
        "\n============================================"
    )

    print(
        "LIVE BOUNDARY STATIC AUDIT: PASS"
    )

    print(
        "============================================"
    )

    print(
        f"\nChecks passed: "
        f"{len(audit.passes)}"
    )

    print(
        "Checks failed: 0"
    )

    print(
        "\nDisconnected live writer reachable "
        "from workflows: NO"
    )

    print(
        "Runnable live-write workflow: NO"
    )

    print(
        "Current live permit issued: NO"
    )

    print(
        "Current live monetary ceiling: $0.00"
    )

    print(
        "Current network write authorization: NO"
    )


if __name__ == "__main__":

    main()
