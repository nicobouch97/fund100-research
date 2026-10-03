from __future__ import annotations

import json
from datetime import datetime, timezone

import fund100_v5_002_shadow as base


# ============================================================
# FUND-100 V5-002 SHADOW FORWARD v1.1
# ============================================================
#
# Purpose:
#
# Prevent metadata-only shadow runs from rewriting
# shadow_state.json.
#
# v1.0 regenerated:
#
#     updated_utc
#
# on every run, including runs with zero new completed
# sessions. Because downstream live safety artifacts bind to
# the exact shadow-state SHA256, that made a no-op run appear
# to be a strategy-state change.
#
# v1.1 preserves the existing file byte-for-byte when the
# meaningful state is unchanged.
#
# A genuine strategy-state change still rewrites the state
# and receives a fresh updated_utc.
#
# NO BROKER CONNECTION.
# NO ORDERS.
# ============================================================


def _normalise_last_date(
    value,
) -> str:

    if hasattr(
        value,
        "date",
    ):

        return str(
            value.date()
        )

    return str(
        value
    )


def build_stable_state_body(
    state: dict,
    manifest_hash: str,
):

    nav = float(
        state[
            "nav"
        ]
    )

    benchmark_nav = float(
        state[
            "benchmark_nav"
        ]
    )

    if benchmark_nav == 0:

        raise RuntimeError(
            "Invalid zero benchmark NAV."
        )

    return {
        "strategy":
            base.MODEL_NAME,

        "manifest_hash":
            manifest_hash,

        "last_date":
            _normalise_last_date(
                state[
                    "last_date"
                ]
            ),

        "nav":
            nav,

        "benchmark_nav":
            benchmark_nav,

        "relative_wealth_vs_acwi":
            (
                nav
                / benchmark_nav
                - 1.0
            ),

        "satellite_weights":
            base.weights_to_dict(
                state[
                    "satellite_weights"
                ]
            ),

        "pending_target":
            base.weights_to_dict(
                state[
                    "pending_target"
                ]
            ),

        "pending_source":
            state[
                "pending_source"
            ],

        "cumulative_turnover":
            float(
                state[
                    "cumulative_turnover"
                ]
            ),

        "cumulative_cost_gbp":
            float(
                state[
                    "cumulative_cost_gbp"
                ]
            ),

        "emergency_signals":
            int(
                state[
                    "emergency_signals"
                ]
            ),

        "emergency_executions":
            int(
                state[
                    "emergency_executions"
                ]
            ),
    }


def build_stable_report_body(
    state: dict,
    manifest_hash: str,
    new_sessions: int,
    revisions: list[dict],
):

    nav = float(
        state[
            "nav"
        ]
    )

    benchmark_nav = float(
        state[
            "benchmark_nav"
        ]
    )

    if benchmark_nav == 0:

        raise RuntimeError(
            "Invalid zero benchmark NAV."
        )

    return {
        "strategy":
            base.MODEL_NAME,

        "manifest_hash":
            manifest_hash,

        "shadow_baseline":
            str(
                base.SHADOW_BASELINE_DATE.date()
            ),

        "first_eligible_forward_date":
            "2026-10-02",

        "last_processed_date":
            _normalise_last_date(
                state[
                    "last_date"
                ]
            ),

        "new_sessions_appended":
            int(
                new_sessions
            ),

        "paper_nav_gbp":
            nav,

        "benchmark_nav_gbp":
            benchmark_nav,

        "relative_wealth_vs_acwi":
            (
                nav
                / benchmark_nav
                - 1.0
            ),

        "cumulative_turnover":
            float(
                state[
                    "cumulative_turnover"
                ]
            ),

        "cumulative_cost_gbp":
            float(
                state[
                    "cumulative_cost_gbp"
                ]
            ),

        "emergency_signals":
            int(
                state[
                    "emergency_signals"
                ]
            ),

        "emergency_executions":
            int(
                state[
                    "emergency_executions"
                ]
            ),

        "market_revision_records_detected":
            len(
                revisions
            ),
    }


def _save_if_changed(
    path,
    timestamp_key: str,
    stable_body: dict,
    unchanged_message: str,
    changed_message: str,
):

    if path.exists():

        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:

            existing = json.load(
                handle
            )

        existing_body = {
            key:
                value
            for key, value
            in existing.items()
            if key
            != timestamp_key
        }

        if (
            existing_body
            == stable_body
        ):

            print(
                unchanged_message
            )

            return False

    output = {
        timestamp_key:
            datetime.now(
                timezone.utc
            ).isoformat(),

        **stable_body,
    }

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            output,
            handle,
            indent=2,
        )

        handle.write(
            "\n"
        )

    print(
        changed_message
    )

    return True


def save_state_v1_1(
    state: dict,
    manifest_hash: str,
):

    stable_body = (
        build_stable_state_body(
            state=
                state,

            manifest_hash=
                manifest_hash,
        )
    )

    return _save_if_changed(
        path=
            base.STATE_PATH,

        timestamp_key=
            "updated_utc",

        stable_body=
            stable_body,

        unchanged_message=(
            "V5-002 shadow state unchanged; "
            "preserving existing updated_utc."
        ),

        changed_message=(
            "V5-002 shadow state changed; "
            "writing new state snapshot."
        ),
    )


def save_report_v1_1(
    state: dict,
    manifest_hash: str,
    new_sessions: int,
    revisions: list[dict],
):

    stable_body = (
        build_stable_report_body(
            state=
                state,

            manifest_hash=
                manifest_hash,

            new_sessions=
                new_sessions,

            revisions=
                revisions,
        )
    )

    return _save_if_changed(
        path=
            base.REPORT_PATH,

        timestamp_key=
            "generated_utc",

        stable_body=
            stable_body,

        unchanged_message=(
            "V5-002 shadow report unchanged; "
            "preserving existing generated_utc."
        ),

        changed_message=(
            "V5-002 shadow report changed; "
            "writing new report snapshot."
        ),
    )


def install_v1_1_savers():

    base.save_state = (
        save_state_v1_1
    )

    base.save_report = (
        save_report_v1_1
    )


def main():

    print(
        "V5-002 shadow persistence layer: v1.1"
    )

    install_v1_1_savers()

    base.main()


if __name__ == "__main__":

    main()
