"""Offline V9-F2 finance two-original-10K research ratio evidence, no trading."""
from copy import deepcopy

import pytest
import fund100_v9_f2_original_finance_ratio_source_v1_0 as f2
from test_fund100_v9_broad_original_sec_quality_coverage_v1_0 import (
    _finance_sample,
)

ASOF="2026-11-10"
BANK="SEC_SIC_BANK_LENDING_CREDIT_AND_FINANCE_REVIEW_ONLY"
CIK="0000320193"


def describe(facts=None,submissions=None,**overrides):
    if facts is None or submissions is None:
        facts,submissions=_finance_sample()
    args=dict(
        companyfacts=facts,submissions=submissions,cik=CIK,
        asof=ASOF,subtype=BANK,core_source_state=f2.READY)
    args.update(overrides)
    return f2.describe(**args)


def test_original_two_fiscal_year_10k_finance_ratios_are_unscored():
    d=describe()
    assert d["schema"]==f2.SCHEMA
    assert d["status"]==f2.OUTPUT
    assert d["latest_return_on_average_assets_bucket"]=="ROAA_AT_LEAST_TWO_PERCENT"
    assert d["latest_equity_to_assets_bucket"]=="EQUITY_TO_ASSETS_AT_LEAST_FIFTEEN_PERCENT"
    assert d["net_income_two_year_sign_state"]=="POSITIVE_BOTH_ORIGINAL_FYS"
    assert d["source_original_two_10k_consecutive"] is True
    assert d["ratio_not_credit_capital_or_valuation"] is True
    assert d["issuer_rank"] is d["trade_decision"] is None
    assert d["broker_gets"]==d["broker_posts"]==d["broker_orders"]==0
    assert d["live_authorized"] is False
    assert CIK not in str(d)
    assert f2.LIVE_AUTHORIZED is False


@pytest.mark.parametrize("input",[
    {"core_source_state":"FINANCE_CORE_FACTS_NOT_IN_SAME_TWO_OWN_10KS"},
    {"subtype":"SEC_SIC_BLANK_CHECK_COMPANY_6770_NOT_STOCK_APPROVAL"},
    {"subtype":"SEC_SIC_REIT_6798_REVIEW_ONLY"},
    {"subtype":"SEC_SIC_INSURANCE_UNDERWRITING_SERVICES_REVIEW_ONLY"},
    {"cik":"0000000001"},
    {"asof":"2026-11-05"},
    {"asof":"2028-11-10"},
])
def test_unqualified_finance_source_cannot_infer_a_tradable_accounting_grade(input):
    with pytest.raises(f2.FinanceRatioHold):
        describe(**input)


def test_bank_sic_current_source_mismatch_never_uses_wrong_finance_bucket():
    facts,sub=_finance_sample()
    sub["sic"]="6798"
    with pytest.raises(f2.FinanceRatioHold):
        describe(facts,sub)


def test_missing_original_accession_is_not_a_later_comparative_fact():
    facts,sub=_finance_sample()
    rows=facts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"]
    rows[0]["accn"]=rows[1]["accn"]
    rows[0]["filed"]=rows[1]["filed"]
    with pytest.raises(f2.FinanceRatioHold):
        describe(facts,sub)


def test_annual_income_requires_full_fiscal_period_and_balance_requires_instant():
    facts,sub=_finance_sample()
    del facts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]["start"]
    with pytest.raises(f2.FinanceRatioHold):
        describe(facts,sub)
    facts,sub=_finance_sample()
    facts["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]["start"]="2024-10-31"
    with pytest.raises(f2.FinanceRatioHold):
        describe(facts,sub)


def test_fiscal_amendment_same_year_never_chooses_a_favourable_revision():
    facts,sub=_finance_sample()
    extra={
        "accessionNumber":"0000320193-26-000099","form":"10-K",
        "filingDate":"2026-11-04","reportDate":"2026-10-30",
        "acceptanceDateTime":"2026-11-04T19:00:00.000Z",
    }
    for field,values in sub["filings"]["recent"].items():
        values.append(extra[field])
    with pytest.raises(f2.FinanceRatioHold):
        describe(facts,sub)


@pytest.mark.parametrize("invalid",[True,None,float("nan"),float("inf"),1e16,"123"])
def test_invalid_original_finance_usd_never_scores(invalid):
    facts,sub=_finance_sample()
    facts["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]["val"]=invalid
    with pytest.raises(f2.FinanceRatioHold):
        describe(facts,sub)


def test_conflicting_same_accession_original_fact_never_selects_highest_profit():
    facts,sub=_finance_sample()
    rows=facts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"]
    altered=dict(rows[-1],val=rows[-1]["val"]*2)
    rows.append(altered)
    with pytest.raises(f2.FinanceRatioHold):
        describe(facts,sub)


def test_nonpositive_denominator_never_generates_misleading_ratios():
    facts,sub=_finance_sample()
    facts["facts"]["us-gaap"]["Assets"]["units"]["USD"][-1]["val"]=0
    z=describe(facts,sub)
    assert z["status"]=="ORIGINAL_FINANCE_NONPOSITIVE_ASSETS_RATIO_UNAVAILABLE"
    assert z["latest_return_on_average_assets_bucket"] is None
    assert z["latest_equity_to_assets_bucket"] is None
    assert z["trade_decision"] is None


def test_negative_profit_and_equity_are_not_hidden_by_positive_companyfacts_history():
    facts,sub=_finance_sample()
    concepts=facts["facts"]["us-gaap"]
    concepts["NetIncomeLoss"]["units"]["USD"][-1]["val"]=-25_000_000
    concepts["StockholdersEquity"]["units"]["USD"][-1]["val"]=-2_000_000
    z=describe(facts,sub)
    assert z["latest_return_on_average_assets_bucket"]=="ROAA_NONPOSITIVE"
    assert z["latest_equity_to_assets_bucket"]=="EQUITY_TO_ASSETS_NONPOSITIVE"
    assert z["net_income_two_year_sign_state"]=="LATEST_ORIGINAL_FY_NONPOSITIVE"


def test_original_sample_broad_coverage_emits_only_bounded_subtype_counts():
    import json
    import fund100_v9_broad_original_sec_quality_coverage_v1_0 as broad
    from test_fund100_v9_broad_original_sec_quality_coverage_v1_0 import run,_apple_source
    def loader(cik,kind):
        if cik==320193:
            return _apple_source(cik,kind)
        facts,sub=_finance_sample()
        facts["cik"]=sub["cik"]=51143
        facts["facts"]["us-gaap"].pop(broad.quality.ANNUAL_TAGS["revenue"])
        return json.dumps(facts if kind=="companyfacts" else sub).encode()
    output=run(fetcher=loader)
    assert output["current_SEC_finance_original_own_10K_ratio_source_status_NOT_a_score"]=={
        f2.OUTPUT:1}
    assert output["current_SEC_finance_current_SIC_ROAA_descriptive_bucket_counts_NOT_a_grade"]=={
        BANK:{"ROAA_AT_LEAST_TWO_PERCENT":1}}
    assert output["current_SEC_finance_current_SIC_equity_to_assets_descriptive_bucket_counts_NOT_capital_grade"]=={
        BANK:{"EQUITY_TO_ASSETS_AT_LEAST_FIFTEEN_PERCENT":1}}
    assert output["current_SEC_finance_current_SIC_two_original_10K_net_income_sign_counts_NOT_a_forecast"]=={
        BANK:{"POSITIVE_BOTH_ORIGINAL_FYS":1}}
    assert output["finance_ratio_descriptions_do_not_validate_bank_credit_or_security_valuation"] is True
    assert output["sample_outcome_counts"]["generic_two_fiscal_year_filing_lagged_score_available"]==1
    assert output["broker_reads"]==output["broker_orders"]==output["private_state_writes"]==0
    payload=json.dumps(output)
    assert "0000320193" not in payload and "0000051143" not in payload
