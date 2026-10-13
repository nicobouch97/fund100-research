"""V2 synthetic IPO/delisting tests: no invented prices or terminal proceeds.

Uses the existing synthetic research bundle fixture. Nothing here proves a
vendor really supplies delisting settlements or as-of historical coverage.
"""

from __future__ import annotations

from datetime import timedelta
import json
import pytest

from fund100_v2.data_contract import load_research_bundle
from fund100_v2.signals import (
    ResearchPanel,
    score_on_close,
    top_research_candidate,
)
from fund100_v2.walkforward import (
    ResearchCosts,
    WalkForwardPlan,
    evaluate_decision,
    walk_forward,
)
from test_fund100_v2_data_contract import (
    make_bundle,
    modify_member,
    modify_price,
)


def _remove_price_rows(path, symbol, missing_sessions):
    modify_price(
        path,
        lambda rows: rows.__setitem__(
            slice(None),
            [
                row for row in rows
                if not (
                    row["symbol"] == symbol
                    and row["session"] in missing_sessions
                )
            ],
        ),
    )


def _mark_membership_false(path, symbol, missing_sessions):
    def change(rows):
        for row in rows:
            if row["symbol"] == symbol and row["session"] in missing_sessions:
                row["eligible"] = "FALSE"

    modify_member(path, change)


def _delete_price_range(path, dates, symbol, indices):
    gone = {dates[i].isoformat() for i in indices}
    _remove_price_rows(path, symbol, gone)
    _mark_membership_false(path, symbol, gone)


def test_pre_ipo_real_price_absence_and_sufficient_history_filter(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    _delete_price_range(tmp_path, days, "UP", range(45))
    panel = load_research_bundle(tmp_path, as_of=days[-1]).panel
    assert all(panel.adjusted_prices["UP"][i] is None for i in range(45))
    assert all(panel.spread_bps["UP"][i] is None for i in range(45))
    assert all("UP" not in panel.eligible_symbols[i] for i in range(45))
    assert panel.adjusted_prices["UP"][45] is not None
    assert top_research_candidate(panel, "medium_momentum", 70) is None
    assert top_research_candidate(panel, "medium_momentum", 106) == "UP"
    with pytest.raises(ValueError, match="Missing real price"):
        score_on_close(panel, "medium_momentum", 70, "UP")


def test_delisted_security_genuinely_disappears_from_panel(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    _delete_price_range(tmp_path, days, "UP", range(180, len(days)))
    bundle = load_research_bundle(tmp_path, as_of=days[-1])
    panel = bundle.panel
    assert panel.adjusted_prices["UP"][179] is not None
    assert all(panel.adjusted_prices["UP"][i] is None
               for i in range(180, len(days)))
    assert all("UP" not in panel.eligible_symbols[i]
               for i in range(180, len(days)))
    assert bundle.evidence.eligible_observations == (
        len(days) * 2 - (len(days) - 180)
    )


def test_open_hypothetical_position_without_delisting_settlement_fails(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    _delete_price_range(tmp_path, days, "UP", range(180, len(days)))
    panel = load_research_bundle(tmp_path, as_of=days[-1]).panel
    # At t=178, UP was eligible. Enter t+1=179, but no real exit t+2=180.
    assert top_research_candidate(panel, "medium_momentum", 178) == "UP"
    with pytest.raises(ValueError, match="delisting/exit settlement"):
        evaluate_decision(panel, "medium_momentum", 178, ResearchCosts())
    with pytest.raises(ValueError, match="delisting/exit settlement"):
        walk_forward(
            panel, WalkForwardPlan(
                min_train_decisions=30,
                test_decisions_per_fold=15,
                benchmark_symbol=None,
            ),
        )


def test_ineligible_at_later_entry_close_skips_fill_not_past_decision(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    _delete_price_range(tmp_path, days, "UP", range(180, len(days)))
    panel = load_research_bundle(tmp_path, as_of=days[-1]).panel
    assert top_research_candidate(panel, "medium_momentum", 179) == "UP"
    out = evaluate_decision(panel, "medium_momentum", 179, ResearchCosts())
    assert out.hypothetical_symbol is None
    assert out.gross_fraction == out.cost_fraction == out.net_fraction == 0


def test_missing_benchmark_close_fails_instead_of_zero_return(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    _delete_price_range(tmp_path, days, "UP", range(180, len(days)))
    panel = load_research_bundle(tmp_path, as_of=days[-1]).panel
    with pytest.raises(ValueError, match="Missing benchmark"):
        evaluate_decision(
            panel, "CASH", 179, ResearchCosts(), benchmark_symbol="UP"
        )


def test_false_membership_does_not_justify_interior_price_gap(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    _delete_price_range(tmp_path, days, "UP", [100])
    with pytest.raises(ValueError, match="Interior missing prices"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_eligible_asset_without_price_is_incomplete_not_cash(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    _remove_price_rows(
        tmp_path, "UP", {days[0].isoformat()}
    )
    with pytest.raises(ValueError, match="Missing price for historically eligible"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_membership_must_cover_pre_ipo_date_symbols(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    _delete_price_range(tmp_path, days, "UP", range(25))
    modify_member(
        tmp_path,
        lambda rows: rows.__setitem__(
            slice(None), [
                row for row in rows
                if not (
                    row["symbol"] == "UP"
                    and row["session"] == days[0].isoformat()
                )
            ]
        ),
    )
    with pytest.raises(ValueError, match="Incomplete historical membership"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_symbol_that_never_has_real_price_is_rejected(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    _delete_price_range(tmp_path, days, "UP", range(len(days)))
    with pytest.raises(ValueError, match="No observed historical price"):
        load_research_bundle(tmp_path, as_of=days[-1])


def test_ragged_dataset_changes_reproducibility_digest(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    original = load_research_bundle(tmp_path, as_of=days[-1])
    _delete_price_range(tmp_path, days, "UP", range(20))
    altered = load_research_bundle(tmp_path, as_of=days[-1])
    assert original.evidence.combined_sha256 != altered.evidence.combined_sha256


def test_delisted_asset_must_not_be_forward_filled_by_assumptions(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    _delete_price_range(tmp_path, days, "UP", range(150, len(days)))
    panel = load_research_bundle(tmp_path, as_of=days[-1]).panel
    assert panel.adjusted_prices["UP"][149] is not None
    assert panel.adjusted_prices["UP"][150] is None
    assert panel.adjusted_prices["UP"][-1] is None


@pytest.mark.parametrize("field", ["adjusted_prices", "spread_bps"])
def test_mismatched_missing_price_spread_rejected(field):
    days = []
    d = __import__("datetime").date(2025, 1, 1)
    while len(days) < 100:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    price = (None,) * 15 + (100.0,) * 85
    spread = (None,) * 15 + (3.0,) * 85
    kwargs = {
        "sessions": tuple(days),
        "adjusted_prices": {"ABC": price},
        "spread_bps": {"ABC": spread},
        "eligible_symbols": (
            (frozenset(),) * 15 + (frozenset({"ABC"}),) * 85
        ),
    }
    if field == "adjusted_prices":
        kwargs[field] = {"ABC": (100.0,) + price[1:]}
    else:
        kwargs[field] = {"ABC": (3.0,) + spread[1:]}
    with pytest.raises(ValueError, match="gaps must match"):
        ResearchPanel(**kwargs)


def test_existing_complete_history_still_scores_as_before(tmp_path):
    days, _, _, _ = make_bundle(tmp_path)
    panel = load_research_bundle(tmp_path, as_of=days[-1]).panel
    assert top_research_candidate(panel, "medium_momentum", 100) == "UP"
    assert all(price is not None for price in panel.adjusted_prices["UP"])
