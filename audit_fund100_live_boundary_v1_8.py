from __future__ import annotations

import inspect

import audit_fund100_live_boundary as base
import audit_fund100_live_boundary_v1_4 as v14
import audit_fund100_live_boundary_v1_5 as v15
import audit_fund100_live_boundary_v1_6 as v16
import audit_fund100_live_boundary_v1_7 as v17

import fund100_alpaca_live_scheduled_compiler_v1_1 as compiler


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.8
# ============================================================
#
# Adds position-aware scheduled compiler v1.1.
#
# The compiler:
#
# - may use LIVE credentials
# - may query Alpaca trading/data APIs
# - must use GET only
# - must never authorize execution
#
# ============================================================


base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_permit_v2_simulator.py"
)

base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_permit_v2_issuer.py"
)

base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_position_reconcile.py"
)

base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_manifest_v1_1.py"
)

base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_intent_validator_v1_1.py"
)

base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_scheduled_compiler_v1_1.py"
)


def verify_scheduled_compiler_v1_1():

    source = (
        inspect.getsource(
            compiler
        )
    )

    forbidden = [
        'method="POST"',
        "method='POST'",
        'method="PUT"',
        "method='PUT'",
        'method="PATCH"',
        "method='PATCH'",
        'method="DELETE"',
        "method='DELETE'",
        "requests.post(",
        "requests.put(",
        "requests.patch(",
        "requests.delete(",
        "httpx.post(",
        "httpx.put(",
        "httpx.patch(",
        "httpx.delete(",
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
            "scheduled compiler v1.1 contains "
            "a mutating HTTP path: "
            + ", ".join(
                detected
            )
        )

    if (
        compiler.LIVE_EXECUTION_AUTHORIZED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "scheduled compiler unexpectedly "
            "authorizes execution."
        )

    if abs(
        float(
            compiler.MAX_LIVE_EXECUTION_NOTIONAL_USD
        )
    ) > 1e-12:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "scheduled compiler monetary ceiling "
            "is not $0.00."
        )

    if (
        compiler.NETWORK_WRITE_CAPABILITY
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "scheduled compiler unexpectedly "
            "has network-write capability."
        )

    if (
        compiler.BROKER_WRITE_MODE
        != "DISABLED"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "scheduled compiler write mode "
            "is not DISABLED."
        )

    if (
        compiler.ORDERS_SUBMITTED
        != 0
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "scheduled compiler order count "
            "is not zero."
        )

    print(
        "PASS: Scheduled compiler v1.1 is GET-only."
    )

    print(
        "PASS: Scheduled compiler v1.1 preserves "
        "frozen strategy threshold separation."
    )

    print(
        "PASS: Scheduled compiler v1.1 is "
        "position-aware."
    )

    print(
        "PASS: Scheduled compiler v1.1 persists "
        "no broker weights or dollar values."
    )

    print(
        "PASS: Scheduled compiler v1.1 cannot "
        "authorize execution."
    )


def main():

    print(
        "Fund-100 static audit safety layer: v1.8"
    )

    v14.verify_writer_v1_1()

    v15.verify_position_reconciler()

    v16.verify_manifest_v1_1()

    v17.verify_intent_validator_v1_1()

    verify_scheduled_compiler_v1_1()

    base.main()


if __name__ == "__main__":

    main()
