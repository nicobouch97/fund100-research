from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import fund100_experiment_runner as base
from fund100 import load_config


SNAPSHOT_PATH = Path(
    "research_lab/frozen_history_v2.csv"
)

MANIFEST_PATH = Path(
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


def main():

    print(
        "============================================"
    )

    print(
        "FREEZE FUND-100 RESEARCH DATASET v2"
    )

    print(
        "============================================"
    )

    if (
        SNAPSHOT_PATH.exists()
        or MANIFEST_PATH.exists()
    ):

        raise RuntimeError(
            "Frozen Research Dataset v2 already exists. "
            "Refusing to overwrite it."
        )

    protocol = (
        base.load_protocol()
    )

    cfg, config_hash = (
        load_config()
    )

    print(
        "\nFrozen v1 config SHA256:"
    )

    print(
        config_hash
    )

    print(
        "\nDownloading historical data one final time..."
    )

    prices, benchmark = (
        base.load_historical_data(
            cfg=
                cfg,

            protocol=
                protocol,
        )
    )

    snapshot = (
        prices[
            base.EQUITY_UNIVERSE
        ]
        .copy()
    )

    snapshot[
        "ACWI_BENCHMARK"
    ] = benchmark

    snapshot.index.name = (
        "date"
    )

    SNAPSHOT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 17 significant digits preserves normal
    # float64 round-trip precision through CSV.
    snapshot.to_csv(
        SNAPSHOT_PATH,
        float_format="%.17g",
    )

    # --------------------------------------------------------
    # Reload what we actually wrote.
    #
    # All future hashes refer to the stored file,
    # not the temporary in-memory Yahoo result.
    # --------------------------------------------------------

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

    frozen_prices = (
        frozen[
            base.EQUITY_UNIVERSE
        ]
        .copy()
    )

    frozen_benchmark = (
        frozen[
            "ACWI_BENCHMARK"
        ]
        .copy()
    )

    data_hash = (
        base.calculate_data_hash(
            prices=
                frozen_prices,

            benchmark=
                frozen_benchmark,
        )
    )

    file_hash = (
        sha256_file(
            SNAPSHOT_PATH
        )
    )

    cutoff = pd.Timestamp(
        protocol[
            "historical_cutoff"
        ]
    )

    if (
        frozen.index[-1]
        != cutoff
    ):

        raise RuntimeError(
            "Frozen dataset does not end at "
            "the registered historical cutoff."
        )

    manifest = {
        "dataset_version":
            "Fund-100 Research Dataset v2",

        "historical_cutoff":
            protocol[
                "historical_cutoff"
            ],

        "first_date":
            str(
                frozen.index[
                    0
                ].date()
            ),

        "last_date":
            str(
                frozen.index[
                    -1
                ].date()
            ),

        "row_count":
            int(
                len(
                    frozen
                )
            ),

        "columns":
            list(
                frozen.columns
            ),

        "source":
            (
                "Yahoo Finance via frozen "
                "Fund-100 download pipeline"
            ),

        "file":
            str(
                SNAPSHOT_PATH
            ),

        "file_sha256":
            file_hash,

        "research_data_sha256":
            data_hash,

        "created_utc":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "policy":
            (
                "This file is immutable. "
                "Future research experiments use "
                "this stored snapshot instead of "
                "redownloading historical market data."
            ),
    }

    with MANIFEST_PATH.open(
        "w"
    ) as f:

        json.dump(
            manifest,
            f,
            indent=2,
        )

    print(
        "\nFrozen dataset created."
    )

    print(
        f"Rows: {len(frozen)}"
    )

    print(
        f"First date: "
        f"{frozen.index[0].date()}"
    )

    print(
        f"Last date: "
        f"{frozen.index[-1].date()}"
    )

    print(
        "\nFile SHA256:"
    )

    print(
        file_hash
    )

    print(
        "\nResearch data SHA256:"
    )

    print(
        data_hash
    )

    print(
        "\nFiles:"
    )

    print(
        SNAPSHOT_PATH
    )

    print(
        MANIFEST_PATH
    )

    print(
        "\n============================================"
    )

    print(
        "RESEARCH DATASET v2 FROZEN"
    )

    print(
        "============================================"
    )


if __name__ == "__main__":
    main()
