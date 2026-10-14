"""Full offline ETF rebalance rehearsal acceptance tests."""

from decimal import Decimal

import pytest

import fund100_etf_paper_rehearsal_v1_0 as paper
import fund100_live_portfolio_risk_v1_0 as portfolio
import fund100_live_operator_control_v1_0 as operator


def test_real_production_two_phase_rehearsal_is_funded_by_sell():
    report = paper.rehearse()
    assert report["status"] == "SUCCESS"
    assert report["mode"] == "OFFLINE_SYNTHETIC_PAPER"
    assert report["risk_level"] == "HIGH"
    assert report["simulated_orders"] == [
        {
            "client_order_id": "f100live-fedcba987654-s-eem",
            "side": "sell", "symbol": "EEM", "notional_usd": "5.00",
        },
        {
            "client_order_id": "f100live-fedcba987654-b-xlv",
            "side": "buy", "symbol": "XLV", "notional_usd": "5.00",
        },
    ]
    assert report["order_count"] == 2
    assert Decimal(report["synthetic_ending_equity_usd"]) == Decimal("100")
    assert report["replay_duplicate_orders"] == 0
    assert report["unmocked_broker_requests"] == 0
    assert [p["phase"] for p in report["phases"]] == ["SELL", "BUY"]
    assert all("cumulative_cap_approved" in p["trace"] for p in report["phases"])


def test_operator_stop_between_phases_blocks_next_trade():
    with pytest.raises(operator.OperatorControlStop, match="STOP"):
        paper.rehearse(stop_after_sell=True)


def test_low_risk_does_not_force_unauthorized_trades():
    with pytest.raises(paper.production.ProductionStop, match="risk-adjusted sizing") as exc:
        paper.rehearse(level="LOW")
    assert isinstance(exc.value.__cause__, portfolio.PortfolioRiskStop)


def test_without_compiler_buy_authority_no_order_is_sent():
    only_sell = [
        x for x in paper.SIGNAL_ORDERS if x["side"] == "sell"
    ]
    with pytest.raises(paper.production.ProductionStop, match="risk-adjusted sizing") as exc:
        paper.rehearse(candidates=only_sell)
    assert isinstance(exc.value.__cause__, portfolio.PortfolioRiskStop)


def test_preview_funded_buy_does_not_bypass_real_cash_check():
    broker = paper.PaperBroker()
    event = paper.synthetic_compiler()
    compiler = paper.production.extract_compiler_view(
        event, compiler_sha256=paper.production.canonical_sha256(event)
    )
    # An attempted BUY before the actual SELL must fail despite preview
    # allowing estimation against hypothetical future SELL proceeds.
    with pytest.raises(paper.production.ProductionStop, match="cash"):
        paper.production.materialize_orders(
            snapshot=broker.snapshot(),
            target_weights=paper.production.extract_target_weights(event),
            candidates=compiler["candidates"],
            phase="BUY",
            capital_ceiling=Decimal("130.30"),
        )


def test_broker_transport_refused_without_fake_get():
    broker = paper.PaperBroker()
    with pytest.raises(AssertionError, match="unmocked broker"):
        broker.live_request(method="POST", path="/v2/orders")
    assert broker.network_calls == 1
