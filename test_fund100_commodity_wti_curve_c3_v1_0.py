"""No broker: public EIA WTI rank-curve research invariants, synthetic fixtures."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

import fund100_commodity_wti_curve_c3_source_v1_0 as source
import fund100_commodity_wti_curve_c3_v1_0 as c3


def synthetic(n=115):
    days = pd.bdate_range("2023-09-01", periods=n)
    t = np.arange(n, dtype=float)
    first = 70. + .055*t + np.sin(t/7)
    second = 70. + .044*t - np.sin(t/7)
    return pd.DataFrame({
        "observation_date": days,
        "available_date": days + pd.offsets.BDay(2),
        "RCLC1": first,
        "RCLC2": second,
    })


def test_c3_is_research_only_not_dbc_spot_or_futures_roll_pnl():
    report = c3.report(synthetic())
    assert report["schema"] == "FUND100_PHASE3_C3_WTI_CURVE_EXPLORATORY_V1"
    assert report["status"] == "RESEARCH_ONLY_NO_PROMOTION"
    assert report["paper_authorized"] is False
    assert report["live_authorized"] is False
    assert report["broker_order_count"] == 0
    assert report["term_structure_is_wti_only_not_dbc_basket"] is True
    assert report["wti_spread_is_not_futures_roll_pnl_or_realized_carry"] is True
    assert report["c3_strategy_backtest_performed"] is False
    assert report["forward_carry_signal_current_as_of_2026"] is False
    assert report["dbc_index_methodology_changed_2025_11_10"] is True
    assert report["last_observation_date"] <= "2024-04-05"
    assert report["historical_months_with_at_least_five_valid_pairs"] >= 4


def test_backwardation_contango_and_flat_sign_convention():
    assert c3.classify(72, 70) == ("WTI_BACKWARDATION", 72/70-1)
    assert c3.classify(69, 70) == ("WTI_CONTANGO", 69/70-1)
    assert c3.classify(70, 70) == ("WTI_FLAT", 0.0)


def test_april_2020_negative_settlement_is_preserved_but_not_divided():
    # Actual WTI front-month settlement briefly became negative in April
    # 2020. Synthetic values here are only an edge-case fixture.
    d = synthetic()
    d.loc[5, "RCLC1"] = -37.63
    clean = c3.validate_source(d)
    assert clean.loc[5, "RCLC1"] == -37.63
    states = c3.features(d)
    assert states.loc[5, "wti_state"] == "NONPOSITIVE_SETTLEMENT_NO_PCT_CARRY"
    assert states.loc[5, "front_minus_second_dollars_per_bbl"] < 0
    assert math.isnan(states.loc[5, "front_over_second_minus_one"])
    result = c3.report(d)
    assert result["nonpositive_quote_rows"] == 1


def test_no_2026_price_is_accepted_as_discontinued_eia_curve():
    d = synthetic()
    d.loc[len(d)-1, "observation_date"] = pd.Timestamp("2026-10-14")
    d.loc[len(d)-1, "available_date"] = pd.Timestamp("2026-10-15")
    with pytest.raises(c3.CurveResearchStop):
        c3.validate_source(d)


def test_missing_rank_data_unordered_dates_and_fake_releases_are_rejected():
    d = synthetic()
    for bad in (
        lambda x: x.drop(columns=["RCLC2"]),
        lambda x: x.assign(RCLC1=np.nan),
        lambda x: x.assign(RCLC2=float("inf")),
        lambda x: x.assign(RCLC1="fake"),
        lambda x: x.iloc[::-1],
        lambda x: x.iloc[:12],
        lambda x: pd.concat([x, x.iloc[-1:]], ignore_index=True),
    ):
        with pytest.raises(c3.CurveResearchStop):
            c3.validate_source(bad(d))
    d = synthetic()
    d.loc[5, "available_date"] = pd.Timestamp("2023-01-01")
    with pytest.raises(c3.CurveResearchStop):
        c3.validate_source(d)


def test_monthly_proxy_is_not_equated_to_dbc_pnl():
    f = c3.monthly_features(synthetic())
    assert len(f) > 3
    assert f["wti_only_not_dbc_roll_return"].all()
    assert (f["positive_quote_pair_days"] >= 5).all()


def test_sha_is_sensitive_to_a_single_source_revision():
    d = synthetic()
    original = c3.input_sha256(d)
    assert original == c3.input_sha256(d.copy())
    changed = d.copy()
    changed.loc[4, "RCLC1"] += .01
    assert c3.input_sha256(changed) != original


def test_eia_parser_requires_exact_rank_and_complete_named_records():
    payload = {"response": {"data": [
        {"series": "RCLC1", "period": "2024-03-01", "value": "79.97"},
        {"series": "RCLC1", "period": "2024-03-04", "value": "-12.5"},
    ], "total": "2"}}
    d = source.parse_page(payload, "RCLC1")
    assert list(d.columns) == ["observation_date", "RCLC1"]
    assert d["RCLC1"].tolist() == [79.97, -12.5]
    for wrong in (
        {"response": {"data": [{"series": "RCLC2", "period": "2024-03-01", "value": 70}]}},
        {"response": {"data": [{"series": "RCLC1", "period": "2026-01-01", "value": 70}]}},
        {"response": {"data": [{"series": "RCLC1", "period": "2024-02-01", "value": None}]}},
        {"response": {"data": []}},
    ):
        with pytest.raises(c3.CurveResearchStop):
            source.parse_page(wrong, "RCLC1")


def test_eia_pair_only_same_date_never_forward_fills():
    d = synthetic()
    first = d[["observation_date", "RCLC1"]]
    second = d[["observation_date", "RCLC2"]].drop(index=[10, 11])
    result = source.pair_ranks(first, second)
    assert len(result) == len(d) - 2
    assert pd.Timestamp(d.loc[10, "observation_date"]) not in set(result["observation_date"])
    assert pd.Timestamp(d.loc[11, "observation_date"]) not in set(result["observation_date"])
    assert all(result["available_date"] > result["observation_date"])


def test_eia_api_url_source_does_not_fetch_broker_or_require_key():
    assert source.API.startswith("https://api.eia.gov/v2/petroleum/pri/fut/")
    assert not ("alpaca" in source.API or "broker" in source.API)
    assert source.EIA_CUTOFF == pd.Timestamp("2024-04-05")
    with pytest.raises(c3.CurveResearchStop):
        source.download_history("BTCUSD")


def test_report_never_mutates_real_source():
    d = synthetic()
    old = d.copy()
    c3.report(d)
    pd.testing.assert_frame_equal(d, old)

def test_blocked_eia_http_source_cannot_produce_fake_curve_data(monkeypatch):
    from urllib.error import HTTPError

    def blocked(*args, **kwargs):
        raise HTTPError("https://api.eia.gov/", 403, "Forbidden", {}, None)

    monkeypatch.setattr(source, "urlopen", blocked)
    with pytest.raises(c3.CurveResearchStop, match="source unavailable"):
        source.download_history("RCLC1")
    # No fallback to ETF spot returns or invented near-future settlements.
