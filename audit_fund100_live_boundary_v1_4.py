from __future__ import annotations

import audit_fund100_live_boundary as base
import fund100_experiment_runner as research
import fund100_alpaca_live_writer_disconnected_v1_1 as writer


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.4
# ============================================================
#
# v1.4 adds:
#
# - complete V5 research/live universe parity
# - disconnected writer v1.1 hard-stop verification
#
# It does not enable broker access.
# ============================================================


base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_permit_v2_simulator.py"
)

base.ALLOWED_LIVE_CREDENTIAL_SCRIPTS.add(
    "fund100_alpaca_live_permit_v2_issuer.py"
)


def verify_writer_v1_1():

    expected = (
        set(
            research.EQUITY_UNIVERSE
        )
        | {
            "ACWI",
        }
    )

    if (
        writer.ALLOWED_SYMBOLS
        != expected
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer v1.1 universe does not exactly "
            "match frozen research universe plus ACWI."
        )

    writer.validate_frozen_v5_execution_universe(
        research.EQUITY_UNIVERSE
    )

    if (
        writer.LIVE_WRITER_CONNECTED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer v1.1 connection flag is not FALSE."
        )

    try:

        writer.require_adapter_connected()

    except writer.LiveWriterDisconnected:

        pass

    else:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer v1.1 disconnect guard has a success path."
        )

    try:

        writer.submit_authorized_order_batch(
            intents=[],
            permit_package={},
            key="not-used",
            secret="not-used",
        )

    except writer.LiveWriterDisconnected:

        pass

    else:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer v1.1 submit entrypoint is reachable."
        )

    print(
        "PASS: Writer v1.1 frozen V5 universe parity."
    )

    print(
        "PASS: Writer v1.1 remains hard disconnected."
    )


def main():

    print(
        "Fund-100 static audit safety layer: v1.4"
    )

    verify_writer_v1_1()

    base.main()


if __name__ == "__main__":

    main()
