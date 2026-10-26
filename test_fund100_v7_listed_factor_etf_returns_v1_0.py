"""Synthetic source-only tests for ETF factor research; never hit market/broker."""
import pandas as pd
import numpy as np
import pytest

import fund100_v7_listed_factor_etf_returns_v1_0 as m

STAMP="2026-10-26T16:00:00Z"
SOURCE="YFINANCE_ADJUSTED_CLOSE_SOURCE_VINTAGE"

def prices(*,momentum_mid=0.00065,momentum_final=0.00065,
           qualify=0.00050):
    dates=m._nyse_dates(m.FIRST,m.ASOF)
    rows=[]
    p={s:100.0 for s in m.TICKERS}
    for date in dates:
        y=date.year
        rates={
            "MTUM":(0.00055 if y<=2019 else momentum_mid if y<=2022
                    else momentum_final),
            "QUAL":qualify,
            "SPY":0.00035,
            "ACWI":0.00025,
        }
        for sym in p:p[sym]*=(1+rates[sym])
        rows.append(p.copy())
    return pd.DataFrame(rows,index=dates)

def inspect(df=None,**args):
    return m.analyze(prices() if df is None else df,captured_utc=args.pop(
        "captured_utc",STAMP),source_id=args.pop("source_id",SOURCE),**args)

def test_factor_etfs_have_positive_genuine_historical_risk_adjusted_comparison():
    z=inspect()
    assert z["first_observed_trading_session"]==m.FIRST
    assert z["last_observed_trading_session"]==m.ASOF
    assert set(z["era_results"])=={"2015_2019","2020_2022","2023_2025","2026_YTD_DESCRIPTIVE_ONLY"}
    assert z["factor_era_screen"]["MTUM"]["screen"]=="DESCRIPTIVE_NET_PREMIUM_IN_ALL_PRESET_ERAS_NOT_ALPHA"
    assert z["factor_era_screen"]["QUAL"]["positive_spy_relative_eras"]==3
    for name,_,_ in m.ERAS:
        for b in (5,15,35):
            report=z["era_results"][name][str(b)]
            assert report["cost_bps_per_side"]==b
            assert report["listed_vehicles"]["MTUM"]["net_costed_cagr_pct"]>report["listed_vehicles"]["SPY"]["net_costed_cagr_pct"]
            assert report["listed_vehicles"]["MTUM"]["net_costed_cagr_pct"]>report["listed_vehicles"]["ACWI"]["net_costed_cagr_pct"]
            assert report["listed_vehicles"]["MTUM"]["net_costed_cagr_pct"]<report["listed_vehicles"]["MTUM"]["gross_cagr_pct"]
    assert z["source_returns_include_etf_fees_and_reinvested_distributions_assumption"]
    assert z["mtum_index_variant_changed_in_2020"]
    assert z["dividend_adjustments_and_corporate_actions_vendor_revisable"]
    assert z["retrospectively_known_symbols_and_periods_not_independent_holdout"]
    assert z["current_alpaca_broker_ticker_eligibility_authenticated"] is False
    assert z["real_broker_gets"]==z["real_broker_posts"]==0
    assert z["live_order_authorized"] is False

def test_mixed_real_etf_factor_periods_are_not_alpha_promotion():
    z=inspect(prices(momentum_mid=0.0001,momentum_final=0.00065))
    assert z["factor_era_screen"]["MTUM"]["screen"]=="MIXED_OR_REGIME_DEPENDENT_FACTOR_VEHICLE_PREMIUM"
    assert z["factor_era_screen"]["MTUM"]["positive_spy_relative_eras"]==2
    assert z["era_results"]["2020_2022"]["15"]["factor_minus_matching_market"]["MTUM"]["vs_spy_net_cagr_pp"]<0

def test_no_real_factor_premium_era_is_permitted_negative():
    z=inspect(prices(momentum_mid=0.0001,momentum_final=0.0001,qualify=0.0001))
    assert z["factor_era_screen"]["QUAL"]["screen"]=="NO_POSITIVE_PRESET_ERA_FACTOR_VEHICLE_PREMIUM"
    assert z["factor_era_screen"]["MTUM"]["screen"]=="MIXED_OR_REGIME_DEPENDENT_FACTOR_VEHICLE_PREMIUM"

@pytest.mark.parametrize("remove",["2015-01-02","2020-03-16","2024-02-21","2026-10-23"])
def test_missing_exchange_session_stops_instead_of_interpolating(remove):
    df=prices()
    assert pd.Timestamp(remove) in df.index
    with pytest.raises(m.ListedFactorStop,match="missing NYSE"):
        inspect(df.drop(pd.Timestamp(remove)))

def test_nontrading_day_and_duplicate_source_rejected():
    d=prices()
    extra=pd.DataFrame([d.iloc[0].to_dict()],index=[pd.Timestamp("2015-01-03")])
    with pytest.raises(m.ListedFactorStop,match="missing NYSE"):
        inspect(pd.concat((d,extra)).sort_index())
    with pytest.raises(m.ListedFactorStop,match="shape"):
        inspect(pd.concat((d,d.iloc[:1])).sort_index())

def test_invalid_broker_unauthenticated_market_source_rejected():
    with pytest.raises(m.ListedFactorStop,match="Unknown or unapproved"):
        inspect(source_id="ALPACA_LIVE")
    with pytest.raises(m.ListedFactorStop,match="Source date"):
        inspect(captured_utc="2026-10-23T19:00:00Z")
    with pytest.raises(m.ListedFactorStop,match="Source date"):
        inspect(captured_utc="2026-11-30T19:00:00Z")

def test_price_mutations_and_invalid_coverage_fail_closed():
    d=prices()
    d.loc["2020-03-16","MTUM"]=np.nan
    with pytest.raises(m.ListedFactorStop,match="discontinuity"):
        inspect(d)
    d=prices()
    d.loc["2020-03-16","MTUM"]=0
    with pytest.raises(m.ListedFactorStop,match="discontinuity"):
        inspect(d)
    d=prices()
    d.loc["2020-03-16","MTUM"]*=3
    with pytest.raises(m.ListedFactorStop,match="discontinuity"):
        inspect(d)
    d=prices().drop(columns="ACWI")
    with pytest.raises(m.ListedFactorStop,match="shape"):
        inspect(d)

def test_identical_factor_and_market_get_no_claimed_edge_after_equal_costs():
    d=prices()
    d.loc[:,"MTUM"]=d["SPY"]
    result=inspect(d)
    assert result["factor_era_screen"]["MTUM"]["screen"]=="NO_POSITIVE_PRESET_ERA_FACTOR_VEHICLE_PREMIUM"
    for era,_,_ in m.ERAS:
        assert result["era_results"][era]["15"]["factor_minus_matching_market"]["MTUM"]["vs_spy_net_cagr_pp"]==0

def test_fixed_source_csv_hash_and_untraded_status():
    d=prices()
    z=inspect(d)
    import hashlib
    assert hashlib.sha256(m.canonical_csv(d)).hexdigest()==z["original_source_canonical_csv_sha256"]
    assert m.TRADING_RELEASED is False
    assert m.BROKER_GETS==m.BROKER_POSTS==0
    from pathlib import Path
    source=Path(m.__file__).read_text()
    for banned in ("ALPACA_LIVE_KEY","ALPACA_LIVE_SECRET",
                   "TradingClient","order_class","api.alpaca.markets"):
        assert banned not in source
