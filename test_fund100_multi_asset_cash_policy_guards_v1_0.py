"""Reject unsafe cash-policy research inputs; no broker or order authority."""
import json
import unittest

import fund100_multi_asset_portfolio_arbiter_v1_0 as arb
import fund100_v6_investment_thesis_gate_v1_0 as theses


class ResearchCashPolicyGuards(unittest.TestCase):
    def test_undefined_cash_policy_rejected(self):
        reg=json.loads(theses.REGISTER.read_text())
        for candidate in (None, True, 0.95, "95%", "LIVE",
                          "UNLIMITED", "FULLY_ALLOCATED_100_LIVE", "", {}):
            with self.subTest(candidate=repr(candidate)):
                with self.assertRaises(arb.ArbiterStop):
                    arb.simulate(register=reg,proposals=[],cash_policy=candidate)

    def test_allowed_policy_set_is_frozen_and_no_leverage(self):
        self.assertEqual(set(arb.CASH_POLICIES),
                         {"BASELINE_95","LOW_BUFFER_98","FULLY_ALLOCATED_100"})
        self.assertTrue(all(0 <= x <= 1 for x in arb.CASH_POLICIES.values()))
        self.assertFalse(arb.LIVE_ORDERS_RELEASED)
        self.assertFalse(arb.BROKER_NETWORK_ENABLED)
        self.assertFalse(arb.PRIVATE_STATE_MUTATION_ENABLED)

    def test_full_allocation_does_not_authorize_research_hypothesis(self):
        reg=json.loads(theses.REGISTER.read_text())
        report=arb.simulate(register=reg,proposals=[],
                            cash_policy="FULLY_ALLOCATED_100")
        self.assertEqual(report["hypothetical_cash_usd"],"130.30")
        self.assertEqual(report["valid_live_strategy_count"],0)
        self.assertFalse(report["new_live_asset_classes_authorized"])
        self.assertEqual(report["broker_get_requests"],0)
        self.assertEqual(report["broker_post_requests"],0)
        self.assertEqual(report["private_state_write_requests"],0)

if __name__=="__main__":
    unittest.main()
