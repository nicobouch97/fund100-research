from __future__ import annotations

import fund100_alpaca_live_activation_rehearsal as rehearsal
import fund100_alpaca_live_writer_disconnected as writer


def test_rehearsal_schema_is_never_writer_schema():

    assert (
        rehearsal.REHEARSAL_SCHEMA
        != writer.REQUIRED_PERMIT_SCHEMA
    )


def test_synthetic_cap_is_positive_but_not_executable():

    assert (
        rehearsal.SYNTHETIC_CAP_SENTINEL_USD
        > 0.0
    )

    compiler = (
        rehearsal.build_fake_compiler_package()
    )

    account = (
        rehearsal.build_fake_account()
    )

    session = (
        rehearsal.build_fake_session()
    )

    event_id, event_hash = (
        rehearsal.build_event_binding(
            compiler
        )
    )

    conditions = (
        rehearsal.evaluate_positive_path(
            compiler_package=
                compiler,

            account=
                account,

            session=
                session,

            event_id=
                event_id,

            consumed_event_ids=
                set(),
        )
    )

    package = (
        rehearsal.build_rehearsal_permit(
            compiler_package=
                compiler,

            account_binding_sha256=
                rehearsal.build_fake_account_binding(),

            event_id=
                event_id,

            event_binding_sha256=
                event_hash,

            session=
                session,

            conditions=
                conditions,
        )
    )

    body = (
        package[
            "rehearsal"
        ]
    )

    assert (
        body[
            "synthetic_execution_ceiling_usd"
        ]
        > 0.0
    )

    assert (
        body[
            "max_live_execution_notional_usd"
        ]
        == 0.0
    )

    assert (
        body[
            "permit_issued"
        ]
        is False
    )


def test_every_positive_path_condition_can_pass():

    compiler = (
        rehearsal.build_fake_compiler_package()
    )

    account = (
        rehearsal.build_fake_account()
    )

    session = (
        rehearsal.build_fake_session()
    )

    event_id, _ = (
        rehearsal.build_event_binding(
            compiler
        )
    )

    conditions = (
        rehearsal.evaluate_positive_path(
            compiler_package=
                compiler,

            account=
                account,

            session=
                session,

            event_id=
                event_id,

            consumed_event_ids=
                set(),
        )
    )

    assert all(
        conditions.values()
    )


def test_replay_second_use_fails():

    compiler = (
        rehearsal.build_fake_compiler_package()
    )

    account = (
        rehearsal.build_fake_account()
    )

    session = (
        rehearsal.build_fake_session()
    )

    event_id, _ = (
        rehearsal.build_event_binding(
            compiler
        )
    )

    result = (
        rehearsal.rehearse_replay_protection(
            compiler_package=
                compiler,

            account=
                account,

            session=
                session,

            event_id=
                event_id,
        )
    )

    assert (
        result[
            "first_attempt_all_conditions_pass"
        ]
        is True
    )

    assert (
        result[
            "second_attempt_all_conditions_pass"
        ]
        is False
    )

    assert (
        result[
            "second_attempt_replay_condition"
        ]
        is False
    )


def test_writer_rejects_rehearsal_permit():

    compiler = (
        rehearsal.build_fake_compiler_package()
    )

    account = (
        rehearsal.build_fake_account()
    )

    session = (
        rehearsal.build_fake_session()
    )

    event_id, event_hash = (
        rehearsal.build_event_binding(
            compiler
        )
    )

    conditions = (
        rehearsal.evaluate_positive_path(
            compiler_package=
                compiler,

            account=
                account,

            session=
                session,

            event_id=
                event_id,

            consumed_event_ids=
                set(),
        )
    )

    package = (
        rehearsal.build_rehearsal_permit(
            compiler_package=
                compiler,

            account_binding_sha256=
                rehearsal.build_fake_account_binding(),

            event_id=
                event_id,

            event_binding_sha256=
                event_hash,

            session=
                session,

            conditions=
                conditions,
        )
    )

    result = (
        rehearsal.prove_writer_rejects_rehearsal(
            package
        )
    )

    assert (
        result[
            "writer_rejected"
        ]
        is True
    )


def test_writer_still_disconnected():

    result = (
        rehearsal.prove_writer_remains_disconnected()
    )

    assert (
        result[
            "writer_disconnected"
        ]
        is True
    )
