"""ONE original funded XLK BUY writer boundary (source HARD LOCKED).

This is actual HTTP code, NOT an enabled workflow. It is deliberately
non-runnable until an independently reviewed scoped funded BUY workflow,
the first-sale GET sources, and the buy ledger provisioned state exist.
The default constants and all upstream real source releases remain FALSE.

Core order of operations in ONE GitHub Actions invocation, never resumed:
  read current original signed ACWI seq2; verify immutable asset source;
  read original BUY seq1 with TWO private principals;
  independently requalify complete original ACWI FILL + fresh 1x account
  and post-ACWI HIGH 6/20/35 + exact BUY amount/cost; verify V6 operator GO;
  GET broker existing exact first-buy client ID, HOLD if any;
  CAS PUT one signed possible-POST BUY seq2 ONCE and reGET both heads;
  fresh same-process risk/operator GO immediately before any broker POST;
  GET exact broker client ID a second time, HOLD if any;
  make at most ONE POST /v2/orders with market-notional DAY XLK BUY.
Any 404/timeout/409 after CAS possible-POST is a NEVER-RETRY HOLD.
Multiple concurrent invocations cannot both CAS the same seq1 parent.

NO separate method exposes a usable live order payload. No environment-
only override of the code HARD LOCK; source-read locks are independent.
Signed BUY state and original immutable binding are never logged.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256
import json
import os
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,build_opener,HTTPRedirectHandler

import fund100_v6_s1_first_xlk_buy_cas_offline_v1_0 as buy
import fund100_v6_s1_first_acwi_buy_liquidity_getonly_locked_v1_0 as risk
import fund100_v6_s1_private_git_cas_protocol_v1_0 as original
import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_immutable_release_anchor_v1_0 as anchor
import fund100_v6_s1_operator_control_v2_0 as operator

SCHEMA="FUND100_V6_S1_FIRST_XLK_BUY_ATOMIC_CAS_SINGLE_WRITER_LOCKED_V1"
RUNTIME_RELEASED=False
BROKER_BUY_POST_RELEASED=False
RESTART_OR_RESUBMIT_RELEASED=False
MAX_FIRST_BUY_POSTS=1
EXPECTED_REF=(
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-s1-first-xlk-buy-funded-once.yml@refs/heads/main"
)
GITHUB_BUY_CONTENTS_URL=(
    "https://api.github.com/repos/"+buy.REPO+"/contents/"+buy.PATH)
GITHUB_ORIGINAL_CONTENTS_URL=(
    "https://api.github.com/repos/"+original.STATE_REPO+
    "/contents/"+original.STATE_PATH)
BROKER_GET_URL=(
    "https://api.alpaca.markets/v2/orders:by_client_order_id?"+
    urlencode({"client_order_id":buy.CLIENT_ID}))
BROKER_POST_URL="https://api.alpaca.markets/v2/orders"
NO_AUTOMATIC_RETRY=True

class FirstBuyWriterStop(RuntimeError):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise FirstBuyWriterStop("Unexpected redirect while writing first BUY")

def _locked():
    """MUST be first executable statement of first BUY submission entry."""
    e=os.environ
    if (RUNTIME_RELEASED is not True
        or BROKER_BUY_POST_RELEASED is not True
        or RESTART_OR_RESUBMIT_RELEASED is not False
        or MAX_FIRST_BUY_POSTS!=1
        or risk.SOURCE_RELEASED is not True
        or e.get("GITHUB_ACTIONS")!="true"
        or e.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or e.get("GITHUB_REF")!="refs/heads/main"
        or e.get("GITHUB_WORKFLOW_REF")!=EXPECTED_REF
        or e.get("GITHUB_RUN_ATTEMPT")!="1"
        or e.get("GITHUB_EVENT_NAME")!="schedule"
        or e.get("FUND100_RISK_LEVEL")!="HIGH"
        or e.get("FUND100_BROKER_KILL_SWITCH")!="DISENGAGED"):
        raise FirstBuyWriterStop("First XLK BUY writer HARD LOCKED")

def _distinct(*secrets):
    if (any(type(v) is not str or len(v.strip())<10 or v!=v.strip()
            or "\n" in v or "\r" in v for v in secrets)
        or len(secrets)!=len(set(secrets))):
        raise FirstBuyWriterStop("Missing segregated private/broker principals")

def _net(*,url,method,headers,body=None,transport=None,
         max_bytes=32000,missing_ok=False):
    if (method,url.split("?")[0]) not in {
        ("GET",GITHUB_ORIGINAL_CONTENTS_URL),
        ("GET",GITHUB_BUY_CONTENTS_URL),
        ("PUT",GITHUB_BUY_CONTENTS_URL),
        ("GET",BROKER_GET_URL.split("?")[0]),
        ("POST",BROKER_POST_URL),
    }:
        raise FirstBuyWriterStop("Unexpected broker/private endpoint or method")
    if (url==BROKER_GET_URL and method=="GET") or (
        url in (GITHUB_ORIGINAL_CONTENTS_URL+"?ref=main",
                GITHUB_BUY_CONTENTS_URL+"?ref=main",
                GITHUB_BUY_CONTENTS_URL,BROKER_POST_URL)):
        pass
    else:
        raise FirstBuyWriterStop("Unexpected query, host or endpoint")
    req=Request(url,method=method,headers=headers,data=body)
    send=build_opener(NoRedirect()).open if transport is None else transport
    try:
        with send(req,timeout=15) as response:
            if getattr(response,"status",None)!={
                "GET":200,"PUT":200,"POST":200
            }[method] and not (method=="POST" and getattr(response,"status",None)==201):
                raise FirstBuyWriterStop("Unaccepted first-buy HTTP response")
            raw=response.read(max_bytes+1)
        if len(raw)>max_bytes:
            raise FirstBuyWriterStop("First BUY HTTP response oversized")
        data=json.loads(raw)
        if type(data) is not dict:
            raise FirstBuyWriterStop("First BUY HTTP response not a JSON object")
        return data
    except HTTPError as e:
        if method=="GET" and url==BROKER_GET_URL and e.code==404 and missing_ok:
            return None
        raise FirstBuyWriterStop("First BUY broker/Git CAS failure: HOLD NO RETRY") from None
    except (URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise FirstBuyWriterStop("First BUY HTTP uncertain: HOLD NO RETRY") from None

def _gh_headers(token):
    return {"Accept":"application/vnd.github+json",
            "Authorization":"Bearer "+token,
            "X-GitHub-Api-Version":"2022-11-28",
            "Cache-Control":"no-store",
            "User-Agent":"fund100-first-xlk-once"}

def _get_both(*,url,read_token,write_token,transport):
    src=_net(url=url+"?ref=main",method="GET",
             headers=_gh_headers(read_token),transport=transport)
    second=_net(url=url+"?ref=main",method="GET",
             headers=_gh_headers(write_token),transport=transport)
    if (type(src.get("sha")) is not str
        or src.get("sha")!=second.get("sha")
        or src.get("content")!=second.get("content")
        or src.get("path")!=second.get("path")):
        raise FirstBuyWriterStop("Private original/BUY HEAD two principal mismatch")
    return src

def _op_go():
    current=operator.read_current_control()
    if (current.get("risk_level")!="HIGH"
        or current.get("pilot_capital_ceiling_usd")!="130.30"
        or current.get("trading_enabled") is not True
        or os.environ.get("FUND100_BROKER_KILL_SWITCH")!="DISENGAGED"):
        raise FirstBuyWriterStop("Current V6 operator/risk/broker STOP")
    return True

def _risk_go(*,source_kwargs,amount,cost,broker_key,broker_secret):
    if type(source_kwargs) is not dict:
        raise FirstBuyWriterStop("No exact protected first-ACWI FILL source")
    args=dict(source_kwargs)
    if ("fake_postorder_kwargs" in args or "fake_account_get" in args
        or "now_utc" in args or "first_xlk_buy_notional_usd" in args
        or "worst_case_all_in_cost_usd" in args
        or args.get("broker_key")!=broker_key
        or args.get("broker_secret")!=broker_secret):
        raise FirstBuyWriterStop("Injected/unsourced BUY risk evidence prohibited")
    report=risk.inspect(
        **args,first_xlk_buy_notional_usd=amount,
        worst_case_all_in_cost_usd=cost)
    if (report.get("schema")!=risk.SCHEMA
        or report.get("fully_fake_source_transports") is not False
        or report.get("status")!=
           "REAL_READONLY_FIRST_ACWI_POSTSALE_1X_LIQUIDITY_GET_SOURCE_NOT_AUTHORIZED"
        or report.get("broker_current_account_source_authenticated") is not True
        or report.get("original_first_acwi_signed_fill_flat_authenticated") is not True
        or report.get("actual_posttrade_high_6_20_35_risk_verified") is not True
        or report.get("funding_adjusted_post_acwi_high_6_20_35_source_screen_passed") is not True
        or report.get("first_xlk_exact_order_notional_and_all_in_cost_screen_passed") is not True
        or report.get("first_xlk_exact_cash_and_1x_nonmarginable_bp_screen_from_same_gets") is not True
        or report.get("first_xlk_buy_live_authorized") is not False
        or report.get("next_legacy_sell_or_live_buy_authorized") is not False
        or report.get("broker_POSTs")!=0
        or report.get("private_Git_PUTs")!=0):
        raise FirstBuyWriterStop("Authenticated first-XLK broker risk source HOLD")
    return True

def _broker_headers(key,secret):
    return {"Accept":"application/json",
            "APCA-API-KEY-ID":key,
            "APCA-API-SECRET-KEY":secret,
            "User-Agent":"fund100-first-xlk-once"}

def _by_client(*,key,secret,transport):
    return _net(url=BROKER_GET_URL,method="GET",
                headers=_broker_headers(key,secret),
                missing_ok=True,transport=transport)

def _post_one(*,key,secret,amount,transport):
    payload={
        "symbol":buy.SYMBOL,"side":buy.SIDE,"type":"market",
        "time_in_force":"day","extended_hours":False,
        "notional":amount,"client_order_id":buy.CLIENT_ID,
    }
    response=_net(url=BROKER_POST_URL,method="POST",
       headers={**_broker_headers(key,secret),"Content-Type":"application/json"},
       body=json.dumps(payload,sort_keys=True,separators=(",",":")).encode("ascii"),
       transport=transport)
    if (response.get("symbol")!="XLK" or response.get("side")!="buy"
        or response.get("client_order_id")!=buy.CLIENT_ID
        or response.get("type")!="market"
        or response.get("time_in_force")!="day"
        or response.get("status") not in (
            "new","accepted","pending_new","partially_filled","filled")
        or type(response.get("id")) is not str or not response["id"]):
        raise FirstBuyWriterStop("Original first XLK BUY broker response uncertain")
    return response["status"]

def submit_one_original_xlk_buy(*,amount_usd:str,cost_usd:str,
       private_read_token:str,private_write_token:str,
       public_read_token:str,broker_key:str,broker_secret:str,
       hmac_key:bytes,source_kwargs:dict,
       private_transport=None,broker_transport=None)->dict:
    """One CAS seq1 -> seq2, one BUY POST, never restart this invocation."""
    _locked()  # FIRST executable operation: no GET/PUT/POST on current main.
    _distinct(private_read_token,private_write_token,public_read_token,
              broker_key,broker_secret)
    if type(hmac_key) is not bytes or len(hmac_key)<32:
        raise FirstBuyWriterStop("Missing signed private BUY HMAC verifier")
    amount=buy._cent(amount_usd,"first XLK amount")
    cost=buy._cent(cost_usd,"first XLK cost")
    if (amount<buy.MIN_NOTIONAL or amount>buy.MAX_NOTIONAL
        or cost>amount*buy.MAX_COST_FRAC):
        raise FirstBuyWriterStop("First XLK notional/cost out of budget")
    amount=format(amount,".2f")
    cost=format(cost,".2f")
    _op_go()
    # Current GitHub original HMAC seq2 two-principal identity. Its immutable
    # first ACWI full FILL/flat is independently verified by _risk_go below.
    orig=_get_both(url=GITHUB_ORIGINAL_CONTENTS_URL,
        read_token=private_read_token,write_token=private_write_token,
        transport=private_transport)
    binding=witness.verify()
    original_sha,doc=original._read_source(orig,
        private_genesis=binding["original_public_genesis_nonce"],
        account_binding_sha256=binding["original_live_account_binding_sha256"],
        key=hmac_key)
    if (doc.get("sequence")!=2 or set(doc.get("entries",{}))!={"ACWI"}
        or doc["entries"]["ACWI"]["state"]!="POST_MAY_HAVE_BEEN_SENT"):
        raise FirstBuyWriterStop("Original signed ACWI SELL prepost not current")
    # Immutable asset is pinned to a FIXED official provider URL. The prior
    # source reader also verifies the release metadata and this same asset
    # with the exact ACWI HMAC owner in-process before returning a REAL proof.
    immutable_bytes=anchor._get(url=anchor.DOWNLOAD_URL,token=None,
        accept="application/octet-stream",limit=anchor.MAX_ASSET_BYTES)
    asset_sha=sha256(immutable_bytes).hexdigest()
    args={
        "account_binding_sha256":
            binding["original_live_account_binding_sha256"],
        "original_private_genesis":binding["original_public_genesis_nonce"],
        "original_acwi_seq2_blob_sha":original_sha,
        "original_immutable_asset_sha256":asset_sha,
        "key":hmac_key,
    }
    # Must already exist at signed seq1 after a separately reviewed BUY
    # reservation; never auto-initialize the private first BUY file on 404.
    head=_get_both(url=GITHUB_BUY_CONTENTS_URL,
        read_token=private_read_token,write_token=private_write_token,
        transport=private_transport)
    sha,current=buy._read(head,**args)
    if current["sequence"]!=1:
        raise FirstBuyWriterStop("First XLK BUY not reserved exactly once")
    item=current["first_buy"]
    if (item["client_order_id"]!=buy.CLIENT_ID
        or item["notional_usd"]!=amount
        or item["all_in_cost_usd"]!=cost):
        raise FirstBuyWriterStop("Current original first BUY reservation/amount drift")
    _risk_go(source_kwargs=source_kwargs,amount=amount,cost=cost,
             broker_key=broker_key,broker_secret=broker_secret)
    _op_go()
    if _by_client(key=broker_key,secret=broker_secret,
                  transport=broker_transport) is not None:
        raise FirstBuyWriterStop("First XLK broker ID exists; NEVER POST again")

    # IRREVERSIBLE first BUY possible POST record committed BEFORE Alpaca.
    # No retry if PUT times out, 409s, or a second run races us.
    plan=buy.possible_post(head,amount_usd=amount,cost_usd=cost,**args)
    if (plan.get("stage")!="PLAN_POSSIBLE_BUY_POST_NO_PRIVATE_WRITE_OR_BROKER_SEND"
        or plan.get("commit",{}).get("expected_current_sha")!=sha):
        raise FirstBuyWriterStop("Unconfirmed first BUY possible-POST transition")
    changes=plan["commit"]
    raw=json.dumps({
        "branch":"main","sha":sha,
        "message":"fund100: FIRST XLK BUY possible POST NO RETRY",
        "content":changes["content_base64"],
    },sort_keys=True,separators=(",",":")).encode("ascii")
    _net(url=GITHUB_BUY_CONTENTS_URL,method="PUT",
         headers={**_gh_headers(private_write_token),
                  "Content-Type":"application/json"},
         body=raw,transport=private_transport)
    updated=_get_both(url=GITHUB_BUY_CONTENTS_URL,
       read_token=private_read_token,write_token=private_write_token,
       transport=private_transport)
    updated_sha,post=buy._read(updated,**args)
    if (updated_sha!=plan["new_blob_sha"]
        or post["sequence"]!=2
        or post["prior_blob_sha"]!=sha):
        raise FirstBuyWriterStop("BUY CAS write/read-back uncertain, no broker POST")
    # Second fresh real SAME-PROCESS risk / operator check after CAS,
    # preventing a stale pre-CAS portfolio snapshot from permitting a buy.
    _risk_go(source_kwargs=source_kwargs,amount=amount,cost=cost,
             broker_key=broker_key,broker_secret=broker_secret)
    _op_go()
    if _by_client(key=broker_key,secret=broker_secret,
                  transport=broker_transport) is not None:
        raise FirstBuyWriterStop("First XLK broker ID present after CAS, HOLD")
    # Exactly ONE actual Alpaca order submission per one CAS attempt.
    status=_post_one(key=broker_key,secret=broker_secret,
                     amount=amount,transport=broker_transport)
    return {
        "schema":SCHEMA,
        "status":"FIRST_XLK_BUY_POST_ATTEMPTED_NEVER_RETRY",
        "broker_status_class":"ACCEPTED_OR_FILLED" if status in (
             "filled","accepted","new","pending_new","partially_filled") else "UNKNOWN",
        "first_buy_order_submissions_in_this_process":1,
        "repeat_allowed":False,
        "actual_broker_fill_and_settlement_verified":False,
        "first_buy_cas_sequence_at_possible_post":2,
        "second_new_buy_or_legacy_sell_authorized":False,
        "broker_private_account":None,"order_id":None,
        "client_order_id":None,"private_hmac_key":None,
        "source_credentials":None,"order_notional":None,
    }
