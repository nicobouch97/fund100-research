"""Independent scheduled original V6-S1 ACWI HIGH account-risk watch.

Unlike the legacy V5 watcher, this requires historical V5 STOP and checks
the *separate* V6 current-main GO. When V6 is STOPPED, do zero broker GETs.
When V6 original ACWI is GO, perform the reviewed eight fixed live broker
GETs, verify full original inventory, 6/20/35 and funded NYSE sessions, and
attest PASS only for this positive outcome. On failure try a scoped STOP-only
GitHub CAS and selective Fund-100 order cancellation, no new broker order.
Source hard-locks are NOT bypassed or released by this monitoring path.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
import re

import fund100_live_operator_control_v1_0 as v5
import fund100_v6_s1_operator_control_v2_0 as v6
import fund100_v6_s1_active_high_acwi_sell_risk_v2_0 as active
import fund100_v6_s1_protected_first_acwi_intent_only_v1_0 as intent
import fund100_v6_brokerless_transition_preview_v1_0 as original
import fund100_v6_real_live_getonly_transition_readiness_v1_0 as original_files
import fund100_v6_s1_live_risk_history_getonly_v1_0 as history
import fund100_v6_s1_live_private_xle_activity_getonly_v1_0 as activities
import fund100_v6_s1_live_flow_timing_native_none_getonly_v1_0 as native
import fund100_v6_s1_three_month_prefunding_probe_v1_0 as extended
import fund100_alpaca_live_readonly_smoke as broker
import fund100_v6_s1_first_acwi_signed_cancel_only_v1_0 as cancel

SCHEMA = "FUND100_V6_S1_INDEPENDENT_SCHEDULED_ACWI_RISK_WATCH_V1"
WATCH_REF = ("nicobouch97/fund100-research/.github/workflows/"
             "fund100-v6-s1-independent-risk-watch.yml@refs/heads/main")
NO_BROKER_POST = True
NO_TRADE_RELEASE = True
# Source-only staging: deliberately not callable until separate signed review.
SCHEDULED_RUNTIME_RELEASED = False
NO_OPERATOR_GO_WRITE = True
MAX_STOP_CAS_ATTEMPTS = 1
EXPECTED_PASS = "WITHIN_V6_S1_ORIGINAL_ACWI_RISK_LIMITS"


class V6WatchStop(RuntimeError):
    pass


def _scope() -> None:
    e = os.environ
    if (e.get("GITHUB_ACTIONS") != "true"
        or e.get("GITHUB_REPOSITORY") != v6.EXPECTED_REPO
        or e.get("GITHUB_REF") != "refs/heads/main"
        or e.get("GITHUB_EVENT_NAME") != "schedule"
        or e.get("GITHUB_WORKFLOW_REF") != WATCH_REF
        or e.get("GITHUB_RUN_ATTEMPT") != "1"
        or type(e.get("GITHUB_SHA")) is not str
        or re.fullmatch(r"[0-9a-f]{40}", e["GITHUB_SHA"]) is None
        or e.get("FUND100_RISK_LEVEL") != "HIGH"
        or e.get("FUND100_ENABLE_LIVE_READONLY") != "YES_READ_ONLY_LIVE"):
        raise V6WatchStop("V6 scheduled main watcher scope invalid")


def _current_v6_first_go() -> bool:
    state = v6.read_current_control()
    if (state["trading_enabled"] is True
        and state["first_original_acwi_sell_enabled"] is True):
        return True
    if (state["trading_enabled"] is False
        and state["first_original_acwi_sell_enabled"] is False):
        return False
    raise V6WatchStop("V6 first ACWI GO state not coherent")


def _check_main_stopped_and_v6_go() -> None:
    if v5.validate_control(v5.read_current_control()) is not False:
        raise V6WatchStop("Historical V5 operator must remain STOP")
    if v6.require_s1_running() is not True:
        raise V6WatchStop("V6 first ACWI operator STOP or unavailable")
    if os.environ.get("FUND100_BROKER_KILL_SWITCH") != "DISENGAGED":
        raise V6WatchStop("V6 broker kill switch not released")
    broker.require_readonly_arm()


def _risk_eight_get() -> str:
    """Fixed original eight broker GETs; no writer, no order POST."""
    _scope()
    _check_main_stopped_and_v6_go()
    key, secret = broker.load_credentials()
    approved = (
        ("/v2/account", None),
        ("/v2/positions", None),
        ("/v2/orders", {"status":"open", "limit":100}),
        ("/v2/clock", None),
        (history.HISTORY_PATH, history.HISTORY_PARAMS),
        (activities.ACTIVITIES_PATH, activities.ACTIVITY_PARAMS),
        (history.HISTORY_PATH, native.EXTRA_PARAMS),
        (history.HISTORY_PATH, extended.EXTENDED_PARAMS),
    )
    if (tuple(path for path, _ in approved[:7]) != native.PATHS
        or approved[-1] != (history.HISTORY_PATH,
                           {"period":"3M", "timeframe":"1D"})):
        raise V6WatchStop("Fixed eight original broker GET contract changed")
    docs = []
    for index, (path, params) in enumerate(approved):
        docs.append(broker.get_json(path=path, params=params,
                                    key=key, secret=secret))
        # A closed exchange is normal before/after market; it must NOT
        # continually auto-STOP an otherwise safely armed standing V6.
        # It also must never emit a broker-risk PASS for a pending order.
        if (index == 3 and type(docs[3]) is dict
            and docs[3].get("is_open") is False):
            _check_main_stopped_and_v6_go()
            return "MARKET_CLOSED_NO_PASS"
    _check_main_stopped_and_v6_go()
    bootstrap, _ = original.original(original_files.BOOT)
    policy, _ = original.original(original_files.POLICY)
    qty = intent.original_acwi_qty()
    observed = datetime.now(timezone.utc).isoformat().replace("+00:00","Z")
    checked = active.evaluate_original_sell_only(
        account=docs[0], positions=docs[1], orders=docs[2],
        clock=docs[3], history=docs[4], activities=docs[5],
        native_none_history=docs[6], extended_history=docs[7],
        bootstrap=bootstrap, original_policy=policy, original_qty=qty,
        observed_at_utc=observed)
    if (type(checked) is not dict
        or checked.get("schema") != active.SCHEMA
        or checked.get("status") !=
           "ORIGINAL_ACWI_ORDER_TIME_BROKER_RISK_LIVE_AUTHORIZED_V2"
        or checked.get("same_process_real_broker_gets") != 8
        or checked.get("original_acwi_exact_fractional_holdings_verified") is not True
        or checked.get("original_strict_postfunding_6_20_35_risk_pass") is not True
        or checked.get("broker_post_attempts") != 0
        or checked.get("orders_submitted_here") != 0
        or checked.get("buy_authorized") is not False):
        raise V6WatchStop("Independent V6 account risk did not PASS")
    # Do not treat the pure active source's *candidate* sell-allowed flag as
    # production permission; this is an independent GET-only watcher only.
    _check_main_stopped_and_v6_go()
    _scope()
    return EXPECTED_PASS


def _stop_v6_first_only() -> str:
    """STOP-only current-main CAS, exactly one PUT, no retry on unknown ACK.

    Invokable only from this pinned original V6 scheduled watcher. It does not
    weaken or change the separate manual emergency-stop entrypoint.
    """
    _scope()
    if MAX_STOP_CAS_ATTEMPTS != 1:
        raise V6WatchStop("Unsafe V6 STOP retry policy")
    token = v6._token()
    existing = v6._request(method="GET", token=token)
    before = v6._parse(existing)
    if (before["trading_enabled"] is False
        and before["first_original_acwi_sell_enabled"] is False):
        return "ALREADY_STOPPED"
    safe = dict(before, trading_enabled=False,
                first_original_acwi_sell_enabled=False)
    v6._validate(safe)
    raw = (json.dumps(safe, sort_keys=True, indent=2) + chr(10)).encode()
    payload = json.dumps({
        "branch": "main",
        "sha": existing["sha"],
        "message": "AUTOMATIC V6 S1 RISK STOP: independent account risk HOLD",
        "content": base64.b64encode(raw).decode("ascii"),
    }, sort_keys=True).encode()
    v6._request(method="PUT", token=token, raw=payload)
    if _current_v6_first_go():
        raise V6WatchStop("V6 automatic risk STOP not confirmed")
    return "STOPPED"


def _emit_pass_only() -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if type(output) is not str or not output:
        raise V6WatchStop("Missing PASS-only scheduled GitHub output")
    with open(output, "a", encoding="utf-8") as stream:
        stream.write("verified_v6_original_acwi_risk=YES" + chr(10))


def watch_once() -> str:
    if SCHEDULED_RUNTIME_RELEASED is not True:
        raise V6WatchStop("Independent watcher source remains unreleased")
    _scope()
    try:
        if not _current_v6_first_go():
            # Verified initial pre-launch STOP: no broker request and no PASS.
            return "ALREADY_STOPPED"
        verdict = _risk_eight_get()
        if verdict == "MARKET_CLOSED_NO_PASS":
            return verdict
        if verdict != EXPECTED_PASS:
            raise V6WatchStop("V6 broker risk PASS unavailable")
        _emit_pass_only()
        return EXPECTED_PASS
    except Exception:
        # Failed source or future market-hour risk violation: first prevent
        # any further order by confirming a persistent V6 current-main STOP.
        # Never leak source financial data or raw API error responses.
        print("Independent V6 original ACWI risk unavailable; requesting STOP.")
        stop_confirmed = False
        try:
            stop_confirmed = _stop_v6_first_only() in (
                "STOPPED", "ALREADY_STOPPED")
        except Exception:
            pass  # Unknown STOP ack: NEVER retry; STILL attempt cancellation.
        cancel_confirmed = False
        try:
            # Independent best-effort selective cancellation, even if the
            # V6 Git STOP CAS failed, raced or had an unknown acknowledgement.
            # No other account orders and no positions may be touched.
            cancel.cancel_open_first_signed_acwi_orders()
            cancel_confirmed = True
        except Exception:
            pass
        if not stop_confirmed:
            raise V6WatchStop("V6 automatic STOP unconfirmed; cancel attempted; HOLD")
        if not cancel_confirmed:
            raise V6WatchStop("V6 STOP confirmed but order cancel uncertain")
        return "AUTO_STOP_CONFIRMED"


if __name__ == "__main__":
    print("Fund-100 V6 independent ACWI risk watch:", watch_once())
