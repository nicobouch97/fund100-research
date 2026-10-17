"""C7 original CME document-header and full CL futures line integrity tests.

The tests construct synthetic *text fixtures*, not authentic market quotes.
The real source workflow separately downloads exact CME PDF raw bytes.
"""
from __future__ import annotations

import pytest
import fund100_cme_section61_original_c7_v1_0 as c7

ACQ="2026-10-17T13:10:00Z"
MONTHS=["NOV26","DEC26","JAN27","FEB27","MAR27","APR27","MAY27",
        "JUN27","JUL27","AUG27","SEP27","OCT27","NOV27","DEC27"]


def page(*,status="FINAL",date="Thu, Oct 08, 2026",name="NYMEX CRUDE OIL (PHYSICAL)",
         months=None,oi_offset=0,replace_rows=None):
    months=MONTHS if months is None else months
    header=(f"ENERGY FUTURES PRODUCTS\n2026 DAILY INFORMATION BULLETIN\n"
            f"CME Group, Inc.\nPG61 BULLETIN # 194@ {date} PG61\n"
            f"{status}\nPRICE INDICATOR KEY\nSETT. PRICE\n")
    contracts=[]
    for i,t in enumerate(months):
        # Matches the original pdf: open high/low [SETTLEMENT] +/- point
        # [Globex volume] [PNT/PIT vol] [OPEN INTEREST] change.
        contracts.append(f" {t} 89.00 93.20 /88.77 {91.49-i*.52:.2f} + 0.32 33152 1089 {10000+37*i} + 25")
    if replace_rows is not None:
        contracts=replace_rows
    total=sum(10000+37*i for i in range(len(months)))+oi_offset
    return (header+f" CL FUT {name}\n"+"\n".join(contracts)+"\n"
            +f" TOTAL CL FUT 991200 99001 {total} - 9655\n"
            +" HO FUT NYMEX HEATING OIL (PHYSICAL)\n")


def test_valid_final_bulletin_maturity_settlements_open_interest_sum():
    original=page()
    report=c7.parse_first_page(original,acquired_utc=ACQ)
    assert report["status"]=="OFFICIAL_FINAL_CME_CONTRACT_CURVE_SOURCE_ONLY"
    assert report["source_product_code"]=="CL"
    assert report["source_original_status"]=="FINAL"
    assert report["original_trade_date"]=="2026-10-08"
    assert report["contract_month_count"]==14
    assert report["sum_verified"]
    assert report["source_contract_months"][0]["contract_month"]=="NOV26"
    assert report["source_contract_months"][0]["delivery_month"]=="2026-11"
    assert report["source_contract_months"][1]["delivery_month"]=="2026-12"
    assert report["source_contract_months"][0]["open_interest_contracts"]==10000
    assert report["front_next_month_spread_usd_per_barrel"]==pytest.approx(.52)
    assert report["front_next_curve_shape"]=="BACKWARDATION"
    assert report["stale_for_current_market_read"] is True
    assert not report["exact_original_cme_publication_utc_verified"]
    assert not report["realized_roll_yield_measured"]
    assert report["broker_orders"]==0
    assert not report["live_authorized"] and not report["paper_authorized"]


def test_preliminary_and_undated_rejected():
    with pytest.raises(c7.CMEStop,match="PRELIMINARY"):
        c7.parse_first_page(page(status="PRELIMINARY"),acquired_utc=ACQ)
    with pytest.raises(c7.CMEStop,match="FINAL"):
        c7.parse_first_page(page(status="DRAFT"),acquired_utc=ACQ)
    with pytest.raises(c7.CMEStop,match="Undated"):
        c7.parse_first_page(page().replace("BULLETIN # 194@", "BULLETIN WRONG"),acquired_utc=ACQ)


def test_source_mismatch_and_open_interest_reconciliation_fails_closed():
    with pytest.raises(c7.CMEStop,match="product|block"):
        c7.parse_first_page(page(name="CRYPTO FUTURES"),acquired_utc=ACQ)
    with pytest.raises(c7.CMEStop,match="OI total inconsistent"):
        c7.parse_first_page(page(oi_offset=1),acquired_utc=ACQ)


def test_market_date_and_capture_clock_not_guessed():
    with pytest.raises(c7.CMEStop,match="inconsistent"):
        c7.parse_first_page(page(date="Tue, Oct 08, 2026"),acquired_utc=ACQ)
    with pytest.raises(c7.CMEStop,match="future or stale"):
        c7.parse_first_page(page(),acquired_utc="2026-10-06T08:10:00Z")
    with pytest.raises(c7.CMEStop,match="future or stale"):
        c7.parse_first_page(page(),acquired_utc="2026-10-28T08:10:00Z")
    with pytest.raises(c7.CMEStop,match="canonical"):
        c7.parse_first_page(page(),acquired_utc="2026-10-17 13:00:00")


def test_missing_near_month_or_duplicate_maturity_not_reassigned():
    with pytest.raises(c7.CMEStop,match="missing immediate"):
        c7.parse_first_page(page(months=["NOV26","JAN27",*MONTHS[3:]]),acquired_utc=ACQ)
    with pytest.raises(c7.CMEStop,match="Duplicate"):
        c7.parse_first_page(page(months=[*MONTHS[:4],"FEB27",*MONTHS[4:]]),acquired_utc=ACQ)
    with pytest.raises(c7.CMEStop,match="Not enough"):
        c7.parse_first_page(page(months=MONTHS[:5]),acquired_utc=ACQ)


def test_price_low_or_no_quote_rejected():
    rows=page().splitlines()
    corrupted=[("NOV26 --- --- /--- ---- + 0.32 33152 1089 10000 + 25" if "NOV26 " in x else x) for x in rows]
    with pytest.raises(c7.CMEStop,match="Unparseable"):
        c7.parse_first_page("\n".join(corrupted),acquired_utc=ACQ)


def test_future_delivery_calendar_and_oi_change_distinct():
    assert c7.month_number("DEC26")-c7.month_number("NOV26")==1
    assert c7.month_number("JAN27")-c7.month_number("DEC26")==1
    with pytest.raises(c7.CMEStop,match="delivery month"):
        c7.month_number("DEC-26")


def test_non_pdf_fake_source_and_pdf_that_cannot_be_read():
    for raw in (b"",b"SPOOF %PDF-"+b"0"*10000,b"%PDF-"+b"0"*5):
        with pytest.raises(c7.CMEStop,match="PDF bytes"):
            c7.extract_first_page_pdf(raw)

def test_actual_multicolumn_cme_bulletin_header_is_accepted_only_if_final():
    line="PG61 BULLETIN # 194@ Thu, Oct 08, 2026 PG61"
    real_layout="PG61 BULLETIN # 194@                  ENERGY FUTURES PRODUCTS                Thu, Oct 08, 2026 PG61"
    report=c7.parse_first_page(page().replace(line,real_layout),acquired_utc=ACQ)
    assert report["original_trade_date"]=="2026-10-08"
    assert report["original_bulletin_id"]==194
    with pytest.raises(c7.CMEStop,match="PRELIMINARY"):
        c7.parse_first_page(page(status="PRELIMINARY").replace(line,real_layout),acquired_utc=ACQ)
