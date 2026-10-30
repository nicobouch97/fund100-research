"""Research-only rolling SEC100 cohort source and forward-mark coverage."""
from pathlib import Path

import pandas as pd
import pytest

import fund100_v7_u8_sec100_rolling_forward_v1_0 as rolling


def _source(rows, prior=10):
    return {
        "deduplicated_stock_entry_exposures": [
            {"ticker": symbol, "entry_close": "2026-11-02",
             "exit_close": "2026-11-03"} for symbol in rows],
        "previous_main_observer_run": prior,
        "broker_orders": 0,
        "trading_authorized": False,
        "live_authorized": False,
    }



def _fake_evaluation(frozen, *, completed):
    rows = frozen["deduplicated_stock_entry_exposures"]
    fields = ("stock_net_minus_spy_net_percentage_points",
              "stock_net_minus_rsp_net_percentage_points",
              "stock_net_minus_gross_spy_percentage_points",
              "stock_net_minus_gross_rsp_percentage_points")
    observations = []
    for row in rows:
        ticker = row["ticker"]
        values = (2., 1., 1.5, .5) if ticker == "AAPL" else (-1., -2., -1.5, -2.5)
        mark = {
            "ticker": ticker, "frozen_entry_close": row["entry_close"],
            "frozen_exit_close": row["exit_close"],
            "original_earnings_accessions": row.get("accessions"),
            "status": ("TWO_COMPLETED_CLOSES_COSTED_DESCRIPTIVE_NOT_ALPHA" if completed
                       else "WAITING_FOR_INDEPENDENT_FUTURE_COMPLETED_PRICE_SOURCE"),
        }
        for field, value in zip(fields, values):
            mark[field] = {str(bp): value for bp in (5, 15, 35)} if completed else None
        observations.append(mark)
    return {
        "unique_model_exposures": len(rows),
        "priced_two_close_exposures": len(rows) if completed else 0,
        "pending_two_close_exposures": 0 if completed else len(rows),
        "source_dated_return_observations": observations,
    }

def test_every_consecutive_source_pair_is_replayed_before_prices(monkeypatch):
    seen = []

    def fake_freeze(**kwargs):
        seen.append(kwargs)
        return _source(["AAPL"], kwargs["previous_main_id"])

    monkeypatch.setattr(rolling.u6, "freeze_from_sources", fake_freeze)
    observed = [(10, Path("first")), (20, Path("second")), (30, Path("third"))]
    frozen = rolling.freeze_chain(
        original_u3=Path("u3"), original_first_sec=Path("u4"),
        observations=observed)
    assert len(frozen) == 2
    assert [(x["previous_main_id"], x["later_sec"]) for x in seen] == [
        (10, Path("second")), (20, Path("third"))]
    assert rolling.required_symbols(frozen) == {"AAPL", "SPY", "RSP"}


def test_rolling_marks_all_cohorts_and_does_not_promote_alpha(monkeypatch):
    seen = []

    def fake_evaluate(frozen, *, prices, later_price_acquired_utc,
                      provider_reference):
        seen.append((frozen["previous_main_observer_run"], list(prices.columns)))
        return _fake_evaluation(frozen, completed=True)

    monkeypatch.setattr(rolling.u7, "evaluate", fake_evaluate)
    cohorts = [(10, 20, _source(["AAPL"], 10)),
               (20, 30, _source(["MSFT"], 20))]
    prices = pd.DataFrame({"AAPL": [100., 101.], "MSFT": [90., 91.],
                           "SPY": [200., 202.], "RSP": [150., 151.]})
    out = rolling.mark_chain(
        cohorts, prices=prices,
        acquired_utc="2026-11-04T03:00:00Z",
        provider_reference="independent later market source")
    assert seen == [(10, ["AAPL", "RSP", "SPY"]),
                    (20, ["MSFT", "RSP", "SPY"])]
    assert out["source_relative_distinct_exposures"] == 2
    assert out["priced_two_close_exposures"] == 2
    assert out["archived_observer_pairs"] == 2
    assert out["statistically_proven_alpha"] is False
    assert out["broker_orders"] == 0
    assert out["trading_authorized"] is False


def test_missing_price_symbol_rejects_entire_cohort_not_only_survivors():
    cohorts = [(10, 20, _source(["AAPL", "MSFT"], 10))]
    incomplete = pd.DataFrame({"AAPL": [1.], "SPY": [1.], "RSP": [1.]})
    with pytest.raises(rolling.RollingStop, match="surviving tickers"):
        rolling.mark_chain(cohorts, prices=incomplete,
                           acquired_utc="2026-11-04T03:00:00Z",
                           provider_reference="incomplete original vendor panel")


def test_zero_event_cohorts_do_not_acquire_prices(monkeypatch):
    calls = []

    def fake_evaluate(frozen, *, prices, later_price_acquired_utc,
                      provider_reference):
        calls.append((prices, later_price_acquired_utc, provider_reference))
        return _fake_evaluation(frozen, completed=False)

    monkeypatch.setattr(rolling.u7, "evaluate", fake_evaluate)
    cohorts = [(10, 20, _source([], 10)), (20, 30, _source([], 20))]
    assert rolling.required_symbols(cohorts) == set()
    result = rolling.mark_chain(cohorts, prices=None)
    assert calls == [(None, None, None), (None, None, None)]
    assert result["source_relative_distinct_exposures"] == 0
    assert result["all_nonempty_cohorts_fully_priced"] is False


@pytest.mark.parametrize("observations", [
    [(10, Path("first"))],
    [(20, Path("first")), (10, Path("second"))],
    [(10, Path("first")), (10, Path("second"))],
    [(10, "first"), (20, Path("second"))],
    [(True, Path("first")), (20, Path("second"))],
])
def test_unverified_or_nonconsecutive_observer_metadata_holds(observations):
    with pytest.raises(rolling.RollingStop):
        rolling.freeze_chain(original_u3=Path("u3"),
                             original_first_sec=Path("u4"),
                             observations=observations)


def test_any_source_replay_failure_aborts_all_cohorts(monkeypatch):
    def fake_freeze(**kwargs):
        if kwargs["previous_main_id"] == 20:
            raise ValueError("SEC original archive mismatch")
        return _source(["AAPL"], kwargs["previous_main_id"])

    monkeypatch.setattr(rolling.u6, "freeze_from_sources", fake_freeze)
    with pytest.raises(rolling.RollingStop, match="archive replay failed"):
        rolling.freeze_chain(original_u3=Path("u3"),
                             original_first_sec=Path("u4"),
                             observations=[(10, Path("a")), (20, Path("b")),
                                           (30, Path("c"))])


def test_any_forward_evaluation_failure_aborts_without_subset_result(monkeypatch):
    calls = []

    def fake_evaluate(frozen, **kwargs):
        calls.append(frozen["previous_main_observer_run"])
        if len(calls) == 2:
            raise ValueError("future stock close missing")
        return _fake_evaluation(frozen, completed=True)

    monkeypatch.setattr(rolling.u7, "evaluate", fake_evaluate)
    cohorts = [(10, 20, _source(["AAPL"], 10)),
               (20, 30, _source(["MSFT"], 20))]
    prices = pd.DataFrame({"AAPL": [1.], "MSFT": [1.],
                           "SPY": [1.], "RSP": [1.]})
    with pytest.raises(rolling.RollingStop, match="cannot be priced safely"):
        rolling.mark_chain(cohorts, prices=prices,
                           acquired_utc="2026-11-04T03:00:00Z",
                           provider_reference="independent later vendor")
    assert calls == [10, 20]


def test_rolling_workflow_is_main_only_and_never_writes_private_or_broker():
    text = Path(".github/workflows/fund100-v7-u8-sec100-rolling-forward.yml").read_text()
    assert "if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request'" in text
    assert "contents: read" in text and "actions: read" in text
    assert "FUND100_BROKER_KILL_SWITCH: ENGAGED" in text
    assert "FUND100_LIVE_WRITE_MODE: DISABLED" in text
    assert "fund100_v7_u8_sec100_rolling_forward_v1_0.py" in text
    assert "actions/upload-artifact@v4" in text
    assert "if-no-files-found: error" in text
    assert "git push" not in text and "alpaca" not in text.lower()


@pytest.mark.parametrize("completed", [False, True])
def test_same_ticker_and_entry_from_distinct_sec_cohorts_counts_once(monkeypatch, completed):
    """Separate SEC accessions on one date must not inflate economic sample N."""
    def fake_evaluate(frozen, **kwargs):
        n = len(frozen["deduplicated_stock_entry_exposures"])
        return _fake_evaluation(frozen, completed=completed)

    monkeypatch.setattr(rolling.u7, "evaluate", fake_evaluate)
    def cohort(run, ticker):
        return {"previous_main_observer_run": run,
                "deduplicated_stock_entry_exposures": [{
                    "ticker": ticker, "entry_close": "2026-11-02",
                    "exit_close": "2026-11-03"}]}
    cohorts = [(10, 20, cohort(10, "AAPL")),
               (20, 30, cohort(20, "AAPL")),
               (30, 40, cohort(30, "MSFT"))]
    prices = (pd.DataFrame({"AAPL": [100., 101.], "MSFT": [100., 102.],
                            "SPY": [200., 201.], "RSP": [150., 151.]})
              if completed else None)
    out = rolling.mark_chain(
        cohorts, prices=prices,
        acquired_utc="2026-11-04T03:00:00Z" if completed else None,
        provider_reference="independent source" if completed else None)
    assert out["source_relative_distinct_exposures"] == 3
    assert out["cohort_exposure_observations_not_independent_bets"] == 3
    assert out["economic_unique_ticker_entry_exposures"] == 2
    assert out["duplicate_ticker_entry_observations_across_cohorts"] == 1
    assert out["economic_completed_ticker_entry_exposures"] == (2 if completed else 0)
    assert out["economic_pending_ticker_entry_exposures"] == (0 if completed else 2)
    assert out["statistically_proven_alpha"] is False
    assert out["broker_orders"] == 0


def test_same_economic_exposure_cannot_disagree_about_completion(monkeypatch):
    def fake_evaluate(frozen, **kwargs):
        done = frozen["previous_main_observer_run"] == 10
        return _fake_evaluation(frozen, completed=done)

    monkeypatch.setattr(rolling.u7, "evaluate", fake_evaluate)
    row = {"ticker": "AAPL", "entry_close": "2026-11-02",
           "exit_close": "2026-11-03"}
    cohorts = [(10, 20, {"previous_main_observer_run": 10,
                         "deduplicated_stock_entry_exposures": [row]}),
               (20, 30, {"previous_main_observer_run": 20,
                         "deduplicated_stock_entry_exposures": [row]})]
    prices = pd.DataFrame({"AAPL": [100., 101.], "SPY": [200., 201.],
                           "RSP": [150., 151.]})
    with pytest.raises(rolling.RollingStop, match="conflicting future marks"):
        rolling.mark_chain(cohorts, prices=prices,
                           acquired_utc="2026-11-04T03:00:00Z",
                           provider_reference="independent source")


def test_completed_economic_date_cohort_deduplicates_and_compares_after_costs(monkeypatch):
    monkeypatch.setattr(rolling.u7, "evaluate",
                        lambda frozen, **kwargs: _fake_evaluation(frozen, completed=True))
    cohorts = [(10, 20, _source(["AAPL"], 10)),
               (20, 30, _source(["AAPL"], 20)),
               (30, 40, _source(["MSFT"], 30))]
    panel = pd.DataFrame({"AAPL": [100., 101.], "MSFT": [90., 91.],
                          "SPY": [200., 202.], "RSP": [150., 151.]})
    result = rolling.mark_chain(
        cohorts, prices=panel, acquired_utc="2026-11-04T03:00:00Z",
        provider_reference="independent original prices")
    dates = result["economic_entry_date_costed_comparisons"]
    assert dates["unique_entry_date_clusters"] == 1
    assert dates["pending_entry_date_clusters"] == []
    completed = dates["completed_entry_date_clusters"]
    assert len(completed) == 1 and completed[0]["unique_stock_exposures"] == 2
    assert completed[0]["stock_net_minus_spy_net_percentage_points"]["15"] == .5
    assert completed[0]["stock_net_minus_rsp_net_percentage_points"]["35"] == -.5
    assert dates["date_clustered_descriptive_returns_not_investable_portfolio_or_alpha"]
    assert result["statistically_proven_alpha"] is False


def test_partly_completed_entry_date_never_publishes_subset_return(monkeypatch):
    def fake(frozen, **kwargs):
        return _fake_evaluation(
            frozen, completed=frozen["previous_main_observer_run"] == 10)
    monkeypatch.setattr(rolling.u7, "evaluate", fake)
    cohorts = [(10, 20, _source(["AAPL"], 10)),
               (20, 30, _source(["MSFT"], 20))]
    panel = pd.DataFrame({"AAPL": [100., 101.], "MSFT": [90., 91.],
                          "SPY": [200., 202.], "RSP": [150., 151.]})
    result = rolling.mark_chain(
        cohorts, prices=panel, acquired_utc="2026-11-04T03:00:00Z",
        provider_reference="independent original prices")
    dates = result["economic_entry_date_costed_comparisons"]
    assert dates["completed_entry_date_clusters"] == []
    assert dates["pending_entry_date_clusters"] == [{
        "entry_close": "2026-11-02", "unique_stock_exposures": 2,
        "completed_stock_exposures": 1, "no_partial_cohort_return": True}]


def test_duplicate_economic_exposure_cannot_change_costed_return(monkeypatch):
    def fake(frozen, **kwargs):
        result = _fake_evaluation(frozen, completed=True)
        if frozen["previous_main_observer_run"] == 20:
            result["source_dated_return_observations"][0][
                "stock_net_minus_spy_net_percentage_points"]["15"] += .25
        return result
    monkeypatch.setattr(rolling.u7, "evaluate", fake)
    cohorts = [(10, 20, _source(["AAPL"], 10)),
               (20, 30, _source(["AAPL"], 20))]
    panel = pd.DataFrame({"AAPL": [100., 101.], "SPY": [200., 202.],
                          "RSP": [150., 151.]})
    with pytest.raises(rolling.RollingStop, match="conflicting returns"):
        rolling.mark_chain(
            cohorts, prices=panel, acquired_utc="2026-11-04T03:00:00Z",
            provider_reference="independent original prices")


@pytest.mark.parametrize("bad_value", [float("nan"), True, None])
def test_corrupt_costed_stock_mark_fails_closed(monkeypatch, bad_value):
    def fake(frozen, **kwargs):
        result = _fake_evaluation(frozen, completed=True)
        result["source_dated_return_observations"][0][
            "stock_net_minus_spy_net_percentage_points"]["5"] = bad_value
        return result
    monkeypatch.setattr(rolling.u7, "evaluate", fake)
    cohorts = [(10, 20, _source(["AAPL"], 10))]
    panel = pd.DataFrame({"AAPL": [100., 101.], "SPY": [200., 202.],
                          "RSP": [150., 151.]})
    with pytest.raises(rolling.RollingStop, match="nonfinite"):
        rolling.mark_chain(
            cohorts, prices=panel, acquired_utc="2026-11-04T03:00:00Z",
            provider_reference="independent original prices")
