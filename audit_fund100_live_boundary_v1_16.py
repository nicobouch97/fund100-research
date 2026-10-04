from __future__ import annotations

import ast
import inspect
from pathlib import Path

import audit_fund100_live_boundary_v1_15 as v115

import fund100_alpaca_live_cumulative_cap_guard_v1_0 as cap_guard
import fund100_alpaca_live_writer_candidate_v1_1 as candidate


# ============================================================
# FUND-100 LIVE BOUNDARY STATIC AUDIT v1.16
# ============================================================
#
# Adds review of the cumulative permit-cap reconstruction
# guard.
#
# The guard must remain:
#
# - pure
# - credential-free
# - environment-free
# - network-free
# - persistence-free
# - without main()
#
# It must require complete broker lookup reconstruction across
# every compiler-authorized client_order_id before approving a
# new batch.
#
# ============================================================


ROOT = Path(
    __file__
).resolve().parent


CAP_GUARD_PATH = (
    ROOT
    / "fund100_alpaca_live_cumulative_cap_guard_v1_0.py"
)


CAP_GUARD_TEST_PATH = (
    ROOT
    / "test_fund100_alpaca_live_cumulative_cap_guard_v1_0.py"
)


def imported_modules(
    source: str,
):

    tree = ast.parse(
        source
    )

    result = set()

    for node in ast.walk(
        tree
    ):

        if isinstance(
            node,
            ast.Import,
        ):

            for alias in node.names:

                result.add(
                    alias.name
                )

        elif isinstance(
            node,
            ast.ImportFrom,
        ):

            if node.module:

                result.add(
                    node.module
                )

    return result


def verify_cumulative_cap_guard():

    if not CAP_GUARD_PATH.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap guard source missing."
        )

    if not CAP_GUARD_TEST_PATH.exists():

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap guard tests missing."
        )

    source = (
        CAP_GUARD_PATH.read_text(
            encoding="utf-8"
        )
    )

    modules = (
        imported_modules(
            source
        )
    )

    prohibited_network_modules = {
        "requests",
        "httpx",
        "aiohttp",
        "socket",
        "urllib.request",
        "urllib3",
    }

    network_hits = (
        prohibited_network_modules
        .intersection(
            modules
        )
    )

    if network_hits:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap guard imports "
            "network client(s): "
            + ", ".join(
                sorted(
                    network_hits
                )
            )
        )

    prohibited_modules = {
        "os",
        "subprocess",
        "sqlite3",
    }

    module_hits = (
        prohibited_modules
        .intersection(
            modules
        )
    )

    if module_hits:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap guard imports "
            "prohibited runtime/persistence module(s): "
            + ", ".join(
                sorted(
                    module_hits
                )
            )
        )

    prohibited_tokens = [
        "ALPACA_LIVE_KEY",
        "ALPACA_LIVE_SECRET",
        "ALPACA_PAPER_KEY",
        "ALPACA_PAPER_SECRET",
        "os.environ",
        "getenv(",
        "urlopen(",
        "Request(",
        "open(",
        "write_text(",
        "write_bytes(",
        "json.dump(",
    ]

    hits = [
        token
        for token
        in prohibited_tokens
        if token in source
    ]

    if hits:

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap guard contains "
            "prohibited runtime/network/persistence "
            "token(s): "
            + ", ".join(
                hits
            )
        )

    if hasattr(
        cap_guard,
        "main",
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap guard contains main()."
        )

    if (
        cap_guard.GUARD_VERSION
        != "1.0"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "unexpected cumulative-cap guard version."
        )

    if (
        cap_guard.PERSISTENCE_POLICY
        != "EPHEMERAL_DO_NOT_COMMIT"
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative-cap guard persistence "
            "policy changed."
        )

    required_functions = [
        "build_authorized_index",
        "validate_complete_lookup_map",
        "validate_observed_order",
        "reconstruct_consumed_state",
        "validate_proposed_batch",
        "evaluate_cumulative_cap",
    ]

    for name in required_functions:

        if not callable(
            getattr(
                cap_guard,
                name,
                None,
            )
        ):

            raise RuntimeError(
                "LIVE STATIC AUDIT STOP: "
                f"cumulative-cap function "
                f"{name!r} missing."
            )

    evaluate_source = (
        inspect.getsource(
            cap_guard.evaluate_cumulative_cap
        )
    )

    required_evaluate_tokens = [
        "reconstruct_consumed_state",
        "blocking_existing_orders",
        "validate_proposed_batch",
        "projected > permit_cap",
    ]

    for token in required_evaluate_tokens:

        if token not in evaluate_source:

            raise RuntimeError(
                "LIVE STATIC AUDIT STOP: "
                "cumulative-cap evaluator lost "
                f"required control {token!r}."
            )

    reconstruct_source = (
        inspect.getsource(
            cap_guard.reconstruct_consumed_state
        )
    )

    if (
        "validate_complete_lookup_map"
        not in reconstruct_source
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "cumulative reconstruction no longer "
            "requires complete client-ID lookup."
        )

    if (
        candidate.TRANSPORT_RELEASED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer candidate transport released."
        )

    if (
        candidate.PUBLIC_EXECUTION_ENABLED
        is not False
    ):

        raise RuntimeError(
            "LIVE STATIC AUDIT STOP: "
            "writer candidate public execution enabled."
        )

    print(
        "PASS: Cumulative-cap guard is pure."
    )

    print(
        "PASS: Cumulative-cap guard imports no "
        "network client."
    )

    print(
        "PASS: Cumulative-cap guard contains no "
        "broker credential hook."
    )

    print(
        "PASS: Cumulative-cap guard contains no "
        "environment activation hook."
    )

    print(
        "PASS: Cumulative-cap guard contains no "
        "persistence path."
    )

    print(
        "PASS: Cumulative-cap guard has no main()."
    )

    print(
        "PASS: Complete authorized client-ID lookup "
        "is mandatory."
    )

    print(
        "PASS: Historical broker-observed notional "
        "is reconstructed before new batch gross."
    )

    print(
        "PASS: Historical plus new gross is checked "
        "against one permit ceiling."
    )

    print(
        "PASS: Terminal/unsafe historical state "
        "blocks continued execution."
    )

    print(
        "PASS: Writer candidate v1.1 remains "
        "hard locked."
    )


def main():

    print(
        "Fund-100 static audit safety layer: v1.16"
    )

    verify_cumulative_cap_guard()

    v115.main()


if __name__ == "__main__":

    main()
