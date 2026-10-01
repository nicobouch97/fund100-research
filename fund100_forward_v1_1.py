from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import fund100_forward as base
from fund100 import load_config


# ============================================================
# FUND-100 FORWARD LAB v1.1
# ============================================================
#
# v1.1 keeps the original append-only Fund-100 ledger intact
# while allowing normal market-data-vendor revisions to be
# audited instead of permanently stopping the system.
#
# Original ledger observations are NEVER rewritten.
#
# If several completed sessions must be reconstructed after
# an outage, they are labelled:
#
#     RECOVERED_AFTER_OUTAGE
#
# rather than ordinary FORWARD observations.
# ============================================================


REVISION_LOG_PATH = Path(
    "forward_outputs/market_revision_log.csv"
)

REVISION_COLUMNS = [
    "detected_utc",
    "date",
    "strategy",
    "ledger_row_type",
    "stored_market_hash",
    "current_market_hash",
]


# ============================================================
# REVISION AUDIT LOG
# ============================================================

def record_market_revisions(
    revisions: list[dict],
) -> None:

    if not revisions:
        return

    incoming = pd.DataFrame(
        revisions
    )

    if REVISION_LOG_PATH.exists():

        existing = pd.read_csv(
            REVISION_LOG_PATH,
            dtype=str,
        )

    else:

        existing = pd.DataFrame(
            columns=REVISION_COLUMNS
        )

    combined = pd.concat(
        [
            existing,
            incoming,
        ],
        ignore_index=True,
    )

    # Do not record the same vendor revision repeatedly.
    combined = combined.drop_duplicates(
        subset=[
            "date",
            "strategy",
            "stored_market_hash",
            "current_market_hash",
        ],
        keep="first",
    )

    combined = combined[
        REVISION_COLUMNS
    ]

    combined.to_csv(
        REVISION_LOG_PATH,
        index=False,
    )


# ============================================================
# LEDGER VALIDATION
# ============================================================

def validate_existing_ledger_v11(
    ledger: pd.DataFrame,
    prices: pd.DataFrame,
    benchmark: pd.Series,
    manifest: dict,
) -> list[dict]:

    required_columns = {
        "date",
        "strategy",
        "row_type",
        "chain_hash",
        "previous_chain_hash",
        "payload_json",
    }

    missing_columns = (
        required_columns
        - set(
            ledger.columns
        )
    )

    if missing_columns:

        raise RuntimeError(
            "Forward ledger is missing columns: "
            f"{sorted(missing_columns)}"
        )

    if ledger.duplicated(
        subset=[
            "date",
            "strategy",
        ]
    ).any():

        raise RuntimeError(
            "Duplicate strategy/date rows found "
            "in the Forward Lab ledger."
        )

    strategy_hashes = (
        manifest[
            "strategy_hashes"
        ]
    )

    revisions = []

    # ========================================================
    # Validate each frozen model.
    # ========================================================

    for model_name in base.MODELS:

        subset = (
            ledger[
                ledger[
                    "strategy"
                ]
                == model_name
            ]
            .copy()
        )

        if subset.empty:

            raise RuntimeError(
                f"Ledger missing model "
                f"{model_name}."
            )

        subset[
            "date_dt"
        ] = pd.to_datetime(
            subset[
                "date"
            ]
        )

        subset = (
            subset
            .sort_values(
                "date_dt"
            )
            .reset_index(
                drop=True
            )
        )

        first_row = (
            subset.iloc[0]
        )

        if (
            first_row[
                "row_type"
            ]
            != "BASELINE"
        ):

            raise RuntimeError(
                f"{model_name} does not begin "
                "with a BASELINE row."
            )

        if (
            pd.Timestamp(
                first_row[
                    "date"
                ]
            )
            != base.HISTORICAL_CUTOFF
        ):

            raise RuntimeError(
                f"{model_name} baseline date "
                "does not match the historical cutoff."
            )

        expected_previous_hash = (
            "GENESIS"
        )

        # ====================================================
        # Validate every immutable ledger row.
        # ====================================================

        for _, row in subset.iterrows():

            payload_json = str(
                row[
                    "payload_json"
                ]
            )

            payload = json.loads(
                payload_json
            )

            if (
                payload[
                    "strategy"
                ]
                != model_name
            ):

                raise RuntimeError(
                    "Ledger payload strategy mismatch."
                )

            if (
                payload[
                    "strategy_hash"
                ]
                != strategy_hashes[
                    model_name
                ]
            ):

                raise RuntimeError(
                    f"{model_name} strategy definition "
                    "has changed. Refusing to continue."
                )

            if (
                str(
                    row[
                        "previous_chain_hash"
                    ]
                )
                != expected_previous_hash
            ):

                raise RuntimeError(
                    f"{model_name} ledger chain is broken."
                )

            expected_chain_hash = (
                base.sha256_text(
                    expected_previous_hash
                    + "|"
                    + payload_json
                )
            )

            if (
                expected_chain_hash
                != str(
                    row[
                        "chain_hash"
                    ]
                )
            ):

                raise RuntimeError(
                    f"{model_name} ledger hash mismatch."
                )

            # =================================================
            # Market-data revision audit.
            #
            # The permanent ledger remains unchanged even if
            # today's Yahoo adjusted history differs from the
            # historical snapshot originally recorded.
            # =================================================

            date = pd.Timestamp(
                payload[
                    "date"
                ]
            )

            if date not in prices.index:

                raise RuntimeError(
                    "A date stored in the ledger "
                    "no longer exists in downloaded data."
                )

            current_market_hash = (
                base.market_snapshot_hash(
                    date=
                        date,
                    prices=
                        prices,
                    benchmark=
                        benchmark,
                )
            )

            stored_market_hash = str(
                payload[
                    "market_snapshot_hash"
                ]
            )

            if (
                current_market_hash
                != stored_market_hash
            ):

                revisions.append({
                    "detected_utc":
                        datetime.now(
                            timezone.utc
                        ).isoformat(),

                    "date":
                        str(
                            date.date()
                        ),

                    "strategy":
                        model_name,

                    "ledger_row_type":
                        str(
                            payload[
                                "row_type"
                            ]
                        ),

                    "stored_market_hash":
                        stored_market_hash,

                    "current_market_hash":
                        current_market_hash,
                })

            expected_previous_hash = (
                expected_chain_hash
            )

    # ========================================================
    # Every frozen model must contain the same dates.
    # ========================================================

    dates_by_model = {}

    for model_name in base.MODELS:

        dates_by_model[
            model_name
        ] = set(
            ledger.loc[
                ledger[
                    "strategy"
                ]
                == model_name,
                "date",
            ]
        )

    reference_dates = (
        dates_by_model[
            base.MODELS[0]
        ]
    )

    for model_name in base.MODELS[1:]:

        if (
            dates_by_model[
                model_name
            ]
            != reference_dates
        ):

            raise RuntimeError(
                "Forward models do not contain "
                "identical observation dates."
            )

    return revisions


# ============================================================
# APPEND NEW COMPLETED SESSIONS
# ============================================================

def append_new_sessions_v11(
    ledger: pd.DataFrame,
    states: dict,
    signals: dict,
    prices: pd.DataFrame,
    benchmark: pd.Series,
    manifest: dict,
):

    strategy_hashes = (
        manifest[
            "strategy_hashes"
        ]
    )

    last_dates = {
        model_name:
            states[
                model_name
            ][
                "last_date"
            ]

        for model_name
        in base.MODELS
    }

    if len(
        set(
            last_dates.values()
        )
    ) != 1:

        raise RuntimeError(
            "Frozen models have different "
            "last processed dates."
        )

    last_date = list(
        last_dates.values()
    )[0]

    new_dates = (
        prices.index[
            prices.index
            > last_date
        ]
    )

    if len(
        new_dates
    ) == 0:

        return (
            ledger,
            states,
            0,
            0,
        )

    # More than one missed session means the system is
    # reconstructing observations after an outage.
    recovery_mode = (
        len(
            new_dates
        )
        > 1
    )

    row_type = (
        "RECOVERED_AFTER_OUTAGE"
        if recovery_mode
        else "FORWARD"
    )

    previous_hashes = (
        base.latest_chain_hashes(
            ledger
        )
    )

    new_rows = []

    # ========================================================
    # Process missing sessions chronologically.
    # ========================================================

    for date in new_dates:

        market_hash = (
            base.market_snapshot_hash(
                date=
                    date,
                prices=
                    prices,
                benchmark=
                    benchmark,
            )
        )

        for model_name in base.MODELS:

            state = (
                states[
                    model_name
                ]
            )

            daily = (
                base.process_one_day(
                    state=
                        state,
                    date=
                        date,
                    signals=
                        signals,
                    model_name=
                        model_name,
                    cost_bps=
                        base.ONE_WAY_COST_BPS,
                    zero_market_return=
                        False,
                )
            )

            payload = (
                base.build_payload(
                    row_type=
                        row_type,
                    state=
                        state,
                    date=
                        date,
                    model_name=
                        model_name,
                    strategy_hash=
                        strategy_hashes[
                            model_name
                        ],
                    market_hash=
                        market_hash,
                    signals=
                        signals,
                    daily=
                        daily,
                )
            )

            ledger_row = (
                base.payload_to_ledger_row(
                    payload=
                        payload,
                    previous_chain_hash=
                        previous_hashes[
                            model_name
                        ],
                )
            )

            previous_hashes[
                model_name
            ] = (
                ledger_row[
                    "chain_hash"
                ]
            )

            new_rows.append(
                ledger_row
            )

    # ========================================================
    # Append permanently.
    # ========================================================

    ledger = pd.concat(
        [
            ledger,
            pd.DataFrame(
                new_rows
            ),
        ],
        ignore_index=True,
    )

    ledger[
        "date_dt"
    ] = pd.to_datetime(
        ledger[
            "date"
        ]
    )

    ledger = (
        ledger
        .sort_values(
            [
                "date_dt",
                "strategy",
            ]
        )
        .drop(
            columns=[
                "date_dt"
            ]
        )
        .reset_index(
            drop=True
        )
    )

    ledger.to_csv(
        base.LEDGER_PATH,
        index=False,
        float_format="%.12g",
    )

    recovered_count = (
        len(
            new_dates
        )
        if recovery_mode
        else 0
    )

    return (
        ledger,
        states,
        len(
            new_dates
        ),
        recovered_count,
    )


# ============================================================
# REVISION SUMMARY
# ============================================================

def print_revision_summary(
    revisions: list[dict],
) -> None:

    if not revisions:

        print(
            "No historical vendor revisions detected."
        )

        return

    affected_dates = sorted(
        {
            item[
                "date"
            ]
            for item
            in revisions
        }
    )

    print(
        "\n============================================"
    )

    print(
        "MARKET DATA REVISION WARNING"
    )

    print(
        "============================================"
    )

    print(
        "The market-data vendor changed historical "
        "adjusted-price observations."
    )

    print(
        "Original Fund-100 ledger rows were NOT modified."
    )

    print(
        "\nAffected stored dates:"
    )

    for date in affected_dates:

        print(
            f"  - {date}"
        )

    print(
        "\nRevision records detected:"
    )

    print(
        len(
            revisions
        )
    )

    print(
        "\nRevision audit file:"
    )

    print(
        REVISION_LOG_PATH
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "============================================"
    )

    print(
        "FUND-100 FORWARD LAB v1.1"
    )

    print(
        "============================================"
    )

    print(
        f"\nHistorical research cutoff: "
        f"{base.HISTORICAL_CUTOFF.date()}"
    )

    # ========================================================
    # Frozen configuration
    # ========================================================

    print(
        "\nLoading frozen configuration..."
    )

    cfg, config_hash = (
        load_config()
    )

    print(
        "Loaded v1 config hash:"
    )

    print(
        config_hash
    )

    if (
        config_hash
        != base.V1_CONFIG_HASH
    ):

        raise RuntimeError(
            "Frozen v1 configuration hash changed. "
            "Forward Lab refuses to continue."
        )

    # ========================================================
    # Original strategy manifest
    # ========================================================

    manifest = (
        base.build_forward_manifest()
    )

    protocol_hash = (
        base.sha256_json(
            manifest
        )
    )

    print(
        "\nForward protocol SHA256:"
    )

    print(
        protocol_hash
    )

    base.ensure_forward_manifest(
        manifest
    )

    # ========================================================
    # Completed market data
    # ========================================================

    print(
        "\nDownloading completed market data..."
    )

    prices, benchmark = (
        base.load_completed_market_data(
            cfg
        )
    )

    print(
        f"Completed market data: "
        f"{prices.index.min().date()} "
        f"to "
        f"{prices.index.max().date()}"
    )

    print(
        "\nBuilding frozen signals..."
    )

    signals = (
        base.build_signals(
            prices=
                prices,
            benchmark=
                benchmark,
        )
    )

    # ========================================================
    # Existing append-only ledger
    # ========================================================

    if not base.LEDGER_PATH.exists():

        print(
            "\nNo existing Forward Lab ledger found."
        )

        print(
            "Creating original baseline..."
        )

        (
            ledger,
            states,
        ) = (
            base.initialise_ledger(
                signals=
                    signals,
                prices=
                    prices,
                benchmark=
                    benchmark,
                manifest=
                    manifest,
            )
        )

        revisions = []

    else:

        print(
            "\nExisting forward ledger found."
        )

        ledger = pd.read_csv(
            base.LEDGER_PATH
        )

        print(
            "Validating immutable hash chain..."
        )

        revisions = (
            validate_existing_ledger_v11(
                ledger=
                    ledger,
                prices=
                    prices,
                benchmark=
                    benchmark,
                manifest=
                    manifest,
            )
        )

        record_market_revisions(
            revisions
        )

        print(
            "Ledger hash-chain integrity passed."
        )

        print_revision_summary(
            revisions
        )

        states = (
            base.restore_states_from_ledger(
                ledger
            )
        )

    # ========================================================
    # Catch up any unseen completed sessions
    # ========================================================

    (
        ledger,
        states,
        new_session_count,
        recovered_count,
    ) = (
        append_new_sessions_v11(
            ledger=
                ledger,
            states=
                states,
            signals=
                signals,
            prices=
                prices,
            benchmark=
                benchmark,
            manifest=
                manifest,
        )
    )

    # ========================================================
    # Validate updated permanent ledger again
    # ========================================================

    revisions_after = (
        validate_existing_ledger_v11(
            ledger=
                ledger,
            prices=
                prices,
            benchmark=
                benchmark,
            manifest=
                manifest,
        )
    )

    record_market_revisions(
        revisions_after
    )

    # ========================================================
    # Save latest state
    # ========================================================

    base.save_state_snapshot(
        states=
            states,
        manifest=
            manifest,
    )

    base.build_latest_report(
        states=
            states,
        prices=
            prices,
        signals=
            signals,
        new_session_count=
            new_session_count,
        manifest=
            manifest,
    )

    # ========================================================
    # Existing Fund-100 report
    # ========================================================

    base.print_report(
        states=
            states,
        prices=
            prices,
        signals=
            signals,
        manifest=
            manifest,
        new_session_count=
            new_session_count,
    )

    # ========================================================
    # v1.1 recovery report
    # ========================================================

    print(
        "\n============================================"
    )

    print(
        "v1.1 RECOVERY STATUS"
    )

    print(
        "============================================"
    )

    print(
        f"New completed sessions processed: "
        f"{new_session_count}"
    )

    print(
        f"Sessions labelled "
        f"RECOVERED_AFTER_OUTAGE: "
        f"{recovered_count}"
    )

    if recovered_count > 0:

        print(
            "\nRecovered sessions are retained for "
            "portfolio accounting and diagnostics."
        )

        print(
            "They are not classified as pristine "
            "strict-forward observations because "
            "they were reconstructed after the outage."
        )

        print(
            "\nThe next normally processed completed "
            "session will again receive the FORWARD label."
        )

    elif new_session_count == 1:

        print(
            "\nOne normal FORWARD session was appended."
        )

    else:

        print(
            "\nNo new completed market sessions "
            "were available."
        )

    print(
        "\nOriginal ledger observations were "
        "never rewritten."
    )

    print(
        "Historical vendor revisions were "
        "recorded separately."
    )

    print(
        "\n============================================"
    )

    print(
        "FORWARD LAB v1.1 RUN COMPLETE"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":
    main()
