from __future__ import annotations

import fund100_alpaca_live_permit_v2_simulator as v2


def test_simulation_schema_is_not_writer_schema():

    assert (
        v2.SIMULATION_SCHEMA
        != v2.FUTURE_WRITER_SCHEMA
    )


def test_simulated_cap_is_zero():

    assert (
        v2.SIMULATED_MAX_LIVE_EXECUTION_NOTIONAL_USD
        == 0.0
    )


def test_replay_detection():

    ledger = {
        "consumed_event_ids": [
            "event-a",
        ]
    }

    assert (
        v2.event_is_consumed(
            event_id="event-a",
            ledger=ledger,
        )
        is True
    )

    assert (
        v2.event_is_consumed(
            event_id="event-b",
            ledger=ledger,
        )
        is False
    )


def test_even_perfect_simulated_conditions_do_not_issue():

    compiler_package = {
        "compiler_sha256":
            "abc123",

        "compiler": {
            "strategy":
                "V5-002_SHADOW",

            "strategy_state_date":
                "2099-01-01",

            "compiler_mode":
                "current",

            "status":
                "GENUINE_SCHEDULED_EVENT",

            "genuine_scheduled_event":
                True,
        },
    }

    session = {
        "session_binding_sha256":
            "session-hash",

        "candidate_expiry":
            "2099-01-01T16:00:00-04:00",
    }

    conditions = {
        "source_mode_is_current":
            True,

        "source_status_is_genuine_event":
            True,

        "source_genuine_event_flag":
            True,

        "manual_approval_present":
            True,

        "permit_built_while_kill_switch_engaged":
            True,

        "account_status_active":
            True,

        "account_not_blocked":
            True,

        "trading_not_blocked":
            True,

        "no_open_orders":
            True,

        "market_session_open":
            True,

        "permit_expiry_is_future":
            True,

        "event_not_previously_consumed":
            True,

        # Even this is deliberately set True to prove that
        # the simulator itself still cannot issue.
        "positive_execution_ceiling_configured":
            True,
    }

    package = (
        v2.build_v2_simulation(
            compiler_package=
                compiler_package,

            account_binding_sha256=
                "account-hash",

            event_id=
                "event-test",

            event_binding_sha256=
                "event-hash",

            session=
                session,

            conditions=
                conditions,

            replay_consumed=
                False,
        )
    )

    body = (
        package[
            "permit_v2_simulation"
        ]
    )

    assert (
        body[
            "all_contract_conditions_satisfied"
        ]
        is True
    )

    assert (
        body[
            "simulation_only"
        ]
        is True
    )

    assert (
        body[
            "permit_issued"
        ]
        is False
    )

    assert (
        body[
            "live_execution_authorized"
        ]
        is False
    )

    assert (
        body[
            "network_write_capability"
        ]
        is False
    )

    assert (
        body[
            "broker_write_mode"
        ]
        == "DISABLED"
    )

    v2.assert_simulation_cannot_authorize(
        body
    )
