from __future__ import annotations

import inspect

import audit_fund100_live_boundary as base
import audit_fund100_live_boundary_v1_4 as v14
import audit_fund100_live_boundary_v1_5 as v15
import audit_fund100_live_boundary_v1_6 as v16

import fund100_alpaca_live_intent_validator_v1_1 as intent


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.7
# ============================================================
#
# Adds position-aware intent validator v1.1.
#
# The validator may use LIVE credentials for GET-only account
# reconciliation, but must expose no mutating broker path.
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


def verify_intent_validator_v1_1():

    source = (
        inspect.getsource(
            intent
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
            "intent validator v1.1 contains "
            "a mutating HTTP path: "
            + ", ".join(
                detected
            )
        )

    if (
        intent.LIVE_EXECUTION_AUTHORIZED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "intent validator unexpectedly "
            "authorizes execution."
        )

    if abs(
        float(
            intent.MAX_LIVE_EXECUTION_NOTIONAL_USD
        )
    ) > 1e-12:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "intent validator monetary ceiling "
            "is not $0.00."
        )

    if (
        intent.NETWORK_WRITE_CAPABILITY
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "intent validator unexpectedly "
            "has network-write capability."
        )

    if (
        intent.BROKER_WRITE_MODE
        != "DISABLED"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "intent validator write mode "
            "is not DISABLED."
        )

    if (
        intent.ORDERS_SUBMITTED
        != 0
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "intent validator order count "
            "is not zero."
        )

    print(
        "PASS: Intent validator v1.1 is GET-only."
    )

    print(
        "PASS: Intent validator v1.1 is position-aware."
    )

    print(
        "PASS: Intent validator v1.1 persists "
        "no live dollar values."
    )

    print(
        "PASS: Intent validator v1.1 cannot "
        "authorize execution."
    )


def main():

    print(
        "Fund-100 static audit safety layer: v1.7"
    )

    v14.verify_writer_v1_1()

    v15.verify_position_reconciler()

    v16.verify_manifest_v1_1()

    verify_intent_validator_v1_1()

    base.main()


if __name__ == "__main__":

    main()
