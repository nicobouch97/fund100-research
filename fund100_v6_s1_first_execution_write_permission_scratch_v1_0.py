"""First-funded-ACWI one-shot principal WRITE reachability, disposable ONLY.

Production signed private ledger/owner and original immutable release tag are
NEVER addressed. At most one CREATE, SHA-conditional UPDATE and DELETE of one
unique disposable private test file; no retries after ambiguous outcomes.
The public test creates and deletes one DRAFT only, NEVER uploads/publishes an
asset. No Alpaca requests or credentials. A successful diagnostic would prove
private Contents create/update CAS and PUBLIC DRAFT create/delete, NOT permission
to publish the immutable real release or to execute any funded broker order.
"""
from __future__ import annotations

from base64 import b64encode, b64decode
from hashlib import sha1
from io import BytesIO
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

SCHEMA = "FUND100_V6_S1_FIRST_EXECUTION_DISPOSABLE_WRITE_SCOPE_V2"
REPO = "nicobouch97/fund100-research"
EXPECTED_WORKFLOW_REF = (
    REPO + "/.github/workflows/"
    "fund100-v6-s1-first-execution-write-permission-scratch.yml@refs/heads/main"
)
PRIVATE_BASE = (
    "https://api.github.com/repos/nicobouch97/fund100-state-private/"
    "contents/diagnostics/"
)
PUBLIC_RELEASES = "https://api.github.com/repos/" + REPO + "/releases"
PRIVATE_STEM = "fund100_v6_s1_permission_probe_run_"
PUBLIC_STEM = "fund100-v6-s1-permission-probe-run-"
MAX_READ = 24_000
MAX_WRITE = 8_000
NO_ALPACA_NETWORK = True
NO_ORIGINAL_PRIVATE_STATE_WRITE = True
NO_ORIGINAL_IMMUTABLE_RELEASE_MUTATION = True
LIVE_TRADING_RELEASED = False
NEVER_RETRY_UNKNOWN_WRITE = True

class ScratchStop(RuntimeError):
    pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ScratchStop("Unapproved GitHub redirect; HOLD")

def _env(e):
    import json as j
    from pathlib import Path
    if (e.get("GITHUB_ACTIONS") != "true"
        or e.get("GITHUB_REPOSITORY") != REPO
        or e.get("GITHUB_REF") != "refs/heads/main"
        or e.get("GITHUB_EVENT_NAME") != "push"
        or e.get("GITHUB_WORKFLOW_REF") != EXPECTED_WORKFLOW_REF
        or e.get("GITHUB_RUN_ATTEMPT") != "1"
        or e.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or e.get("FUND100_RISK_LEVEL") != "HIGH"
        or re.fullmatch(r"[1-9][0-9]{0,18}",e.get("GITHUB_RUN_ID","")) is None
        or re.fullmatch(r"[0-9a-f]{40}",e.get("GITHUB_SHA","")) is None):
        raise ScratchStop("Original protected stopped main-only scope required")
    v5 = j.loads(Path("fund100_live_operator_control.json").read_text())
    v6 = j.loads(Path("fund100_v6_s1_operator_control.json").read_text())
    if (v5.get("trading_enabled") is not False
        or v6.get("trading_enabled") is not False
        or v6.get("first_original_acwi_sell_enabled") is not False
        or v6.get("risk_level") != "HIGH"
        or v6.get("pilot_capital_ceiling_usd") != "130.30"):
        raise ScratchStop("Current original operators not STOPPED")
    return e["GITHUB_RUN_ID"]

def _token(e,name):
    value=e.get(name)
    if (type(value) is not str or len(value) < 12
        or value != value.strip() or "\n" in value or "\r" in value):
        raise ScratchStop("Protected independent scoped GitHub principal absent")
    return value

def _blob_sha(raw:bytes)->str:
    return sha1(b"blob "+str(len(raw)).encode("ascii")+b"\x00"+raw).hexdigest()

def _paths(run):
    if type(run) is not str or re.fullmatch(r"[1-9][0-9]{0,18}",run) is None:
        raise ScratchStop("Untrusted original run identity")
    private=PRIVATE_BASE+PRIVATE_STEM+run+".txt"
    release_tag=PUBLIC_STEM+run
    return private, release_tag

def _fetch(*,method,url,token,body=None,missing=False,transport=None):
    # Caller is limited to the exact paths constructed by _paths. The
    # released source never supplies the owner/ledger paths or release tag.
    if method not in ("GET","PUT","POST","DELETE"):
        raise ScratchStop("Unsupported diagnostic HTTP method")
    if type(url) is not str or not url.startswith("https://api.github.com/"):
        raise ScratchStop("Unapproved diagnostic host")
    if body is not None:
        raw=json.dumps(body,sort_keys=True,separators=(",",":")).encode()
        if len(raw)>MAX_WRITE:
            raise ScratchStop("Oversized diagnostic payload")
    else:
        raw=None
    req=Request(url,data=raw,method=method,headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2022-11-28",
        "Content-Type":"application/json",
        "User-Agent":"fund100-v6-s1-disposable-principal-write-probe",
    })
    sender=(build_opener(NoRedirect()).open if transport is None else transport)
    try:
        with sender(req,timeout=12) as response:
            status=getattr(response,"status",None)
            result=response.read(MAX_READ+1)
        if len(result)>MAX_READ:
            raise ScratchStop("Diagnostic response oversized; never retry")
        if method=="DELETE" and status in (200,204):
            # GitHub Contents DELETE => 200 JSON; Releases DELETE => 204.
            return {} if not result else json.loads(result)
        # Actual signed owner/ledger transitions require Contents UPDATE
        # with the *current remote blob SHA*, HTTP 200; CREATE without SHA
        # must instead get HTTP 201. A mere CREATE/DELETE test cannot prove
        # this first-order critical compare-and-swap authority.
        if method=="PUT":
            updating=(type(body) is dict and "sha" in body)
            if updating and (type(body["sha"]) is not str
                             or re.fullmatch(r"[a-f0-9]{40}",body["sha"]) is None):
                raise ScratchStop("Invalid disposable exact-SHA update")
            expected=200 if updating else 201
        else:
            expected={"GET":200,"POST":201}[method]
        if status!=expected:
            raise ScratchStop("Diagnostic response status unexpected; never retry")
        document=json.loads(result)
        if type(document) is not dict:
            raise ScratchStop("Diagnostic response invalid; never retry")
        return document
    except HTTPError as exc:
        if missing and method=="GET" and exc.code==404:
            return None
        raise ScratchStop("GitHub write/read diagnostic failed; never retry") from None
    except (URLError,OSError,TimeoutError,ValueError,UnicodeError,TypeError):
        raise ScratchStop("GitHub diagnostic outcome uncertain; never retry") from None

def inspect(*,run_id,private_read,private_write,release_write,transport=None):
    """One disposable Contents CREATE/SHA-CAS UPDATE/DELETE, then DRAFT create/delete.

    Never modify the original signed seq1/owner or the actual release tag.
    No retries after a 4xx, timeout, lost ack or malformed reply; abandoned
    disposable objects require separate, human-reviewed cleanup.
    """
    private,tag=_paths(run_id)
    if len({private_read,private_write,release_write})!=3:
        raise ScratchStop("Distinct original GitHub principals required")
    for v in (private_read,private_write,release_write):
        if type(v) is not str or len(v)<12:
            raise ScratchStop("Missing protected principal")
    def ask(method,url,token,body=None,missing=False):
        return _fetch(method=method,url=url,token=token,body=body,
                      missing=missing,transport=transport)
    content=("Fund-100 disposable permission probe; not signed state; run="+run_id+"\n").encode()
    sha=_blob_sha(content)
    # We cannot prove actual signed Contents(write) via a GET. A disposable
    # sibling path on the SAME PRIVATE REPO and SAME main branch tests it
    # without spending the original irreversible HMAC signed owner.
    if ask("GET",private+"?ref=main",private_read,missing=True) is not None:
        raise ScratchStop("Private diagnostic path already present; no overwrite")
    created=ask("PUT",private,private_write,body={
        "branch":"main",
        "message":"fund100: disposable WRITE principal preflight (NO TRADE)",
        "content":b64encode(content).decode("ascii"),
    })
    info=created.get("content")
    if (type(info) is not dict or info.get("path")!=(
        "diagnostics/"+PRIVATE_STEM+run_id+".txt")
        or info.get("sha")!=sha):
        raise ScratchStop("Private diagnostic create unconfirmed; never retry")
    observed=ask("GET",private+"?ref=main",private_read)
    if (observed.get("sha")!=sha or observed.get("encoding")!="base64"
        or observed.get("path")!=info["path"]
        or type(observed.get("content")) is not str):
        raise ScratchStop("Independent read principal cannot verify private test write")
    try:
        checked=b64decode(observed["content"].replace("\n",""),validate=True)
    except Exception:
        raise ScratchStop("Private diagnostic content changed") from None
    if checked!=content:
        raise ScratchStop("Private diagnostic test content mismatch")
    # Crucial: original first-sale owner and ledger files already exist and
    # require a SHA-conditional Contents UPDATE, not Contents CREATE. Use
    # the same exact source SHA as GitHub's optimistic concurrency contract
    # and independently GET+verify the new blob before deleting it.
    revised=content+b"sha-cas-update-tested; no signed original state\n"
    revised_sha=_blob_sha(revised)
    changed=ask("PUT",private,private_write,body={
        "branch":"main",
        "message":"fund100: disposable private SHA-CAS update (NO TRADE)",
        "sha":sha,
        "content":b64encode(revised).decode("ascii"),
    })
    updated_info=changed.get("content")
    if (type(updated_info) is not dict
        or updated_info.get("path")!=info["path"]
        or updated_info.get("sha")!=revised_sha):
        raise ScratchStop("Private SHA-conditional update acknowledgement invalid")
    updated=ask("GET",private+"?ref=main",private_read)
    if (updated.get("sha")!=revised_sha
        or updated.get("encoding")!="base64"
        or updated.get("path")!=info["path"]
        or type(updated.get("content")) is not str):
        raise ScratchStop("Private disposable CAS update remote HEAD unconfirmed")
    try:
        revised_content=b64decode(updated["content"].replace("\n",""),validate=True)
    except Exception:
        raise ScratchStop("Private disposable CAS content invalid") from None
    if revised_content!=revised:
        raise ScratchStop("Private disposable SHA-CAS update bytes changed")
    deleted=ask("DELETE",private,private_write,body={
        "branch":"main",
        "message":"fund100: remove disposable WRITE principal probe (NO TRADE)",
        "sha":revised_sha,
    })
    if (type(deleted) is not dict or type(deleted.get("commit")) is not dict
        or deleted["commit"].get("sha") is None
        or ask("GET",private+"?ref=main",private_read,missing=True) is not None):
        raise ScratchStop("Private scratch cleanup not independently confirmed; HOLD")
    # Release(write) tests only a unique DRAFT. Never create the original
    # immutable first-ACWI release tag and never publish any test release.
    public=ask("POST",PUBLIC_RELEASES,release_write,body={
        "tag_name":tag,
        "target_commitish":os.environ["GITHUB_SHA"],
        "name":"Fund-100 disposable permission probe "+run_id,
        "body":"DRAFT ONLY: source principal permission check. No trade authority.",
        "draft":True,"prerelease":True,"make_latest":"false",
        "generate_release_notes":False,
    })
    release_id=public.get("id")
    if (type(release_id) is not int or release_id<=0
        or public.get("draft") is not True or public.get("tag_name")!=tag
        or type(public.get("assets")) is not list or public["assets"]):
        raise ScratchStop("Public DRAFT release create not uniquely acknowledged")
    release_url=PUBLIC_RELEASES+"/"+str(release_id)
    observed=ask("GET",release_url,release_write)
    if (observed.get("id")!=release_id or observed.get("draft") is not True
        or observed.get("tag_name")!=tag
        or observed.get("assets")!=[]):
        raise ScratchStop("Public DRAFT identity unconfirmed; never publish or delete")
    ask("DELETE",release_url,release_write)
    if ask("GET",release_url,release_write,missing=True) is not None:
        raise ScratchStop("Public disposable DRAFT cleanup unconfirmed")
    return {
        "schema":SCHEMA,
        "status":"DISPOSABLE_PRIVATE_CREATE_SHA_CAS_AND_PUBLIC_DRAFT_WRITE_PROVEN",
        "private_distinct_read_write_observed":True,
        "private_contents_existing_sha_cas_update_proven":True,
        "public_immutable_asset_upload_and_publish_proven":False,
        "public_draft_release_create_delete_proven":True,
        "original_signed_state_mutations":0,
        "original_immutable_release_mutations":0,
        "alpaca_requests":0,
        "broker_orders":0,
        "live_trading_authorized":False,
        "permission_to_write_original_signed_state":False,
        "private_token_or_raw_source":None,
    }

def main():
    env=dict(os.environ)
    run_id=_env(env)
    read=_token(env,"FUND100_PRIVATE_STATE_READ_TOKEN")
    write=_token(env,"FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN")
    release=_token(env,"FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN")
    result=inspect(run_id=run_id,private_read=read,private_write=write,
                   release_write=release)
    print("schema:",result["schema"])
    print("status:",result["status"])
    print("broker_orders:",result["broker_orders"])
    print("Actual signed state and original immutable release NEVER mutated.")
    print("Private credentials, contents and account data not printed.")

if __name__=="__main__":
    main()
