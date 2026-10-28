"""One non-trading protected private Git Contents(write) permission probe.

Creates exactly ONE NEW audit/ path in fund100-state-private, never touches
signed state, release objects, public issues, Alpaca or financial credentials.
Protected main-only push, first run_attempt, stopped V6 and broker kill ENGAGED.
A 404-before/one PUT/independent private READ-after protocol: NO retry after
any ambiguous PUT. A successful probe certifies only private Contents(write)
for this specific audit path at the observed time, not signed CAS permission,
branch policy tomorrow, GitHub Release(write), or any live trade authorization.
"""
from __future__ import annotations

from base64 import b64encode,b64decode
from hashlib import sha1
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

import fund100_v6_s1_first_execution_principals_getonly_v1_0 as original

SCHEMA="FUND100_V6_S1_FIRST_PRIVATE_CONTENTS_WRITE_PERMISSION_PROBE_NONTRADING_V1"
PRIVATE_REPO="nicobouch97/fund100-state-private"
API="https://api.github.com/repos/"+PRIVATE_REPO+"/contents/"
PREFIX="audit/fund100_v6_s1_first_acwi_private_write_probe_"
MAX_BYTES=16_000
MAX_ONE_REAL_PUT=1
LIVE_BROKER_CALLS_PERMITTED=False
SIGNATURE_LEDGER_WRITES_PERMITTED=False
PUBLIC_ISSUE_OR_RELEASE_WRITES_PERMITTED=False
LIVE_TRADING_AUTHORIZED=False

class ProbeStop(RuntimeError): pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ProbeStop("GitHub permission probe redirected; HOLD")

def _context(e):
    if (e.get("GITHUB_ACTIONS")!="true"
        or e.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or e.get("GITHUB_REF")!="refs/heads/main"
        or e.get("GITHUB_EVENT_NAME")!="push"
        or e.get("GITHUB_RUN_ATTEMPT")!="1"
        or e.get("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or e.get("FUND100_RISK_LEVEL")!="HIGH"
        or MAX_ONE_REAL_PUT!=1
        or SIGNATURE_LEDGER_WRITES_PERMITTED is not False
        or PUBLIC_ISSUE_OR_RELEASE_WRITES_PERMITTED is not False
        or LIVE_BROKER_CALLS_PERMITTED is not False
        or LIVE_TRADING_AUTHORIZED is not False):
        raise ProbeStop("Private permission probe requires protected original STOP")
    run=e.get("GITHUB_RUN_ID")
    sha=e.get("GITHUB_SHA")
    if (type(run) is not str or re.fullmatch("[1-9][0-9]{0,18}",run) is None
        or type(sha) is not str or re.fullmatch("[0-9a-f]{40}",sha) is None):
        raise ProbeStop("Untrusted original first-attempt GitHub identity")
    read=e.get("FUND100_PRIVATE_STATE_READ_TOKEN")
    write=e.get("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN")
    if (type(read) is not str or len(read)<10 or type(write) is not str
        or len(write)<10 or read==write or "\n" in read+write
        or "\r" in read+write or read.strip()!=read
        or write.strip()!=write):
        raise ProbeStop("Distinct protected private token scopes unavailable")
    return run,sha,read,write

def _request(*,method,run_id,token,raw=None,transport=None,allow_absent=False):
    if (method not in ("GET","PUT")
        or type(run_id) is not str
        or re.fullmatch("[1-9][0-9]{0,18}",run_id) is None
        or type(token) is not str or len(token)<10
        or (method=="GET" and raw is not None)
        or (method=="PUT" and (type(raw) is not bytes or len(raw)>MAX_BYTES))
        or (method=="PUT" and allow_absent)):
        raise ProbeStop("Only exact original audit GET and one bounded PUT allowed")
    path=PREFIX+run_id+".json"
    url=API+path+("?ref=main" if method=="GET" else "")
    headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"fund100-v6-first-private-nontrading-one-shot-probe",
    }
    if raw is not None:headers["Content-Type"]="application/json"
    req=Request(url,method=method,data=raw,headers=headers)
    sender=build_opener(NoRedirect()).open if transport is None else transport
    try:
        with sender(req,timeout=12) as response:
            if response.status!=(200 if method=="GET" else 201):
                raise ProbeStop("GitHub audit contents status uncertain; HOLD")
            response_body=response.read(MAX_BYTES+1)
        if len(response_body)>MAX_BYTES:
            raise ProbeStop("GitHub audit contents reply oversized; HOLD")
        value=json.loads(response_body)
    except HTTPError as e:
        if method=="GET" and allow_absent and e.code==404:
            return None
        raise ProbeStop("Original audit permission probe HTTP failure; NEVER RETRY") from None
    except ProbeStop:raise
    except (URLError,TimeoutError,OSError,ValueError,UnicodeError,TypeError):
        raise ProbeStop("Original audit permission probe transport unknown; NEVER RETRY") from None
    if type(value) is not dict:
        raise ProbeStop("GitHub audit permission response malformed; HOLD")
    return value

def _blob_sha(raw):
    return sha1(b"blob "+str(len(raw)).encode()+b"\x00"+raw).hexdigest()

def run_once():
    e=os.environ
    run,source_sha,read,write=_context(e)
    # The prior protected principal code proves distinct token identities,
    # ORIGINAL private seq1 and owner seq0 HMAC, immutability setting, GO STOP.
    proof=original.inspect(environ=e)
    if (proof.get("status")!=
        "FIVE_DISTINCT_GITHUB_PRINCIPALS_AUTHENTICATED_READ_ONLY_NO_WRITE_PROOF"
        or proof.get("original_private_signed_seq1_and_owner_seq0_verified") is not True
        or proof.get("private_candidate_repository_push_metadata")!=
             "PUSH_INDICATED_NOT_ENDPOINT_WRITE_PROOF"
        or proof.get("signed_state_mutations")!=0
        or proof.get("public_release_mutations")!=0
        or proof.get("public_issue_mutations")!=0
        or proof.get("broker_orders")!=0
        or proof.get("funded_order_authorized") is not False):
        raise ProbeStop("Original private signed state or token readiness HOLD")
    # Failure in the read-before-PUT is a HOLD; never overwrite any path.
    if _request(method="GET",run_id=run,token=read,allow_absent=True) is not None:
        raise ProbeStop("Audit probe path already exists; NEVER create twice")
    document={
        "schema":SCHEMA,
        "purpose":"ONE_NONTRADING_PRIVATE_REPOSITORY_CONTENTS_WRITE_SCOPE",
        "github_run_id":run,
        "public_source_sha":source_sha,
        "signed_order_ledger_modified":False,
        "original_owner_claim_modified":False,
        "broker_orders_sent":0,
    }
    content=(json.dumps(document,sort_keys=True,separators=(",",":"))+"\n").encode("ascii")
    path=PREFIX+run+".json"
    commit=json.dumps({
        "message":"Nontrading permission probe: verify private Contents(write) once",
        "branch":"main","content":b64encode(content).decode("ascii"),
    },sort_keys=True,separators=(",",":")).encode("ascii")
    if len(commit)>MAX_BYTES:
        raise ProbeStop("Audit commit payload oversized")
    # This is the ONLY mutation. Never retry even on timeout or uncertain ack.
    observed=_request(method="PUT",run_id=run,token=write,raw=commit)
    blob=_blob_sha(content)
    if (type(observed.get("content")) is not dict
        or observed["content"].get("path")!=path
        or observed["content"].get("sha")!=blob
        or type(observed.get("commit")) is not dict
        or type(observed["commit"].get("sha")) is not str
        or re.fullmatch("[a-f0-9]{40}",observed["commit"]["sha"]) is None):
        raise ProbeStop("Private audit PUT ambiguous; NEVER RETRY")
    # Cross-principal READ proves committed exact content (not mere 201 ack).
    after=_request(method="GET",run_id=run,token=read)
    if (after.get("type")!="file" or after.get("path")!=path
        or after.get("sha")!=blob or after.get("encoding")!="base64"
        or type(after.get("content")) is not str):
        raise ProbeStop("Private audit independent readback missing; NEVER RETRY")
    try:
        b=b64decode(after["content"],validate=False)
    except Exception:
        raise ProbeStop("Private audit readback bytes invalid; NEVER RETRY") from None
    if b!=content:
        raise ProbeStop("Private audit exact body mismatch; NEVER RETRY")
    return {
        "schema":SCHEMA,
        "status":"PRIVATE_MAIN_CONTENTS_WRITE_ONCE_AND_INDEPENDENT_READBACK_VERIFIED",
        "private_audit_file_created":True,
        "signed_private_ledger_unchanged_by_this_probe":True,
        "original_owner_fence_unchanged_by_this_probe":True,
        "public_issue_or_release_writes":0,
        "broker_requests":0,"broker_orders":0,
        "actual_release_write_permission_proven":False,
        "signed_ledger_CAS_write_permission_proven":False,
        "one_time_funded_launch_authorized":False,
        "private_token":None,"account":None,"order":None,
    }

def main():
    report=run_once()
    print(report["status"])
    print("One isolated private permission audit file; no broker or ledger changes.")
    print("Original signed CAS and public Release WRITE rights NOT yet proven.")

if __name__=="__main__":
    main()
