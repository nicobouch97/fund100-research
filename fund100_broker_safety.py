from __future__ import annotations

import os


# ============================================================
# FUND-100 BROKER SAFETY
# ============================================================
#
# Independent broker-write kill switch.
#
# SAFE DEFAULT:
#
#     ENGAGED
#
# The only state that permits broker write operations is:
#
#     DISENGAGED
#
# Missing, empty, malformed or unexpected values all result
# in broker writes being blocked.
# ============================================================


KILL_SWITCH_VARIABLE = (
    "FUND100_BROKER_KILL_SWITCH"
)

ENGAGED = "ENGAGED"

DISENGAGED = "DISENGAGED"


class BrokerKillSwitchEngaged(
    RuntimeError
):
    pass


def get_kill_switch_state() -> str:

    raw = os.environ.get(
        KILL_SWITCH_VARIABLE,
        "",
    )

    value = str(
        raw
    ).strip().upper()

    # Missing variable = safe state.
    if value == "":

        return ENGAGED

    if value == ENGAGED:

        return ENGAGED

    if value == DISENGAGED:

        return DISENGAGED

    # Any malformed value also fails safe.
    return ENGAGED


def require_broker_writes_allowed() -> None:

    state = (
        get_kill_switch_state()
    )

    if state != DISENGAGED:

        raise BrokerKillSwitchEngaged(
            "KILL SWITCH ENGAGED: "
            "all Fund-100 broker write operations "
            "are disabled."
        )
