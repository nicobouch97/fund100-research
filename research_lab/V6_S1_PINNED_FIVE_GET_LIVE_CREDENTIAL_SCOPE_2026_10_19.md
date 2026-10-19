# V6-S1 – separate narrow LIVE credential pin review

**19 October 2026, after credential-free source PR #66 was independently merged.**

The first actual connected five-GET design was correctly **rejected** by the existing global LIVE static audit because its command was new and not in the explicitly approved, source-hash-pinned credential list. We did not weaken that audit or treat PR-only tests as a genuine broker inspection. PR #66 isolated the data/parser work, kept the connected job disabled, and passed all original repository audits before merge.

This second, explicitly separate scoped release adds ONLY this one extra allowed pair to `audit_fund100_live_boundary.py`:

- Workflow: `.github/workflows/fund100-v6-s1-live-risk-history-getonly.yml`.
- Executable: `fund100_v6_s1_live_risk_history_getonly_v1_0.py`, exact reviewed Git **blob SHA** `e195746ed594c3215f6d83198c64778a24a8cf63`.

Approval remains **revocable on code change**, not globally granted to the file name: every import or code change that alters these direct trusted read-only/risk dependency Git blobs will fail permission until separately reviewed:

- `fund100_alpaca_live_readonly_smoke.py` blob SHA `cf871f849a140c7b1db29fd991c8e00da31e1974`. Exact method **GET** only.
- `fund100_v6_real_live_getonly_transition_readiness_v1_0.py` blob SHA `7fc9f7b0c75ca265ceb3e9a9a7106eae34d262a2`. Previous 4-GET account identity/original quantity verifier.
- `fund100_live_portfolio_risk_v1_0.py` exact original risk-module pin. Raw 1D history only, never sufficient for money-flow-adjusted release.

The new workflow may only give the reviewed script credentials in the existing protected `fund100-live-broker` environment on **main** and outside pull requests. It must hold `FUND100_BROKER_KILL_SWITCH`, `FUND100_RISK_LEVEL`, `FUND100_ENABLE_LIVE_READONLY=YES_READ_ONLY_LIVE` original checks. It has no recurring schedule, no broadened allowlist, no submit/modify/delete permissions or order adapter, and no CASH balances or account IDs in logs. The credential command's file SHA is checked by the same global audit. Negative unit tests intentionally alter **every one** of these required locks/pins to prove credential eligibility disappears. Zero LIVE orders.

Unlike the offline PR, a successful post-merge push on main will attempt a **genuine authenticated original Alpaca five-GET source inspection**. If the account history is unavailable or insufficient, it will truthfully report a blocked/unknown broker raw-history status. It will **not** infer T+1 settled sale proceeds, cash-flow-adjusted strategy performance, successful active-investment alpha or V6 LIVE trading release. The actual old ACWI/EEM/XLE/XLV positions remain held; the broker kill and remote operator STOP remain engaged.
