"""Source-hashed broad prospective 100-issuer roster: NO BROKER."""
import json
import pytest

import fund100_v7_u1_original_ivv_100_issuer_freeze_v1_0 as u

NOW="2026-10-27T15:00:00Z"

def fixtures():
    header='iShares Core S&P 500 ETF\nFund Holdings as of,"Oct 23, 2026"\n'
    head="Ticker,Name,Sector,Asset Class,Weight (%),Market Value\n"
    rows=[]
    # 450 original equity identifiers; 10 larger issuer weights and
    # 440 smaller source weights total 99.80 percent.
    for i in range(450):
        rows.append(f'S{i:03},Issuer {i},Technology,Equity,{"0.30" if i<10 else "0.22"},100000')
    rows.append("CASH,USD,Other,Cash,0.20,100")
    raw=(header+head+"\n".join(rows)+"\nProvider disclaimer: not a trading signal.\n").encode()
    records={}
    for i in range(1200):
        ticker=f"S{i:03}" if i<450 else f"T{i:03}"
        records[str(i)]={"ticker":ticker,"cik_str":i+1000,
                         "title":f"Test Issuer {i}"}
    return raw,json.dumps(records,sort_keys=True).encode()

def evaluate(hold=None,sec=None,now=NOW):
    h,m=fixtures()
    return u.freeze(holdings_csv=h if hold is None else hold,
                    sec_ticker_json=m if sec is None else sec,
                    captured_at_utc=now)

def test_first_source_is_weight_ranked_unique_sec_issuer_roster():
    result=evaluate()
    assert result["schema"]==u.SCHEMA
    assert result["original_holdings_reported_asof"]=="2026-10-23"
    assert result["original_source_collected_at_utc"]==NOW
    assert result["original_equity_symbols_count"]==450
    assert result["original_official_provider_weight_sum_with_cash_excluded"]=="99.80"
    assert len(result["prospectively_frozen_100_unique_cik_roster"])==100
    assert result["prospectively_frozen_100_unique_cik_roster"][0]["ticker"]=="S000"
    assert result["prospectively_frozen_100_unique_cik_roster"][99]["ticker"]=="S099"
    assert result["prospectively_frozen_100_unique_cik_roster"][0]["sec_cik_10_digit"]=="0000001000"
    assert not result["eligible_to_rank_or_execute_live_orders"]
    assert not result["live_authorized"] and not result["trading_authorized"]
    assert result["broker_gets"]==result["broker_posts"]==result["broker_orders"]==0

def test_cik_deduplication_does_not_double_count_second_share_class():
    raw,sec=fixtures()
    data=json.loads(sec)
    # S001 represents another class of S000's original issuer.
    data["1"]["cik_str"]=data["0"]["cik_str"]
    result=evaluate(hold=raw,sec=json.dumps(data).encode())
    names=[r["ticker"] for r in result["prospectively_frozen_100_unique_cik_roster"]]
    assert "S000" in names and "S001" not in names
    assert len(names)==100
    assert names[-1]=="S100"
    assert len({r["sec_cik_10_digit"] for r in result["prospectively_frozen_100_unique_cik_roster"]})==100

def test_source_weight_ranking_not_alphabetical_future_winner():
    raw,sec=fixtures()
    changed=raw.replace(b"S430,Issuer 430,Technology,Equity,0.22,100000",
                        b"S430,Issuer 430,Technology,Equity,0.31,100000")
    # Keep original full-source weight within valid 95-102% bounds.
    doc=evaluate(hold=changed,sec=sec)
    names=[r["ticker"] for r in doc["prospectively_frozen_100_unique_cik_roster"]]
    assert names[0]=="S430"
    assert names[1]=="S000"
    assert names[-1]=="S098"

def test_missing_provider_date_or_source_after_now_refused():
    raw,sec=fixtures()
    with pytest.raises(u.UniverseStop):
        evaluate(hold=raw.replace(b"Fund Holdings as of",b"Unknown reported date"),sec=sec)
    with pytest.raises(u.UniverseStop):
        evaluate(hold=raw,sec=sec,now="2026-10-22T15:00:00Z")
    with pytest.raises(u.UniverseStop):
        evaluate(hold=raw,sec=sec,now="2026-11-04T15:00:00Z")
    with pytest.raises(u.UniverseStop):
        evaluate(hold=raw,sec=sec,now="2026-10-26T15:00:00Z")

def test_shorter_membership_or_cash_treated_as_equity_fails():
    raw,sec=fixtures()
    reduced=b"\n".join(raw.splitlines()[:250])
    with pytest.raises(u.UniverseStop):
        evaluate(hold=reduced,sec=sec)
    wrong=raw.replace(b"S200,Issuer 200,Technology,Equity,0.22,100000",
                      b"S200,Issuer 200,Technology,Cash,0.22,100000")
    # Removing one 0.22% issuer would make the provider weight sum 99.58
    # (valid), but source equities still reach >=400. The instrument must
    # remain excluded even if the source label changes.
    doc=evaluate(hold=wrong,sec=sec)
    assert doc["original_equity_symbols_count"]==449
    assert all(x["ticker"]!="CASH" for x in doc["prospectively_frozen_100_unique_cik_roster"])

def test_missing_sec_identity_is_not_silently_invented():
    raw,sec=fixtures()
    payload=json.loads(sec)
    for i in range(420):
        payload[str(i)]["ticker"]=f"X{i:03}"
    with pytest.raises(u.UniverseStop,match="Insufficient uniquely"):
        evaluate(hold=raw,sec=json.dumps(payload).encode())

def test_unknown_provider_duplicate_ticker_or_bad_weight_rejected():
    raw,sec=fixtures()
    duplicated=raw.replace(b"S100,Issuer 100",b"S000,Issuer 100")
    with pytest.raises(u.UniverseStop):
        evaluate(hold=duplicated,sec=sec)
    modified=raw.replace(b"S020,Issuer 20,Technology,Equity,0.22,100000",
                         b"S020,Issuer 20,Technology,Equity,-1.00,100000")
    with pytest.raises(u.UniverseStop):
        evaluate(hold=modified,sec=sec)
    modified=raw.replace(b"S020,Issuer 20,Technology,Equity,0.22,100000",
                         b"S020,Issuer 20,Technology,Equity,NaN,100000")
    with pytest.raises(u.UniverseStop):
        evaluate(hold=modified,sec=sec)

def test_source_rewrites_have_distinct_hashes_even_if_top100_same():
    raw,sec=fixtures()
    base=evaluate(hold=raw,sec=sec)
    replaced=raw.replace(b"S300,Issuer 300",b"S300,Issuer THREEHUNDRED")
    another=evaluate(hold=replaced,sec=sec)
    assert base["original_provider_csv_sha256"]!=another["original_provider_csv_sha256"]
    assert (base["prospectively_frozen_100_unique_cik_roster"]==
            another["prospectively_frozen_100_unique_cik_roster"])
    assert base["future_sec_events_or_returns_observed"]==another["future_sec_events_or_returns_observed"]==0

def test_conflicting_ticker_cik_source_fails_instead_of_guessing():
    raw,sec=fixtures()
    records=json.loads(sec)
    records["1100"]={"ticker":"S000","cik_str":999999,
                     "title":"Different Issuer Same Ticker"}
    with pytest.raises(u.UniverseStop,match="Ambiguous"):
        evaluate(hold=raw,sec=json.dumps(records).encode())
