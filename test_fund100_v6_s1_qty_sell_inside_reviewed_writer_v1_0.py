"""Credentialless only mocked V6 ACWI SELL inside original V5 reviewed writer."""
from io import BytesIO
from copy import deepcopy
import json
from pathlib import Path
from urllib.error import URLError, HTTPError

import pytest

import fund100_alpaca_live_writer_candidate_v1_1 as writer
import fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as pure
import test_fund100_v6_s1_locked_live_acwi_sell_http_candidate_v1_0 as fixture
import fund100_v6_s1_immutable_release_anchor_v1_0 as anchor
import test_fund100_v6_s1_immutable_release_anchor_v1_0 as immutable_fixture
import fund100_v6_s1_fresh_acwi_order_time_risk_getonly_v1_0 as risk
import pytest

@pytest.fixture(autouse=True)
def fake_FUTURE_risk_V2_release_only_in_credentialless_test(monkeypatch):
    # This report DOES NOT EXIST in production. Real V1 always returns STOP;
    # unit-test monkeypatching tests the post-gate reviewed HTTP payload only.
    def fake_approved(*,original_qty,key,secret):
        assert original_qty==QTY
        assert key==TEST_KEY and secret==TEST_SECRET
        return {
            "status":"ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2",
            "same_process_real_broker_gets":7,
            "original_acwi_exact_fractional_holdings_verified":True,
            "original_open_market_and_no_pending_order_verified":True,
            "original_strict_postfunding_6_20_35_risk_pass":True,
            "broker_order_authorized":True,
            "sell_only_original_legacy_ACWI":True,
            "buy_authorized":False,
            "capital_ceiling_usd":"130.30",
            "full_original_acwi_exit_bounded_by_authenticated_inventory":True,
            "maximum_new_order_notional_usd":"65.00",
            "orders_submitted_here":0,
            "settled_cash_verified":False,
            "broker_post_attempts":0,
        }
    monkeypatch.setattr(risk,"inspect_actual_original_seven_get",fake_approved)
    # Mock ONLY: current-main GitHub operator and broker kill read are
    # deliberately NEVER bypassed in the real reviewed writer.
    import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as active
    monkeypatch.setattr(active,"_scope",lambda:None)


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
        "V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED",
        "V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED",
        "V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED",
        "V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED",
    ):
        monkeypatch.setattr(writer,key,True)


def call(fake, signed=None, owner=None, *, release_change=None, release_asset=None):
    authentic_owner,authentic_signed=fixture.claimed_owner_and_original_signed_prepost()
    exact_public=anchor.original_signed_anchor_asset(
        signed_owner_sources=authentic_owner,
        prepost_source=authentic_signed["prepost_source"])
    mock_release=immutable_fixture.GitHubImmutable(
        exact_public if release_asset is None else release_asset,
        change=release_change)
    return writer.submit_v6_s1_original_acwi_fractional_sell(
        original_qty=QTY,
        signed_sources=authentic_signed if signed is None else signed,
        owner_sources=authentic_owner if owner is None else owner,
        public_release_read_token=immutable_fixture.READ,
        key=TEST_KEY,secret=TEST_SECRET,
        transport=fake,release_transport=mock_release.transport)


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



@pytest.mark.parametrize("legacy",["TRANSPORT_RELEASED","PUBLIC_EXECUTION_ENABLED"])
def test_independent_v6_sell_never_unlocks_v5_global_writer(legacy,monkeypatch):
    fake_release(monkeypatch)  # only V6-specific flags released in FAKE process
    assert writer.TRANSPORT_RELEASED is False
    assert writer.PUBLIC_EXECUTION_ENABLED is False
    fake=FakeBrokerPost()
    monkeypatch.setattr(writer,legacy,True)
    with pytest.raises(writer.LiveWriterCandidateLocked,match="original V5 global writer STOP"):
        call(fake)
    assert fake.calls==0


def test_v6_separate_release_uses_only_v6_flags_not_legacy_global_go(monkeypatch):
    fake_release(monkeypatch)
    assert writer.TRANSPORT_RELEASED is False
    assert writer.PUBLIC_EXECUTION_ENABLED is False
    # All remote reads/writes on the test path are synthetic; this is NOT
    # a workflow release, a broker authorization or a funded order.
    fake=FakeBrokerPost()
    answer=call(fake)
    assert fake.calls==1
    assert answer["resubmission_permitted"] is False
    assert writer.require_public_execution_released is not None

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


@pytest.mark.parametrize("tamper",[
    "missing","changed_owner_run","changed_nonce","changed_main_sha",
    "changed_broker_source_run","claim_restarted_attempt","changed_fence_head",
    "changed_first_signed_comment","changed_order_quantity",
])
def test_different_or_unverifiable_hmac_owner_never_reaches_mock_broker(tamper,monkeypatch):
    fake_release(monkeypatch)
    owner,signed=fixture.claimed_owner_and_original_signed_prepost()
    owner=deepcopy(owner)
    if tamper=="missing":owner={}
    elif tamper=="changed_owner_run":owner["owner_run_id"]="39812340002"
    elif tamper=="changed_nonce":owner["owner_nonce"]="b"*64
    elif tamper=="changed_main_sha":owner["current_main_sha"]="f"*40
    elif tamper=="changed_broker_source_run":owner["source_broker_run_id"]="39812340002"
    elif tamper=="claim_restarted_attempt":owner["owner_attempt"]=2
    elif tamper=="changed_fence_head":owner["current_fence_source"]["sha"]="0"*40
    elif tamper=="changed_first_signed_comment":owner["first_comment"]["body"]="forged"
    elif tamper=="changed_order_quantity":owner["original_qty"]="0.123456788"
    fake=FakeBrokerPost()
    with pytest.raises(writer.LiveWriterCandidateLocked,match="owner"):
        call(fake,signed=signed,owner=owner)
    assert fake.calls==0


def test_owner_hmac_valid_but_mismatched_signed_prepost_source_cannot_submit(monkeypatch):
    fake_release(monkeypatch)
    owner,signed=fixture.claimed_owner_and_original_signed_prepost()
    signed=deepcopy(signed)
    signed["first_comment"]["body"]="forged"
    fake=FakeBrokerPost()
    with pytest.raises(writer.LiveWriterCandidateLocked,match="owner"):
        call(fake,signed=signed,owner=owner)
    assert fake.calls==0


@pytest.mark.parametrize("release_change",[
    "404","mutable","no_immutable_field","draft","wrong_tag",
    "wrong_sha","wrong_actor","wrong_digest","wrong_size","extra_asset",
    "asset_not_uploaded","wrong_download_url","oversized_metadata",
    "bad_bytes","asset_403",
])
def test_final_reviewed_writer_rejects_untrusted_mutable_or_missing_release_before_broker(
        release_change,monkeypatch):
    fake_release(monkeypatch)
    fake=FakeBrokerPost()
    with pytest.raises(writer.LiveWriterCandidateLocked,match="immutable"):
        call(fake,release_change=release_change)
    assert fake.calls==0


def test_final_writer_needs_actual_immutable_verification_not_fake_flags(monkeypatch):
    fake_release(monkeypatch)
    fake=FakeBrokerPost()
    with pytest.raises(writer.LiveWriterCandidateLocked,match="immutable"):
        writer.submit_v6_s1_original_acwi_fractional_sell(
            original_qty=QTY,
            signed_sources=fixture.claimed_owner_and_original_signed_prepost()[1],
            owner_sources=fixture.claimed_owner_and_original_signed_prepost()[0],
            public_release_read_token="invalid",
            key=TEST_KEY,secret=TEST_SECRET,transport=fake)
    assert fake.calls==0


def test_real_current_v1_broker_risk_STOP_is_not_bypassable_even_after_mock_release_flags(monkeypatch):
    fake_release(monkeypatch)
    fake=FakeBrokerPost()
    monkeypatch.setattr(risk,"inspect_actual_original_seven_get",
        lambda **kw:{
            "status":"ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_PASSED_STILL_STOPPED",
            "same_process_real_broker_gets":7,
            "original_acwi_exact_fractional_holdings_verified":True,
            "original_open_market_and_no_pending_order_verified":True,
            "original_strict_postfunding_6_20_35_risk_pass":True,
            "broker_order_authorized":False,
            "broker_post_attempts":0,
        })
    with pytest.raises(writer.LiveWriterCandidateLocked,match="risk remains STOPPED"):
        call(fake)
    assert fake.calls==0


def test_final_writer_broker_risk_source_unavailable_blocks_any_post(monkeypatch):
    fake_release(monkeypatch)
    fake=FakeBrokerPost()
    def unavailable(**kwargs):raise TimeoutError("no actual risk GET")
    monkeypatch.setattr(risk,"inspect_actual_original_seven_get",unavailable)
    with pytest.raises(writer.LiveWriterCandidateLocked,match="seven-GET risk unavailable"):
        call(fake)
    assert fake.calls==0


@pytest.mark.parametrize("tamper",[
    ("status","FORGED_GO"),("same_process_real_broker_gets",6),
    ("original_acwi_exact_fractional_holdings_verified",False),
    ("original_open_market_and_no_pending_order_verified",False),
    ("original_strict_postfunding_6_20_35_risk_pass",False),
    ("broker_order_authorized",False),("broker_post_attempts",1),
    ("sell_only_original_legacy_ACWI",False),
    ("buy_authorized",True),
    ("capital_ceiling_usd","999.00"),
    ("maximum_new_order_notional_usd","130.30"),
    ("full_original_acwi_exit_bounded_by_authenticated_inventory",False),
    ("orders_submitted_here",1),
    ("settled_cash_verified",True),
])
def test_final_writer_rejects_incomplete_or_stale_same_process_broker_risk(
        monkeypatch,tamper):
    fake_release(monkeypatch)
    fake=FakeBrokerPost()
    def report(**kwargs):
        r={
            "status":"ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2",
            "same_process_real_broker_gets":7,
            "original_acwi_exact_fractional_holdings_verified":True,
            "original_open_market_and_no_pending_order_verified":True,
            "original_strict_postfunding_6_20_35_risk_pass":True,
            "broker_order_authorized":True,
            "sell_only_original_legacy_ACWI":True,
            "buy_authorized":False,
            "capital_ceiling_usd":"130.30",
            "full_original_acwi_exit_bounded_by_authenticated_inventory":True,
            "maximum_new_order_notional_usd":"65.00",
            "orders_submitted_here":0,
            "settled_cash_verified":False,
            "broker_post_attempts":0,
        }
        r[tamper[0]]=tamper[1]
        return r
    monkeypatch.setattr(risk,"inspect_actual_original_seven_get",report)
    with pytest.raises(writer.LiveWriterCandidateLocked,match="risk remains STOPPED"):
        call(fake)
    assert fake.calls==0



@pytest.mark.parametrize("missing",[
    "sell_only_original_legacy_ACWI","buy_authorized","capital_ceiling_usd",
    "full_original_acwi_exit_bounded_by_authenticated_inventory","maximum_new_order_notional_usd","orders_submitted_here","settled_cash_verified",
])
def test_final_writer_rejects_missing_original_active_high_sell_scope_before_any_post(
        monkeypatch,missing):
    fake_release(monkeypatch)
    fake=FakeBrokerPost()
    def report(**kwargs):
        r={
            "status":"ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2",
            "same_process_real_broker_gets":7,
            "original_acwi_exact_fractional_holdings_verified":True,
            "original_open_market_and_no_pending_order_verified":True,
            "original_strict_postfunding_6_20_35_risk_pass":True,
            "broker_order_authorized":True,
            "sell_only_original_legacy_ACWI":True,
            "buy_authorized":False,
            "capital_ceiling_usd":"130.30",
            "full_original_acwi_exit_bounded_by_authenticated_inventory":True,
            "maximum_new_order_notional_usd":"65.00",
            "orders_submitted_here":0,
            "settled_cash_verified":False,
            "broker_post_attempts":0,
        }
        r.pop(missing)
        return r
    monkeypatch.setattr(risk,"inspect_actual_original_seven_get",report)
    with pytest.raises(writer.LiveWriterCandidateLocked,match="risk remains STOPPED"):
        call(fake)
    assert fake.calls==0


def test_emergency_stop_after_risk_before_original_acwi_post_fails_closed(
        monkeypatch):
    import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as active
    fake_release(monkeypatch)
    attempted=FakeBrokerPost()
    checks=[]
    def emergency_stop():
        checks.append("current_main_GO_revoked_after_real_broker_risk")
        raise active.ActiveSellStop("V6 operator stopped after seven GET")
    monkeypatch.setattr(active,"_scope",emergency_stop)
    with pytest.raises(writer.LiveWriterCandidateLocked,
                       match="operator revoked or emergency kill before POST"):
        call(attempted)
    assert checks==["current_main_GO_revoked_after_real_broker_risk"]
    assert attempted.calls==0


def test_last_gate_operator_scope_read_occurs_once_before_first_alpaca_post(
        monkeypatch):
    import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as active
    fake_release(monkeypatch)
    checks=[]
    monkeypatch.setattr(active,"_scope",lambda:checks.append("GO revalidated"))
    fake=FakeBrokerPost()
    result=call(fake)
    assert checks==["GO revalidated"]
    assert fake.calls==1
    assert result["resubmission_permitted"] is False


def test_revocation_recheck_occurs_after_live_risk_before_broker_post():
    source=Path(writer.__file__).read_text()
    start=source.index("def submit_v6_s1_original_acwi_fractional_sell(")
    end=len(source)
    body=source[start:end]
    gate=body.index("order_time=risk.inspect_actual_original_seven_get(")
    scope=body.index("active._scope()",gate)
    broker=body.index('url=LIVE_BASE_URL+LIVE_ORDER_PATH',scope)
    request=body.index('method="POST"',broker)
    assert gate<scope<broker<request
    assert "operator revoked or emergency kill before POST" in body


def test_original_v5_writer_entrypoint_and_hard_locks_preserved():
    source=Path(writer.__file__).read_text()
    assert "def submit_authorized_order_batch(" in source
    assert "def _post_live_market_order(" in source
    assert "def submit_v6_s1_original_acwi_fractional_sell(" in source
    assert "V6_S1_ACWI_QTY_SELL_TRANSPORT_RELEASED = False" in source
    assert "V6_S1_ACWI_QTY_SELL_EXECUTION_RELEASED = False" in source
    assert "V6_S1_ACWI_FRESH_ACCOUNT_RISK_SOURCE_RELEASED = False" in source
    assert "V6_S1_ACWI_EXTERNAL_WATERMARK_RELEASED = False" in source
    assert "owner_sources: dict" in source
    assert "public_release_read_token: str" in source
    assert "v6.owner_fence.verify_claimed_owner(**owner_sources)" in source
    assert "anchor.verify_published_immutable_anchor(" in source
    assert "anchor.original_signed_anchor_asset(" in source
    assert "risk.inspect_actual_original_seven_get(" in source
    assert "ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2" in source
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
