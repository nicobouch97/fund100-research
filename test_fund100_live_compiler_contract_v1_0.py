"""Contract tests against the EXACT current V5-002 compiler v1.1 schema.

The compiler is a GET-only, non-executable signal producer. Tests below
never invoke its main() or connect to a broker. No LIVE authorization.
"""
from decimal import Decimal
import pytest

import fund100_live_production_controller_v1_0 as production
from fund100_alpaca_live_scheduled_compiler_v1_1 import COMPILER_SCHEMA


def compiler_output(*, genuine=True, status="GENUINE_SCHEDULED_EVENT"):
    return {
        "schema": COMPILER_SCHEMA,
        "strategy": "V5-002_SHADOW",
        "compiler_mode": "current",
        "status": status,
        "genuine_scheduled_event": genuine,
        "executed_satellite_weights": {
            "SPY": 0.0,
            "IWM": 0.0,
            "EFA": 0.0,
            "EEM": 0.08,
            "VNQ": 0.0,
            "XLK": 0.0,
            "XLF": 0.0,
            "XLI": 0.0,
            "XLV": 0.08,
            "XLP": 0.0,
            "XLY": 0.0,
            "XLE": 0.09,
            "XLU": 0.0,
        },
        "candidate_intents": [
            {
                "symbol": "EEM", "side": "sell",
                "client_order_id": "f100live-fedcba987654-s-eem",
                "notional_usd": None,
                "executable": False,
            },
            {
                "symbol": "XLV", "side": "buy",
                "client_order_id": "f100live-fedcba987654-b-xlv",
                "notional_usd": None,
                "executable": False,
            },
        ],
        "live_execution_authorized": False,
        "orders_submitted": 0,
    }


def test_real_compiler_genuine_event_not_inferred_from_label():
    body = compiler_output()
    event = production.extract_compiler_view(
        body, compiler_sha256=production.canonical_sha256(body),
    )
    assert event["genuine"] is True
    assert sorted(event["candidates"]) == ["EEM", "XLV"]
    assert event["candidates"]["XLV"]["side"] == "buy"
    assert event["candidates"]["XLV"]["client_order_id"] == (
        "f100live-fedcba987654-b-xlv"
    )


def test_real_compiler_weights_derive_exact_acwi_core():
    body = compiler_output()
    targets = production.extract_target_weights(body)
    assert targets["ACWI"] == Decimal("0.75")
    assert targets["EEM"] == Decimal("0.08")
    assert targets["XLV"] == Decimal("0.08")
    assert targets["XLE"] == Decimal("0.09")
    assert sum(targets.values()) == Decimal("1")
    assert len(targets) == 14


def test_real_no_event_compiler_is_safe_noop():
    body = compiler_output(genuine=False, status="NO_SCHEDULED_EVENT")
    body["candidate_intents"] = []
    body.pop("executed_satellite_weights")
    event = production.extract_compiler_view(
        body, compiler_sha256=production.canonical_sha256(body)
    )
    assert event["genuine"] is False
    assert event["candidates"] == {}


def test_real_event_requires_explicit_genuine_flag():
    body = compiler_output()
    del body["genuine_scheduled_event"]
    with pytest.raises(production.ProductionStop, match="explicit flag"):
        production.extract_compiler_view(
            body, compiler_sha256=production.canonical_sha256(body)
        )


@pytest.mark.parametrize("genuine,status", [
    (False, "GENUINE_SCHEDULED_EVENT"),
    (True, "NO_SCHEDULED_EVENT"),
])
def test_status_flag_mismatch_fails_closed(genuine, status):
    body = compiler_output(genuine=genuine, status=status)
    if not genuine:
        body["candidate_intents"] = []
    with pytest.raises(production.ProductionStop, match="contradiction"):
        production.extract_compiler_view(
            body, compiler_sha256=production.canonical_sha256(body)
        )


def test_invalid_compiler_satellite_weight_fails_closed():
    for bad in ["NaN", -1, 1.2]:
        body = compiler_output()
        body["executed_satellite_weights"]["EEM"] = bad
        with pytest.raises(production.ProductionStop):
            production.extract_target_weights(body)


def test_compiler_must_not_mix_explicit_full_and_satellite_weights():
    body = compiler_output()
    body["final_target_weights"] = {"ACWI": 1.0}
    with pytest.raises(production.ProductionStop, match="conflicting"):
        production.extract_target_weights(body)


def test_desired_but_not_executed_weights_cannot_authorize_orders():
    body = compiler_output()
    body["desired_satellite_weights"] = body.pop("executed_satellite_weights")
    with pytest.raises(production.ProductionStop, match="missing"):
        production.extract_target_weights(body)


def test_compiler_core_cannot_be_forged_as_satellite():
    body = compiler_output()
    body["executed_satellite_weights"]["ACWI"] = 0.1
    with pytest.raises(production.ProductionStop, match="contain core"):
        production.extract_target_weights(body)


def test_no_event_must_not_carry_candidate_intents():
    body = compiler_output(genuine=False, status="NO_SCHEDULED_EVENT")
    with pytest.raises(production.ProductionStop, match="non-genuine"):
        production.extract_compiler_view(
            body, compiler_sha256=production.canonical_sha256(body)
        )


def test_synthetic_compiler_mode_is_not_genuine_event():
    body = compiler_output(genuine=False, status="SYNTHETIC_SCHEDULED_EVENT")
    body["compiler_mode"] = "synthetic"
    body["candidate_intents"] = []
    with pytest.raises(production.ProductionStop, match="not in current mode"):
        production.extract_compiler_view(
            body, compiler_sha256=production.canonical_sha256(body)
        )


def test_real_compiler_generates_directional_paper_intents():
    """End-to-end adapter from the ACTUAL v1.1 position-aware compiler."""
    import pandas as pd
    import fund100_alpaca_live_scheduled_compiler_v1_1 as compiler
    import fund100_alpaca_live_scheduled_compiler as v10
    import v4_dispersion_overlay as base

    current = {
        "ACWI": 0.75,
        "EEM": 0.15,
        "XLE": 0.10,
    }
    rows = [
        {"symbol": symbol, "current_weight": weight}
        for symbol, weight in current.items()
    ]
    satellites = pd.Series(
        {
            symbol: (
                0.10 if symbol in ("EEM", "XLE")
                else 0.05 if symbol == "XLV"
                else 0.0
            )
            for symbol in base.EQUITY_UNIVERSE
        }
    )
    seed = "a" * 64
    true_compiler_candidates = compiler.compile_position_aware_intents(
        reconciliation_body={"reconciliation_rows": rows},
        executed_satellites=satellites,
        seed=seed,
    )
    assert {
        (entry["symbol"], entry["side"])
        for entry in true_compiler_candidates
    } == {("EEM", "sell"), ("XLV", "buy")}
    assert all(entry["executable"] is False for entry in true_compiler_candidates)

    body = compiler_output()
    body["candidate_intents"] = true_compiler_candidates
    body["executed_satellite_weights"] = {
        symbol: float(satellites[symbol])
        for symbol in base.EQUITY_UNIVERSE
    }
    view = production.extract_compiler_view(
        body, compiler_sha256=production.canonical_sha256(body)
    )
    weights = production.extract_target_weights(body)
    assert view["genuine"] is True
    assert weights["ACWI"] == Decimal("0.75")
    assert view["candidates"]["EEM"]["client_order_id"] == (
        v10.build_client_id(seed=seed, side="sell", symbol="EEM")
    )
    assert view["candidates"]["XLV"]["client_order_id"] == (
        v10.build_client_id(seed=seed, side="buy", symbol="XLV")
    )
