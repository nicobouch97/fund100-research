"""One-shot candidate: provider-immutable public ACWI seq2 anchor publication.

Only a future separately reviewed SAME original protected GitHub Actions first
attempt may use this sequence, after signed private seq2 CAS. The real transport
is HARD LOCKED. Never run this module independently or retry any publication
operation. No Alpaca import, credentials, POST or broker authorization.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, HTTPRedirectHandler, build_opener

import fund100_v6_s1_immutable_release_anchor_v1_0 as anchor
import fund100_v6_s1_one_time_owner_claim_cas_v1_0 as original
import fund100_v6_s1_private_git_cas_protocol_v1_0 as ledger

SCHEMA="FUND100_V6_S1_LOCKED_SINGLE_ATTEMPT_PUBLIC_IMMUTABLE_RELEASE_V1"
IMMUTABLE_SETTING_URL=anchor.API+"/immutable-releases"
METADATA_URL=anchor.API+"/releases"
MAX_RESPONSE=26000
PUBLISH_SIGNED_HEAD_RELEASED=False
ALLOW_RETRY_AFTER_ANY_RELEASE_POST=False
LIVE_BROKER_ORDER_RELEASED=False
NO_LIVE_WORKFLOW_OR_ENTRYPOINT=True

class PublicationStop(RuntimeError):
    pass

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise PublicationStop("GitHub publication redirect forbidden; NEVER RETRY")

def _request(*,method,url,token,payload=None,content_type=None,transport=None,allow_missing=False):
    # Exact repository endpoints only. No user-provided or redirect URL.
    permitted=(IMMUTABLE_SETTING_URL,anchor.RELEASE_URL,METADATA_URL)
    if (url not in permitted
        and re.fullmatch(
            re.escape(anchor.API)+r"/releases/[1-9][0-9]{0,18}",url) is None
        and re.fullmatch(
            r"https://uploads\.github\.com/repos/nicobouch97/"
            r"fund100-research/releases/[1-9][0-9]{0,18}/assets"
            r"\?name=fund100-v6-s1-first-acwi-head\.json",url) is None):
        raise PublicationStop("Nonoriginal release publisher endpoint")
    if type(token) is not str or len(token.strip())<10 or "\r" in token or "\n" in token:
        raise PublicationStop("Missing exact GitHub publisher credential")
    if method not in ("GET","POST","PATCH") or (
        method=="GET" and url not in (IMMUTABLE_SETTING_URL,anchor.RELEASE_URL)
    ) or (
        method=="POST" and url!=METADATA_URL and not url.startswith(
            "https://uploads.github.com/repos/nicobouch97/fund100-research/releases/")
    ) or (method=="PATCH" and url in permitted):
        raise PublicationStop("Unexpected publication HTTP operation")
    headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+token,
        "X-GitHub-Api-Version":"2026-03-10",
        "User-Agent":"fund100-original-acwi-immutable-release-once",
    }
    if payload is not None:
        if type(payload) is not bytes or len(payload)>MAX_RESPONSE:
            raise PublicationStop("Unbounded release publication payload")
        headers["Content-Type"]=content_type
    req=Request(url,method=method,data=payload,headers=headers)
    sender=build_opener(_NoRedirect()).open if transport is None else transport
    try:
        with sender(req,timeout=12) as resp:
            status=getattr(resp,"status",None)
            raw=resp.read(MAX_RESPONSE+1)
        if len(raw)>MAX_RESPONSE:
            raise PublicationStop("Release acknowledgement oversized; NEVER RETRY")
        if status!={"GET":200,"POST":201,"PATCH":200}[method]:
            raise PublicationStop("Release HTTP outcome not uniquely confirmed; NEVER RETRY")
        data=json.loads(raw.decode("utf-8"))
        if type(data) is not dict:
            raise PublicationStop("Invalid original immutable release reply")
        return data
    except HTTPError as exc:
        if (allow_missing is True and method=="GET"
            and url==anchor.RELEASE_URL and exc.code==404):
            return None
        raise PublicationStop("GitHub release request failed; NEVER RETRY") from None
    except (URLError,TimeoutError,OSError,UnicodeError,ValueError):
        raise PublicationStop("GitHub release request ambiguous; NEVER RETRY") from None

def _distinct_tokens(*tokens):
    if any(type(t) is not str or len(t)<10 or "\r" in t or "\n" in t for t in tokens):
        raise PublicationStop("Missing protected distinct principals")
    if len(set(tokens))!=len(tokens):
        raise PublicationStop("Public admin/read, release WRITE, private read/write must be distinct")

def _verify_current_private(*owner_sources,prepost_source,read_token,write_token,
                            transport=None):
    # Two independently credentialed actual GETs of BOTH signed original HEADs.
    # A forged passed-in current_fence_source cannot simply claim a valid owner.
    signed_owner=owner_sources["current_fence_source"]
    if not isinstance(signed_owner,dict) or not isinstance(prepost_source,dict):
        raise PublicationStop("Missing authenticated signed remote source")
    pairs=(
        (original.PRIVATE_CONTENTS_URL,signed_owner),
        (original.ORIGINAL_ORDER_LEDGER_URL,prepost_source),
    )
    for url,passed in pairs:
        for tok in (read_token,write_token):
            try:
                live=original._get_bounded_json(
                    url=url+"?ref=main",token=tok,transport=transport)
            except Exception:
                raise PublicationStop("Current signed private HEAD GET unconfirmed") from None
            if (live.get("sha")!=passed.get("sha")
                or live.get("content")!=passed.get("content")
                or live.get("path")!=passed.get("path")
                or live.get("encoding")!="base64"):
                raise PublicationStop("Original signed HEAD diverged; never publish")

def publish_exact_acwi_signed_seq2_release_same_attempt_only(
    *,owner_sources,prepost_source,private_read_token,private_write_token,
    admin_read_token,public_release_write_token,
    private_transport=None,public_transport=None,immutable_read_transport=None,
):
    """At most ONE draft/create, ONE asset POST and ONE publish PATCH, NO RETRY.

    No external call is made before the production release locks. The
    immutable-setting query MUST return 200 enabled=true using an account
    with GitHub's repo Administration(read) permission; a 403 or 404 is HOLD.
    Once a mutation is attempted, every uncertain result is irreversible HOLD.
    """
    if (PUBLISH_SIGNED_HEAD_RELEASED is not True
        or ALLOW_RETRY_AFTER_ANY_RELEASE_POST is not False
        or LIVE_BROKER_ORDER_RELEASED is not False
        or anchor.LIVE_BROKER_POST_RELEASED is not False
        or ledger.LIVE_ORDER_RELEASED is not False
        or original.LIVE_BROKER_ORDER_RELEASED is not False):
        raise PublicationStop("Original ACWI immutable release transport HARD LOCKED")
    _distinct_tokens(private_read_token,private_write_token,
                     admin_read_token,public_release_write_token)
    if type(owner_sources) is not dict or type(prepost_source) is not dict:
        raise PublicationStop("Signed same-attempt owner or original seq2 unavailable")
    try:
        original._require_real_same_run(
            owner_run_id=owner_sources["owner_run_id"],
            owner_attempt=owner_sources["owner_attempt"],
            current_main_sha=owner_sources["current_main_sha"])
    except Exception:
        raise PublicationStop("Not original main first-attempt owner") from None

    # Local HMAC validation and unique original owner/seq2 binding first.
    try:
        expected=anchor.original_signed_anchor_asset(
            signed_owner_sources=owner_sources,prepost_source=prepost_source)
    except Exception:
        raise PublicationStop("HMAC original owner and seq2 not authenticated") from None

    # GitHub Contents is mutable; always independently reread the actual HEAD
    # through BOTH existing private principals just before the first RELEASE POST.
    _verify_current_private(
        owner_sources=owner_sources,prepost_source=prepost_source,
        read_token=private_read_token,write_token=private_write_token,
        transport=private_transport)

    # Preflight is explicitly ADMIN READ scoped. No reliance on generic repo
    # metadata, user statements, issue comments or a github.token lacking admin.
    setting=_request(method="GET",url=IMMUTABLE_SETTING_URL,
                     token=admin_read_token,transport=public_transport)
    if setting.get("enabled") is not True or type(setting.get("enforced_by_owner")) is not bool:
        raise PublicationStop("GitHub provider release immutability NOT VERIFIED")
    # Existing releases block; 404 is allowed only on this exact read URL.
    # GitHub will enforce tag uniqueness during draft creation as well.
    prior=_request(method="GET",url=anchor.RELEASE_URL,
                   token=public_release_write_token,transport=public_transport,
                   allow_missing=True)
    if prior is not None:
        raise PublicationStop("Original immutable release already exists; NEVER OVERWRITE")
    payload=json.dumps({
        "tag_name":anchor.TAG,
        "target_commitish":owner_sources["current_main_sha"],
        "name":"Fund-100 first original ACWI signed possible-POST HEAD",
        "body":"Nonsecret original ACWI signed ledger HEAD witness. No trade authority.",
        "draft":True,"prerelease":False,"make_latest":False,
        "generate_release_notes":False,
    },sort_keys=True,separators=(",",":")).encode("utf-8")
    # First irreversible public step. After ANY ambiguity, never retry, even
    # if API reports no release/asset on a subsequent GET.
    draft=_request(method="POST",url=METADATA_URL,
                   token=public_release_write_token,payload=payload,
                   content_type="application/json",transport=public_transport)
    release_id=draft.get("id")
    if (type(release_id) is not int or release_id<=0
        or draft.get("draft") is not True
        or draft.get("tag_name")!=anchor.TAG
        or draft.get("target_commitish")!=owner_sources["current_main_sha"]
        or type(draft.get("assets")) is not list
        or draft["assets"]):
        raise PublicationStop("Draft may exist but not uniquely verified; NEVER RETRY")
    # Upload exactly one canonical original HMAC-bound, nonsecret bytes.
    upload=(
        "https://uploads.github.com/repos/nicobouch97/fund100-research/releases/"
        +str(release_id)+"/assets?name="+anchor.ASSET)
    uploaded=_request(method="POST",url=upload,
        token=public_release_write_token,payload=expected,
        content_type="application/json",transport=public_transport)
    if (uploaded.get("name")!=anchor.ASSET
        or uploaded.get("size")!=len(expected)
        or uploaded.get("state")!="uploaded"
        or uploaded.get("digest")!="sha256:"+sha256(expected).hexdigest()
        or uploaded.get("browser_download_url")!=anchor.DOWNLOAD_URL):
        raise PublicationStop("Release asset may exist but invalid; NEVER RETRY")
    # Publish ONCE, only after upload confirmation. Immutable release
    # enforcement should freeze asset and tag at publication.
    publish_url=METADATA_URL+"/"+str(release_id)
    pub=_request(method="PATCH",url=publish_url,
        token=public_release_write_token,
        payload=b'{"draft":false}',content_type="application/json",
        transport=public_transport)
    if (pub.get("id")!=release_id or pub.get("draft") is not False
        or pub.get("tag_name")!=anchor.TAG
        or pub.get("immutable") is not True
        or type(pub.get("published_at")) is not str):
        raise PublicationStop("Published immutable release not acknowledged; NEVER RETRY")

    try:
        verified=anchor.verify_published_immutable_anchor(
            expected_asset=expected,public_read_token=admin_read_token,
            transport=immutable_read_transport)
    except Exception:
        raise PublicationStop("Published immutable HEAD reread failed; NEVER RETRY") from None
    if (verified.get("provider_immutable_release_and_exact_asset_verified") is not True
        or verified.get("first_live_broker_order_authorized") is not False):
        raise PublicationStop("Original immutable HEAD not independently proven")
    return {
        "schema":SCHEMA,
        "stage":"SIGNED_ORIGINAL_ACWI_SEQ2_PUBLISHED_IMMUTABLE_NO_BROKER",
        "exact_original_unique_owner_and_seq2_bound":True,
        "two_private_principals_same_original_HEAD_verified":True,
        "provider_immutable_setting_authenticated_before_first_post":True,
        "provider_immutable_asset_independent_GET_verified":True,
        "publisher_draft_attempts":1,"publisher_asset_upload_attempts":1,
        "publisher_release_attempts":1,"broker_POST_attempts":0,
        "live_order_authorized":False,"retry_permitted":False,
        "account_id":None,"original_qty":None,"private_hmac":None,
        "owner_nonce":None,"private_source_contents":None,
    }

# Deliberately no runnable main, no production workflow, and no ALPACA key.
# This one-time publisher is permanently HARD LOCKED in checked-in code.
