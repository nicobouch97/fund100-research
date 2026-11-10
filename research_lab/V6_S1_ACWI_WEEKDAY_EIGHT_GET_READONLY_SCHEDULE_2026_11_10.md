# Fund-100 V6-S1: original ACWI protected weekday read-only market-open replay

**10 November 2026 — no trade release, no new BUY principal.**

The last protected eight-GET run on 10 November at 21:04 UTC
authenticated the original 1M/3M broker source and had complete funded
XNYS sessions, but the authentic market clock was CLOSED. Thus the
active first-ACWI pure replay returned MARKET_NOT_OPEN_ACTIVE_REPLAY_HOLD
rather than evaluating the updated original-inventory-bounded SELL gate
from #625. The previous one-run-per-week Monday 09:39 New York
observation can defer new evidence unnecessarily.

Change only the existing workflow's **single reviewed cron** to
09:39 America/New_York Monday to Friday. No new workflow, job,
credential, secret, HTTP method, terminal risk writer, release switch,
operator setting, standing mandate, buy authorization or private
state mutation is added. Keep the identical eight GET endpoints,
time/cash source validations, exact source blob SHA, scoped
read-only GitHub token, main-branch restriction and source pin checks.

The full source-scope auditor must independently require the **exact
single** timezone-aware weekday cron, fail closed on altered weekdays
or any second schedule, and reject any new credentialed writer. The
read-only reader always verifies the original STOP and engaged kill
switch before protected broker access. Its replay uses the **real
broker clock**; a delayed, holiday or closed-market run says HOLD, never
pretends open or grants a broker POST. A source-only perfect match
also remains research only and cannot authorize orders.

The owner wants fully autonomous trading after proper release with
no routine per-order approvals. This scheduling change advances the
source evidence automatically, without an additional owner step;
separately released production risk and durable signed-state
control are still required to execute an order. Broker checks run
on GitHub Actions best-effort scheduling, not guaranteed exact time.
