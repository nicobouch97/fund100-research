"""No-network adversarial original 10-K per-share EPS availability tests."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import pytest

import fund100_v9_f6_original_10k_diluted_eps_coverage_v1_0 as f6
import fund100_stock_historical_sec_listing_p4u_v1_0 as p4u

ASOF = datetime(2026,11,11,12,40,tzinfo=timezone.utc)
ACC = "0001193125-26-000001"
FILED = "2026-02-20"
END = "2025-12-31"
START = "2025-01-01"
GOOD = [320193,1002,1003]
ALL = GOOD + [1004,1005,1006,1007,1008]
FROZEN_DIGEST = f6.f5.FROZEN_F4_CIK_COMMITMENT


def subs(cik: int, *, form="10-K", filed=FILED, end=END):
    return {"cik":f"{cik:010d}","filings":{"recent":{
        "accessionNumber":[ACC],
        "form":[form],
        "reportDate":[end],
        "filingDate":[filed],
        "acceptanceDateTime":[filed+"T16:30:00.000Z"],
    }}}


def primary_html(*, symbol="AAPL", listed=True):
    row = ("<tr><td>Common Stock</td><td>"+symbol+"</td>"
           "<td>Nasdaq Global Select Market</td></tr>" if listed else "")
    return ("<html><body><p>Securities registered pursuant to Section 12(b)"
            " of the Act</p><table><tr><th>Title</th><th>Trading symbol"
            "</th><th>Exchange</th></tr>"+row+"</table>"
            "<p>Securities registered pursuant to Section 12(g) of the Act: None</p>"
            "</body></html>").encode()


def filing_primary(path: str, *, listed: bool):
    name="annual_10k.htm"
    index_url,primary_url=p4u._primary_urls(path,name)
    index=("<html><table><tr><td>1</td><td>Annual</td><td>"
           '<a href="'+primary_url+'">'+name+"</a></td><td>10-K</td>"
           "<td>100</td></tr></table></html>").encode()
    return (primary_html(listed=listed),index,name,primary_url,index_url)


def companyfacts(cik: int, eps=2.5, *, accession=ACC, filed=FILED,
                 start=START, end=END):
    units = {"USD/shares": [{
        "accn":accession,"filed":filed,"form":"10-K",
        "start":start,"end":end,"val":eps,
    }]} if eps is not None else {"USD/shares":[]}
    return {"cik":cik,"facts":{"us-gaap":{
        "EarningsPerShareDiluted":{"units":units}
    }}}


def sources(monkeypatch, *, eps_map=None, primary_issues=None):
    """Eight frozen original issuers, three matched, four no row, one stale FY."""
    eps_map=eps_map or {GOOD[0]:2.5,GOOD[1]:-1.5,GOOD[2]:None}
    primary_issues=primary_issues or {}
    monkeypatch.setattr(f6.f4, "selected_jobs", lambda **kw:(
        [(c,"AAPL","Nasdaq") for c in ALL],FROZEN_DIGEST,8))
    counts = {"companyfacts":[],"primary":[],"submissions":[]}
    def subs_get(cik):
        counts["submissions"].append(cik)
        if cik==ALL[-1]:
            return json.dumps(subs(cik,filed="2023-01-20",end="2022-12-31")).encode()
        return json.dumps(subs(cik)).encode()
    def primary_get(path):
        counts["primary"].append(path)
        cik=int(path.split("/")[2])
        if cik in primary_issues:
            raise p4u.FilingSourceFailure(primary_issues[cik])
        return filing_primary(path,listed=cik in GOOD)
    def facts_get(cik):
        counts["companyfacts"].append(cik)
        if eps_map[cik]=="missing-source":
            return None
        return json.dumps(companyfacts(cik,eps=eps_map[cik])).encode()
    return counts,subs_get,primary_get,facts_get


def test_strict_original_own_10k_eps_positive_nonpositive_missing_and_provenance():
    sub=subs(GOOD[0])
    for eps,wanted in [
        (2.5,"ORIGINAL_OWN_10K_DILUTED_EPS_POSITIVE_REVIEW_ONLY"),
        (0,"ORIGINAL_OWN_10K_DILUTED_EPS_NONPOSITIVE_REVIEW_ONLY"),
        (-1.5,"ORIGINAL_OWN_10K_DILUTED_EPS_NONPOSITIVE_REVIEW_ONLY"),
        (None,"ORIGINAL_OWN_10K_DILUTED_EPS_NOT_AVAILABLE_HOLD"),
    ]:
        assert f6.eps_original_own_accession_status(
            facts=companyfacts(GOOD[0],eps),submissions=sub,cik=GOOD[0],
            accession=ACC,filed=FILED,end=END)==wanted


@pytest.mark.parametrize("changes",[
    {"accession":"0001193125-26-000002"},
    {"filed":"2026-02-21"},
    {"end":"2025-06-30"},
    {"start":"2025-12-30"},
])
def test_eps_must_be_original_10k_own_accession_fy_filing_and_full_year(changes):
    assert f6.eps_original_own_accession_status(
        facts=companyfacts(GOOD[0],**changes),
        submissions=subs(GOOD[0]),cik=GOOD[0],
        accession=ACC,filed=FILED,end=END
    )=="ORIGINAL_OWN_10K_DILUTED_EPS_NOT_AVAILABLE_HOLD"


def test_reject_eps_from_different_issuer_or_mismatched_submissions_cik():
    for bad in (companyfacts(GOOD[1]),):
        result=f6.eps_original_own_accession_status(
            facts=bad,submissions=subs(GOOD[0]),cik=GOOD[0],
            accession=ACC,filed=FILED,end=END)
        assert result=="ORIGINAL_EPS_SOURCE_UNQUALIFIED_HOLD"
    result=f6.eps_original_own_accession_status(
        facts=companyfacts(GOOD[0]),submissions=subs(GOOD[1]),cik=GOOD[0],
        accession=ACC,filed=FILED,end=END)
    assert result=="ORIGINAL_EPS_SOURCE_UNQUALIFIED_HOLD"


def test_conflicting_original_eps_values_are_quarantined():
    facts=companyfacts(GOOD[0])
    facts["facts"]["us-gaap"]["EarningsPerShareDiluted"]["units"]["USD/shares"].append({
        "accn":ACC,"filed":FILED,"form":"10-K",
        "start":START,"end":END,"val":99.0,
    })
    result=f6.eps_original_own_accession_status(
        facts=facts,submissions=subs(GOOD[0]),cik=GOOD[0],
        accession=ACC,filed=FILED,end=END)
    assert result=="ORIGINAL_EPS_SOURCE_UNQUALIFIED_HOLD"


def test_frozen_original_eight_and_only_three_class_matches_fetch_companyfacts(monkeypatch):
    counts,subs_get,primary_get,facts_get=sources(monkeypatch)
    report=f6.assess(directories={},sec_raw=b"{}",observed=ASOF,
                     submissions_get=subs_get,primary_get=primary_get,
                     facts_get=facts_get,min_pool=2)
    assert len(counts["submissions"])==8
    assert len(counts["primary"])==7
    assert counts["companyfacts"]==GOOD
    assert report["original_issuer_denominator"]==8
    assert report["original_issuer_declared_12b_class_candidates"]==3
    assert report["companyfacts_source_requests_for_only_class_candidates"]==3
    assert report["source_status_counts"]=={
        "ORIGINAL_OWN_10K_DILUTED_EPS_POSITIVE_REVIEW_ONLY":1,
        "ORIGINAL_OWN_10K_DILUTED_EPS_NONPOSITIVE_REVIEW_ONLY":1,
        "ORIGINAL_OWN_10K_DILUTED_EPS_NOT_AVAILABLE_HOLD":1,
        "NO_STRUCTURED_12B_PLAIN_COMMON_ROW_HOLD":4,
        "NO_RECENT_ASOF_ELIGIBLE_OWN_10K_HOLD":1,
    }
    assert report["independent_issuer_cik_to_figi_proven"] is False
    assert report["expected_alpha_or_cheap_stock_inferred"] is False
    assert report["live_authorized"] is False
    assert report["broker_gets"]==report["broker_posts"]==report["broker_orders"]==0
    report_text=json.dumps(report)
    for forbidden in ("320193","1002","AAPL",ACC,"annual_10k.htm","2.5"):
        assert forbidden not in report_text


def test_missing_companyfacts_is_hold_not_cheap_or_zero(monkeypatch):
    counts,a,b,c=sources(monkeypatch,eps_map={
        GOOD[0]:"missing-source",GOOD[1]:-1.5,GOOD[2]:None})
    report=f6.assess(directories={},sec_raw=b"{}",observed=ASOF,
                     submissions_get=a,primary_get=b,facts_get=c,min_pool=2)
    assert report["source_status_counts"]["ORIGINAL_SEC_COMPANYFACTS_404_HOLD"]==1
    assert len(counts["companyfacts"])==3


def test_primary_index_failure_is_hold_and_cannot_promote_different_candidate(monkeypatch):
    counts,a,b,c=sources(monkeypatch,primary_issues={GOOD[1]:"HTTP_403"})
    with pytest.raises(f6.EpsCoverageHold,
                       match="three class matches changed"):
        f6.assess(directories={},sec_raw=b"{}",observed=ASOF,
                  submissions_get=a,primary_get=b,facts_get=c,min_pool=2)
    assert counts["companyfacts"]==[GOOD[0],GOOD[2]]


def test_changed_original_cohort_commitment_never_reselects(monkeypatch):
    monkeypatch.setattr(f6.f4,"selected_jobs",lambda **kw:([], "wrong", 8))
    with pytest.raises(f6.EpsCoverageHold,match="eight issuer cohort changed"):
        f6.assess(directories={},sec_raw=b"{}",observed=ASOF,
                  submissions_get=lambda _:pytest.fail("No source GET"),
                  primary_get=lambda _:pytest.fail("No SEC primary GET"),
                  facts_get=lambda _:pytest.fail("No companyfacts GET"),
                  min_pool=2)
