"""One-time external-principal reachability on protected GitHub main (GET ONLY).

Checks existing private READ/WRITE-scope principals' ability to read the
same ORIGINAL signed owner and reserved ACWI states. Also checks separately
scoped GitHub immutable Administration(read), prospective Release(write) token
read reachability, and public issue-read principal. NEVER mutate any GitHub
state or connect to Alpaca. GET does NOT prove WRITE permission: a future
authorised first original order still needs independently reviewed WRITE
permission and an explicit funded-order GO.
"""
from __future__ import annotations
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as owner
import fund100_v6_s1_immutable_release_publish_locked_v1_0 as publication
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_public_genesis_witness_v1_0 as witness

SCHEMA="FUND100_V6_S1_FIRST_ACWI_DISTINCT_PRINCIPALS_GET_ONLY_V1"
NO_HTTP_MUTATIONS=True
NO_BROKER_CONNECTION=True
NO_WRITE_PERMISSION_PROOF=True
REQUIRED=(
    "FUND100_PRIVATE_STATE_READ_TOKEN",
    "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
    "FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN",
    "FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN",
    "GITHUB_TOKEN",
    "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
)
ISSUE_URL="https://api.github.com/repos/nicobouch97/fund100-research/issues/8"
SELF_URL="https://api.github.com/user"
PRIVATE_REPO_URL="https://api.github.com/repos/nicobouch97/fund100-state-private"
PUBLIC_REPO_URL="https://api.github.com/repos/nicobouch97/fund100-research"
MAX_REPO_METADATA_BYTES=128_000


class PrincipalStop(RuntimeError):pass

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise PrincipalStop("Public issue GET redirected; STOP")

def _public_issue_get(*,token,transport=None):
    req=Request(ISSUE_URL,method="GET",headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"fund100-first-acwi-principals-getonly"})
    sender=build_opener(NoRedirect()).open if transport is None else transport
    try:
        with sender(req,timeout=12) as response:
            if getattr(response,"status",None)!=200:
                raise PrincipalStop("Public issue read unavailable")
            body=response.read(65537)
            if len(body)>65536:
                raise PrincipalStop("Public issue metadata oversized")
    except (HTTPError,URLError,TimeoutError,OSError):
        raise PrincipalStop("Public issue read failed") from None
    import json
    try:
        obj=json.loads(body)
    except Exception:
        raise PrincipalStop("Public issue JSON invalid") from None
    if (type(obj) is not dict or obj.get("number")!=8
        or type(obj.get("repository_url")) is not str
        or obj["repository_url"]!="https://api.github.com/repos/nicobouch97/fund100-research"):
        raise PrincipalStop("Public witness issue binding invalid")
    return True


def _release_token_authenticated(*,token,transport=None):
    """GET /user is auth-required; a public release 404 alone proves nothing."""
    req=Request(SELF_URL,method="GET",headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"fund100-first-acwi-release-token-auth-getonly"})
    sender=build_opener(NoRedirect()).open if transport is None else transport
    try:
        with sender(req,timeout=12) as response:
            if getattr(response,"status",None)!=200:
                raise PrincipalStop("Release-token authentication status invalid")
            raw=response.read(4000)
        import json
        user=json.loads(raw)
        if type(user) is not dict or type(user.get("login")) is not str or not user["login"]:
            raise PrincipalStop("Release-token identity missing")
        return True
    except PrincipalStop:raise
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise PrincipalStop("RELEASE_WRITE_TOKEN_AUTHENTICATED_GET_FAILED") from None

def _repository_push_metadata(*,url,expected_name,token,transport=None):
    """Read repository permission metadata, never infer endpoint WRITE proof.

    For fine-grained PATs, a repository GET can at best reveal a negative
    coarse push permission. Even push=True does not independently prove
    Contents(write), Release(write) or owner-branch policy. No mutation.
    """
    if (url,expected_name) not in (
        (PRIVATE_REPO_URL,"nicobouch97/fund100-state-private"),
        (PUBLIC_REPO_URL,"nicobouch97/fund100-research"),
    ):
        raise PrincipalStop("Unexpected token-bound repo metadata endpoint")
    req=Request(url,method="GET",headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"fund100-original-first-write-candidate-metadata-getonly"})
    sender=build_opener(NoRedirect()).open if transport is None else transport
    try:
        with sender(req,timeout=12) as response:
            if getattr(response,"status",None)!=200:
                raise PrincipalStop("Candidate repository metadata GET not authenticated")
            raw=response.read(MAX_REPO_METADATA_BYTES+1)
        if len(raw)>MAX_REPO_METADATA_BYTES:
            raise PrincipalStop("Candidate repository metadata oversized")
        import json
        value=json.loads(raw)
    except PrincipalStop:
        raise
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise PrincipalStop("Candidate repository metadata unavailable") from None
    if (type(value) is not dict
        or value.get("full_name")!=expected_name
        or type(value.get("permissions")) is not dict):
        # Metadata may be omitted for some fine-grained token types. UNKNOWN
        # cannot be interpreted as write authority or a verified denial.
        return "UNDETERMINED"
    permission=value["permissions"].get("push")
    if type(permission) is not bool:
        return "UNDETERMINED"
    return "PUSH_INDICATED_NOT_ENDPOINT_WRITE_PROOF" if permission else "PUSH_DENIED"


def inspect(*,environ=None,transport=None)->dict:
    """Deterministic source-HMAC and public-principal GETs only; no orders."""
    e=os.environ if environ is None else environ
    if (e.get("GITHUB_ACTIONS")!="true"
        or e.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or e.get("GITHUB_REF")!="refs/heads/main"
        or e.get("GITHUB_RUN_ATTEMPT")!="1"
        or e.get("GITHUB_EVENT_NAME") not in ("push","workflow_dispatch")
        or e.get("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or e.get("FUND100_RISK_LEVEL")!="HIGH"):
        raise PrincipalStop("Original protected main STOP context unavailable")
    values={}
    missing=[]
    for name in REQUIRED:
        value=e.get(name)
        if (type(value) is not str or len(value.strip())<10
            or value!=value.strip() or "\n" in value or "\r" in value):
            missing.append(name)
        else:
            values[name]=value
    if missing:
        # Enumerate missing secret NAMES in one run, never the secret values.
        raise PrincipalStop("MISSING_OR_MALFORMED_"+",".join(missing))
    tokens=[values[k] for k in REQUIRED if k!="FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX"]
    if len(set(tokens))!=5:
        raise PrincipalStop("DISTINCT_GITHUB_PRINCIPALS_MISSING")
    hmac=values["FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX"]
    if re.fullmatch("[0-9a-f]{64}",hmac) is None:
        raise PrincipalStop("PRIVATE_SIGNED_HMAC_INVALID")
    try:
        publication._distinct_tokens(
            values["FUND100_PRIVATE_STATE_READ_TOKEN"],
            values["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
            values["FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN"],
            values["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"])
    except Exception:
        raise PrincipalStop("DISTINCT_GITHUB_PRINCIPALS_MISSING") from None
    read=values["FUND100_PRIVATE_STATE_READ_TOKEN"]
    proposed_write=values["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"]
    stage="READ_TOKEN_ORIGINAL_OWNER_GET"
    try:
        a=owner._get_signed_source(token=read,transport=transport)
        stage="WRITE_CANDIDATE_ORIGINAL_OWNER_GET"
        b=owner._get_signed_source(token=proposed_write,transport=transport)
        if not all(a.get(k)==b.get(k) for k in ("path","sha","encoding","content")):
            raise PrincipalStop("Original owner private READ/WRITE candidate HEADs differ")
        stage="ORIGINAL_PUBLIC_WITNESS_LOCAL_VERIFICATION"
        w=witness.verify()
        stage="ORIGINAL_OWNER_HMAC_VERIFICATION"
        _,claim=fence._read(a,
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=bytes.fromhex(hmac))
        if claim.get("sequence")!=0 or claim.get("claim") is not None:
            raise PrincipalStop("Original one-time owner already claimed")
        def ledger_source(t):
            return owner._get_bounded_json(
                url=owner.ORIGINAL_ORDER_LEDGER_URL+"?ref=main",
                token=t,transport=transport)
        stage="READ_TOKEN_ORIGINAL_LEDGER_GET"
        x=ledger_source(read)
        stage="WRITE_CANDIDATE_ORIGINAL_LEDGER_GET"
        y=ledger_source(proposed_write)
        if not all(x.get(k)==y.get(k) for k in ("path","sha","encoding","content")):
            raise PrincipalStop("Original reserved private READ/WRITE candidate HEADs differ")
        stage="ORIGINAL_LEDGER_HMAC_VERIFICATION"
        _,state=cas._read_source(x,
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=bytes.fromhex(hmac))
        if state.get("sequence")!=1 or set(state.get("entries",{}))!={"ACWI"}:
            raise PrincipalStop("Original ACWI signed seq1 no longer reserved")
    except PrincipalStop:
        raise
    except Exception:
        # Stage is code-owned, finite and redacted: never print token,
        # private Contents source, HMAC key, account ID or HTTP payload.
        raise PrincipalStop("ORIGINAL_PRIVATE_HMAC_SOURCE_FAILED_AT_"+stage) from None
    try:
        admin=publication._request(method="GET",
            url=publication.IMMUTABLE_SETTING_URL,
            token=values["FUND100_IMMUTABLE_RELEASE_ADMIN_READ_TOKEN"],
            transport=transport)
        if (admin.get("enabled") is not True
            or type(admin.get("enforced_by_owner")) is not bool):
            raise PrincipalStop("IMMUTABLE_RELEASE_PROVIDER_DISABLED")
    except PrincipalStop:raise
    except Exception:
        raise PrincipalStop("IMMUTABLE_RELEASE_ADMIN_GET_DENIED") from None
    # Public tag GET 404 is NOT proof the supplied bearer token is valid.
    # Authenticate the candidate Release WRITE token via private /user GET.
    _release_token_authenticated(
        token=values["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"],
        transport=transport)
    try:
        previous=publication._request(method="GET",
            url=publication.anchor.RELEASE_URL,
            token=values["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"],
            transport=transport,allow_missing=True)
        if previous is not None:
            raise PrincipalStop("ORIGINAL_ACWI_IMMUTABLE_RELEASE_ALREADY_EXISTS")
    except PrincipalStop:raise
    except Exception:
        raise PrincipalStop("RELEASE_WRITE_TOKEN_READ_REACHABILITY_FAILED") from None
    try:
        _public_issue_get(token=values["GITHUB_TOKEN"],transport=transport)
    except Exception:
        raise PrincipalStop("PUBLIC_ISSUE_GET_DENIED") from None
    # These are explicit GET-only negative-permission screens. The final
    # signed private owner CAS and GitHub Release WRITE are NOT exercised.
    private_push=_repository_push_metadata(
        url=PRIVATE_REPO_URL,expected_name="nicobouch97/fund100-state-private",
        token=values["FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN"],
        transport=transport)
    release_push=_repository_push_metadata(
        url=PUBLIC_REPO_URL,expected_name="nicobouch97/fund100-research",
        token=values["FUND100_IMMUTABLE_RELEASE_WRITE_TOKEN"],
        transport=transport)
    if private_push=="PUSH_DENIED":
        raise PrincipalStop("ORIGINAL_PRIVATE_WRITE_CANDIDATE_REPOSITORY_PUSH_DENIED")
    if release_push=="PUSH_DENIED":
        raise PrincipalStop("ORIGINAL_RELEASE_WRITE_CANDIDATE_REPOSITORY_PUSH_DENIED")
    return {
        "schema":SCHEMA,
        "status":"FIVE_DISTINCT_GITHUB_PRINCIPALS_AUTHENTICATED_READ_ONLY_NO_WRITE_PROOF",
        "private_candidate_repository_push_metadata":private_push,
        "release_candidate_repository_push_metadata":release_push,
        "positive_push_metadata_is_proof_of_release_or_git_contents_write":False,
        "original_private_signed_seq1_and_owner_seq0_verified":True,
        "github_provider_immutable_releases_enabled":True,
        "private_write_permission_confirmed":False,
        "public_issue_write_permission_confirmed":False,
        "public_release_write_permission_confirmed":False,
        "signed_state_mutations":0,"public_release_mutations":0,
        "public_issue_mutations":0,"broker_orders":0,
        "funded_order_authorized":False,
    }

def main():
    result=inspect()
    assert result["signed_state_mutations"]==result["broker_orders"]==0
    print(result["status"])
    print("Immutable setting and private signed original seq1/owner seq0 READ verified.")
    print("Private WRITE candidate repo permission:",result["private_candidate_repository_push_metadata"])
    print("Public release candidate repo permission:",result["release_candidate_repository_push_metadata"])
    print("GitHub WRITE capability NOT established by GET. Funded trading STILL STOP.")

if __name__=="__main__":
    main()
