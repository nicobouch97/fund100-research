from __future__ import annotations

import inspect
from pathlib import Path

import audit_fund100_live_boundary as root_audit
import audit_fund100_live_boundary_v1_12 as v112

import fund100_alpaca_live_preconnect_runtime_check as preconnect


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.13
# ============================================================
#
# Adds the credentialed GET-only pre-connect runtime checker.
#
# This script may receive LIVE credentials because:
#
# - it imports only the reviewed read-only broker helper
# - it contains no HTTP mutation
# - it does NOT import the writer candidate
# - the writer candidate is inspected only as source text/AST
# - its workflow keeps FUND100_LIVE_WRITE_MODE=DISABLED
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


PRECONNECT_SCRIPT = (
    "fund100_alpaca_live_preconnect_runtime_check.py"
)


WORKFLOW_PATH = (
    ROOT
    / ".github"
    / "workflows"
    / "fund100-alpaca-live-preconnect-runtime-check.yml"
)


# ============================================================
# MODULE AUDIT
# ============================================================


def verify_preconnect_module():

    source = (
        inspect.getsource(
            preconnect
        )
    )

    imports = (
        v112.imported_modules(
            source
        )
    )

    if (
        "fund100_alpaca_live_writer_candidate_v1_0"
        in imports
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "credentialed pre-connect checker imports "
            "the POST-capable writer candidate."
        )

    forbidden_network_imports = {
        "requests",
        "httpx",
        "aiohttp",
        "socket",
        "urllib.request",
    }

    bad_imports = (
        imports
        & forbidden_network_imports
    )

    if bad_imports:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "pre-connect checker imports a direct "
            "network client: "
            + ", ".join(
                sorted(
                    bad_imports
                )
            )
        )

    mutations = (
        v112.v111.executable_http_mutations(
            source
        )
    )

    if mutations:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "pre-connect checker contains executable "
            "HTTP mutation: "
            + ", ".join(
                mutations
            )
        )

    if (
        "live.get_json("
        not in source
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "pre-connect checker does not use "
            "the reviewed GET-only helper."
        )

    if (
        "extract_candidate_release_constants"
        not in source
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "pre-connect checker does not statically "
            "inspect candidate release constants."
        )

    print(
        "PASS: Pre-connect checker does not import "
        "the POST-capable writer candidate."
    )

    print(
        "PASS: Pre-connect checker imports no direct "
        "network client."
    )

    print(
        "PASS: Pre-connect checker contains no executable "
        "HTTP mutation."
    )

    print(
        "PASS: Pre-connect checker uses reviewed GET-only "
        "broker helper."
    )

    print(
        "PASS: Writer candidate is inspected as source only."
    )


# ============================================================
# WORKFLOW AUDIT
# ============================================================


def verify_preconnect_workflow():

    if not WORKFLOW_PATH.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "pre-connect runtime workflow is missing."
        )

    source = (
        WORKFLOW_PATH.read_text(
            encoding="utf-8"
        )
    )

    required_tokens = [
        "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET",
        "FUND100_BROKER_KILL_SWITCH",
        "FUND100_ENABLE_LIVE_READONLY",
        "YES_READ_ONLY_LIVE",
        "FUND100_LIVE_WRITE_MODE",
        "DISABLED",
        "FUND100_ENABLE_LIVE_PRECONNECT_CHECK",
        "YES_GET_ONLY_PRECONNECT",
        "python fund100_alpaca_live_preconnect_runtime_check.py",
    ]

    missing = [
        token
        for token
        in required_tokens
        if token
        not in source
    ]

    if missing:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "pre-connect workflow is missing required "
            "safety configuration: "
            + ", ".join(
                missing
            )
        )

    forbidden_tokens = [
        "FUND100_LIVE_WRITE_MODE: ENABLED",
        "FUND100_LIVE_WRITE_MODE: \"ENABLED\"",
        "python fund100_alpaca_live_writer_candidate_v1_0.py",
        "python3 fund100_alpaca_live_writer_candidate_v1_0.py",
        "import fund100_alpaca_live_writer_candidate_v1_0",
        "from fund100_alpaca_live_writer_candidate_v1_0 import",
        "FUND100_LIVE_APPROVAL_TOKEN",
    ]

    detected = [
        token
        for token
        in forbidden_tokens
        if token
        in source
    ]

    if detected:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "pre-connect workflow exposes a prohibited "
            "activation/writer path: "
            + ", ".join(
                detected
            )
        )

    print(
        "PASS: Dedicated LIVE pre-connect workflow exists."
    )

    print(
        "PASS: Pre-connect workflow supplies credentials "
        "only for GET-only inspection."
    )

    print(
        "PASS: Pre-connect workflow keeps live write mode "
        "DISABLED."
    )

    print(
        "PASS: Pre-connect workflow does not invoke/import "
        "the POST-capable writer candidate."
    )

    print(
        "PASS: Pre-connect workflow contains no "
        "approval token."
    )


# ============================================================
# MAIN
# ============================================================


def main():

    print(
        "Fund-100 static audit safety layer: v1.13"
    )

    # --------------------------------------------------------
    # Explicitly allow this one credentialed script.
    #
    # Root workflow audit will still reject any OTHER Python
    # script command receiving live credentials.
    # --------------------------------------------------------

    root_audit.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
        PRECONNECT_SCRIPT
    )

    verify_preconnect_module()

    verify_preconnect_workflow()

    v112.main()


if __name__ == "__main__":

    main()
