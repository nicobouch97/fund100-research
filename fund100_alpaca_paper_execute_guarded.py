from __future__ import annotations

import sys

import fund100_alpaca_paper_execute_bootstrap as executor

from fund100_broker_safety import (
    BrokerKillSwitchEngaged,
    get_kill_switch_state,
    require_broker_writes_allowed,
)


# ============================================================
# FUND-100 GUARDED ALPACA PAPER EXECUTOR
# ============================================================
#
# This wrapper places the independent Fund-100 kill switch
# in front of the existing validated paper execution engine.
#
# Defence in depth:
#
# 1. Kill switch checked before executor starts.
# 2. Actual POST-order function is wrapped with another
#    kill-switch check.
#
# Therefore changing state during execution also blocks the
# broker write path the next time it is reached.
# ============================================================


ORIGINAL_SUBMIT_PAPER_ORDER = (
    executor.submit_paper_order
)


def guarded_submit_paper_order(
    *args,
    **kwargs,
):

    # Last possible safety gate immediately
    # before the underlying broker POST.
    require_broker_writes_allowed()

    return (
        ORIGINAL_SUBMIT_PAPER_ORDER(
            *args,
            **kwargs,
        )
    )


def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 GUARDED BROKER EXECUTION"
    )

    print(
        "============================================"
    )

    state = (
        get_kill_switch_state()
    )

    print(
        f"\nBroker kill switch: {state}"
    )

    print(
        "Execution environment: ALPACA PAPER"
    )

    print(
        "Live broker endpoint: DISABLED"
    )

    # --------------------------------------------------------
    # FIRST INDEPENDENT SAFETY GATE
    # --------------------------------------------------------

    require_broker_writes_allowed()

    print(
        "Broker-write kill switch: CLEAR"
    )

    # --------------------------------------------------------
    # SECOND SAFETY GATE
    #
    # Every order POST made by the existing executor now
    # passes through guarded_submit_paper_order().
    # --------------------------------------------------------

    executor.submit_paper_order = (
        guarded_submit_paper_order
    )

    executor.main()


if __name__ == "__main__":

    try:

        main()

    except BrokerKillSwitchEngaged as exc:

        print(
            "\n============================================",
            file=sys.stderr,
        )

        print(
            "BROKER WRITE BLOCKED",
            file=sys.stderr,
        )

        print(
            "============================================",
            file=sys.stderr,
        )

        print(
            str(
                exc
            ),
            file=sys.stderr,
        )

        raise

    except Exception:

        raise
