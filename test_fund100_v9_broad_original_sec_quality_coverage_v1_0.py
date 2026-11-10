"""No-network source/provenance tests for V9 original SEC quality coverage."""
from datetime import datetime, timezone
import json
import pytest

import fund100_v9_broad_original_sec_quality_coverage_v1_0 as m
import test_fund100_v9_sec_current_listing_association_v1_0 as fx
import test_fund100_stock_sec_quality_p4a_v1_0 as fqa

ASOF = datetime(2026,11,10,18,0,tzinfo=timezone.utc)
FILES = fx.directories()
REGISTRY = fx.sec_json()


def get_sample(**kw):
    return m.eligible_issuer_sample(
        directories=FILES, sec_associations=REGISTRY,
        observed=ASOF, sample_n=2, min_pool=2, **kw)


def test_original_exact_exchange_and_common_wording_issuer_sample():
    ciks, fingerprint, original = get_sample()
    assert set(ciks)=={320193,51143}
    assert len(fingerprint)==64
    assert original["distinct_current_SEC_CIKs_with_explicit_common_wording_only"]==2
    assert original["association_reason_counts"]["exact_current_ticker_and_exchange_associations"]==3
    assert get_sample()[0]==ciks
    assert 1067983 not in ciks  # BRK-B versus BRK.B remains unjoined
    assert 789019 not in ciks   # unresolved security name, not explicit common


def _apple_source(cik, kind):
    if cik!=320193:
        return None
    facts, submissions = fqa.sample()
    return json.dumps(facts if kind=="companyfacts" else submissions).encode()


def run(fetcher=_apple_source, **kw):
    return m.annual_coverage(
        directories=FILES, sec_associations=REGISTRY, observed=ASOF,
        fetcher=fetcher, sample_n=2, min_pool=2, **kw)


def test_source_linked_eligible_apple_and_independent_ibm_404_are_counted():
    out=run()
    assert out["sample_size"]==2
    assert out["sample_outcome_counts"]=={
        "at_least_one_SEC_document_HTTP_404":1,
        "both_SEC_documents_received_and_CIK_matched":1,
        "generic_two_fiscal_year_filing_lagged_score_available":1,
    }
    assert out["generic_original_filing_contract_states"]=={
        "ANNUAL_REPORTED_QUALITY_AVAILABLE_NOT_TRADE_READY":1,
    }
    assert out["official_SEC_document_bytes_observed"]>100
    assert len(out["official_SEC_documents_observed_sha256_aggregate"])==64
    assert out["selection_method"]=="PREDECLARED_SHA256_CIK_SORT_NO_RETURN_OR_FINANCIAL_SELECTION"
    assert out["sample_is_persistently_replayable_without_archived_original_bytes"] is False
    assert out["share_class_market_cap_or_valuation_proven"] is False
    assert out["point_in_time_historical_universe_authenticated"] is False
    assert out["live_authorized"] is False
    assert out["broker_reads"]==out["broker_orders"]==out["private_state_writes"]==0
    text=json.dumps(out)
    for forbidden in ('"AAPL"','"IBM"','"0000320193"','"0000051143"','Apple Inc.'):
        assert forbidden not in text


def test_industrial_quality_model_missing_is_not_zero_imputed():
    def loader(cik, kind):
        if cik==320193:
            return _apple_source(cik,kind)
        facts,sub=fqa.sample()
        if kind=="companyfacts":
            return json.dumps({"cik":51143, "facts":{"us-gaap":{}}}).encode()
        sub["cik"]=51143
        return json.dumps(sub).encode()
    out=run(fetcher=loader)
    assert out["sample_outcome_counts"]=={
        "both_SEC_documents_received_and_CIK_matched":2,
        "generic_filing_lagged_score_unavailable":1,
        "generic_two_fiscal_year_filing_lagged_score_available":1,
    }
    assert out["generic_original_filing_contract_states"][
        "MISSING_ELIGIBLE_FULL_YEAR_FILINGS"]==1


def test_source_identity_mismatch_is_hard_hold_not_missing():
    def bad(cik, kind):
        f,s=fqa.sample()
        return json.dumps(f if kind=="companyfacts" else s).encode()
    with pytest.raises(m.SourceHold,match="identity"):
        run(fetcher=bad)


def test_untrusted_loader_data_is_hard_hold():
    with pytest.raises(m.SourceHold,match="bytes"):
        run(fetcher=lambda cik,kind:"not original bytes")


def test_no_funding_permissions_or_new_trading_authority():
    assert m.LIVE_AUTHORIZED is False
    assert m.NO_BROKER_READS==m.NO_BROKER_ORDERS==m.NO_PRIVATE_WRITES==0
    assert m.SAMPLE_N==32
    assert m.MIN_CURRENT_CIK_POOL==1000
    assert m.SLEEP_PER_SEC_REQUEST>=0.35
    from pathlib import Path
    code=Path(m.__file__).read_text()
    assert "alpaca" not in code.lower()
    assert "submit_order" not in code


def test_small_or_nonreplayable_pool_and_invalid_params_fail():
    with pytest.raises(m.SourceHold):
        m.eligible_issuer_sample(directories=FILES,sec_associations=REGISTRY,
                                 observed=ASOF,sample_n=3,min_pool=3)
    with pytest.raises(m.SourceHold):
        m.eligible_issuer_sample(directories=FILES,sec_associations=REGISTRY,
                                 observed=ASOF,sample_n=33,min_pool=33)
    with pytest.raises(m.SourceHold):
        m.eligible_issuer_sample(directories=FILES,sec_associations=REGISTRY,
                                 observed=ASOF,sample_n=2,min_pool=1)


def test_original_symbol_and_sec_schema_fail_closed():
    broken=fx.directories()
    broken["nasdaqlisted.txt"]=b"MALFORMED"
    with pytest.raises((m.SourceHold,m.listing.ListingsStop)):
        m.eligible_issuer_sample(directories=broken,sec_associations=REGISTRY,
                                 observed=ASOF,sample_n=2,min_pool=2)
    with pytest.raises((m.SourceHold,m.link.AssociationStop)):
        m.eligible_issuer_sample(directories=FILES,sec_associations=b"{}",
                                 observed=ASOF,sample_n=2,min_pool=2)
