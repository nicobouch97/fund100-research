"""Offline genuine compiler -> PAPER broker-state parity tests.

No credentials, no sockets and no real trading. This module explicitly
does not attest future compiler output freshness or enable order writes.
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

import fund100_v5_genuine_paper_parity_v1_0 as parity
from test_fund100_live_compiler_contract_v1_0 import compiler_output


UNIVERSE = {
    "ACWI", "SPY", "IWM", "EFA", "EEM", "VNQ", "XLK", "XLF",
    "XLI", "XLV", "XLP", "XLY", "XLE", "XLU",
}


def paper_snapshot():
    return {
        "account": {
            "status": "ACTIVE", "trading_blocked": False,
            "equity": "100", "cash": "0", "last_equity": "100",
        },
        "positions": {
            "ACWI": {"market_value": "75", "qty": "1"},
            "EEM": {"market_value": "10", "qty": "1"},
            "XLE": {"market_value": "10", "qty": "1"},
            "XLV": {"market_value": "5", "qty": "1"},
        },
        "open_orders": [],
    }


def paper_history(values=None):
    values = values or [100, 100, 100, 100, 100, 100, 100]
    now = datetime.now(timezone.utc)
    return {
        "timeframe": "1D",
        "timestamp": [
            int((now - timedelta(days=len(values) - i)).timestamp())
            for i in range(len(values))
        ],
        "equity": values,
    }


def plan(**overrides):
    args = {
        "compiler_body": compiler_output(),
        "paper_snapshot": paper_snapshot(),
        "paper_history": paper_history(),
        "execution_universe": UNIVERSE,
        "capital_ceiling": "130.30",
        "risk_level": "HIGH",
    }
    args.update(overrides)
    return parity.plan_genuine_paper_event(**args)


def test_genuine_v5_compiler_rebound_to_paper_positions_without_http():
    with patch.object(
        parity.production.live, "live_request",
        side_effect=AssertionError("Broker API called"),
    ), patch.object(
        parity.compiler.v10, "get_clock",
        side_effect=AssertionError("Compiler network called"),
    ):
        report = plan()
    assert report["status"] == "GENUINE_EVENT_PREFLIGHT_ONLY"
    assert report["executable"] is False
    assert report["risk_level"] == "HIGH"
    assert report["paper_order_count"] == 3
    assert report["gross_notional_usd"] == "6.00"
    assert report["paper_orders"] == [
        {
            "symbol": "EEM", "side": "sell", "notional_usd": "2.00",
            "client_order_id": report["paper_orders"][0]["client_order_id"],
        },
        {
            "symbol": "XLE", "side": "sell", "notional_usd": "1.00",
            "client_order_id": report["paper_orders"][1]["client_order_id"],
        },
        {
            "symbol": "XLV", "side": "buy", "notional_usd": "3.00",
            "client_order_id": report["paper_orders"][2]["client_order_id"],
        },
    ]
    assert all(
        o["client_order_id"].startswith("f100paper-")
        for o in report["paper_orders"]
    )
    assert all("f100live-" not in str(o) for o in report["paper_orders"])
    assert sum(report["paper_target_weights"].values()) == Decimal("1")


def test_no_genuine_compiler_event_short_circuits_without_broker_snapshot():
    body = compiler_output(genuine=False, status="NO_SCHEDULED_EVENT")
    body["candidate_intents"] = []
    body.pop("executed_satellite_weights")
    result = plan(
        compiler_body=body, paper_snapshot=None, paper_history=None,
    )
    assert result["status"] == "NO_GENUINE_EVENT"
    assert result["paper_orders"] == []
    assert result["executable"] is False


def test_genuine_compiler_without_intents_cannot_create_paper_orders():
    body = compiler_output()
    body["candidate_intents"] = []
    result = plan(
        compiler_body=body, paper_snapshot=None, paper_history=None,
    )
    assert result["status"] == "GENUINE_EVENT_NO_COMPILER_INTENTS"
    assert result["paper_orders"] == []


@pytest.mark.parametrize("risk_level", ["LOW", "MEDIUM"])
def test_reduced_risk_rejects_unapproved_directions(risk_level):
    # Shrinking a fully invested portfolio requires additional SELLs.
    # The paper-specific signal compiler MUST authorize those directions.
    # May produce a valid lower-risk plan only where exactly supported.
    with pytest.raises(parity.PaperParityStop):
        plan(risk_level=risk_level)


def test_open_order_or_foreign_position_blocks_paper_parity():
    source = paper_snapshot()
    source["open_orders"] = [{"id": "foreign-order"}]
    with pytest.raises(parity.PaperParityStop, match="open orders"):
        plan(paper_snapshot=source)

    source = paper_snapshot()
    source["positions"]["BTCUSD"] = {"qty": "1", "market_value": "20"}
    with pytest.raises(parity.PaperParityStop, match="outside"):
        plan(paper_snapshot=source)


def test_account_history_stale_or_unavailable_denies_plan():
    with pytest.raises(parity.PaperParityStop):
        plan(paper_history=None)
    stale = paper_history()
    stale["timestamp"] = [1000000000 + 86400 * i for i in range(7)]
    with pytest.raises(parity.PaperParityStop):
        plan(paper_history=stale)


def test_no_event_with_candidates_is_invalid():
    body = compiler_output(genuine=False, status="NO_SCHEDULED_EVENT")
    with pytest.raises(parity.PaperParityStop):
        plan(compiler_body=body)


def test_compiler_wrong_schema_does_not_generate_paper_execution():
    body = compiler_output()
    body["schema"] = "V5_UNREVIEWED"
    with pytest.raises(parity.PaperParityStop):
        plan(compiler_body=body)


def test_paper_parity_refuses_cap_below_position_exposure():
    with pytest.raises(parity.PaperParityStop):
        plan(capital_ceiling="50")


def test_snapshot_short_position_is_denied():
    source = paper_snapshot()
    source["positions"]["XLE"]["qty"] = "-1"
    with pytest.raises(parity.PaperParityStop, match="Short"):
        plan(paper_snapshot=source)


def test_risk_tier_missing_or_invalid_fails_closed():
    with pytest.raises(parity.PaperParityStop):
        plan(risk_level="")


def test_compiler_original_order_ids_cannot_be_replayed_to_paper():
    original = compiler_output()
    original_ids = {
        o["client_order_id"] for o in original["candidate_intents"]
    }
    plan_report = plan(compiler_body=original)
    paper_ids = {o["client_order_id"] for o in plan_report["paper_orders"]}
    assert not paper_ids.intersection(original_ids)
