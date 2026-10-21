"""Credentialless only mocked V6 ACWI SELL inside original V5 reviewed writer."""
from io import BytesIO
import json
from pathlib import Path
from urllib.error import URLError, HTTPError

import pytest

import fund100_alpaca_live_writer_candidate_v1_1 as writer
import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as pure
import test_fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as fixture

QTY=fixture.ORIGINAL_QTY
ID=fixture.ORDER_ID
TEST_KEY="offline-dummy-key-very-definitely-not-real"
TEST_SECRET="offline-dummy-secret-very-definitely-not-real"


class FakeResponse:
    def __init__(self,body,status=201):
        self.status=status
        self.data=BytesIO(json.dumps(body).encode("utf-8"))
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def read(self,size):return self.data.read(size)


class FakeBrokerPost:
    def __init__(self,response=None,fail=None):
        self.response=fixture.receipt() if response is None else response
        self.fail=fail
        self.calls=0
        self.payload=None
    def __call__(self,request,timeout):
        self.calls+=1
        assert timeout==12
        assert request.get_method()=="POST"
        assert request.full_url=="https://api.alpaca.markets/v2/orders"
        assert request.get_header("Apca-api-key-id")==TEST_KEY
        assert request.get_header("Apca-api-secret-key")==TEST_SECRET
        self.payload=json.loads(request.data.decode("ascii"))
        assert self.payload==pure.build_exact_sell_payload(original_qty=QTY)
        if self.fail=="unknown":
            raise URLError("mock unknown acceptance")
        if self.fail=="403":
            raise HTTPError(request.full_url,403,"mock forbidden",None,None)
        if self.fail=="500":
            raise HTTPError(request.full_url,500,"mock broker error",None,None)
        return FakeResponse(self.response)


def fake_release(monkeypatch):
    # Test-process monkeypatch ONLY. None of these changes reaches GitHub main.
    for key in (
        "TRANSPORT_RELEASED","PUBLIC_EXECUTION_ENABLED",
        "V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED",
        "V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED",
        "V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED",
        "V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED",
    ):
        monkeypatch.setattr(writer,key,True)


def call(fake, signed=None):
    return writer.submit_v6_s1_original_acwi_fractional_sell(
        original_qty=QTY,
        signed_sources=fixture.signed() if signed is None else signed,
        key=TEST_KEY,secret=TEST_SECRET,
        transport=fake)


def test_real_original_reviewed_writer_stays_hard_locked_by_default():
    fake=FakeBrokerPost()
    with pytest.raises(writer.LiveWriterCandidateLocked):
        call(fake)
    assert fake.calls==0
    assert writer.TRANSPORT_RELEASED is False
    assert writer.PUBLIC_EXECUTION_ENABLED is False
    assert writer.V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED is False
    assert writer.V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED is False
    assert writer.V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED is False
    assert writer.V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED is False


@pytest.mark.parametrize("field",[
    "TRANSPORT_RELEASED","PUBLIC_EXECUTION_ENABLED",
    "V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED",
    "V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED",
    "V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED",
    "V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED",
])
def test_any_single_unreleased_flag_blocks_before_mock_network(field,monkeypatch):
    fake_release(monkeypatch)
    monkeypatch.setattr(writer,field,False)
    fake=FakeBrokerPost()
    with pytest.raises(writer.LiveWriterCandidateLocked):
        call(fake)
    assert fake.calls==0


def test_exact_original_qty_market_day_wire_then_redacted_fake_receipt(monkeypatch):
    fake_release(monkeypatch)
    fake=FakeBrokerPost()
    answer=call(fake)
    assert fake.calls==1
    assert fake.payload=={
        "symbol":"ACWI","qty":QTY,"side":"sell",
        "type":"market","time_in_force":"day","extended_hours":False,
        "client_order_id":pure.cas.CLIENT_IDS["ACWI"],
    }
    assert answer["stage"]=="POST_ACCEPTED_ACTIVE_OR_PARTIAL_HOLD_NO_RETRY"
    assert answer["resubmission_permitted"] is False
    assert answer["broker_position_flat_independently_verified"] is False
    assert answer["broker_fill_activities_independently_verified"] is False
    assert answer["sale_proceeds_settled_and_spendable"] is False
    assert answer["broker_order_id"] is None
    assert answer["order_quantity"] is None
    assert answer["order_payload"] is None


def test_fake_filled_receipt_cannot_claim_settlement(monkeypatch):
    fake_release(monkeypatch)
    fake=FakeBrokerPost(fixture.receipt(
        status="filled",filled=QTY,filled_at="2026-10-21T18:30:00Z"))
    answer=call(fake)
    assert answer["stage"]=="POST_ACCEPTED_FILLED_RECEIPT_NEEDS_POSITION_AND_ACTIVITY_PROOF"
    assert not answer["sale_proceeds_settled_and_spendable"]
    assert fake.calls==1


@pytest.mark.parametrize("change",[
    ("reserved_source",{"sha":"f"*40}),
    ("prepost_source",{"sha":"f"*40}),
    ("first_comment",{"body":"tamper"}),
    ("prepost_comment",{"user":{"login":"attacker"}}),
    ("genesis_comment",{"body":"tamper"}),
])
def test_unauthenticated_account_signed_sources_reject_before_broker(change,monkeypatch):
    fake_release(monkeypatch)
    data=fixture.signed()
    data[change[0]].update(change[1])
    fake=FakeBrokerPost()
    with pytest.raises(writer.LiveWriterCandidateLocked,match="HMAC"):
        call(fake,data)
    assert fake.calls==0


@pytest.mark.parametrize("provided",[
    {},{"approved":True},{"schema":"FAKE"},
])
def test_no_user_forged_approval_releases_qty_sell(provided,monkeypatch):
    fake_release(monkeypatch)
    fake=FakeBrokerPost()
    with pytest.raises(writer.LiveWriterCandidateLocked):
        call(fake,provided)
    assert fake.calls==0


@pytest.mark.parametrize("fail",["unknown","403","500"])
def test_uncertain_or_rejected_http_post_issued_once_and_never_retried(fail,monkeypatch):
    fake_release(monkeypatch)
    fake=FakeBrokerPost(fail=fail)
    with pytest.raises(writer.LiveWriterCandidateLocked,match="NEVER retry"):
        call(fake)
    assert fake.calls==1


@pytest.mark.parametrize("status",[
    "rejected","canceled","expired","held","replaced",
    "pending_replace","unexpected",
])
def test_fake_received_terminal_or_ambiguous_receipt_holds_no_retry(status,monkeypatch):
    fake_release(monkeypatch)
    fake=FakeBrokerPost(fixture.receipt(status=status))
    with pytest.raises(writer.LiveWriterCandidateLocked,match="HOLD never retry"):
        call(fake)
    assert fake.calls==1


def test_original_v5_writer_entrypoint_and_hard_locks_preserved():
    source=Path(writer.__file__).read_text()
    assert "def submit_authorized_order_batch(" in source
    assert "def _post_live_market_order(" in source
    assert "def submit_v6_s1_original_acwi_fractional_sell(" in source
    assert "V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED = False" in source
    assert "V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED = False" in source
    assert "V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED = False" in source
    assert "V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED = False" in source
    assert "if __name__" not in source
    assert "def main(" not in source
    assert "ALPACA_LIVE_KEY" not in source
    assert "ALPACA_LIVE_SECRET" not in source


def test_original_alpaca_writer_is_the_ONLY_new_post_executable_python_module():
    pure_source=Path(pure.__file__).read_text()
    assert "Request(" not in pure_source
    assert "urlopen(" not in pure_source
    assert "from urllib.request" not in pure_source
    assert "method=\"POST\"" in Path(writer.__file__).read_text()
