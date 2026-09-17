from pathlib import Path
import json

import numpy as np
import pandas as pd

from fund100 import (
    load_config,
    download_prices,
    compute_signals,
    run_backtest,
    performance_metrics,
)


OUTPUT_DIR = Path("validation_outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


def make_composite(signals, weights):
    """
    Construct a diagnostic composite signal.

    These are NOT new production strategies.
    They are ablation tests used to determine
    what each existing v1 component contributes.
    """

    result = None

    for signal_name, weight in weights.items():

        component = (
            signals[signal_name] * weight
        )

        if result is None:
            result = component.copy()
        else:
            result = result + component

    return result


def run_ablation_tests(
    prices,
    benchmark,
    signals,
    cfg,
):

    # ----------------------------------------------------------
    # These variants remove components from v1.
    #
    # They are diagnostics, NOT parameter optimisation.
    # ----------------------------------------------------------

    variants = {
        "FULL_V1": {
            "trend": 0.45,
            "residual": 0.35,
            "breakout": 0.20,
        },

        "TREND_ONLY": {
            "trend": 1.00,
        },

        "RESIDUAL_ONLY": {
            "residual": 1.00,
        },

        "BREAKOUT_ONLY": {
            "breakout": 1.00,
        },

        "TREND_RESIDUAL": {
            "trend": 0.5625,
            "residual": 0.4375,
        },

        "TREND_BREAKOUT": {
            "trend": 0.6923076923,
            "breakout": 0.3076923077,
        },

        "RESIDUAL_BREAKOUT": {
            "residual": 0.6363636364,
            "breakout": 0.3636363636,
        },
    }

    cost_scenarios = [
        5,
        15,
        35,
    ]

    starting_nav = float(
        cfg["account"]["starting_nav_gbp"]
    )

    rows = []

    for variant_name, signal_weights in variants.items():

        print(
            f"\nTesting {variant_name}..."
        )

        test_signals = dict(signals)

        test_signals["composite"] = (
            make_composite(
                signals,
                signal_weights,
            )
        )

        for cost_bps in cost_scenarios:

            result = run_backtest(
                prices=prices,
                benchmark=benchmark,
                signals=test_signals,
                cfg=cfg,
                one_way_cost_bps=cost_bps,
            )

            metrics = performance_metrics(
                result=result,
                starting_nav=starting_nav,
            )

            rows.append({
                "variant":
                    variant_name,

                "cost_bps":
                    cost_bps,

                "final_nav_gbp":
                    metrics[
                        "final_nav_gbp"
                    ],

                "cagr":
                    metrics[
                        "cagr"
                    ],

                "annual_volatility":
                    metrics[
                        "annual_volatility"
                    ],

                "sharpe":
                    metrics[
                        "sharpe_ratio_rf0"
                    ],

                "sortino":
                    metrics[
                        "sortino_ratio_rf0"
                    ],

                "max_drawdown":
                    metrics[
                        "max_drawdown"
                    ],

                "information_ratio":
                    metrics[
                        "information_ratio"
                    ],

                "beta":
                    metrics[
                        "beta_to_benchmark"
                    ],

                "regression_alpha":
                    metrics[
                        "annualised_regression_alpha_rf0"
                    ],

                "annual_turnover":
                    metrics[
                        "annual_turnover"
                    ],

                "transaction_cost_gbp":
                    metrics[
                        "total_transaction_cost_gbp"
                    ],
            })

    results = pd.DataFrame(rows)

    results.to_csv(
        OUTPUT_DIR
        / "signal_ablation.csv",
        index=False,
    )

    return results


def yearly_analysis(
    baseline_result
):

    history = (
        baseline_result["history"]
        .copy()
    )

    strategy_yearly = (
        history["daily_return"]
        .groupby(
            history.index.year
        )
        .apply(
            lambda x:
                (1.0 + x).prod()
                - 1.0
        )
    )

    benchmark_yearly = (
        history["benchmark_return"]
        .groupby(
            history.index.year
        )
        .apply(
            lambda x:
                (1.0 + x).prod()
                - 1.0
        )
    )

    yearly = pd.DataFrame({
        "strategy_return":
            strategy_yearly,

        "benchmark_return":
            benchmark_yearly,
    })

    yearly[
        "excess_return"
    ] = (
        yearly[
            "strategy_return"
        ]
        - yearly[
            "benchmark_return"
        ]
    )

    yearly.index.name = "year"

    yearly.to_csv(
        OUTPUT_DIR
        / "yearly_returns.csv"
    )

    return yearly


def rolling_analysis(
    baseline_result
):

    history = (
        baseline_result["history"]
        .copy()
    )

    window = 252 * 3

    strategy_growth = (
        (1.0 + history["daily_return"])
        .rolling(window)
        .apply(
            np.prod,
            raw=True,
        )
    )

    benchmark_growth = (
        (
            1.0
            + history[
                "benchmark_return"
            ]
        )
        .rolling(window)
        .apply(
            np.prod,
            raw=True,
        )
    )

    rolling = pd.DataFrame(
        index=history.index
    )

    rolling[
        "strategy_3y_cagr"
    ] = (
        strategy_growth
        ** (1.0 / 3.0)
        - 1.0
    )

    rolling[
        "benchmark_3y_cagr"
    ] = (
        benchmark_growth
        ** (1.0 / 3.0)
        - 1.0
    )

    rolling[
        "three_year_excess_cagr"
    ] = (
        rolling[
            "strategy_3y_cagr"
        ]
        - rolling[
            "benchmark_3y_cagr"
        ]
    )

    rolling.to_csv(
        OUTPUT_DIR
        / "rolling_3y.csv"
    )

    return rolling


def exposure_analysis(
    baseline_result
):

    weights = (
        baseline_result["weights"]
        .copy()
    )

    groups = {
        "US_Equity": [
            "SPY",
            "IWM",
            "XLK",
            "XLF",
            "XLI",
            "XLV",
            "XLP",
            "XLY",
            "XLE",
            "XLU",
        ],

        "International_Equity": [
            "EFA",
            "EEM",
        ],

        "Real_Estate": [
            "VNQ",
        ],

        "Fixed_Income": [
            "TLT",
            "IEF",
            "SHY",
            "TIP",
            "LQD",
        ],

        "Real_Assets": [
            "GLD",
            "DBC",
        ],
    }

    exposure = pd.DataFrame(
        index=weights.index
    )

    for group_name, members in groups.items():

        existing = [
            ticker
            for ticker in members
            if ticker in weights.columns
        ]

        exposure[group_name] = (
            weights[
                existing
            ]
            .sum(axis=1)
        )

    exposure[
        "Gross_Exposure"
    ] = weights.sum(axis=1)

    exposure[
        "Cash"
    ] = (
        1.0
        - exposure[
            "Gross_Exposure"
        ]
    )

    exposure.to_csv(
        OUTPUT_DIR
        / "asset_class_exposure.csv"
    )

    summary = pd.DataFrame({
        "mean":
            exposure.mean(),

        "median":
            exposure.median(),

        "minimum":
            exposure.min(),

        "maximum":
            exposure.max(),

        "p10":
            exposure.quantile(
                0.10
            ),

        "p90":
            exposure.quantile(
                0.90
            ),
    })

    summary.to_csv(
        OUTPUT_DIR
        / "exposure_summary.csv"
    )

    return exposure, summary


def latest_portfolio(
    baseline_result
):

    weights = (
        baseline_result[
            "weights"
        ]
        .iloc[-1]
    )

    active = (
        weights[
            weights
            > 0.000001
        ]
        .sort_values(
            ascending=False
        )
    )

    latest = pd.DataFrame({
        "weight": active
    })

    latest.loc[
        "CASH",
        "weight"
    ] = (
        1.0
        - active.sum()
    )

    latest.to_csv(
        OUTPUT_DIR
        / "latest_portfolio.csv"
    )

    return latest


def main():

    print(
        "===================================="
    )

    print(
        "FUND-100 RED-TEAM VALIDATION v1"
    )

    print(
        "===================================="
    )

    cfg, config_hash = (
        load_config()
    )

    print(
        "\nFrozen v1 config hash:"
    )

    print(config_hash)

    print(
        "\nDownloading data..."
    )

    prices, benchmark = (
        download_prices(cfg)
    )

    print(
        "\nComputing original v1 signals..."
    )

    signals = (
        compute_signals(
            prices=prices,
            benchmark=benchmark,
            cfg=cfg,
        )
    )

    # ----------------------------------------------------------
    # BASELINE
    # ----------------------------------------------------------

    print(
        "\nRunning frozen v1 baseline..."
    )

    baseline = run_backtest(
        prices=prices,
        benchmark=benchmark,
        signals=signals,
        cfg=cfg,
        one_way_cost_bps=15,
    )

    # ----------------------------------------------------------
    # SIGNAL ABLATION
    # ----------------------------------------------------------

    ablation = (
        run_ablation_tests(
            prices=prices,
            benchmark=benchmark,
            signals=signals,
            cfg=cfg,
        )
    )

    # ----------------------------------------------------------
    # TIME PERIOD ANALYSIS
    # ----------------------------------------------------------

    yearly = yearly_analysis(
        baseline
    )

    rolling = rolling_analysis(
        baseline
    )

    # ----------------------------------------------------------
    # EXPOSURE ANALYSIS
    # ----------------------------------------------------------

    exposure, exposure_summary = (
        exposure_analysis(
            baseline
        )
    )

    latest = latest_portfolio(
        baseline
    )

    # ----------------------------------------------------------
    # SUMMARY
    # ----------------------------------------------------------

    history = (
        baseline["history"]
    )

    rolling_valid = (
        rolling[
            "three_year_excess_cagr"
        ]
        .dropna()
    )

    summary = {
        "config_sha256":
            config_hash,

        "average_gross_exposure":
            float(
                history[
                    "gross_exposure"
                ]
                .mean()
            ),

        "panic_days_percent":
            float(
                history[
                    "panic_regime"
                ]
                .mean()
                * 100.0
            ),

        "fraction_of_3y_windows_beating_benchmark":
            float(
                (
                    rolling_valid
                    > 0
                )
                .mean()
            )
            if len(
                rolling_valid
            )
            else None,

        "median_3y_excess_cagr":
            float(
                rolling_valid
                .median()
            )
            if len(
                rolling_valid
            )
            else None,
    }

    with (
        OUTPUT_DIR
        / "validation_summary.json"
    ).open("w") as f:

        json.dump(
            summary,
            f,
            indent=2,
        )

    print(
        "\n===================================="
    )

    print(
        "15 BPS SIGNAL ABLATION"
    )

    print(
        "===================================="
    )

    display_columns = [
        "variant",
        "final_nav_gbp",
        "cagr",
        "sharpe",
        "max_drawdown",
        "information_ratio",
        "regression_alpha",
        "annual_turnover",
    ]

    print(
        ablation[
            ablation[
                "cost_bps"
            ] == 15
        ][
            display_columns
        ]
        .sort_values(
            "cagr",
            ascending=False,
        )
        .round(4)
        .to_string(
            index=False
        )
    )

    print(
        "\n===================================="
    )

    print(
        "YEARLY RESULTS"
    )

    print(
        "===================================="
    )

    print(
        yearly
        .round(4)
        .to_string()
    )

    print(
        "\n===================================="
    )

    print(
        "EXPOSURE SUMMARY"
    )

    print(
        "===================================="
    )

    print(
        exposure_summary
        .round(4)
        .to_string()
    )

    print(
        "\n===================================="
    )

    print(
        "LATEST MODEL PORTFOLIO"
    )

    print(
        "===================================="
    )

    print(
        latest
        .round(4)
        .to_string()
    )

    print(
        "\n===================================="
    )

    print(
        "ROLLING 3Y SUMMARY"
    )

    print(
        "===================================="
    )

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )

    print(
        "\nValidation files written "
        "to ./validation_outputs/"
    )


if __name__ == "__main__":
    main()
