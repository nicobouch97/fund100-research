"""Q1 source-stage tests: synthetic accounting fixtures, no stock orders or values."""
from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_q1_original_sec_cash_proxy_v1_0 as q
import fund100_stock_quality_momentum_p4g_v1_0 as p4g


def baseline():
    missing={"XOM","JNJ"}
    obs=[]
    values={}
    for sym in q.TICKERS:
        good=sym not in missing
        obs.append({
          "ticker":sym,"cik":"0000000001",
          "asof_research_date":"2026-10-15",
          "state":("DESCRIPTIVE_NEWEST_ORIGINAL_10K_ISSUER_SPECIFIC_QUALITY"
                   if good else "LATEST_10K_MISSING_FROZEN_OR_COMPARATIVE_GAAP_FACT"),
          "quality_score":3 if good else None,
          "latest_10k_accession":"0001-26-000001",
          "latest_10k_filing_date":"2026-02-15",
          "capex_source_tag":"PaymentsToAcquireProductiveAssets"
             if sym=="AMZN" else "PaymentsToAcquirePropertyPlantAndEquipment",
          "free_cash_flow_margin":0.1 if good else None,
        })
        values[sym]=({"accession":"0001-26-000001",
                      "operating_cash_usd":150.0,"productive_asset_spend_usd":50.0,
                      "revenue_usd":1000.0} if good else {})
    return obs,values


def run():
    rows,values=baseline()
    return q.summarize(issuer_observations=rows,financial_values=values,
      source_manifest_sha256=p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256,
      original_capture_utc=p4g.FROZEN_SEC_OBSERVED_AT_UTC)


def test_cash_proxy_not_buffett_owner_earnings_or_trading_alpha():
    x=run()
    assert x["issuer_cfo_capex_complete_count"]==6
    assert x["issuer_count"]==8 and x["unknown_issuer_count"]==2
    assert not x["price_valuation_signal_available"] and not x["maintenance_capex_verified"]
    assert not x["live_authorized"] and not x["paper_authorized"]
    assert x["broker_calls"]==x["broker_orders"]==0
    assert len(x["valuation_and_owner_earnings_inputs_missing"])>=7
    assert "NOT_OWNER_EARNINGS" in x["accounting_measure"]


def test_one_sourced_cash_example_is_not_hindsight_fair_value():
    x=run()
    first=x["observations"][0]
    assert first["cash_proxy"]["reported_operating_cash_after_asset_spending_usd"]=="100.0"
    assert first["cash_proxy"]["reported_operating_cash_after_spending_margin"]=="0.10000000"
    assert first["historic_fair_value_signal_available"] is False
    assert first["current_trade_signal_available"] is False


def test_unknown_stays_unknown_never_interpreted_as_weak_stock():
    x=run()
    for row in x["observations"]:
        if row["ticker"] in ("XOM","JNJ"):
            assert row["cash_proxy"] is None
            assert row["p4e_quality_score"] is None
            assert row["accounting_source_status"].startswith("UNKNOWN")


@pytest.mark.parametrize("field,value",[
 ("operating_cash_usd","NaN"),
 ("productive_asset_spend_usd","Infinity"),
 ("productive_asset_spend_usd",-1),
 ("revenue_usd",0),
 ("revenue_usd",-10),
])
def test_invalid_accounting_facts_fail_closed(field,value):
    rows,values=baseline()
    values["AAPL"][field]=value
    with pytest.raises(q.Q1SourceStop):
        q.summarize(issuer_observations=rows,financial_values=values,
          source_manifest_sha256=p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256,
          original_capture_utc=p4g.FROZEN_SEC_OBSERVED_AT_UTC)


def test_source_manifest_vintage_not_replaceable():
    rows,values=baseline()
    for source,date in [("0"*64,p4g.FROZEN_SEC_OBSERVED_AT_UTC),
                        (p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256,"2026-10-19T00:00:00Z")]:
        with pytest.raises(q.Q1SourceStop):
            q.summarize(issuer_observations=rows,financial_values=values,
              source_manifest_sha256=source,original_capture_utc=date)


def test_different_accession_or_wrong_quality_valuation_cannot_pass():
    rows,values=baseline()
    values["AAPL"]["accession"]="replaced"
    with pytest.raises(q.Q1SourceStop):
        q.summarize(issuer_observations=rows,financial_values=values,
          source_manifest_sha256=p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256,
          original_capture_utc=p4g.FROZEN_SEC_OBSERVED_AT_UTC)


def test_refuses_hindsight_issuer_bench_expansion():
    rows,values=baseline()
    rows.append(deepcopy(rows[0]))
    with pytest.raises(q.Q1SourceStop):
        q.summarize(issuer_observations=rows,financial_values=values,
          source_manifest_sha256=p4g.FROZEN_SEC_SOURCE_MANIFEST_SHA256,
          original_capture_utc=p4g.FROZEN_SEC_OBSERVED_AT_UTC)


def test_no_stock_prices_broker_or_direct_network_in_pure_source_engine():
    txt=(Path(__file__).resolve().parent/"fund100_v6_q1_original_sec_cash_proxy_v1_0.py").read_text()
    for token in ("ALPACA_LIVE_KEY","ALPACA_PAPER_KEY","/v2/orders","requests.post(","urlopen(","yfinance","place_order("):
        assert token not in txt
    assert q.REPORT_ONLY.startswith("DESCRIPTIVE")
    assert q.MISSING_VALUATION
