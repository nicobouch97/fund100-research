"""Source-pinned LIVE Alpaca POST code path tested with FAKE transports only."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError,URLError

import pytest

import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as m
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import test_fund100_v6_s1_prepost_one_shot_fake_bridge_v1_0 as fixtures

TEST_KEY="offline-not-real-api-credential-1234"
TEST_SECRET="offline-not-real-alpaca-secret-5678"
ORIGINAL_QTY=fixtures.QUANTITY
ORDER_ID="550e8400-e29b-41d4-a716-446655440001"


def good():
    s,c0,c1=fixtures.start()
    mock=fixtures.FakeTransports(s)
    fixtures.operate(s,c0,c1,mock)
    return {
        "reserved_source":s,"prepost_source":mock.source,
        "genesis_comment":c0,"first_comment":c1,
        "prepost_comment":mock.comment,
        "first_comment_id":fixtures.FIRST_COMMENT_ID,
        "first_run_id":fixtures.FIRST_RUN_ID,
        "prepost_comment_id":str(fixtures.SECOND_COMMENT_ID),
        "prepost_run_id":fixtures.SIM_RUN_ID,
        "original_qty":ORIGINAL_QTY,"key":fixtures.KEY,
    }


def receipt(status="accepted",qty=ORIGINAL_QTY,filled="0",filled_at=None):
    x=m.seller.inspect_sell_shape(symbol="ACWI",original_qty=ORIGINAL_QTY)
    x.update({
        "id":ORDER_ID,"status":status,"qty":qty,
        "filled_qty":filled,"filled_at":filled_at,
        "notional":None,
    })
    return x


class FakeResponse:
    def __init__(self,response,status=201):
        self.status=status
        self.data=BytesIO(json.dumps(response).encode())
    def __enter__(self): return self
    def __exit__(self,*x): return False
    def read(self,size): return self.data.read(size)


class FakeBroker:
    def __init__(self,response=None,inject=None):
        self.calls=0
        self.response=receipt() if response is None else response
        self.inject=inject
        self.payload=None
    def __call__(self,request,timeout):
        self.calls+=1
        assert timeout==12
        assert request.get_method()=="POST"
        assert request.full_url=="https://api.alpaca.markets/v2/orders"
        assert request.get_header("Apca-api-key-id")==TEST_KEY
        assert request.get_header("Apca-api-secret-key")==TEST_SECRET
        self.payload=json.loads(request.data.decode())
        assert self.payload==m.seller.inspect_sell_shape(
            symbol="ACWI",original_qty=ORIGINAL_QTY)
        if self.inject=="timeout":
            raise URLError("fake unknown acceptance")
        if self.inject=="http403":
            raise HTTPError(request.full_url,403,"forbidden",None,None)
        return FakeResponse(self.response)


def temporarily_mock_release(monkeypatch):
    # Real code ALWAYS has all these false, no Github workflow can set them.
    monkeypatch.setattr(m,"TRANSPORT_RELEASED",True)
    monkeypatch.setattr(m,"PUBLIC_EXECUTION_ENABLED",True)
    monkeypatch.setattr(m,"SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT",True)


def test_original_hmac_signed_prepost_chain_validated_but_no_live_release():
    checked=m.check_prepost_sources(**good())
    assert checked["stage"]=="ORIGINAL_SIGNED_PREPOST_AND_PUBLIC_CHAIN_STRUCTURALLY_VALID_LOCKED"
    assert checked["signed_private_sequence"]==2
    assert checked["first_symbol"]=="ACWI"
    assert checked["stable_original_client_order_id"]==cas.CLIENT_IDS["ACWI"]
    assert checked["first_reservation_HMAC_verified"]
    assert checked["prepost_advance_HMAC_verified"]
    assert checked["public_bot_issue_head_chain_verified"]
    assert checked["immutable_rollback_watermark_verified"] is False
    assert checked["fresh_live_broker_source_verified"] is False
    assert checked["live_order_authorized"] is False
    assert checked["broker_orders_submitted"]==0


def test_default_hard_lock_prevents_even_request_construction_before_any_network():
    fake=FakeBroker()
    with pytest.raises(m.LockedSellStop,match="HARD LOCKED"):
        m.submit_live_original_acwi_sell(
            original_qty=ORIGINAL_QTY,api_key=TEST_KEY,
            api_secret=TEST_SECRET,signed_sources=good(),transport=fake)
    assert fake.calls==0
    assert m.TRANSPORT_RELEASED is False
    assert m.PUBLIC_EXECUTION_ENABLED is False
    assert m.SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT is False


@pytest.mark.parametrize("flag",[
    "TRANSPORT_RELEASED","PUBLIC_EXECUTION_ENABLED",
    "SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT",
])
def test_even_two_of_three_flags_fake_unlocked_do_not_enable_wire(monkeypatch,flag):
    fake=FakeBroker()
    temporarily_mock_release(monkeypatch)
    monkeypatch.setattr(m,flag,False)
    with pytest.raises(m.LockedSellStop,match="HARD LOCKED"):
        m.submit_live_original_acwi_sell(original_qty=ORIGINAL_QTY,
            api_key=TEST_KEY,api_secret=TEST_SECRET,
            signed_sources=good(),transport=fake)
    assert fake.calls==0


def test_exact_acwi_fractional_live_market_DAY_wire_with_fake_transport(monkeypatch):
    # Forced in-process fake unlock for a MOCK transport ONLY; no real API call.
    fake=FakeBroker()
    temporarily_mock_release(monkeypatch)
    res=m.submit_live_original_acwi_sell(original_qty=ORIGINAL_QTY,
        api_key=TEST_KEY,api_secret=TEST_SECRET,signed_sources=good(),transport=fake)
    assert fake.calls==1
    assert res["stage"]=="POST_ACCEPTED_ACTIVE_OR_PARTIAL_HOLD_NO_RETRY"
    assert res["broker_receipt_shape_checked_in_memory"]
    assert res["resubmission_permitted"] is False
    assert res["broker_position_flat_independently_verified"] is False
    assert res["sale_proceeds_settled_and_spendable"] is False
    assert res["account_id"] is res["broker_order_id"] is res["order_quantity"] is res["order_payload"] is None
    assert fake.payload["client_order_id"]==cas.CLIENT_IDS["ACWI"]
    assert fake.payload["qty"]==ORIGINAL_QTY
    assert fake.payload["side"]=="sell"
    assert fake.payload["type"]=="market"
    assert fake.payload["time_in_force"]=="day"
    assert "notional" not in fake.payload


def test_fully_filled_receipt_does_not_prove_position_flat_or_settled(monkeypatch):
    fake=FakeBroker(receipt("filled",filled=ORIGINAL_QTY,filled_at="2026-10-21T18:00:00Z"))
    temporarily_mock_release(monkeypatch)
    result=m.submit_live_original_acwi_sell(original_qty=ORIGINAL_QTY,
        api_key=TEST_KEY,api_secret=TEST_SECRET,signed_sources=good(),transport=fake)
    assert result["stage"]=="POST_ACCEPTED_FILLED_RECEIPT_NEEDS_POSITION_AND_ACTIVITY_PROOF"
    assert result["broker_fill_activities_independently_verified"] is False
    assert result["broker_position_flat_independently_verified"] is False


@pytest.mark.parametrize("status",[
    "accepted","pending_new","new","partially_filled","pending_cancel",
    "stopped","done_for_day","calculated",
])
def test_matching_active_broker_status_is_hold_never_resubmit(status):
    assert m._validate_receipt(receipt(status),original_qty=ORIGINAL_QTY)[
        "stage"]=="POST_ACCEPTED_ACTIVE_OR_PARTIAL_HOLD_NO_RETRY"


@pytest.mark.parametrize("status",[
    "rejected","canceled","expired","held","replaced","pending_replace",
    "suspended","weird","",
])
def test_terminal_ambiguous_and_unknown_broker_responses_hold(status):
    with pytest.raises(m.LockedSellStop):
        m._validate_receipt(receipt(status),original_qty=ORIGINAL_QTY)


@pytest.mark.parametrize("wrong",[
    {"symbol":"XLE"},{"side":"buy"},{"client_order_id":"modified"},
    {"qty":"0.123456788"},{"type":"limit"},{"time_in_force":"gtc"},
    {"notional":"10"},{"id":"fake"}, {"filled_qty":"999"},
    {"status":"filled","filled_at":None,"filled_qty":ORIGINAL_QTY},
    {"status":"filled","filled_at":"2026-10-21T18:00:00Z","filled_qty":"0"},
])
def test_invalid_order_receipt_cannot_be_reconciled(wrong):
    x=receipt()
    x.update(wrong)
    with pytest.raises(m.LockedSellStop):
        m._validate_receipt(x,original_qty=ORIGINAL_QTY)


@pytest.mark.parametrize("where,change",[
    ("reserved_source",{"sha":"f"*40}),
    ("prepost_source",{"sha":"f"*40}),
    ("first_comment",{"body":"tampered"}),
    ("prepost_comment",{"body":"tampered"}),
    ("genesis_comment",{"id":100}),
    ("prepost_comment",{"user":{"login":"attacker"}}),
    ("prepost_comment",{"issue_url":"https://example.org/evil"}),
])
def test_signed_prepost_tampering_blocks_early_and_never_fakes_an_order(where,change,monkeypatch):
    data=good()
    data[where].update(change)
    with pytest.raises(m.LockedSellStop):
        m.check_prepost_sources(**data)
    fake=FakeBroker()
    temporarily_mock_release(monkeypatch)
    with pytest.raises(m.LockedSellStop):
        m.submit_live_original_acwi_sell(
            original_qty=ORIGINAL_QTY,api_key=TEST_KEY,api_secret=TEST_SECRET,
            signed_sources=data,transport=fake)
    assert fake.calls==0


def test_invalid_signed_review_flags_or_wrong_qty_never_call_transport(monkeypatch):
    temporarily_mock_release(monkeypatch)
    fake=FakeBroker()
    for source in (None,{},{"approved":True}, {**good(),"original_qty":"0.123456788"}):
        with pytest.raises(m.LockedSellStop):
            m.submit_live_original_acwi_sell(
                original_qty=ORIGINAL_QTY,api_key=TEST_KEY,
                api_secret=TEST_SECRET,signed_sources=source,transport=fake)
    assert fake.calls==0


@pytest.mark.parametrize("failure",["timeout","http403"])
def test_unknown_broker_POST_response_is_never_retried(monkeypatch,failure):
    temporarily_mock_release(monkeypatch)
    fake=FakeBroker(inject=failure)
    with pytest.raises(m.LockedSellStop,match="NEVER retry"):
        m.submit_live_original_acwi_sell(original_qty=ORIGINAL_QTY,
            api_key=TEST_KEY,api_secret=TEST_SECRET,
            signed_sources=good(),transport=fake)
    assert fake.calls==1


def test_no_second_request_in_one_invocation_after_ambiguous_status(monkeypatch):
    temporarily_mock_release(monkeypatch)
    fake=FakeBroker(receipt("rejected"))
    with pytest.raises(m.LockedSellStop):
        m.submit_live_original_acwi_sell(original_qty=ORIGINAL_QTY,
            api_key=TEST_KEY,api_secret=TEST_SECRET,signed_sources=good(),
            transport=fake)
    assert fake.calls==1


def test_cannot_build_http_request_for_XLE_or_illegal_decimal():
    for qty in ("1e-5","0","0.0000000001","NaN","-1"):
        with pytest.raises(Exception):
            m.build_exact_wire_request(
                original_qty=qty,api_key=TEST_KEY,api_secret=TEST_SECRET)
    assert m.seller.LEGACY_TO_EXIT==("ACWI","EEM","XLV")
    assert "XLE" not in m.seller.LEGACY_TO_EXIT


def test_module_has_no_live_action_main_or_github_credentials():
    code=Path(m.__file__).read_text()
    assert "def main(" not in code
    assert "if __name__" not in code
    assert "os.getenv(" not in code
    assert "ALPACA_LIVE_KEY" not in code
    assert "ALPACA_LIVE_SECRET" not in code
    assert "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN" not in code
    assert "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX" not in code
    assert m.NO_MAIN_OR_WORKFLOW
    assert m.TRANSPORT_RELEASED is False
    assert m.PUBLIC_EXECUTION_ENABLED is False
    assert m.SEPARATE_SIGNED_V6_LIVE_RELEASE_PRESENT is False
    assert m.AUTOMATIC_RETRY_RELEASED is False
