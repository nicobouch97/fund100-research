"""Review-only, pinned GitHub Actions LIVE security migration planner.

Generates a precise unified diff for *human security review*.
NEVER writes a workflow, changes GitHub Settings, reads secret values,
calls a broker or approves execution. It operates on 40 local YAML
workflow sources. Rejects drift from the reviewed main commit, validates
the proposed change with the strict safety scanner, and outputs only
source-code YAML diffs plus audit metadata.

The patch is NOT safe to apply until an authorised admin independently
verifies a main-restricted GitHub Environment, environment-only secrets
and absence of repository/organization LIVE secret copies.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import difflib
import hashlib
import sys

from fund100_live_workflow_mutex_audit_v1_0 import (
    ACCOUNT_WRITER_MUTEX,
    CREDENTIAL_SCRIPT_BY_WORKFLOW,
    LIVE_CREDENTIAL_ENVIRONMENT,
    LIVE_ORDER_WRITER_WORKFLOWS,
    read_workflow_sources,
    scan_workflow_sources,
)

REVIEWED_MAIN_COMMIT = "3dc2ccf77bd8e08089fbaddbf6977af2abbea511"

# Reviewed Git object blob hashes, not GitHub secret contents. Any source
# change, including whitespace, INVALIDATES the proposed release package.
BASELINE_BLOB_SHA1 = {
    "fund100-alpaca-live-boundary-test.yml": "6ab36b42aff1a26ffca69a8849db2159d11e25fe",
    "fund100-alpaca-live-intent-validator.yml": "ebaf4fd45c723201ac0eaf2b360ea9a9c3a6c261",
    "fund100-alpaca-live-manifest.yml": "2784d5d385281b092f60e821da595be763c47123",
    "fund100-alpaca-live-permit-v2-issuer.yml": "309fcd68334055c7a0d0dc5c66a0ed6fe8c18790",
    "fund100-alpaca-live-permit-v2-simulation.yml": "e15854ed6e2b1b7dc8df7c672db74b94ae6375a1",
    "fund100-alpaca-live-position-reconcile.yml": "e711d4257fc660a119d0e0cefc6fa60a2d952918",
    "fund100-alpaca-live-preconnect-runtime-check.yml": "20be7578c608fe4a558520e205da86339ebee489",
    "fund100-alpaca-live-preflight.yml": "cf1bbbd5c06d66d29380c4001ae04fdb84d0a6dc",
    "fund100-alpaca-live-readonly.yml": "33ec6fff9bb88b94d8bab9fca76a324653f89daa",
    "fund100-alpaca-live-scheduled-compiler.yml": "001d3dff38fc81648de871b1cea118b62df2d1a4",
    "fund100-live-micro-pilot-prepare.yml": "745d4ae0360652b98828c0c06277efa67727ffa2",
    "fund100-live-bootstrap.yml": "31232f6be912985cc58e5f90953cec37fb4a1ec9",
    "fund100-v5-live-production.yml": "d5170f0447ae6d396f03355b3613fc5de66570a9",
}

EXACT_MAIN_GUARD = "    if: github.ref == 'refs/heads/main'"
ONE_JOB_RUNNER = "    runs-on: ubuntu-latest"
ONE_JOB_ENVIRONMENT = "    environment: fund100-live-broker"
LIVE_KEY_REF = "ALPACA_LIVE_KEY: ${{ secrets.ALPACA_LIVE_KEY }}"
LIVE_SECRET_REF = "ALPACA_LIVE_SECRET: ${{ secrets.ALPACA_LIVE_SECRET }}"


@dataclass(frozen=True)
class ProposedRelease:
    old_git_commit: str
    patched_workflow_count: int
    environment_bindings: int
    changed_writer_groups: int
    added_main_only_guards: int
    unified_diff: str
    unified_diff_sha256: str
    warnings: tuple[str, ...] = (
        "NOT APPLIED: workflow files remain unchanged",
        "No proof of actual GitHub Environment protections",
        "No proof LIVE secrets were removed from repository/organization scope",
        "No operator authorisation for funded LIVE orders",
    )


def _git_blob_hash(text: str) -> str:
    raw = text.encode("utf-8")
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw
    ).hexdigest()


def _replace_exact(source: str, needle: str, replacement: str) -> str:
    if source.count(needle) != 1:
        raise ValueError(f"Unsafe ambiguous/missing workflow anchor: {needle}")
    return source.replace(needle, replacement, 1)


def prepare_proposal(sources: dict[str, str]) -> ProposedRelease:
    """Return in-memory exact-change diff; NEVER mutate supplied sources."""
    if set(CREDENTIAL_SCRIPT_BY_WORKFLOW) != set(BASELINE_BLOB_SHA1):
        raise ValueError("Reviewed LIVE inventory changed")
    if any(name not in sources for name in BASELINE_BLOB_SHA1):
        raise ValueError("Missing LIVE workflow from supplied inventory")

    proposed = dict(sources)
    env_count = 0
    mutex_count = 0
    branch_count = 0
    sections: list[str] = []

    for name in sorted(BASELINE_BLOB_SHA1):
        original = sources[name]
        if _git_blob_hash(original) != BASELINE_BLOB_SHA1[name]:
            raise ValueError(
                f"Baseline changed, independent review needed: {name}"
            )
        if (
            original.count(LIVE_KEY_REF) != 1
            or original.count(LIVE_SECRET_REF) != 1
        ):
            raise ValueError(f"Unexpected credential sources: {name}")
        if "    environment:" in original:
            raise ValueError(f"Environment already exists: {name}")

        updated = original
        if name in LIVE_ORDER_WRITER_WORKFLOWS:
            old = (
                "  group: fund100-live-micro-pilot-bootstrap"
                if name == "fund100-live-bootstrap.yml"
                else "  group: fund100-v5-002-live-production"
            )
            updated = _replace_exact(
                updated, old,
                "  group: " + ACCOUNT_WRITER_MUTEX,
            )
            mutex_count += 1
            if EXACT_MAIN_GUARD in updated:
                raise ValueError(f"Main-branch guard already present: {name}")
            updated = _replace_exact(
                updated,
                ONE_JOB_RUNNER,
                EXACT_MAIN_GUARD + "\n" + ONE_JOB_RUNNER,
            )
            branch_count += 1

        updated = _replace_exact(
            updated,
            ONE_JOB_RUNNER,
            ONE_JOB_RUNNER + "\n" + ONE_JOB_ENVIRONMENT,
        )
        env_count += 1
        proposed[name] = updated

        changes = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile="a/.github/workflows/" + name,
            tofile="b/.github/workflows/" + name,
            n=3,
        ))
        if not changes or not changes.endswith("\n"):
            raise ValueError(f"Invalid or empty patch: {name}")
        sections.append(changes)

    if (env_count, mutex_count, branch_count) != (13, 2, 2):
        raise ValueError("Unsafe count of proposed protected workflow edits")
    validation = scan_workflow_sources(proposed)
    if not validation.passed:
        raise ValueError(
            "Proposed YAML fails the strict offline scanner: "
            + " | ".join(validation.problems)
        )
    patch = "".join(sections)
    return ProposedRelease(
        old_git_commit=REVIEWED_MAIN_COMMIT,
        patched_workflow_count=len(BASELINE_BLOB_SHA1),
        environment_bindings=env_count,
        changed_writer_groups=mutex_count,
        added_main_only_guards=branch_count,
        unified_diff=patch,
        unified_diff_sha256=hashlib.sha256(
            patch.encode("utf-8")
        ).hexdigest(),
    )


def read_and_prepare(repo_root: Path) -> ProposedRelease:
    return prepare_proposal(read_workflow_sources(repo_root))


def main() -> int:
    try:
        result = read_and_prepare(Path(__file__).resolve().parent)
    except (OSError, TypeError, ValueError) as exc:
        print("REVIEW PACKAGE STOP:", exc, file=sys.stderr)
        return 1

    print(
        "# REVIEW-ONLY: NOT APPLIED. Environment secrets, main branch "
        "policy and repo-secret absence must be independently verified."
    )
    print("# Baseline:", result.old_git_commit)
    print("# 13 env bindings + 2 mutex changes + 2 main-only guards")
    print("# Diff SHA256:", result.unified_diff_sha256)
    print(result.unified_diff, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
