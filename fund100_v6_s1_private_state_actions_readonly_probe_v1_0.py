"""Private Fund-100 state repository: READ-ONLY GitHub Actions access check.

Does NOT read account/order state, HMACs, Alpaca, broker credentials, or
any production ledger. Verifies narrow cross-repository token on owner
controlled PRIVATE repository via exactly two GETs. Never emits secrets.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError,URLError
from urllib.parse import urlparse
from urllib.request import Request,urlopen

EXPECTED_REPO="nicobouch97/fund100-state-private"
EXPECTED_REPO_ID="1426833955"
BASE="https://api.github.com/repos/"+EXPECTED_REPO
ALLOW=frozenset((BASE,BASE+"/contents/README.md?ref=main"))
NO_LIVE_TRADING=True

class PrivateRepoProbeStop(RuntimeError):pass

def safe_get(*,url:str,token:str,transport=None):
    if type(url) is not str or url not in ALLOW:
        raise PrivateRepoProbeStop("Unreviewed private repo GET endpoint")
    parsed=urlparse(url)
    if parsed.scheme!="https" or parsed.hostname!="api.github.com":
        raise PrivateRepoProbeStop("Private storage API hostname mismatch")
    if type(token) is not str or not token.strip():
        raise PrivateRepoProbeStop("Missing private state read token")
    if transport is None:transport=urlopen
    req=Request(url,method="GET",headers={
       "Accept":"application/vnd.github+json",
       "Authorization":"Bearer "+token,
       "X-GitHub-Api-Version":"2022-11-28",
       "User-Agent":"fund100-private-state-readonly-check",
    })
    if req.get_method()!="GET":raise PrivateRepoProbeStop("GET-only boundary changed")
    try:
        with transport(req,timeout=12) as r:
            val=json.loads(r.read().decode("utf-8"))
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):
        raise PrivateRepoProbeStop("Private repo read-only authorization failed; redacted") from None
    if not isinstance(val,dict):
        raise PrivateRepoProbeStop("Private repo response must be object")
    return val

def classify(*,repo:dict,readme:dict)->dict:
    if (type(repo) is not dict
        or repo.get("full_name")!=EXPECTED_REPO
        or str(repo.get("id"))!=EXPECTED_REPO_ID
        or repo.get("private") is not True
        or repo.get("default_branch")!="main"
        or repo.get("archived") is True
        or type(readme) is not dict
        or readme.get("path")!="README.md"
        or readme.get("type")!="file"
        or readme.get("encoding")!="base64"
        or type(readme.get("sha")) is not str
        or len(readme["sha"])!=40
        or type(readme.get("content")) is not str):
        raise PrivateRepoProbeStop("Private repository identity/visibility/source mismatch")
    return {
      "schema":"FUND100_V6_S1_PRIVATE_CROSS_ACTIONS_READONLY_CHECK_V1",
      "private_repo_verified":True,
      "verified_private_owner_name_and_repo_id":True,
      "default_branch_main":True,
      "readme_reachable":True,
      "cross_repo_write_access_proven":False,
      "remote_CAS_or_stale_conflict_tested":False,
      "offhost_rollback_anchor_verified":False,
      "production_state_file_exists_or_authorized":False,
      "alpaca_requests":0,
      "github_get_requests":2,
      "github_write_requests":0,
      "broker_order_requests":0,
      "private_token_or_payload":None,
      "live_trading_authorized":False,
    }

def main():
    if (os.getenv("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or os.getenv("GITHUB_REF")!="refs/heads/main"
        or os.getenv("FUND100_BROKER_KILL_SWITCH")!="ENGAGED"):
        raise PrivateRepoProbeStop("Only original stopped Fund-100 main can check state")
    token=os.getenv("FUND100_PRIVATE_STATE_READ_TOKEN","")
    r=safe_get(url=BASE,token=token)
    readme=safe_get(url=BASE+"/contents/README.md?ref=main",token=token)
    result=classify(repo=r,readme=readme)
    for key in ("schema","private_repo_verified",
                "verified_private_owner_name_and_repo_id",
                "readme_reachable","cross_repo_write_access_proven",
                "remote_CAS_or_stale_conflict_tested",
                "production_state_file_exists_or_authorized",
                "github_get_requests","github_write_requests",
                "broker_order_requests","live_trading_authorized"):
        print(key+":",result[key])
    print("Private content and token never printed or persisted.")

if __name__=="__main__":
    main()
