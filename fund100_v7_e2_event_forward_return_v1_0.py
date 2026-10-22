"""V7 E2: pure, forward-only event trade research, never a brokerage instruction."""
from __future__ import annotations
from datetime import datetime, date, timezone
from math import isfinite

class EvidenceStop(ValueError):
    pass

def utc(s: str) -> datetime:
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise EvidenceStop("invalid source timestamp") from exc
    if d.tzinfo is None:
        raise EvidenceStop("timestamp lacks timezone")
    return d.astimezone(timezone.utc)

def evaluate(event: dict, sessions: list[dict], cost_bps=(5, 15, 35)) -> dict:
    """Sessions: consecutive completed market sessions with dated closes.
    Entry/exit values are indicative CLOSE-to-CLOSE, not executable broker fills.
    event requires genuinely acquired SEC and price-source UTC timestamps.
    """
    if event.get("source_kind") != "SEC_8K_ITEM_2_02" or not event.get("sec_accession"):
        raise EvidenceStop("source is not an evidenced original SEC earnings filing")
    filing = date.fromisoformat(event["filing_date"])
    sec_at = utc(event["sec_acquired_at_utc"])
    price_at = utc(event["price_acquired_at_utc"])
    rows = sorted(sessions, key=lambda r: r["session"])
    dates = [date.fromisoformat(r["session"]) for r in rows]
    if dates != sorted(set(dates)) or len(rows) < 5:
        raise EvidenceStop("duplicate, unordered or insufficient sessions")
    for row in rows:
        for k in ("stock_close", "benchmark_close"):
            v = float(row[k])
            if not isfinite(v) or v <= 0:
                raise EvidenceStop("invalid price")
    before = [i for i,d in enumerate(dates) if d < filing]
    after = [i for i,d in enumerate(dates) if d > filing]
    if not before or len(after) < 4:
        raise EvidenceStop("need pre-filing and four post-filing sessions")
    signal_i = after[1]
    entry_i = after[2]
    exit_i = after[3]
    signal_end = utc(rows[signal_i]["completed_at_utc"])
    entry_end = utc(rows[entry_i]["completed_at_utc"])
    exit_end = utc(rows[exit_i]["completed_at_utc"])
    if sec_at > signal_end or price_at < signal_end or price_at >= entry_end:
        raise EvidenceStop("SEC or signal data not available by entry session")
    if not (signal_end < entry_end < exit_end):
        raise EvidenceStop("sessions not in chronological completion order")
    # Both future closes need independent acquisition AFTER the exit close.
    future_at = utc(event["future_prices_acquired_at_utc"])
    if future_at < exit_end:
        raise EvidenceStop("future price source predates exit close")
    base_i = before[-1]
    s0 = float(rows[base_i]["stock_close"])
    b0 = float(rows[base_i]["benchmark_close"])
    signal_rel = (float(rows[signal_i]["stock_close"])/s0 - 1) - (float(rows[signal_i]["benchmark_close"])/b0 - 1)
    if signal_rel < .02:
        return {"status":"NO_SIGNAL", "signal_relative_return":round(signal_rel, 10), "orders_authorized":False}
    stock = float(rows[exit_i]["stock_close"])/float(rows[entry_i]["stock_close"])-1
    bench = float(rows[exit_i]["benchmark_close"])/float(rows[entry_i]["benchmark_close"])-1
    costs = {}
    for bps in cost_bps:
        if not isinstance(bps, int) or bps < 0 or bps > 1000:
            raise EvidenceStop("invalid per-side cost")
        costs[str(bps)] = round(stock - bench - 2*bps/10000, 10)
    return {
        "status":"HYPOTHETICAL_FORWARD_CLOSE_MARK_NOT_FILL",
        "entry_session":str(dates[entry_i]), "exit_session":str(dates[exit_i]),
        "signal_relative_return":round(signal_rel,10),
        "gross_stock_return":round(stock,10), "gross_benchmark_return":round(bench,10),
        "benchmark_relative_net_two_sided_cost":costs,
        "execution_prices_authenticated":False, "alpha_proven":False,
        "orders_authorized":False
    }
