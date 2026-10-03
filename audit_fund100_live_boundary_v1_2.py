from __future__ import annotations

import audit_fund100_live_boundary as base


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.2
# ============================================================
#
# Extends v1.1 to allow the V2 permit simulator to receive
# live credentials.
#
# The simulator itself contains no HTTP write path, so the
# existing Python write-path audit still independently checks
# that it remains read-only.
# ============================================================


base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_permit_v2_simulator.py"
)


def main():

    print(
        "Fund-100 static audit safety layer: v1.2"
    )

    base.main()


if __name__ == "__main__":

    main()
