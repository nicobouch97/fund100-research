"""Test gross-vs-cost attribution from fully signed immutable ETF forward ledger."""
import json
from hashlib import sha256
from pathlib import Path

import pandas as pd
import pytest

import fund100_forward as base
import fund100_forward_active_attribution_v1_0 as diagnostic
import fund100_forward_evidence_scorecard_v1_0 as score
from test_fund100_forward_evidence_scorecard_v1_0 import _fixture


def signed_fixture():
    ledger, manifest = _fixture()
    for name in base.MODELS:
        idxs=list(ledger.index[ledger["strategy"]==name])
        previous="GENESIS"
        for pos, idx in enumerate(idxs):
            p=json.loads(ledger.at[idx,"payload_json"])
            if pos==0:
                for col in ("daily_return","benchmark_return","gross_overlay_return",
                            "active_return","cost_drag_return"):
                    p[col]=0.0
            else:
                last=idxs[pos-1]
                net=ledger.at[idx,"nav"]/ledger.at[last,"nav"]-1
                bench=(ledger.at[idx,"benchmark_nav"]
                       /ledger.at[last,"benchmark_nav"]-1)
                p["daily_return"]=net
                p["benchmark_return"]=bench
                p["active_return"]=net-bench
                # Gross same-weight return is net plus 10bps hypothetical
                # model friction. This is NOT a resimulated alternative model.
                p["cost_drag_return"]=-0.001
                p["gross_overlay_return"]=net+0.001-bench
            raw=json.dumps(p,sort_keys=True,separators=(",",":"))
            sig=sha256((previous+"|"+raw).encode()).hexdigest()
            ledger.at[idx,"payload_json"]=raw
            ledger.at[idx,"previous_chain_hash"]=previous
            ledger.at[idx,"chain_hash"]=sig
            previous=sig
    return ledger,manifest


def test_real_ledger_reconciles_selection_costs_and_source_integrity():
    ledger=pd.read_csv(base.LEDGER_PATH)
    manifest=json.loads(base.MANIFEST_PATH.read_text())
    result=diagnostic.analyze(ledger,manifest)
    assert result["schema"]==diagnostic.SCHEMA
    assert result["paper_returns_are_not_broker_fills"] is True
    assert result["recovered_source_rows_never_qualified_as_pristine_forward"]
    assert result["gross_path_is_same_realized_weights_not_recomputed_no_fee_strategy"]
    assert result["model_selection_or_strategy_promotion_authorized"] is False
    assert result["live_order_authorized"] is False
    assert result["broker_GETs"]==result["broker_POSTs"]==result["broker_orders"]==0
    original=score.analyze(ledger,manifest)
    for name in base.MODELS:
        d=result["models"][name]
        o=original["models"][name]
        assert d["strict_forward_intervals"]==o["strict_forward_intervals"]
        assert d["recovered_after_outage_intervals"]==o["recovered_after_outage_intervals"]
        assert d["actual_original_paper_after_cost_nav"]==o["final_paper_nav_units"]
        assert d["source_history_hash_last"]==o["last_chain_hash"]
        assert d["same_weight_path_gross_before_cost_nav"] >= d["actual_original_paper_after_cost_nav"] - 1e-7
        assert d["strict_forward_market_gross_intervals"]==d["strict_forward_intervals"]


def test_signed_synthetic_cost_drag_algebra_and_same_weight_difference():
    ledger,manifest=signed_fixture()
    d=diagnostic.analyze(ledger,manifest)
    for name in base.MODELS:
        row=d["models"][name]
        assert row["strict_forward_intervals"]==2
        assert row["recovered_after_outage_intervals"]==1
        assert row["same_weight_path_cost_effect_nav_units"] > 0
        assert row["strict_forward_cost_drag_log_relative_wealth_pp"] < 0
        assert row["recovered_cost_drag_log_relative_wealth_pp"] < 0
        assert row["gross_selection_minus_acwi_total_return_pp"] > row[
            "net_strategy_minus_acwi_total_return_pp"]
    # Two independent strict-forward observations are too few for a
    # statistically useful model-correlation estimate. Never report 1.0.
    assert d["strict_forward_gross_active_return_correlations"]=={
        "V3__V4":None, "V3__RM25":None, "V4__RM25":None}
    assert d["all_original_models_highly_similar_on_strict_forward_observations"] is False


def test_genuine_scorecard_chain_or_original_manifest_mutation_fails():
    rows,manifest=signed_fixture()
    rows.loc[rows["strategy"]=="V3","chain_hash"]="f"*64
    with pytest.raises(score.ScorecardStop):
        diagnostic.analyze(rows,manifest)
    rows,manifest=signed_fixture()
    manifest["historical_cutoff"]="2026-09-17"
    with pytest.raises(score.ScorecardStop):
        diagnostic.analyze(rows,manifest)


@pytest.mark.parametrize("key,bad",[
    ("gross_overlay_return",300.0),
    ("cost_drag_return",+0.00001),
    ("cost_drag_return",-0.5),
    ("active_return",100.0),
    ("benchmark_return",-1.0),
    ("daily_return",1.3),
])
def test_even_newly_resigned_but_internally_wrong_pnl_cannot_pass(key,bad):
    rows,manifest=signed_fixture()
    idx=int(rows.index[(rows["strategy"]=="V3")
                        & (rows["date"]=="2026-09-17")][0])
    p=json.loads(rows.at[idx,"payload_json"])
    p[key]=bad
    # Recompute V3 chain, simulating a genuine signed but economically
    # misleading later ledger. Original checksum alone isn't enough.
    indices=list(rows.index[rows["strategy"]=="V3"])
    prev="GENESIS"
    for i in indices:
        q=p if i==idx else json.loads(rows.at[i,"payload_json"])
        raw=json.dumps(q,sort_keys=True,separators=(",",":"))
        sig=sha256((prev+"|"+raw).encode()).hexdigest()
        rows.at[i,"payload_json"]=raw
        rows.at[i,"previous_chain_hash"]=prev
        rows.at[i,"chain_hash"]=sig
        prev=sig
    with pytest.raises(diagnostic.AttributionStop):
        diagnostic.analyze(rows,manifest)


def test_nobody_claims_uncertainty_or_independent_alpha_from_correlated_models():
    assert diagnostic._corr([0.0]*8,[0.0]*8) is None
    assert diagnostic._corr([0.1]*4,[0.1]*4) is None
    assert diagnostic._corr([1,2,3,4,5],[5,4,3,2,1]) == -1.0
    assert diagnostic._corr([1,2,3,4,5],[1,2,3,4,5]) == 1.0
    assert diagnostic.LIVE_AUTHORIZED is False
    assert diagnostic.MODEL_PROMOTION_AUTHORIZED is False


def test_no_private_broker_or_git_remote_writer_in_analysis():
    s=(Path(__file__).resolve().parent/
       "fund100_forward_active_attribution_v1_0.py").read_text()
    assert "urlopen" not in s and "requests." not in s
    assert "submit_order" not in s
    assert "alpaca" not in s.lower()
