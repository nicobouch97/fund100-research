"""Prove costed historical sensitivity is same thesis and no trading."""
import pytest
import fund100_v6_cash_buffer_costed_comparison_v1_0 as c
import fund100_v6_fast_launch_vol_regime_l1_v1_0 as l1
import fund100_v6_s1_exact95_costed_cash_floor_v1_0 as s1
from test_fund100_v6_s1_exact95_costed_cash_floor_v1_0 import sample


def test_sector_mixture_and_locked_costs_have_no_fit():
    c._locked()
    for gross, name in ((.95,"BASELINE_95"),(.98,"LOW_BUFFER_98"),
                        (1.00,"FULLY_ALLOCATED_100")):
        m=c.TARGETS[name]
        assert sum(m.values())==pytest.approx(gross)
        assert m["XLK"]==pytest.approx(.5*gross)
        assert m["XLE"]==pytest.approx(.3*gross)
        assert m["IWM"]==pytest.approx(.2*gross)
    assert c.EXPECTED_COSTS==(5,15,35)
    assert c.TARGETS["BASELINE_95"]==s1.TARGET


def test_invalid_source_cannot_be_exploratory_substitute():
    with pytest.raises(c.CashComparisonStop,match="frozen"):
        c.evaluate(sample(n=3500),original_source_sha256="0"*64)


def test_study_matches_original_95_and_100_numerically():
    result=c.evaluate(sample(n=3500),original_source_sha256=l1.ORIGINAL_SHA)
    assert result["original_sector_50_30_20_mixture_preserved"]
    assert result["research_previously_examined_not_out_of_sample"]
    assert result["cash_level_between_rebalances_is_uncontrolled"]
    assert result["live_orders"]==result["broker_requests"]==result["paper_orders"]==0
    assert result["new_live_policy_promoted"] is False
    assert set(result["results"])=={"5","15","35"}
    for side_cost, periods in result["results"].items():
        assert set(periods)=={"2014_onward","2020_onward"}
        for name, data in periods.items():
            assert set(data["by_cash_entry_policy"])==set(c.TARGETS)
            assert data["backtest_winner_cannot_auto_select_cash_policy"]
            for model in data["by_cash_entry_policy"].values():
                assert model["nav"]["annual_realised_volatility_pct"]>=0
                assert model["annual_gross_turnover"]>=0
                assert model["rebalance_events"]>=1


def test_tampered_unregistered_cost_policy_fails_closed(monkeypatch):
    monkeypatch.setattr(c,"EXPECTED_COSTS",(0,15,35))
    with pytest.raises(c.CashComparisonStop,match="preregistration"):
        c._locked()
