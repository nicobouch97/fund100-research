from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.1
# ============================================================
#
# OFFLINE ONLY.
#
# Fixes v1.0 false positives:
#
# 1. Merely checking that the disconnected writer FILE exists
#    is no longer treated as invoking the writer.
#
# 2. "api.alpaca.markets" is no longer matched as a substring
#    inside "paper-api.alpaca.markets".
#
# This audit performs NO broker requests and requires NO
# Alpaca credentials.
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


DISCONNECTED_WRITER_MODULE = (
    "fund100_alpaca_live_writer_disconnected"
)

DISCONNECTED_WRITER_FILENAME = (
    DISCONNECTED_WRITER_MODULE
    + ".py"
)


# ============================================================
# EXACT LIVE-ENDPOINT DETECTION
# ============================================================
#
# IMPORTANT:
#
# These patterns deliberately match:
#
#     https://api.alpaca.markets
#     "api.alpaca.markets"
#
# but DO NOT match:
#
#     https://paper-api.alpaca.markets
#
# ============================================================


EXACT_LIVE_URL_PATTERN = re.compile(
    r"""https://api\.alpaca\.markets(?=[/"'\s]|$)""",
    re.IGNORECASE,
)

EXACT_QUOTED_LIVE_HOST_PATTERN = re.compile(
    r"""["']api\.alpaca\.markets["']""",
    re.IGNORECASE,
)


# ============================================================
# WORKFLOW WRITER-INVOCATION DETECTION
# ============================================================
#
# Merely mentioning the filename is allowed.
#
# Examples that DO fail:
#
#     python fund100_alpaca_live_writer_disconnected.py
#     python -m fund100_alpaca_live_writer_disconnected
#     import fund100_alpaca_live_writer_disconnected
#     submit_authorized_order_batch(...)
#
# ============================================================


WRITER_INVOCATION_PATTERNS = [
    re.compile(
        r"""python(?:3)?\s+(?:\./)?fund100_alpaca_live_writer_disconnected\.py\b""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""python(?:3)?\s+-m\s+fund100_alpaca_live_writer_disconnected\b""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""\bimport\s+fund100_alpaca_live_writer_disconnected\b""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""\bfrom\s+fund100_alpaca_live_writer_disconnected\s+import\b""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""\bsubmit_authorized_order_batch\s*\(""",
        re.IGNORECASE,
    ),
]


# ============================================================
# HTTP WRITE DETECTION
# ============================================================


PYTHON_WRITE_PATTERNS = [
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

WORKFLOW_MUTATING_CURL_PATTERN = re.compile(
    r"""\bcurl\b[^\n]*(?:-X|--request)\s*(?:POST|PUT|PATCH|DELETE)""",
    re.IGNORECASE,
)


# ============================================================
# LIVE-CREDENTIAL WORKFLOW ALLOWLIST
# ============================================================


ALLOWED_LIVE_CREDENTIAL_SCRIPTS = {
    "fund100_alpaca_live_readonly_smoke.py",
    "fund100_alpaca_live_preflight.py",
    "fund100_alpaca_live_execution_boundary.py",
    "fund100_alpaca_live_manifest.py",
    "fund100_alpaca_live_intent_validator.py",
    "fund100_alpaca_live_scheduled_compiler.py",
}

PYTHON_SCRIPT_PATTERN = re.compile(
    r"""(?:^|\s)python(?:3)?\s+([A-Za-z0-9_./-]+\.py)(?:\s|$)""",
    re.IGNORECASE,
)


# ============================================================
# SECRET-HYGIENE PATTERNS
# ============================================================


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
# RESULT COLLECTION
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
# GENERIC HELPERS
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


def canonical_json(
    obj,
) -> str:

    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def sha256_json(
    obj,
) -> str:

    return hashlib.sha256(
        canonical_json(
            obj
        ).encode(
            "utf-8"
        )
    ).hexdigest()


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

    # Skip a possible function docstring.
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
# DISCONNECTED WRITER AUDIT
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
            "LIVE_WRITER_CONNECTED is not "
            "statically False."
        )

    required_schema = (
        simple_assignment(
            tree,
            "REQUIRED_PERMIT_SCHEMA",
        )
    )

    if (
        required_schema
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

    guarded_functions = [
        "_get_order_by_client_id",
        "_post_live_market_order",
        "submit_authorized_order_batch",
    ]

    for name in guarded_functions:

        function = (
            find_function(
                tree,
                name,
            )
        )

        if function is None:

            audit.failed(
                f"{name}() is missing."
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
                f"{name}() hits disconnect guard "
                "before other executable code."
            )

        else:

            audit.failed(
                f"{name}() no longer begins with "
                "require_adapter_connected()."
            )

    if (
        find_function(
            tree,
            "main",
        )
        is None
    ):

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

    writer_invocations = []

    enabled_write_modes = []

    direct_live_mutations = []

    unauthorized_credential_commands = []

    for workflow in workflows:

        source = (
            read_text(
                workflow
            )
        )

        relative = str(
            workflow.relative_to(
                ROOT
            )
        )

        # ----------------------------------------------------
        # A simple "test -f writer.py" is intentionally fine.
        #
        # Only actual invocation/import patterns fail.
        # ----------------------------------------------------

        for pattern in (
            WRITER_INVOCATION_PATTERNS
        ):

            if pattern.search(
                source
            ):

                writer_invocations.append(
                    relative
                )

                break

        if re.search(
            r"""FUND100_LIVE_WRITE_MODE\s*:\s*["']?ENABLED["']?""",
            source,
            flags=re.IGNORECASE,
        ):

            enabled_write_modes.append(
                relative
            )

        # ----------------------------------------------------
        # Workflow-level direct live mutation.
        # ----------------------------------------------------

        if (
            EXACT_LIVE_URL_PATTERN.search(
                source
            )
            or
            EXACT_QUOTED_LIVE_HOST_PATTERN.search(
                source
            )
        ):

            if (
                WORKFLOW_MUTATING_CURL_PATTERN.search(
                    source
                )
            ):

                direct_live_mutations.append(
                    relative
                )

        # ----------------------------------------------------
        # Live credential exposure.
        # ----------------------------------------------------

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

                    unauthorized_credential_commands.append(
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

                unauthorized_credential_commands.append(
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

                unauthorized_credential_commands.append(
                    (
                        relative,
                        "curl",
                    )
                )

    if writer_invocations:

        audit.failed(
            "Runnable workflow invokes/imports "
            "the disconnected writer: "
            + ", ".join(
                sorted(
                    set(
                        writer_invocations
                    )
                )
            )
        )

    else:

        audit.passed(
            "No workflow invokes/imports the "
            "disconnected live writer."
        )

    if enabled_write_modes:

        audit.failed(
            "Workflow enables "
            "FUND100_LIVE_WRITE_MODE=ENABLED: "
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

    if direct_live_mutations:

        audit.failed(
            "Workflow directly performs a mutating "
            "request against the LIVE Alpaca endpoint: "
            + ", ".join(
                sorted(
                    set(
                        direct_live_mutations
                    )
                )
            )
        )

    else:

        audit.passed(
            "No workflow directly performs a "
            "mutating LIVE Alpaca HTTP request."
        )

    if unauthorized_credential_commands:

        details = "; ".join(
            (
                f"{workflow} -> {command}"
            )
            for (
                workflow,
                command,
            )
            in unauthorized_credential_commands
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


def source_targets_live_environment(
    path: Path,
    source: str,
) -> bool:

    # --------------------------------------------------------
    # A file with the explicit live module naming convention
    # is treated as live.
    #
    # Additionally, an arbitrarily named file is treated as
    # live if it contains the EXACT live Alpaca host.
    #
    # "paper-api.alpaca.markets" does NOT satisfy either exact
    # hostname pattern.
    # --------------------------------------------------------

    if path.name.startswith(
        "fund100_alpaca_live_"
    ):

        return True

    if EXACT_LIVE_URL_PATTERN.search(
        source
    ):

        return True

    if EXACT_QUOTED_LIVE_HOST_PATTERN.search(
        source
    ):

        return True

    return False


def audit_live_python_files(
    audit: Audit,
) -> None:

    write_files = []

    for path in (
        repository_python_files()
    ):

        if path == WRITER_PATH:

            # This is the intentionally disconnected
            # future writer and is audited separately.
            continue

        source = (
            read_text(
                path
            )
        )

        if not source_targets_live_environment(
            path=
                path,

            source=
                source,
        ):

            continue

        for pattern in (
            PYTHON_WRITE_PATTERNS
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
            "LIVE Python write method exists "
            "outside the disconnected writer: "
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
            "No LIVE Python module outside the "
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

    secret_files = []

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
            or
            name.endswith(
                ".pem"
            )
            or
            name.endswith(
                ".p12"
            )
            or
            name.endswith(
                ".pfx"
            )
        ):

            secret_files.append(
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

    if secret_files:

        audit.failed(
            "Potential secret-bearing file committed: "
            + ", ".join(
                sorted(
                    set(
                        secret_files
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
            "Required artifact missing: "
            + str(
                path.relative_to(
                    ROOT
                )
            )
        )

    with path.open(
        "r"
    ) as f:

        return json.load(
            f
        )


def verify_package_hash(
    package: dict,
    body_key: str,
    hash_key: str,
):

    if body_key not in package:

        raise RuntimeError(
            f"Missing body key: {body_key}"
        )

    if hash_key not in package:

        raise RuntimeError(
            f"Missing hash key: {hash_key}"
        )

    recorded = str(
        package[
            hash_key
        ]
    )

    calculated = (
        sha256_json(
            package[
                body_key
            ]
        )
    )

    if recorded != calculated:

        raise RuntimeError(
            f"{hash_key} verification failed."
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
# CURRENT LIVE ARTIFACT AUDIT
# ============================================================


def audit_live_artifacts(
    audit: Audit,
) -> None:

    # --------------------------------------------------------
    # MANIFEST
    # --------------------------------------------------------

    try:

        package = (
            load_json(
                MANIFEST_PATH
            )
        )

        verify_package_hash(
            package=
                package,

            body_key=
                "manifest",

            hash_key=
                "manifest_sha256",
        )

        manifest = (
            package[
                "manifest"
            ]
        )

        audit.passed(
            "Live manifest SHA256 verification: PASS."
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

    # --------------------------------------------------------
    # INTENTS
    # --------------------------------------------------------

    try:

        package = (
            load_json(
                INTENTS_PATH
            )
        )

        verify_package_hash(
            package=
                package,

            body_key=
                "intent_bundle",

            hash_key=
                "intent_bundle_sha256",
        )

        intents = (
            package[
                "intent_bundle"
            ]
        )

        audit.passed(
            "Live intent-bundle SHA256 verification: PASS."
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

        executable = [
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

        if executable:

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

    # --------------------------------------------------------
    # SCHEDULED COMPILER
    # --------------------------------------------------------

    try:

        package = (
            load_json(
                SCHEDULED_PATH
            )
        )

        verify_package_hash(
            package=
                package,

            body_key=
                "compiler",

            hash_key=
                "compiler_sha256",
        )

        scheduled = (
            package[
                "compiler"
            ]
        )

        audit.passed(
            "Scheduled compiler SHA256 verification: PASS."
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
                    "",
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

    # --------------------------------------------------------
    # PERMIT
    # --------------------------------------------------------

    try:

        package = (
            load_json(
                PERMIT_PATH
            )
        )

        verify_package_hash(
            package=
                package,

            body_key=
                "permit",

            hash_key=
                "permit_sha256",
        )

        permit = (
            package[
                "permit"
            ]
        )

        audit.passed(
            "Live permit SHA256 verification: PASS."
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
                "Current permit remains "
                "deny-only V1 schema."
            )

        else:

            audit.failed(
                "Current live permit schema "
                "is no longer V1."
            )

    except Exception as exc:

        audit.failed(
            f"Live permit validation failed: {exc}"
        )


# ============================================================
# DISCONNECTED-WRITER TEST AUDIT
# ============================================================


def audit_writer_tests(
    audit: Audit,
) -> None:

    if not WRITER_TEST_PATH.exists():

        audit.failed(
            "Disconnected-writer safety test "
            "file is missing."
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
        "FUND-100 LIVE BOUNDARY STATIC AUDIT v1.1"
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
