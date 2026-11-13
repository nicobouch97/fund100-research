"""Offline adversarial tests for separate Trading API OAuth broker-risk reader.

No real Alpaca calls, no tokens, signer keys or order endpoints. Even passing
a fake eight-GET witness must NOT authorize a live trade.
"""
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

import fund100_v6_private_oauth_risk_witness_locked_v1_0 as watcher
import fund100_v6_readonly_oauth_eight_get_transport_v1_0 as oauth

ACCOUNT = "OFFLINEACCOUNT001"
BINDING = sha256(("FUND100-LIVE-ACCOUNT|" + ACCOUNT).encode()).hexdigest()
POLICY = {"account_binding_sha256": BINDING, "capital_ceiling_usd": "130.30"}
POLICY_SHA = sha256(json.dumps(POLICY,sort_keys=True,separators=(",",":"),
                               ensure_ascii=True).encode()).hexdigest()
GRANT = {"access_token": "OFFLINE_ONLY_OAUTH_BEARER_123456789",
         "token_type": "Bearer", "scope": ""}
MAIN = "a"*40
BOOT = {"offline_signed_bootstrap": True}


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(watcher, "SOURCE_RELEASED", True)
    monkeypatch.setattr(
        watcher,"PROVIDER_READONLY_GRANT_CUSTODY_INDEPENDENTLY_VERIFIED",True)
    monkeypatch.setattr(
        watcher,"SIGNED_ORIGINAL_POLICY_SOURCE_INDEPENDENTLY_VERIFIED",True)
    monkeypatch.setattr(watcher,"APPROVED_ACCOUNT_BINDING_SHA256", BINDING)
    monkeypatch.setattr(watcher,"APPROVED_POLICY_SHA256", POLICY_SHA)
    monkeypatch.setattr(watcher,"APPROVED_MAIN_SHA", MAIN)
    monkeypatch.setattr(oauth,"GET_TRANSPORT_RELEASED",True)
    monkeypatch.setenv(watcher.ENV_MODE,watcher.REQUIRED_MODE)
    for x in watcher.FORBIDDEN_CREDENTIALS:
        monkeypatch.delenv(x,raising=False)
    events=[]
    def transport_one(path, params, token, *, transport=None):
        assert token == GRANT["access_token"]
        assert (path,params) == oauth.REQUEST_PLAN[len(events)]
        events.append(path)
        if len(events)==1:
            return {"id":ACCOUNT}
        if len(events)==4:
            return {"is_open":True}
        return []
    monkeypatch.setattr(oauth, "_request_one", transport_one)
    def evaluator(**kwargs):
        assert kwargs["account"]["id"] == ACCOUNT
        assert kwargs["bootstrap"] == BOOT
        assert kwargs["original_policy"] == POLICY
        assert kwargs["original_qty"] == "0.123"
        assert kwargs["observed_at_utc"].endswith("Z")
        assert len(events)==8
        return {
            "schema": watcher.risk.SCHEMA,
            "status": "ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2",
            "same_process_real_broker_gets":8,
            "original_acwi_exact_fractional_holdings_verified":True,
            "original_strict_postfunding_6_20_35_risk_pass":True,
            "broker_post_attempts":0,
            "orders_submitted_here":0,
            "buy_authorized":False,
        }
    monkeypatch.setattr(watcher.risk,"evaluate_original_sell_only",evaluator)
    return events


def capture():
    return watcher.capture_original_acwi_private_witness(
        verified_grant=GRANT, signed_bootstrap=BOOT,
        signed_policy=POLICY, original_qty="0.123")


def test_default_source_locked_without_transport(monkeypatch):
    assert watcher.SOURCE_RELEASED is False
    assert watcher.PROVIDER_READONLY_GRANT_CUSTODY_INDEPENDENTLY_VERIFIED is False
    assert watcher.SIGNED_ORIGINAL_POLICY_SOURCE_INDEPENDENTLY_VERIFIED is False
    assert watcher.APPROVED_ACCOUNT_BINDING_SHA256 is None
    assert watcher.APPROVED_POLICY_SHA256 is None
    assert watcher.APPROVED_MAIN_SHA is None
    monkeypatch.setattr(oauth,"original_eight_get_snapshot",
                        lambda *a,**k:pytest.fail("Broker accessed while locked"))
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="HARD LOCKED"):
        capture()


def test_exact_eight_get_no_order_and_private_result(offline):
    witness=capture()
    assert offline == [x[0] for x in oauth.REQUEST_PLAN]
    assert witness["private_witness_not_signed"] is True
    assert witness["trade_authorized"] is False
    assert witness["broker_writes"] == 0
    assert witness["head_sha"] == MAIN
    assert witness["account_id"] == ACCOUNT
    assert witness["policy"] == POLICY
    assert witness["checked"]["same_process_real_broker_gets"] == 8
    assert "ed25519_signature_hex" not in witness


@pytest.mark.parametrize("name",[
    "SOURCE_RELEASED",
    "PROVIDER_READONLY_GRANT_CUSTODY_INDEPENDENTLY_VERIFIED",
    "SIGNED_ORIGINAL_POLICY_SOURCE_INDEPENDENTLY_VERIFIED",
])
def test_release_latch_required_before_any_get(offline,monkeypatch,name):
    monkeypatch.setattr(watcher,name,False)
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="HARD LOCKED"):
        capture()
    assert offline==[]


@pytest.mark.parametrize("env",watcher.FORBIDDEN_CREDENTIALS)
def test_never_colocate_trading_secret_or_signer_key(
        offline,monkeypatch,env):
    monkeypatch.setenv(env,"NO_REAL_CREDENTIALS")
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="HARD LOCKED"):
        capture()
    assert offline==[]


@pytest.mark.parametrize("field,bad",[
    ("scope","trading"),
    ("scope","account:write"),
    ("scope","data"),
    ("scope",None),
    ("token_type","Basic"),
    ("access_token","bad"),
])
def test_unverified_oauth_grant_cannot_read_broker(
        offline,field,bad):
    grant=dict(GRANT,**{field:bad})
    with pytest.raises(watcher.PrivateRiskWitnessHold):
        watcher.capture_original_acwi_private_witness(
            verified_grant=grant,signed_bootstrap=BOOT,
            signed_policy=POLICY,original_qty="0.123")
    assert offline==[]


def test_unpinned_or_changed_policy_stops_before_oauth_get(offline,monkeypatch):
    policy=dict(POLICY,capital_ceiling_usd="9999.00")
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="policy digest"):
        watcher.capture_original_acwi_private_witness(
            verified_grant=GRANT,signed_bootstrap=BOOT,
            signed_policy=policy,original_qty="0.123")
    assert offline==[]
    monkeypatch.setattr(watcher,"APPROVED_POLICY_SHA256",None)
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="HARD LOCKED"):
        capture()


def test_oauth_snapshot_network_outage_is_generic_hold(offline,monkeypatch):
    def fail(*a,**kw):
        raise OSError("OFFLINE_ONLY_TOKEN_SHOULD_NOT_LOG")
    monkeypatch.setattr(oauth, "original_eight_get_snapshot",fail)
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="broker risk unavailable") as x:
        capture()
    assert "OFFLINE_ONLY_TOKEN" not in str(x.value)
    assert offline==[]


def test_incomplete_broker_gets_cannot_be_a_pass(offline,monkeypatch):
    monkeypatch.setattr(oauth,"original_eight_get_snapshot",
                        lambda *a,**kw:tuple({} for _ in range(7)))
    with pytest.raises(watcher.PrivateRiskWitnessHold):
        capture()


def test_changed_account_id_never_passes_even_if_evaluator_would(
        offline,monkeypatch):
    def wrong_account(*args,**kwargs):
        return ({"id":"DIFFERENTACCOUNT999"}, [], [], {"is_open":True},
                [], [], [], [])
    monkeypatch.setattr(oauth,"original_eight_get_snapshot",wrong_account)
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="bound account"):
        capture()


def test_closed_market_never_passes(offline,monkeypatch):
    monkeypatch.setattr(oauth,"original_eight_get_snapshot",lambda *a,**kw:
                        ({"id":ACCOUNT}, [], [], {"is_open":False},
                         [], [], [], []))
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="market"):
        capture()


@pytest.mark.parametrize("field,bad",[
    ("same_process_real_broker_gets",7),
    ("broker_post_attempts",1),
    ("orders_submitted_here",True),
    ("original_strict_postfunding_6_20_35_risk_pass",False),
    ("original_acwi_exact_fractional_holdings_verified",False),
    ("buy_authorized",True),
])
def test_evaluator_result_must_match_reviewed_contract(
        offline,monkeypatch,field,bad):
    original=watcher.risk.evaluate_original_sell_only
    def tamper(**kw):
        return dict(original(**kw),**{field:bad})
    monkeypatch.setattr(watcher.risk,"evaluate_original_sell_only",tamper)
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="did not PASS"):
        capture()


def test_snapshot_delayed_beyond_bound_cannot_pass(offline,monkeypatch):
    times=iter([10.0,10.0+watcher.MAX_SECONDS+0.25])
    monkeypatch.setattr(watcher.time,"monotonic",lambda:next(times))
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="stale"):
        capture()


def test_mode_and_no_preexisting_oauth_key(offline,monkeypatch):
    monkeypatch.delenv(watcher.ENV_MODE)
    with pytest.raises(watcher.PrivateRiskWitnessHold,match="HARD LOCKED"):
        capture()
    assert offline==[]


def test_source_is_only_an_in_memory_witness():
    content=Path(watcher.__file__).read_text()
    assert "SOURCE_RELEASED = False" in content
    assert "NO_SIGNER_KEY = True" in content
    assert "NO_PUBLIC_OUTPUT = True" in content
    assert "NO_BROKER_WRITE = True" in content
    assert "NO_TRADE_RELEASE = True" in content
    assert "oauth.original_eight_get_snapshot(" in content
    assert "risk.evaluate_original_sell_only(" in content
    assert "urlopen(" not in content
    assert "method=\"POST\"" not in content
    assert "submit_order(" not in content
    assert "Ed25519PrivateKey" not in content
