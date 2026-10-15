"""Offline-only synthetic C3B tests; no licensed quotes, broker or live data."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

import fund100_commodity_contract_curves_c3b_v1_0 as c


def fixtures():
    data = []
    # Synthetic identified-expiry quotes; NOT market data or DBC basket.
    for i, day in enumerate(("2026-10-12", "2026-10-13", "2026-10-14")):
        for mic, product, contract, month, expiry, price, unit, vol, oi in (
            ("XNYM", "CL", "CLF27", "2027-01", "2026-12-18", 75+i, "USD_PER_BARREL", 1200, 30000),
            ("XNYM", "CL", "CLG27", "2027-02", "2027-01-20", 76+i, "USD_PER_BARREL", 800, 18000),
            ("XCEC", "GC", "GCZ26", "2026-12", "2026-12-28", 2700+i, "USD_PER_TROY_OUNCE", 1800, 25000),
            ("XCEC", "GC", "GCG27", "2027-02", "2027-02-24", 2680+i, "USD_PER_TROY_OUNCE", 350, 10000),
        ):
            data.append({
                "observation_date": day, "published_at_utc": day+"T23:00:00Z",
                "captured_at_utc": day+"T23:45:00Z", "exchange_mic": mic,
                "product_code": product, "contract_id": contract,
                "delivery_month": month, "expiry_date": expiry,
                "settlement_price": float(price), "quote_unit": unit,
                "volume": vol, "open_interest": oi,
            })
    frame = pd.DataFrame(data, columns=c.COLUMNS)
    raw = frame.to_csv(index=False).encode()
    manifest = {
        "schema": c.SCHEMA,
        "provider_name": "Synthetic Fixture Provider",
        "source_type": "public_delayed",
        "source_url": "https://www.cmegroup.com/market-data/daily-settlements.html",
        "data_license_note": "Synthetic fixture only; absolutely not a real source license.",
        "dataset_sha256": c.raw_sha256(raw),
        "acquired_at_utc": "2026-10-15T08:00:00Z",
        "contract_expiries_source_note":
            "Fictitious reference expiries supplied only for unit tests.",
        "data_release_verification": False,
        "dbc_index_constituent_weights_included": False,
    }
    return frame, raw, manifest


def test_real_contract_identifiers_and_expiry_pairing_not_ranked_eia():
    frame, raw, manifest = fixtures()
    data = c.read_snapshot(raw, manifest)
    pairs = c.curve_pairs(data)
    assert len(pairs) == 6
    assert all(pairs["two_expiry_quotes_observed"])
    cl = pairs.query("product_code == 'CL'")
    gc = pairs.query("product_code == 'GC'")
    assert (cl["curve_state"] == "CONTANGO").all()
    assert (gc["curve_state"] == "BACKWARDATION").all()
    assert (cl["near_contract_id"] == "CLF27").all()
    assert (cl["far_contract_id"] == "CLG27").all()
    assert (cl["days_between_expiries"] == 33).all()
    assert (gc["quote_unit"] == "USD_PER_TROY_OUNCE").all()


def test_expiry_annualized_log_price_slope_not_earned_futures_carry():
    data, raw, manifest = fixtures()
    pairs = c.curve_pairs(c.read_snapshot(raw, manifest))
    cl = pairs.query("product_code == 'CL'").iloc[0]
    assert cl["far_over_near_minus_one"] == pytest.approx(76/75-1)
    assert cl["annualized_log_curve_slope_NOT_realized_carry"] > 0
    assert cl["dbc_basket_return_observed"] == False
    assert cl["asof_published_utc"] == "2026-10-12T23:00:00Z"


def test_historically_negative_settlement_retained_no_log_or_pct():
    frame, _, _ = fixtures()
    frame.loc[frame["contract_id"] == "CLF27", "settlement_price"] = -10.5
    paired = c.curve_pairs(frame).query("product_code == 'CL'")
    assert (paired["curve_state"] == "NONPOSITIVE_PRICE_NO_RATIO").all()
    assert paired["far_over_near_minus_one"].isna().all()
    assert paired["annualized_log_curve_slope_NOT_realized_carry"].isna().all()
    assert (paired["far_minus_near_price"] > 0).all()


def test_manifest_never_turns_provider_claim_into_independent_vintage_proof():
    _, raw, m = fixtures()
    m["data_release_verification"] = True
    result = c.research_report(c.read_snapshot(raw, m), m, raw)
    assert result["provider_claimed_release_verification"] is True
    assert result["independent_historical_vintage_verification_performed"] is False
    assert result["contract_level_candidate_strategy_approved"] is False
    assert result["dbc_constituent_and_roll_weights_available"] is False
    assert result["paper_authorized"] is False
    assert result["live_authorized"] is False
    assert result["broker_order_count"] == 0


def test_source_hash_must_match_raw_bytes_not_copy_paste():
    _, raw, m = fixtures()
    with pytest.raises(c.ContractDataStop, match="SHA256 mismatch"):
        c.validate_manifest(m, raw + b"\n")
    m2 = deepcopy(m)
    m2["source_url"] = "http://unsupported-futures.example"
    with pytest.raises(c.ContractDataStop, match="HTTPS"):
        c.validate_manifest(m2, raw)
    m2 = deepcopy(m)
    m2["dbc_index_constituent_weights_included"] = True
    with pytest.raises(c.ContractDataStop, match="cannot be inferred"):
        c.validate_manifest(m2, raw)


def test_unknown_exchange_product_and_different_quote_unit_are_rejected():
    frame, _, _ = fixtures()
    for bad in (
        lambda x: x.assign(product_code="BTC"),
        lambda x: x.assign(exchange_mic="XXXX"),
        lambda x: x.assign(quote_unit="USD_PER_UNIT"),
        lambda x: x.drop(columns=["contract_id"]),
    ):
        with pytest.raises(c.ContractDataStop):
            c.validate_contracts(bad(frame))


def test_duplicate_contract_revisions_and_inconsistent_expiry_rejected():
    frame, _, _ = fixtures()
    with pytest.raises(c.ContractDataStop, match="Duplicate"):
        c.validate_contracts(pd.concat([frame, frame.iloc[:1]], ignore_index=True))
    revised = frame.copy()
    revised.loc[
        (revised["observation_date"] == "2026-10-14") &
        (revised["contract_id"] == "CLF27"), "expiry_date"
    ] = "2026-12-19"
    with pytest.raises(c.ContractDataStop, match="identity/expiry"):
        c.validate_contracts(revised)


def test_same_expiry_cannot_create_false_time_spread():
    frame, _, _ = fixtures()
    frame.loc[frame["contract_id"] == "CLG27", "expiry_date"] = "2026-12-18"
    with pytest.raises(c.ContractDataStop, match="same expiry"):
        c.curve_pairs(frame)


def test_publication_capture_and_acquisition_chronology_required():
    frame, raw, m = fixtures()
    earlier_pub = frame.copy()
    earlier_pub.loc[0, "published_at_utc"] = "2026-10-11T23:00:00Z"
    with pytest.raises(c.ContractDataStop, match="Publication/capture"):
        c.validate_contracts(earlier_pub)
    premature = frame.copy()
    premature.loc[0, "captured_at_utc"] = "2026-10-12T20:00:00Z"
    with pytest.raises(c.ContractDataStop, match="Publication/capture"):
        c.validate_contracts(premature)
    delayed = deepcopy(m)
    delayed["acquired_at_utc"] = "2026-10-12T12:00:00Z"
    with pytest.raises(c.ContractDataStop, match="after manifest acquisition"):
        c.read_snapshot(raw, delayed)


def test_expired_quotes_cannot_be_treated_as_forward_contracts():
    frame, _, _ = fixtures()
    frame.loc[0, "expiry_date"] = "2026-10-10"
    with pytest.raises(c.ContractDataStop, match="Expired"):
        c.validate_contracts(frame)


def test_bad_price_volume_and_open_interest_fail_closed():
    frame, _, _ = fixtures()
    for change in (
        lambda f: f.assign(settlement_price=np.nan),
        lambda f: f.assign(settlement_price=float("inf")),
        lambda f: f.assign(volume=-5),
        lambda f: f.assign(open_interest=1.5),
        lambda f: f.assign(open_interest="missing"),
    ):
        with pytest.raises(c.ContractDataStop):
            c.validate_contracts(change(frame))


def test_missing_far_contract_cannot_be_fabricated_by_forward_fill():
    frame, _, _ = fixtures()
    filtered = frame.loc[~((frame["observation_date"] == "2026-10-13") &
                            (frame["contract_id"] == "CLG27"))]
    pairs = c.curve_pairs(filtered)
    assert len(pairs) == 5
    assert not ((pairs["observation_date"] == "2026-10-13") &
                (pairs["product_code"] == "CL")).any()


def test_nontrading_report_without_any_futures_return_prediction():
    frame, raw, manifest = fixtures()
    report = c.research_report(c.read_snapshot(raw, manifest), manifest, raw)
    assert report["observed_near_far_curve_pairs"] == 6
    assert report["input_settlement_rows"] == 12
    assert report["contango_curve_pairs"] == 3
    assert report["backwardation_curve_pairs"] == 3
    assert report["dbc_current_and_historical_roll_pnl_calculated"] is False
    assert report["state"] == "RESEARCH_DATA_ONLY_NOT_TRADE_READY"
