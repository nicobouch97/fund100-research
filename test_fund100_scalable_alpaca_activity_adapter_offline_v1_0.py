"""Alpaca-shaped fixture paging tests, no real broker or order integration."""
import copy
import pytest

import fund100_scalable_alpaca_activity_adapter_offline_v1_0 as m

ID1 = "20261103000000000::fixture-001"


def event(index, *, kind="DIV", amount="1.00", day="2026-11-03",
          currency="USD"):
    return {
        "id": f"20261103000000000::fixture-{index:03d}",
        "activity_type": kind, "date": day, "net_amount": amount,
        "currency": currency,
    }


def pages(count=1):
    rows = [event(i) for i in range(count)]
    if rows:
        rows[0] = event(0, kind="CSD", amount="130.30")
    return [rows[i:i+m.PAGE_SIZE] for i in range(0, count, m.PAGE_SIZE)] or [[]]


def simulate(batch, *, fail_at=None, inception="2026-09-02", maximum=20):
    calls = []
    def request(*, path, params):
        assert path == "/v2/account/activities"
        assert params["category"] == "non_trade_activity"
        assert params["direction"] == "asc"
        assert params["after"] == "2026-09-01"
        assert params["page_size"] == 100
        if calls:
            assert params["page_token"] == batch[len(calls)-1][-1]["id"]
        else:
            assert "page_token" not in params
        if fail_at is not None and len(calls) == fail_at:
            raise OSError("synthetic unavailable")
        idx = len(calls)
        calls.append((path, params))
        return batch[idx] if idx < len(batch) else []
    out = m.inspect_injected(
        request=request, source_mode=m.SOURCE_MODE,
        account_inception_date=inception, latest_date="2026-11-09",
        max_pages=maximum)
    return out, calls


def stopped(result):
    assert result["live_orders_authorized"] is False
    assert result["standing_mandate_owner_authorized"] is False
    assert result["private_signed_funding_ledger_verified"] is False
    assert result["settled_cash_authenticated"] is False
    assert result["full_live_account_history_proven"] is False
    assert result["inception_date_authenticated"] is False
    assert result["private_account_activity_data_persisted"] is False
    assert result["identity_or_cash_values_disclosed"] is False
    assert result["broker_GETs"] == result["broker_POSTs"] == 0


def test_one_short_page_never_implies_settlement_or_live_authority():
    out, calls = simulate(pages(3))
    assert len(calls) == 1
    assert out["stage"] == "REVIEW_ONLY_DATE_NOT_SETTLEMENT"
    stopped(out)


def test_101_activity_rows_follow_tail_token_exactly():
    result, calls = simulate(pages(101))
    assert len(calls) == 2
    assert result["simulated_pages_read"] == 2
    assert result["simulated_rows_examined"] == 101
    assert result["stage"] == "REVIEW_ONLY_DATE_NOT_SETTLEMENT"
    stopped(result)


def test_exactly_100_rows_needs_empty_terminal_request():
    result, calls = simulate(pages(100))
    assert len(calls) == 2
    assert result["stage"] == "HOLD_NO_PROVEN_SETTLEMENT_OR_OWNER_AUTHORITY"
    stopped(result)


def test_complete_200_row_history_not_falsely_assumed_finished():
    result, calls = simulate(pages(200), maximum=2)
    assert len(calls) == 2
    assert result["stage"] == "HOLD_PAGINATION_LIMIT_REACHED"
    stopped(result)


def test_original_account_inception_before_query_bound_holds():
    result, calls = simulate(pages(1), inception="2026-08-28")
    assert calls == []
    assert result["stage"] == "HOLD_ACTIVITY_WINDOW_NOT_INCEPTION_QUALIFIED"
    stopped(result)


def test_exclusive_after_filter_must_predate_opening_day():
    r, calls = simulate(pages(1), inception="2026-09-01")
    assert calls == []
    assert r["stage"] == "HOLD_ACTIVITY_WINDOW_NOT_INCEPTION_QUALIFIED"
    stopped(r)


def test_empty_activity_history_holds():
    result, calls = simulate(pages(0))
    assert result["stage"] == "HOLD_NO_ACTIVITY_SOURCE"
    stopped(result)


def test_no_csd_only_income_holds():
    result, _ = simulate([[event(0, kind="DIV")]])
    assert result["stage"] == "HOLD_NO_QUALIFIED_CASH_DEPOSIT"
    stopped(result)


@pytest.mark.parametrize("bad", [
    lambda b: b[0][0].update(activity_type="ACATC"),
    lambda b: b[0][0].update(activity_type="JNLC"),
    lambda b: b[0][0].update(activity_type="UNKNOWN"),
    lambda b: b[0][0].update(activity_type="FILL"),
    lambda b: b[0][0].update(net_amount="-10.00"),
    lambda b: b[0][0].update(net_amount="1.001"),
    lambda b: b[0][0].update(net_amount="NaN"),
    lambda b: b[0][0].update(net_amount=None),
    lambda b: b[0][0].update(currency="GBP"),
    lambda b: b[0][0].update(currency=None),
    lambda b: b[0][0].update(date="2026-12-31"),
    lambda b: b[0][0].update(date="2026-01-01"),
    lambda b: b[0][0].update(id=""),
])
def test_unsupported_ambiguous_or_unsettled_flow_shape_holds(bad):
    b = pages(1)
    bad(b)
    r, _ = simulate(b)
    assert r["stage"] == "HOLD_UNQUALIFIED_ACTIVITY_ROWS"
    stopped(r)


def test_duplicate_activity_id_across_full_page_boundaries_holds():
    b = pages(101)
    b[1][0]["id"] = b[0][-1]["id"]
    r, _ = simulate(b)
    assert r["stage"] == "HOLD_UNQUALIFIED_ACTIVITY_ROWS"
    stopped(r)


def test_nonmonotone_activity_date_holds():
    b = [[event(0, kind="CSD", day="2026-11-05"),
          event(1, day="2026-11-04")]]
    r, _ = simulate(b)
    assert r["stage"] == "HOLD_UNQUALIFIED_ACTIVITY_ROWS"
    stopped(r)


def test_negative_principal_from_withdrawal_holds():
    b = [[event(0, kind="CSD", amount="10.00"),
          event(1, kind="CSW", amount="-11.00")]]
    r, _ = simulate(b)
    assert r["stage"] == "HOLD_NEGATIVE_CONTRIBUTED_PRINCIPAL"
    stopped(r)


def test_query_exception_holds_without_returning_private_ids():
    b = pages(101)
    r, _ = simulate(b, fail_at=1)
    assert r["stage"] == "HOLD_INJECTED_ACTIVITY_QUERY_FAILED"
    assert "fixture-" not in str(r) and "130.30" not in str(r)
    stopped(r)


def test_no_live_source_or_transport_release_possible():
    with pytest.raises(m.ActivityStop):
        m.inspect_injected(
            request=lambda **kw: [], source_mode="ALPACA_LIVE",
            account_inception_date="2026-09-02", latest_date="2026-11-09")
    assert m.LIVE_BROKER_READS_RELEASED is False
    assert m.LIVE_TRADING_RELEASED is False
    assert m.BROKER_GETS == m.BROKER_POSTS == 0
    from pathlib import Path
    source = Path(m.__file__).read_text()
    assert "urlopen" not in source
    assert "get_json" not in source
    assert "submit_order" not in source
    assert "load_credentials" not in source
