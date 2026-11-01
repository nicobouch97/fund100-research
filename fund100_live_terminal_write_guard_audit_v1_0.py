"""Offline, fail-closed terminal Alpaca LIVE POST boundary audit.

Both LIVE order writers call bootstrap.live_request. The separately
reviewed proposed repair introduces a final local kill-switch check and
limits HTTP POST to the exact order endpoint. This is defense-in-depth:
it does not authenticate a remote change to an already-running process.

Source audit only: no GitHub Settings, Alpaca requests, orders or keys.\n\nThe source fingerprint for the production controller is updated to the\n2026-10-28 main version, which adds account-level risk checks, operator\nSTOP re-reads and stricter event parsing. It is still an EXACT blob pin,\nnot a wildcard acceptance of arbitrary production code. Only the shared\nbootstrap transport owns the network POST; any changed order call sites\nremain subject to this AST scanner and its negative tests.
This contract is intentionally RED on the unchanged protected baseline.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path
from typing import Mapping

BOOTSTRAP = "fund100_live_bootstrap_v1_0.py"
PRODUCTION = "fund100_live_production_controller_v1_0.py"
REVIEWED_WRITER_BLOBS = {
    BOOTSTRAP: "3d866d415ba228b6c538adac6d0a70e6b93de34d",
    PRODUCTION: "e441cd43930010d34ef02c901ccfb633babd45f6",
}

# These exact AST tests have predictable meaning, regardless of formatting.
POST_CONDITION = "method == 'POST'"
LIMITED_POST_PATH = "path != '/v2/orders'"
ENGAGED_KILL_CONDITION = (
    "os.environ.get('FUND100_BROKER_KILL_SWITCH', '')"
    ".strip().upper() != 'DISENGAGED'"
)


@dataclass(frozen=True)
class TerminalWriteAudit:
    baseline_pinned: bool
    guarded_approved_order_path_count: int
    raw_network_sink_count: int
    problems: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.problems


def _canonical_expr(code: str) -> str:
    return ast.dump(ast.parse(code, mode="eval").body, include_attributes=False)


def _is_test(statement: ast.stmt, test: str) -> bool:
    return (
        isinstance(statement, ast.If)
        and ast.dump(statement.test, include_attributes=False)
        == _canonical_expr(test)
    )


def _direct_raise(statement: ast.stmt) -> bool:
    return isinstance(statement, ast.If) and len(statement.body) > 0 and (
        isinstance(statement.body[0], ast.Raise)
    )


def _git_blob(text: str) -> str:
    data = text.encode("utf-8")
    return sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    ).hexdigest()


def _find_function(tree: ast.Module, name: str) -> ast.FunctionDef | None:
    values = [
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    ]
    return values[0] if len(values) == 1 else None


def _call_is(call: ast.Call, target: str) -> bool:
    if isinstance(call.func, ast.Name):
        return call.func.id == target
    if isinstance(call.func, ast.Attribute):
        return call.func.attr == target
    return False


def _approved_order_calls(tree: ast.Module) -> tuple[int, int]:
    """Inspect calls in both writers; reject unscoped POST destinations."""
    good = 0
    bad = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _call_is(node, "live_request"):
            continue
        pairs = {x.arg: x.value for x in node.keywords if x.arg}
        method = pairs.get("method")
        if not isinstance(method, ast.Constant) or method.value != "POST":
            continue
        endpoint = pairs.get("path")
        if (
            isinstance(endpoint, ast.Constant)
            and endpoint.value == "/v2/orders"
        ):
            good += 1
        else:
            bad += 1
    return good, bad


def scan_terminal_write_sources(
    sources: Mapping[str, str],
    *,
    verify_pins: bool = True,
) -> TerminalWriteAudit:
    """Fail on missing transport-level kill-switch and path restrictions."""
    if not isinstance(sources, Mapping):
        raise TypeError("Review source mapping required")
    issues = set()
    trees: dict[str, ast.Module] = {}
    pinned = True
    for name, expected in REVIEWED_WRITER_BLOBS.items():
        code = sources.get(name)
        if not isinstance(code, str):
            issues.add(f"missing reviewed LIVE order writer: {name}")
            pinned = False
            continue
        if _git_blob(code) != expected:
            pinned = False
            if verify_pins:
                issues.add(f"reviewed LIVE order writer source changed: {name}")
        try:
            trees[name] = ast.parse(code, filename=name)
        except SyntaxError:
            issues.add(f"malformed reviewed LIVE order writer: {name}")

    raw_count = 0
    good_count = 0
    if BOOTSTRAP in trees:
        tree = trees[BOOTSTRAP]
        fn = _find_function(tree, "live_request")
        if fn is None:
            issues.add("missing sole bootstrap LIVE HTTP transport")
        else:
            first_sink_index = None
            for index, stmt in enumerate(fn.body):
                if any(
                    isinstance(node, ast.Call)
                    and (_call_is(node, "Request")
                         or _call_is(node, "urlopen"))
                    for node in ast.walk(stmt)
                ):
                    first_sink_index = index
                    break
            if first_sink_index is None:
                issues.add("bootstrap transport has no reviewed HTTP sink")
            else:
                raw_count = sum(
                    isinstance(node, ast.Call)
                    and (_call_is(node, "Request")
                         or _call_is(node, "urlopen"))
                    for node in ast.walk(fn)
                )
                # Refuse unreviewed extra network sinks.
                if raw_count != 2:
                    issues.add("unexpected bootstrap raw HTTP sink count")
                post_blocks = [
                    stmt for stmt in fn.body[:first_sink_index]
                    if _is_test(stmt, POST_CONDITION)
                ]
                if len(post_blocks) != 1:
                    issues.add("bootstrap POST transport needs direct pre-HTTP gate")
                else:
                    section = post_blocks[0].body
                    for test, label in (
                        (LIMITED_POST_PATH, "POST endpoint unrestricted"),
                        (ENGAGED_KILL_CONDITION,
                         "POST sink has no final kill-switch check"),
                    ):
                        matched = [
                            stmt for stmt in section
                            if _is_test(stmt, test) and _direct_raise(stmt)
                        ]
                        if len(matched) != 1:
                            issues.add(label)

        approved, bad = _approved_order_calls(tree)
        good_count += approved
        if bad:
            issues.add("bootstrap has unreviewed order POST destination")
    if PRODUCTION in trees:
        approved, bad = _approved_order_calls(trees[PRODUCTION])
        good_count += approved
        if bad:
            issues.add("production has unreviewed order POST destination")

    # Precisely one authorised order submitter in each real writer.
    if good_count != 2:
        issues.add("unreviewed number of LIVE order POST callers")

    return TerminalWriteAudit(
        baseline_pinned=pinned,
        guarded_approved_order_path_count=good_count,
        raw_network_sink_count=raw_count,
        problems=tuple(sorted(issues)),
    )


def read_terminal_sources(root: Path) -> dict[str, str]:
    return {
        name: (Path(root) / name).read_text(encoding="utf-8")
        for name in REVIEWED_WRITER_BLOBS
    }


def main() -> int:
    report = scan_terminal_write_sources(
        read_terminal_sources(Path(__file__).resolve().parent)
    )
    print("FINAL LIVE ORDER HTTP SINK:", "PASS" if report.passed else "BLOCKED")
    print("Direct order POST callers:", report.guarded_approved_order_path_count)
    print("Current writer baseline pinned:", report.baseline_pinned)
    for problem in report.problems:
        print("BLOCK:", problem)
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
