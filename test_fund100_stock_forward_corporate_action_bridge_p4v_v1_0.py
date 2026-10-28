"""P4V corporate-action source verification: synthetic, no broker."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

import fund100_stock_forward_corporate_action_bridge_p4v_v1_0 as p4v


def fixtures():
    index=pd.bdate_range("2025-10-01","2026-10-16")
    n=np.arange(len(index),dtype=float)
    original=pd.DataFrame({
        "PG":145.+0.02*n,
        "MSFT":450.+0.15*n,
        "KO":90.+0.01*n,
        "SPY":600.+0.1*n,
        "SHY":80.+0.001*n,
    },index=index)
    future=pd.bdate_range("2026-10-19","2026-10-27")
    extra=pd.DataFrame({
        "PG":[156.65,158.27,155.81,164.50099,161.02,159.92,159.23],
        "MSFT":[529.0,529.5,530.,531.,524.,532.,531.3],
        "KO":[93.,93.1,93.2,93.3,92.7,92.7,91.18],
        "SPY":[760.,762.,764.,763.,759.97,765.37,769.66],
        "SHY":[81.3,81.31,81.32,81.33,81.5,81.48,81.45],
    },index=future)
    later=pd.concat([original.copy(),extra])
    ratio=1-0.006576473833059482
    later.loc[original.index,"PG"]*=ratio
    return original,later


def test_documented_pg_dividend_does_not_rewrite_frozen_vintage():
    original,later=fixtures()
    joined,proof=p4v.reconcile_documented_pg_dividend(original,later)
    pd.testing.assert_frame_equal(joined.loc[:original.index[-1]],original)
    pd.testing.assert_frame_equal(joined.loc["2026-10-19":],later.loc["2026-10-19":])
    assert proof["historical_overlap_sessions"]==len(original)
    assert proof["manual_published_price_and_dividend_crosscheck"]
    assert proof["absolute_factor_difference"]<1e-5
    assert proof["revised_pre_freeze_rows_used_for_returns"] is False
    assert proof["cash_dividend_actually_settled_verified"] is False
    assert proof["independent_total_return_benchmark_verified"] is False
    assert not proof["external_sources_retrieved_or_authenticated_in_this_job"]
    assert proof["broker_orders"]==0 and not proof["live_authorized"]


@pytest.mark.parametrize("problem",[
    "other_name_drift","fake_pg_one_day","fake_pg_uniform_factor",
    "missing_exdividend_session","missing_prior_close_session",
    "bad_previous_close","nan","zero","mismatched_dates",
])
def test_unrelated_source_drift_cannot_pass_as_dividend(problem):
    original,later=fixtures()
    if problem=="other_name_drift":
        later.loc["2026-07-17","MSFT"]*=1.00002
    elif problem=="fake_pg_one_day":
        later.loc["2026-07-17","PG"]*=1.002
    elif problem=="fake_pg_uniform_factor":
        later.loc[original.index,"PG"]*=0.998
    elif problem=="missing_exdividend_session":
        later=later.drop(pd.Timestamp("2026-10-23"))
    elif problem=="missing_prior_close_session":
        later=later.drop(pd.Timestamp("2026-10-22"))
    elif problem=="bad_previous_close":
        later.loc["2026-10-22","PG"]=163.0
    elif problem=="nan":
        later.loc["2026-10-19","PG"]=float("nan")
    elif problem=="zero":
        later.loc["2026-10-19","MSFT"]=0.
    elif problem=="mismatched_dates":
        later=later.drop(pd.Timestamp("2026-10-16"))
    with pytest.raises(p4v.CorporateActionStop):
        p4v.reconcile_documented_pg_dividend(original,later)


def test_frozen_date_and_failed_missing_dividend_are_not_waived():
    original,later=fixtures()
    with pytest.raises(p4v.CorporateActionStop):
        p4v.reconcile_documented_pg_dividend(original,later,
                                            frozen_date="2026-10-15")
    without=deepcopy(later)
    without.loc[original.index,"PG"]=original["PG"]
    with pytest.raises(p4v.CorporateActionStop):
        p4v.reconcile_documented_pg_dividend(original,without)


def test_p4v_has_no_live_broker_or_automatic_trade_path():
    import inspect
    source=inspect.getsource(p4v)
    assert "requests.post" not in source
    assert "alpaca.markets" not in source
    assert "urlopen(" not in source
    assert "live_authorized\":False" in source
    assert p4v.PG_EVENT["cash_dividend_per_share_usd"]==1.0885
    assert p4v.PG_EVENT["ex_dividend_date"]=="2026-10-23"
