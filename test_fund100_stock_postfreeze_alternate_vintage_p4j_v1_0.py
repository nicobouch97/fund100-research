"""P4J: revised pre-freeze history cannot revise selected forward-only returns."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import fund100_stock_postfreeze_alternate_vintage_p4j_v1_0 as p
import fund100_stock_forward_permanent_anchor_p4i_v1_0 as p4i
import fund100_stock_quality_momentum_p4g_v1_0 as p4g


def prices(last="2026-10-20"):
    idx=pd.bdate_range("2025-10-01",last)
    v=np.arange(len(idx),dtype=float)
    slopes={
        "AAPL":.00032,"MSFT":.00052,"GOOGL":.00041,"AMZN":.00056,
        "XOM":.00023,"JNJ":.00011,"PG":.00030,"KO":.00033,
        "SPY":.00039,"SHY":.00005,
    }
    return pd.DataFrame({k:100*np.exp(s*v) for k,s in slopes.items()},index=idx)


def frozen():
    return p4i.read_anchor(Path(p4i.__file__).resolve().parent/p4i.ANCHOR_FILE)[0]


def follow(last="2026-10-20",acquired="2026-10-21T08:00:00Z"):
    return {"asof_completed_session":last,"source_acquired_at_utc":acquired}


def test_postfreeze-only_two_sessions_are_explicit_alternate_vintage_not_alpha():
    a=p.compare_only_future(frozen(),follow(),prices())
    assert a["schema"]==p.SCHEMA
    assert a["mode"]==p.MODE
    assert a["status"]=="ALTERNATE_VENDOR_VINTAGE_POST_FREEZE_ONLY_HYPOTHETICAL_MARK"
    assert a["original_frozen_selected_stocks"]==["MSFT","KO","PG"]
    assert a["hypothetical_entry_session"]=="2026-10-19"
    assert a["hypothetical_last_mark_session"]=="2026-10-20"
    assert a["postfreeze_return_intervals_observed"]==1
    assert a["historic_pre_freeze_price_rows_used_for_returns"] is False
    assert a["original_P4I_identical_vintage_claimed"] is False
    assert a["broker_fill_or_trade_verified"] is False
    assert a["live_orders_authorized"] is False
    assert a["actual_broker_orders"]==a["broker_http_calls"]==a["private_state_mutations"]==0
    assert set(a["costed_scenarios"])=={"5","15","35"}


def test_revision_to_original_prior_vendor_prices_flags_mismatch_but_cannot_alter_future_only():
    original=prices()
    first=p.compare_only_future(frozen(),follow(),original)
    altered=original.copy()
    altered.loc["2026-07-01","MSFT"]*=1.001
    revised=p.compare_only_future(frozen(),follow(),altered)
    assert revised["original_source_vintage_status"]=="ORIGINAL_HISTORICAL_PREFIX_REVISED"
    assert not revised["original_historical_vendor_price_rows_consistent"]
    assert revised["costed_scenarios"]==first["costed_scenarios"]
    assert revised["later_historical_prefix_sha256"]!=first["later_historical_prefix_sha256"]
    # Existing strict original P4I MUST continue to refuse source revisions.
    fixed=frozen()
    fake=deepcopy(fixed)
    fake["original_p4g_canonical_price_csv_sha256"]=sha256(
        p4g.canonical_price_csv(original.loc[:"2026-10-16"]).encode()).hexdigest()
    with pytest.raises(p4i.AnchorStop,match="FAIL_CLOSED_SOURCE_REVISION"):
        p4i.anchored_forward(fake,follow(),altered)


def test_future_price_change_matters_while_old_history_change_does_not():
    a=prices()
    first=p.compare_only_future(frozen(),follow(),a)
    changed=a.copy()
    changed.loc["2026-10-20","MSFT"]*=1.02
    other=p.compare_only_future(frozen(),follow(),changed)
    assert other["costed_scenarios"]!=first["costed_scenarios"]


@pytest.mark.parametrize("last,received,expected",[
    ("2026-10-16","2026-10-17T08:00:00Z","NO_POST_FREEZE_ENTRY_SESSION"),
    ("2026-10-19","2026-10-20T08:00:00Z","ENTRY_SESSION_ONLY_NO_FORWARD_RETURN"),
    ("2026-10-20","2026-10-21T08:00:00Z","ALTERNATE_VENDOR_VINTAGE_POST_FREEZE_ONLY_HYPOTHETICAL_MARK"),
])
def test_no_hypothetical_profit_before_second_completed_post_freeze_session(last,received,expected):
    a=p.compare_only_future(frozen(),follow(last,received),prices(last))
    assert a["status"]==expected
    if expected!="ALTERNATE_VENDOR_VINTAGE_POST_FREEZE_ONLY_HYPOTHETICAL_MARK":
        assert a["costed_scenarios"] is None


def test_net_of_cost_marks_monotonic_with_more_friction_and_do_not_infer_cagr():
    a=p.compare_only_future(frozen(),follow(),prices())
    cases=a["costed_scenarios"]
    for key in ("selected_net_pct","six_net_pct","spy_net_pct"):
        assert cases["5"][key]>cases["15"][key]>cases["35"][key]
    assert a["statistical_alpha_or_CAGR_claimed"] is False
    assert a["vendor_dividend_adjustments_independently_verified"] is False
    assert a["exchange_session_completeness_independently_verified"] is False
    assert a["true_entry_fills_or_spreads_observed"] if "true_entry_fills_or_spreads_observed" in a else True


@pytest.mark.parametrize("field,value",[
    ("original_preselected_watchlist",["XOM","AMZN"]),
    ("reference_six_quality_cohort",["KO"]),
    ("original_p4g_canonical_price_csv_sha256","0"*64),
    ("original_p4g_json_sha256","0"*64),
    ("entry_and_exit_cost_bps_each_side",[0,0,0]),
    ("original_history_used_as_future_strategy_returns",True),
    ("derivatives_margin_live_stocks_authorized",True),
    ("broker_orders",1),
])
def test_original_frozen_anchor_cannot_be_altered(field,value):
    f=deepcopy(frozen())
    f[field]=value
    with pytest.raises(p.P4JStop):
        p.compare_only_future(f,follow(),prices())


def test_wrong_later_source_vintage_timestamps_are_rejected():
    with pytest.raises(p.P4JStop):
        p.compare_only_future(frozen(),follow(acquired="2026-10-16T08:00:00Z"),prices())
    with pytest.raises(p.P4JStop):
        p.compare_only_future(frozen(),follow(last="2026-10-22"),prices())


def test_missing_bad_later_prices_do_not_fake_stocks_or_benchmark():
    a=prices()
    a=a.drop(columns=["SPY"])
    with pytest.raises(p.P4JStop):
        p.compare_only_future(frozen(),follow(),a)
    a=prices()
    a.loc["2026-10-20","MSFT"]=float("nan")
    with pytest.raises(p.P4JStop):
        p.compare_only_future(frozen(),follow(),a)


def test_no_live_broker_network_mutations_or_secrets_in_module():
    code=Path(p.__file__).read_text()
    for forbidden in (
        "ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET","api.alpaca.markets",
        "FUND100_PRIVATE_STATE_PRODUCTION_WRITE_TOKEN",
        "FUND100_PRIVATE_LEDGER_HMAC_KEY_HEX",
        "urlopen(", "requests.post(", "method=\"POST\"",
        "github.com/repos/",
    ):
        assert forbidden not in code
    assert p.UNRELEASED_LIVE_TRADING
    assert p.NO_HTTP_OR_GITHUB_MUTATIONS
