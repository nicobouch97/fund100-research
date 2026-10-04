from __future__ import annotations

import pytest

import fund100_alpaca_live_writer_candidate_v1_1 as candidate


def intent():

    return {
        "symbol":
            "SPY",

        "side":
            "buy",

        "notional_usd":
            12.34,

        "client_order_id":
            "f100live-status-test-b-spy",

        "executable":
            True,
    }


def order(
    status: str,
):

    return {
        "id":
            "broker-order-123",

        "client_order_id":
            intent()[
                "client_order_id"
            ],

        "symbol":
            "SPY",

        "side":
            "buy",

        "type":
            "market",

        "time_in_force":
            "day",

        "notional":
            "12.34",

        "status":
            status,
    }


def patch_batch_validation(
    monkeypatch,
):

    monkeypatch.setattr(
        candidate,
        "require_public_execution_released",
        lambda: None,
    )

    monkeypatch.setattr(
        candidate,
        "validate_permit_package",
        lambda package: (
            {
                "schema":
                    "FUND100_LIVE_EXECUTION_PERMIT_V2",
            },
            100.0,
        ),
    )

    monkeypatch.setattr(
        candidate,
        "validate_order_batch",
        lambda intents, permit_cap: (
            intents,
            12.34,
        ),
    )

    monkeypatch.setattr(
        candidate,
        "validate_credentials",
        lambda key, secret: None,
    )


def test_release_flags_remain_false():

    assert (
        candidate.TRANSPORT_RELEASED
        is False
    )

    assert (
        candidate.PUBLIC_EXECUTION_ENABLED
        is False
    )


def test_full_frozen_universe():

    assert (
        candidate.ALLOWED_SYMBOLS
        == {
            "ACWI",
            "SPY",
            "IWM",
            "EFA",
            "EEM",
            "VNQ",
            "XLK",
            "XLF",
            "XLI",
            "XLV",
            "XLP",
            "XLY",
            "XLE",
            "XLU",
        }
    )


@pytest.mark.parametrize(
    "status",
    sorted(
        candidate.NO_RESUBMIT_STATUSES
    ),
)
def test_active_or_transitional_status_never_resubmits(
    status,
):

    assert (
        candidate.resolve_existing_order(
            existing=
                order(
                    status
                ),

            intent=
                intent(),
        )
        == "EXISTING_NO_RESUBMIT_ORDER"
    )


def test_filled_order_is_recovered():

    assert (
        candidate.resolve_existing_order(
            existing=
                order(
                    "filled"
                ),

            intent=
                intent(),
        )
        == "EXISTING_FILLED_ORDER"
    )


@pytest.mark.parametrize(
    "status",
    [
        "canceled",
        "expired",
        "rejected",
    ],
)
def test_terminal_failure_status_fails_closed(
    status,
):

    with pytest.raises(
        candidate.ExistingOrderTerminalFailure,
        match="Automatic resubmission",
    ):

        candidate.resolve_existing_order(
            existing=
                order(
                    status
                ),

            intent=
                intent(),
        )


@pytest.mark.parametrize(
    "status",
    [
        "replaced",
        "pending_replace",
        "suspended",
        "held",
        "mystery_status",
        "",
    ],
)
def test_unsafe_or_unknown_status_fails_closed(
    status,
):

    with pytest.raises(
        candidate.ExistingOrderUnsafeStatus,
    ):

        candidate.resolve_existing_order(
            existing=
                order(
                    status
                ),

            intent=
                intent(),
        )


def test_partially_filled_is_never_resubmitted():

    assert (
        candidate.resolve_existing_order(
            existing=
                order(
                    "partially_filled"
                ),

            intent=
                intent(),
        )
        == "EXISTING_NO_RESUBMIT_ORDER"
    )


def test_terminal_existing_order_never_calls_post(
    monkeypatch,
):

    patch_batch_validation(
        monkeypatch
    )

    monkeypatch.setattr(
        candidate,
        "_get_order_by_client_id",
        lambda **kwargs:
            order(
                "canceled"
            ),
    )

    post_called = {
        "value":
            False,
    }

    def forbidden_post(
        **kwargs,
    ):

        post_called[
            "value"
        ] = True

        raise AssertionError(
            "POST must not occur."
        )

    monkeypatch.setattr(
        candidate,
        "_post_live_market_order",
        forbidden_post,
    )

    with pytest.raises(
        candidate.ExistingOrderTerminalFailure,
    ):

        candidate.submit_authorized_order_batch(
            intents=[
                intent()
            ],

            permit_package={
                "synthetic":
                    True,
            },

            key=
                "fake-key",

            secret=
                "fake-secret",
        )

    assert (
        post_called[
            "value"
        ]
        is False
    )


def test_partially_filled_existing_order_never_calls_post(
    monkeypatch,
):

    patch_batch_validation(
        monkeypatch
    )

    monkeypatch.setattr(
        candidate,
        "_get_order_by_client_id",
        lambda **kwargs:
            order(
                "partially_filled"
            ),
    )

    post_called = {
        "value":
            False,
    }

    def forbidden_post(
        **kwargs,
    ):

        post_called[
            "value"
        ] = True

        raise AssertionError(
            "POST must not occur."
        )

    monkeypatch.setattr(
        candidate,
        "_post_live_market_order",
        forbidden_post,
    )

    result = (
        candidate.submit_authorized_order_batch(
            intents=[
                intent()
            ],

            permit_package={
                "synthetic":
                    True,
            },

            key=
                "fake-key",

            secret=
                "fake-secret",
        )
    )

    assert (
        result[
            "orders"
        ][
            0
        ][
            "status"
        ]
        == "EXISTING_NO_RESUBMIT_ORDER"
    )

    assert (
        post_called[
            "value"
        ]
        is False
    )


def test_filled_existing_order_never_calls_post(
    monkeypatch,
):

    patch_batch_validation(
        monkeypatch
    )

    monkeypatch.setattr(
        candidate,
        "_get_order_by_client_id",
        lambda **kwargs:
            order(
                "filled"
            ),
    )

    post_called = {
        "value":
            False,
    }

    def forbidden_post(
        **kwargs,
    ):

        post_called[
            "value"
        ] = True

        raise AssertionError(
            "POST must not occur."
        )

    monkeypatch.setattr(
        candidate,
        "_post_live_market_order",
        forbidden_post,
    )

    result = (
        candidate.submit_authorized_order_batch(
            intents=[
                intent()
            ],

            permit_package={
                "synthetic":
                    True,
            },

            key=
                "fake-key",

            secret=
                "fake-secret",
        )
    )

    assert (
        result[
            "orders"
        ][
            0
        ][
            "status"
        ]
        == "EXISTING_FILLED_ORDER"
    )

    assert (
        post_called[
            "value"
        ]
        is False
    )


def test_absent_order_submits_once(
    monkeypatch,
):

    patch_batch_validation(
        monkeypatch
    )

    monkeypatch.setattr(
        candidate,
        "_get_order_by_client_id",
        lambda **kwargs:
            None,
    )

    posts = {
        "count":
            0,
    }

    def fake_post(
        *,
        intent,
        key,
        secret,
    ):

        del key
        del secret

        posts[
            "count"
        ] += 1

        return order(
            "new"
        )

    monkeypatch.setattr(
        candidate,
        "_post_live_market_order",
        fake_post,
    )

    result = (
        candidate.submit_authorized_order_batch(
            intents=[
                intent()
            ],

            permit_package={
                "synthetic":
                    True,
            },

            key=
                "fake-key",

            secret=
                "fake-secret",
        )
    )

    assert (
        posts[
            "count"
        ]
        == 1
    )

    assert (
        result[
            "orders"
        ][
            0
        ][
            "status"
        ]
        == "SUBMITTED"
    )


@pytest.mark.parametrize(
    "status",
    [
        "canceled",
        "expired",
        "rejected",
    ],
)
def test_post_response_terminal_failure_fails_closed(
    status,
):

    with pytest.raises(
        candidate.SubmittedOrderTerminalFailure,
    ):

        candidate.validate_submitted_order_response(
            response=
                order(
                    status
                ),

            intent=
                intent(),
        )


@pytest.mark.parametrize(
    "status",
    [
        "replaced",
        "pending_replace",
        "suspended",
        "held",
        "unknown_status",
    ],
)
def test_post_response_unsafe_status_fails_closed(
    status,
):

    with pytest.raises(
        candidate.SubmittedOrderUnsafeStatus,
    ):

        candidate.validate_submitted_order_response(
            response=
                order(
                    status
                ),

            intent=
                intent(),
        )


@pytest.mark.parametrize(
    "status",
    [
        "accepted",
        "pending_new",
        "new",
        "partially_filled",
        "pending_cancel",
        "filled",
    ],
)
def test_post_response_safe_status_is_accepted(
    status,
):

    response = (
        order(
            status
        )
    )

    assert (
        candidate.validate_submitted_order_response(
            response=
                response,

            intent=
                intent(),
        )
        is response
    )


def test_status_sets_do_not_overlap():

    groups = [
        candidate.FILLED_STATUSES,
        candidate.NO_RESUBMIT_STATUSES,
        candidate.TERMINAL_FAILURE_STATUSES,
        candidate.AMBIGUOUS_UNSAFE_STATUSES,
    ]

    for index, left in enumerate(
        groups
    ):

        for right in groups[
            index + 1:
        ]:

            assert (
                left.isdisjoint(
                    right
                )
            )


def test_candidate_has_no_main():

    assert not hasattr(
        candidate,
        "main",
    )


def test_direct_get_stops_before_network(
    monkeypatch,
):

    called = {
        "value":
            False,
    }

    def forbidden_urlopen(
        *args,
        **kwargs,
    ):

        called[
            "value"
        ] = True

        raise AssertionError(
            "Network must not be reached."
        )

    monkeypatch.setattr(
        candidate,
        "urlopen",
        forbidden_urlopen,
    )

    with pytest.raises(
        candidate.LiveWriterCandidateLocked,
    ):

        candidate._get_order_by_client_id(
            client_order_id=
                "f100live-v11-get-test",

            key=
                "fake-key",

            secret=
                "fake-secret",
        )

    assert (
        called[
            "value"
        ]
        is False
    )


def test_direct_post_stops_before_network(
    monkeypatch,
):

    called = {
        "value":
            False,
    }

    def forbidden_urlopen(
        *args,
        **kwargs,
    ):

        called[
            "value"
        ] = True

        raise AssertionError(
            "Network must not be reached."
        )

    monkeypatch.setattr(
        candidate,
        "urlopen",
        forbidden_urlopen,
    )

    with pytest.raises(
        candidate.LiveWriterCandidateLocked,
    ):

        candidate._post_live_market_order(
            intent=
                intent(),

            key=
                "fake-key",

            secret=
                "fake-secret",
        )

    assert (
        called[
            "value"
        ]
        is False
    )
