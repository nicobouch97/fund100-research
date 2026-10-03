from __future__ import annotations

import json

import pandas as pd

import fund100_experiment_runner as research_base
import fund100_v5_002_shadow as base
import fund100_v5_002_shadow_v1_1 as stable


def make_state():

    weights = pd.Series(
        0.0,
        index=
            research_base.EQUITY_UNIVERSE,
        dtype=float,
    )

    weights[
        "EEM"
    ] = 0.083

    weights[
        "XLV"
    ] = 0.083

    weights[
        "XLE"
    ] = 0.084

    return {
        "last_date":
            pd.Timestamp(
                "2026-10-01"
            ),

        "nav":
            100.0,

        "benchmark_nav":
            100.0,

        "satellite_weights":
            weights,

        "pending_target":
            None,

        "pending_source":
            None,

        "cumulative_turnover":
            0.0,

        "cumulative_cost_gbp":
            0.0,

        "emergency_signals":
            0,

        "emergency_executions":
            0,
    }


def test_noop_state_save_is_byte_stable(
    tmp_path,
    monkeypatch,
):

    state_path = (
        tmp_path
        / "shadow_state.json"
    )

    monkeypatch.setattr(
        base,
        "STATE_PATH",
        state_path,
    )

    state = (
        make_state()
    )

    stable.save_state_v1_1(
        state=
            state,

        manifest_hash=
            "manifest-test",
    )

    first = (
        state_path.read_bytes()
    )

    with state_path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        first_json = json.load(
            handle
        )

    first_timestamp = (
        first_json[
            "updated_utc"
        ]
    )

    stable.save_state_v1_1(
        state=
            state,

        manifest_hash=
            "manifest-test",
    )

    second = (
        state_path.read_bytes()
    )

    with state_path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        second_json = json.load(
            handle
        )

    assert (
        first
        == second
    )

    assert (
        second_json[
            "updated_utc"
        ]
        == first_timestamp
    )


def test_real_state_change_rewrites_state(
    tmp_path,
    monkeypatch,
):

    state_path = (
        tmp_path
        / "shadow_state.json"
    )

    monkeypatch.setattr(
        base,
        "STATE_PATH",
        state_path,
    )

    state = (
        make_state()
    )

    stable.save_state_v1_1(
        state=
            state,

        manifest_hash=
            "manifest-test",
    )

    first = (
        state_path.read_bytes()
    )

    state[
        "nav"
    ] = 101.0

    stable.save_state_v1_1(
        state=
            state,

        manifest_hash=
            "manifest-test",
    )

    second = (
        state_path.read_bytes()
    )

    assert (
        first
        != second
    )

    with state_path.open(
        "r",
        encoding="utf-8",
    ) as handle:

        stored = json.load(
            handle
        )

    assert (
        stored[
            "nav"
        ]
        == 101.0
    )


def test_noop_report_save_is_byte_stable(
    tmp_path,
    monkeypatch,
):

    report_path = (
        tmp_path
        / "latest_shadow_report.json"
    )

    monkeypatch.setattr(
        base,
        "REPORT_PATH",
        report_path,
    )

    state = (
        make_state()
    )

    stable.save_report_v1_1(
        state=
            state,

        manifest_hash=
            "manifest-test",

        new_sessions=
            0,

        revisions=
            [],
    )

    first = (
        report_path.read_bytes()
    )

    stable.save_report_v1_1(
        state=
            state,

        manifest_hash=
            "manifest-test",

        new_sessions=
            0,

        revisions=
            [],
    )

    second = (
        report_path.read_bytes()
    )

    assert (
        first
        == second
    )
