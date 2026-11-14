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


def test_retired_v5_bootstrap_no_requests_even_if_kill_disengaged(monkeypatch):
    """Synthetic GO and live key names cannot revive historical bootstrap."""
    assert bootstrap.LEGACY_V5_BOOTSTRAP_RELEASED is False
    monkeypatch.setenv("FUND100_BROKER_KILL_SWITCH", "DISENGAGED")
    monkeypatch.setenv("FUND100_LIVE_BOOTSTRAP_ARM", "YES")
    monkeypatch.setenv("ALPACA_LIVE_KEY", "OFFLINE_SYNTHETIC_NOT_REAL")
    monkeypatch.setenv("ALPACA_LIVE_SECRET", "OFFLINE_SYNTHETIC_NOT_REAL")
    monkeypatch.setattr(bootstrap, "urlopen", lambda *a, **k: pytest.fail(
        "Legacy V5 must never access Alpaca transport"))
    monkeypatch.setattr(bootstrap, "require_environment", lambda: pytest.fail(
        "Legacy V5 must stop before live environment bootstrap"))
    for method in ("GET", "POST"):
        with pytest.raises(bootstrap.LiveBootstrapStop,
                           match="Retired V5 bootstrap broker access disabled"):
            bootstrap.live_request(method=method, path="/v2/orders", body={})
    with pytest.raises(bootstrap.LiveBootstrapStop,
                       match="Retired V5 bootstrap entrypoint disabled"):
        bootstrap.main()
    assert bootstrap.GET_COUNT == 0
    assert bootstrap.POST_COUNT == 0


def test_retired_v5_bootstrap_lock_precedes_credentials_and_network():
    import inspect
    code = inspect.getsource(bootstrap.live_request)
    check = code.index("if LEGACY_V5_BOOTSTRAP_RELEASED is not True:")
    assert check < code.index("method = (")
    assert check < code.index("request = Request(")
    main = inspect.getsource(bootstrap.main)
    assert main.index("if LEGACY_V5_BOOTSTRAP_RELEASED is not True:") < main.index(
        "require_environment()")
    assert bootstrap.LEGACY_V5_BOOTSTRAP_RELEASED is False
