"""Research-only rolling SEC100 cohort source and forward-mark coverage."""
from pathlib import Path

import pandas as pd
import pytest

import fund100_v7_u8_sec100_rolling_forward_v1_0 as rolling


def _source(rows, prior=10):
    return {
        "deduplicated_stock_entry_exposures": [
            {"ticker": symbol} for symbol in rows],
        "previous_main_observer_run": prior,
        "broker_orders": 0,
        "trading_authorized": False,
        "live_authorized": False,
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
        return {"unique_model_exposures": 1,
                "priced_two_close_exposures": 1,
                "pending_two_close_exposures": 0}

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
        return {"unique_model_exposures": 0,
                "priced_two_close_exposures": 0,
                "pending_two_close_exposures": 0}

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
        return {"unique_model_exposures": 1,
                "priced_two_close_exposures": 1,
                "pending_two_close_exposures": 0}

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
