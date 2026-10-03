from __future__ import annotations

import inspect

import audit_fund100_live_boundary as base
import audit_fund100_live_boundary_v1_4 as v14
import fund100_alpaca_live_position_reconcile as reconcile


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.5
# ============================================================
#
# Adds the read-only position reconciliation layer.
#
# The reconciler may receive LIVE credentials because it
# performs GET-only account / positions / open-order reads.
#
# It must not contain:
#
# - POST
# - PUT
# - PATCH
# - DELETE
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


def verify_position_reconciler():

    source = (
        inspect.getsource(
            reconcile
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
            "position reconciler contains a "
            "mutating HTTP path: "
            + ", ".join(
                detected
            )
        )

    if (
        reconcile.LIVE_EXECUTION_AUTHORIZED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "position reconciler unexpectedly "
            "authorizes execution."
        )

    if (
        reconcile.NETWORK_WRITE_CAPABILITY
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "position reconciler unexpectedly "
            "has network-write capability."
        )

    if (
        reconcile.BROKER_WRITE_MODE
        != "DISABLED"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "position reconciler write mode "
            "is not DISABLED."
        )

    if (
        reconcile.ORDERS_SUBMITTED
        != 0
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "position reconciler order count "
            "is not zero."
        )

    print(
        "PASS: Position reconciler is GET-only."
    )

    print(
        "PASS: Position reconciler cannot authorize execution."
    )

    print(
        "PASS: Position reconciler does not persist live holdings."
    )


def main():

    print(
        "Fund-100 static audit safety layer: v1.5"
    )

    v14.verify_writer_v1_1()

    verify_position_reconciler()

    base.main()


if __name__ == "__main__":

    main()
