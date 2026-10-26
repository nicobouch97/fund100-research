"""V7 E6 full-cohort identity and event authenticity tests. No SEC requests."""
import json
import pytest

import fund100_v7_e6_24issuer_sec_earnings_capture_v1_0 as e6
import fund100_stock_sec_source_p4b_v1_0 as sec
import fund100_v7_e4_sec_event_capture_v1_0 as e4

AGENT="Fund100 Fixture fixture-research@proof.invalid"  # no real requests

def source(cik,mode="mixed"):
    if mode=="empty":
        recent={"form":[],"accessionNumber":[],"filingDate":[],"items":[]}
    else:
        dates=["2026-10-26","2026-10-21","2026-10-27","2026-10-26"]
        recent={
            "form":["8-K","8-K","8-K/A","10-K"],
            "accessionNumber":[f"0000000000-26-00000{i}" for i in range(1,5)],
            "filingDate":dates,
            "items":["2.02,9.01","2.02,9.01","2.02","2.02"],
        }
    return json.dumps({"cik":int(cik),"filings":{"recent":recent}}).encode()

def snapshot(mode="mixed"):
    expected=e6.identities()
    ciks={r["cik"] for r in expected}
    calls=[]
    def loader(url,agent):
        assert url.startswith("https://data.sec.gov/submissions/CIK")
        assert agent==AGENT
        cik=url.split("CIK",1)[1].split(".json",1)[0]
        assert cik in ciks
        calls.append(cik)
        return source(cik,mode=mode)
    obj,raw=e6.collect(agent=AGENT,loader=loader,
                       clock=lambda:"2026-10-27T16:10:21Z")
    assert len(calls)==24 and len(set(calls))==24
    return obj,raw

def write(tmp_path,obj,raw):
    for path,data in raw.items():
        fp=tmp_path/path
        fp.parent.mkdir(parents=True,exist_ok=True)
        fp.write_bytes(data)
    (tmp_path/"manifest.json").write_text(json.dumps(obj))

def test_all_24_are_frozen_and_no_identity_drift():
    roster=e6.identities()
    assert len(roster)==24
    assert len({r["ticker"] for r in roster})==24
    assert len({r["cik"] for r in roster})==24
    assert roster==sorted(roster,key=lambda r:r["ticker"])
    assert len([r for r in roster
                if r["frozen_registration"]=="2026-10-15"])==8
    assert len([r for r in roster
                if r["frozen_registration"]=="2026-10-24"])==16
    assert e6.ORIGINAL_P4N_RUN_ID==40345993054
    assert e6.ORIGINAL_P4N_MANIFEST_SHA256==(
        "39a1cf8ab1bc5f6cfa2f915da409231be3b23c84b2adbc210f94fafade5b530e")
    assert set(e6.EXTRA_SIXTEEN)=={
        "AVGO","CAT","COST","CVX","DIS","HD","JPM","LLY","MA",
        "MCD","META","NEE","NVDA","PEP","V","WMT"}
    assert e4.REGISTERED=="2026-10-15"

def test_21_oct_event_counts_for_eight_but_excludes_new_16_and_amendments(tmp_path):
    doc,raw=snapshot()
    assert doc["source_count"]==24
    assert len(raw)==24
    assert doc["after_registration_event_count"]==32   # all 24 on Oct 26 + original 8 on Oct 21
    assert doc["precohort_reference_event_count"]==16  # new 16 on Oct 21
    assert all(r["filing_date"]=="2026-10-21" for r in
               doc["precohort_reference_earnings_8k_events_not_trade_signals"])
    assert all(r["cohort_status"].startswith("EARLIER_THAN")
               for r in doc["precohort_reference_earnings_8k_events_not_trade_signals"])
    assert all(r["cohort_status"].startswith("AFTER_REGISTERED")
               for r in doc["after_registration_earnings_8k_events_not_trade_signals"])
    assert doc["forward_return_observations"]==0
    assert not doc["live_authorized"] and not doc["paper_authorized"]
    assert doc["broker_orders"]==doc["broker_http_requests"]==0
    assert not doc["new_event_first_discovered_in_this_capture_proven"]
    write(tmp_path,doc,raw)
    assert e6.verify(tmp_path)["after_registration_event_count"]==32

def test_offline_capture_with_no_8k_is_valid_and_never_synthetic_profit(tmp_path):
    doc,raw=snapshot("empty")
    assert doc["after_registration_event_count"]==0
    assert doc["precohort_reference_event_count"]==0
    assert doc["after_registration_earnings_8k_events_not_trade_signals"]==[]
    write(tmp_path,doc,raw)
    assert e6.verify(tmp_path)["forward_return_observations"]==0

def test_sha_mutation_or_manifest_event_injection_never_becomes_signal(tmp_path):
    doc,raw=snapshot()
    write(tmp_path,doc,raw)
    target=tmp_path/next(iter(raw))
    target.write_bytes(b'{}')
    with pytest.raises(e6.ExpandedFeedStop,match="bytes and SHA"):
        e6.verify(tmp_path)
    write(tmp_path,doc,raw)
    forged=json.loads((tmp_path/"manifest.json").read_text())
    forged["after_registration_earnings_8k_events_not_trade_signals"].append(
        {"ticker":"FAKE","orders_authorized":True})
    (tmp_path/"manifest.json").write_text(json.dumps(forged))
    with pytest.raises(e6.ExpandedFeedStop,match="Source events"):
        e6.verify(tmp_path)

def test_separate_original_E4_cohort_remains_unchanged():
    assert len(sec.read_cohort())==8
    assert e4.SCHEMA=="FUND100_V7_E4_PROSPECTIVE_SEC_SUBMISSIONS_SOURCE_V1"
    assert e6.SCHEMA!=e4.SCHEMA

def test_future_dates_and_false_CIK_are_rejected():
    def bad_future(url,agent):
        cik=url.split("CIK",1)[1].split(".json",1)[0]
        data=json.loads(source(cik))
        data["filings"]["recent"]["filingDate"][0]="2026-11-01"
        return json.dumps(data).encode()
    with pytest.raises(Exception,match="Future-dated"):
        e6.collect(agent=AGENT,loader=bad_future,
                   clock=lambda:"2026-10-27T16:10:21Z")
    def false_cik(url,agent):
        return source("0000000001")
    with pytest.raises(sec.SecIntakeStop,match="CIK identity"):
        e6.collect(agent=AGENT,loader=false_cik,
                   clock=lambda:"2026-10-27T16:10:21Z")

def test_capture_never_backdates_or_mixes_before_registration():
    def normal(url,agent):
        cik=url.split("CIK",1)[1].split(".json",1)[0]
        return source(cik,mode="empty")
    with pytest.raises(e6.ExpandedFeedStop,match="Future cohort not yet registered"):
        e6.collect(agent=AGENT,loader=normal,
                   clock=lambda:"2026-10-22T00:00:00Z")
    count=[0]
    def clock():
        count[0]+=1
        return "2026-10-27T16:10:22Z" if count[0]<=24 else "2026-10-27T16:10:20Z"
    with pytest.raises(e6.ExpandedFeedStop,match="completion"):
        e6.collect(agent=AGENT,loader=normal,clock=clock)

def test_contact_identity_legal_and_zero_broker_or_live_state():
    with pytest.raises(sec.SecIntakeStop):
        e6.collect(agent="Anonymous someone@example.com",
                   loader=lambda *args: (_ for _ in ()).throw(AssertionError()))
    from pathlib import Path
    script=Path(e6.__file__).read_text()
    assert e6.BROKER_ORDERS==0
    for forbidden in ("ALPACA_LIVE_KEY","TradingClient","create_order",
                      "api.alpaca.markets","alpaca-py","FUND100_BROKER_KILL_SWITCH"):
        assert forbidden not in script


def test_large_real_jpm_style_sec_recent_feed_is_validated_then_windowed():
    cik=e6.EXTRA_SIXTEEN["JPM"]
    # Official JPM "recent" original had 26,430 rows; original eight E1
    # bounds are 5k. Historical, pre-registered trailing 10-K rows cannot
    # cause a truthful source-only 24-company earnings feed to fail.
    n=26430
    filings={
        "form":["10-K"]*(n-1)+["8-K"],
        "accessionNumber":[f"0000000000-16-{i:06d}" for i in range(n-1)]
                          +["0000000000-26-000777"],
        "filingDate":["2016-12-31"]*(n-1)+["2026-10-26"],
        "items":[""]*(n-1)+["2.02,9.01"],
    }
    sec_obj={"cik":int(cik),"filings":{"recent":filings}}
    good,older=e6._events(sec_obj,"JPM",cik,"2026-10-24",
                          "2026-10-27T17:00:00Z")
    assert len(good)==1 and good[0]["original_sec_accession"]=="0000000000-26-000777"
    assert older==[]
    # Full source array consistency is checked BEFORE any date filtering.
    filings["items"].pop()
    with pytest.raises(e6.ExpandedFeedStop,match="inconsistent or unbounded"):
        e6._events(sec_obj,"JPM",cik,"2026-10-24",
                   "2026-10-27T17:00:00Z")


def test_large_source_future_earnings_filing_cannot_be_filtered_away():
    cik=e6.EXTRA_SIXTEEN["JPM"]
    n=5500
    records={
        "form":["10-K"]*(n-1)+["8-K"],
        "accessionNumber":[f"0000000000-16-{i:06d}" for i in range(n-1)]
                          +["0000000000-26-000778"],
        "filingDate":["2016-12-31"]*(n-1)+["2026-10-28"],
        "items":[""]*(n-1)+["2.02,9.01"],
    }
    with pytest.raises(Exception,match="Future-dated"):
        e6._events({"filings":{"recent":records}},"JPM",cik,
                   "2026-10-24","2026-10-27T17:00:00Z")
    records["filingDate"]=["2026-10-28"]*n
    with pytest.raises(e6.ExpandedFeedStop,match="unexpectedly oversized"):
        e6._events({"filings":{"recent":records}},"JPM",cik,
                   "2026-10-24","2026-10-27T17:00:00Z")
