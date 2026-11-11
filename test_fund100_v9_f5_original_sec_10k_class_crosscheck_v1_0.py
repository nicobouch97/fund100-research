"""Adversarial, no-network original 10-K source identity and 12(b) tests."""
from datetime import datetime, timezone
import json
import pytest

import fund100_v9_f5_original_sec_10k_class_crosscheck_v1_0 as m


ASOF=datetime(2026,11,11,11,30,tzinfo=timezone.utc)
SEC_CIK=320193
SEC_ACC="0001193125-26-000001"
SEC_PATH=f"edgar/data/{SEC_CIK}/{SEC_ACC}.txt"


def submissions(cik=SEC_CIK, *, form="10-K", end="2025-12-31",
                filed="2026-02-20", accession=SEC_ACC):
    return {"cik":cik,"filings":{"recent":{
        "accessionNumber":[accession],
        "form":[form],
        "reportDate":[end],
        "filingDate":[filed],
        "acceptanceDateTime":["2026-02-20T17:00:00.000Z"],
    }}}


def primary_markup(*, symbol="AAPL", exchange="Nasdaq Global Select Market",
                   security="Common Stock", extra=""):
    return (f"<html><body><h1>Securities registered pursuant to Section 12(b)"
            f" of the Act</h1><table><tr><th>Title of each class</th>"
            f"<th>Trading symbol</th><th>Exchange</th></tr>"
            f"<tr><td>{security}</td><td>{symbol}</td><td>{exchange}</td></tr>"
            f"{extra}</table><p>Securities registered pursuant to Section 12(g)"
            f" of the Act: None</p></body></html>").encode()




def test_authentic_sec_submissions_text_cik_matches_original_issuer_exactly():
    # SEC's real submissions endpoint typically reports a zero-padded CIK
    # string, unlike companyfacts; the broad SEC original source decoder
    # already accepts exactly this representation.
    for value in (str(SEC_CIK),f"{SEC_CIK:010d}",SEC_CIK):
        payload=submissions(cik=value)
        v,status=m.candidate_filing(submissions=payload,cik=SEC_CIK,observed=ASOF)
        assert status=="SOURCE_ELIGIBLE"
        assert v[0]==SEC_PATH
    for value in ("0000999999","not-a-CIK","-320193","320193.0",
                  "",None,True,320193.0):
        with pytest.raises(m.CoverHold,match="CIK inconsistent"):
            m.candidate_filing(submissions=submissions(cik=value),
                               cik=SEC_CIK,observed=ASOF)

def test_original_10k_filing_selection_checks_own_cik_lag_and_year():
    v,state=m.candidate_filing(submissions=submissions(),cik=SEC_CIK,observed=ASOF)
    assert state=="SOURCE_ELIGIBLE"
    assert v==(SEC_PATH,SEC_ACC,"2026-02-20","2025-12-31")
    with pytest.raises(m.CoverHold):
        m.candidate_filing(submissions=submissions(cik=42),cik=SEC_CIK,observed=ASOF)
    for kw in (
        {"form":"10-K/A"},
        {"filed":"2027-02-20"},
        {"end":"2023-12-31","filed":"2024-02-20"},
    ):
        v,state=m.candidate_filing(
            submissions=submissions(**kw),cik=SEC_CIK,observed=ASOF)
        assert v is None
        assert state=="NO_RECENT_ASOF_ELIGIBLE_OWN_10K_HOLD"


def test_original_filing_same_fy_double_accession_refuses_favorable_selection():
    duplicate=submissions()
    for key in duplicate["filings"]["recent"]:
        duplicate["filings"]["recent"][key].append(
            duplicate["filings"]["recent"][key][0])
    duplicate["filings"]["recent"]["accessionNumber"][1]="0001193125-26-000002"
    v,state=m.candidate_filing(submissions=duplicate,cik=SEC_CIK,observed=ASOF)
    assert v is None
    assert state=="AMBIGUOUS_MULTIPLE_ORIGINAL_10K_FOR_FY_HOLD"


def test_original_12b_parser_used_for_exact_symbol_and_venue():
    import fund100_stock_historical_sec_listing_p4u_v1_0 as p4u
    parsed=p4u.inspect_primary_10k(primary_markup())
    assert m.classify_10k(parsed=parsed,ticker="AAPL",venue="Nasdaq")==(
        "EXACT_OWN_10K_12B_SYMBOL_COMMON_VENUE_REVIEW_ONLY_NOT_FIGI_PROVEN")
    assert m.classify_10k(parsed=parsed,ticker="MSFT",venue="Nasdaq")==(
        "ORIGINAL_10K_TICKER_NOT_EQUAL_CURRENT_MATCH_HOLD")
    assert m.classify_10k(parsed=parsed,ticker="AAPL",venue="NYSE")==(
        "ORIGINAL_10K_VENUE_NOT_EQUAL_CURRENT_MATCH_HOLD")


@pytest.mark.parametrize("change,expected",[
    ({"symbol":"", "exchange":"Nasdaq"}, "NO_INDEPENDENT_10K_TICKER_SYMBOL_HOLD"),
    ({"security":"Preferred Stock"}, "NO_STRUCTURED_12B_PLAIN_COMMON_ROW_HOLD"),
    ({"security":"Warrants to purchase Common Stock"}, "NO_STRUCTURED_12B_PLAIN_COMMON_ROW_HOLD"),
    ({"exchange":"Cboe"}, "NO_STRUCTURED_12B_PLAIN_COMMON_ROW_HOLD"),
])
def test_no_12b_plain_common_evidence_is_not_legal_identity(change,expected):
    import fund100_stock_historical_sec_listing_p4u_v1_0 as p4u
    data={"symbol":"AAPL","exchange":"Nasdaq","security":"Common Stock"}
    data.update(change)
    parsed=p4u.inspect_primary_10k(primary_markup(**data))
    assert m.classify_10k(parsed=parsed,ticker="AAPL",venue="Nasdaq")==expected


def test_multiple_original_10k_common_classes_are_not_one_issuer_equity():
    import fund100_stock_historical_sec_listing_p4u_v1_0 as p4u
    other="<tr><td>Class B Common Stock</td><td>APLB</td><td>Nasdaq</td></tr>"
    parsed=p4u.inspect_primary_10k(primary_markup(extra=other))
    assert m.classify_10k(parsed=parsed,ticker="AAPL",venue="Nasdaq")==(
        "MULTIPLE_PLAIN_COMMON_12B_CLASSES_AMBIGUOUS_HOLD")


def test_strict_distinct_exchange_names():
    assert m.venue_matches("The New York Stock Exchange", "NYSE")
    assert not m.venue_matches("NYSE American", "NYSE")
    assert not m.venue_matches("NYSE Arca", "NYSE")
    assert m.venue_matches("NYSE American", "NYSE American")
    assert m.venue_matches("NYSE Arca", "NYSE Arca")
    assert not m.venue_matches("Nasdaq", "IEX")
    assert not m.venue_matches("Nasdaq", "Cboe")


def test_real_source_shape_aggregate_no_account_or_single_issuer_rows(monkeypatch):
    import fund100_stock_historical_sec_listing_p4u_v1_0 as p4u
    from hashlib import sha256
    monkeypatch.setattr(m.f4,"selected_jobs",lambda **kw:(
        [(SEC_CIK,"AAPL","Nasdaq")],m.FROZEN_F4_CIK_COMMITMENT,8))
    calls=[]
    def sub(cik):
        calls.append(("sub",cik))
        return json.dumps(submissions(cik=f"{SEC_CIK:010d}")).encode()
    def primary(path):
        calls.append(("primary",path))
        assert path==SEC_PATH
        index=b"<html>Official SEC index table fixture</html>"
        body=primary_markup()
        index_url,primary_url=p4u._primary_urls(path,"test-10k.htm")
        return body,index,"test-10k.htm",primary_url,index_url
    output=m.assess(directories={},sec_raw=b"{}",observed=ASOF,
                    submissions_get=sub,primary_get=primary,min_pool=2)
    assert calls==[("sub",SEC_CIK),("primary",SEC_PATH)]
    assert output["frozen_issuer_source_status_counts"]=={
        "EXACT_OWN_10K_12B_SYMBOL_COMMON_VENUE_REVIEW_ONLY_NOT_FIGI_PROVEN":1,
        "PRECOMMITTED_ISSUER_MULTI_SYMBOL_OR_UNMATCHED_HOLD":7,
    }
    assert output["original_issuer_count"]==8
    assert output["original_vendor_figi_to_sec_cik_identity_proven"] is False
    assert output["live_authorized"] is False
    assert output["broker_gets"]==output["broker_posts"]==output["broker_orders"]==0
    blob=json.dumps(output)
    for item in ("AAPL",SEC_ACC,"320193","test-10k.htm"):
        assert item not in blob


def test_source_document_not_canonical_is_never_favorable(monkeypatch):
    monkeypatch.setattr(m.f4,"selected_jobs",lambda **kw:(
        [(SEC_CIK,"AAPL","Nasdaq")],m.FROZEN_F4_CIK_COMMITMENT,8))
    def bad_primary(path):
        return (primary_markup(),b"index","name.htm",
                "https://untrusted.example/10k",
                "https://untrusted.example/index")
    with pytest.raises(m.CoverHold):
        m.assess(directories={},sec_raw=b"{}",observed=ASOF,
                 submissions_get=lambda _:json.dumps(submissions()).encode(),
                 primary_get=bad_primary,min_pool=2)


def test_10k_without_filing_or_unreachable_original_stays_hold(monkeypatch):
    monkeypatch.setattr(m.f4,"selected_jobs",lambda **kw:(
        [(SEC_CIK,"AAPL","Nasdaq")],m.FROZEN_F4_CIK_COMMITMENT,8))
    o=m.assess(directories={},sec_raw=b"{}",observed=ASOF,
               submissions_get=lambda _:None,
               primary_get=lambda _:pytest.fail("No primary request authorized"),min_pool=2)
    assert o["frozen_issuer_source_status_counts"][
        "ORIGINAL_SEC_SUBMISSIONS_404_HOLD"]==1
    assert o["original_issuer_count"]==8
