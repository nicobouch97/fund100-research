"""TWTR original Form 8-K proof vs P4Z source ZIP, no invented cash receipts."""
import pytest
import fund100_stock_delisted_sample_p4z_v1_0 as p4z
import fund100_stock_twtr_merger_terminal_p4aa_v1_0 as p

def official(right="54.20",effective="October 27, 2022",
             stop="October 28, 2022"):
    doc="""<!DOCTYPE html><html><body>
UNITED STATES SECURITIES AND EXCHANGE COMMISSION
FORM 8-K CURRENT REPORT
Date of Report (Date of earliest event reported): October 27, 2022
Twitter, Inc.
Delaware 001-36164 20-8913779
Securities registered pursuant to Section 12(b) of the Act:
Common Stock TWTR New York Stock Exchange
Introductory Note
On EVENT_DATE, pursuant to the terms of the Merger Agreement,
Acquisition Sub merged with and into Twitter, with Twitter surviving
and becoming a wholly owned subsidiary.
Pursuant to the terms of the Merger Agreement, each issued and
outstanding share of Twitter's common stock (subject to certain exceptions)
was canceled and converted into the right to receive $MERGER_AMOUNT
in cash, without interest (the "Merger Consideration").
Item 1.01 Entry into a Material Definitive Agreement.
Some instruments have other consideration.
Item 2.01 Completion of Acquisition or Disposition of Assets.
On EVENT_DATE, pursuant to the terms of the Merger Agreement,
the Merger was consummated. Outstanding common stock was converted.
Item 3.01 Notice of Delisting or Failure to Satisfy a Continued Listing Rule
or Standard; Transfer of Listing.
As a result, trading of Twitter's common stock on the NYSE
was suspended prior to the opening of the NYSE on STOP_DATE.
</body></html>"""
    return (doc.replace("EVENT_DATE",effective).replace("MERGER_AMOUNT",right)
            .replace("STOP_DATE",stop).encode("utf-8"))

def sample():
    return {
        "schema":p4z.SCHEMA,
        "original_zip_sha256":p.ORIGINAL_THIRD_PARTY_SAMPLE_SHA256,
        "twtr_last_trading_bar":"2022-10-27",
        "twtr_source_delisting_label":"2022-10-31",
        "twtr_terminal_shareholder_proceeds_usd":None,
        "twtr_post_delisting_total_return":None,
        "four_chosen_names_not_historical_point_in_time_universe":True,
        "broker_gets":0,"broker_posts":0,"broker_orders":0,
        "trading_authorized":False,
        "listings":[
            {"symbol":s,"last_price_date":"2022-10-27" if s=="TWTR" else "2022-12-30",
             "archive_delisting_label":"2022-10-31" if s=="TWTR" else None,
             "daily_source_sha256":"a"*64} for s in ("TSLA","KO","SPY","TWTR")
        ],
    }

def test_official_completion_gives_entitlement_but_no_reusable_cash():
    r=p.reconcile(official(),sample())
    assert r["per_eligible_common_share_merger_entitlement_usd"]=="54.20"
    assert r["share_cancelled_at_completed_merger_not_sold_at_last_bar"]
    assert r["confirmed_no_trading_from"]=="2022-10-28"
    assert r["shareholder_broker_receipt_date_utc"] is None
    assert r["shareholder_settled_cash_available_date_utc"] is None
    assert not r["cash_settlement_or_reinvestment_in_2022_authorized"]
    assert not r["historical_strategy_alpha_test_eligible"]
    assert r["original_v5_live_ceiling_usd"]=="130.30"
    assert r["broker_gets"]==r["broker_posts"]==r["broker_orders"]==0
    assert not r["trading_authorized"]

def test_offer_does_not_prove_completed_event_or_cleared_cash():
    for blob in (
        official(effective="October 26, 2022"),
        official(stop="October 27, 2022"),
        official(right="53.20"),
        official().replace(b"Merger was consummated",b"Merger was proposed"),
        official().replace(b"FORM 8-K",b"FORM 10-Q"),
        official().replace(b"Twitter, Inc.",b"Not Twitter Ltd"),
        official().replace(b"TWTR New York",b"XYZ New York"),
        official().replace(b"001-36164",b"999-99999"),
    ):
        with pytest.raises(p.MergerEvidenceStop):
            p.reconcile(blob,sample())

def test_original_source_security_hash_and_lifecycle_are_required():
    for field,value in (
        ("original_zip_sha256","0"*64),
        ("twtr_last_trading_bar","2022-10-28"),
        ("twtr_terminal_shareholder_proceeds_usd","54.20"),
        ("twtr_post_delisting_total_return","0.0"),
        ("broker_orders",1),
        ("trading_authorized",True)):
        payload=sample()
        payload[field]=value
        with pytest.raises(p.MergerEvidenceStop):
            p.reconcile(official(),payload)
    r=sample()
    r["listings"][3]["daily_source_sha256"]="missing"
    with pytest.raises(p.MergerEvidenceStop):
        p.reconcile(official(),r)

def test_source_must_be_bounded_and_refuse_fake_cash_right():
    with pytest.raises(p.MergerEvidenceStop):
        p.reconcile(b"Form 8-K Twitter 54.20",sample())
    with pytest.raises(p.MergerEvidenceStop):
        p.reconcile(b"x"*(p.MAX_SEC_BYTES+1),sample())
    with pytest.raises(p.MergerEvidenceStop):
        p.reconcile(official().replace(
            b"in cash, without interest",
            b"in stock, without interest"),sample())

def test_no_original_live_or_fake_historical_cash_activation():
    assert p.BROKER_GETS==p.BROKER_POSTS==p.BROKER_ORDERS==0
    assert p.LIVE_AUTHORIZED is False
    assert p.ORIGINAL_SEC_CIK==1418091
    assert p.ORIGINAL_SEC_ACCESSION=="0001193125-22-272772"
    assert p.ORIGINAL_8K_URL.startswith("https://www.sec.gov/Archives/")
