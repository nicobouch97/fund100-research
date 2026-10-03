from __future__ import annotations

import audit_fund100_live_boundary as base


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.3
# ============================================================
#
# Adds the real V2 permit issuer to the credential allowlist.
#
# The base audit still independently verifies that live Python
# files outside the disconnected writer contain no mutating
# HTTP methods.
# ============================================================


base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_permit_v2_simulator.py"
)

base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_permit_v2_issuer.py"
)


def main():

    print(
        "Fund-100 static audit safety layer: v1.3"
    )

    base.main()


if __name__ == "__main__":

    main()
