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
    assert out["original_current_SEC_taxonomy_namespace_by_P4A_outcome_NOT_an_accounting_model"]=={
        "ORIGINAL_GENERIC_SCORE_AVAILABLE":{
            "CURRENT_SEC_US_GAAP_NAMESPACE_SOURCE_ONLY":1}}
    assert out["original_current_SEC_SIC_coarse_band_by_P4A_outcome_NOT_an_industry_exposure"]=={
        "ORIGINAL_GENERIC_SCORE_AVAILABLE":{
            "CURRENT_SEC_SIC_UNAVAILABLE_NO_SECTOR_INFERENCE":1}}
    assert out["SEC_current_SIC_does_not_verify_US_common_security_or_sector_accounting"] is True
    assert out["sample_outcome_counts"]=={
        "at_least_one_SEC_document_HTTP_404":1,
        "both_SEC_documents_received_and_CIK_matched":1,
        "generic_two_fiscal_year_filing_lagged_score_available":1,
    }
    assert out["generic_original_filing_contract_states"]=={
        "ANNUAL_REPORTED_QUALITY_AVAILABLE_NOT_TRADE_READY":1,
    }
    assert out["unscored_original_source_reason_counts"]=={}
    assert out["missing_exact_generic_usgaap_USD_tag_issuer_counts"]=={}
    assert out["possible_alternative_usgaap_tag_presence_NOT_a_substitute"]=={}
    assert out["no_alternative_tag_applied_to_quality_score"] is True
    assert out["generic_unavailable_issuers_with_undownloaded_older_SEC_file_descriptors_only"]==0
    assert out["filings_files_metadata_does_not_prove_archived_10K_or_authorize_backfill"] is True
    assert out["unscored_source_reasons_are_not_company_valuation_judgments"] is True
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
    assert out["unscored_original_source_reason_counts"]=={
        "TWO_PLUS_10K_MISSING_GENERIC_CONCEPT_OR_USD_ROWS":1
    }
    assert out["missing_exact_generic_usgaap_USD_tag_issuer_counts"]=={
        "revenue":1, "operating_income":1, "operating_cash_flow":1,
        "capital_expenditure":1,
    }
    assert out["joint_four_input_same_two_original_10K_years_source_states_NOT_a_score"]=={
        "MISSING_ANY_USD_SOURCE_TAG_FOR_ONE_OR_MORE_INPUTS":1,
    }
    assert out["possible_alternative_usgaap_tag_presence_NOT_a_substitute"]=={}
    assert out["generic_unavailable_issuers_with_undownloaded_older_SEC_file_descriptors_only"]==0


@pytest.mark.parametrize("form_count,reason", [
    (0, "ZERO_10K_IN_RECENT_SUBMISSIONS_LEDGER"),
    (1, "ONE_10K_IN_RECENT_SUBMISSIONS_LEDGER"),
    (2, "TWO_PLUS_10K_CONCEPTS_PRESENT_BUT_NO_QUALIFIED_PAIR"),
])
def test_no_fake_historical_10k_from_metadata_only(form_count, reason):
    facts,sub=fqa.sample()
    sub["filings"]["recent"]["form"]=[
        "10-K" if i<form_count else "8-K" for i in range(2)]
    sub["filings"]["files"]=[{
        "name":"CIK0000320193-submissions-001.json",
        "filingFrom":"2022-01-01",
        "filingTo":"2024-12-31",
        "filingCount":500,
    }]
    observed=m._unscored_source_reason(
        companyfacts=facts,submissions=sub,
        model_state="MISSING_ELIGIBLE_FULL_YEAR_FILINGS")
    assert observed==(reason,True)
    assert m._unscored_source_reason(
        companyfacts=facts,submissions=sub,
        model_state="LAST_ANNUAL_REPORT_TOO_STALE")==(
        "LATEST_ANNUAL_TOO_STALE",True)


def test_two_recent_10k_but_a_generic_revenue_tag_missing_is_not_extrapolated():
    facts,sub=fqa.sample()
    del facts["facts"]["us-gaap"][m.quality.ANNUAL_TAGS["revenue"]]
    category,old_files=m._unscored_source_reason(
        companyfacts=facts,submissions=sub,
        model_state="MISSING_ELIGIBLE_FULL_YEAR_FILINGS")
    assert category=="TWO_PLUS_10K_MISSING_GENERIC_CONCEPT_OR_USD_ROWS"
    assert old_files is False


def test_full_live_sample_counts_missing_10k_separately_from_invalid_facts():
    def loader(cik,kind):
        if cik==320193:
            return _apple_source(cik,kind)
        facts,sub=fqa.sample()
        if kind=="companyfacts":
            facts["cik"]=51143
            return json.dumps(facts).encode()
        sub["cik"]=51143
        sub["filings"]["recent"]["form"]=["8-K","8-K"]
        sub["filings"]["files"]=[{"name":"not-downloaded-older-source.json"}]
        return json.dumps(sub).encode()
    out=run(fetcher=loader)
    assert out["sample_outcome_counts"][
        "generic_filing_lagged_score_unavailable"]==1
    assert out["unscored_original_source_reason_counts"]=={
        "ZERO_10K_IN_RECENT_SUBMISSIONS_LEDGER":1
    }
    assert out["generic_unavailable_issuers_with_undownloaded_older_SEC_file_descriptors_only"]==1
    assert "not-downloaded-older-source" not in json.dumps(out)


def test_strict_P4A_fact_conflict_quarantined_not_inferred_as_bad_issuer():
    def loader(cik,kind):
        if cik!=320193:
            return None
        facts, sub=fqa.sample()
        if kind=="companyfacts":
            d=facts["facts"]["us-gaap"]
            tag=m.quality.ANNUAL_TAGS["revenue"]
            invalid=dict(d[tag]["units"]["USD"][0])
            invalid["val"] += 1
            d[tag]["units"]["USD"].append(invalid)
        return json.dumps(facts if kind=="companyfacts" else sub).encode()
    out=run(fetcher=loader)
    assert out["sample_outcome_counts"]=={
        "at_least_one_SEC_document_HTTP_404":1,
        "both_SEC_documents_received_and_CIK_matched":1,
        "SEC_facts_incompatible_with_generic_industrial_quality_contract":1,
    }
    assert out["unscored_original_source_reason_counts"]=={
        "P4A_ORIGINAL_SOURCE_STRICT_VALIDATION_REJECTED":1
    }
    assert out["generic_unavailable_issuers_with_undownloaded_older_SEC_file_descriptors_only"]==0


def test_optional_SEC_older_descriptor_malformed_type_is_hard_hold():
    facts,sub=fqa.sample()
    sub["filings"]["files"]={"name":"fake"}
    with pytest.raises(m.SourceHold,match="descriptors"):
        m._unscored_source_reason(
            companyfacts=facts,submissions=sub,
            model_state="MISSING_ELIGIBLE_FULL_YEAR_FILINGS")


def test_alternative_revenue_and_capex_tag_presence_is_no_annual_score():
    """Even tags with matching USD rows do not stand in for own-10-K accounts."""
    def load(cik, kind):
        if cik==320193:
            return _apple_source(cik,kind)
        facts,sub=fqa.sample()
        if kind=="companyfacts":
            facts["cik"]=51143
            gaap=facts["facts"]["us-gaap"]
            revenue=gaap.pop(m.quality.ANNUAL_TAGS["revenue"])
            capex=gaap.pop(m.quality.ANNUAL_TAGS["capital_expenditure"])
            gaap["Revenues"]=revenue
            gaap["SalesRevenueNet"]=revenue
            gaap["PaymentsToAcquireProductiveAssets"]=capex
            return json.dumps(facts).encode()
        sub["cik"]=51143
        return json.dumps(sub).encode()
    out=run(fetcher=load)
    assert out["sample_outcome_counts"][
        "generic_two_fiscal_year_filing_lagged_score_available"]==1
    assert out["sample_outcome_counts"]["generic_filing_lagged_score_unavailable"]==1
    assert out["unscored_original_source_reason_counts"]=={
        "TWO_PLUS_10K_MISSING_GENERIC_CONCEPT_OR_USD_ROWS":1,
    }
    assert out["missing_exact_generic_usgaap_USD_tag_issuer_counts"]=={
        "revenue":1, "capital_expenditure":1
    }
    assert out["possible_alternative_usgaap_tag_presence_NOT_a_substitute"]=={
        "revenue:Revenues":1,
        "revenue:SalesRevenueNet":1,
        "capital_expenditure:PaymentsToAcquireProductiveAssets":1,
    }
    assert out["alternative_tag_original_10K_own_accession_pair_diagnostics_NOT_equivalence"]=={
        "revenue:Revenues:TWO_OWN_ACCESSION_10K_FY_FACTS_REVIEW_ONLY_NOT_EQUIVALENT":1,
        "revenue:SalesRevenueNet:TWO_OWN_ACCESSION_10K_FY_FACTS_REVIEW_ONLY_NOT_EQUIVALENT":1,
        "capital_expenditure:PaymentsToAcquireProductiveAssets:TWO_OWN_ACCESSION_10K_FY_FACTS_REVIEW_ONLY_NOT_EQUIVALENT":1,
    }
    assert out["joint_four_input_same_two_original_10K_years_source_states_NOT_a_score"]=={
        "MULTIPLE_ALTERNATIVE_TAG_OPTIONS_NO_ARBITRARY_PICK":1,
    }
    assert out["joint_four_input_source_alignment_never_promotes_original_P4A_score"] is True
    assert out["alternative_10K_pair_diagnostic_does_not_make_revenue_capex_interchangeable"] is True
    assert out["alternative_tag_exists_in_any_current_companyfacts_not_same_10K_proof"] is True
    assert out["no_alternative_tag_applied_to_quality_score"] is True
    assert "Apple Inc." not in json.dumps(out)
    assert out["broker_orders"]==out["broker_reads"]==0


def test_alternate_tag_without_USD_rows_is_not_evidence():
    def loader(cik,kind):
        if cik==320193:
            return _apple_source(cik,kind)
        facts,sub=fqa.sample()
        if kind=="companyfacts":
            facts["cik"]=51143
            gaap=facts["facts"]["us-gaap"]
            del gaap[m.quality.ANNUAL_TAGS["revenue"]]
            gaap["Revenues"]={"units":{"shares":[{"val":10}]}}
            return json.dumps(facts).encode()
        sub["cik"]=51143
        return json.dumps(sub).encode()
    out=run(fetcher=loader)
    assert out["missing_exact_generic_usgaap_USD_tag_issuer_counts"]=={"revenue":1}
    assert out["possible_alternative_usgaap_tag_presence_NOT_a_substitute"]=={}
    assert out["alternative_tag_original_10K_own_accession_pair_diagnostics_NOT_equivalence"]=={}


def test_alternative_10k_source_fact_only_one_own_fiscal_year_cannot_qualify():
    facts,sub=fqa.sample()
    gaap=facts["facts"]["us-gaap"]
    gaap["Revenues"]={"units":{"USD":[
        dict(gaap[m.quality.ANNUAL_TAGS["revenue"]]["units"]["USD"][-1])
    ]}}
    assert m._alternative_original_10k_pair_status(
        companyfacts=facts,submissions=sub,tag="Revenues",
        asof="2026-11-10")=="FEWER_THAN_TWO_ELIGIBLE_OWN_10K_FISCAL_YEARS"


def test_alternative_comparative_disclosed_later_cannot_retroactively_pass():
    facts,sub=fqa.sample()
    rows=facts["facts"]["us-gaap"][m.quality.ANNUAL_TAGS["revenue"]]["units"]["USD"]
    amended=[dict(x) for x in rows]
    amended[0]["accn"]=fqa.ACCESSIONS[-1]
    amended[0]["filed"]=fqa.FILINGS[-1]
    facts["facts"]["us-gaap"]["Revenues"]={"units":{"USD":amended}}
    assert m._alternative_original_10k_pair_status(
        companyfacts=facts,submissions=sub,tag="Revenues",
        asof="2026-11-10")=="FEWER_THAN_TWO_ELIGIBLE_OWN_10K_FISCAL_YEARS"


def test_second_10k_not_eligible_until_two_weekday_filing_lag():
    facts,sub=fqa.sample()
    gaap=facts["facts"]["us-gaap"]
    gaap["Revenues"]=gaap[m.quality.ANNUAL_TAGS["revenue"]]
    sub["filings"]["recent"]["filingDate"][-1]="2026-11-09"
    gaap["Revenues"]["units"]["USD"][-1]["filed"]="2026-11-09"
    assert m._alternative_original_10k_pair_status(
        companyfacts=facts,submissions=sub,tag="Revenues",
        asof="2026-11-10")=="FEWER_THAN_TWO_ELIGIBLE_OWN_10K_FISCAL_YEARS"


def test_amended_same_fy_original_10k_must_remain_ambiguous():
    facts,sub=fqa.sample()
    gaap=facts["facts"]["us-gaap"]
    gaap["Revenues"]={"units":{"USD":[dict(x)
        for x in gaap[m.quality.ANNUAL_TAGS["revenue"]]["units"]["USD"]]}}
    amended="0000320193-26-000099"
    for key, values in sub["filings"]["recent"].items():
        values.append({
            "accessionNumber":amended,
            "form":"10-K",
            "filingDate":"2026-11-04",
            "reportDate":"2026-10-30",
            "acceptanceDateTime":"2026-11-04T19:00:00.000Z",
        }[key])
    row=dict(gaap["Revenues"]["units"]["USD"][-1])
    row["accn"]=amended
    gaap["Revenues"]["units"]["USD"].append(row)
    assert m._alternative_original_10k_pair_status(
        companyfacts=facts,submissions=sub,tag="Revenues",
        asof="2026-11-10")=="CONFLICTING_OR_MULTIPLE_10K_SOURCE_VINTAGES"


def test_same_fy_source_fact_period_conflict_not_hidden_by_same_usd_amount():
    facts,sub=fqa.sample()
    gaap=facts["facts"]["us-gaap"]
    gaap["Revenues"]={"units":{"USD":[dict(x)
        for x in gaap[m.quality.ANNUAL_TAGS["revenue"]]["units"]["USD"]]}}
    row=dict(gaap["Revenues"]["units"]["USD"][-1])
    row["start"]="2025-11-02"  # still annual length, but distinct FY start
    gaap["Revenues"]["units"]["USD"].append(row)
    assert m._alternative_original_10k_pair_status(
        companyfacts=facts,submissions=sub,tag="Revenues",
        asof="2026-11-10")=="CONFLICTING_OR_MULTIPLE_10K_SOURCE_VINTAGES"


def test_malformed_matching_original_10k_amount_is_rejected_not_imputed():
    facts,sub=fqa.sample()
    gaap=facts["facts"]["us-gaap"]
    gaap["Revenues"]={"units":{"USD":[dict(x)
        for x in gaap[m.quality.ANNUAL_TAGS["revenue"]]["units"]["USD"]]}}
    gaap["Revenues"]["units"]["USD"][-1]["val"]=True
    with pytest.raises(m.SourceHold,match="amount"):
        m._alternative_original_10k_pair_status(
            companyfacts=facts,submissions=sub,tag="Revenues",
            asof="2026-11-10")


def test_10k_pair_is_stale_at_later_asof_and_cannot_be_backfilled():
    facts,sub=fqa.sample()
    gaap=facts["facts"]["us-gaap"]
    gaap["Revenues"]=gaap[m.quality.ANNUAL_TAGS["revenue"]]
    assert m._alternative_original_10k_pair_status(
        companyfacts=facts,submissions=sub,tag="Revenues",
        asof="2028-11-10")=="LATEST_TWO_10K_FY_NOT_CONSECUTIVE_AND_FRESH"


def _joint_missing_revenue(*, with_capex=False):
    facts, sub = fqa.sample()
    concepts = facts["facts"]["us-gaap"]
    revenue = concepts.pop(m.quality.ANNUAL_TAGS["revenue"])
    concepts["Revenues"] = {"units":{"USD":[dict(x)
        for x in revenue["units"]["USD"]]}}
    missing = ("revenue",)
    if with_capex:
        capex = concepts.pop(m.quality.ANNUAL_TAGS["capital_expenditure"])
        concepts["PaymentsToAcquireProductiveAssets"] = {"units":{
            "USD":[dict(x) for x in capex["units"]["USD"]]}}
        missing = ("revenue","capital_expenditure")
    return facts, sub, missing


def test_joint_four_original_sec_inputs_two_exact_10ks_review_only_not_a_score():
    facts, sub, missing = _joint_missing_revenue(with_capex=True)
    assert m._joint_four_inputs_same_original_10k_years(
        companyfacts=facts,submissions=sub,missing=missing,
        asof="2026-11-10"
    )=="FOUR_SOURCE_INPUTS_SHARE_TWO_ORIGINAL_10KS_REVIEW_ONLY"


def test_joint_no_automatic_preferred_revenue_if_both_source_alternatives_valid():
    facts,sub,missing = _joint_missing_revenue()
    facts["facts"]["us-gaap"]["SalesRevenueNet"] = facts["facts"]["us-gaap"]["Revenues"]
    assert m._joint_four_inputs_same_original_10k_years(
        companyfacts=facts,submissions=sub,missing=missing,
        asof="2026-11-10"
    )=="MULTIPLE_ALTERNATIVE_TAG_OPTIONS_NO_ARBITRARY_PICK"


def test_missing_any_other_original_quality_input_blocks_joint_review():
    facts,sub,missing = _joint_missing_revenue()
    del facts["facts"]["us-gaap"][m.quality.ANNUAL_TAGS["operating_income"]]
    assert m._joint_four_inputs_same_original_10k_years(
        companyfacts=facts,submissions=sub,missing=("revenue","operating_income"),
        asof="2026-11-10"
    )=="MISSING_ANY_USD_SOURCE_TAG_FOR_ONE_OR_MORE_INPUTS"


def test_joint_annual_fiscal_start_must_be_identical_across_all_four_fields():
    facts,sub,missing = _joint_missing_revenue()
    original=facts["facts"]["us-gaap"][m.quality.ANNUAL_TAGS["operating_income"]]["units"]["USD"]
    original[1]["start"]="2025-11-02"  # still 330-380 days
    assert m._joint_four_inputs_same_original_10k_years(
        companyfacts=facts,submissions=sub,missing=missing,
        asof="2026-11-10"
    )=="FOUR_INPUTS_10K_ANNUAL_STARTS_NOT_ALIGNED"


def test_joint_recent_10k_comparative_in_later_accession_not_original_older():
    facts,sub,missing = _joint_missing_revenue()
    old=facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]
    old["accn"] = fqa.ACCESSIONS[-1]
    old["filed"] = fqa.FILINGS[-1]
    assert m._joint_four_inputs_same_original_10k_years(
        companyfacts=facts,submissions=sub,missing=missing,
        asof="2026-11-10"
    )=="FOUR_INPUTS_NOT_IN_SAME_TWO_ORIGINAL_10K_ACCESSIONS"


def test_joint_two_10k_original_facts_must_not_be_from_distinct_securities():
    facts,sub,missing = _joint_missing_revenue()
    facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"][-1]["accn"]="0000999999-26-000001"
    assert m._joint_four_inputs_same_original_10k_years(
        companyfacts=facts,submissions=sub,missing=missing,
        asof="2026-11-10"
    )=="FOUR_INPUTS_NOT_IN_SAME_TWO_ORIGINAL_10K_ACCESSIONS"


def test_joint_two_fiscal_years_only_after_public_filing_lag():
    facts,sub,missing = _joint_missing_revenue()
    assert m._joint_four_inputs_same_original_10k_years(
        companyfacts=facts,submissions=sub,missing=missing,
        asof="2026-11-05"
    )=="INSUFFICIENT_ORIGINAL_ELIGIBLE_10K_LEDGER_YEARS"


def test_joint_two_fiscal_years_stale_must_not_be_used_as_current():
    facts,sub,missing = _joint_missing_revenue()
    assert m._joint_four_inputs_same_original_10k_years(
        companyfacts=facts,submissions=sub,missing=missing,
        asof="2028-11-10"
    )=="LATEST_TWO_10K_YEARS_STALE_OR_NONCONSECUTIVE"


def test_joint_same_fiscal_year_two_original_filing_accessions_ambiguous():
    facts,sub,missing = _joint_missing_revenue()
    extra="0000320193-26-000099"
    new_10k={
        "accessionNumber":extra,"form":"10-K",
        "filingDate":"2026-11-04","reportDate":"2026-10-30",
        "acceptanceDateTime":"2026-11-04T19:00:00.000Z"}
    for k,v in sub["filings"]["recent"].items():
        v.append(new_10k[k])
    assert m._joint_four_inputs_same_original_10k_years(
        companyfacts=facts,submissions=sub,missing=missing,
        asof="2026-11-10"
    )=="MULTIPLE_ORIGINAL_10K_ACCESSIONS_SAME_FY_UNRESOLVED"


def test_joint_same_accession_conflicting_annual_usd_amount_never_picked():
    facts,sub,missing = _joint_missing_revenue()
    row=dict(facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"][-1])
    row["val"] += 1
    facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append(row)
    assert m._joint_four_inputs_same_original_10k_years(
        companyfacts=facts,submissions=sub,missing=missing,
        asof="2026-11-10"
    )=="CONFLICTING_ORIGINAL_10K_FACT_AMOUNT_OR_START"


def test_joint_matching_10k_bad_amount_is_source_hold():
    facts,sub,missing = _joint_missing_revenue()
    facts["facts"]["us-gaap"]["Revenues"]["units"]["USD"][-1]["val"]=float("nan")
    with pytest.raises(m.SourceHold,match="amount"):
        m._joint_four_inputs_same_original_10k_years(
            companyfacts=facts,submissions=sub,missing=missing,
            asof="2026-11-10")


def test_joint_sample_reconciles_all_missing_tag_issuers_with_no_new_scores():
    def loader(cik,kind):
        if cik==320193:
            return _apple_source(cik,kind)
        facts,sub,missing=_joint_missing_revenue(with_capex=True)
        (facts if kind=="companyfacts" else sub)["cik"]=51143
        return json.dumps(facts if kind=="companyfacts" else sub).encode()
    out=run(fetcher=loader)
    assert out["sample_outcome_counts"][
        "generic_two_fiscal_year_filing_lagged_score_available"]==1
    assert out["sample_outcome_counts"][
        "generic_filing_lagged_score_unavailable"]==1
    assert out["joint_four_input_same_two_original_10K_years_source_states_NOT_a_score"]=={
        "FOUR_SOURCE_INPUTS_SHARE_TWO_ORIGINAL_10KS_REVIEW_ONLY":1}
    assert out["joint_four_input_source_alignment_not_accounting_semantics_verified"] is True
    assert out["joint_four_input_source_alignment_never_promotes_original_P4A_score"] is True
    assert out["broker_reads"]==out["broker_orders"]==out["private_state_writes"]==0


def test_genuine_usd_tag_presence_does_not_override_filing_packet_eligibility():
    fact,sub=fqa.sample()
    names=m._missing_generic_concepts(fact)
    assert names==()
    sub["filings"]["recent"]["form"]=["8-K","8-K"]
    reason, _=m._unscored_source_reason(
        companyfacts=fact,submissions=sub,
        model_state="MISSING_ELIGIBLE_FULL_YEAR_FILINGS")
    assert reason=="ZERO_10K_IN_RECENT_SUBMISSIONS_LEDGER"


@pytest.mark.parametrize("sic,expected", [
    (None, "CURRENT_SEC_SIC_UNAVAILABLE_NO_SECTOR_INFERENCE"),
    ("", "CURRENT_SEC_SIC_UNAVAILABLE_NO_SECTOR_INFERENCE"),
    ("6021", "CURRENT_SIC_FINANCE_INSURANCE_REAL_ESTATE_REVIEW"),
    (6021, "CURRENT_SIC_FINANCE_INSURANCE_REAL_ESTATE_REVIEW"),
    ("6798", "CURRENT_SIC_FINANCE_INSURANCE_REAL_ESTATE_REVIEW"),
    ("4911", "CURRENT_SIC_UTILITIES_REVIEW"),
    ("1311", "CURRENT_SIC_MINING_EXTRACTION_REVIEW"),
    ("3571", "CURRENT_SIC_OTHER_CANNOT_ESTABLISH_BUSINESS_MODEL"),
    ("0000", "CURRENT_SEC_SIC_UNCLASSIFIED_NO_SECTOR_INFERENCE"),
])
def test_original_SEC_sic_is_coarse_current_issuer_metadata_only(sic,expected):
    facts,sub=fqa.sample()
    if sic is not None:
        sub["sic"]=sic
    taxonomy, band=m._issuer_original_source_accounting_context(
        companyfacts=facts,submissions=sub)
    assert taxonomy=="CURRENT_SEC_US_GAAP_NAMESPACE_SOURCE_ONLY"
    assert band==expected


@pytest.mark.parametrize("change,expected", [
    (lambda facts: facts.update({"facts":{"ifrs-full":{}}}),
     "CURRENT_SEC_IFRS_NAMESPACE_SOURCE_ONLY"),
    (lambda facts: facts["facts"].update({"ifrs-full":{}}),
     "CURRENT_SEC_BOTH_US_GAAP_AND_IFRS_NAMESPACES_SOURCE_ONLY"),
    (lambda facts: facts.update({"facts":{"dei":{}}}),
     "CURRENT_SEC_NO_US_GAAP_OR_IFRS_NAMESPACE"),
])
def test_original_companyfacts_US_GAAP_vs_IFRS_namespace_is_not_annual_eligibility(change,expected):
    facts,sub=fqa.sample()
    change(facts)
    taxonomy,band=m._issuer_original_source_accounting_context(
        companyfacts=facts,submissions=sub)
    assert taxonomy==expected
    assert band=="CURRENT_SEC_SIC_UNAVAILABLE_NO_SECTOR_INFERENCE"


@pytest.mark.parametrize("sic", [True, 1.5, {}, ["6021"], "NOT_A_SIC", "-100", "٦٠٢١"])
def test_malformed_SIC_metadata_never_guesses_business_sector(sic):
    facts,sub=fqa.sample()
    sub["sic"]=sic
    with pytest.raises(m.SourceHold,match="SIC"):
        m._issuer_original_source_accounting_context(
            companyfacts=facts,submissions=sub)


@pytest.mark.parametrize("bad_facts", [
    [], {"us-gaap":[]}, {"us-gaap":{},"ifrs-full":8}
])
def test_malformed_SEC_accounting_namespace_not_treated_as_valid_US_GAAP(bad_facts):
    facts,sub=fqa.sample()
    facts["facts"]=bad_facts
    with pytest.raises(m.SourceHold,match="namespace"):
        m._issuer_original_source_accounting_context(
            companyfacts=facts,submissions=sub)


def test_sample_source_coverage_strict_and_missing_stay_in_same_predeclared_denominator():
    def loader(cik,kind):
        facts,sub=fqa.sample()
        if cik==51143:
            facts["cik"]=51143
            sub["cik"]=51143
            sub["sic"]="6021"
            # A bank can have a US-GAAP namespace yet lack generic
            # industrial accounting concepts. Do not set score=0.
            facts["facts"]={"us-gaap":{}}
        else:
            sub["sic"]="3571"
        return json.dumps(facts if kind=="companyfacts" else sub).encode()
    out=run(fetcher=loader)
    assert out["sample_outcome_counts"][
        "generic_two_fiscal_year_filing_lagged_score_available"]==1
    assert out["sample_outcome_counts"][
        "generic_filing_lagged_score_unavailable"]==1
    assert out["original_current_SEC_taxonomy_namespace_by_P4A_outcome_NOT_an_accounting_model"]=={
        "ORIGINAL_GENERIC_SCORE_AVAILABLE":{
            "CURRENT_SEC_US_GAAP_NAMESPACE_SOURCE_ONLY":1},
        "ORIGINAL_GENERIC_SCORE_UNAVAILABLE":{
            "CURRENT_SEC_US_GAAP_NAMESPACE_SOURCE_ONLY":1}}
    assert out["original_current_SEC_SIC_coarse_band_by_P4A_outcome_NOT_an_industry_exposure"]=={
        "ORIGINAL_GENERIC_SCORE_AVAILABLE":{
            "CURRENT_SIC_OTHER_CANNOT_ESTABLISH_BUSINESS_MODEL":1},
        "ORIGINAL_GENERIC_SCORE_UNAVAILABLE":{
            "CURRENT_SIC_FINANCE_INSURANCE_REAL_ESTATE_REVIEW":1}}
    assert out["sample_size"]==2
    assert out["broker_orders"]==0
    assert "6021" not in json.dumps(out)


def test_original_IFRS_only_case_stays_unscored_or_strict_not_US_GAAP_imputed():
    def loader(cik,kind):
        facts,sub=fqa.sample()
        if cik==51143:
            facts["cik"]=51143
            sub["cik"]=51143
            facts["facts"]={"ifrs-full":{"Revenue":{}}}
            sub["sic"]="6798"
        return json.dumps(facts if kind=="companyfacts" else sub).encode()
    out=run(fetcher=loader)
    assert out["sample_size"]==2
    ctx=out["original_current_SEC_taxonomy_namespace_by_P4A_outcome_NOT_an_accounting_model"]
    # P4A's strict US-GAAP contract cannot score IFRS-only issuers;
    # the current source context flags them WITHOUT inferring domicile.
    assert ctx["STRICT_ORIGINAL_SOURCE_REJECTED"]=={
        "CURRENT_SEC_IFRS_NAMESPACE_SOURCE_ONLY":1}
    assert out["sample_outcome_counts"]["generic_two_fiscal_year_filing_lagged_score_available"]==1
    assert out["sample_outcome_counts"][
        "SEC_facts_incompatible_with_generic_industrial_quality_contract"]==1
    assert out["live_authorized"] is False
    assert out["point_in_time_historical_universe_authenticated"] is False


@pytest.mark.parametrize("sic,expected", [
    ("6021","SEC_SIC_BANK_LENDING_CREDIT_AND_FINANCE_REVIEW_ONLY"),
    ("6141","SEC_SIC_BANK_LENDING_CREDIT_AND_FINANCE_REVIEW_ONLY"),
    ("6211","SEC_SIC_BROKER_DEALER_EXCHANGE_ADVICE_REVIEW_ONLY"),
    ("6311","SEC_SIC_INSURANCE_UNDERWRITING_SERVICES_REVIEW_ONLY"),
    ("6411","SEC_SIC_INSURANCE_UNDERWRITING_SERVICES_REVIEW_ONLY"),
    ("6512","SEC_SIC_REAL_ESTATE_OPERATORS_SERVICES_REVIEW_ONLY"),
    ("6770","SEC_SIC_BLANK_CHECK_COMPANY_6770_NOT_STOCK_APPROVAL"),
    ("6798","SEC_SIC_REIT_6798_REVIEW_ONLY"),
    ("6799","SEC_SIC_OTHER_HOLDING_INVESTMENT_STRUCTURES_REVIEW_ONLY"),
    ("6021","SEC_SIC_BANK_LENDING_CREDIT_AND_FINANCE_REVIEW_ONLY"),
    ("3571","SEC_SIC_OUTSIDE_6000_TO_6799"),
    (None,"SIC_MISSING_NOT_FINANCE_CONFIRMED"),
])
def test_SEC_specific_finance_subtype_is_not_common_share_or_quality_grade(sic,expected):
    subs={} if sic is None else {"sic":sic}
    assert m._current_finance_subtype_from_SEC_sic(subs)==expected


@pytest.mark.parametrize("bad", [True, 6.3, {}, ["6798"], "6798X", "٦٧٩٨"])
def test_finance_SIC_metadata_invalid_never_infers_REIT_or_bank(bad):
    with pytest.raises(m.SourceHold,match="SIC"):
        m._current_finance_subtype_from_SEC_sic({"sic":bad})


def _finance_sample():
    facts,sub=fqa.sample()
    gaap=facts["facts"]["us-gaap"]
    for tag,values in (("Assets",(500_000_000,520_000_000)),
                       ("StockholdersEquity",(100_000_000,110_000_000))):
        gaap[tag]={"units":{"USD":[{
            "accn":fqa.ACCESSIONS[i], "form":"10-K",
            "filed":fqa.FILINGS[i], "end":fqa.DATES[i],
            "val":values[i]
        } for i in range(2)]}}
    gaap["NetIncomeLoss"]={"units":{"USD":[{
        "accn":fqa.ACCESSIONS[i], "form":"10-K",
        "filed":fqa.FILINGS[i], "start":fqa.FY_START[i],
        "end":fqa.DATES[i], "val":v
    } for i,v in enumerate((8_000_000,12_000_000))]}}
    sub["sic"]="6021"
    return facts,sub


def _core_status(facts=None,sub=None,asof="2026-11-10"):
    if facts is None or sub is None:
        facts,sub=_finance_sample()
    return m._finance_core_original_two_10k_source_readiness(
        companyfacts=facts,submissions=sub,asof=asof)


def test_finance_core_own_10k_balance_sheet_instant_plus_income_annual_research_only():
    assert _core_status()==(
        "ASSETS_EQUITY_NETINCOME_TWO_OWN_10KS_SOURCE_ONLY",())


def test_finance_missing_core_tags_never_imputed():
    facts,sub=_finance_sample()
    del facts["facts"]["us-gaap"]["StockholdersEquity"]
    assert _core_status(facts,sub)==(
        "MISSING_EXACT_FINANCE_CORE_CONCEPT_USD_TAG",("equity",))


def test_finance_independent_US_GAAP_namespace_cannot_be_inferred_from_IFRS():
    facts,sub=_finance_sample()
    facts["facts"]={"ifrs-full":{}}
    assert _core_status(facts,sub)==("NO_US_GAAP_SOURCE_FOR_FINANCE_CORE",())


def test_finance_core_annual_income_cannot_be_instant_source():
    facts,sub=_finance_sample()
    del facts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]["start"]
    assert _core_status(facts,sub)==(
        "FINANCE_CORE_FACTS_NOT_IN_SAME_TWO_OWN_10KS",())


def test_finance_balance_sheet_cannot_be_annual_duration_source():
    facts,sub=_finance_sample()
    facts["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]["start"]=fqa.FY_START[0]
    assert _core_status(facts,sub)==(
        "FINANCE_CORE_FACTS_NOT_IN_SAME_TWO_OWN_10KS",())


def test_finance_core_later_comparative_row_not_original_older_10k():
    facts,sub=_finance_sample()
    old=facts["facts"]["us-gaap"]["Assets"]["units"]["USD"][0]
    old["accn"]=fqa.ACCESSIONS[1]
    old["filed"]=fqa.FILINGS[1]
    assert _core_status(facts,sub)==(
        "FINANCE_CORE_FACTS_NOT_IN_SAME_TWO_OWN_10KS",())


def test_finance_core_two_weekday_lag_prevents_future_fact_use():
    assert _core_status(asof="2026-11-05")==(
        "FEWER_THAN_TWO_ORIGINAL_FINANCE_10KS",())


def test_finance_core_stale_source_not_two_current_annual_years():
    assert _core_status(asof="2028-11-10")==(
        "NONCONSECUTIVE_OR_STALE_FINANCE_10KS",())


def test_finance_10k_amendment_same_FY_not_arbitrarily_chosen():
    facts,sub=_finance_sample()
    extra={"accessionNumber":"0000320193-26-000099", "form":"10-K",
           "filingDate":"2026-11-04","reportDate":"2026-10-30",
           "acceptanceDateTime":"2026-11-04T19:00:00.000Z"}
    for k,arr in sub["filings"]["recent"].items():
        arr.append(extra[k])
    assert _core_status(facts,sub)==(
        "DUPLICATE_OR_AMENDED_FINANCE_FISCAL_YEARS",())


def test_finance_source_instant_fact_conflict_fails_as_unresolved():
    facts,sub=_finance_sample()
    r=dict(facts["facts"]["us-gaap"]["Assets"]["units"]["USD"][-1])
    r["val"]+=1
    facts["facts"]["us-gaap"]["Assets"]["units"]["USD"].append(r)
    assert _core_status(facts,sub)==(
        "CONFLICTING_FINANCE_SOURCE_FACT_VINTAGES",())


def test_finance_bad_numeric_fact_is_HOLD_not_bank_grade():
    facts,sub=_finance_sample()
    facts["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"][0]["val"]=True
    with pytest.raises(m.SourceHold,match="amount"):
        _core_status(facts,sub)


def test_finance_source_coverage_counts_are_separate_from_original_P4A_score():
    def loader(cik,kind):
        if cik==320193:
            return _apple_source(cik,kind)
        facts,sub=_finance_sample()
        facts["cik"]=sub["cik"]=51143
        del facts["facts"]["us-gaap"][m.quality.ANNUAL_TAGS["revenue"]]
        return json.dumps(facts if kind=="companyfacts" else sub).encode()
    out=run(fetcher=loader)
    assert out["current_SEC_finance_SIC_subtypes_NOT_verified_security_industries"]=={
        "SEC_SIC_BANK_LENDING_CREDIT_AND_FINANCE_REVIEW_ONLY":1}
    assert out["current_SEC_finance_assets_equity_netincome_two_own_10K_source_status_NOT_a_score"]=={
        "ASSETS_EQUITY_NETINCOME_TWO_OWN_10KS_SOURCE_ONLY":1}
    assert out["current_SEC_finance_missing_exact_core_tag_USD_issuer_counts"]=={}
    assert out["sample_outcome_counts"]["generic_two_fiscal_year_filing_lagged_score_available"]==1
    assert out["sample_outcome_counts"]["generic_filing_lagged_score_unavailable"]==1
    assert out["finance_balance_sheet_net_income_sources_not_bank_capital_credit_REIT_FFO_metrics"] is True
    assert out["live_authorized"] is False
    assert out["broker_reads"]==out["broker_orders"]==out["private_state_writes"]==0
    assert "6021" not in json.dumps(out)


def _bank_credit_source_sample():
    facts, sub = _finance_sample()
    for j, (label, tag) in enumerate(m.BANK_CREDIT_OPTIONAL_INSTANT_TAGS.items()):
        facts["facts"]["us-gaap"][tag] = {"units": {"USD": [
            {"accn": fqa.ACCESSIONS[i], "form": "10-K",
             "filed": fqa.FILINGS[i], "end": fqa.DATES[i],
             "val": 100_000_000 + i * 5_000_000 + j * 1000}
            for i in range(2)]}}
    return facts, sub


def _bank_credit_status(facts=None, sub=None, asof="2026-11-10"):
    if facts is None or sub is None:
        facts, sub = _bank_credit_source_sample()
    return m._bank_credit_original_two_10k_source_readiness(
        companyfacts=facts, submissions=sub, asof=asof)


def test_bank_credit_current_sic_is_source_coverage_only_not_capital_quality():
    assert _bank_credit_status() == (
        "BANK_CREDIT_THREE_INSTANT_TAGS_TWO_OWN_10KS_SOURCE_ONLY", ())


def test_bank_credit_optional_absence_never_implies_nonbank_or_poor_bank():
    facts, sub = _bank_credit_source_sample()
    del facts["facts"]["us-gaap"]["DepositsDomestic"]
    assert _bank_credit_status(facts, sub) == (
        "MISSING_BANK_CREDIT_EXACT_OPTIONAL_USD_TAG", ("domestic_deposits",))


def test_bank_credit_original_10k_mismatch_and_comparative_rows_are_not_backfilled():
    facts, sub = _bank_credit_source_sample()
    r = facts["facts"]["us-gaap"]["DepositsDomestic"]["units"]["USD"][0]
    r["accn"] = fqa.ACCESSIONS[1]
    r["filed"] = fqa.FILINGS[1]
    assert _bank_credit_status(facts, sub) == (
        "BANK_CREDIT_TAGS_NOT_IN_SAME_TWO_OWN_10KS", ())


def test_bank_credit_annual_duration_is_not_valid_balance_sheet_instant():
    facts, sub = _bank_credit_source_sample()
    facts["facts"]["us-gaap"]["DepositsDomestic"]["units"]["USD"][0]["start"] = fqa.FY_START[0]
    assert _bank_credit_status(facts, sub) == (
        "BANK_CREDIT_TAGS_NOT_IN_SAME_TWO_OWN_10KS", ())


def test_bank_credit_conflicting_original_instant_amount_does_not_choose_winner():
    facts, sub = _bank_credit_source_sample()
    rows = facts["facts"]["us-gaap"]["FinancingReceivableAllowanceForCreditLosses"]["units"]["USD"]
    conflict = dict(rows[1])
    conflict["val"] += 1
    rows.append(conflict)
    assert _bank_credit_status(facts, sub) == (
        "CONFLICTING_BANK_CREDIT_ORIGINAL_FACT_VINTAGES", ())


def test_bank_credit_future_or_stale_original_filings_are_not_evidence():
    assert _bank_credit_status(asof="2026-11-05") == (
        "BANK_CREDIT_FINANCE_CORE_SOURCE_NOT_READY", ())
    assert _bank_credit_status(asof="2028-11-10") == (
        "BANK_CREDIT_FINANCE_CORE_SOURCE_NOT_READY", ())


def test_bank_credit_bad_numeric_fact_is_source_hold_not_grade():
    facts, sub = _bank_credit_source_sample()
    facts["facts"]["us-gaap"]["DepositsDomestic"]["units"]["USD"][0]["val"] = True
    with pytest.raises(m.SourceHold, match="amount"):
        _bank_credit_status(facts, sub)


def test_bank_credit_marginal_counts_no_broker_or_issuer_disclosure():
    def loader(cik, kind):
        if cik == 320193:
            return _apple_source(cik, kind)
        facts, sub = _bank_credit_source_sample()
        facts["cik"] = sub["cik"] = 51143
        del facts["facts"]["us-gaap"][m.quality.ANNUAL_TAGS["revenue"]]
        return json.dumps(facts if kind == "companyfacts" else sub).encode()
    result = run(fetcher=loader)
    assert result["current_SEC_bank_credit_exact_optional_instant_three_tag_two_own_10K_source_status_NOT_a_score"] == {
        "BANK_CREDIT_THREE_INSTANT_TAGS_TWO_OWN_10KS_SOURCE_ONLY": 1}
    assert result["current_SEC_bank_credit_missing_exact_optional_USD_tag_issuer_counts"] == {}
    assert result["bank_credit_optional_source_not_deposit_taking_or_credit_quality_proof"] is True
    assert result["broker_reads"] == result["broker_orders"] == result["private_state_writes"] == 0
    assert "6021" not in json.dumps(result)


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
