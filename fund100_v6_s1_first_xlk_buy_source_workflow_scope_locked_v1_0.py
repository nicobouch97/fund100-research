"""Workflow provenance for post-ACWI GETs reused by first funded XLK BUY.

The original POSTORDER GET-only Actions workflow remains recognised as before.
The original 1x cash/HIGH-risk readers are *not* allowed to run in a funded
BUY workflow by default; that distinct delegation requires a separately
reviewed immutable SOURCE CODE release, beyond the writer's own release,
even if ambient GitHub environment strings are forged.

This module never makes requests, generates executable order permits, changes
the V6 operator STOP, or makes the first BUY source real.
"""
from __future__ import annotations

READONLY_POSTORDER_WORKFLOW_REF=(
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-s1-original-postorder-getonly.yml@refs/heads/main"
)
FIRST_XLK_FUNDED_BUY_WORKFLOW_REF=(
    "nicobouch97/fund100-research/.github/workflows/"
    "fund100-v6-s1-first-xlk-buy-funded-once.yml@refs/heads/main"
)
FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED=False
NO_HTTP=True
NO_BROKER_POST=True
NO_PRIVATE_GIT_WRITE=True

def qualifies(*,environ:dict)->bool:
    """Identity check only, NOT an authorisation for LIVE GET or BUY.

    Caller MUST independently require its own review-released source flag,
    broker GET-only arm, real GitHub principals and LIVE account ownership.
    This does not verify supplied environment values came from GitHub.
    """
    if (type(environ) is not dict
        or environ.get("GITHUB_ACTIONS")!="true"
        or environ.get("GITHUB_REPOSITORY")!="nicobouch97/fund100-research"
        or environ.get("GITHUB_REF")!="refs/heads/main"
        or environ.get("GITHUB_RUN_ATTEMPT")!="1"
        or environ.get("FUND100_RISK_LEVEL")!="HIGH"
        or environ.get("FUND100_ENABLE_LIVE_READONLY")!="YES_READ_ONLY_LIVE"):
        return False
    ref=environ.get("GITHUB_WORKFLOW_REF")
    event=environ.get("GITHUB_EVENT_NAME")
    kill=environ.get("FUND100_BROKER_KILL_SWITCH")
    if ref==READONLY_POSTORDER_WORKFLOW_REF:
        return (event in ("schedule","workflow_dispatch")
                and kill in ("ENGAGED","DISENGAGED"))
    # A read-only inspection is not a standing permission to BUY.
    # Delegation needs exact BUY workflow identity AND its own code review.
    if ref==FIRST_XLK_FUNDED_BUY_WORKFLOW_REF:
        return (FIRST_XLK_BUY_POSTORDER_GET_DELEGATION_RELEASED is True
                and event=="schedule"
                and kill=="DISENGAGED")
    return False
