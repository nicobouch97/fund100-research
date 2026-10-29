"""P4Z offline adversarial tests; synthetic rows only, no vendor downloads."""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED

import pytest

import fund100_stock_delisted_sample_p4z_v1_0 as p4z


def _rows(symbol):
    rows = []
    for stamp in p4z._sessions(p4z.LAST[symbol]):
        row = {key: "" for key in p4z.COLUMNS}
        row.update(date=stamp, open="300", high="301", low="299",
                   close="300", volume="10000", vwap="300",
                   transactions="100", adj_open="300", adj_high="301",
                   adj_low="299", adj_close="300", adj_volume="10000",
                   adj_vwap="300")
        if symbol == "TSLA" and stamp == "2022-08-24":
            row.update(close="891.29", adj_close="297.0967")
        if symbol == "TSLA" and stamp == "2022-08-25":
            row.update(close="296.07", adj_close="296.07", split="1:3")
        if symbol == "KO" and stamp in ("2022-09-15", "2022-11-30"):
            row.update(dividend="0.44", dividend_type="CD")
        if symbol == "SPY" and stamp in ("2022-09-16", "2022-12-16"):
            row.update(dividend="1.50", dividend_type="CD")
        rows.append(row)
    return rows


def _zip(tmp_path, mutate=None, *, missing=None, bad_name=False):
    dest = tmp_path / "source.zip"
    with ZipFile(dest, "w", compression=ZIP_STORED) as archive:
        for symbol, filename in p4z.FILES.items():
            if symbol == missing:
                continue
            rows = _rows(symbol)
            if mutate is not None:
                mutate(symbol, rows)
            stream = StringIO()
            writer = csv.DictWriter(stream, fieldnames=p4z.COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
            if bad_name and symbol == "TWTR":
                filename = "TWTR_day.csv"
            archive.writestr("stocks_sample_2022H2/day_by_symbol/" + filename,
                             stream.getvalue())
    return dest


def test_full_synthetic_source_preserves_terminal_unknown(tmp_path):
    report = p4z.audit_zip(_zip(tmp_path))
    assert report["schema"] == p4z.SCHEMA
    assert [r["daily_rows"] for r in report["listings"]] == [127, 127, 127, 83]
    assert report["twtr_last_trading_bar"] == "2022-10-27"
    assert report["twtr_source_delisting_label"] == "2022-10-31"
    assert report["twtr_terminal_shareholder_proceeds_usd"] is None
    assert report["twtr_post_delisting_total_return"] is None
    assert report["twtr_last_observed_raw_close_usd"] == 300.0
    assert report["twtr_sec_contractual_right_minus_last_close_usd"] is None
    assert report["twtr_sec_contractual_right_vs_last_close_pct"] is None
    assert report["twtr_contractual_spread_ex_post_not_tradeable_or_realized"]
    assert report["twtr_position_cannot_be_dropped_or_valued_at_zero_by_default"]
    assert report["tsla_split_raw_close_return_pct"] < -60
    assert abs(report["tsla_split_adjusted_close_return_pct"]) < 1
    assert not report["historical_stock_alpha_backtest_eligible"]
    assert report["broker_orders"] == report["broker_gets"] == report["broker_posts"] == 0
    assert report["trading_authorized"] is False


def test_missing_or_renamed_delisted_listing_fails_closed(tmp_path):
    with pytest.raises(p4z.DelistedSampleStop, match="listing-specific"):
        p4z.audit_zip(_zip(tmp_path, missing="TWTR"))
    with pytest.raises(p4z.DelistedSampleStop, match="listing-specific"):
        p4z.audit_zip(_zip(tmp_path, bad_name=True))


def test_delisted_history_must_not_be_forward_filled(tmp_path):
    def extend(symbol, rows):
        if symbol == "TWTR":
            rows.append({**rows[-1], "date": "2022-10-28"})
    with pytest.raises(p4z.DelistedSampleStop, match="dates missing"):
        p4z.audit_zip(_zip(tmp_path, extend))


def test_missing_split_or_cash_distribution_fails(tmp_path):
    def split_missing(symbol, rows):
        if symbol == "TSLA":
            next(r for r in rows if r["date"] == "2022-08-25")["split"] = ""
    with pytest.raises(p4z.DelistedSampleStop, match="split marker"):
        p4z.audit_zip(_zip(tmp_path, split_missing))
    def dividend_missing(symbol, rows):
        if symbol == "KO":
            next(r for r in rows if r["date"] == "2022-09-15")["dividend"] = ""
    with pytest.raises(p4z.DelistedSampleStop, match="distribution"):
        p4z.audit_zip(_zip(tmp_path, dividend_missing))


def test_bad_price_and_duplicate_session_rejected(tmp_path):
    def zero(symbol, rows):
        if symbol == "SPY":
            rows[0]["adj_close"] = "0"
    with pytest.raises(p4z.DelistedSampleStop, match="Nonpositive"):
        p4z.audit_zip(_zip(tmp_path, zero))
    def duplicate(symbol, rows):
        if symbol == "KO":
            rows.insert(1, rows[0].copy())
    with pytest.raises(p4z.DelistedSampleStop, match="dates missing"):
        p4z.audit_zip(_zip(tmp_path, duplicate))


def test_research_boundary_does_not_download_or_execute(tmp_path):
    source = Path(p4z.__file__).read_text()
    for forbidden in ("alpaca.markets", "TradingClient", "submit_order",
                      "ALPACA_LIVE_KEY", "requests.post", "urlopen("):
        assert forbidden not in source
    assert p4z.BROKER_GETS == p4z.BROKER_POSTS == p4z.BROKER_ORDERS == 0
    with pytest.raises(p4z.DelistedSampleStop, match="missing"):
        p4z.audit_zip(tmp_path / "absent.zip")


def _sec_html():
    """Synthetic 8-K text: not vendor data and not a historical market signal."""
    return (
        "<html><body><h1>TWITTER, INC.</h1>"
        "<p>Common Stock, par value $0.000005 per share TWTR "
        "New York Stock Exchange</p>"
        "<p>On October 27, 2022, pursuant to the terms of the Merger "
        "Agreement, the Merger was consummated.</p>"
        "<p>Each issued and outstanding share was canceled and "
        "converted into the right to receive $54.20 in cash, "
        "without interest.</p>"
        "<p>As a result, trading of Twitter's common stock on the NYSE "
        "was suspended prior to the opening of the NYSE on "
        "October 28, 2022.</p>"
        + "<p>Unrelated original filing boilerplate.</p>" * 35
        + "</body></html>"
    ).encode()


def test_original_sec_cash_right_is_not_actual_broker_settlement(tmp_path):
    sec = tmp_path / "original-sec-8k.htm"
    sec.write_bytes(_sec_html())
    result = p4z.audit_zip(_zip(tmp_path), sec_merger_filing=sec)
    assert result["twtr_sec_verified_contractual_cash_consideration_usd"] == 54.20
    assert result["twtr_sec_merger_effective_date"] == "2022-10-27"
    assert result["twtr_sec_nyse_trading_suspended_before_open"] == "2022-10-28"
    assert result["sec_contractual_right_not_proof_of_actual_cash_settlement"]
    assert result["sec_later_filing_not_a_signal_at_2022_10_27_close"]
    assert len(result["sec_original_filing_sha256"]) == 64
    assert result["twtr_terminal_shareholder_proceeds_usd"] is None
    assert result["twtr_post_delisting_total_return"] is None
    assert result["historical_stock_alpha_backtest_eligible"] is False


@pytest.mark.parametrize("old,new,reason", [
    ("TWITTER, INC.", "ANOTHER ISSUER", "issuer"),
    ("TWTR New York Stock Exchange", "WRONG NASDAQ", "share-class"),
    ("Merger was consummated", "Merger was postponed", "completion"),
    ("$54.20 in cash", "$0.00 in cash", "consideration"),
    ("October 28, 2022.", "October 31, 2022.", "suspension"),
])
def test_sec_source_conflicts_fail_closed(old, new, reason):
    with pytest.raises(p4z.DelistedSampleStop, match=reason):
        p4z.audit_twtr_sec_merger(_sec_html().replace(old.encode(), new.encode()))


def test_sec_cash_right_requires_complete_original_filing(tmp_path):
    with pytest.raises(p4z.DelistedSampleStop, match="missing"):
        p4z.audit_zip(_zip(tmp_path), sec_merger_filing=tmp_path / "absent.htm")
    with pytest.raises(p4z.DelistedSampleStop, match="missing or oversized"):
        p4z.audit_twtr_sec_merger(b"<html>no filing</html>")


def test_sec_conflicting_cash_right_and_script_spoof_fail_closed():
    html = _sec_html()
    contradiction = html.replace(
        b"</body>",
        b"<p>Other shares converted into the right to receive "
        b"$51.20 in cash, without interest.</p></body>",
    )
    with pytest.raises(p4z.DelistedSampleStop, match="contradictory"):
        p4z.audit_twtr_sec_merger(contradiction)
    spoof = html.replace(
        b"<h1>TWITTER, INC.</h1>",
        b"<script>TWITTER, INC.</script>",
    )
    with pytest.raises(p4z.DelistedSampleStop, match="issuer"):
        p4z.audit_twtr_sec_merger(spoof)


def test_twtr_original_last_close_vs_later_contractual_right_is_ex_post_only(tmp_path):
    sec = tmp_path / "original-sec-8k.htm"
    sec.write_bytes(_sec_html())

    def last_price(symbol, rows):
        if symbol == "TWTR":
            rows[-1]["close"] = "50.00"
            rows[-1]["adj_close"] = "50.00"

    result = p4z.audit_zip(_zip(tmp_path, last_price), sec_merger_filing=sec)
    assert result["twtr_last_observed_raw_close_usd"] == 50.0
    assert result["twtr_sec_contractual_right_minus_last_close_usd"] == 4.2
    assert result["twtr_sec_contractual_right_vs_last_close_pct"] == 8.4
    assert result["twtr_contractual_spread_ex_post_not_tradeable_or_realized"]
    assert result["sec_later_filing_not_a_signal_at_2022_10_27_close"]
    assert result["twtr_terminal_shareholder_proceeds_usd"] is None
    assert result["twtr_post_delisting_total_return"] is None
    assert result["historical_stock_alpha_backtest_eligible"] is False


def test_twtr_ex_post_contractual_spread_can_be_negative(tmp_path):
    sec = tmp_path / "original-sec-8k.htm"
    sec.write_bytes(_sec_html())

    def last_price(symbol, rows):
        if symbol == "TWTR":
            rows[-1]["close"] = "60.00"

    result = p4z.audit_zip(_zip(tmp_path, last_price), sec_merger_filing=sec)
    assert result["twtr_sec_contractual_right_minus_last_close_usd"] == -5.8
    assert result["twtr_sec_contractual_right_vs_last_close_pct"] == pytest.approx(-9.666667)
    assert result["twtr_terminal_shareholder_proceeds_usd"] is None



def test_original_adjusted_vs_raw_corporate_action_return_bias_is_quantified(tmp_path):
    # Synthetic split/dividend adjustments deliberately differ from raw close.
    # The exercise is price-source arithmetic, not historical strategy alpha.
    def adjust(symbol, rows):
        if symbol == "TSLA":
            rows[0]["close"] = "900"
            rows[0]["adj_close"] = "300"
        if symbol in ("KO", "SPY"):
            rows[0]["adj_close"] = "290"
        if symbol == "TWTR":
            rows[-1]["close"] = "330"
            rows[-1]["adj_close"] = "330"
        if symbol == "SPY":
            next(r for r in rows if r["date"] == "2022-10-27")[
                "adj_close"] = "315"

    result = p4z.audit_zip(_zip(tmp_path, adjust))
    by_symbol = result["per_listing_observed_window"]
    assert set(by_symbol) == {"TSLA", "KO", "SPY", "TWTR"}
    assert by_symbol["TSLA"]["raw_close_price_change_pct"] == pytest.approx(
        -66.666667)
    assert by_symbol["TSLA"]["vendor_adjusted_close_change_pct"] == 0
    assert by_symbol["TSLA"]["adjusted_minus_raw_change_pp"] == pytest.approx(
        66.666667)
    assert by_symbol["KO"]["adjusted_minus_raw_change_pp"] == pytest.approx(
        3.448276)
    assert by_symbol["SPY"]["last_observed_close_session"] == "2022-12-30"
    assert by_symbol["TWTR"]["last_observed_close_session"] == "2022-10-27"
    matched = result["twtr_vs_spy_same_pre_suspension_window"]
    assert matched["first_session"] == "2022-07-01"
    assert matched["last_session"] == "2022-10-27"
    assert matched["twtr_vendor_adjusted_close_change_pct"] == 10
    assert matched["spy_vendor_adjusted_close_change_pct"] == pytest.approx(
        8.62069)
    assert matched["twtr_minus_spy_vendor_adjusted_change_pp"] == pytest.approx(
        1.37931)
    assert result["no_twtr_mark_or_portfolio_return_after_last_trading_bar"]
    assert result["vendor_adjusted_prices_not_independently_total_return_certified"]
    assert result["retrospectively_chosen_listings_not_a_point_in_time_universe"]
    assert result["observed_price_changes_not_realized_trade_or_settlement_returns"]
    assert result["twtr_terminal_shareholder_proceeds_usd"] is None
    assert result["twtr_post_delisting_total_return"] is None


def test_matching_twtr_and_spy_window_never_uses_later_spy_prices(tmp_path):
    base = p4z.audit_zip(_zip(tmp_path))

    def change_later_spy(symbol, rows):
        if symbol == "SPY":
            rows[-1]["close"] = "600"
            rows[-1]["adj_close"] = "600"

    changed = p4z.audit_zip(_zip(tmp_path, change_later_spy))
    assert (base["twtr_vs_spy_same_pre_suspension_window"] ==
            changed["twtr_vs_spy_same_pre_suspension_window"])
    assert (base["per_listing_observed_window"]["SPY"] !=
            changed["per_listing_observed_window"]["SPY"])
    assert base["twtr_post_delisting_total_return"] is None
    assert changed["twtr_post_delisting_total_return"] is None


def test_original_return_window_rejects_reversed_sessions():
    with pytest.raises(p4z.DelistedSampleStop, match="Reversed"):
        p4z._observed_close_return(
            {"date": "2022-10-27", "close": "100", "adj_close": "100"},
            {"date": "2022-07-01", "close": "100", "adj_close": "100"})


def test_independent_raw_close_split_and_dividend_chain_is_not_vendor_adjustment():
    # A 3-for-1 split preserves value; a later $1 distribution reinvested
    # against a $30 previous close increases the hypothetical wealth.
    rows = [
        {"date": "2022-08-24", "close": "90", "split": "", "dividend": ""},
        {"date": "2022-08-25", "close": "30", "split": "1:3", "dividend": ""},
        {"date": "2022-08-26", "close": "31", "split": "", "dividend": "1"},
    ]
    assert p4z._reconstruct_corporate_action_return(rows) == pytest.approx(
        100 * (32 / 30 - 1))
    # Unlike the original raw-close comparison, a split alone is not a loss.
    assert p4z._reconstruct_corporate_action_return(rows[:2]) == pytest.approx(0)


def test_independent_reconstruction_refuses_unknown_actions_and_bad_cash():
    rows = [
        {"date": "2022-07-01", "close": "100", "split": "", "dividend": ""},
        {"date": "2022-07-05", "close": "50", "split": "2:1", "dividend": ""},
    ]
    with pytest.raises(p4z.DelistedSampleStop, match="split ratio"):
        p4z._reconstruct_corporate_action_return(rows)
    rows[1].update(split="", dividend="-0.1")
    with pytest.raises(p4z.DelistedSampleStop, match="cash flow"):
        p4z._reconstruct_corporate_action_return(rows)
    rows[1]["dividend"] = "NaN"
    with pytest.raises(p4z.DelistedSampleStop, match="cash flow"):
        p4z._reconstruct_corporate_action_return(rows)
    rows[1].update(date="2022-07-01", dividend="")
    with pytest.raises(p4z.DelistedSampleStop, match="Nonchronological"):
        p4z._reconstruct_corporate_action_return(rows)


def test_source_report_keeps_reconstruction_separate_from_terminal_proceeds(tmp_path):
    result = p4z.audit_zip(_zip(tmp_path))
    assert result["corporate_action_reconstruction_uses_original_split_and_dividend_rows"]
    assert result["corporate_action_reconstruction_is_hypothetical_ex_date_reinvestment"]
    assert result["corporate_action_reconstruction_not_settled_or_investable_return"]
    for symbol in p4z.FILES:
        diagnostics = result["per_listing_observed_window"][symbol]
        assert isinstance(
            diagnostics["raw_close_split_dividend_reconstructed_change_pct"], float)
        assert isinstance(
            diagnostics["reconstructed_minus_vendor_adjusted_change_pp"], float)
    assert result["twtr_terminal_shareholder_proceeds_usd"] is None
    assert result["twtr_post_delisting_total_return"] is None
    assert not result["historical_stock_alpha_backtest_eligible"]
