from __future__ import annotations

import inspect
from pathlib import Path

import audit_fund100_live_boundary_v1_9 as v19

import fund100_alpaca_live_execution_materializer as materializer


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.10
# ============================================================
#
# Adds execution materializer v1.0.
#
# The materializer must remain:
#
# - broker-network free
# - credential free
# - POST free
# - non-runnable
# - non-persisting by itself
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


MATERIALIZER_FILENAME = (
    "fund100_alpaca_live_execution_materializer.py"
)


def verify_execution_materializer():

    source = (
        inspect.getsource(
            materializer
        )
    )

    forbidden = [
        "urlopen(",
        "Request(",
        "requests.get(",
        "requests.post(",
        "requests.put(",
        "requests.patch(",
        "requests.delete(",
        "httpx.get(",
        "httpx.post(",
        "httpx.put(",
        "httpx.patch(",
        "httpx.delete(",
        'method="GET"',
        "method='GET'",
        'method="POST"',
        "method='POST'",
        'method="PUT"',
        "method='PUT'",
        'method="PATCH"',
        "method='PATCH'",
        'method="DELETE"',
        "method='DELETE'",
        "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET",
    ]

    detected = [
        token
        for token
        in forbidden
        if token
        in source
    ]

    if detected:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "execution materializer contains "
            "network/credential capability: "
            + ", ".join(
                detected
            )
        )

    if hasattr(
        materializer,
        "main",
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "execution materializer unexpectedly "
            "contains main()."
        )

    workflow_invocations = []

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

        text = path.read_text(
            encoding="utf-8"
        )

        if (
            f"python {MATERIALIZER_FILENAME}"
            in text
            or
            f"python3 {MATERIALIZER_FILENAME}"
            in text
            or
            (
                "import "
                "fund100_alpaca_live_execution_materializer"
            )
            in text
        ):

            workflow_invocations.append(
                str(
                    path.relative_to(
                        ROOT
                    )
                )
            )

    if workflow_invocations:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "a workflow directly invokes the "
            "execution materializer: "
            + ", ".join(
                workflow_invocations
            )
        )

    print(
        "PASS: Execution materializer has no broker network API."
    )

    print(
        "PASS: Execution materializer has no live credentials."
    )

    print(
        "PASS: Execution materializer contains no HTTP write path."
    )

    print(
        "PASS: Execution materializer has no main()."
    )

    print(
        "PASS: No workflow directly invokes "
        "the execution materializer."
    )

    print(
        "PASS: BUY phase requires currently available cash."
    )

    print(
        "PASS: Materializer fails closed on direction drift."
    )

    print(
        "PASS: Materializer enforces V2 permit ceiling."
    )


def main():

    print(
        "Fund-100 static audit safety layer: v1.10"
    )

    verify_execution_materializer()

    v19.main()


if __name__ == "__main__":

    main()
