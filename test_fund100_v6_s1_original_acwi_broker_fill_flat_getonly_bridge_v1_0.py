"""Credentialless simulated six real-route GETs for original ACWI postorder.

The signed material is built with the EXISTING original seq1/seq2 HMAC
fixtures, but none of these tests authenticate live account state.
"""
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import pytest

import fund100_v6_s1_original_acwi_broker_fill_flat_getonly_bridge_v1_0 as bridge
from test_fund100_v6_s1_original_acwi_fill_flat_offline_v1_0 import base, OBSERVED

KEY="dummy-readonly-alpaca-live-key"
SECRET="dummy-readonly-alpaca-secret"
FAKE_ACCOUNT="fake-original-broker-account-for-source-tests"

def source(monkeypatch):
    original=base()
    docs=[
        deepcopy(original["closed_receipt"]),
        deepcopy(original["fill_pages"][0]),
        {"id":FAKE_ACCOUNT,"status":"ACTIVE","account_blocked":False,
         "trading_blocked":False},
        deepcopy(original["post_positions"]),
        [],
        {"timestamp":"2026-10-22T13:32:40Z","is_open":True},
    ]
    # Fake only the adapter's exact account SHA comparator. The signed
    # seq1/seq2 HMAC proof and pinned historical quantity source remain real.
    expected_sha=sha256(("FUND100-LIVE-ACCOUNT|"+
                         FAKE_ACCOUNT).encode()).hexdigest()
    def binding(account):
        return sha256(("FUND100-LIVE-ACCOUNT|"+
                       account["id"].strip()).encode()).hexdigest()==expected_sha
    monkeypatch.setattr(bridge,"_same_original_live_account",binding)
    expected=[
        ("/v2/orders:by_client_order_id",
         {"client_order_id":bridge.original_ledger.CLIENT_IDS["ACWI"]}),
        ("/v2/account/activities/FILL",
         {"after":"2026-10-01","direction":"asc","page_size":100}),
        ("/v2/account",None),
        ("/v2/positions",None),
        ("/v2/orders",{"status":"open","limit":100}),
        ("/v2/clock",None),
    ]
    calls=[]
    def transport(*,path,params,key,secret):
        assert key==KEY and secret==SECRET
        assert len(calls)<6
        assert (path,params)==expected[len(calls)]
        calls.append(path)
        return deepcopy(docs[len(calls)-1])
    return original,docs,calls,transport

def exercise(monkeypatch,change=None):
    original,docs,calls,transport=source(monkeypatch)
    if change is not None:
        change(original,docs)
    result=bridge.inspect_original_acwi_after_first_attempt(
        signed_prepost_sources=original["signed_prepost_sources"],
        key=KEY,secret=SECRET,
        transport=transport,now_utc=OBSERVED)
    return result,calls

def test_mock_source_exact_six_gets_and_recovery_does_not_authorize_any_trade(monkeypatch):
    result,calls=exercise(monkeypatch)
    assert result["status"]=="BOUNDED_BROKER_GET_ORIGINAL_ACWI_FILL_AND_FLAT_STRUCTURALLY_MATCH"
    assert len(calls)==6
    assert result["broker_GET_count"]==6
    assert result["broker_POST_count"]==result["private_Git_PUT_count"]==0
    assert result["credentialless_injected_transport_used"] is True
    assert result["real_broker_source_authenticated_by_this_adapter"] is False
    assert result["signed_current_private_HEAD_independently_verified"] is False
    assert result["provider_immutable_postsend_HEAD_independently_verified"] is False
    assert result["original_sale_T_plus_one_settled"] is False
    assert result["next_legacy_sell_or_any_live_buy_released"] is False
    assert result["resend_original_ACWI_permitted"] is False
    assert all(result[k] is None for k in ("account_id","order_id",
            "client_order_id","quantity","price","broker_secrets"))
    for value in (KEY,SECRET,FAKE_ACCOUNT):
        assert value not in str(result)

@pytest.mark.parametrize("change",[
    lambda original,docs:docs[0].update(status="partially_filled"),
    lambda original,docs:docs[0].update(client_order_id="foreign"),
    lambda original,docs:docs[0].update(filled_qty="0"),
    lambda original,docs:docs[1].clear(),
    lambda original,docs:docs[1][0].update(side="buy"),
    lambda original,docs:docs[1].extend(deepcopy(docs[1][0]) for _ in range(99)),
    lambda original,docs:docs[2].update(id="different-account"),
    lambda original,docs:docs[3].append({"symbol":"ACWI","qty":"1"}),
    lambda original,docs:docs[3][0].update(qty="999"),
    lambda original,docs:docs[4].append({"symbol":"ACWI","status":"new"}),
    lambda original,docs:docs[5].update(timestamp="2026-10-22T10:00:00Z"),
    lambda original,docs:docs[5].update(is_open=None),
    lambda original,docs:original["signed_prepost_sources"]["prepost_source"].update(sha="0"*40),
])
def test_unreconciled_broker_or_tampered_signed_material_never_passes(monkeypatch,change):
    with pytest.raises(bridge.ReadStop):
        exercise(monkeypatch,change)

def test_first_order_complete_only_after_broker_final_fill_and_flat_both_exist(monkeypatch):
    _original,docs,calls,transport=source(monkeypatch)
    docs[0]["status"]="filled"
    docs[3].append({"symbol":"ACWI","qty":_original["signed_prepost_sources"]["original_qty"]})
    with pytest.raises(bridge.ReadStop):
        bridge.inspect_original_acwi_after_first_attempt(
            signed_prepost_sources=_original["signed_prepost_sources"],
            key=KEY,secret=SECRET,transport=transport,now_utc=OBSERVED)
    assert len(calls)==6

def test_real_clock_observation_occurs_after_final_get_not_before(monkeypatch):
    # A late final broker clock GET is valid, although it happens after
    # the first order/activities GET. A pre-GET observation timestamp would
    # be earlier and falsely reject the clock as future.
    _original,docs,calls,transport=source(monkeypatch)
    docs[5]["timestamp"]=datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    def read(*,path,params):
        return transport(path=path,params=params,key=KEY,secret=SECRET)
    out=bridge._observe(
        read,signed_sources=_original["signed_prepost_sources"],now_utc=None)
    assert out["status"]=="BOUNDED_BROKER_GET_ORIGINAL_ACWI_FILL_AND_FLAT_STRUCTURALLY_MATCH"
    assert len(calls)==6
    assert out["broker_POST_count"]==0


def test_real_broker_network_is_source_hard_locked_before_any_get(monkeypatch):
    original,_,_,_=source(monkeypatch)
    events=[]
    monkeypatch.setattr(bridge.live,"get_json",lambda **kw:events.append("GET"))
    with pytest.raises(bridge.ReadStop,match="HARD LOCKED"):
        bridge.inspect_original_acwi_after_first_attempt(
            signed_prepost_sources=original["signed_prepost_sources"],
            key=KEY,secret=SECRET)
    assert events==[]
    assert bridge.LIVE_BROKER_GET_SOURCE_RELEASED is False

def test_all_source_controls_are_get_only_no_secret_logging_or_cli():
    src=Path(bridge.__file__).read_text()
    assert bridge.NO_BROKER_POST and bridge.NO_PRIVATE_GIT_MUTATION
    assert bridge.NO_SETTLED_CASH_OR_NEXT_TRADE_AUTHORITY
    assert '"/v2/orders:by_client_order_id"' in src
    assert '"/v2/account/activities/FILL"' in src
    assert "proof.assess(" in src
    assert 'LIVE_BROKER_GET_SOURCE_RELEASED=False' in src
    assert "method=\"POST\"" not in src and "method='POST'" not in src
    assert "urlopen(" not in src and "Request(" not in src
    assert "def main(" not in src
