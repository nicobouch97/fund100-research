import unittest
import json
import fund100_multi_asset_portfolio_arbiter_v1_0 as a
import fund100_v6_investment_thesis_gate_v1_0 as t

class Checks(unittest.TestCase):
    def test_empty(self):
        reg=json.loads(t.REGISTER.read_text())
        result=a.simulate(register=reg,proposals=[])
        self.assertEqual(result['hypothetical_cash_usd'],'130.30')
        self.assertFalse(result['portfolio_live_orders_authorized'])
        self.assertEqual(result['broker_post_requests'],0)

if __name__=='__main__': unittest.main()
