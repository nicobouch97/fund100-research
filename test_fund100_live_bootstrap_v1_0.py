from decimal import Decimal

import pytest

import fund100_live_bootstrap_v1_0 as bootstrap


def test_allocations_never_exceed_ceiling():

    allocations = (
        bootstrap.build_allocations(
            weights={
                "ACWI":
                    Decimal("0.75"),

                "EEM":
                    Decimal("0.0833333333"),

                "XLE":
                    Decimal("0.0833333333"),

                "XLV":
                    Decimal("0.0833333334"),
            },
            ceiling=Decimal("130.30"),
        )
    )

    assert (
        sum(
            allocations.values()
        )
        <= Decimal("130.30")
    )


def test_ids_are_deterministic():

    allocations = {
        "ACWI":
            Decimal("97.72"),

        "EEM":
            Decimal("10.85"),
    }

    a = bootstrap.build_client_ids(
        shadow_sha256="a" * 64,
        allocations=allocations,
    )

    b = bootstrap.build_client_ids(
        shadow_sha256="a" * 64,
        allocations=allocations,
    )

    assert a == b


def test_live_host_is_exact():

    assert (
        bootstrap.LIVE_BASE_URL
        == "https://api.alpaca.markets"
    )

    assert (
        bootstrap.EXPECTED_LIVE_HOST
        == "api.alpaca.markets"
    )


def test_negative_target_weight_rejected():

    with pytest.raises(
        bootstrap.LiveBootstrapStop
    ):

        bootstrap.target_weights_from_manifest(
            {
                "target_weights": {
                    "ACWI":
                        1.01,

                    "EEM":
                        -0.01,
                }
            }
        )
