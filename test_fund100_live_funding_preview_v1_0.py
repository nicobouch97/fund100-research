"""Credential-free tests for LIVE GET-only funding reference preview."""
from __future__ import annotations

from copy import deepcopy
from time import time

import pytest

import fund100_live_funding_preview_v1_0 as p

BINDING = "a" * 64


def base():
    policy = {
        "deployment_mode": "LIVE_MICRO_PILOT",
        "strategy": "V5-002_SHADOW",
        "capital_ceiling_usd": "130.30",
        "live_order_authorization_present": False,
        "autonomous_strategy_event_execution_enabled": False,
        "leverage_allowed": False,
        "shorting_allowed": False,
        "crypto_allowed": False,
        "additional_deposits_automatically_usable": False,
        "execution_universe": sorted(p.FROZEN_ETFS),
        "account_binding_sha256": BINDING,
    }
    shadow = {
        "strategy": "V5-002_SHADOW", "last_date": "2026-10-13",
        "pending_source": None, "pending_target": None,
        "satellite_weights": {symbol: (0.08 if symbol in {"EEM", "XLV", "XLE"}
                                      else 0.0)
                              for symbol in p.FROZEN_ETFS - {"ACWI"}},
    }
    history = {
        "timeframe": "1D",
        "timestamp": [int(time()) - 86400 * n for n in range(6, 0, -1)],
        "equity": [100.0] * 6,
    }
    return {
        "account": {"status": "ACTIVE", "trading_blocked": False,
                    "equity": "100.00", "cash": "0.50", "last_equity": "100.00"},
        "positions": [
            {"symbol": "ACWI", "qty": "1", "market_value": "75.50"},
            {"symbol": "EEM", "qty": "1", "market_value": "8.00"},
            {"symbol": "XLV", "qty": "1", "market_value": "8.00"},
            {"symbol": "XLE", "qty": "1", "market_value": "8.00"},
        ],
        "open_orders": [],
        "history": history, "shadow": shadow, "policy": policy,
        "binding": BINDING, "risk_level": "HIGH",
    }


def check(**patch):
    return p.preview(**{**base(), **patch})


def test_no_delta_does_not_invent_authority():
    d = base()
    d["positions"][0]["market_value"] = "76.00"
    d["account"]["cash"] = "0"
    result = p.preview(**d)
    assert result["funding_classification"] == "NO_ACTIONABLE_REFERENCE_DELTAS"
    assert result["live_execution_authorized"] is False
    assert result["broker_mutations"] == 0
    assert result["fresh_post_sell_cash_recheck_required"] is True


def test_zero_cash_cannot_claim_buy_is_funded():
    d = base()
    d["positions"][0]["market_value"] = "69.5"
    d["account"]["cash"] = "0"
    result = p.preview(**d)
    assert result["reference_buy_count"] > 0
    assert result["cash_alone_covers_reference_buys"] is False
    assert result["funding_classification"] == (
        "REFERENCE_BUYS_NOT_COVERED_BY_CASH_OR_DISCOUNTED_SELLS"
    )


def test_cash_only_hypothesis_not_an_order():
    d = base()
    d["account"]["cash"] = "100"
    d["positions"] = []
    result = p.preview(**d)
    assert result["reference_buy_count"] >= 1
    assert result["cash_alone_covers_reference_buys"] is True
    assert result["live_execution_authorized"] is False


@pytest.mark.parametrize("patch", [
    {"cash": "-1"},
    {"equity": "0"},
    {"status": "SUSPENDED"},
    {"trading_blocked": True},
])
def test_unavailable_account_fails(patch):
    d = base()
    d["account"].update(patch)
    with pytest.raises((p.FundingPreviewStop, p.risk.PortfolioRiskStop)):
        p.preview(**d)


@pytest.mark.parametrize("patch", [
    {"live_order_authorization_present": True},
    {"autonomous_strategy_event_execution_enabled": True},
    {"leverage_allowed": True},
    {"additional_deposits_automatically_usable": True},
    {"capital_ceiling_usd": "150.00"},
    {"execution_universe": ["ACWI", "BTCUSD"]},
])
def test_policy_change_fails(patch):
    d = base()
    d["policy"].update(patch)
    with pytest.raises(p.FundingPreviewStop):
        p.preview(**d)


def test_nonempty_orders_fail():
    with pytest.raises(p.FundingPreviewStop):
        check(open_orders=[{"id": "pending"}])


def test_binding_change_fails():
    with pytest.raises(p.FundingPreviewStop):
        check(binding="b" * 64)


def test_no_invented_event_from_pending_state():
    d = base()
    d["shadow"]["pending_source"] = "SCHEDULED"
    d["shadow"]["pending_target"] = {"EEM": 0.10}
    with pytest.raises(p.FundingPreviewStop):
        p.preview(**d)


def test_unapproved_positions_and_shorts_fail():
    d = base()
    d["positions"].append({"symbol": "BTCUSD", "qty": "1", "market_value": "2"})
    with pytest.raises(p.FundingPreviewStop):
        p.preview(**d)
    d = base()
    d["positions"][0]["qty"] = "-1"
    with pytest.raises(p.FundingPreviewStop):
        p.preview(**d)


def test_invalid_history_cannot_enable_preview():
    d = base()
    d["history"]["timestamp"] = [1, 2, 3, 4, 5, 6]
    with pytest.raises(p.risk.PortfolioRiskStop):
        p.preview(**d)


def test_no_persisted_amounts_positions_or_order_ids():
    report = check()
    forbidden = {"account", "positions", "holdings", "cash_usd",
                 "market_value", "notional_usd", "client_order_id",
                 "broker_order_id", "equity"}
    assert forbidden.isdisjoint(report)


def test_reference_cannot_mutate_input():
    data = base()
    original = deepcopy(data)
    p.preview(**data)
    assert data == original
