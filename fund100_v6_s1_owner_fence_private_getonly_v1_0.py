"""Get-only observation of the ORIGINAL private ACWI execution owner fence.

One GitHub Contents GET, separate from the ORIGINAL PURE broker-source
verifier and no private PUT/POST/broker transport. A 404 from READ is neither
two-principal absence nor an order release.
"""
from __future__ import annotations
import re
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

class HandoffStop(ValueError):pass


OWNER_FENCE_GET_URL=(
    "https://api.github.com/repos/nicobouch97/fund100-state-private/"
    "contents/state/v6_s1_first_acwi_execution_owner_fence.json?ref=main"
)


def read_current_original_acwi_owner_fence_getonly(
        *,read_token:str,hmac_hex:str,transport=None)->dict:
    """Observe one genuine private READ principal; never CREATE an owner.

    404 is only ONE observed read with the already authenticated principal:
    it is not two-principal absence, not an immutable rollback witness, and
    never an order submission or owner-claim authorization. A 200 must be
    authenticated against the original HMAC/account/genesis instead of
    wrongly called absent. No private bytes or token leave this function.
    """
    if (type(read_token) is not str or len(read_token.strip())<10
        or type(hmac_hex) is not str
        or re.fullmatch(r"[0-9a-f]{64}",hmac_hex) is None):
        raise HandoffStop("Original fence read-only credential unavailable")
    import fund100_v6_s1_public_genesis_witness_v1_0 as witness
    import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
    try:
        w=witness.verify()
    except Exception:
        raise HandoffStop("Original signed fence witness/source mismatch") from None
    request=Request(OWNER_FENCE_GET_URL,method="GET",headers={
        "Accept":"application/vnd.github+json",
        "Authorization":"Bearer "+read_token,
        "X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"fund100-initial-acwi-owner-fence-single-readonly",
    })
    try:
        with (urlopen if transport is None else transport)(request,timeout=12) as resp:
            if getattr(resp,"status",None)!=200:
                raise HandoffStop("Unexpected original private fence response")
            raw=resp.read(26001)
        if len(raw)>26000:
            raise HandoffStop("Original private fence response too large")
        source=json.loads(raw.decode("utf-8"))
        # GitHub Contents GET returns line-wrapped base64 (normally
        # 60-character lines). The pure original fence parser intentionally
        # validates strict base64; strip ONLY GitHub's CR/LF transport wrapping
        # before rechecking Git blob SHA, canonical bytes and private HMAC.
        # No signature or account-binding validation is relaxed.
        if type(source) is not dict:
            raise HandoffStop("Original owner-fence GET body malformed")
        encoded=source.get("content")
        if type(encoded) is str:
            source["content"]=encoded.replace("\r","").replace("\n","")
    except HTTPError as exc:
        if (exc.code==404 and exc.url==OWNER_FENCE_GET_URL
            and request.get_method()=="GET"):
            return {
                "status":"OWNER_FENCE_NOT_VISIBLE_TO_ORIGINAL_READ_PRINCIPAL",
                "read_principal_get_succeeded_as_404":True,
                "read_scope_original_private_repo_verified_here":False,
                "write_principal_absence_independently_verified":False,
                "owner_fence_signed_head_exists":False,
                "owner_fence_created_by_this_read":False,
                "external_immutable_rollback_anchor_verified":False,
                "owner_claim_or_broker_POST_authorized":False,
                "real_private_Git_PUTs":0,"broker_orders":0,
                "private_body":None,"account_binding":None,
            }
        raise HandoffStop("Private fence GET failed or not authorized") from None
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
        raise HandoffStop("Original private owner-fence GET ambiguous; STOP") from None
    try:
        source_sha,doc=fence._read(
            source,
            private_genesis=w["original_public_genesis_nonce"],
            account_binding_sha256=w["original_live_account_binding_sha256"],
            key=bytes.fromhex(hmac_hex))
        if (type(source_sha) is not str or len(source_sha)!=40
            or doc["sequence"] not in (0,1)):
            raise HandoffStop("Authenticated original fence source missing")
    except Exception:
        raise HandoffStop("Unexpected or tampered signed first owner fence") from None
    return {
        "status":("SIGNED_UNCLAIMED_FIRST_ACWI_OWNER_FENCE_READONLY"
                  if doc["sequence"]==0 else
                  "SIGNED_ALREADY_CLAIMED_FIRST_ACWI_OWNER_FENCE_HOLD"),
        "read_principal_get_succeeded_as_404":False,
        "read_scope_original_private_repo_verified_here":False,
        "write_principal_absence_independently_verified":False,
        "owner_fence_signed_head_exists":True,
        "owner_fence_created_by_this_read":False,
        "external_immutable_rollback_anchor_verified":False,
        "owner_claim_or_broker_POST_authorized":False,
        "real_private_Git_PUTs":0,"broker_orders":0,
        "private_body":None,"account_binding":None,
    }
