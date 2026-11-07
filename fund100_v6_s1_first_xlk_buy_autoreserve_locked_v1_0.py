"""Automatic FIRST XLK BUY private seq0 CREATE -> seq1 signed RESERVE.

Original ACWI full FILL is never assumed: each mutation is preceded by the
genuine current private signed ACWI seq2, provider-immutable asset and the
original entire authenticated broker-fill/cash/6-20-35 HIGH risk gate.
This stage NEVER places an order. It prepares the separate first BUY private
file, which the existing first XLK single-POST writer requires at seq1.

Production source is code-hard-locked and has no installed funded workflow.
This is not permission to buy, and the user need not manage GitHub files.
Private file creation only occurs with remote ABSENCE from two separate
principals; GitHub 201 creates from NO sha, while 200 only updates the
fresh observed blob SHA. Any ambiguous read/write/timeout/concurrency is
a permanent STOP for the invocation. A subsequent fresh protected run may
complete a safely created seq0 (never previously POSTed); a reserved seq1
is idempotent and cannot be enlarged or reissued. A seq2 possible POST
is NEVER resumed.
"""
from __future__ import annotations

from base64 import b64decode
from hashlib import sha256
import json
from urllib.error import HTTPError,URLError
from urllib.request import Request,build_opener

import fund100_v6_s1_first_xlk_buy_atomic_writer_locked_v1_0 as writer
import fund100_v6_s1_first_xlk_buy_cas_offline_v1_0 as buy

SCHEMA="FUND100_V6_S1_FIRST_XLK_BUY_SOURCE_AUTHENTICATED_AUTORESERVE_LOCKED_V1"
AUTORESERVE_RUNTIME_RELEASED=False
NO_ALPACA_ORDER_POST=True
NO_ORIGINAL_ACWI_RETRY=True
NO_NEW_BUY_CLIENT_ID=True
MAX_FIRST_BUY_RESERVATIONS=1

class AutoReserveStop(RuntimeError):
    pass

def _locked():
    # Future reviewed release is SEPARATE from the actual writer and all
    # 1x GET/immutable/owner/GO switches, which remain code hard locked.
    if (AUTORESERVE_RUNTIME_RELEASED is not True
        or writer.RUNTIME_RELEASED is not True
        or writer.BROKER_BUY_POST_RELEASED is not True
        or writer.RESTART_OR_RESUBMIT_RELEASED is not False
        or writer.MAX_FIRST_BUY_POSTS!=1):
        raise AutoReserveStop("First BUY private state autoreserve HARD LOCKED")
    writer._locked()

def _git(*,token,method,body=None,transport=None,allow_missing=False):
    url=writer.GITHUB_BUY_CONTENTS_URL
    if method=="GET":
        url+="?ref=main"
    elif method!="PUT":
        raise AutoReserveStop("Only private BUY GET and CAS PUT are admitted")
    request=Request(
        url,method=method,
        data=body,
        headers={
            **writer._gh_headers(token),
            **({"Content-Type":"application/json"} if method=="PUT" else {})
        })
    send=(build_opener(writer.NoRedirect()).open
          if transport is None else transport)
    try:
        with send(request,timeout=15) as response:
            status=getattr(response,"status",None)
            if (method=="GET" and status!=200
                or method=="PUT" and status not in (200,201)):
                raise AutoReserveStop("Private first BUY CAS status unqualified")
            raw=response.read(16385)
        if len(raw)>16384:
            raise AutoReserveStop("First BUY private response too large")
        doc=json.loads(raw)
        if type(doc) is not dict:
            raise AutoReserveStop("Malformed private first BUY response")
        return (status,doc)
    except HTTPError as e:
        if method=="GET" and allow_missing and e.code==404:
            return (404,None)
        raise AutoReserveStop("Private first BUY CAS HTTP uncertain; HOLD") from None
    except (URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise AutoReserveStop("Private first BUY CAS network uncertain; HOLD") from None

def _read_both(*,read_token,write_token,transport):
    a,src=_git(token=read_token,method="GET",
               transport=transport,allow_missing=True)
    b,other=_git(token=write_token,method="GET",
                 transport=transport,allow_missing=True)
    if a==b==404:
        return None
    if a!=200 or b!=200 or type(src) is not dict or type(other) is not dict:
        raise AutoReserveStop("First BUY private source dual-principal conflict")
    if (src.get("sha")!=other.get("sha")
        or src.get("path")!=other.get("path")
        or src.get("content")!=other.get("content")
        or src.get("type")!=other.get("type")):
        raise AutoReserveStop("First BUY private HEAD two-principal mismatch")
    return src

def _proof(*,key,source_kwargs,amount,cost,read_token,write_token,
           broker_key,broker_secret,private_transport,broker_transport):
    writer._op_go()
    signed=writer._get_both(
        url=writer.GITHUB_ORIGINAL_CONTENTS_URL,
        read_token=read_token,write_token=write_token,
        transport=private_transport)
    binding=writer.witness.verify()
    sha,doc=writer.original._read_source(
        signed,private_genesis=binding["original_public_genesis_nonce"],
        account_binding_sha256=binding["original_live_account_binding_sha256"],
        key=key)
    if (doc.get("sequence")!=2
        or set(doc.get("entries",{}))!={"ACWI"}
        or doc["entries"]["ACWI"]["state"]!="POST_MAY_HAVE_BEEN_SENT"):
        raise AutoReserveStop("Original ACWI first-sale signed seq2 not present")
    asset=writer.anchor._get(
        url=writer.anchor.DOWNLOAD_URL,token=None,
        accept="application/octet-stream",
        limit=writer.anchor.MAX_ASSET_BYTES)
    args={
        "account_binding_sha256":binding["original_live_account_binding_sha256"],
        "original_private_genesis":binding["original_public_genesis_nonce"],
        "original_acwi_seq2_blob_sha":sha,
        "original_immutable_asset_sha256":sha256(asset).hexdigest(),
        "key":key,
    }
    writer._risk_go(
        source_kwargs=source_kwargs,amount=amount,cost=cost,
        broker_key=broker_key,broker_secret=broker_secret)
    if writer._by_client(key=broker_key,secret=broker_secret,
                         transport=broker_transport) is not None:
        raise AutoReserveStop("Original first XLK BUY broker ID already exists")
    writer._op_go()
    return args

def _write(*,token,content,expected_sha,transport):
    body={
        "branch":"main",
        "message":"fund100: FIRST original XLK BUY signed private reservation NO ORDER",
        "content":content,
    }
    if expected_sha is not None:
        body["sha"]=expected_sha
    status,response=_git(
        token=token,method="PUT",
        body=json.dumps(body,sort_keys=True,separators=(",",":")).encode("ascii"),
        transport=transport)
    if status!=(201 if expected_sha is None else 200):
        raise AutoReserveStop("First BUY creation/update not exclusive CAS")
    if (type(response.get("content")) is not dict
        or type(response["content"].get("sha")) is not str):
        raise AutoReserveStop("First BUY private CAS provider reply unknown")
    return response["content"]["sha"]

def autoreserve(*,amount_usd:str,cost_usd:str,
                private_read_token:str,private_write_token:str,
                public_read_token:str,broker_key:str,broker_secret:str,
                hmac_key:bytes,source_kwargs:dict,
                private_transport=None,broker_transport=None):
    """Real GET+PUT only if independently source-released in a future job.

    Same fixed client ID/amount and signed original ACWI seq2 SHA forever.
    No executable BUY order, no broker POST, no status-dependent retry.
    """
    _locked()  # first statement, all current production source locks FALSE
    injected=(private_transport is not None or broker_transport is not None)
    if injected and (
        AUTORESERVE_RUNTIME_RELEASED is not False
        or writer.RUNTIME_RELEASED is not False
        or writer.BROKER_BUY_POST_RELEASED is not False
        or not callable(private_transport)
        or not callable(broker_transport)):
        raise AutoReserveStop("First BUY real reservation forbids fake transports")
    writer._distinct(
        private_read_token,private_write_token,public_read_token,
        broker_key,broker_secret)
    if type(hmac_key) is not bytes or len(hmac_key)<32:
        raise AutoReserveStop("Original ACWI/BUY HMAC verifier missing")
    amount=buy._cent(amount_usd,"BUY amount")
    cost=buy._cent(cost_usd,"all-in cost")
    if (amount<buy.MIN_NOTIONAL or amount>buy.MAX_NOTIONAL
        or cost>amount*buy.MAX_COST_FRAC):
        raise AutoReserveStop("First BUY amount/cost cap exceeded")
    amount=format(amount,".2f")
    cost=format(cost,".2f")
    kwargs=dict(key=hmac_key,source_kwargs=source_kwargs,
                amount=amount,cost=cost,read_token=private_read_token,
                write_token=private_write_token,
                broker_key=broker_key,broker_secret=broker_secret,
                private_transport=private_transport,
                broker_transport=broker_transport)
    # FULL genuine independent signed ACWI and original FILL/account HIGH
    # source proof before querying/creating first BUY private state.
    original_args=_proof(**kwargs)
    head=_read_both(
        read_token=private_read_token,write_token=private_write_token,
        transport=private_transport)
    created=False
    if head is None:
        # No file exists on BOTH principals. A race may create it before
        # our PUT; GitHub creation without sha will fail, and never retry.
        # Require completely fresh original state + current risk at write.
        if _proof(**kwargs)!=original_args:
            raise AutoReserveStop("Signed first ACWI or immutable changed")
        genesis=buy.initial(**original_args)
        expected=buy.original.blob_sha(genesis)
        response_sha=_write(
            token=private_write_token,
            content=__import__("base64").b64encode(genesis).decode("ascii"),
            expected_sha=None,transport=private_transport)
        if response_sha!=expected:
            raise AutoReserveStop("First BUY private genesis CAS SHA uncertain")
        head=_read_both(
            read_token=private_read_token,write_token=private_write_token,
            transport=private_transport)
        if head is None:
            raise AutoReserveStop("First BUY private genesis readback missing")
        current_sha,doc=buy._read(head,**original_args)
        if current_sha!=expected or doc["sequence"]!=0:
            raise AutoReserveStop("First BUY signed genesis readback conflict")
        created=True
    sha,doc=buy._read(head,**original_args)
    if doc["sequence"]==2:
        raise AutoReserveStop("First BUY possible POST exists; NEVER REPEAT")
    if doc["sequence"]==1:
        b=doc["first_buy"]
        if (b["client_order_id"]!=buy.CLIENT_ID
            or b["notional_usd"]!=amount or b["all_in_cost_usd"]!=cost):
            raise AutoReserveStop("Existing first BUY notional/cost drift")
        return {
            "schema":SCHEMA,"status":"EXISTING_SIGNED_FIRST_BUY_RESERVED_NO_NEW_WRITE",
            "first_buy_private_state_sequence":1,
            "buyer_post_authorized":False,
            "private_Git_PUTs":0,
            "broker_POSTs":0,
            "existing_buy_client_order_id":None,
            "private_HMAC":None,"account_balances":None,
        }
    if doc["sequence"]!=0:
        raise AutoReserveStop("Unrecognized first BUY private state")
    if _proof(**kwargs)!=original_args:
        raise AutoReserveStop("Original ACWI/immutable source changed before BUY CAS")
    plan=buy.reserve(head,amount_usd=amount,cost_usd=cost,**original_args)
    if (plan.get("stage")!="PLAN_SINGLE_BUY_RESERVATION_NO_PRIVATE_WRITE"
        or plan["commit"]["expected_current_sha"]!=sha):
        raise AutoReserveStop("First BUY one-shot source reservation rejected")
    response_sha=_write(
        token=private_write_token,
        content=plan["commit"]["content_base64"],
        expected_sha=sha,transport=private_transport)
    if response_sha!=plan["new_blob_sha"]:
        raise AutoReserveStop("First BUY seq1 provider SHA untrusted")
    confirmed=_read_both(
        read_token=private_read_token,write_token=private_write_token,
        transport=private_transport)
    if confirmed is None:
        raise AutoReserveStop("First BUY seq1 missing after Git CAS")
    try: verified_sha,verified=buy._read(confirmed,**original_args)
    except Exception:
        raise AutoReserveStop("First BUY seq1 signature or remote SHA uncertain") from None
    if (verified_sha!=plan["new_blob_sha"]
        or verified["sequence"]!=1
        or verified["prior_blob_sha"]!=sha
        or verified["first_buy"]["notional_usd"]!=amount
        or verified["first_buy"]["all_in_cost_usd"]!=cost):
        raise AutoReserveStop("First BUY seq1 remote signed readback mismatch")
    return {
        "schema":SCHEMA,
        "status":"FIRST_BUY_SIGNED_SEQ1_RESERVED_READY_FOR_SEPARATE_WRITER",
        "first_buy_private_state_sequence":1,
        "created_private_genesis_this_run":created,
        "buyer_post_authorized":False,
        "private_Git_PUTs":2 if created else 1,
        "broker_POSTs":0,
        "existing_buy_client_order_id":None,
        "private_HMAC":None,"account_balances":None,
    }
