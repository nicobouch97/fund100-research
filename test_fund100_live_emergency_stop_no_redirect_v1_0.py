"""No-network transport security regression for LIVE Alpaca emergency STOP.

Tests invoke only synthetic openers/responses. No broker requests or actual
STOP actions; no keys saved to GitHub, Railway or log outputs.
"""
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request
from uuid import uuid4

import pytest

import fund100_live_emergency_stop_v1_0 as stop

KEY = "OFFLINE_KEY_NOT_REAL"
SECRET = "OFFLINE_SECRET_NOT_REAL"


@pytest.fixture(autouse=True)
def fake_auth(monkeypatch):
    monkeypatch.setenv("ALPACA_LIVE_KEY", KEY)
    monkeypatch.setenv("ALPACA_LIVE_SECRET", SECRET)


class FakeResponse:
    def __init__(self, body=b"[]", *, url=None, status=200):
        self.status = status
        self._body = BytesIO(body)
        self.url = url
    def geturl(self):
        return self.url
    def read(self, size=-1):
        return self._body.read(size)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self._body.close()


def intercept(monkeypatch, *, status=200, body=b"[]", url_override=None):
    requests=[]
    def fake_opener(*handlers):
        assert len(handlers)==1
        assert isinstance(handlers[0], stop._NoRedirect)
        class Opener:
            def open(self, request, timeout=None):
                requests.append(request)
                assert timeout == 15
                assert request.get_header("Apca-api-key-id") == KEY
                assert request.get_header("Apca-api-secret-key") == SECRET
                assert request.full_url.startswith("https://api.alpaca.markets/")
                return FakeResponse(body,url=url_override or request.full_url,
                                    status=status)
        return Opener()
    monkeypatch.setattr(stop,"build_opener",fake_opener)
    return requests


def test_exact_get_orders_and_bounded_response(monkeypatch):
    requests=intercept(monkeypatch)
    assert stop._alpaca_request("GET",stop.EXACT_OPEN_ORDERS_PATH)==[]
    assert len(requests)==1
    assert requests[0].get_method()=="GET"
    assert requests[0].full_url==stop.LIVE_HOST+stop.EXACT_OPEN_ORDERS_PATH


def test_exact_uuid_delete_only(monkeypatch):
    requests=intercept(monkeypatch,status=204,body=b"")
    uid=str(uuid4())
    assert stop._alpaca_request("DELETE","/v2/orders/"+uid) is None
    assert len(requests)==1 and requests[0].get_method()=="DELETE"


@pytest.mark.parametrize("method,path",[
    ("POST","/v2/orders"),
    ("PATCH","/v2/orders/00000000-0000-0000-0000-000000000001"),
    ("GET","/v2/account"),
    ("GET","/v2/orders?status=all&limit=500"),
    ("GET","/v2/orders?status=open&limit=501"),
    ("GET","/v2/orders/00000000-0000-0000-0000-000000000001"),
    ("DELETE","/v2/orders"),
    ("DELETE","/v2/orders/../../positions"),
    ("DELETE","/v2/orders/00000000-0000-0000-0000-000000000001?all=1"),
    ("DELETE","/v2/orders/not-an-order-uuid"),
    ("DELETE","/v2/orders/00000000-0000-0000-0000-000000000001/replace"),
    ("DELETE","https://evil.invalid/v2/orders/00000000-0000-0000-0000-000000000001"),
    ("DELETE","/v2/orders/00000000-0000-0000-0000-00000000000A"),
])
def test_invalid_paths_never_access_credentials_or_transport(monkeypatch,method,path):
    monkeypatch.setattr(stop,"build_opener",lambda *args:pytest.fail("network attempted"))
    monkeypatch.delenv("ALPACA_LIVE_KEY")
    monkeypatch.delenv("ALPACA_LIVE_SECRET")
    with pytest.raises(stop.EmergencyStopError,match="Unapproved|Unsupported"):
        stop._alpaca_request(method,path)


def test_http_redirect_is_rejected_before_target_request():
    req=Request(stop.LIVE_HOST+stop.EXACT_OPEN_ORDERS_PATH,method="GET",
                headers={"APCA-API-KEY-ID":KEY,"APCA-API-SECRET-KEY":SECRET})
    with pytest.raises(stop.EmergencyStopError,match="redirect forbidden"):
        stop._NoRedirect().redirect_request(
            req, object(), 302, "Found", {},
            "https://evil.invalid/steal-credentials")


@pytest.mark.parametrize("location",[
    "https://evil.invalid/v2/orders?status=open&limit=500",
    "http://api.alpaca.markets/v2/orders?status=open&limit=500",
    "https://api.alpaca.markets/v2/orders?status=open&limit=500&unreviewed=1",
])
def test_unexpected_response_origin_is_never_accepted(
        monkeypatch,location):
    intercept(monkeypatch,url_override=location)
    with pytest.raises(stop.EmergencyStopError,match="origin"):
        stop._alpaca_request("GET",stop.EXACT_OPEN_ORDERS_PATH)


@pytest.mark.parametrize("status", [201,202,204,301,302,307,308,400,500])
def test_unexpected_get_status_is_not_a_broker_orders_listing(monkeypatch,status):
    intercept(monkeypatch,status=status)
    with pytest.raises(stop.EmergencyStopError,match="status"):
        stop._alpaca_request("GET",stop.EXACT_OPEN_ORDERS_PATH)


@pytest.mark.parametrize("status",[200,202,204])
def test_accepted_delete_response_is_only_request_ack(
        monkeypatch,status):
    intercept(monkeypatch,status=status,body=b"")
    assert stop._alpaca_request(
        "DELETE","/v2/orders/"+str(uuid4())) is None


def test_oversized_or_invalid_get_response_is_not_proof(monkeypatch):
    intercept(monkeypatch,body=b"0"*(stop.MAX_RESPONSE_BYTES+1))
    with pytest.raises(stop.EmergencyStopError,match="oversized"):
        stop._alpaca_request("GET",stop.EXACT_OPEN_ORDERS_PATH)
    intercept(monkeypatch,body=b"{no JSON")
    with pytest.raises(stop.EmergencyStopError,match="Invalid Alpaca response"):
        stop._alpaca_request("GET",stop.EXACT_OPEN_ORDERS_PATH)


@pytest.mark.parametrize("status",[404,422])
def test_delete_fill_cancel_race_must_reconcile_fresh_open_orders(
        monkeypatch,status):
    requests=[]
    def fake(*args):
        class Opener:
            def open(self,request,timeout=None):
                requests.append(request.get_method())
                if request.get_method()=="DELETE":
                    raise HTTPError(request.full_url,status,"race",{},None)
                return FakeResponse(b"[]",url=request.full_url,status=200)
        return Opener()
    monkeypatch.setattr(stop,"build_opener",fake)
    assert stop._alpaca_request("DELETE","/v2/orders/"+str(uuid4())) is None
    assert stop._alpaca_request("GET",stop.EXACT_OPEN_ORDERS_PATH)==[]
    assert requests == ["DELETE","GET"]


def test_emergency_stop_cannot_report_cancellation_when_get_remains_open(
        monkeypatch):
    uid=str(uuid4())
    calls=[]
    def unconfirmed(method,path):
        calls.append(method)
        if method=="GET":
            return [{"id":uid,"client_order_id":"f100live-123456789abc-s-acwi"}]
        return None
    monkeypatch.setattr(stop,"_alpaca_request",unconfirmed)
    monkeypatch.setattr(stop.time,"sleep",lambda _:None)
    with pytest.raises(stop.EmergencyStopError,match="remain"):
        stop.cancel_open_fund100_orders()
    assert calls.count("DELETE")==1
    assert calls.count("GET")==6


def test_offline_source_never_place_trade_or_other_account_delete():
    from pathlib import Path
    source=Path(stop.__file__).read_text()
    assert "from urllib.request import Request, build_opener, HTTPRedirectHandler" in source
    assert "urlopen(" not in source
    assert 'method="POST"' not in source
    assert "EXACT_ORDER_DELETE.fullmatch(path)" in source
    assert "resp.geturl() != url" in source
    assert "max-age=0" not in source
