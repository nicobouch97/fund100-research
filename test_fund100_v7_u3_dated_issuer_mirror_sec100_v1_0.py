"""The U3 mirror is not a direct iShares source, nor brokerage authority."""
import json
import pytest
import fund100_v7_u3_dated_issuer_mirror_sec100_v1_0 as u

NOW="2026-10-27T16:45:00Z"

def fixtures():
    h={f"S{i:03}":0.20 if i<500 else 0.025 for i in range(504)}
    # Weight sum 500*0.20 +4*.025 = 100.1%.
    f={
        "ticker":"IVV","name":"iShares Core S&P 500 ETF",
        "source_layer":"issuer","license":"CC BY 4.0",
        "cite_as":"TickerInside, iShares Core S&P 500 ETF (IVV), holdings from the issuer's file of 2026-10-22, https://tickerinside.com/etf/ivv/, CC BY 4.0",
        "page_url":"https://tickerinside.com/etf/ivv/",
        "holdings_as_of":"2026-10-22",
        "positions":504,
        "category":{"asset_class":"equity","as_of":"2026-10-22"},
        "holdings":h,
    }
    companies={str(i):{"ticker":f"S{i:03}" if i<504 else f"T{i:03}",
                      "cik_str":i+1000,
                      "title":f"Fake stock number {i}"} for i in range(1300)}
    return json.dumps(f,sort_keys=True).encode(),json.dumps(companies,sort_keys=True).encode()

def run(mirror=None,sec=None,now=NOW):
    a,b=fixtures()
    return u.freeze(mirror_bytes=mirror if mirror is not None else a,
                    official_sec_ticker_bytes=sec if sec is not None else b,
                    acquired_utc=now)

def test_first_100_cik_mapped_original_mirror_for_future_only():
    result=run()
    assert result["schema"]==u.SCHEMA
    assert not result["source_is_direct_official_ishares_file"]
    assert result["third_party_provider_claims_issuer_source_layer"]
    assert result["mirror_dated_issuer_attributed_holdings_asof"]=="2026-10-22"
    assert result["source_reported_positions"]==504
    assert result["source_reported_weight_total_percent"]=="100.100"
    selected=result["first_100_distinct_SEC_CIK_mapped_issuer_roster"]
    assert len(selected)==len({r["sec_cik_10_digit"] for r in selected})==100
    assert selected[0]["ticker"]=="S000"
    assert selected[-1]["ticker"]=="S099"
    assert selected[0]["sec_cik_10_digit"]=="0000001000"
    assert result["no_predictive_alpha_evidence"]
    assert result["observed_new_future_returns"]==0
    assert not result["live_authorized"] and not result["trading_authorized"]
    assert result["broker_gets"]==result["broker_posts"]==result["broker_orders"]==0

def test_stock_class_cik_is_counted_once_not_double_sample():
    mirror,sec=fixtures()
    data=json.loads(sec)
    data["1"]["cik_str"]=1000
    result=run(mirror=mirror,sec=json.dumps(data).encode())
    selected=result["first_100_distinct_SEC_CIK_mapped_issuer_roster"]
    assert selected[0]["ticker"]=="S000"
    assert selected[1]["ticker"]=="S002"
    assert selected[-1]["ticker"]=="S100"

def test_vendor_source_date_cannot_be_reinterpreted_at_will():
    a,b=fixtures()
    for stale in ("2026-09-19","2026-10-28","2025-10-22"):
        x=json.loads(a);x["holdings_as_of"]=stale
        x["category"]["as_of"]=stale
        with pytest.raises(u.MirrorStop):
            run(mirror=json.dumps(x).encode(),sec=b)
    with pytest.raises(u.MirrorStop):
        run(mirror=a,sec=b,now="2026-10-27T16:00:00Z")

def test_provider_is_explicitly_third_party_not_unverified_direct_publisher():
    a,b=fixtures()
    for key,value in (
        ("ticker","VOO"),("source_layer","sec_nport"),
        ("license","All rights reserved"),("positions",503),
        ("page_url","https://somethingelse.example/"),
        ("cite_as","iShares source without provider attribution")):
        x=json.loads(a);x[key]=value
        with pytest.raises(u.MirrorStop):
            run(mirror=json.dumps(x).encode(),sec=b)

def test_missing_official_sec_mapping_no_issuer_guesses():
    a,b=fixtures()
    doc=json.loads(b)
    for i in range(430):
        doc[str(i)]["ticker"]=f"X{i:03}"
    with pytest.raises(u.MirrorStop,match="No verified distinct 100"):
        run(mirror=a,sec=json.dumps(doc).encode())

def test_mirrored_issuer_book_never_accepts_forged_weights():
    a,b=fixtures()
    for bad in (-1.0,30,True,"1.5",None):
        x=json.loads(a)
        x["holdings"]["S001"]=bad
        with pytest.raises(u.MirrorStop):
            run(mirror=json.dumps(x).encode(),sec=b)
    x=json.loads(a);x["holdings"]["S001"]=0.4
    assert run(mirror=json.dumps(x).encode(),sec=b)[
        "first_100_distinct_SEC_CIK_mapped_issuer_roster"][0]["ticker"]=="S001"

def test_cik_duplicate_stock_symbol_rejects_unsupported_sec_or_provider_bytes():
    a,b=fixtures()
    doc=json.loads(b)
    doc["1100"]={"ticker":"S000","cik_str":1234500,"title":"Conflicting company"}
    with pytest.raises(u.UniverseStop):
        run(mirror=a,sec=json.dumps(doc).encode())
    x=json.loads(a);x["holdings"]["BAD/TICKER"]=0.01;x["positions"]=505
    with pytest.raises(u.MirrorStop):
        run(mirror=json.dumps(x).encode(),sec=b)

def test_different_2026_vendor_vintage_has_distinct_hash_even_same_top100():
    a,b=fixtures()
    doc=json.loads(a)
    doc["holdings"]["S400"]=0.201
    changed=run(mirror=json.dumps(doc).encode(),sec=b)
    before=run(mirror=a,sec=b)
    assert changed["exact_mirror_original_json_sha256"]!=before["exact_mirror_original_json_sha256"]
    assert changed["first_100_distinct_SEC_CIK_mapped_issuer_roster"]==before["first_100_distinct_SEC_CIK_mapped_issuer_roster"]
    assert before["direct_issuer_source_unavailable_at_first_attempt"]
    assert not before["historical_investable_universe"]
