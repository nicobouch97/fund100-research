"""V6-C11 SEC-filing look-through provenance and anti-hindsight controls."""
from pathlib import Path
from shutil import copy2

import pytest

import fund100_v6_c11_dbc_sec_futures_lookthrough_v1_0 as c11


def audit(asof: str, share: str = "0.15"):
    return c11.research_asof(
        decision_date=asof, hypothetical_dbc_fraction=share)


def test_pinned_original_28_futures_positions_and_gross_notional():
    snapshots = c11.original_snapshots()
    assert set(snapshots) == {"2025-12-31", "2026-03-31", "2026-06-30"}
    assert [snapshots[d]["original_sec_transcribed_contract_count"] for d
            in sorted(snapshots)] == [28, 28, 28]
    assert snapshots["2025-12-31"]["gross_futures_notional_usd"] == 1223550999
    assert snapshots["2026-03-31"]["gross_futures_notional_usd"] == 1689474972
    assert snapshots["2026-06-30"]["gross_futures_notional_usd"] == 1576215941


@pytest.mark.parametrize("asof,expected", [
    ("2026-03-02", None),
    ("2026-03-03", "2025-12-31"),
    ("2026-05-07", "2025-12-31"),
    ("2026-05-08", "2026-03-31"),
    ("2026-08-09", "2026-03-31"),
    ("2026-08-10", "2026-06-30"),
    ("2026-10-21", "2026-06-30"),
])
def test_no_future_sec_filing_can_be_known_early(asof, expected):
    result = audit(asof)
    assert result["chosen_statement_date"] == expected
    assert not result["new_trade_authorized"]
    assert not result["usable_as_LIVE_allocator_risk_factor_weights"]


def test_three_original_energy_futures_gross_notional_fractions():
    cases = [
        ("2026-03-03", 0.3740),
        ("2026-05-08", 0.4885),
        ("2026-08-10", 0.4700),
    ]
    for date, energy in cases:
        snapshot = audit(date)
        part = snapshot["sector_weights_fraction_of_reported_futures_notional"]
        assert sum(float(x) for x in part.values()) == pytest.approx(1, abs=1e-7)
        assert float(part["Energy"]) == pytest.approx(energy, abs=0.0001)


def test_15pct_DBC_sleeve_energy_mix_does_not_claim_equity_beta():
    r = audit("2026-10-21", "0.15")
    sectors = r["sector_weights_fraction_of_reported_futures_notional"]
    proxy = r["hypothetical_DBC_sleeve_sector_mix_not_beta"]
    assert 0.469 < float(sectors["Energy"]) < 0.471
    assert 0.0704 < float(proxy["Energy"]) < 0.0706
    assert r["dated_snapshot_not_current_daily_holdings"] is True
    assert r["dbc_commodity_futures_and_xle_energy_equity_are_not_same_exposure"]
    assert not r["security_overlap_or_beta_independently_measured"]
    assert not r["measured_carry_profit_or_roll_PNL"]
    assert not r["valid_as_current_fund_broker_weights"]
    assert r["gross_futures_notional_usd_not_fund_equity"] == 1576215941
    assert r["broker_request_count"] == r["paper_orders"] == r["live_orders"] == 0


def test_no_futures_source_means_no_historical_lookthrough_not_zero():
    result = audit("2026-01-01")
    assert result["status"] == "NO_PUBLICLY_AVAILABLE_FILING_AT_DECISION_DATE"
    assert result["sector_weights_fraction_of_reported_futures_notional"] is None
    assert result["hypothetical_DBC_sleeve_sector_mix_not_beta"] is None


def test_100pct_dbc_is_illustrative_only_not_fund_trade():
    result = audit("2026-10-21", "1.000")
    assert result["hypothetical_dbc_sleeve_fraction"] == "1.000"
    assert not result["new_trade_authorized"]
    assert not result["valid_as_current_fund_broker_weights"]


@pytest.mark.parametrize("amount", ["-1", "1.01", "inf", "nan", "0.1234567", 0.15,
                                     None, "", "2", "1e-1"])
def test_unknown_leverage_and_float_fraction_blocked(amount):
    with pytest.raises(c11.FilingLookthroughStop):
        audit("2026-10-21", amount)


@pytest.mark.parametrize("stamp", ["2026-02-30", "2026-5-08", "2026/08/10", "not-date"])
def test_noncanonical_or_impossible_dates_blocked(stamp):
    with pytest.raises(c11.FilingLookthroughStop):
        audit(stamp)


def test_original_research_source_tamper_or_truncation_fails(tmp_path):
    src = c11.ROOT / c11.SUBDIR
    dst = tmp_path / c11.SUBDIR
    dst.mkdir(parents=True)
    for f in c11.SOURCE_BLOBS:
        copy2(src / f, dst / f)
    assert c11.original_snapshots(root=tmp_path)
    victim = dst / "dbc_sec_futures_holdings_2026_q1_q2.csv"
    victim.write_bytes(victim.read_bytes().replace(b"2026-08-10", b"2026-08-09", 1))
    with pytest.raises(c11.FilingLookthroughStop, match="transcription"):
        c11.original_snapshots(root=tmp_path)


def test_module_has_no_broker_data_fetch_or_trade_permission():
    source = Path(c11.__file__).read_text()
    for forbidden in ("requests.get(", "requests.post(", "urlopen(",
                      "alpaca_trade_api", "api.alpaca.markets",
                      "/v2/orders", "place_order(", "GH_TOKEN"):
        assert forbidden not in source
    assert c11.NO_BROKER_REQUESTS is True
