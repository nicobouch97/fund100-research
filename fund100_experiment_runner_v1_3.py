from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

import fund100_experiment_runner as base
import fund100_experiment_runner_v1_2 as v12


SNAPSHOT_PATH = Path(
    "research_lab/frozen_history_v2.csv"
)

SNAPSHOT_MANIFEST_PATH = Path(
    "research_lab/frozen_history_v2_manifest.json"
)


def sha256_file(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as f:

        while True:

            chunk = f.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def load_frozen_history(
    cfg: dict,
    protocol: dict,
):

    # cfg deliberately unused.
    # Historical experiments no longer query Yahoo.

    if not SNAPSHOT_PATH.exists():

        raise RuntimeError(
            "Frozen Research Dataset v2 is missing."
        )

    if not SNAPSHOT_MANIFEST_PATH.exists():

        raise RuntimeError(
            "Frozen Research Dataset v2 manifest "
            "is missing."
        )

    with SNAPSHOT_MANIFEST_PATH.open(
        "r"
    ) as f:

        manifest = json.load(
            f
        )

    current_file_hash = (
        sha256_file(
            SNAPSHOT_PATH
        )
    )

    if (
        current_file_hash
        != manifest[
            "file_sha256"
        ]
    ):

        raise RuntimeError(
            "Frozen Research Dataset v2 file "
            "hash mismatch. Refusing to run."
        )

    if (
        str(
            protocol[
                "historical_cutoff"
            ]
        )
        != str(
            manifest[
                "historical_cutoff"
            ]
        )
    ):

        raise RuntimeError(
            "Research protocol cutoff does not "
            "match Frozen Dataset v2."
        )

    frozen = pd.read_csv(
        SNAPSHOT_PATH,
        parse_dates=[
            "date"
        ],
    )

    frozen = (
        frozen
        .set_index(
            "date"
        )
        .sort_index()
    )

    required_columns = (
        list(
            base.EQUITY_UNIVERSE
        )
        + [
            "ACWI_BENCHMARK"
        ]
    )

    missing = [
        column
        for column
        in required_columns
        if column
        not in frozen.columns
    ]

    if missing:

        raise RuntimeError(
            "Frozen Dataset v2 missing columns: "
            f"{missing}"
        )

    prices = (
        frozen[
            base.EQUITY_UNIVERSE
        ]
        .copy()
    )

    benchmark = (
        frozen[
            "ACWI_BENCHMARK"
        ]
        .copy()
    )

    return (
        prices,
        benchmark,
    )


def validate_frozen_history(
    prices: pd.DataFrame,
    benchmark: pd.Series,
    protocol: dict,
) -> str:

    with SNAPSHOT_MANIFEST_PATH.open(
        "r"
    ) as f:

        manifest = json.load(
            f
        )

    current_file_hash = (
        sha256_file(
            SNAPSHOT_PATH
        )
    )

    if (
        current_file_hash
        != manifest[
            "file_sha256"
        ]
    ):

        raise RuntimeError(
            "Frozen Research Dataset v2 was modified."
        )

    data_hash = (
        base.calculate_data_hash(
            prices=
                prices,

            benchmark=
                benchmark,
        )
    )

    if (
        data_hash
        != manifest[
            "research_data_sha256"
        ]
    ):

        raise RuntimeError(
            "Frozen Research Dataset v2 data "
            "hash mismatch."
        )

    print(
        "\nUsing immutable Research Dataset v2."
    )

    print(
        "Frozen dataset SHA256:"
    )

    print(
        data_hash
    )

    return data_hash


def main():

    # --------------------------------------------------------
    # Replace only the historical data source used by the
    # Research Lab.
    #
    # All strategy/backtest/registry logic remains unchanged.
    # --------------------------------------------------------

    base.load_historical_data = (
        load_frozen_history
    )

    base.ensure_data_manifest = (
        validate_frozen_history
    )

    # v1.2 references the same base module, but assign these
    # explicitly as an additional safeguard.
    v12.base.load_historical_data = (
        load_frozen_history
    )

    v12.base.ensure_data_manifest = (
        validate_frozen_history
    )

    v12.main()


if __name__ == "__main__":
    main()
