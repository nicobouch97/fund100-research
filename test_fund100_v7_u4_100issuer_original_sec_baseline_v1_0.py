"""Prospective U4 SEC first baseline is NOT a discovered new earnings signal."""
import json
from pathlib import Path
import pytest

import fund100_v7_u3_dated_issuer_mirror_sec100_v1_0 as u3
import fund100_v7_u4_100issuer_original_sec_baseline_v1_0 as u4
from test_fund100_v7_u3_dated_issuer_mirror_sec100_v1_0 import fixtures

AGENT="Fund100 independent tests sourcecontact@fund100-research.invalid"
DATE="2026-10-27T17:05:00Z"

def u3_files(where:Path):
    mirror,sec=fixtures()
    record=u3.freeze(mirror_bytes=mirror,official_sec_ticker_bytes=sec,
                     acquired_utc="2026-10-27T16:45:00Z")
    where.mkdir(parents=True,exist_ok=True)
    (where/"U3-first-100-issuer-research-roster.json").write_text(json.dumps(record))
    (where/"first-vintage-third-party-IVV-snapshot.json").write_bytes(mirror)
    (where/"first-vintage-official-SEC-ticker-map.json").write_bytes(sec)
    return record

def source(cik,after=False,vanish=False,form="8-K"):
    names=[
        "0000000000-26-000001",
        "0000000000-26-000002",
        "0000000000-26-000003",
        "0000000000-26-000004",
    ]
    entries={
        "form":["8-K","8-K","8-K/A","10-K"],
        "accessionNumber":names,
        "filingDate":["2026-10-23","2026-10-27","2026-10-27","2026-10-27"],
        "items":["2.02,9.01","2.02","2.02","2.02"],
    }
    if vanish:
        for k in entries:entries[k]=entries[k][1:]
    if after:
        entries["form"].append(form)
        entries["accessionNumber"].append("0000000000-26-000005")
        entries["filingDate"].append("2026-10-28")
        entries["items"].append("2.02,9.01")
    return json.dumps({"cik":int(cik),"filings":{"recent":entries}},
                      sort_keys=True).encode()

def loader(*,after=False,vanish=False,wrong=False):
    calls=[]
    def get(url,agent):
        assert agent==AGENT
        assert url.startswith("https://data.sec.gov/submissions/CIK")
        cik=url.split("CIK",1)[1].split(".json")[0]
        calls.append(cik)
        return source("0000000001" if wrong else cik,after=after,vanish=vanish)
    return get,calls

def snapshot(tmp_path,*,later=False,after=False,wrong=False):
    u3path=tmp_path/"u3"
    if not u3path.is_dir():u3_files(u3path)
    clock=("2026-10-28T17:05:00Z" if later else DATE)
    get,calls=loader(after=after,wrong=wrong)
    report,raw=u4.collect(u3_dir=u3path,agent=AGENT,loader=get,
                          clock=lambda:clock)
    return report,raw,calls

def write(root,report,raw):
    root.mkdir(parents=True,exist_ok=True)
    for name,content in raw.items():
        f=root/name
        f.parent.mkdir(parents=True,exist_ok=True)
        f.write_bytes(content)
    (root/"manifest.json").write_text(json.dumps(report))

def test_original_first_snapshot_all_one_hundred_sec_sources_not_new_events(tmp_path):
    d,raw,calls=snapshot(tmp_path)
    assert len(calls)==len(set(calls))==100
    assert d["source_count"]==len(raw)==100
    assert d["status"]=="ORIGINAL_FIRST_100_ISSUER_SEC_BASELINE_NOT_A_NEW_EVENT"
    assert d["baseline_historical_earnings_filing_accession_count"]==200
    assert d["first_new_postbaseline_sec_event_count"]==0
    assert not d["independent_first_public_release_proven"]
    assert not d["earnings_surprise_or_quality_alpha_proven"]
    assert d["observed_future_aftercost_returns"]==0
    assert d["broker_gets"]==d["broker_posts"]==d["broker_orders"]==0
    assert not d["trading_authorized"] and not d["live_authorized"]
    assert all(len(a["source_observed_item2_02_accessions"])==2 for a in
               d["first_source_issuer_rows"])
    write(tmp_path/"baseline",d,raw)
    assert u4.verify(u3_dir=tmp_path/"u3",report_dir=tmp_path/"baseline")==d

def test_delta_after_frozen_original_baseline_is_observation_not_surprise(tmp_path):
    before,raw,_=snapshot(tmp_path)
    later,_,_=snapshot(tmp_path,later=True,after=True)
    result=u4.compare(baseline=before,later=later)
    assert result["candidate_first_delta_count"]==100
    assert len(result["candidate_first_delta_filings_not_trade_signals"])==100
    assert result["forward_aftercost_outcomes_observed"]==0
    assert all(x["original_SEC_filing_date"]=="2026-10-28"
               and not x["first_original_disclosure_timestamp_confirmed"]
               and not x["order_authorized"]
               for x in result["candidate_first_delta_filings_not_trade_signals"])
    assert not result["live_authorized"] and result["broker_orders"]==0
    assert u4.compare(baseline=before,later=snapshot(
        tmp_path,later=True,after=False)[0])["candidate_first_delta_count"]==0

def test_baseline_does_not_launder_already_public_8k_as_new_deal(tmp_path):
    d,_,_=snapshot(tmp_path)
    # 23 and 27 Oct filings in the *first* capture are historical baseline,
    # even though the latter has same calendar date as freeze.
    assert d["first_new_postbaseline_sec_event_count"]==0
    assert all(a["source_observed_item2_02_accessions"][1]["filing_date"]=="2026-10-27"
               for a in d["first_source_issuer_rows"])

def test_source_sha_or_manifest_forgery_is_rejected(tmp_path):
    d,raw,_=snapshot(tmp_path)
    root=tmp_path/"baseline"
    write(root,d,raw)
    target=root/next(iter(raw))
    original=target.read_bytes()
    target.write_bytes(original[:-4]+b"xxxx")
    with pytest.raises(Exception):
        u4.verify(u3_dir=tmp_path/"u3",report_dir=root)
    target.write_bytes(original)
    fake=json.loads((root/"manifest.json").read_text())
    fake["first_source_issuer_rows"][0]["source_observed_item2_02_accessions"]=[]
    (root/"manifest.json").write_text(json.dumps(fake))
    with pytest.raises(u4.BaselineStop):
        u4.verify(u3_dir=tmp_path/"u3",report_dir=root)

def test_u3_original_roster_or_sec_id_change_is_not_reselection(tmp_path):
    d,_,_=snapshot(tmp_path)
    original=tmp_path/"u3"/"U3-first-100-issuer-research-roster.json"
    data=json.loads(original.read_text())
    data["first_100_distinct_SEC_CIK_mapped_issuer_roster"][0]["ticker"]="OUTSIDER"
    original.write_text(json.dumps(data))
    with pytest.raises(u4.BaselineStop):
        u4.original_issuer_roster(tmp_path/"u3")
    with pytest.raises(u4.BaselineStop):
        u4.collect(u3_dir=tmp_path/"u3",agent=AGENT,
                   loader=lambda *_: (_ for _ in ()).throw(AssertionError()))

def test_false_original_sec_cik_and_early_capture_fail_closed(tmp_path):
    u3_files(tmp_path/"u3")
    bad,_=loader(wrong=True)
    with pytest.raises(Exception,match="CIK"):
        u4.collect(u3_dir=tmp_path/"u3",agent=AGENT,
                   loader=bad,clock=lambda:DATE)
    get,_=loader()
    with pytest.raises(u4.BaselineStop,match="precedes"):
        u4.collect(u3_dir=tmp_path/"u3",agent=AGENT,
                   loader=get,clock=lambda:"2026-10-27T16:20:00Z")

def test_later_missing_preexisting_accessions_or_changed_population_stops(tmp_path):
    d,_,_=snapshot(tmp_path)
    later,_,_=snapshot(tmp_path,later=True,after=True)
    later["first_source_issuer_rows"][0]["source_observed_item2_02_accessions"].pop(0)
    with pytest.raises(u4.BaselineStop,match="disappeared"):
        u4.compare(baseline=d,later=later)
    later,_,_=snapshot(tmp_path,later=True,after=True)
    later["first_source_issuer_rows"][0]["ticker"]="NOTINUNIVERSE"
    with pytest.raises(u4.BaselineStop,match="membership"):
        u4.compare(baseline=d,later=later)

def test_no_broker_and_no_fake_prior_first_observation(tmp_path):
    assert u4.ORIGINAL_U3_RUN_ID==40545345749
    assert u4.ORIGINAL_U3_ARTIFACT_ID==12752028069
    assert u4.BROKER_GETS==u4.BROKER_POSTS==u4.BROKER_ORDERS==0
    assert u4.LIVE_ENABLED is False
    assert "https://data.sec.gov/submissions/CIK" in u4.sec.sec_url(
        "0000001000","submissions")
    d,_,_=snapshot(tmp_path)
    with pytest.raises(u4.BaselineStop):
        u4.compare(baseline=d,later=d)
