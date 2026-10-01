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
# Changes from v1.0:
#
# 1. Existing ledger/hash-chain integrity remains mandatory.
#
# 2. Historical market-data revisions are audited rather
#    than treated as fatal ledger corruption.
#
# 3. If more than one previously unseen completed market
#    session must be reconstructed in a single run, those
#    observations are explicitly labelled:
#
#        RECOVERED_AFTER_OUTAGE
#
#    rather than pristine FORWARD observations.
#
# 4. Original ledger rows are NEVER rewritten.
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
# REVISION LOG
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

    # Do not record the same observed revision every day.
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

    required = {
        "date",
        "strategy",
        "row_type",
        "chain_hash",
        "previous_chain_hash",
        "payload_json",
    }

    missing = (
        required
        - set(
            ledger.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Forward ledger is missing columns: "
            f"{sorted(missing)}"
        )

    duplicate_mask = (
        ledger.duplicated(
            subset=[
                "date",
                "strategy",
            ]
        )
    )

    if duplicate_mask.any():

        raise RuntimeError(
            "Duplicate strategy/date rows found "
            "in forward ledger."
        )

    strategy_hashes = (
        manifest[
            "strategy_hashes"
        ]
    )

    revisions = []

    for model_name in base.MODES:

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
                f"Ledger missing model {model_name}."
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
        )

        first = (
            subset.iloc[0]
        )

        if (
            first[
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
                first[
                    "date"
                ]
            )
            != base.HISTORICAL_CUTOFF
        ):

            raise RuntimeError(
                f"{model_name} baseline date "
                "does not match cutoff."
            )

        expected_previous = (
            "GENESIS"
        )

        for _, row in subset.iterrows():

            payload_json = str(
                row[
                    "payload_json"
                ]
            )

            payload = json.loads(
                payload_json
            )

            # ------------------------------------------------
            # IMMUTABLE STRATEGY CHECK
            # ------------------------------------------------

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
                    f"{model_name} strategy hash changed. "
                    "Refusing to rewrite history."
                )

            # ------------------------------------------------
            # HASH-CHAIN CHECK
            # ------------------------------------------------

            if (
                str(
                    row[
                        "previous_chain_hash"
                    ]
                )
                != expected_previous
            ):

                raise RuntimeError(
                    f"{model_name} ledger chain broken."
                )

            expected_chain = (
                base.sha256_text(
                    expected_previous
                    + "|"
                    + payload_json
                )
            )

            if (
                expected_chain
                != str(
                    row[
                        "chain_hash"
                    ]
                )
            ):

                raise RuntimeError(
                    f"{model_name} ledger hash mismatch."
                )

            # ------------------------------------------------
            # MARKET DATA CHECK
            #
            # v1.0 treated any vendor revision as fatal.
            #
            # v1.1 preserves the original ledger and records
            # the revision instead.
            # ------------------------------------------------

            date = pd.Timestamp(
                payload[
                    "date"
                ]
            )

            if date not in prices.index:

                raise RuntimeError(
                    "A ledger date no longer exists "
                    "in downloaded market data."
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

            expected_previous = (
                expected_chain
            )

    # --------------------------------------------------------
    # Every strategy must contain exactly the same dates.
    # --------------------------------------------------------

    dates_by_model = {}

    for model_name in base.MODES:

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
            base.MODES[0]
        ]
    )

    for model_name in base.MODES[1:]:

        if (
            dates_by_model[
                model_name
            ]
            != reference_dates
        ):

            raise RuntimeError(
                "Models do not contain identical "
                "forward observation dates."
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
        model:
            states[
                model
            ][
                "last_date"
            ]

        for model
        in base.MODES
    }

    if len(
        set(
            last_dates.values()
        )
    ) != 1:

        raise RuntimeError(
            "Model states have different "
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

    # --------------------------------------------------------
    # RECOVERY SEMANTICS
    #
    # One newly completed session:
    #     ordinary FORWARD observation.
    #
    # Multiple unseen sessions appearing in one run:
    #     system was unavailable / behind.
    #
    # Those sessions are retained for accounting, but clearly
    # distinguished from pristine daily forward observations.
    # --------------------------------------------------------

    recovery_mode = (
        len(
            new_dates
        )
        > 1
    )

    if recovery_mode:

        row_type = (
            "RECOVERED_AFTER_OUTAGE"
        )

    else:

        row_type = (
            "FORWARD"
        )

    previous_hashes = (
        base.latest_chain_hashes(
            ledger
        )
    )

    new_rows = []

    for date in new_dates:

        snapshot = (
            base.market_snapshot_hash(
                date=
                    date,

                prices=
                    prices,

                benchmark=
                    benchmark,
            )
        )

        for model_name in base.MODES:

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
                        snapshot,

                    signals=
                        signals,

                    daily=
                        daily,
                )
            )

            row = (
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
                row[
                    "chain_hash"
                ]
            )

            new_rows.append(
                row
            )

    if new_rows:

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

    # Existing v1.0 manifest deliberately remains valid.
    base.ensure_forward_manifest(
        manifest
    )

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

    # --------------------------------------------------------
    # LOAD OR INITIALISE
    # --------------------------------------------------------

    if not base.LEDGER_PATH.exists():

        print(
            "\nNo existing forward ledger found."
        )

        print(
            "Creating baseline ledger..."
        )

        (
            ledger,
            states,
        ) = base.initialise_ledger(
            signals=
                signals,

            prices=
                prices,

            benchmark=
                benchmark,

            manifest=
                manifest,
        )

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

        if revisions:

            unique_dates = sorted(
                set(
                    item[
                        "date"
                    ]
                    for item
                    in revisions
                )
            )

            print(
                "\nMARKET DATA REVISION WARNING"
            )

            print(
                "The data vendor changed historical "
                "adjusted-price observations."
            )

            print(
                "Original Fund-100 ledger rows "
                "were NOT modified."
            )

            print(
                "Affected stored dates:"
            )

            for date in unique_dates:

                print(
                    f"  - {date}"
                )

            print(
                f"Revision audit: "
                f"{REVISION_LOG_PATH}"
            )

        else:

            print(
                "No historical vendor revisions "
                "were detected."
            )

        states = (
            base.restore_states_from_ledger(
                ledger
            )
        )

    # --------------------------------------------------------
    # APPEND NEW SESSIONS
    # --------------------------------------------------------

    (
        ledger,
        states,
        new_session_count,
        recovered_count,
    ) = append_new_sessions_v11(
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

    # --------------------------------------------------------
    # VALIDATE AGAIN
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # SAVE CURRENT STATE
    # --------------------------------------------------------

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

    if recovered_count:

        print(
            "\nRecovered observations are retained "
            "for accounting and diagnostics."
        )

        print(
            "They should NOT be treated as pristine "
            "strict-forward evidence because they "
            "were reconstructed after the outage."
        )

        print(
            "\nStrict daily forward evidence resumes "
            "with the next session processed normally "
            "after this recovery run."
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
