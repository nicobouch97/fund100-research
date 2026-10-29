"""V8 Q2 exact-roster, post-observation prospective rule regression tests."""
from copy import deepcopy

import pytest

import fund100_stock_broad_momentum_p4l_v1_0 as cohort
import fund100_v8_qm_first_original_sec_price_capture_v1_0 as original
import fund100_v8_q2_net_income_roa_momentum_v1_0 as q2


def inputs():
    out=[]
    for index,ticker in enumerate(original._cohort()):
        out.append({
            "symbol":ticker,
            "sector":original._label(cohort.SECTORS[ticker]),
            "frozen_issuer_identity_status":"FROZEN_ORIGINAL_ID_MATCH",
            "original_raw_sec_receipt_sha256":format(index+1,"064x"),
            "matched_annual_net_income_usd":str(1000+index*100),
            "matched_annual_assets_usd":str(10000+index*100),
            "original_10k_filed_available_utc":"2026-02-20T00:00:00Z",
            "original_10k_accession_sha256":format(index+50,"064x"),
            "adjusted_close_minus252":"100",
            "adjusted_close_minus42":str(125+index),
            "original_price_panel_sha256":"f"*64,
            "ordinary_share_asof":True,
        })
    return out


def evaluate(rows,**overrides):
    kwargs=dict(rows=rows,benchmark_minus252="100",
                benchmark_minus42="105",
                decision_utc="2026-10-30T12:00:00Z",
                price_session="2026-10-29",source_mode=q2.SOURCE_MODE)
    kwargs.update(overrides)
    return q2.select(**kwargs)


def missing(row,*,drift=False):
    row.update({
        "matched_annual_net_income_usd":None,
        "matched_annual_assets_usd":None,
        "original_10k_filed_available_utc":None,
        "original_10k_accession_sha256":None,
    })
    if drift:
        row["frozen_issuer_identity_status"]="QUARANTINED_ID_DRIFT"


def test_new_vintage_complete_caller_supplied_roa_selection_never_authorizes_broker():
    result=evaluate(inputs())
    assert result["source_24_member_count"]==24
    assert result["matched_positive_annual_net_income_assets"]==24
    assert result["selection_candidate"] is not None
    basket=result["selection_candidate"]
    assert len(set(basket["symbols"]))==8
    assert basket["initial_hypothetical_weight_each"]=="0.11875"
    assert basket["hypothetical_cash_fraction"]==".05"
    assert basket["sector_count"]>=4
    sectors=[cohort.SECTORS[s] for s in basket["symbols"]]
    assert max(sectors.count(s) for s in set(sectors))<=2
    assert basket["first_forward_horizon_sessions"]==63
    assert basket["cost_bps_per_side"]==[5,15,35]
    assert basket["live_order_authorized"] is False
    assert result["source_inputs_authenticated_by_external_receipt"] is False
    assert result["prospective_63_session_alpha_proven"] is False
    assert result["live_order_authorized"] is False
    assert result["broker_gets"]==result["broker_posts"]==result["broker_orders"]==0


def test_original_identity_drift_is_not_relabeled_and_partial_coverage_explicit():
    rows=inputs()
    for idx in range(4):
        missing(rows[idx],drift=rows[idx]["symbol"]=="XOM")
    result=evaluate(rows)
    assert result["matched_positive_annual_net_income_assets"]==20
    assert len(result["source_gaps"])==4
    assert len(result["selection_candidate"]["symbols"])==8
    assert not set(result["source_gaps"]) & set(
        result["selection_candidate"]["symbols"])
    assert result["frozen_issuer_identity_quarantined"]==(
        ["XOM"] if "XOM" in {x["symbol"] for x in rows[:4]} else [])


def test_less_than_18_positive_matching_annual_records_is_permanent_hold():
    rows=inputs()
    for row in rows[:7]:
        missing(row)
    result=evaluate(rows)
    assert result["matched_positive_annual_net_income_assets"]==17
    assert result["selection_candidate"] is None
    assert result["status"]=="HOLD_SOURCE_COVERAGE_OR_DIVERSITY"
    assert not result["live_order_authorized"]


def test_all_negative_relative_momentum_never_generates_8_stock_basket():
    rows=inputs()
    for row in rows:
        row["adjusted_close_minus42"]="100"
    result=evaluate(rows)
    assert result["matched_positive_annual_net_income_assets"]==24
    assert result["selection_candidate"] is None
    assert result["broker_orders"]==0


def test_quarantined_cik_cannot_carry_current_financials():
    rows=inputs()
    rows[0]["frozen_issuer_identity_status"]="QUARANTINED_ID_DRIFT"
    with pytest.raises(q2.Q2Hold,match="Drifted original"):
        evaluate(rows)


@pytest.mark.parametrize("mutation",[
    lambda x:x.pop(),
    lambda x:x.append(deepcopy(x[0])),
    lambda x:x[0].update(symbol="FAKE"),
    lambda x:x[0].update(sector="TECHNOLOGY" if x[0]["sector"]!="TECHNOLOGY" else "FINANCIALS"),
    lambda x:x[0].update(ordinary_share_asof=False),
    lambda x:x[0].update(original_raw_sec_receipt_sha256="not a digest"),
    lambda x:x[0].update(original_10k_accession_sha256="badhash"),
    lambda x:x[0].update(matched_annual_net_income_usd=None),
    lambda x:x[0].update(original_10k_filed_available_utc="2026-11-01T00:00:00Z"),
    lambda x:x[0].update(adjusted_close_minus42="10000"),
])
def test_invalid_or_spliced_source_fails_closed(mutation):
    rows=inputs()
    mutation(rows)
    with pytest.raises(q2.Q2Hold):
        evaluate(rows)


@pytest.mark.parametrize("override",[
    {"decision_utc":"2026-10-29T23:59:59Z"},
    {"price_session":"2026-10-30"},
    {"price_session":"2026-10-20"},
    {"source_mode":"REAL_VERIFIED_SEC"},
    {"benchmark_minus252":"0"},
])
def test_old_original_v8_source_or_unregistered_inputs_cannot_be_q2(override):
    with pytest.raises(q2.Q2Hold):
        evaluate(inputs(),**override)


def test_q2_is_isolated_from_broker_and_prior_gross_profit_rule():
    import inspect
    import fund100_v8_prospective_stock_profitability_momentum_v1_0 as old
    assert q2.BROKER_GETS==q2.BROKER_POSTS==q2.BROKER_ORDERS==0
    assert not q2.LIVE_STRATEGY_RELEASED
    assert not q2.TRADING_AUTHORIZED
    assert old.GROSS if hasattr(old,"GROSS") else old.SELECTION_COUNT==8
    assert "gross_profit_usd" in inspect.getsource(old.select)
    assert "matched_annual_net_income_usd" in inspect.getsource(q2.select)
    assert "alpaca" not in inspect.getsource(q2).lower()
