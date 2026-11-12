"""Source-locked, OFFLINE ONLY plan for externally triggered Fund-100 STOP.

A future continuously running risk monitor may ask GitHub to dispatch the
ALREADY reviewed manual emergency workflow. That workflow owns GitHub STOP
writes and existing selective Alpaca cancellation jobs. The monitor must
NEVER get brokerage trading credentials or a GitHub Contents-write token.

This module is not an HTTP transport and never actually triggers an action.
An Actions:write fine-grained GitHub credential can dispatch OTHER workflows
too: it is NOT intrinsically STOP-only. A dedicated future isolated caller,
GitHub policy review, approved credential provisioning, alert/retry protocol,
and live automatic STOP/cancel end-to-end evidence are all still required.
"""
from __future__ import annotations

SCHEMA = "FUND100_V6_EXTERNAL_EMERGENCY_STOP_DISPATCH_INTENT_V1"
STOP_DISPATCH_PLANNING_RELEASED = False
HTTP_DISPATCH_TRANSPORT_RELEASED = False
NO_NETWORK = True
NO_BROKER_CREDENTIAL = True
NO_BROKER_POST_OR_DELETE = True
NO_GITHUB_CONTENTS_WRITE = True
NO_TRADE_RELEASE = True
NEVER_RETRY_UNKNOWN_DISPATCH = True
NEVER_REPORT_STOP_CONFIRMED = True

# Exact documented GitHub Actions workflow_dispatch REST endpoint.
# Always target the already-reviewed manual STOP workflow, never the
# first-ACWI order workflow and never a caller-supplied URL, ref or inputs.
ENDPOINT = (
    "https://api.github.com/repos/nicobouch97/fund100-research/"
    "actions/workflows/fund100-live-emergency-stop.yml/dispatches"
)
REF = "main"
BODY_UTF8 = '{"ref":"main"}'
# GitHub workflow_dispatch API 2026-03-10 returns a specific run id by
# default (since the February 2026 run-details improvement). This proves
# which run was requested, NOT that STOP/cancel succeeded.
GITHUB_API_VERSION_IF_SENT = "2026-03-10"
EXPECTED_HTTP_STATUS_IF_SENT = 200
EXPECTED_RESPONSE_FIELDS = ("workflow_run_id", "run_url", "html_url")
FUTURE_REQUIRED_GITHUB_PERMISSION = "Actions:write"
OUTAGE_REASONS = frozenset((
    "BROKER_RISK_HOLD",
    "BROKER_API_UNAVAILABLE",
    "BROKER_ACCOUNT_UNKNOWN",
    "SIGNED_RECEIPT_MISSING",
    "SIGNED_RECEIPT_EXPIRED",
    "SIGNED_RECEIPT_INVALID",
    "MONITOR_RECOVERED_FROM_OUTAGE_NEEDS_RECONCILIATION",
    "OPERATOR_STATE_UNAVAILABLE",
    "CANCEL_RECONCILIATION_UNKNOWN",
))


class StopDispatchIntentError(RuntimeError):
    """Do not interpret a failure to plan as an acknowledged emergency STOP."""


def plan_stop_only_dispatch(*, reason: object) -> dict:
    """Return a fixed, credentialless STOP intent; NEVER transmit it.

    The caller may report any enumerated risk HOLD; because STOP is
    one-directional there is no operator-GO mode and no user-provided
    job inputs. This is not risk data validation or authentication.
    """
    if STOP_DISPATCH_PLANNING_RELEASED is not True:
        raise StopDispatchIntentError("Independent STOP dispatch intent HARD LOCKED")
    if HTTP_DISPATCH_TRANSPORT_RELEASED is not False or any((
        NO_NETWORK is not True, NO_BROKER_CREDENTIAL is not True,
        NO_BROKER_POST_OR_DELETE is not True,
        NO_GITHUB_CONTENTS_WRITE is not True,
        NO_TRADE_RELEASE is not True,
        NEVER_RETRY_UNKNOWN_DISPATCH is not True,
        NEVER_REPORT_STOP_CONFIRMED is not True,
    )):
        raise StopDispatchIntentError("Independent STOP only-source contract changed")
    if type(reason) is not str or reason not in OUTAGE_REASONS:
        raise StopDispatchIntentError("Unrecognized risk HOLD category")
    return {
        "schema": SCHEMA,
        "status": "STOP_DISPATCH_PLAN_NOT_SENT",
        "method_if_separately_released": "POST",
        "endpoint": ENDPOINT,
        "json_body": BODY_UTF8,
        "expected_acceptance_status": EXPECTED_HTTP_STATUS_IF_SENT,
        "github_api_version_if_released": GITHUB_API_VERSION_IF_SENT,
        "expected_response_fields": EXPECTED_RESPONSE_FIELDS,
        "workflow_run_id_required_for_future_verification": True,
        "permission_required_if_released": FUTURE_REQUIRED_GITHUB_PERMISSION,
        "outage_category": reason,
        "dispatch_attempt_count": 0,
        "dispatch_acknowledged": False,
        "github_stop_verified": False,
        "broker_cancel_verified": False,
        "new_trading_orders_allowed": False,
        "retry_after_unknown_dispatch": False,
        "broker_credentials_included": False,
        "github_contents_write_included": False,
        "inputs": None,
    }
