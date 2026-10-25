"""Separate original V6 HIGH sell-only operator latch, independent of frozen V5.

The original V5 tracked STOP must remain FALSE forever for signed V5
bootstrap/legacy proof. V6 gets its own current-main GitHub-backed STOP
that emergency-stop can revoke without modifying the historical V5 source.

Read-only in normal use. The only write is a STOP (true -> false) signal.
Never enables V6 trading, publishes a release or touches Alpaca. Every
unavailable, malformed, redirected or stale GitHub response means STOP.
"""
from __future__ import annotations

import base64
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

SCHEMA="FUND100_V6_S1_OPERATOR_CONTROL_V2"
PATH="fund100_v6_s1_operator_control.json"
API="https://api.github.com/repos/nicobouch97/fund100-research/contents/"+PATH
EXPECTED_REPO="nicobouch97/fund100-research"
MAX_BYTES=3000
NO_ACTIVATION_WRITE=True
NO_BROKER_NETWORK=True

class V6OperatorStop(RuntimeError):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise V6OperatorStop("V6 current main operator redirected; STOP")

def _token(*,write=False):
    if (os.environ.get("GITHUB_REPOSITORY")!=EXPECTED_REPO
        or os.environ.get("GITHUB_REF")!="refs/heads/main"):
        raise V6OperatorStop("V6 operator not on original main")
    token=os.environ.get("GITHUB_TOKEN","")
    if (type(token) is not str or len(token.strip())<10 or
        token!=token.strip() or "\r" in token or "\n" in token):
        raise V6OperatorStop("Missing scoped GitHub main operator credential")
    if write and os.environ.get("GITHUB_EVENT_NAME")!="workflow_dispatch":
        raise V6OperatorStop("STOP may only be committed by manual emergency workflow")
    return token

def _request(*,method,token,raw=None,transport=None):
    if method not in ("GET","PUT") or method=="PUT" and raw is None:
        raise V6OperatorStop("Only V6 current GET / STOP-only PUT approved")
    url=API+("?ref=main&nonce="+str(time.time_ns()) if method=="GET" else "")
    h={"Accept":"application/vnd.github+json",
       "Authorization":"Bearer "+token,
       "X-GitHub-Api-Version":"2022-11-28",
       "Cache-Control":"no-store, no-cache",
       "User-Agent":"fund100-v6-s1-independent-stop"}
    if raw is not None:
        if type(raw) is not bytes or len(raw)>MAX_BYTES:
            raise V6OperatorStop("Oversized V6 STOP payload")
        h["Content-Type"]="application/json"
    req=Request(url,method=method,data=raw,headers=h)
    sender=build_opener(NoRedirect()).open if transport is None else transport
    try:
        with sender(req,timeout=12) as resp:
            if getattr(resp,"status",None)!=({"GET":200,"PUT":200}[method]):
                raise V6OperatorStop("Original V6 operator GitHub status failed")
            body=resp.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:
            raise V6OperatorStop("V6 operator Github response too large")
        doc=json.loads(body)
        if type(doc) is not dict:
            raise V6OperatorStop("V6 operator GitHub response malformed")
        return doc
    except (HTTPError,URLError,TimeoutError,OSError,UnicodeError,ValueError):
        raise V6OperatorStop("V6 operator network unknown; STOP") from None

def _parse(source):
    if (type(source) is not dict or source.get("path")!=PATH
        or source.get("type")!="file"
        or source.get("encoding")!="base64"
        or type(source.get("sha")) is not str
        or len(source["sha"])!=40
        or type(source.get("content")) is not str):
        raise V6OperatorStop("V6 operator main blob missing")
    try:
        raw=base64.b64decode(
            source["content"].replace("\n",""),validate=True)
        from hashlib import sha1
        actual=sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()
        if actual!=source["sha"] or len(raw)>1000:
            raise V6OperatorStop("V6 operator Git object SHA changed")
        value=json.loads(raw)
    except Exception:
        raise V6OperatorStop("Invalid V6 operator SHA or payload") from None
    _validate(value)
    return value

def _validate(obj):
    if (type(obj) is not dict or set(obj)!={
        "schema","risk_level","pilot_capital_ceiling_usd",
        "trading_enabled","first_original_acwi_sell_enabled"}
        or obj.get("schema")!=SCHEMA
        or obj.get("risk_level")!="HIGH"
        or obj.get("pilot_capital_ceiling_usd")!="130.30"
        or type(obj.get("trading_enabled")) is not bool
        or type(obj.get("first_original_acwi_sell_enabled")) is not bool):
        raise V6OperatorStop("V6 STOP/HIGH policy schema invalid")
    if obj["first_original_acwi_sell_enabled"] and not obj["trading_enabled"]:
        raise V6OperatorStop("Inconsistent V6 operator GO state")
    return obj

def read_current_control(*,transport=None):
    token=_token()
    doc=_request(method="GET",token=token,transport=transport)
    return _parse(doc)

def require_s1_running(*,transport=None):
    # Independent current GitHub GO cannot alter original V5 operator STOP.
    # The active seven-GET reader separately verifies V5 STOP around calls.
    current=read_current_control(transport=transport)
    if (current["trading_enabled"] is not True
        or current["first_original_acwi_sell_enabled"] is not True):
        raise V6OperatorStop("V6 first ACWI operator STOP engaged")
    return True

def commit_stop_signal(*,transport=None):
    """Emergency-only V6 latch: cannot turn ON trading.

    No retries after unknown PUT; emergency order-cancel job still runs via
    'if: always()' if this fails. Re-dispatching a STOP is idempotent.
    """
    token=_token(write=True)
    existing=_request(method="GET",token=token,transport=transport)
    before=_parse(existing)
    if (before["trading_enabled"] is False
        and before["first_original_acwi_sell_enabled"] is False):
        return "ALREADY_STOPPED"
    safe=dict(before,trading_enabled=False,first_original_acwi_sell_enabled=False)
    _validate(safe)
    raw=(json.dumps(safe,sort_keys=True,indent=2)+"\n").encode()
    payload=json.dumps({
        "branch":"main","sha":existing["sha"],
        "message":"EMERGENCY STOP: disable original V6-S1 ACWI trade authorization",
        "content":base64.b64encode(raw).decode("ascii"),
    },sort_keys=True).encode()
    _request(method="PUT",token=token,raw=payload,transport=transport)
    confirmed=read_current_control(transport=transport)
    if confirmed["trading_enabled"] or confirmed["first_original_acwi_sell_enabled"]:
        raise V6OperatorStop("V6 STOP not confirmed on main")
    return "STOPPED"
