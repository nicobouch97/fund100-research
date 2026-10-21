import json
import unittest
import fund100_multi_asset_portfolio_arbiter_v1_0 as a
import fund100_v6_investment_thesis_gate_v1_0 as t

def make():
    return {"strategy_id":"V6-S1","asset_class":"equity_etfs",
            "mode":a.MODE,"requested_usd":"10.00",
            "instruments":{"XLK":"1"},"risk_factors":{"TECH":"1"},
            "order_authorized":False}

def run(q):
    return a.simulate(register=json.loads(t.REGISTER.read_text()),proposals=[q])

class InvalidProposals(unittest.TestCase):
    def test_decimal_money(self):
        for amount in ("-1","1.234","1e2","131.00"):
            p=make();p["requested_usd"]=amount
            with self.assertRaises(a.ArbiterStop):run(p)

    def test_baskets(self):
        for instruments in ({"XLK":"-1"},{"XLK":"0.9"},{"XLK":"0","XLE":"1"},{}):
            p=make();p["instruments"]=instruments
            with self.assertRaises(a.ArbiterStop):run(p)

    def test_unknown_thesis(self):
        p=make();p["strategy_id"]="UNKNOWN"
        with self.assertRaises(a.ArbiterStop):run(p)

if __name__=="__main__":unittest.main()
