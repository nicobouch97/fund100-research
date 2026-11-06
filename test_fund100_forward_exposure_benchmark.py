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



    def test_stale_exposure_is_rejected_without_forward_fill(self):
        from fund100_forward_exposure_benchmark import dated_exposure_matched_benchmark
        a = [("2026-11-05", 0.01)]
        c = [("2026-11-05", 0.0001)]
        stale = [("2026-11-05", "2026-10-20T20:00:00+00:00", 0.25)]
        with self.assertRaisesRegex(ValueError, "stale"):
            dated_exposure_matched_benchmark(a, c, stale)
        fresh = [("2026-11-05", "2026-11-04T20:00:00+00:00", 0.25)]
        self.assertEqual(len(dated_exposure_matched_benchmark(a, c, fresh)), 1)
        for age in (0, -1, float("nan"), float("inf")):
            with self.subTest(age=age), self.assertRaises(ValueError):
                dated_exposure_matched_benchmark(a, c, fresh, max_exposure_age_days=age)
        # Research may explicitly choose a longer window, but never silently.
        self.assertEqual(len(dated_exposure_matched_benchmark(
            a, c, stale, max_exposure_age_days=30
        )), 1)

    def test_dated_alignment_and_pre_session_cutoff(self):
        from fund100_forward_exposure_benchmark import dated_exposure_matched_benchmark
        a = [("2026-11-02", 0.04), ("2026-11-03", 0.0)]
        c = [("2026-11-02", 0.002), ("2026-11-03", 0.0)]
        w = [("2026-11-02", "2026-11-01T22:00:00+00:00", 0.25),
             ("2026-11-03", "2026-11-02T22:00:00+00:00", 0.25)]
        result = dated_exposure_matched_benchmark(a, c, w)
        self.assertEqual([x[0] for x in result], ["2026-11-02", "2026-11-03"])
        self.assertAlmostEqual(result[0][1], 0.0115)
        bad = [
            (a, c[::-1], w),
            (a[::-1], c, w),
            (a, c, [(w[0][0], "2026-11-02T00:00:00+00:00", 0.25), w[1]]),
            (a, c, [(w[0][0], "2026-11-01T22:00:00", 0.25), w[1]]),
            (a, c, [w[0], w[0]]),
        ]
        for aa, cc, ww in bad:
            with self.subTest(aa=aa, cc=cc, ww=ww):
                with self.assertRaises(ValueError):
                    dated_exposure_matched_benchmark(aa, cc, ww)

if __name__ == "__main__":
    unittest.main()
