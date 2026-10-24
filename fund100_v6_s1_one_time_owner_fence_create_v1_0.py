"""One confirmed signed owner-fence genesis CREATE; NEVER an Alpaca order.

Reuses original seq1 signed ACWI reader, original owner-fence schema and
existing private READ/WRITE secrets. Both distinct credentials must observe
404 immediately before a SINGLE absent-only Contents CREATE. A 422, timeout,
lost response or failed reread is a permanent STOP: NEVER retry a PUT here.
No Alpaca secret, order client or authenticated order transport exists.
"""
from __future__ import annotations
import json
import os
import re
from base64 import b64encode
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fund100_v6_s1_public_genesis_witness_v1_0 as witness
import fund100_v6_s1_acwi_unique_owner_fence_offline_v1_0 as fence
import fund100_v6_s1_private_git_cas_protocol_v1_0 as cas
import fund100_v6_s1_independent_signed_genesis_recovery_getonly_v1_0 as signed
import fund100_v6_s1_private_state_actions_readonly_probe_v1_0 as identity
import fund100_v6_s1_owner_fence_private_getonly_v1_0 as observer
import fund100_v6_s1_reconciled_high_live_policy_candidate_v1_0 as high

CONFIRM="INITIALIZE_SIGNED_ACWI_OWNER_FENCE_NO_ORDERS"
WRITE_URL=observer.OWNER_FENCE_GET_URL.split("?ref=main")[0]
NO_BROKER_NETWORK=True
LIVE_ORDER_RELEASED=False
MAX_OWNER_FENCE_CREATES=1
ORIGINAL_SIGNED_LEDGER_WRITE_ALLOWED=False
FIRST_OWNER_CLAIM_ALLOWED=False
GENESIS_COMMENT_ID="6321330005"
GENESIS_RUN_ID="39637082911"

class FenceCreateStop(RuntimeError):
    pass

def _token(value,label):
    if type(value) is not str or len(value.strip())<10:
        raise FenceCreateStop("Original "+label+" credential missing")
    return value

def _created_once(*,token,content_base64,transport=None):
    """No SHA field: GitHub Contents *CREATE* only, never overwrite/repair."""
    payload={"message":"fund100: initialize signed ACWI owner fence ONLY (NO ORDERS)",
             "branch":"main","content":content_base64}
    req=Request(WRITE_URL,method="PUT",
        data=json.dumps(payload,separators=(",",":"),sort_keys=True).encode("ascii"),
        headers={"Accept":"application/vnd.github+json",
                 "Authorization":"Bearer "+_token(token,"separate WRITE"),
                 "Content-Type":"application/json",
                 "X-GitHub-Api-Version":"2022-11-28",
                 "User-Agent":"fund100-one-time-owner-fence-genesis-no-orders"})
    try:
        with (urlopen if transport is None else transport)(req,timeout=12) as result:
            if getattr(result,"status",None)!=201:
                raise FenceCreateStop("Original owner-fence CREATE not uniquely acknowledged")
            raw=result.read(40_001)
        if len(raw)>40_000:
            raise FenceCreateStop("Owner-fence CREATE response too large; STOP")
        reply=json.loads(raw.decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,UnicodeError):
        raise FenceCreateStop("Original owner-fence create uncertain/denied; NEVER RETRY") from None
    if (type(reply) is not dict or type(reply.get("content")) is not dict):
        raise FenceCreateStop("Original owner-fence CREATE reply ambiguous; STOP")
    return reply

def _assert_absent(*,token,hmac_hex,transport=None,read_observer=observer.read_current_original_acwi_owner_fence_getonly):
    got=read_observer(read_token=token,hmac_hex=hmac_hex,transport=transport)
    if (type(got) is not dict
        or got.get("status")!="OWNER_FENCE_NOT_VISIBLE_TO_ORIGINAL_READ_PRINCIPAL"
        or got.get("read_principal_get_succeeded_as_404") is not True
        or got.get("owner_fence_signed_head_exists") is not False
        or got.get("owner_claim_or_broker_POST_authorized") is not False
        or got.get("real_private_Git_PUTs")!=0):
        raise FenceCreateStop("One independent owner-fence principal is NOT absent")
    return True

def execute(*,read_token,write_token,hmac_hex,public_token,source_root=Path("."),
            private_transport=None,write_transport=None,
            read_identity=identity.safe_get,
            signed_recovery=signed.recover_current_original_signed_head_readonly,
            read_observer=observer.read_current_original_acwi_owner_fence_getonly):
    if read_token==write_token:
        raise FenceCreateStop("Private read and production WRITE principals must differ")
    for label,token in (("READ",read_token),("WRITE",write_token),("public",public_token)):
        _token(token,label)
    if (type(hmac_hex) is not str
        or re.fullmatch(r"[0-9a-f]{64}",hmac_hex) is None):
        raise FenceCreateStop("Original verifier HMAC key invalid")
    # Original HIGH strategy remains proposal-only, broker STOP remains true.
    policy=high.contract(root=source_root)
    if (policy.get("orders_authorized") is not False
        or policy.get("stage")!="RECONCILED_SEPARATE_V6_HIGH_PROPOSED_POLICY_NO_ORDERS"):
        raise FenceCreateStop("Original HIGH STOP proposal changed")
    w=witness.verify(root=source_root)
    try:
        original=signed_recovery(
            public_comment_id=GENESIS_COMMENT_ID,
            bootstrap_run_id=GENESIS_RUN_ID,
            read_token=read_token,hmac_hex=hmac_hex,public_token=public_token,
            private_transport=private_transport)
        if (original.get("status")!="ORIGINAL_ACWI_SIGNED_SEQ1_AND_PUBLIC_HEAD_RECONFIRMED_READONLY"
            or original.get("private_ledger_sequence")!=1
            or original.get("first_reserved_symbol")!="ACWI"
            or original.get("first_reservation_state")!="RESERVED_NO_RETRY"
            or original.get("original_ACWI_qty_commitment_verified") is not True
            or original.get("production_trade_order_submission_authorized") is not False):
            raise FenceCreateStop("Original signed ACWI seq1/source unqualified")
        repo=read_identity(url=identity.BASE,token=write_token)
        readme=read_identity(url=identity.BASE+"/contents/README.md?ref=main",
                             token=write_token)
        identity.classify(repo=repo,readme=readme)
        # Two fresh, separate, authenticated credential views. 404 alone
        # is NOT an immutable witness or an order permit.
        _assert_absent(token=read_token,hmac_hex=hmac_hex,
                       transport=private_transport,read_observer=read_observer)
        _assert_absent(token=write_token,hmac_hex=hmac_hex,
                       transport=private_transport,read_observer=read_observer)
    except FenceCreateStop:
        raise
    except Exception:
        raise FenceCreateStop("Independent original signed source/absence unverified; STOP") from None

    raw=fence.synthetic_fence_genesis(
        private_genesis=w["original_public_genesis_nonce"],
        account_binding_sha256=w["original_live_account_binding_sha256"],
        key=bytes.fromhex(hmac_hex))
    expected_sha=cas.blob_sha(raw)
    if len(raw)>8000 or fence.PRODUCTION_FENCE_CREATED is not False:
        raise FenceCreateStop("Original signed first fence source invalid")
    # Exactly ONE irreversible CREATE request; no conflict or timeout retry.
    acknowledged=_created_once(token=write_token,
        content_base64=b64encode(raw).decode("ascii"),transport=write_transport)
    if (acknowledged["content"].get("path")!=fence.PATH
        or acknowledged["content"].get("sha")!=expected_sha):
        raise FenceCreateStop("Signed first owner-fence commit differs; NEVER RETRY")
    # Independent postcreate GET using READ (not WRITE) credential.
    try:
        reread=read_observer(read_token=read_token,hmac_hex=hmac_hex,
                             transport=private_transport)
    except Exception:
        raise FenceCreateStop("Independent owner-fence reread uncertain; NO RETRY") from None
    if (type(reread) is not dict
        or reread.get("status")!="SIGNED_UNCLAIMED_FIRST_ACWI_OWNER_FENCE_READONLY"
        or reread.get("owner_fence_signed_head_exists") is not True
        or reread.get("owner_claim_or_broker_POST_authorized") is not False):
        raise FenceCreateStop("Signed owner-fence postcreate HMAC reread mismatch; NO RETRY")
    return {
        "status":"FIRST_ORIGINAL_ACWI_SIGNED_OWNER_FENCE_GENESIS_CREATED_NO_ORDERS",
        "original_signed_order_ledger_sequence":1,
        "first_owner_fence_signed_sequence":0,
        "original_seq1_and_public_witness_verified":True,
        "independent_read_and_write_404_before_create":True,
        "signed_created_readback_verified":True,
        "owner_claim_exists":False,
        "immutable_external_anti_rollback_anchor_verified":False,
        "order_authorized":False,
        "ambiguous_create_retry_authorized":False,
        "real_private_fence_creates":1,
        "original_private_order_ledger_writes":0,
        "broker_GETs":0,"broker_POSTs":0,
        "raw_private_sha":None,"HMAC_key":None,"account_id":None,
    }

def main():
    e=os.environ
    if (e.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or e.get("GITHUB_EVENT_NAME")!="workflow_dispatch"
        or e.get("GITHUB_REF")!="refs/heads/main"
        or e.get("GITHUB_RUN_ATTEMPT")!="1"
        or e.get("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"
        or e.get("FUND100_RISK_LEVEL")!="HIGH"
        or e.get("FUND100_INITIAL_OWNER_FENCE_CONFIRM")!=CONFIRM):
        raise FenceCreateStop("Original first fence requires one stopped explicit main dispatch")
    control=json.loads(Path("fund100_live_operator_control.json").read_text())
    if control.get("trading_enabled") is not False:
        raise FenceCreateStop("Original operator trading control changed")
    result=execute(
        read_token=e.get("FUND100_PRIVATE_STATE_READ_TOKEN",""),
        write_token=e.get("FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",""),
        hmac_hex=e.get("FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",""),
        public_token=e.get("GITHUB_TOKEN",""))
    for field in ("status","original_signed_order_ledger_sequence",
        "first_owner_fence_signed_sequence",
        "original_seq1_and_public_witness_verified",
        "independent_read_and_write_404_before_create",
        "signed_created_readback_verified","owner_claim_exists",
        "immutable_external_anti_rollback_anchor_verified",
        "order_authorized","ambiguous_create_retry_authorized",
        "real_private_fence_creates","original_private_order_ledger_writes",
        "broker_GETs","broker_POSTs"):
        print(field+": "+str(result[field]))

if __name__=="__main__":
    main()
