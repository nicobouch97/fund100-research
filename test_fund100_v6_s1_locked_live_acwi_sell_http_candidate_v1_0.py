"""Zero-network signed seq2, original fractional SELL JSON and fake receipt."""

from copy import deepcopy
from pathlib import Path
import pytest

import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as m
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import test_fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as fixture

ORIGINAL_QTY=fixture.QUANTITY
ORDER_ID="550e8400-e29b-41d4-a716-446655440001"


def signed():
    s,c0,c1=fixture.start()
    transport=fixture.FakeTransports(s)
    fixture.operate(s,c0,c1,transport)
    return {
        "reserved_source":s,"prepost_source":transport.source,
        "genesis_comment":c0,"first_comment":c1,
        "prepost_comment":transport.comment,
        "first_comment_id":fixture.FIRST_COMMENT_ID,
        "first_run_id":fixture.FIRST_RUN_ID,
        "prepost_comment_id":str(fixture.SECOND_COMMENT_ID),
        "prepost_run_id":fixture.SIM_RUN_ID,
        "original_qty":ORIGINAL_QTY,"key":fixture.KEY,
    }


def receipt(status="accepted",qty=ORIGINAL_QTY,filled="0",filled_at=None):
    doc=m.build_exact_sell_payload(original_qty=ORIGINAL_QTY)
    doc.update({
        "id":ORDER_ID,"status":status,"qty":qty,
        "filled_qty":filled,"filled_at":filled_at,
        "notional":None,
    })
    return doc


def test_hmac_original_seq2_and_three_public_comments_structurally_validate():
    doc=m.check_prepost_sources(**signed())
    assert doc["stage"]=="ORIGINAL_SIGNED_PREPOST_AND_PUBLIC_CHAIN_STRUCTURALLY_VALID_LOCKED"
    assert doc["signed_private_sequence"]==2
    assert doc["first_symbol"]=="ACWI"
    assert doc["stable_original_client_order_id"]==cas.CLIENT_IDS["ACWI"]
    assert doc["first_reservation_HMAC_verified"]
    assert doc["prepost_advance_HMAC_verified"]
    assert doc["public_bot_issue_head_chain_verified"]
    assert doc["immutable_rollback_watermark_verified"] is False
    assert doc["fresh_live_broker_source_verified"] is False
    assert doc["live_order_authorized"] is False
    assert doc["broker_orders_submitted"]==0


def test_exact_pure_original_fractional_market_DAY_payload_is_never_sent():
    p=m.build_exact_sell_payload(original_qty=ORIGINAL_QTY)
    assert p=={
        "symbol":"ACWI","qty":ORIGINAL_QTY,"side":"sell",
        "type":"market","time_in_force":"day",
        "extended_hours":False,
        "client_order_id":cas.CLIENT_IDS["ACWI"],
    }
    assert "notional" not in p
    assert "XLE" not in cas.LEGACY
    assert m.TRANSPORT_RELEASED is False


def test_signed_source_and_simulated_accepted_receipt_only_return_redacted_result():
    x=m.offline_review_signed_prepost_and_receipt(
        signed_sources=signed(),simulated_receipt=receipt())
    assert x["status"]=="PURE_SIGNED_PREPOST_AND_FAKE_BROKER_RECEIPT_VERIFIED_NO_SEND"
    assert x["signed_sequence"]==2
    assert x["original_symbol"]=="ACWI"
    assert x["receipt_stage"]=="POST_ACCEPTED_ACTIVE_OR_PARTIAL_HOLD_NO_RETRY"
    assert x["independent_real_broker_receipt_verified"] is False
    assert x["real_live_order_authorized"] is False
    assert x["actual_broker_POSTs"]==0
    assert x["payload"] is None
    assert x["original_quantity_or_receipt_exported"] is False


def test_even_completely_fake_unlocked_flags_cannot_send_a_live_order(monkeypatch):
    monkeypatch.setattr(m,"TRANSPORT_RELEASED",True)
    monkeypatch.setattr(m,"PUBLIC_EXECUTION_ENABLED",True)
    monkeypatch.setattr(m,"SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT",True)
    class TrappedTransport:
        def __call__(self,*args,**kwargs):
            raise AssertionError("NO BROKER NETWORK METHOD MAY BE CALLED")
    with pytest.raises(m.LockedSellStop,match="NOT approved"):
        m.submit_live_original_acwi_sell(
            original_qty=ORIGINAL_QTY,api_key="fake-not-secret",
            api_secret="fake-not-secret",signed_sources=signed(),
            transport=TrappedTransport())


@pytest.mark.parametrize("flag",[
    "TRANSPORT_RELEASED","PUBLIC_EXECUTION_ENABLED",
    "SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT",
])
def test_any_one_missing_release_lock_is_an_immediate_stop(monkeypatch,flag):
    monkeypatch.setattr(m,"TRANSPORT_RELEASED",True)
    monkeypatch.setattr(m,"PUBLIC_EXECUTION_ENABLED",True)
    monkeypatch.setattr(m,"SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT",True)
    monkeypatch.setattr(m,flag,False)
    with pytest.raises(m.LockedSellStop,match="HARD LOCKED"):
        m.submit_live_original_acwi_sell(
            original_qty=ORIGINAL_QTY,api_key="fake",
            api_secret="fake",signed_sources=signed())


def test_fake_complete_fill_does_not_prove_account_flat_or_cash_settled():
    x=m.offline_review_signed_prepost_and_receipt(
        signed_sources=signed(),
        simulated_receipt=receipt("filled",filled=ORIGINAL_QTY,
                                  filled_at="2026-10-21T18:00:00Z"))
    assert x["receipt_stage"]=="POST_ACCEPTED_FILLED_RECEIPT_NEEDS_POSITION_AND_ACTIVITY_PROOF"
    assert not x["independent_real_broker_receipt_verified"]


@pytest.mark.parametrize("status",[
    "accepted","pending_new","new","partially_filled","pending_cancel",
    "stopped","done_for_day","calculated",
])
def test_fake_active_status_never_implies_resubmission_permission(status):
    x=m._validate_receipt(receipt(status),original_qty=ORIGINAL_QTY)
    assert x["stage"]=="POST_ACCEPTED_ACTIVE_OR_PARTIAL_HOLD_NO_RETRY"
    assert x["resubmission_permitted"] is False


@pytest.mark.parametrize("status",[
    "rejected","canceled","expired","held","replaced","pending_replace",
    "suspended","weird","",
])
def test_fake_terminal_ambiguous_and_unknown_orders_hold(status):
    with pytest.raises(m.LockedSellStop):
        m._validate_receipt(receipt(status),original_qty=ORIGINAL_QTY)


@pytest.mark.parametrize("wrong",[
    {"symbol":"XLE"},{"side":"buy"},{"client_order_id":"modified"},
    {"qty":"0.123456788"},{"type":"limit"},{"time_in_force":"gtc"},
    {"notional":"10"},{"id":"fake"},{"filled_qty":"999"},
    {"status":"filled","filled_at":None,"filled_qty":ORIGINAL_QTY},
    {"status":"filled","filled_at":"2026-10-21T18:00:00Z","filled_qty":"0"},
])
def test_broken_broker_order_receipts_cannot_claim_a_safe_exit(wrong):
    doc=receipt()
    doc.update(wrong)
    with pytest.raises(m.LockedSellStop):
        m._validate_receipt(doc,original_qty=ORIGINAL_QTY)


@pytest.mark.parametrize("where,change",[
    ("reserved_source",{"sha":"f"*40}),
    ("prepost_source",{"sha":"f"*40}),
    ("first_comment",{"body":"tampered"}),
    ("prepost_comment",{"body":"tampered"}),
    ("genesis_comment",{"id":100}),
    ("prepost_comment",{"user":{"login":"attacker"}}),
    ("prepost_comment",{"issue_url":"https://example.org/evil"}),
])
def test_no_fake_receipt_proof_with_tampered_original_signed_state(where,change):
    args=signed()
    args[where].update(change)
    with pytest.raises(m.LockedSellStop):
        m.check_prepost_sources(**args)


@pytest.mark.parametrize("qty",["1e-5","0","0.0000000001","NaN","-1"])
def test_unsupported_original_fractional_qty_not_an_executable_shape(qty):
    with pytest.raises(Exception):
        m.build_exact_sell_payload(original_qty=qty)


def test_synthetic_source_is_not_broker_authentication_and_has_no_network_path():
    code=Path(m.__file__).read_text()
    assert "def main(" not in code
    assert "if __name__" not in code
    assert "os.getenv(" not in code
    assert "Request(" not in code
    assert "urlopen(" not in code
    assert "from urllib.request" not in code
    assert "ALPACA_LIVE_KEY" not in code
    assert "ALPACA_LIVE_SECRET" not in code
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in code
    assert m.NO_MAIN_OR_WORKFLOW
    assert m.TRANSPORT_RELEASED is False
    assert m.PUBLIC_EXECUTION_ENABLED is False
    assert m.SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT is False
    assert m.AUTOMATIC_RETRY_RELEASED is False
