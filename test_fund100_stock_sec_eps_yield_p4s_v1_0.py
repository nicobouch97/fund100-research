"""P4S synthetic regression tests. No vendor network or broker requests."""
import copy
import math

import pandas as pd
import pytest

import fund100_stock_sec_eps_yield_p4s_v1_0 as p4s
import test_fund100_stock_sec_quality_forward_p4r_v1_0 as p4r_fixtures


def fixture():
    annual = p4r_fixtures.annual()
    events = p4r_fixtures.run()
    index = pd.bdate_range("2017-01-02", "2026-10-23")
    tickers = ["AVGO", "CAT"]
    close = pd.DataFrame(100.0, index=index, columns=tickers)
    splits = pd.DataFrame(0.0, index=index, columns=tickers)
    eps = {(row["ticker"], row["original_10k_accession"]):
           (20.0 if row["ticker"] == "CAT" else 2.0)
           for row in events["event_returns"]}
    return annual, events, eps, close, splits


def evaluate(a=None, e=None, eps=None, close=None, splits=None):
    orig = fixture()
    return p4s.analyze(
        a if a is not None else orig[0],
        e if e is not None else orig[1],
        eps if eps is not None else orig[2],
        close if close is not None else orig[3],
        splits if splits is not None else orig[4],
        market_capture_utc="2026-10-24T19:00:00Z")


def test_original_accession_and_full_year_diluted_eps_only():
    facts = {"EarningsPerShareDiluted": {"units": {"USD/shares": [
        {"accn": "A", "filed": "2025-02-14", "form": "10-K",
         "start": "2024-01-01", "end": "2024-12-31", "val": 4.25},
        {"accn": "B", "filed": "2026-02-14", "form": "10-K",
         "start": "2024-01-01", "end": "2024-12-31", "val": 99.0},
        {"accn": "A", "filed": "2025-02-14", "form": "10-K",
         "start": "2024-10-01", "end": "2024-12-31", "val": 9.0},
    ]}}}
    assert p4s.original_annual_eps(facts, "A", "2025-02-14", "2024-12-31") == 4.25
    assert p4s.original_annual_eps(facts, "MISSING", "2025-02-14", "2024-12-31") is None
    facts["EarningsPerShareDiluted"]["units"]["USD/shares"].append(
        {"accn": "A", "filed": "2025-02-14", "form": "10-K",
         "start": "2024-01-01", "end": "2024-12-31", "val": 4.3})
    with pytest.raises(p4s.EarningsYieldStop, match="Conflicting"):
        p4s.original_annual_eps(facts, "A", "2025-02-14", "2024-12-31")


def test_undo_future_stock_split_without_adjusted_dividend_close():
    a, e, eps, close, splits = fixture()
    # Vendor's present-day Close is split-adjusted; a later 4:1 split
    # means the original February 2025 as-traded price was 4x higher.
    splits.loc["2025-03-03", "CAT"] = 4.0
    out = evaluate(a, e, eps, close, splits)
    by_ticker = {r["ticker"]: r for r in out["events"]}
    cat = by_ticker["CAT"]
    assert cat["last_prefiling_raw_close_date"] == "2025-02-17"
    assert cat["approximate_as_traded_prefiling_price_usd"] == 400.0
    assert cat["approximate_gaap_earnings_yield"] == 0.05
    assert cat["valuation_bucket"] == "POSITIVE_EPS_YIELD_AT_LEAST_5PCT"
    assert by_ticker["AVGO"]["valuation_bucket"] == "POSITIVE_EPS_YIELD_BELOW_5PCT"
    assert out["completed_events"] == 2 and out["original_eps_available"] == 2
    assert out["valuation_by_prior_momentum"]["nonpositive_momentum"][
        "POSITIVE_EPS_YIELD_AT_LEAST_5PCT"]["events"] == 1
    assert not out["trading_authorized"] and not out["paper_authorized"]
    assert not out["live_authorized"] and out["broker_orders"] == 0


def test_split_on_prefiling_day_is_not_undone_and_filing_day_price_not_used():
    a, e, eps, close, splits = fixture()
    splits.loc["2025-02-17", "CAT"] = 4.0
    close.loc["2025-02-18", "CAT"] = 50000.0  # must never enter denominator
    out = evaluate(a, e, eps, close, splits)
    cat = next(r for r in out["events"] if r["ticker"] == "CAT")
    assert cat["approximate_as_traded_prefiling_price_usd"] == 100.0
    assert cat["approximate_gaap_earnings_yield"] == 0.2


def test_missing_and_nonpositive_gaap_eps_are_explicit_not_backfilled():
    a, e, eps, close, splits = fixture()
    keys = list(eps)
    eps[keys[0]] = None
    eps[keys[1]] = -1.0
    out = evaluate(a, e, eps, close, splits)
    assert out["original_eps_available"] == 1
    assert {r["valuation_bucket"] for r in out["events"]} == {
        "MISSING_ORIGINAL_DILUTED_EPS", "NONPOSITIVE_EARNINGS"}
    assert sum(group["events"] for cells in out["valuation_by_prior_momentum"].values()
               for group in cells.values()) == 2


def test_original_lineage_and_no_broker_release_are_fail_closed():
    a, e, eps, close, splits = fixture()
    altered = copy.deepcopy(e)
    altered["source_sec_manifest_sha256"] = "0" * 64
    with pytest.raises(p4s.EarningsYieldStop, match="lineage"):
        evaluate(a, altered, eps, close, splits)
    altered = copy.deepcopy(e)
    altered["live_authorized"] = True
    with pytest.raises(p4s.EarningsYieldStop, match="lineage"):
        evaluate(a, altered, eps, close, splits)
    altered = copy.deepcopy(e)
    altered["broker_orders"] = 1
    with pytest.raises(p4s.EarningsYieldStop, match="lineage"):
        evaluate(a, altered, eps, close, splits)


def test_reject_missing_duplicate_or_untrusted_eps_source():
    a, e, eps, close, splits = fixture()
    eps.pop(next(iter(eps)))
    with pytest.raises(p4s.EarningsYieldStop, match="Duplicate events or missing"):
        evaluate(a, e, eps, close, splits)
    a, e, eps, close, splits = fixture()
    eps[next(iter(eps))] = float("nan")
    with pytest.raises(p4s.EarningsYieldStop, match="Nonfinite"):
        evaluate(a, e, eps, close, splits)


def test_market_dates_and_split_source_must_be_complete():
    a, e, eps, close, splits = fixture()
    with pytest.raises(p4s.EarningsYieldStop, match="not aligned"):
        evaluate(a, e, eps, close, splits.iloc[:-1])
    a, e, eps, close, splits = fixture()
    splits.loc["2025-03-03", "CAT"] = float("nan")
    with pytest.raises(p4s.EarningsYieldStop, match="Invalid original price"):
        evaluate(a, e, eps, close, splits)
    a, e, eps, close, splits = fixture()
    splits.loc["2025-03-03", "CAT"] = 101.0
    with pytest.raises(p4s.EarningsYieldStop, match="Unverifiable"):
        evaluate(a, e, eps, close, splits)
    a, e, eps, close, splits = fixture()
    close.loc["2025-02-17", "CAT"] = 0
    with pytest.raises(p4s.EarningsYieldStop, match="Invalid original price"):
        evaluate(a, e, eps, close, splits)


def test_reject_future_price_capture_and_event_date_corruption():
    a, e, eps, close, splits = fixture()
    with pytest.raises(p4s.EarningsYieldStop, match="acquisition day"):
        p4s.analyze(a, e, eps, close, splits,
                    market_capture_utc="2026-10-23T19:00:00Z")
    e = copy.deepcopy(e)
    e["event_returns"][0]["entry_next_session_close"] = "2025-02-18"
    with pytest.raises(p4s.EarningsYieldStop, match="chronology"):
        evaluate(a, e, eps, close, splits)


def test_research_is_not_owner_earnings_or_point_in_time_alpha():
    out = evaluate()
    assert out["predeclared_positive_earnings_yield_threshold"] == .05
    assert out["comparison_cost_per_side_bps"] == 15
    assert out["today_retrieved_sec_not_original_historical_vendor_vintage"]
    assert out["reconstructed_yahoo_close_and_splits_not_independent_corporate_action_proof"]
    assert out["eps_share_class_and_post_filing_price_execution_not_independently_verified"]
    assert out["no_historical_investable_backtest_or_validated_alpha"]
    assert out["no_intrinsic_value_or_owner_earnings_claim"]


def test_within_issuer_contrast_does_not_confuse_cross_company_within_signal():
    def row(ticker, momentum, bucket, excess):
        return {"ticker": ticker, "positive_pre_filing_relative_momentum": momentum,
                "valuation_bucket": bucket,
                "net_15bps_stock_minus_spy_pp": excess}
    high = "POSITIVE_EPS_YIELD_AT_LEAST_5PCT"
    low = "POSITIVE_EPS_YIELD_BELOW_5PCT"
    records = [
        row("MSFT", True, high, 4), row("MSFT", True, low, -2),
        row("KO", True, high, -1), row("KO", True, low, 3),
        row("PG", True, high, 8),  # no low-yield match
        row("CAT", False, high, 1), row("CAT", False, low, 2),
        row("AVGO", False, high, 100),  # cannot inflate paired result
        row("CAT", True, low, 50),  # other momentum state must not leak
        row("MSFT", True, "MISSING_ORIGINAL_DILUTED_EPS", 1000),
    ]
    result = p4s._within_issuer_valuation_contrasts(records)
    pos = result["by_prior_momentum"]["positive_momentum"]
    neg = result["by_prior_momentum"]["nonpositive_momentum"]
    assert pos["issuers_with_both_yield_buckets_in_same_momentum_state"] == 2
    assert pos["issuers_with_any_eligible_yield"] == 4
    assert pos["issuer_equal_high_minus_low_yield_excess_pp"] == 1.0
    assert pos["per_issuer"]["MSFT"]["high_minus_low_yield_mean_excess_pp"] == 6.0
    assert pos["per_issuer"]["KO"]["high_minus_low_yield_mean_excess_pp"] == -4.0
    assert pos["leave_one_issuer_out_pp"] == {"KO": 6.0, "MSFT": -4.0}
    assert neg["issuers_with_both_yield_buckets_in_same_momentum_state"] == 1
    assert neg["issuer_equal_high_minus_low_yield_excess_pp"] == -1.0
    assert neg["leave_one_issuer_out_pp"] == {}
    assert pos["insufficient_paired_issuers_for_stable_conclusion"]
    assert result["comparison_is_descriptive_not_independent_inference"]


def test_real_evaluator_reports_no_paired_issuer_as_no_evidence():
    out = evaluate()
    contrast = out["within_issuer_valuation_contrasts"]
    assert contrast["method"] == (
        "WITHIN_ISSUER_SAME_PRIOR_MOMENTUM_5PCT_EPS_YIELD_CONTRAST")
    for cell in contrast["by_prior_momentum"].values():
        assert cell["issuers_with_both_yield_buckets_in_same_momentum_state"] == 0
        assert cell["issuer_equal_high_minus_low_yield_excess_pp"] is None
        assert cell["leave_one_issuer_out_pp"] == {}
        assert cell["insufficient_paired_issuers_for_stable_conclusion"]
    assert out["broker_requests"] == out["broker_orders"] == 0
    assert out["live_authorized"] is False
