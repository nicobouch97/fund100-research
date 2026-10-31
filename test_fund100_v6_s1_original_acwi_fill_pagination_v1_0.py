"""Bounded original ACWI FILL pagination, synthetic GETs only; no trading."""
from copy import deepcopy

import pytest

import fund100_v6_s1_original_acwi_broker_fill_flat_getonly_bridge_v1_0 as bridge
from test_fund100_v6_s1_original_acwi_broker_fill_flat_getonly_bridge_v1_0 import (
    source, KEY, SECRET,
)
from test_fund100_v6_s1_original_acwi_fill_flat_offline_v1_0 import (
    OBSERVED, OTHER_ID, START,
)


def _setup(monkeypatch):
    original, docs, _, _ = source(monkeypatch)
    final = deepcopy(docs[1][0])
    prior = []
    for n in range(bridge.FILL_LIMIT):
        row = deepcopy(final)
        row.update(
            id=f"historical-buy::{n}",
            order_id=OTHER_ID,
            transaction_time=START,
            symbol="EEM",
            side="buy",
            qty="0.01",
            cum_qty="0.01",
            leaves_qty="0",
        )
        prior.append(row)
    return original, docs, prior, final


def _transport(docs, prior, continuation):
    calls = []
    fixed = {
        "/v2/orders:by_client_order_id": docs[0],
        "/v2/account": docs[2],
        "/v2/positions": docs[3],
        "/v2/orders": docs[4],
        "/v2/clock": docs[5],
    }

    def request(*, path, params, key, secret):
        assert key == KEY and secret == SECRET
        calls.append((path, deepcopy(params)))
        if path == "/v2/account/activities/FILL":
            assert params["after"] == bridge.FILL_QUERY_AFTER
            assert params["direction"] == "asc"
            assert params["page_size"] == bridge.FILL_LIMIT
            if "page_token" not in params:
                return deepcopy(prior)
            assert params["page_token"] == prior[-1]["id"]
            return deepcopy(continuation)
        assert path in fixed
        return deepcopy(fixed[path])

    return request, calls


def _inspect(original, transport):
    return bridge.inspect_original_acwi_after_first_attempt(
        signed_prepost_sources=original["signed_prepost_sources"],
        key=KEY,
        secret=SECRET,
        transport=transport,
        now_utc=OBSERVED,
    )


def test_complete_101_fill_history_requires_second_real_route_get(monkeypatch):
    original, docs, prior, final = _setup(monkeypatch)
    transport, calls = _transport(docs, prior, [final])
    result = _inspect(original, transport)
    assert result["status"] == (
        "BOUNDED_BROKER_GET_ORIGINAL_ACWI_FILL_AND_FLAT_STRUCTURALLY_MATCH")
    assert result["broker_GET_count"] == 7
    assert len(calls) == 7
    assert calls[2] == (
        "/v2/account/activities/FILL",
        {"after": bridge.FILL_QUERY_AFTER, "direction": "asc",
         "page_size": bridge.FILL_LIMIT, "page_token": prior[-1]["id"]},
    )
    assert result["broker_POST_count"] == result["private_Git_PUT_count"] == 0
    assert result["next_legacy_sell_or_any_live_buy_released"] is False
    assert result["real_broker_source_authenticated_by_this_adapter"] is False


def test_repeated_full_page_fails_closed_without_any_broker_write(monkeypatch):
    original, docs, prior, _ = _setup(monkeypatch)
    transport, calls = _transport(docs, prior, prior)
    with pytest.raises(bridge.ReadStop):
        _inspect(original, transport)
    assert len(calls) == 3
    assert all(path in (
        "/v2/orders:by_client_order_id", "/v2/account/activities/FILL")
        for path, _ in calls)


def test_full_page_without_last_activity_id_cannot_be_paginated(monkeypatch):
    original, docs, prior, final = _setup(monkeypatch)
    prior[-1]["id"] = ""
    transport, calls = _transport(docs, prior, [final])
    with pytest.raises(bridge.ReadStop):
        _inspect(original, transport)
    assert len(calls) == 2


def test_exhausted_page_limit_fails_closed_before_other_account_gets(monkeypatch):
    original, docs, prior, _ = _setup(monkeypatch)
    calls = []
    def request(*, path, params, key, secret):
        assert key == KEY and secret == SECRET
        calls.append(path)
        if path == "/v2/orders:by_client_order_id":
            return deepcopy(docs[0])
        assert path == "/v2/account/activities/FILL"
        page_index = len(calls) - 2
        page = deepcopy(prior)
        for row in page:
            row["id"] += f"::page-{page_index}"
        if page_index:
            assert params["page_token"] == (
                f"historical-buy::{bridge.FILL_LIMIT-1}::page-{page_index-1}")
        return page
    with pytest.raises(bridge.ReadStop):
        _inspect(original, request)
    assert len(calls) == 1 + bridge.proof.MAX_PAGES
    assert all(path == "/v2/account/activities/FILL" for path in calls[1:])


def test_nonlist_continuation_is_not_a_complete_history(monkeypatch):
    original, docs, prior, _ = _setup(monkeypatch)
    transport, calls = _transport(docs, prior, {"unexpected": "shape"})
    with pytest.raises(bridge.ReadStop):
        _inspect(original, transport)
    assert len(calls) == 3
