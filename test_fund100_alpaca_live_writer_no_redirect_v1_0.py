"""Direct Trading API writer HTTPS boundary, synthetic HTTP ONLY.

The actual v1.1 candidate remains release-locked. Each test monkeypatches
only the selected method's guard and uses an in-memory, no-network opener.
"""
from io import BytesIO
import json
from urllib.error import HTTPError
from urllib.request import Request

import pytest

import fund100_alpaca_live_writer_candidate_v1_1 as w

KEY="OFFLINE_NOT_REAL_LIVE_KEY"
SECRET="OFFLINE_NOT_REAL_LIVE_SECRET"
CID="f100live-123456789abc-b-acwi"


class Response:
    def __init__(self, url, payload, status):
        self.url=url
        self.data=BytesIO(payload)
        self.status=status
    def __enter__(self):
        return self
    def __exit__(self,*args):
        self.data.close()
    def geturl(self):
        return self.url
    def read(self,n=-1):
        return self.data.read(n)


@pytest.fixture
def scoped(monkeypatch):
    # Never change release constants on main. This fixture is isolated.
    monkeypatch.setattr(w,"require_transport_released",lambda:None)
    monkeypatch.setattr(w,"validate_credentials",lambda *args:None)
    monkeypatch.setattr(w,"build_order_payload",lambda intent:{
        "symbol":"ACWI","side":"buy","type":"market",
        "time_in_force":"day","notional":"12.00","client_order_id":CID
    })
    monkeypatch.setattr(w,"validate_submitted_order_response",
                        lambda response,intent:response)


def request(monkeypatch,method,*,status=200,url=None,body=None):
    requests=[]
    def build(*handlers):
        assert len(handlers)==1 and isinstance(handlers[0],w._NoRedirect)
        class Opener:
            def open(self,r,timeout=None):
                requests.append(r)
                assert timeout==20
                assert r.get_method()==method
                assert r.full_url.startswith("https://api.alpaca.markets/v2/orders")
                assert r.get_header("Apca-api-key-id")==KEY
                assert r.get_header("Apca-api-secret-key")==SECRET
                return Response(url or r.full_url,body or b'{"status":"new"}',status)
        return Opener()
    monkeypatch.setattr(w,"build_opener",build)
    return requests


def test_direct_lookup_uses_exact_broker_https_no_redirect(scoped,monkeypatch):
    calls=request(monkeypatch,"GET",body=b'{"id":"test"}')
    assert w._get_order_by_client_id(CID,KEY,SECRET)=={"id":"test"}
    assert len(calls)==1
    assert calls[0].full_url.startswith(
        "https://api.alpaca.markets/v2/orders:by_client_order_id?")


def test_direct_market_post_uses_exact_broker_https_no_redirect(
        scoped,monkeypatch):
    calls=request(monkeypatch,"POST",status=201)
    result=w._post_live_market_order({"symbol":"ACWI","side":"buy",
                                      "client_order_id":CID},KEY,SECRET)
    assert result=={"status":"new"}
    assert len(calls)==1
    assert calls[0].full_url=="https://api.alpaca.markets/v2/orders"
    assert json.loads(calls[0].data.decode("utf-8"))["client_order_id"]==CID


def test_redirect_handler_prevents_live_key_exfiltration():
    # A credential-bearing GET demonstrates redirect rejection without adding
    # an executable POST Request fixture outside the reviewed writer boundary.
    req=Request("https://api.alpaca.markets/v2/orders",
                method="GET",
                headers={"APCA-API-KEY-ID":KEY,"APCA-API-SECRET-KEY":SECRET})
    with pytest.raises(w.LiveWriterCandidateLocked,match="redirect forbidden"):
        w._NoRedirect().redirect_request(req,None,302,"Found",{},
                                          "https://untrusted.invalid/steal")


@pytest.mark.parametrize("method,path,expected",[
    ("GET", "https://untrusted.invalid/v2/orders", "origin"),
    ("POST","https://untrusted.invalid/v2/orders", "origin"),
    ("GET", "http://api.alpaca.markets/v2/orders", "origin"),
    ("POST","https://api.alpaca.markets/v2/other", "origin"),
])
def test_foreign_response_url_is_rejected_without_resending(
        scoped,monkeypatch,method,path,expected):
    calls=request(monkeypatch,method,url=path,status=201 if method=="POST" else 200)
    with pytest.raises(w.LiveWriterCandidateLocked,match=expected):
        if method=="GET":
            w._get_order_by_client_id(CID,KEY,SECRET)
        else:
            w._post_live_market_order({"symbol":"ACWI","side":"buy",
                                       "client_order_id":CID},KEY,SECRET)
    assert len(calls)==1


@pytest.mark.parametrize("method,status",[
    ("GET",201),("GET",204),("GET",302),("GET",400),
    ("POST",202),("POST",204),("POST",302),("POST",500),
])
def test_unexpected_broker_status_fails_closed_once(
        scoped,monkeypatch,method,status):
    calls=request(monkeypatch,method,status=status)
    with pytest.raises(w.LiveWriterCandidateLocked,match="status"):
        if method=="GET":
            w._get_order_by_client_id(CID,KEY,SECRET)
        else:
            w._post_live_market_order({"symbol":"ACWI","side":"buy",
                                       "client_order_id":CID},KEY,SECRET)
    assert len(calls)==1


@pytest.mark.parametrize("method",["GET","POST"])
def test_response_limit_denies_oversized_broker_data(
        scoped,monkeypatch,method):
    calls=request(monkeypatch,method,
                  status=201 if method=="POST" else 200,
                  body=b"x"*(w.MAX_BROKER_ORDER_RESPONSE_BYTES+1))
    with pytest.raises(w.LiveWriterCandidateLocked,match="oversized"):
        if method=="GET":
            w._get_order_by_client_id(CID,KEY,SECRET)
        else:
            w._post_live_market_order({"symbol":"ACWI","side":"buy",
                                       "client_order_id":CID},KEY,SECRET)
    assert len(calls)==1


def test_original_v6_fractional_writer_still_hard_locked(monkeypatch):
    from pathlib import Path
    src=Path(w.__file__).read_text()
    assert "TRANSPORT_RELEASED = False" in src
    assert "PUBLIC_EXECUTION_ENABLED = False" in src
    assert "sender=(build_opener(_NoRedirect()).open" in src
    assert "transport is None and response.geturl() != url" in src
    assert "sender=urlopen" not in src
    assert "with urlopen(" not in src
    assert "ONE and only one POST request" in src


def test_direct_market_writer_flags_not_released():
    assert w.TRANSPORT_RELEASED is False
    assert w.PUBLIC_EXECUTION_ENABLED is False
    assert w.LIVE_BASE_URL == "https://api.alpaca.markets"
