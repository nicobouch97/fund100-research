"""Redacted GET-only diagnosis of private production WRITE-candidate GitHub PAT.

This checks a genuine authenticated /user endpoint, then one exact private
owner-Contents path whose existence the separate READ principal confirms.
It NEVER proves Contents(write), never retrieves secrets into a report,
never submits a GitHub mutation or Alpaca request, and never changes STOP.
The existing strict signed five-principal gate still runs afterwards.
"""
from __future__ import annotations

import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

SCHEMA = "FUND100_V6_PRIVATE_WRITER_CANDIDATE_HTTP_GET_DIAGNOSIS_V1"
USER_URL = "https://api.github.com/user"
OWNER_URL = ("https://api.github.com/repos/nicobouch97/fund100-state-private/"
             "contents/state/v6_s1_first_acwi_execution_owner_fence.json?ref=main")
URL_ALLOWLIST = frozenset({USER_URL, OWNER_URL})
NO_GIT_WRITES = NO_BROKER_CALLS = True
PRIVATE_PUTS = BROKER_POSTS = 0
WRITER_PERMISSION_ESTABLISHED = LIVE_TRADE_AUTHORIZED = False
SAFE_HTTP_CODES = frozenset({200, 401, 403, 404, 429})
MAX_USER_BYTES = 4096


class DiagnosticStop(RuntimeError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DiagnosticStop("Protected GitHub GET redirect rejected")


def _token(environ, key):
    value = environ.get(key)
    if (type(value) is not str or len(value) < 10
        or value != value.strip() or "\r" in value or "\n" in value):
        raise DiagnosticStop("Missing or malformed protected principal: " + key)
    return value


def _category(code, remaining):
    if code == 200:
        return "HTTP_200"
    if code == 401:
        return "HTTP_401_TOKEN_NOT_AUTHENTICATED"
    if code == 403 and remaining == "0":
        return "HTTP_403_RATE_LIMIT_INDICATED"
    if code == 403:
        return "HTTP_403_ACCESS_DENIED_OR_RATE_LIMIT_UNPROVEN"
    if code == 404:
        return "HTTP_404_RESOURCE_NOT_VISIBLE_TO_THIS_PRINCIPAL"
    if code == 429:
        return "HTTP_429_RATE_LIMITED"
    if type(code) is int and 500 <= code <= 599:
        return "HTTP_5XX_GITHUB_UNAVAILABLE"
    return "HTTP_UNEXPECTED_OR_TRANSPORT_UNCERTAIN"


def _get_status(*, url, token, transport=None, authenticate_user=False):
    if url not in URL_ALLOWLIST or (authenticate_user != (url == USER_URL)):
        raise DiagnosticStop("Unapproved GitHub diagnostic GET endpoint")
    req = Request(url, method="GET", headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Cache-Control": "no-store",
        "User-Agent": "fund100-private-writer-candidate-get-diagnostic",
    })
    sender = build_opener(NoRedirect()).open if transport is None else transport
    try:
        with sender(req, timeout=12) as response:
            status = getattr(response, "status", None)
            remaining = response.headers.get("X-RateLimit-Remaining") if getattr(
                response, "headers", None) is not None else None
            if status != 200:
                return _category(status, remaining)
            if authenticate_user:
                raw = response.read(MAX_USER_BYTES + 1)
                if len(raw) > MAX_USER_BYTES:
                    return "HTTP_200_BUT_AUTH_IDENTITY_INVALID"
                profile = json.loads(raw)
                if (type(profile) is not dict
                    or type(profile.get("login")) is not str
                    or not profile["login"]):
                    return "HTTP_200_BUT_AUTH_IDENTITY_INVALID"
            # On owner Contents, do not read or log the signed private source:
            # this is permission/reachability diagnosis, NOT signed validation.
            return "HTTP_200"
    except HTTPError as exc:
        remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
        return _category(exc.code, remaining)
    except DiagnosticStop:
        return "HTTP_REDIRECT_OR_UNAPPROVED_DESTINATION"
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError, TypeError):
        return "HTTP_UNEXPECTED_OR_TRANSPORT_UNCERTAIN"
    except Exception:
        # No raw HTTP response or exception string may enter Actions logs.
        return "HTTP_UNEXPECTED_OR_TRANSPORT_UNCERTAIN"


def diagnose(*, environ=None, transport=None):
    e = os.environ if environ is None else environ
    if (e.get("GITHUB_ACTIONS") != "true"
        or e.get("GITHUB_REPOSITORY") != "nicobouch97/fund100-research"
        or e.get("GITHUB_REF") != "refs/heads/main"
        or e.get("GITHUB_RUN_ATTEMPT") != "1"
        or e.get("GITHUB_EVENT_NAME") not in ("push", "workflow_dispatch")
        or e.get("FUND100_BROKER_KILL_SWITCH") != "ENGAGED"
        or e.get("FUND100_RISK_LEVEL") != "HIGH"):
        raise DiagnosticStop("Protected main original HIGH/STOP context unavailable")
    read = _token(e, "FUND100_PRIVATE_STATE_READ_TOKEN")
    write = _token(e, "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN")
    if read == write:
        raise DiagnosticStop("Original private principal separation required")
    baseline = _get_status(url=OWNER_URL, token=read, transport=transport)
    if baseline != "HTTP_200":
        raise DiagnosticStop("Authenticated private owner READ baseline not available")
    auth = _get_status(
        url=USER_URL, token=write, transport=transport, authenticate_user=True)
    owner = (_get_status(url=OWNER_URL, token=write, transport=transport)
             if auth == "HTTP_200" else "SKIPPED_CANDIDATE_USER_NOT_AUTHENTICATED")
    if auth != "HTTP_200":
        assessment = "CANDIDATE_AUTHENTICATION_UNAVAILABLE_HOLD"
    elif owner == "HTTP_200":
        assessment = "CANDIDATE_OWNER_GET_HTTP_200_NOT_WRITE_PROOF"
    elif owner == "HTTP_404_RESOURCE_NOT_VISIBLE_TO_THIS_PRINCIPAL":
        assessment = "CANDIDATE_AUTHENTICATED_BUT_PRIVATE_OWNER_NOT_VISIBLE_HOLD"
    else:
        assessment = "CANDIDATE_PRIVATE_OWNER_GET_NOT_VERIFIED_HOLD"
    return {
        "schema": SCHEMA, "assessment": assessment,
        "independent_reader_owner_get": "HTTP_200",
        "write_candidate_user_auth_get": auth,
        "write_candidate_owner_get": owner,
        "candidate_github_contents_write_permission_verified": False,
        "production_private_git_puts": 0,
        "broker_posts": 0,
        "live_orders_authorized": False,
        "approval_prompt_required": False,
    }


def main():
    outcome = diagnose()
    for name in ("assessment", "write_candidate_user_auth_get",
                 "write_candidate_owner_get"):
        print(name + "=" + outcome[name])
    print("PRIVATE_WRITER_CANDIDATE_NOT_WRITE_VERIFIED; NO GIT PUT OR BROKER POST")


if __name__ == "__main__":
    main()
