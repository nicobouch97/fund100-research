"""Synthetic-only Actions-private CAS proof; mocked GitHub REST, zero orders."""
from base64 import b64encode
from io import BytesIO
import json
from pathlib import Path
from urllib.error import HTTPError

import pytest

import fund100_v6_s1_actions_private_sandbox_cas_probe_v1_0 as p


SEED_BYTES = (json.dumps(p.INITIAL, indent=2, ensure_ascii=True) + "\n").encode()
assert p._git_sha(SEED_BYTES) == p.INITIAL_SHA


class Response:
    status = 200
    def __init__(self, data):
        self.raw = BytesIO(json.dumps(data).encode())
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n=-1):
        return self.raw.read(n)


class FakePrivateGit:
    def __init__(self, current=SEED_BYTES):
        self.blob = current
        self.methods=[]
        self.writes=0
        self.conflicts=0
    def __call__(self, req, timeout):
        assert timeout == 12
        assert req.full_url in (p.URL, p.READ_URL)
        assert req.get_method() in ("GET", "PUT")
        assert req.get_header("Authorization") == "Bearer fake-PAT-not-real"
        self.methods.append(req.get_method())
        if req.get_method()=="GET":
            assert req.full_url == p.READ_URL
            return Response({
                "path": p.SANDBOX, "type": "file", "encoding": "base64",
                "sha": p._git_sha(self.blob),
                "content": b64encode(self.blob).decode(),
            })
        assert req.full_url == p.URL
        body = json.loads(req.data)
        assert set(body) == {"message", "content", "sha", "branch"}
        assert body["branch"] == "main"
        assert "production" not in req.full_url
        assert "state/v6_s1_original_legacy_sales.json" not in req.full_url
        assert body["sha"] == p.INITIAL_SHA
        assert b64encode(p.DONE_BYTES).decode() == body["content"]
        if body["sha"] != p._git_sha(self.blob):
            self.conflicts += 1
            raise HTTPError(req.full_url, 409, "expected stale source conflict",
                            None, None)
        self.writes += 1
        self.blob=p.DONE_BYTES
        return Response({"content": {"path": p.SANDBOX, "sha": p.DONE_SHA}})


def test_genuine_first_writer_and_stale_second_writer_rejected():
    backend=FakePrivateGit()
    r=p.verify(token="fake-PAT-not-real",transport=backend)
    assert r["status"]=="VERIFIED_PROTECTED_ACTIONS_SANDBOX_CAS"
    assert r["private_actions_write_proven"]
    assert r["sandbox_git_cas_conflict_rejection_proven"]
    assert not r["private_state_production_writer_released"]
    assert not r["original_live_orders_authorized"]
    assert r["broker_requests"]==r["broker_orders"]==0
    assert r["production_private_state_writes"]==0
    assert r["private_sandbox_successful_writes"]==1
    assert backend.methods == ["GET", "PUT", "GET", "PUT"]
    assert backend.writes==1 and backend.conflicts==1


def test_second_run_is_idempotent_and_never_duplicates_any_write():
    backend=FakePrivateGit()
    p.verify(token="fake-PAT-not-real",transport=backend)
    prev_writes=backend.writes
    out=p.verify(token="fake-PAT-not-real",transport=backend)
    assert out["status"]=="ALREADY_COMPLETE_NO_NEW_ACTIONS_WRITE"
    assert not out["private_actions_write_proven"]
    assert out["private_sandbox_successful_writes"]==0
    assert backend.writes==prev_writes


def test_no_token_denies_even_sandbox_get():
    with pytest.raises(p.SandboxCasStop,match="token"):
        p.verify(token="",transport=FakePrivateGit())


def test_modified_unknown_or_reinitialized_seed_refused_without_write():
    for modified in ({**p.INITIAL,"sequence":5},
                     {**p.INITIAL,"broker_orders":1},
                     {**p.INITIAL,"production_state_touched":True},
                     {**p.INITIAL,"purpose":"SOMETHING_ELSE"}):
        backend=FakePrivateGit(
            (json.dumps(modified,indent=2)+"\n").encode())
        with pytest.raises(p.SandboxCasStop):
            p.verify(token="fake-PAT-not-real",transport=backend)
        assert backend.writes==0


def test_unapproved_git_method_and_payload_rejected():
    with pytest.raises(p.SandboxCasStop,match="method"):
        p._request(method="POST",token="test")
    with pytest.raises(p.SandboxCasStop,match="Method/payload"):
        p._request(method="PUT",token="test",body=None)
    with pytest.raises(p.SandboxCasStop,match="Method/payload"):
        p._request(method="GET",token="test",body={})


def test_private_source_b64_sha_must_match():
    for source in (
        {"path":p.SANDBOX, "type":"file","encoding":"base64",
         "content":b64encode(SEED_BYTES).decode(), "sha":"0"*40},
        {"path":"state/v6_s1_original_legacy_sales.json","type":"file",
         "encoding":"base64", "content":b64encode(SEED_BYTES).decode(),
         "sha":p.INITIAL_SHA},
    ):
        with pytest.raises(p.SandboxCasStop):
            p._source(source)


def test_stale_put_unexpected_acceptance_is_a_hard_failure():
    class BrokenGit(FakePrivateGit):
        def __call__(self, req, timeout):
            if req.get_method()=="PUT" and self.writes==1:
                return Response({"content":{"path":p.SANDBOX,"sha":p.DONE_SHA}})
            return super().__call__(req,timeout)
    backend=BrokenGit()
    with pytest.raises(p.SandboxCasStop, match="unexpectedly accepted"):
        p.verify(token="fake-PAT-not-real",transport=backend)


def test_no_original_financial_or_broker_access():
    content=Path(p.__file__).read_text()
    for text in ("FUND100_PRIVATE_STATE_READ_TOKEN",
                 "ALPACA_LIVE_KEY", "ALPACA_LIVE_SECRET",
                 "api.alpaca.markets", "place_order(", "/v2/orders",
                 '"state/v6_s1_original_legacy_sales.json"'):
        assert text not in content
    assert p.BROKER_ACCESS is False
    assert p.PRODUCTION_STATE_ACCESS is False
    assert p.PRODUCTION_LEDGER_INITIALIZATION is False
    assert p.LIVE_TRADING_AUTHORITY is False
