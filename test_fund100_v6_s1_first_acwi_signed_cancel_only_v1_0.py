"""No-network regression tests for exact signed original ACWI cancellation.

Only fake Alpaca GET/DELETE; no live credentials or private Git requests.
"""
from uuid import uuid4
from pathlib import Path

import pytest

import fund100_v6_s1_first_acwi_signed_cancel_only_v1_0 as c
import audit_fund100_live_boundary as audit


def original(order_id=None, **replace):
    item = {"id":str(order_id or uuid4()), "symbol":"ACWI", "side":"sell",
            "client_order_id":c.SIGNED_FIRST_ACWI_CLIENT_ID}
    item.update(replace)
    return item


def test_v5_emergency_source_remains_immutably_pinned():
    pin = audit.PINNED_LIVE_CREDENTIAL_JOBS[(
        ".github/workflows/fund100-live-emergency-stop.yml",
        "fund100_live_emergency_stop_v1_0.py")]
    assert pin == audit.git_blob_digest(Path("fund100_live_emergency_stop_v1_0.py"))
    assert pin == "5ef6fb7c8e01a8f002b6167aca28c89590931767"
    assert c.SIGNED_FIRST_ACWI_CLIENT_ID == c.signed.CLIENT_IDS["ACWI"]
    assert c.SIGNED_FIRST_ACWI_CLIENT_ID not in [
        c.signed.CLIENT_IDS["EEM"], c.signed.CLIENT_IDS["XLV"]]


def test_empty_broker_orders_no_delete(monkeypatch):
    calls = []
    def fake(method, path):
        calls.append((method,path))
        assert method == "GET" and path == c.OPEN_ORDERS_PATH
        return []
    monkeypatch.setattr(c.v5_emergency,"_alpaca_request",fake)
    assert c.cancel_open_first_signed_acwi_orders() == 0
    assert calls == [("GET",c.OPEN_ORDERS_PATH)] * 2


def test_exact_original_signed_acwi_sell_cancelled_selectively(monkeypatch):
    ours, manual, other = str(uuid4()), str(uuid4()), str(uuid4())
    listing = iter([
        [original(ours), {"id":manual,"client_order_id":"manual","symbol":"ACWI","side":"sell"},
         {"id":other,"client_order_id":c.signed.CLIENT_IDS["EEM"],"symbol":"EEM","side":"sell"}],
        [{"id":manual,"client_order_id":"manual"}, {"id":other,"client_order_id":c.signed.CLIENT_IDS["EEM"]}],
    ])
    calls = []
    def fake(method,path):
        calls.append((method,path))
        if method=="GET":
            assert path == c.OPEN_ORDERS_PATH
            return next(listing)
        assert method=="DELETE" and path=="/v2/orders/"+ours
        return None
    monkeypatch.setattr(c.v5_emergency,"_alpaca_request",fake)
    assert c.cancel_open_first_signed_acwi_orders()==1
    assert calls==[("GET",c.OPEN_ORDERS_PATH),("DELETE","/v2/orders/"+ours),
                   ("GET",c.OPEN_ORDERS_PATH)]


@pytest.mark.parametrize("bad", [
    None, {}, ["bad"], [{}]*500, [None],
    [original(**{"id":"not-a-uuid"})],
    [original(**{"symbol":"EEM"})],
    [original(**{"side":"buy"})],
    [original(**{"side":None})],
    [original(**{"client_order_id":c.SIGNED_FIRST_ACWI_CLIENT_ID,"id":None})],
    [original(order_id="123")],
])
def test_untrusted_open_orders_fail_before_any_delete(monkeypatch,bad):
    calls=[]
    def fake(method,path):
        calls.append((method,path))
        assert method=="GET"
        return bad
    monkeypatch.setattr(c.v5_emergency,"_alpaca_request",fake)
    with pytest.raises(c.FirstAcwiCancelStop):
        c.cancel_open_first_signed_acwi_orders()
    assert calls==[("GET",c.OPEN_ORDERS_PATH)]


def test_duplicate_signed_acwi_order_id_is_rejected(monkeypatch):
    item=original()
    monkeypatch.setattr(c.v5_emergency,"_alpaca_request",lambda method,path:[item,item])
    with pytest.raises(c.FirstAcwiCancelStop,match="Duplicate"):
        c.cancel_open_first_signed_acwi_orders()


def test_multiple_distinct_orders_with_same_signed_id_are_rejected(monkeypatch):
    x=[original(),original()]
    monkeypatch.setattr(c.v5_emergency,"_alpaca_request",lambda method,path:x)
    with pytest.raises(c.FirstAcwiCancelStop,match="Duplicate"):
        c.cancel_open_first_signed_acwi_orders()


def test_unrelated_v6_signed_id_not_selected(monkeypatch):
    item = original(client_order_id=c.signed.CLIENT_IDS["XLV"],symbol="XLV")
    monkeypatch.setattr(c.v5_emergency,"_alpaca_request",
        lambda method,path: [item] if method=="GET" else pytest.fail("wrong delete"))
    assert c.cancel_open_first_signed_acwi_orders()==0


def test_no_ack_after_delete_must_not_claim_success(monkeypatch):
    item=original()
    calls=[]
    def fake(method,path):
        calls.append((method,path))
        return [item] if method=="GET" else None
    monkeypatch.setattr(c.v5_emergency,"_alpaca_request",fake)
    monkeypatch.setattr(c.time,"sleep",lambda seconds:None)
    with pytest.raises(c.FirstAcwiCancelStop,match="remains open"):
        c.cancel_open_first_signed_acwi_orders()
    assert sum(method=="DELETE" for method,_ in calls)==1
    assert sum(method=="GET" for method,_ in calls)==6


def test_broker_error_is_not_swallowed_or_reported_as_success(monkeypatch):
    def fail(method,path):
        raise c.v5_emergency.EmergencyStopError("broker unavailable")
    monkeypatch.setattr(c.v5_emergency,"_alpaca_request",fail)
    with pytest.raises(c.v5_emergency.EmergencyStopError):
        c.cancel_open_first_signed_acwi_orders()


def test_source_never_posts_or_unstops_or_liquidates():
    src=Path(c.__file__).read_text()
    assert c.NO_BROKER_POST and c.NO_LIQUIDATION and c.NO_OPERATOR_WRITE
    assert '_alpaca_request("GET"' in src
    assert '"DELETE"' in src and '"POST"' not in src
    assert "fund100_live_emergency_stop_v1_0 as v5_emergency" in src
    assert "fund100_v6_s1_private_git_cas_protocol_v1_0 as signed" in src
    assert "FUND100_BROKER_KILL_SWITCH" not in src
