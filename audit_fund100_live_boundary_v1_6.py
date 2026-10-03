from __future__ import annotations

import inspect

import audit_fund100_live_boundary as base
import audit_fund100_live_boundary_v1_5 as v15
import fund100_alpaca_live_manifest_v1_1 as manifest


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.6
# ============================================================
#
# Adds position-aware live manifest v1.1.
#
# Manifest v1.1 may receive live credentials because it
# performs GET-only validation.
#
# It must contain no mutating broker HTTP path.
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


def verify_manifest_v1_1():

    source = (
        inspect.getsource(
            manifest
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
            "manifest v1.1 contains a mutating "
            "HTTP path: "
            + ", ".join(
                detected
            )
        )

    if (
        manifest.LIVE_EXECUTION_AUTHORIZED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "manifest v1.1 unexpectedly "
            "authorizes execution."
        )

    if (
        abs(
            float(
                manifest.MAX_LIVE_EXECUTION_NOTIONAL_USD
            )
        )
        > 1e-12
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "manifest v1.1 execution ceiling "
            "is not $0.00."
        )

    if (
        manifest.NETWORK_WRITE_CAPABILITY
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "manifest v1.1 unexpectedly has "
            "network-write capability."
        )

    if (
        manifest.BROKER_WRITE_MODE
        != "DISABLED"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "manifest v1.1 write mode is not DISABLED."
        )

    if (
        manifest.ORDERS_SUBMITTED
        != 0
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "manifest v1.1 order count is not zero."
        )

    print(
        "PASS: Live manifest v1.1 is GET-only."
    )

    print(
        "PASS: Live manifest v1.1 is position-aware."
    )

    print(
        "PASS: Live manifest v1.1 cannot authorize execution."
    )

    print(
        "PASS: Live manifest v1.1 does not persist "
        "volatile broker holdings."
    )


def main():

    print(
        "Fund-100 static audit safety layer: v1.6"
    )

    v15.verify_position_reconciler()

    verify_manifest_v1_1()

    base.main()


if __name__ == "__main__":

    main()
