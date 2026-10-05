from pathlib import Path
import sys,unittest
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run import simulate,arc_elasticity,contrast,MULTIPLIERS

class Experiments(unittest.TestCase):
    def test_accounting_and_customer_grain(self):
        d=simulate('Corridor-A',MULTIPLIERS,10000,np.random.default_rng(6),'screen')
        self.assertEqual(d.customer_id.nunique(),len(d))
        self.assertEqual(set(d.price_multiplier),set(MULTIPLIERS))
        np.testing.assert_allclose(d.contribution_usd,d.converted*(d.price_usd-d.variable_cost_usd))
        self.assertEqual(d.loc[d.converted==0,'revenue_usd'].sum(),0)
    def test_elasticity_sign_for_both_directions(self):
        self.assertLess(arc_elasticity(.65,.6,4.,5.),0)
        self.assertLess(arc_elasticity(.55,.6,6.,5.),0)
        self.assertEqual(arc_elasticity(.6,.6,6.,5.),0)
    def test_guardrail_rejects_large_conversion_loss(self):
        d=simulate('Corridor-C',[1.,1.2],30000,np.random.default_rng(7),'screen')
        r=contrast(d[d.price_multiplier==1.2],d[d.price_multiplier==1.],3.)
        self.assertLess(r['conversion_ni_lower'],0)
    def test_independent_followup_customer_ids(self):
        rng=np.random.default_rng(1)
        a=simulate('Corridor-A',[1.,1.1],1000,rng,'screening')
        b=simulate('Corridor-A',[1.,1.1],1000,rng,'confirmation')
        self.assertFalse(set(a.customer_id)&set(b.customer_id))
if __name__=='__main__':unittest.main()
