"""Offline regression tests for the research-only matched comparator."""
import math
import unittest

from fund100_forward_exposure_benchmark import (
    compounded_nav,
    exposure_matched_benchmark,
)


class ExposureMatchedBenchmarkTests(unittest.TestCase):
    def test_constant_quarter_equity_no_cash_yield(self):
        result = exposure_matched_benchmark([0.04], [0.0], [0.25])
        self.assertAlmostEqual(result[0], 0.01)

    def test_verified_cash_yield_is_used(self):
        result = exposure_matched_benchmark([0.04], [0.002], [0.25])
        self.assertAlmostEqual(result[0], 0.0115)

    def test_first_day_initial_allocation_cost_is_explicit(self):
        result = exposure_matched_benchmark(
            [0], [0], [0.25], initial_equity_weight=0
        )
        self.assertAlmostEqual(result[0], -0.25 * 0.0015)

    def test_rebalance_cost_uses_drifted_end_weight(self):
        result = exposure_matched_benchmark(
            [0.10, 0], [0, 0], [0.5, 0.5], one_way_cost_bps=100
        )
        self.assertAlmostEqual(result[0], 0.05)
        drifted = 0.5 * 1.10 / 1.05
        self.assertAlmostEqual(result[1], -abs(0.5 - drifted) * 0.01)

    def test_zero_equity_is_cash_only(self):
        self.assertEqual(
            exposure_matched_benchmark([0.1], [0.003], [0]), [0.003]
        )

    def test_full_equity_is_acwi_only(self):
        self.assertEqual(
            exposure_matched_benchmark([0.1], [0.003], [1]), [0.1]
        )

    def test_missing_rates_and_invalid_weights_fail_closed(self):
        cases = [
            ([0.01], [], [0.25]),
            ([0.01], [float("nan")], [0.25]),
            ([0.01], [0], [1.2]),
            ([0.01], [0], [-0.1]),
            ([], [], []),
        ]
        for a, c, w in cases:
            with self.subTest(a=a, c=c, w=w):
                with self.assertRaises(ValueError):
                    exposure_matched_benchmark(a, c, w)

    def test_compounding(self):
        self.assertAlmostEqual(compounded_nav([0.1, -0.1]), 99.0)


if __name__ == "__main__":
    unittest.main()
