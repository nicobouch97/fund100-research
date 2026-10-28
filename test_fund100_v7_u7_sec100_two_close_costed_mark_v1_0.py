"""U7 negative/causal two-close mark regression. No network or broker."""
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

import fund100_v7_u6_sec100_causal_forward_admission_v1_0 as u6
import fund100_v7_u7_sec100_two_close_costed_mark_v1_0 as u7
from test_fund100_v7_u6_sec100_causal_forward_admission_v1_0 import report,new_row

def frozen(*rows):
    return u6.freeze_verified_delta(report(rows=list(rows)))

def panel(*,aapl=(100.0,110.0),spy=(200.0,204.0),
          dates=("2026-10-28","2026-10-29")):
    return pd.DataFrame(
        {"AAPL":aapl,"SPY":spy},index=pd.to_datetime(list(dates)))

def test_latest_true_sec100_zero_exposure_requires_no_price_download():
    result=u7.evaluate(frozen(),prices=None)
    assert result["status"]=="NO_SOURCE_QUALIFIED_NEW_EVENTS"
    assert result["unique_model_exposures"]==0
    assert result["priced_two_close_exposures"]==0
    assert result["later_price_source_csv_sha256"] is None
    assert not result["source_dated_return_observations"]
    assert result["broker_gets"]==result["broker_posts"]==result["broker_orders"]==0

def test_no_prior_first_seen_unknown_remains_no_entry():
    cohort=u6.freeze_verified_delta(report(with_previous=False))
    out=u7.evaluate(cohort,prices=None)
    assert out["unique_model_exposures"]==0
    assert out["priced_two_close_exposures"]==0

def test_source_first_and_independently_later_close_mark_has_costed_spy():
    source=frozen(new_row())
    out=u7.evaluate(source,prices=panel(),
        later_price_acquired_utc="2026-10-30T19:00:00Z",
        provider_reference="independent yfinance completed-price source Oct 30")
    assert out["status"]=="SOURCE_DATED_DESCRIPTIVE_FORWARD_MARKS_NOT_ALPHA"
    assert out["priced_two_close_exposures"]==1
    r=out["source_dated_return_observations"][0]
    assert r["frozen_entry_close"]=="2026-10-28"
    assert r["frozen_exit_close"]=="2026-10-29"
    assert r["stock_two_close_gross_return"]==pytest.approx(.1)
    assert r["spy_two_close_gross_return"]==pytest.approx(.02)
    assert r["stock_net_minus_spy_net_percentage_points"]["15"] == pytest.approx(
        100*(1.1-1.02)*(1-0.0015)**2,abs=1e-8)
    assert r["stock_net_minus_gross_spy_percentage_points"]["15"] == pytest.approx(
        100*(1.1*(1-0.0015)**2-1.02),abs=1e-8)
    assert out["statistically_proven_alpha"] is False
    assert out["broker_orders"]==0 and out["trading_authorized"] is False
    assert len(out["later_price_source_csv_sha256"])==64

def test_future_closes_not_available_stays_pending():
    out=u7.evaluate(frozen(new_row()),prices=panel(aapl=(100.,),
                              spy=(200.,),dates=("2026-10-28",)),
        later_price_acquired_utc="2026-10-29T19:00:00Z",
        provider_reference="one completed close only vendor original")
    assert out["pending_two_close_exposures"]==1
    assert out["priced_two_close_exposures"]==0
    assert out["source_dated_return_observations"][0]["stock_two_close_gross_return"] is None

def test_two_filings_same_stock_same_entry_are_one_return():
    cohort=frozen(new_row(),new_row(accession="0000000123-26-000002"))
    out=u7.evaluate(cohort,prices=panel(),
        later_price_acquired_utc="2026-10-30T19:00:00Z",
        provider_reference="independent original stock and spy source")
    assert out["unique_model_exposures"]==1
    assert out["priced_two_close_exposures"]==1
    assert len(out["source_dated_return_observations"][0]["original_earnings_accessions"])==2

@pytest.mark.parametrize("mutate",[
    lambda a:a.update(alpha_established=True),
    lambda a:a.update(broker_orders=1),
    lambda a:a.update(trading_authorized=True),
    lambda a:a.update(forward_price_mark_count=1),
    lambda a:a.update(distinct_model_exposures=2),
    lambda a:a.update(new_accessions_relative_to_preceding_successful_observer=2),
    lambda a:a["deduplicated_stock_entry_exposures"][0].update(entry_close="2026-10-27"),
    lambda a:a["deduplicated_stock_entry_exposures"][0].update(
        stock_and_SPY_future_closes_authenticated=True),
    lambda a:a["deduplicated_stock_entry_exposures"][0].update(
        accessions=["0000000123-26-999999"]),
    lambda a:a["deduplicated_stock_entry_exposures"].append(
        deepcopy(a["deduplicated_stock_entry_exposures"][0])),
])
def test_tampered_original_source_or_selected_entry_cannot_mark(mutate):
    c=frozen(new_row())
    mutate(c)
    with pytest.raises((u7.MarkStop,u6.ForwardAdmissionStop)):
        u7.evaluate(c,prices=None)

@pytest.mark.parametrize("frame",[
    panel().drop(columns=["SPY"]),
    panel(aapl=(100.,np.nan)),
    panel(aapl=(100.,160.)),
    panel(dates=("2026-10-28","2026-10-30")),
    panel(dates=("2026-10-29","2026-10-28")),
])
def test_price_lineage_missing_sessions_symbols_nonfinite_or_gap_fail(frame):
    with pytest.raises(u7.MarkStop):
        u7.evaluate(frozen(new_row()),prices=frame,
            later_price_acquired_utc="2026-11-02T18:30:00Z",
            provider_reference="independent price panel with original source dates")

def test_no_same_day_or_early_price_vintage_lookahead():
    for when in ("2026-10-27T18:31:00Z","2026-10-29T21:00:00Z"):
        with pytest.raises(u7.MarkStop):
            u7.evaluate(frozen(new_row()),prices=panel(),
                later_price_acquired_utc=when,
                provider_reference="invalid source timestamp independent observation")

def test_zero_source_does_not_accept_prices_for_spurious_universe():
    with pytest.raises(u7.MarkStop):
        u7.evaluate(frozen(),prices=panel(),
            later_price_acquired_utc="2026-10-30T20:00:00Z",
            provider_reference="must not fetch prices when no new SEC events")

def test_missing_price_metadata_or_source_disagreement_is_rejected():
    with pytest.raises(u7.MarkStop):
        u7.evaluate(frozen(new_row()),prices=panel())
    with pytest.raises(u7.MarkStop):
        u7.evaluate(frozen(new_row()),prices=None,
            provider_reference="misleading market data without prices")

def test_original_raw_u5_sources_replayed_by_entry_function(monkeypatch):
    called=[]
    def read_and_freeze(**kwargs):
        called.append(kwargs)
        return frozen(new_row())
    monkeypatch.setattr(u7.u6,"freeze_from_sources",read_and_freeze)
    original=u7.u6.freeze_from_sources(original_u3="u3",original_first_sec="u4",
        later_sec="u5",previous_sec="prior",previous_main_id=40560695303)
    got=u7.evaluate(original,prices=None)
    assert got["priced_two_close_exposures"]==0
    assert called[0]["previous_main_id"]==40560695303

def test_first_authentic_sec100_followup_is_main_only_and_read_only():
    from pathlib import Path
    text=Path(".github/workflows/fund100-v7-u7-sec100-forward-marks.yml").read_text()
    assert "if: github.ref == 'refs/heads/main' && github.event_name != 'pull_request'" in text
    assert "permissions:\\n  contents: read\\n  actions: read" in text
    assert "cancel-in-progress: false" in text
    assert "FUND100_BROKER_KILL_SWITCH: ENGAGED" in text
    assert "FUND100_LIVE_WRITE_MODE: DISABLED" in text
    for run in ("40545345749", "40550119246", "40563410754", "40621873197"):
        assert run in text
    assert "--previous-successful-main-run-id 40563410754" in text
    assert "fund100_v7_u7_sec100_two_close_costed_mark_v1_0.py" in text
    assert "actions/upload-artifact@v4" in text
    assert "if-no-files-found: error" in text
    assert "git push" not in text and "alpaca" not in text.lower()
