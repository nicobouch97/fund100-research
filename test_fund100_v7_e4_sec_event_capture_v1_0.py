"""V7-E4 offline official SEC capture fixtures. Never call external SEC."""
from datetime import datetime
import json
from pathlib import Path
import pytest

import fund100_v7_e4_sec_event_capture_v1_0 as e4
import fund100_stock_sec_source_p4b_v1_0 as p4b

FAKE_AGENT="Fixture Offline tests@research-fixture.org"

def snapshot():
    cohort=p4b.read_cohort()
    def loader(url,agent):
        assert agent==FAKE_AGENT and url.startswith("https://data.sec.gov/submissions/CIK")
        cik=url.split("CIK")[1].split(".json")[0]
        assert cik in {r["cik_10_digit"] for r in cohort}
        return json.dumps({"cik":int(cik),"filings":{"recent":{
            "form":["8-K","8-K/A","8-K","10-Q"],
            "accessionNumber":[f"{cik}-26-000001",f"{cik}-26-000002",f"{cik}-26-000003",f"{cik}-26-000004"],
            "filingDate":["2026-10-21","2026-10-21","2026-10-14","2026-10-21"],
            "items":["2.02,9.01","2.02","2.02","2.02"]
        }}}).encode()
    now=lambda:"2026-10-22T09:15:00Z"
    return e4.collect(user_agent=FAKE_AGENT,loader=loader,clock=now)

def test_only_postregistration_original_8k_202_is_research_evidence(tmp_path):
    manifest,files=snapshot()
    assert len(files)==8 and len(manifest["observed_filings_not_necessarily_new_today"])==8
    assert manifest["item_2_02_filings_since_registration_in_current_source"]==8
    assert not manifest["trading_authorized"] and not manifest["live_authorized"]
    assert all(not r["orders_authorized"] for r in manifest["observed_filings_not_necessarily_new_today"])
    for path,raw in files.items():
        dest=tmp_path/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    (tmp_path/"manifest.json").write_text(json.dumps(manifest))
    assert e4.verify(tmp_path)["source_count"]==8

def test_sha_mutation_does_not_become_a_signal(tmp_path):
    manifest,files=snapshot()
    for path,raw in files.items():
        dest=tmp_path/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    (tmp_path/"manifest.json").write_text(json.dumps(manifest))
    first=next(iter(files))
    (tmp_path/first).write_bytes(b'{}')
    with pytest.raises(e4.FeedStop):e4.verify(tmp_path)

def test_future_filing_fails_closed():
    roster=p4b.read_cohort()
    def loader(url,agent):
        cik=url.split("CIK")[1].split(".json")[0]
        return json.dumps({"cik":int(cik),"filings":{"recent":{
            "form":["8-K"],"accessionNumber":["0000000000-26-000001"],
            "filingDate":["2026-10-23"],"items":["2.02"]
        }}}).encode()
    with pytest.raises(Exception,match="Future-dated"):
        e4.collect(user_agent=FAKE_AGENT,loader=loader,
                   clock=lambda:"2026-10-22T09:15:00Z")

def test_missing_real_contact_fails_before_request():
    with pytest.raises(p4b.SecIntakeStop):
        e4.collect(user_agent="Fake Example x@example.com",
                   loader=lambda *args: (_ for _ in ()).throw(AssertionError("must not call")))

def test_no_results_is_allowed_and_never_a_fake_trade():
    def loader(url,agent):
        cik=url.split("CIK")[1].split(".json")[0]
        return json.dumps({"cik":int(cik),"filings":{"recent":{
            "form":[],"accessionNumber":[],"filingDate":[],"items":[]
        }}}).encode()
    obj,_=e4.collect(user_agent=FAKE_AGENT,loader=loader,
                     clock=lambda:"2026-10-22T09:15:00Z")
    assert obj["item_2_02_filings_since_registration_in_current_source"]==0
    assert obj["broker_orders"]==0

def test_snapshot_clock_cannot_finish_before_member_observation():
    n=[0]
    def clock():
        n[0]+=1
        return "2026-10-22T09:15:10Z" if n[0]<9 else "2026-10-22T09:15:00Z"
    def loader(url,agent):
        cik=url.split("CIK")[1].split(".json")[0]
        return json.dumps({"cik":int(cik),"filings":{"recent":{
            "form":[],"accessionNumber":[],"filingDate":[],"items":[]
        }}}).encode()
    with pytest.raises(e4.FeedStop,match="capture end"):
        e4.collect(user_agent=FAKE_AGENT,loader=loader,clock=clock)
