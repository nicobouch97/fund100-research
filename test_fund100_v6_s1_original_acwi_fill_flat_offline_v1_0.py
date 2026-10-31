"""Mock-only first ACWI signed PRE-POST, receipt FILL, flat tests."""
from base64 import b64encode, b64decode
from copy import deepcopy
import json
from pathlib import Path

import pytest

import fund100_v6_s1_original_acwi_fill_flat_offline_v1_0 as m
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_one_shot_private_empty_genesis_bootstrap_v1_0 as boot
import fund100_v6_s1_first_private_head_external_witness_offline_v1_0 as first
import fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as second
import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as pure

KEY=bytes.fromhex("0123456789abcdef"*4)
OID="550e8400-e29b-41d4-a716-446655440001"
OTHER_ID="550e8400-e29b-41d4-a716-446655440002"
FIRST_ID="1234567890"
SECOND_ID="2345678901"
FIRST_RUN="9876543210"
SECOND_RUN="9876543211"
START="2026-10-22T13:30:00Z"
FILL1="2026-10-22T13:31:00Z"
FILL2="2026-10-22T13:31:30Z"
COMPLETED="2026-10-22T13:32:00Z"
OBSERVED="2026-10-22T13:33:00Z"


def contents(raw):
    return {"type":"file","path":cas.STATE_PATH,
            "sha":cas.blob_sha(raw),"encoding":"base64",
            "content":b64encode(raw).decode("ascii")}


def signed_sources():
    w=witness.verify()
    original=m._original_quantities()
    qty=format(original["ACWI"],"f")
    init=contents(cas.genesis(
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],key=KEY))
    r=cas.plan_reserve(init,symbol="ACWI",original_qty=qty,
                       private_genesis=w["original_public_genesis_nonce"],
                       account_binding_sha256=w["original_live_account_binding_sha256"],key=KEY)
    reserved=contents(b64decode(r["commit"]["content_base64"]))
    p=cas.plan_possible_post(reserved,symbol="ACWI",original_qty=qty,
                             private_genesis=w["original_public_genesis_nonce"],
                             account_binding_sha256=w["original_live_account_binding_sha256"],key=KEY)
    post=contents(b64decode(p["commit"]["content_base64"]))
    issue=second.ORIGINAL_ISSUE_URL
    bot={"login":second.EXPECTED_BOT}
    c0={"id":int(second.ORIGINAL_GENESIS_COMMENT),
        "issue_url":issue,"user":bot,
        "body":boot.public_comment(
            digest=boot.public_head_commitment(
                nonce=w["original_public_genesis_nonce"],
                private_blob_sha=init["sha"]),
            run_url="https://github.com/nicobouch97/fund100-research/actions/runs/39637082911")}
    c1={"id":int(FIRST_ID),"issue_url":issue,"user":bot,
        "body":first.first_next_comment(
            original_nonce=w["original_public_genesis_nonce"],
            old_private_sha=init["sha"],new_private_sha=reserved["sha"],
            run_id=FIRST_RUN)}
    c2={"id":int(SECOND_ID),"issue_url":issue,"user":bot,
        "body":second.second_head_comment(
            nonce=w["original_public_genesis_nonce"],
            old_blob_sha=reserved["sha"],new_blob_sha=post["sha"],
            first_comment_id=FIRST_ID,simulation_run_id=SECOND_RUN)}
    return {
        "reserved_source":reserved,"prepost_source":post,
        "genesis_comment":c0,"first_comment":c1,
        "prepost_comment":c2,"first_comment_id":FIRST_ID,
        "first_run_id":FIRST_RUN,"prepost_comment_id":SECOND_ID,
        "prepost_run_id":SECOND_RUN,"original_qty":qty,"key":KEY}


def base():
    source=signed_sources()
    qty=source["original_qty"]
    receipt=pure.build_exact_sell_payload(original_qty=qty)
    receipt.update({"id":OID,"status":"filled","filled_qty":qty,
                    "filled_at":COMPLETED,"filled_avg_price":"1","notional":None})
    fill={"id":"acwi-fill::1","activity_type":"FILL",
          "order_id":OID,"transaction_time":FILL1,
          "symbol":"ACWI","side":"sell","type":"fill",
          "qty":qty,"cum_qty":qty,"leaves_qty":"0","price":"1"}
    original=m._original_quantities()
    positions=[{"symbol":s,"qty":format(original[s],"f")} for s in m.RETAIN]
    return {
        "signed_prepost_sources":source,
        "closed_receipt":receipt,"fill_pages":[[fill]],
        "post_positions":positions,"open_orders":[],
        "observed_at_utc":OBSERVED,"fill_query_after_utc":START}


def run(**changed):
    doc=base()
    doc.update(changed)
    return m.assess(**doc)


def test_valid_original_first_sell_is_only_a_structural_synthetic_proof():
    v=run()
    assert v["stage"]=="SYNTHETIC_ACWI_SELL_RECEIPT_FILLS_AND_FLAT_STRUCTURALLY_MATCH"
    assert v["mode"]==m.MODE
    assert v["first_symbol"]=="ACWI"
    assert v["signed_original_prepost_HMAC_and_public_chain_verified"]
    assert v["broker_receipt_to_complete_FILLS_structurally_linked"]
    assert v["receipt_average_price_matches_FILLS"]
    assert v["original_ACWI_absent_in_post_positions"]
    assert v["EEM_XLE_XLV_retained_in_original_quantities"]
    assert v["all_hypothetical_fill_pages_complete"]
    assert not v["real_broker_origin_authenticated_by_this_module"]
    assert not v["latest_durable_private_head_independently_anchored"]
    assert not v["actual_sale_proceeds_settled"]
    assert not v["next_legacy_sell_authorized"]
    assert not v["live_buy_authorized"]
    assert v["private_Git_writes"]==v["broker_GETs"]==v["broker_POSTs"]==0
    assert v["private_order_id"] is v["original_quantities"] is v["fill_prices"] is None


def test_two_original_partial_and_final_fill_activities_sum_exactly():
    a=base()
    from decimal import Decimal
    qty= m._original_quantities()["ACWI"]
    half=format(qty/2,"f")
    a["fill_pages"][0][0].update({
        "qty":half,"cum_qty":half,"leaves_qty":half,"type":"partial_fill"})
    last=deepcopy(a["fill_pages"][0][0])
    last.update({"id":"acwi-fill::2","transaction_time":FILL2,
                 "type":"fill","qty":half,
                 "cum_qty":format(qty,"f"),"leaves_qty":"0"})
    a["fill_pages"][0].append(last)
    assert m.assess(**a)["broker_receipt_to_complete_FILLS_structurally_linked"]


@pytest.mark.parametrize("bad",[None,"NaN","Infinity","0","-1","1.02",2])
def test_filled_receipt_average_price_must_be_present_finite_and_match_fills(bad):
    a=base()
    a["closed_receipt"]["filled_avg_price"]=bad
    with pytest.raises(m.FillFlatStop,match="average price"):
        m.assess(**a)


def test_weighted_partial_fill_prices_must_match_receipt_average():
    from decimal import Decimal
    a=base()
    qty=Decimal(a["signed_prepost_sources"]["original_qty"])
    half=format(qty/2,"f")
    first_fill=a["fill_pages"][0][0]
    first_fill.update(qty=half,cum_qty=half,leaves_qty=half,
                      type="partial_fill",price="1")
    second_fill=deepcopy(first_fill)
    second_fill.update(id="acwi-fill::2",transaction_time=FILL2,
                       qty=half,cum_qty=format(qty,"f"),leaves_qty="0",
                       type="fill",price="2")
    a["fill_pages"][0].append(second_fill)
    a["closed_receipt"]["filled_avg_price"]="1.50"
    assert m.assess(**a)["receipt_average_price_matches_FILLS"] is True
    a["closed_receipt"]["filled_avg_price"]="1.51"
    with pytest.raises(m.FillFlatStop,match="disagrees with FILL"):
        m.assess(**a)


def test_broker_cent_rounding_tolerance_not_permission_to_ignore_price():
    a=base()
    a["closed_receipt"]["filled_avg_price"]="1.00"
    a["fill_pages"][0][0]["price"]="1.004"
    assert m.assess(**a)["receipt_average_price_matches_FILLS"] is True
    a["fill_pages"][0][0]["price"]="1.006"
    with pytest.raises(m.FillFlatStop,match="disagrees with FILL"):
        m.assess(**a)


def test_first_full_page_requires_second_page_even_if_one_order_filled():
    a=base()
    target=a["fill_pages"][0][0]
    fillers=[]
    for n in range(100):
        fillers.append({
            "id":f"prior-buy::{n}","activity_type":"FILL",
            "order_id":OTHER_ID,"transaction_time":START,
            "symbol":"ACWI","side":"buy","type":"fill",
            "qty":"0.01","cum_qty":"0.01","leaves_qty":"0",
            "price":"1",
        })
    a["fill_pages"]=[fillers,[target]]
    assert m.assess(**a)["all_hypothetical_fill_pages_complete"]
    a["fill_pages"]=[fillers]
    with pytest.raises(m.FillFlatStop,match="Last FILL page full"):
        m.assess(**a)
    a["fill_pages"]=[fillers[:99],[target]]
    with pytest.raises(m.FillFlatStop,match="pagination has a gap"):
        m.assess(**a)


@pytest.mark.parametrize("field,bad",[
    ("status","partially_filled"),
    ("status","accepted"),
    ("symbol","XLE"),
    ("side","buy"),
    ("client_order_id","wrong"),
    ("qty","0.999999999"),
    ("filled_qty","0"),
    ("type","limit"),
    ("time_in_force","gtc"),
    ("filled_at",None),
    ("id","not-a-uuid"),
    ("notional","50"),
])
def test_fake_broker_closed_receipt_cannot_overrule_signed_intent(field,bad):
    a=base()
    a["closed_receipt"][field]=bad
    with pytest.raises(m.FillFlatStop):
        m.assess(**a)


@pytest.mark.parametrize("field,bad",[
    ("activity_type","DIV"),
    ("id",""),
    ("order_id","bad"),
    ("transaction_time","2026-10-23T12:00:00Z"),
    ("qty","0"),
    ("qty","NaN"),
    ("cum_qty","0.1"),
    ("leaves_qty","0.1"),
    ("price","0"),
    ("type","partial_fill"),
    ("symbol","EEM"),
    ("side","buy"),
])
def test_fake_fill_activity_identity_quantity_or_type_mismatch_stops(field,bad):
    a=base()
    a["fill_pages"][0][0][field]=bad
    with pytest.raises(m.FillFlatStop):
        m.assess(**a)


def test_repeated_activity_same_id_or_extra_after_final_rejected():
    a=base()
    a["fill_pages"][0].append(deepcopy(a["fill_pages"][0][0]))
    with pytest.raises(m.FillFlatStop):
        m.assess(**a)
    a=base()
    extra=deepcopy(a["fill_pages"][0][0])
    extra["id"]="acwi-fill::2"
    extra["transaction_time"]=FILL2
    a["fill_pages"][0].append(extra)
    with pytest.raises(m.FillFlatStop):
        m.assess(**a)


def test_wrong_order_id_does_not_sum_into_acwi_receipt():
    a=base()
    a["fill_pages"][0][0]["order_id"]=OTHER_ID
    with pytest.raises(m.FillFlatStop):
        m.assess(**a)



@pytest.mark.parametrize("when",[FILL1,FILL2,"2026-10-22T13:32:30Z"])
def test_unrelated_buy_during_or_after_first_acwi_fill_cannot_pass_reconciliation(when):
    a=base()
    other=deepcopy(a["fill_pages"][0][0])
    other.update({"id":"foreign-buy","order_id":OTHER_ID,
                  "symbol":"XLK","side":"buy","transaction_time":when})
    a["fill_pages"][0].append(other)
    a["fill_pages"][0].sort(key=lambda row:row["transaction_time"])
    with pytest.raises(m.FillFlatStop,match="Other BUY activity"):
        m.assess(**a)


def test_earlier_historical_buy_does_not_invalidate_isolated_acwi_execution():
    a=base()
    other=deepcopy(a["fill_pages"][0][0])
    other.update({"id":"earlier-buy","order_id":OTHER_ID,
                  "symbol":"EEM","side":"buy","transaction_time":START})
    a["fill_pages"][0].insert(0,other)
    assert m.assess(**a)["broker_receipt_to_complete_FILLS_structurally_linked"]


def test_unrelated_sell_activity_is_not_silent_migration_of_EEM():
    a=base()
    other=deepcopy(a["fill_pages"][0][0])
    other.update({"id":"unrelated","order_id":OTHER_ID,
                  "symbol":"EEM","transaction_time":START})
    a["fill_pages"][0].insert(0,other)
    with pytest.raises(m.FillFlatStop,match="Other SELL"):
        m.assess(**a)


@pytest.mark.parametrize("change",[
    ("post_positions",[]),
    ("post_positions",[{"symbol":"ACWI","qty":"1"}]),
    ("post_positions",[{"symbol":"EEM","qty":"0"}]),
    ("open_orders",[{"symbol":"ACWI","status":"new"}]),
])
def test_cannot_claim_first_order_flat_and_zero_open_orders(change):
    with pytest.raises(m.FillFlatStop):
        run(**{change[0]:change[1]})


def test_missing_xle_or_modified_original_positions_rejected():
    a=base()
    a["post_positions"][1]["symbol"]="XLK"
    with pytest.raises(m.FillFlatStop):
        m.assess(**a)
    a=base()
    a["post_positions"][0]["qty"]="999"
    with pytest.raises(m.FillFlatStop):
        m.assess(**a)


def test_query_window_and_observation_chronology_fails_closed():
    for changed in [
        {"fill_query_after_utc":"2026-10-22T13:32:01Z"},
        {"observed_at_utc":COMPLETED},
        {"observed_at_utc":"bad"},
        {"fill_query_after_utc":"2026-10-22T13:35:00Z"},
    ]:
        with pytest.raises(m.FillFlatStop):
            run(**changed)


def test_completed_original_acwi_inventory_exit_above_65_is_reconciled_not_a_new_order():
    from decimal import Decimal
    a=base()
    qty=Decimal(a["signed_prepost_sources"]["original_qty"])
    # This SELL consumes the entire original bound holding. Its proceeds
    # may exceed the new BUY order limit without granting fresh exposure.
    price=(Decimal("80")/qty).quantize(Decimal("0.01"))
    a["fill_pages"][0][0]["price"]=format(price,"f")
    a["closed_receipt"]["filled_avg_price"]=format(price,"f")
    assert qty*price>Decimal("65")
    report=m.assess(**a)
    assert report["stage"]=="SYNTHETIC_ACWI_SELL_RECEIPT_FILLS_AND_FLAT_STRUCTURALLY_MATCH"
    assert report["actual_sale_proceeds_settled"] is False
    assert report["next_legacy_sell_authorized"] is False
    assert report["live_buy_authorized"] is False
    assert report["broker_POSTs"]==report["private_Git_writes"]==0


def test_fill_price_and_qty_still_require_positive_realistic_decimal_evidence():
    for price in ("0","NaN","-1"):
        a=base()
        a["fill_pages"][0][0]["price"]=price
        with pytest.raises(m.FillFlatStop):
            m.assess(**a)


@pytest.mark.parametrize("which,change",[
    ("reserved_source",{"sha":"0"*40}),
    ("prepost_source",{"sha":"0"*40}),
    ("genesis_comment",{"body":"fake"}),
    ("first_comment",{"body":"fake"}),
    ("prepost_comment",{"body":"fake"}),
    ("prepost_comment",{"user":{"login":"intruder"}}),
])
def test_bad_original_HMAC_git_sha_or_external_public_witness_stops(which,change):
    a=base()
    a["signed_prepost_sources"][which].update(change)
    with pytest.raises(m.FillFlatStop,match="signed pre-POST"):
        m.assess(**a)


def test_historical_wrong_qty_cannot_be_supplied_by_fake_signed_data():
    a=base()
    a["signed_prepost_sources"]["original_qty"]="0.999999999"
    with pytest.raises(m.FillFlatStop,match="Original fractional"):
        m.assess(**a)


def test_only_original_pinned_stopped_contract_and_zero_network_capabilities():
    assert m.ORIGINAL_FULL_INVENTORY_EXIT_NOT_SUBJECT_TO_NEW_ORDER_CAP is True
    assert "MAX_FIRST_ORDER_GROSS_USD" not in Path(m.__file__).read_text()
    assert not m.LIVE_BROKER_REQUESTS_RELEASED
    assert not m.PRIVATE_LEDGER_ADVANCES_RELEASED
    assert not m.NEXT_SELL_OR_BUY_RELEASED
    source=Path(m.__file__).read_text()
    for forbidden in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                      "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
                      "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
                      "Request(","urlopen(","requests.post(",
                      "method=\"POST\"","/v2/orders","def main("):
        assert forbidden not in source
