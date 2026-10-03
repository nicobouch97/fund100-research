from __future__ import annotations

import inspect

import audit_fund100_live_boundary as base
import audit_fund100_live_boundary_v1_8 as v18

import fund100_alpaca_live_permit_v2_issuer as issuer_base
import fund100_alpaca_live_permit_v2_issuer_v1_1 as issuer
import fund100_alpaca_live_writer_disconnected_v1_1 as writer


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.9
# ============================================================
#
# Adds the V2 permit issuer v1.1 compatibility layer.
#
# Issuer v1.1:
#
# - receives LIVE credentials
# - may use GET only
# - submits zero orders
# - uses disconnected writer v1.1
# - blocks preview / issue until final issuer-aware lock
#
# ============================================================


base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_permit_v2_simulator.py"
)

base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_permit_v2_issuer.py"
)

base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_permit_v2_issuer_v1_1.py"
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


def verify_v2_issuer_v1_1():

    source = (
        inspect.getsource(
            issuer
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
            "V2 issuer v1.1 compatibility layer "
            "contains a broker mutation path: "
            + ", ".join(
                detected
            )
        )

    issuer.apply_v1_1()

    if (
        issuer_base.RELEASE_LOCK_SCHEMA
        != issuer.RELEASE_LOCK_SCHEMA
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "V2 issuer release-lock schema "
            "was not upgraded."
        )

    if (
        issuer_base.MANIFEST_SCHEMA
        != issuer.MANIFEST_SCHEMA
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "V2 issuer manifest schema "
            "was not upgraded."
        )

    if (
        issuer_base.COMPILER_SCHEMA
        != issuer.COMPILER_SCHEMA
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "V2 issuer compiler schema "
            "was not upgraded."
        )

    if (
        issuer_base.writer
        is not writer
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "V2 issuer is not using writer v1.1."
        )

    if (
        writer.LIVE_WRITER_CONNECTED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer v1.1 is connected."
        )

    interim = {
        "schema":
            issuer.RELEASE_LOCK_SCHEMA,

        "position_aware_live_chain_verified":
            True,

        "position_reconciliation_policy":
            issuer.POSITION_POLICY,

        "v2_issuer_v1_1_compatibility_upgrade_required":
            True,

        "final_activation_lock_required_after_issuer_upgrade":
            True,

        "critical_file_sha256":
            {},
    }

    issuer.require_action_allowed_by_lock(
        action=
            issuer_base.ACTION_CHECK,

        lock_body=
            interim,
    )

    preview_blocked = False

    try:

        issuer.require_action_allowed_by_lock(
            action=
                issuer_base.ACTION_PREVIEW,

            lock_body=
                interim,
        )

    except issuer_base.PermitIssuerStop:

        preview_blocked = True

    if not preview_blocked:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "preview is reachable before final "
            "issuer-aware lock."
        )

    issue_blocked = False

    try:

        issuer.require_action_allowed_by_lock(
            action=
                issuer_base.ACTION_ISSUE,

            lock_body=
                interim,
        )

    except issuer_base.PermitIssuerStop:

        issue_blocked = True

    if not issue_blocked:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "issue is reachable before final "
            "issuer-aware lock."
        )

    print(
        "PASS: V2 issuer v1.1 compatibility layer "
        "contains no broker mutation method."
    )

    print(
        "PASS: V2 issuer v1.1 targets position-aware schemas."
    )

    print(
        "PASS: V2 issuer v1.1 uses full frozen V5 writer."
    )

    print(
        "PASS: V2 issuer v1.1 CHECK is available."
    )

    print(
        "PASS: V2 issuer v1.1 PREVIEW is blocked "
        "before final issuer-aware lock."
    )

    print(
        "PASS: V2 issuer v1.1 ISSUE is blocked "
        "before final issuer-aware lock."
    )

    print(
        "PASS: Writer remains hard disconnected."
    )


def main():

    print(
        "Fund-100 static audit safety layer: v1.9"
    )

    verify_v2_issuer_v1_1()

    v18.main()


if __name__ == "__main__":

    main()
