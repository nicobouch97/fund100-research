"""Adversarial no-network V9 Nasdaq + current SEC exchange association tests."""
from datetime import datetime, timezone
import json
import pytest

import fund100_v9_sec_current_listing_association_v1_0 as m

NOW = datetime(2026,11,10,18,0,tzinfo=timezone.utc)
FOOTER = "File Creation Time: 1110202610:00"
NHEAD = "Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares"
OHEAD = "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol"
NR = (
    "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N",
    "MSFT|Microsoft Corporation|Q|N|N|100|N|N",
    "ABC|Mismatch issuer example|G|N|N|100|N|N",
    "SPY1|Index Fund ETF|Q|N|N|100|Y|N",
)
OR = (
    "IBM|International Business Machines Common Stock|N|IBM|N|100|N|IBM",
    "BRK.B|Berkshire Class B Common Stock|N|BRK.B|N|100|N|BRK/B",
    "BAC$D|Preferred Security|N|BACpD|N|100|N|BAC-D",
    "UNK|Unknown market sample|H|UNK|N|100|N|UNK",
)
SR = [
    [320193,"Apple Inc.","AAPL","Nasdaq"],
    [789019,"Microsoft Corporation","MSFT","Nasdaq"],
    [333,"Mismatch","ABC","NYSE"],
    [51143,"International Business Machines","IBM","NYSE"],
    [1067983,"Berkshire Hathaway","BRK-B","NYSE"],
    [8888,"Unmapped Preferred","BAC-D","NYSE"],
]


def directories(nasdaq_rows=NR, other_rows=OR):
    return {
        "nasdaqlisted.txt": (NHEAD+"\n"+"\n".join(nasdaq_rows)+"\n"+FOOTER+"|||||||\n").encode(),
        "otherlisted.txt": (OHEAD+"\n"+"\n".join(other_rows)+"\n"+FOOTER+"|||||||\n").encode(),
    }


def sec_json(rows=SR):
    return json.dumps({"fields":["cik","name","ticker","exchange"],"data":rows}).encode()


def inspect(*,dirs=None, sec_rows=None):
    return m.inspect(
        nasdaq_raw=directories() if dirs is None else dirs,
        sec_raw=sec_json() if sec_rows is None else sec_json(sec_rows),
        observed=NOW,min_directory_rows=1,min_sec_rows=1)


def test_exact_current_ticker_and_exchange_links_only():
    r=inspect()
    assert r["stage"]=="PROSPECTIVE_CURRENT_ISSUER_ASSOCIATION_COVERAGE_NOT_STOCK_UNIVERSE"
    assert r["listing_candidates_reviewed"]==6
    assert r["association_reason_counts"]=={
        "SEC_exchange_not_equal_to_original_listing_exchange":1,
        "exact_current_ticker_and_exchange_associations":3,
        "no_exact_SEC_ticker_association":2,
    }
    assert r["all_current_non_etf_listings_source_name_cue_counts"]=={
        "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY":1,
        "EXPLICIT_COMMON_OR_ORDINARY_WORDING_REVIEW_ONLY":3,
        "UNRESOLVED_SECURITY_NAME_NO_CLASS_INFERENCE":2,
    }
    assert r["exact_SEC_association_source_name_cue_counts"]=={
        "EXPLICIT_COMMON_OR_ORDINARY_WORDING_REVIEW_ONLY":2,
        "UNRESOLVED_SECURITY_NAME_NO_CLASS_INFERENCE":1,
    }
    assert r["distinct_current_SEC_CIKs_with_explicit_common_wording_only"]==2
    assert r["source_name_cues_are_verified_security_classes"] is False
    assert r["source_name_cues_are_approval_to_trade"] is False
    assert r["issuer_name_cue_is_US_domicile_proof"] is False
    assert r["distinct_SEC_filer_CIKs_with_exact_current_ticker_exchange_association"]==3
    assert r["nasdaq_discovery_original_report"]["unknown_code_rows_quarantined_total"]==1
    assert r["current_SEC_association_is_a_qualified_share_class"] is False
    assert r["SEC_ticker_map_is_historical_asof_source"] is False
    assert r["historical_delistings_and_corporate_actions_covered"] is False
    assert r["US_common_share_and_domicile_verified"] is False
    assert r["live_authorized"] is False
    assert r["broker_reads"] == r["broker_orders"] == r["private_state_writes"] == 0
    public=json.dumps(r)
    for name in ("Apple Inc.", "AAPL", "Microsoft Corporation", "MSFT",
                 "Berkshire Hathaway", "BRK.B", "320193", "51143", "1067983"):
        assert name not in public
    assert len(r["SEC_original_bytes_sha256"])==64


@pytest.mark.parametrize("label,expected", [
    ("Example Inc. - Common Stock",
     "EXPLICIT_COMMON_OR_ORDINARY_WORDING_REVIEW_ONLY"),
    ("Example Holdings - Class A Ordinary Shares",
     "EXPLICIT_COMMON_OR_ORDINARY_WORDING_REVIEW_ONLY"),
    ("United Companies - COMMON SHARES",
     "EXPLICIT_COMMON_OR_ORDINARY_WORDING_REVIEW_ONLY"),
    ("Example plc", "UNRESOLVED_SECURITY_NAME_NO_CLASS_INFERENCE"),
    ("Example Inc. Class A", "UNRESOLVED_SECURITY_NAME_NO_CLASS_INFERENCE"),
    ("Example Trust", "UNRESOLVED_SECURITY_NAME_NO_CLASS_INFERENCE"),
    ("Examples Preferred Series A",
     "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY"),
    ("Examples - Warrants to purchase Common Stock",
     "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY"),
    ("Example - Ordinary Shares and Warrants",
     "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY"),
    ("Examples - Common Stock Units",
     "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY"),
    ("Examples American Depositary Shares",
     "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY"),
    ("Examples Depository Receipt",
     "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY"),
    ("Examples Convertible Notes",
     "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY"),
    ("Examples ETF",
     "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY"),
])
def test_name_review_cues_are_not_security_master(label,expected):
    assert m.security_name_text_cue(label)==expected


def test_conflicting_common_text_and_instrument_words_never_count_as_common():
    # Classifier must never make "warrants to buy common" a common-share cue.
    bad=directories(nasdaq_rows=(
        "AAPL|Apple Common Stock Warrants|Q|N|N|100|N|N",
        "MSFT|Microsoft Ordinary Shares|Q|N|N|100|N|N",
        "ABC|Mismatch issuer example|G|N|N|100|N|N",
        "SPY1|Index Fund ETF|Q|N|N|100|Y|N",
    ))
    result=inspect(dirs=bad)
    assert result["exact_SEC_association_source_name_cue_counts"]=={
        "EXPLICIT_ALTERNATIVE_INSTRUMENT_WORDING_REVIEW_ONLY":1,
        "EXPLICIT_COMMON_OR_ORDINARY_WORDING_REVIEW_ONLY":2,
    }
    assert result["distinct_current_SEC_CIKs_with_explicit_common_wording_only"]==2
    assert result["US_common_share_and_domicile_verified"] is False
    assert result["live_authorized"] is False


def test_name_cue_does_not_promote_unmatched_and_ambiguous_issuers():
    source=SR+[[999999,"Different issuer","AAPL","Nasdaq"]]
    result=inspect(sec_rows=source)
    assert result["all_current_non_etf_listings_source_name_cue_counts"][
        "EXPLICIT_COMMON_OR_ORDINARY_WORDING_REVIEW_ONLY"]==3
    assert result["exact_SEC_association_source_name_cue_counts"]=={
        "EXPLICIT_COMMON_OR_ORDINARY_WORDING_REVIEW_ONLY":1,
        "UNRESOLVED_SECURITY_NAME_NO_CLASS_INFERENCE":1,
    }
    assert result["distinct_current_SEC_CIKs_with_explicit_common_wording_only"]==1


def test_blank_name_does_not_gain_security_class():
    with pytest.raises(m.AssociationStop):
        m.security_name_text_cue("")
    with pytest.raises(m.AssociationStop):
        m.security_name_text_cue(None)


def test_sec_duplicate_ticker_cik_ambiguity_does_not_choose_convenient_issuer():
    r=inspect(sec_rows=SR+[[999999,"Different entity","AAPL","Nasdaq"]])
    assert r["association_reason_counts"]["ambiguous_SEC_CIK_or_exchange_associations"]==1
    assert r["association_reason_counts"]["exact_current_ticker_and_exchange_associations"]==2
    assert r["distinct_SEC_filer_CIKs_with_exact_current_ticker_exchange_association"]==2


def test_real_sec_null_exchange_is_unqualified_not_inferred_or_hard_fail():
    source=SR+[[320193,"Apple Inc.","AAPL",None],
               [2345678,"Unassigned US issuer","UNASSIGNED",None]]
    r=inspect(sec_rows=source)
    assert r["SEC_source_unqualified_rows"]=={"null_exchange_unqualified":2}
    # Exact sourced AAPL/Nasdaq still qualifies on its own, but the null
    # observation cannot supply additional CIKs or exchange eligibility.
    assert r["association_reason_counts"]["exact_current_ticker_and_exchange_associations"]==3
    assert r["distinct_SEC_filer_CIKs_with_exact_current_ticker_exchange_association"]==3
    assert r["current_SEC_association_is_a_qualified_share_class"] is False
    assert r["live_authorized"] is False
    assert "Unassigned US issuer" not in json.dumps(r)


def test_null_exchange_by_itself_never_qualifies_broker_eligible_identity():
    source=[row for row in SR if row[2]!="AAPL"]+[
        [320193,"Apple Inc.","AAPL",None]]
    r=inspect(sec_rows=source)
    assert r["association_reason_counts"]["no_exact_SEC_ticker_association"]==3
    assert r["association_reason_counts"]["exact_current_ticker_and_exchange_associations"]==2
    assert r["SEC_source_unqualified_rows"]=={"null_exchange_unqualified":1}


def test_sec_duplicate_identical_association_not_extra_issuer():
    r=inspect(sec_rows=SR+[SR[0]])
    assert r["association_reason_counts"]["exact_current_ticker_and_exchange_associations"]==3


def test_cross_directory_duplicate_ticker_quarantined_in_both_sources():
    raw=directories(other_rows=OR+(
        "AAPL|Same root on another venue|N|AAPL|N|100|N|AAPL",))
    r=inspect(dirs=raw)
    assert r["association_reason_counts"]["same_ticker_in_multiple_listing_records"]==2
    assert r["association_reason_counts"]["exact_current_ticker_and_exchange_associations"]==2


@pytest.mark.parametrize("modifier", [
    lambda x: x.pop("fields"),
    lambda x: x.update({"fields":["name","cik","ticker","exchange"]}),
    lambda x: x.update({"fields":["cik","name","ticker","exchange","name"]}),
    lambda x: x.update({"data":{}}),
    lambda x: x.update({"data":[["AAPL","Nasdaq"]]}),
    lambda x: x.update({"data":[[True,"False","AAPL","Nasdaq"]]}),
    lambda x: x.update({"data":[[320193,"","AAPL","Nasdaq"]]}),
    lambda x: x.update({"data":[[320193,"Apple Inc.",123,"Nasdaq"]]}),
    lambda x: x.update({"data":[[320193,"Apple Inc.","AAPL",17]]}),
    lambda x: x.update({"data":[[320193,"Apple Inc.","AAPL",False]]}),
])
def test_malformed_sec_map_stops_entire_join(modifier):
    raw={"fields":["cik","name","ticker","exchange"],"data":SR[:]}
    modifier(raw)
    with pytest.raises(m.AssociationStop):
        m.inspect(nasdaq_raw=directories(),sec_raw=json.dumps(raw).encode(),
                  observed=NOW,min_directory_rows=1,min_sec_rows=1)


def test_missing_noncurrent_or_garbage_original_nasdaq_stops():
    for mutate in (
        lambda s:s.pop("otherlisted.txt"),
        lambda s:s.update({"otherlisted.txt":b"x"}),
        lambda s:s.update({"nasdaqlisted.txt":s["nasdaqlisted.txt"].replace(
            b"MSFT|",b"AAPL|")}),
    ):
        s=directories()
        mutate(s)
        with pytest.raises((m.AssociationStop,m.listing.ListingsStop)):
            inspect(dirs=s)


def test_missing_and_incomplete_sec_breadth_fail_closed():
    with pytest.raises(m.AssociationStop):
        m.inspect(nasdaq_raw=directories(), sec_raw=b"", observed=NOW,
                  min_directory_rows=1,min_sec_rows=1)
    with pytest.raises(m.AssociationStop):
        m.inspect(nasdaq_raw=directories(), sec_raw=sec_json(),
                  observed=NOW, min_directory_rows=1, min_sec_rows=1000)


def test_uncanonical_SEC_ticker_never_guessed_to_match_listing():
    bad=SR+[[3456,"Another share","BRK/B","NYSE"]]
    r=inspect(sec_rows=bad)
    assert r["association_reason_counts"]["no_exact_SEC_ticker_association"]==2
    assert r["SEC_source_unqualified_rows"]=={"unrecognised_ticker_format":1}


def test_no_broker_or_late_filing_research_trading_claim():
    from pathlib import Path
    src=Path(m.__file__).read_text()
    assert "alpaca" not in src.lower()
    assert "submit_order" not in src
    assert m.NO_BROKER_READS==m.NO_BROKER_ORDERS==m.NO_PRIVATE_STATE_WRITES==0
    assert m.LIVE_AUTHORIZED is False


def test_current_issuer_one_symbol_is_only_denominator_research_not_security_class():
    result=inspect()
    assert result["SEC_CIK_to_current_symbol_denominator_source_status_counts_NOT_security_class"] == {
        "SINGLE_MATCH_COMMON_TEXT_ONLY_UNVERIFIED_SHARE_CLASS": 2,
        "SINGLE_MATCH_NO_EXPLICIT_CLASS_TEXT_QUARANTINE": 1,
    }
    for field in (
        "SEC_CIK_to_one_matched_symbol_proves_exact_share_class",
        "SEC_issuer_level_share_count_proves_same_traded_class_denominator",
        "original_asof_price_and_class_specific_shares_verified",
        "current_ticker_link_is_historical_or_delisting_coverage",
        "current_class_source_status_is_stock_valuation_or_buy_signal",
    ):
        assert result[field] is False
    assert result["broker_reads"] == result["broker_orders"] == 0
    for sensitive in ("Apple Inc.", "AAPL", "320193", "Microsoft Corporation", "MSFT"):
        assert sensitive not in json.dumps(result)


def test_additional_sec_class_without_listing_match_quarantines_entire_issuer_denominator():
    # Exactly matching AAPL remains an issuer association, but the extra
    # SEC share/symbol means no class-specific market cap can be assumed.
    result=inspect(sec_rows=SR + [[320193, "Apple other class", "AAPLX", "Nasdaq"]])
    assert result["association_reason_counts"]["exact_current_ticker_and_exchange_associations"] == 3
    assert result["SEC_CIK_to_current_symbol_denominator_source_status_counts_NOT_security_class"] == {
        "MULTIPLE_OR_UNRECONCILED_SEC_TICKER_VENUE_ASSOCIATIONS": 1,
        "SINGLE_MATCH_COMMON_TEXT_ONLY_UNVERIFIED_SHARE_CLASS": 1,
        "SINGLE_MATCH_NO_EXPLICIT_CLASS_TEXT_QUARANTINE": 1,
    }
    assert result["original_asof_price_and_class_specific_shares_verified"] is False
    assert "AAPLX" not in json.dumps(result)


def test_two_genuine_listed_symbols_linked_to_one_issuer_are_not_one_denominator():
    dirs=directories(nasdaq_rows=NR + (
        "AAPLX|Apple Inc. - Class B Common Stock|G|N|N|100|N|N",
    ))
    sec=SR + [[320193, "Apple Inc.", "AAPLX", "Nasdaq"]]
    result=inspect(dirs=dirs,sec_rows=sec)
    status=result["SEC_CIK_to_current_symbol_denominator_source_status_counts_NOT_security_class"]
    assert status["MULTIPLE_OR_UNRECONCILED_SEC_TICKER_VENUE_ASSOCIATIONS"] == 1
    assert sum(status.values()) == result["distinct_SEC_filer_CIKs_with_exact_current_ticker_exchange_association"]
    assert result["current_class_source_status_is_stock_valuation_or_buy_signal"] is False


def test_exact_noncommon_symbol_never_becomes_security_valuation_eligibility():
    dirs=directories(other_rows=OR + (
        "PREF|Example Preferred Shares|N|PREF|N|100|N|PREF",
    ))
    sec=SR + [[71111,"Example Group","PREF","NYSE"]]
    result=inspect(dirs=dirs,sec_rows=sec)
    statuses=result["SEC_CIK_to_current_symbol_denominator_source_status_counts_NOT_security_class"]
    assert statuses["SINGLE_MATCH_ALTERNATIVE_INSTRUMENT_TEXT_QUARANTINE"] == 1
    assert result["SEC_CIK_to_one_matched_symbol_proves_exact_share_class"] is False
    assert "71111" not in json.dumps(result)


@pytest.mark.parametrize("extra", [
    [320193, "Apple alt class with unknown venue", "AAPLX", None],
    [320193, "Apple alt class with noncanonical ticker", "AAPL/X", "Nasdaq"],
])
def test_quarantined_sec_rows_still_disqualify_one_share_class_denominator(extra):
    # Existing SEC matching filters correctly refuse null/unknown symbols,
    # but their original existence must remain issuer-multiplicity evidence.
    result=inspect(sec_rows=SR + [extra])
    assert result["association_reason_counts"]["exact_current_ticker_and_exchange_associations"] == 3
    assert result["SEC_CIK_to_current_symbol_denominator_source_status_counts_NOT_security_class"][
        "MULTIPLE_OR_UNRECONCILED_SEC_TICKER_VENUE_ASSOCIATIONS"] == 1
    assert result["original_asof_price_and_class_specific_shares_verified"] is False
    assert extra[2] not in json.dumps(result)
