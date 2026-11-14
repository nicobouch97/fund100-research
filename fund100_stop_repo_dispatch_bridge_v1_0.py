"""Original STOP -> repository_dispatch event bridge, dispatch-only.

This executes ONLY inside the existing protected original emergency STOP's
broker-credentialless GitHub Contents:write job. GitHub documents
repository_dispatch as a GITHUB_TOKEN recursion exception. The sole POST
asks a separate GitHub GET-only observer to re-read THIS original run once
all three original jobs finish; it is never STOP completion proof.

No new broker access, no order operation, no control writes, no GO,
no signed receipt, no unbounded retry and no user authorization per trade.
"""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPO = "nicobouch97/fund100-research"
API = "https://api.github.com/repos/" + REPO
ENDPOINT = API + "/dispatches"
EXPECTED_WORKFLOW_REF = (REPO + "/.github/workflows/"
                         "fund100-live-emergency-stop.yml@refs/heads/main")
EVENT_TYPE = "fund100-original-stop-outcome-readonly-v1"
NO_BROKER_ACCESS = True
NO_GITHUB_CONTENTS_MUTATION = True
NO_STOP_DISPATCH = True
NO_ORDER = True
NO_SIGNER = True
NO_TRADE_REARM = True
NO_SUCCESS_CLAIM = True
NO_RETRY = True


class BridgeHold(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise BridgeHold("Refusing repository dispatch redirect")


def _scope() -> int:
    e = os.environ
    if (not all((NO_BROKER_ACCESS, NO_GITHUB_CONTENTS_MUTATION,
                 NO_STOP_DISPATCH, NO_ORDER, NO_SIGNER,
                 NO_TRADE_REARM, NO_SUCCESS_CLAIM, NO_RETRY))
        or e.get("GITHUB_ACTIONS") != "true"
        or e.get("GITHUB_REPOSITORY") != REPO
        or e.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
        or e.get("GITHUB_REF") != "refs/heads/main"
        or e.get("GITHUB_WORKFLOW_REF") != EXPECTED_WORKFLOW_REF
        or e.get("GITHUB_RUN_ATTEMPT") != "1"
        or re.fullmatch(r"[0-9a-f]{40}",e.get("GITHUB_SHA","")) is None
        or any(k in e for k in (
            "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
            "ALPACA_PAPER_KEY","ALPACA_PAPER_SECRET",
            "FUND100_STOP_SIGNER_ED25519_PRIVATE_HEX",
            "FUND100_V6_RISK_SIGNER_ED25519_PRIVATE_HEX",
        ))):
        raise BridgeHold("Wrong original STOP dispatch-only source scope")
    run=e.get("GITHUB_RUN_ID","")
    if (type(run) is not str
        or re.fullmatch(r"[1-9][0-9]{0,18}",run) is None):
        raise BridgeHold("Original STOP run ID not canonical")
    return int(run)


def _token() -> str:
    tok=os.getenv("GITHUB_TOKEN","")
    if (type(tok) is not str or not 20<=len(tok)<=4096
        or re.search(r"\s",tok) is not None):
        raise BridgeHold("Protected original STOP token missing")
    return tok


def _payload(run_id: int) -> bytes:
    if type(run_id) is not int or not 0<run_id<10**19:
        raise BridgeHold("Invalid original STOP event ID")
    return json.dumps({
        "event_type":EVENT_TYPE,
        "client_payload":{"original_stop_run_id":str(run_id)},
    },sort_keys=True,separators=(",",":")).encode("ascii")


def _send_once(*, run_id: int, token: str) -> None:
    raw=_payload(run_id)
    if (type(token) is not str or not 20<=len(token)<=4096
        or re.search(r"\s",token) is not None):
        raise BridgeHold("Invalid bridge token")
    req=Request(ENDPOINT,method="POST",data=raw,headers={
        "Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2026-03-10",
        "Content-Type":"application/json",
        "Cache-Control":"no-store",
        "User-Agent":"fund100-stop-to-getonly-repository-dispatch",
    })
    try:
        with build_opener(NoRedirect()).open(req,timeout=8) as response:
            if response.status!=204 or response.geturl()!=ENDPOINT:
                raise BridgeHold("Repository dispatch ACK not verified")
            if response.read(1):
                raise BridgeHold("Unexpected dispatch response body")
    except (HTTPError,URLError,TimeoutError,OSError):
        raise BridgeHold("Repository dispatch outcome unknown; NO RETRY") from None


def main() -> None:
    try:
        run=_scope()
        _send_once(run_id=run,token=_token())
    except BridgeHold:
        print("BROKERLESS_OBSERVER_EVENT_UNVERIFIED; STOP_STAYS_ENGAGED")
        raise SystemExit(1) from None
    print("BROKERLESS_OBSERVER_EVENT_ACCEPTED; ORIGINAL_RUN_ID="+str(run))
    print("NOT_STOP_COMPLETION; NO_BROKER_OBSERVATION; NO_REARM")


if __name__=="__main__":
    main()
