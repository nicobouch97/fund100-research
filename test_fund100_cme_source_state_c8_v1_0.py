"""C8 original CME raw-body/final/draft rejection provenance regression tests.

PDF bytes are synthetic headers; ALL market values are artificial and
never become an exchange source. Tests forbid broker orders and publication
time fabrication.
"""
from __future__ import annotations

from hashlib import sha256
import json
from unittest.mock import patch
import pytest

import fund100_cme_source_state_c8_v1_0 as c8
import fund100_cme_section61_original_c7_v1_0 as c7
from test_fund100_cme_section61_original_c7_v1_0 import page

AT="2026-10-18T12:55:00Z"
FAKE=b"%PDF-"+b"not an actual CME PDF; synthetic test only."*280


def test_preliminary_original_has_hash_date_but_no_market_quotes(monkeypatch):
    real_page=page(status="PRELIMINARY",date="Fri, Oct 16, 2026")
    real_page=real_page.replace(
        "PG61 BULLETIN # 194@ Fri, Oct 16, 2026 PG61",
        "PG61 BULLETIN # 200@           ENERGY FUTURES PRODUCTS             Fri, Oct 16, 2026 PG61")
    monkeypatch.setattr(c7,"extract_first_page_pdf",lambda raw:real_page)
    result=c8.evaluate_raw(FAKE,acquired_utc=AT)
    assert result["source_admission_status"]=="REJECT_PRELIMINARY"
    assert result["printed_original_status"]=="PRELIMINARY"
    assert result["printed_original_trade_date"]=="2026-10-16"
    assert result["printed_bulletin_id"]==200
    assert result["original_pdf_sha256"]==sha256(FAKE).hexdigest()
    assert result["original_pdf_byte_count"]==len(FAKE)
    assert not result["original_pdf_archived"]
    assert not result["admitted_contract_curve"]
    assert not result["futures_settlement_values_present_in_report"]
    assert "settlement_usd_per_barrel" not in json.dumps(result)
    assert result["broker_orders"]==0 and not result["operator_authorized_etf_liquidation"]
    assert not result["live_authorized"] and not result["paper_authorized"]


def test_original_final_is_independently_accepted_only_on_full_c7_revalidation(monkeypatch):
    fake_page=page()
    monkeypatch.setattr(c7,"extract_first_page_pdf",lambda raw:fake_page)
    result=c8.evaluate_raw(FAKE,acquired_utc=AT)
    assert result["source_admission_status"]=="ACCEPT_FINAL_SOURCE_ONLY"
    assert result["original_pdf_archived"]
    assert result["printed_original_trade_date"]=="2026-10-08"
    assert result["admitted_final_curve"]["contract_month_count"]==14
    assert result["admitted_final_curve"]["original_pdf_sha256"]==result["original_pdf_sha256"]
    assert result["one_date_is_not_historical_earned_carry"]
    assert not result["independent_historical_settlement_return_series"]
    assert not result["live_authorized"] and not result["trading_authorized"]


def test_forged_final_invalid_full_original_curve_remains_rejected(monkeypatch):
    page_with_mismatch=page(oi_offset=9999)
    monkeypatch.setattr(c7,"extract_first_page_pdf",lambda raw:page_with_mismatch)
    result=c8.evaluate_raw(FAKE,acquired_utc=AT)
    assert result["source_admission_status"]=="REJECT_FINAL_SOURCE_INVALID"
    assert result["printed_original_status"]=="FINAL"
    assert not result["admitted_contract_curve"]
    assert not result["original_pdf_archived"]
    assert "admitted_final_curve" not in result


@pytest.mark.parametrize("bad",[
    b"", b"random no pdf"*1000, b"%PDF-" + b"a"*4, b"%PDF-" + b"b"*(c7.MAX_PDF+10),
])
def test_source_body_invalid_refused_and_no_fake_curve(bad):
    result=c8.evaluate_raw(bad,acquired_utc=AT)
    assert result["source_admission_status"]=="REJECT_INVALID_SOURCE"
    assert not result["admitted_contract_curve"]
    assert result["original_pdf_archived"] is False
    assert result["broker_orders"]==0


def test_status_unknown_or_no_bulletin_does_not_infer_final(monkeypatch):
    fake_page=page().replace("BULLETIN # 194@","BULLETIN # BAD@")
    monkeypatch.setattr(c7,"extract_first_page_pdf",lambda raw:fake_page)
    result=c8.evaluate_raw(FAKE,acquired_utc=AT)
    assert result["source_admission_status"]=="REJECT_INVALID_SOURCE"
    assert result["printed_original_trade_date"] is None
    assert not result["admitted_contract_curve"]


def test_network_failure_emits_truthful_metadata_with_no_original_hash():
    result=c8.no_source(acquired_utc=AT,reason="Network unavailable.")
    assert result["source_admission_status"]=="REJECT_SOURCE_UNAVAILABLE"
    assert result["original_pdf_sha256"] is None
    assert result["original_body_received"] is False
    assert result["original_pdf_archived"] is False
    assert "admitted_final_curve" not in result
    assert not result["operator_authorized_new_futures"]


def test_acquisition_clock_must_be_real_utc():
    with pytest.raises(c7.CMEStop):
        c8.no_source(acquired_utc="2026/10/18",reason="Synthetic network failure.")


def test_actual_fetch_requests_original_url_and_cache_bypass(monkeypatch):
    seen=[]
    class MockResult:
        status=200
        def geturl(self):
            return c8.SOURCE
        def read(self,n):
            assert n==c8.READ_LIMIT+1
            return FAKE
        def __enter__(self):
            return self
        def __exit__(self,*exc):
            pass
    def stub(req,timeout):
        seen.append((req.full_url,req.get_header("Cache-control"),req.get_header("Pragma"),timeout))
        return MockResult()
    monkeypatch.setattr(c8,"urlopen",stub)
    assert c8.one_public_request()==FAKE
    assert seen==[(c8.SOURCE,"no-cache, no-store, max-age=0","no-cache",30)]


def test_redirect_source_refused(monkeypatch):
    class Result:
        status=200
        def geturl(self):
            return "https://malicious.example/fake.pdf"
        def __enter__(self):
            return self
        def __exit__(self,*exc):
            pass
    monkeypatch.setattr(c8,"urlopen",lambda *args,**kwargs:Result())
    with pytest.raises(c7.CMEStop,match="redirected"):
        c8.one_public_request()
