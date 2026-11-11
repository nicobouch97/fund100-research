"""V9 F4 authentic-source-shape tests; all offline, no public network or broker."""
from datetime import datetime, timedelta, timezone
import json

import pytest

import fund100_v9_f4_current_openfigi_class_reference_v1_0 as m
import test_fund100_v9_broad_original_sec_quality_coverage_v1_0 as fx


def jobs(monkeypatch):
    monkeypatch.setattr(m, "REGISTERED_COHORT_SIZE", 2)
    records, digest, size = m.selected_jobs(
        directories=fx.FILES, sec_raw=fx.REGISTRY,
        observed=fx.ASOF, min_pool=2)
    assert size == 2 and len(records) == 2 and len(digest) == 64
    assert set(v[1] for v in records) == {"AAPL","IBM"}
    return records


def fake(records, *, share=None):
    response=[]
    for i, (_,ticker,_) in enumerate(records):
        response.append({"data":[{
            "ticker":ticker,"exchCode":"US","marketSector":"Equity",
            "securityType":"Common Stock","securityType2":"Common Stock",
            "figi":f"BBG0000000{i+1}","compositeFIGI":f"BBG0000001{i+1}",
            "shareClassFIGI":share or f"BBG0000002{i+1}",
            "name":"Unverified issuer name"
        }]})
    return json.dumps(response).encode()


def test_original_exact_precommitted_two_source_symbols_never_prove_sec_cik_link(monkeypatch):
    records=jobs(monkeypatch)
    assert all(q["includeUnlistedEquities"] is True for q in m.mapping_payload(records))
    output=m.report(
        directories=fx.FILES,sec_raw=fx.REGISTRY,observed=fx.ASOF,
        figi_raw=fake(records),
        figi_observed=fx.ASOF+timedelta(minutes=1),min_pool=2)
    assert output["registered_original_issuer_cohort_not_return_selected"]==2
    assert output["first_eight_source_linked_current_symbols_queried"]==2
    assert output["source_status_counts_not_issuer_to_class_corroboration"]=={
        "CURRENT_SYMBOL_COMMON_CLASS_CANDIDATE_NOT_CIK_PROVEN":2}
    assert output["openfigi_vendor_identity_not_sec_cik_verified"] is True
    assert output["class_specific_share_count_price_or_market_cap_verified"] is False
    assert output["underlying_us_share_class_permanent_id_verified"] is False
    assert output["live_authorized"] is False
    assert output["broker_gets"]==output["broker_posts"]==output["broker_orders"]==0
    for raw in ("AAPL","IBM","320193","51143","BBG00000021","BBG00000022"):
        assert raw not in json.dumps(output)


def test_duplicate_share_class_across_two_distinct_issuer_queries_cannot_be_counted_twice(monkeypatch):
    records=jobs(monkeypatch)
    classes=m.classify(jobs=records,raw=fake(records,share="BBG000002222"))
    assert classes=={"DUPLICATE_CLASS_CROSS_ISSUER_HOLD":2}


def test_null_exchange_original_sec_alias_quarantines_selected_issuer(monkeypatch):
    monkeypatch.setattr(m, "REGISTERED_COHORT_SIZE",2)
    sec=json.loads(fx.REGISTRY)
    sec["data"].append([320193,"Apple alternate", "APPLX",None])
    records,_,total=m.selected_jobs(
        directories=fx.FILES,sec_raw=json.dumps(sec).encode(),
        observed=fx.ASOF,min_pool=2)
    assert total==2 and len(records)==1
    assert records[0][1]=="IBM"


@pytest.mark.parametrize("change,expected",[
    (lambda x:x[0].update({"warning":"source incomplete"}), "SOURCE_WARNED_UNQUALIFIED"),
    (lambda x:x[0].update({"error":"source missing"}), "SOURCE_NO_MAPPING_OR_ERROR"),
    (lambda x:x[0].update({"data":[]}), "ZERO_OR_MULTIPLE_OPENFIGI_CANDIDATES_HOLD"),
    (lambda x:x[0]["data"][0].update({"shareClassFIGI":None}),
     "UNMATCHED_OR_MISSING_INSTRUMENT_ID_HOLD"),
    (lambda x:x[0]["data"][0].update({"ticker":"OTHER"}),
     "UNMATCHED_OR_MISSING_INSTRUMENT_ID_HOLD"),
    (lambda x:x[0]["data"][0].update({"securityType2":"Preferred Stock"}),
     "NONCOMMON_OR_UNVERIFIED_INSTRUMENT_HOLD"),
    (lambda x:x[0]["data"][0].update({"marketSector":"Fixed Income"}),
     "NONCOMMON_OR_UNVERIFIED_INSTRUMENT_HOLD"),
])
def test_unqualified_mapping_is_not_trade_ready(monkeypatch,change,expected):
    records=jobs(monkeypatch)
    data=json.loads(fake(records))
    change(data)
    result=m.classify(jobs=records,raw=json.dumps(data).encode())
    assert result[expected]>=1
    assert sum(result.values())==len(records)


@pytest.mark.parametrize("response",[
    b"",b"garbage",b"{}",b"[]",b"{}{}",b'{"data":[]}',
    b'[{"data":[]},{"data":[]},{"data":[]}]',
    b'[{"data":{}} , {"data":[]}]',
    b'[{"other":"untrusted"}, {"data":[]}]',
    b'[{"error":17}, {"data":[]}]',
])
def test_malformed_current_reference_source_fails_closed(monkeypatch,response):
    records=jobs(monkeypatch)
    with pytest.raises(m.FigiHold):
        m.classify(jobs=records,raw=response)


def test_symbol_or_exchange_cannot_be_forged_in_source_request(monkeypatch):
    records=jobs(monkeypatch)
    for replacement in ((123,"AAA","Nasdaq"),(12,"AAPL/","Nasdaq"),
                        (12,"AAPL","X"),(12,"AAPL","Nasdaq")):
        sample=records[:] + [replacement]
        with pytest.raises(m.FigiHold):
            m.mapping_payload(sample)
    assert m.NO_BROKER_GETS==m.NO_BROKER_POSTS==m.NO_BROKER_ORDERS==0


def test_original_source_timestamp_order_required(monkeypatch):
    records=jobs(monkeypatch)
    with pytest.raises(m.FigiHold):
        m.report(
            directories=fx.FILES,sec_raw=fx.REGISTRY,observed=fx.ASOF,
            figi_raw=fake(records),
            figi_observed=fx.ASOF-timedelta(seconds=1),min_pool=2)
