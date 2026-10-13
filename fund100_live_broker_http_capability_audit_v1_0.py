"""Offline broker HTTP capability evidence for non-order-writing entrypoints.

Do not mistake a reference to a disabled POST transport for proven
GET-only import closure. Several credentialed LIVE *research* modules
transitively import a legacy writer containing dormant POST code.

Checks:
- local AST import closure from the 11 non-order-writer credentials scripts
- every urllib.Request has literal method GET unless it resides inside
  the reviewed, unconditional-guarded legacy _post_live_market_order
- urllib.urlopen allowed only in the reviewed GET transport modules and
  the disabled legacy writer; unexpected network transports fail closed
- hardstop functions must remain first-statement guards before any HTTP
- core transport source blobs are pinned to independently reviewed main

This is structural static evidence, NOT proof of runtime purity against
monkeypatching, arbitrary dynamic module loads, other GitHub workflow
commands, or external account-order writers. No Alpaca request is made.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Mapping

from fund100_live_workflow_mutex_audit_v1_0 import (
    CREDENTIAL_SCRIPT_BY_WORKFLOW,
    LIVE_ORDER_WRITER_WORKFLOWS,
)

TRANSPORT_BLOBS = {
    "fund100_alpaca_live_readonly_smoke.py":
        "cf871f849a140c7b1db29fd991c8e00da31e1974",
    "fund100_live_pilot_prepare_v1_0.py":
        "dfebc7cedcd9820b1141c74a69d85e500c287748",
    "fund100_alpaca_live_writer_disconnected.py":
        "9e0501d2785275748a4916df6da6862a9815de9b",
    "fund100_alpaca_live_writer_disconnected_v1_1.py":
        "2a10c19485d6f52c8df391fb1f2756bca2630889",
}
GET_MODULES = frozenset({
    "fund100_alpaca_live_readonly_smoke",
    "fund100_live_pilot_prepare_v1_0",
    "fund100_alpaca_live_writer_disconnected",
})
DORMANT_POST_MODULE = "fund100_alpaca_live_writer_disconnected"
DORMANT_POST_FUNCTION = "_post_live_market_order"

# Sources are only Python files in the repository; vendor libraries are
# never imported or executed by the audit.
BANNED_IMPORTS = frozenset({
    "requests", "httpx", "socket", "subprocess", "aiohttp",
    "importlib", "ftplib", "http", "websockets",
})
BANNED_DYNAMIC_CALLS = frozenset({
    "eval", "exec", "__import__", "compile",
})


@dataclass(frozen=True)
class BrokerCapabilityAudit:
    credential_read_entrypoints: tuple[str, ...]
    analyzed_modules: tuple[str, ...]
    request_get_sites: tuple[str, ...]
    dormant_post_sites: tuple[str, ...]
    problems: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return len(self.problems) == 0


def _git_blob(text: str) -> str:
    data = text.encode("utf-8")
    return sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def _local_imports(tree: ast.AST, available: set[str]) -> set[str]:
    deps: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name.split(".")[0]
                if name in available:
                    deps.add(name)
        if isinstance(node, ast.ImportFrom):
            name = (node.module or "").split(".")[0]
            if name in available:
                deps.add(name)
    return deps


def _first_statement_call(func: ast.FunctionDef, name: str) -> bool:
    if not func.body or not isinstance(func.body[0], ast.Expr):
        return False
    expression = func.body[0].value
    return (
        isinstance(expression, ast.Call)
        and isinstance(expression.func, ast.Name)
        and expression.func.id == name
    )


def _find_named(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    funcs = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    return funcs[0] if len(funcs) == 1 else None


def _is_dead_writer_guard(module: str, tree: ast.Module) -> bool:
    if module == DORMANT_POST_MODULE:
        guard = _find_named(tree, "require_adapter_connected")
        return (
            guard is not None
            and bool(guard.body)
            and isinstance(guard.body[0], ast.Raise)
            and isinstance(guard.body[0].exc, ast.Call)
            and isinstance(guard.body[0].exc.func, ast.Name)
            and guard.body[0].exc.func.id == "LiveWriterDisconnected"
        )
    if module == "fund100_alpaca_live_writer_disconnected_v1_1":
        guard = _find_named(tree, "require_adapter_connected")
        if guard is None or not guard.body:
            return False
        node = guard.body[0]
        return (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "base"
            and node.value.func.attr == "require_adapter_connected"
        )
    return False


def scan_capability_sources(
    sources: Mapping[str, str],
    *,
    verify_blob_pins: bool = True,
) -> BrokerCapabilityAudit:
    """Never evaluate supplied Python source. Fail closed on unknown sinks."""
    if not isinstance(sources, Mapping):
        raise TypeError("Python source mapping required")
    available = {
        filename[:-3] for filename in sources
        if isinstance(filename, str) and filename.endswith(".py")
    }
    readers = tuple(sorted(
        name[:-3]
        for workflow, name in CREDENTIAL_SCRIPT_BY_WORKFLOW.items()
        if workflow not in LIVE_ORDER_WRITER_WORKFLOWS
    ))
    problems: set[str] = set()
    parsed: dict[str, ast.Module] = {}
    visited: set[str] = set()
    pending = list(readers)

    while pending:
        mod = pending.pop()
        if mod in visited:
            continue
        visited.add(mod)
        filename = mod + ".py"
        src = sources.get(filename)
        if not isinstance(src, str):
            problems.add(f"missing transitive source: {filename}")
            continue
        try:
            tree = ast.parse(src, filename=filename)
        except SyntaxError:
            problems.add(f"invalid Python AST: {filename}")
            continue
        parsed[mod] = tree
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [a.name.split(".")[0] for a in node.names]
                    if isinstance(node, ast.Import)
                    else [(node.module or "").split(".")[0]]
                )
                if any(name in BANNED_IMPORTS for name in names):
                    problems.add(f"unreviewed network/dynamic import: {mod}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in BANNED_DYNAMIC_CALLS:
                    problems.add(f"dynamic execution: {mod}")
        pending.extend(sorted(_local_imports(tree, available) - visited))

    for filename, digest in TRANSPORT_BLOBS.items():
        source = sources.get(filename)
        if verify_blob_pins and (
            not isinstance(source, str)
            or _git_blob(source) != digest
        ):
            problems.add(f"reviewed transport source changed: {filename}")

    for name in (
        DORMANT_POST_MODULE,
        "fund100_alpaca_live_writer_disconnected_v1_1",
    ):
        tree = parsed.get(name)
        if tree is None or not _is_dead_writer_guard(name, tree):
            problems.add(f"writer disconnect no longer a hard stop: {name}")
        if tree is not None:
            post = _find_named(tree, "submit_authorized_order_batch")
            if post is None or not _first_statement_call(
                post, "require_adapter_connected"
            ):
                problems.add(f"writer batch guard missing: {name}")

    for mod, tree in parsed.items():
        get_requests: list[str] = []
        post_requests: list[str] = []
        urlopen_sites: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for stmt in ast.walk(node):
                if not isinstance(stmt, ast.Call):
                    continue
                func = stmt.func
                if isinstance(func, ast.Name) and func.id == "Request":
                    methods = [
                        keyword.value
                        for keyword in stmt.keywords
                        if keyword.arg == "method"
                    ]
                    method = (
                        methods[0].value if len(methods) == 1
                        and isinstance(methods[0], ast.Constant)
                        and isinstance(methods[0].value, str)
                        else "UNKNOWN"
                    )
                    if method == "GET":
                        if mod not in GET_MODULES:
                            problems.add(f"unexpected broker GET transport: {mod}")
                        get_requests.append(f"{mod}.{node.name}")
                    elif (
                        method == "POST"
                        and mod == DORMANT_POST_MODULE
                        and node.name == DORMANT_POST_FUNCTION
                        and _first_statement_call(
                            node, "require_adapter_connected"
                        )
                    ):
                        post_requests.append(f"{mod}.{node.name}")
                    else:
                        problems.add(
                            f"unapproved HTTP {method} path: "
                            f"{mod}.{node.name}"
                        )
                if isinstance(func, ast.Name) and func.id == "urlopen":
                    urlopen_sites.append(f"{mod}.{node.name}")
                    if mod not in GET_MODULES:
                        problems.add(f"unexpected urllib network sink: {mod}")

        # Demand no top-level urllib method invocation or unreviewed aliases.
        for stmt in tree.body:
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                func = stmt.value.func
                if isinstance(func, ast.Name) and func.id in {"urlopen", "Request"}:
                    problems.add(f"top-level broker HTTP call: {mod}")
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "urllib.request":
                for alias in node.names:
                    if alias.name in {"Request", "urlopen"} and (
                        alias.asname is not None or mod not in GET_MODULES
                    ):
                        problems.add(f"unexpected urllib alias/reader: {mod}")

        if mod == "fund100_alpaca_live_writer_disconnected":
            if not any(x.endswith("._post_live_market_order") for x in post_requests):
                problems.add("dormant POST contract not observed as guarded")

    return BrokerCapabilityAudit(
        credential_read_entrypoints=readers,
        analyzed_modules=tuple(sorted(parsed)),
        request_get_sites=tuple(sorted(
            f"{mod}.{node.name}"
            for mod, tree in parsed.items()
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            for c in ast.walk(node)
            if isinstance(c, ast.Call)
            and isinstance(c.func, ast.Name)
            and c.func.id == "Request"
            and any(k.arg == "method" and isinstance(k.value, ast.Constant)
                    and k.value.value == "GET" for k in c.keywords)
        )),
        dormant_post_sites=(
            ("fund100_alpaca_live_writer_disconnected._post_live_market_order",)
            if DORMANT_POST_MODULE in parsed else ()
        ),
        problems=tuple(sorted(problems)),
    )


def read_python_sources(root: Path) -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(Path(root).glob("*.py"))
    }


def main() -> int:
    report = scan_capability_sources(
        read_python_sources(Path(__file__).resolve().parent)
    )
    print("Credential non-order-writing entrypoints:", len(report.credential_read_entrypoints))
    print("Transitive source modules inspected:", len(report.analyzed_modules))
    print("Reviewed GET request call sites:", len(report.request_get_sites))
    print("Dormant POST sites (guard-checked):", len(report.dormant_post_sites))
    for item in report.problems:
        print("BLOCK:", item)
    print("SOURCE HTTP GATE:", "PASS" if report.passed else "FAILED")
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
