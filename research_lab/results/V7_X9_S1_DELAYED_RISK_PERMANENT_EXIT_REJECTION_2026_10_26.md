# V7-X9 empirical source-frozen S1 permanent-stop result — fail as return replacement

**26 October 2026, after testing the already preregistered rule.** Original
green brokerless run:
https://github.com/nicobouch97/fund100-research/actions/runs/40402140946
Seven focused adversarial tests passed; report artifact
fund100-v7-x9-source-frozen-risk-repairs-40402140946 contains 5, 15 and 35
basis-point scenarios for three fixed starts. No trading occurred.

## Historical return comparison, 15 bp per traded side

| Fixed start / common last session | Next-close risk maintained S1 CAGR | Unmanaged exact S1 CAGR | Equal-cash 95% ACWI CAGR | First permanent-stop signal |
| --- | ---: | ---: | ---: | --- |
| 2014 | **5.243964%** | 18.461156% | 11.925044% | 2020-03-09 |
| 2020 | **-2.667897%** | 18.405705% | 11.679244% | 2020-03-09 |
| 2023 | **3.890600%** | 21.715431% | 15.796919% | 2025-04-03 |

These are **retrospective synthetic account CAGRs, not actual performance,
forward forecasts or attainable alpha**. The eras substantially overlap.
The existing original ETF source was examined in earlier experiments.
The managed rule includes initial ETF buy friction, later modeled sell fees,
the next-close delay after a trigger, and the final comparison sell charge.
The unmanaged and ACWI references use the original exactly cash-matched
X8 side-cost model; real spreads, taxes and partial fills are unavailable.

The next-close model does NOT keep the account continuously compliant:
at 15bp, recorded after-delay cap breaches for the 2014 experiment include
**12 single-symbol breach sessions, 1 gross breach session,
1 cash-floor breach session and 1 day worse than the -6% daily limit**.
The 2020 experiment also breached the historical 20% drawdown trigger
before the next-close liquidation. In the 2023-start experiment, a
breach of the historical drawdown trigger persisted for many subsequent
cash-only sessions because the fund NAV remained below its old peak;
these are **not independent new drawdown events**.

## Decision

**Reject this deliberately permanent EXIT-then-remain-in-cash model as the
Fund-100 return-maximising S1 operating policy**. A stop triggered during
a sharp selloff permanently excluded later economic recovery, turning a
historically high-return sector exposure into a low-return cash account.
It is not proof that stop-losses are undesirable in general, and NOT a
reason to relax the original hard 6%/20%/35% account limits or assume
historical 18% S1 sector returns will recur.

A potential re-entry policy is a **distinct, future-sourced hypothesis**:
it must state an economically justified requalification criterion BEFORE
observing later outcomes, distinguish a hard trading stop from a new
mandate activation, account for new BUY-side costs and cash settlement,
reconfirm account risk and original stop/kill authority, and compare
risk-adjusted/after-cost forward outcomes with simple passive alternatives.
Do NOT post-hoc choose a re-entry date, trailing-vol window or price
threshold using this exact repeated 2014–2026 history.

The $130.30 LIVE mandate, original V5 positions, STOP, environment kill
and all brokerage-order permissions remain unchanged. This finding only
prioritises economically credible downside-control strategy research.
