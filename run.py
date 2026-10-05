"""Randomized corridor price experiments; all customers and outcomes are synthetic."""
from pathlib import Path
import json, sqlite3
import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import norm, chisquare
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
SEED=41
MULTIPLIERS=[.8,.9,1.,1.1,1.2]
# Independent illustrative assumptions, not employer prices or elasticities.
CORRIDORS={'Corridor-A':(5.,.5,1.5),'Corridor-B':(7.,.2,3.4),'Corridor-C':(9.,-.1,7.5)}

def simulate(corridor, multipliers, n, rng, phase):
    base,intercept,sensitivity=CORRIDORS[corridor]
    assigned=rng.choice(multipliers,n)
    probability=expit(intercept-sensitivity*(assigned-1))
    converted=rng.binomial(1,probability)
    return pd.DataFrame({'customer_id':[f'{phase}-{corridor}-{i}' for i in range(n)],
        'corridor':corridor,'phase':phase,'price_multiplier':assigned,
        'price_usd':base*assigned,'send_amount_usd':300.,'converted':converted,
        'variable_cost_usd':.3*base,'revenue_usd':converted*base*assigned,
        'contribution_usd':converted*(base*assigned-.3*base)})

def contrast(t,c,z,conversion_margin=.1):
    pt,pc=t.converted.mean(),c.converted.mean()
    # Noninferiority tests p_t - (1-margin)*p_c >= 0.
    ni=pt-(1-conversion_margin)*pc
    ni_se=np.sqrt(pt*(1-pt)/len(t)+(1-conversion_margin)**2*pc*(1-pc)/len(c))
    diff=t.contribution_usd.mean()-c.contribution_usd.mean()
    cm_se=np.sqrt(t.contribution_usd.var(ddof=1)/len(t)+c.contribution_usd.var(ddof=1)/len(c))
    return {'conversion_relative_change':pt/pc-1,
            'conversion_ni_lower':ni-z*ni_se,
            'contribution_gain_usd':diff,'contribution_gain_lower':diff-z*cm_se,
            'contribution_gain_upper':diff+z*cm_se}

def arc_elasticity(pt,pc,price_t,price_c):
    return ((pt-pc)/((pt+pc)/2))/((price_t-price_c)/((price_t+price_c)/2))

def main():
    for folder in ['data','outputs']:(ROOT/folder).mkdir(exist_ok=True)
    rng=np.random.default_rng(SEED);tables=[];arm_rows=[];comparisons=[];decisions=[];confirm=[]
    # 12 screening comparisons across 3 corridors, simultaneous 95% coverage per metric family.
    z_screen=norm.ppf(1-.05/(2*12))
    # 6 confirmation endpoints across 3 corridors: conservative simultaneous intervals.
    z_confirm=norm.ppf(1-.05/(2*6))
    for corridor in CORRIDORS:
        d=simulate(corridor,MULTIPLIERS,25000,rng,'screening');tables.append(d)
        c=d[d.price_multiplier==1.];arm_stats=[];feasible=[]
        counts=d.groupby('price_multiplier').size().reindex(MULTIPLIERS)
        srm=float(chisquare(counts).pvalue)
        # Familywise 1% SRM alarm over up to six phase/corridor allocation checks.
        if srm < .01/6: raise RuntimeError('Screening allocation SRM alarm: investigate assignment before analysis')
        for m,g in d.groupby('price_multiplier'):
            row={'corridor':corridor,'multiplier':float(m),'customers':len(g),'price_usd':float(g.price_usd.iloc[0]),
                 'conversion':float(g.converted.mean()),'revenue_per_customer':float(g.revenue_usd.mean()),
                 'contribution_per_customer':float(g.contribution_usd.mean()),'srm_p_value':srm}
            arm_rows.append(row);arm_stats.append(row)
            if m==1.:
                feasible.append(row);continue
            stats=contrast(g,c,z_screen)
            # Stratified row bootstrap for finite-change (arc) elasticity; uncertainty conditional on arms.
            boots=[]
            for _ in range(500):
                # Binary sufficient statistics yield the same bootstrap as resampling Bernoulli rows.
                pt=rng.binomial(len(g),g.converted.mean())/len(g)
                pc=rng.binomial(len(c),c.converted.mean())/len(c)
                boots.append(arc_elasticity(pt,pc,g.price_usd.iloc[0],c.price_usd.iloc[0]))
            lo,hi=np.quantile(boots,[.025,.975])
            stats.update({'corridor':corridor,'multiplier':float(m),
                          'arc_elasticity':arc_elasticity(g.converted.mean(),c.converted.mean(),g.price_usd.iloc[0],c.price_usd.iloc[0]),
                          'elasticity_ci_low':float(lo),'elasticity_ci_high':float(hi),
                          'passes_conversion_guardrail':bool(stats['conversion_ni_lower']>=0)})
            comparisons.append(stats)
            if stats['passes_conversion_guardrail']:feasible.append(row)
        selected=max(feasible,key=lambda r:r['contribution_per_customer'])
        m=selected['multiplier']
        if m==1.:
            outcome='Keep current price';confirmation_result={}
        else:
            # Independent sample after selection: never reuse screening data to confirm uplift.
            v=simulate(corridor,[1.,m],16000,rng,'confirmation');tables.append(v)
            confirm_srm=float(chisquare(v.groupby('price_multiplier').size()).pvalue)
            if confirm_srm < .01/6: raise RuntimeError('Confirmation allocation SRM alarm: investigate assignment')
            confirmation_result=contrast(v[v.price_multiplier==m],v[v.price_multiplier==1.],z_confirm)
            confirmation_result['confirmation_srm_p_value']=confirm_srm
            confirm.append({'corridor':corridor,'multiplier':m,**confirmation_result})
            passed=confirmation_result['conversion_ni_lower']>=0 and confirmation_result['contribution_gain_lower']>0
            outcome='Confirmed in synthetic follow-up' if passed else 'Inconclusive: keep current pending further evidence'
        decisions.append({'corridor':corridor,'screening_selected_multiplier':m,'screening_srm_p_value':srm,
                          'outcome':outcome,**confirmation_result})
    data=pd.concat(tables,ignore_index=True);data.to_csv(ROOT/'data/customer_experiments.csv',index=False)
    arms=pd.DataFrame(arm_rows);arms.to_csv(ROOT/'outputs/arm_metrics.csv',index=False)
    pd.DataFrame(comparisons).to_csv(ROOT/'outputs/elasticity_and_guardrails.csv',index=False)
    pd.DataFrame(confirm).to_csv(ROOT/'outputs/confirmation_results.csv',index=False)
    pd.DataFrame(decisions).to_csv(ROOT/'outputs/recommendations.csv',index=False)
    conn=sqlite3.connect(ROOT/'outputs/experiments.sqlite');data.to_sql('experiments',conn,if_exists='replace',index=False)
    pd.read_sql_query((ROOT/'sql/metrics.sql').read_text(),conn).to_csv(ROOT/'outputs/sql_metrics.csv',index=False);conn.close()
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for corridor,g in arms.groupby('corridor'):
        axes[0].plot(g.multiplier,g.conversion,marker='o',label=corridor)
        axes[1].plot(g.multiplier,g.contribution_per_customer,marker='o',label=corridor)
    axes[0].set(xlabel='Price multiplier (1 = control)',ylabel='Observed conversion rate')
    axes[1].set(xlabel='Price multiplier (1 = control)',ylabel='Observed contribution / eligible customer (USD)')
    axes[0].legend();fig.suptitle('Synthetic randomized price increases and decreases')
    fig.savefig(ROOT/'outputs/experiment_tradeoffs.png',dpi=160);plt.close(fig)
    summary={'seed':SEED,'customers':len(data),'srm_alarm_threshold':.01/6,'conversion_guardrail':'No more than 10% relative conversion loss; chosen independently for illustration.',
             'selection_rule':'Highest observed contribution among tested prices passing the simultaneous conversion noninferiority guardrail; control always eligible.',
             'screening_ci':'Bonferroni 95% simultaneous across 12 comparisons per metric family',
             'confirmation_ci':'Bonferroni 95% simultaneous across up to 6 corridor endpoints',
             'elasticity_ci':'Pointwise 95% bootstrap, 500 draws; exploratory, not simultaneous',
             'recommendations':decisions,'scope':'Entirely synthetic; no employer prices, policies, customers or results.'}
    (ROOT/'outputs/summary.json').write_text(json.dumps(summary,indent=2))
    lines=['# Corridor price experiment: synthetic decision memo','',
           'Question: should each corridor lower, keep or raise its price? Measure response experimentally, maximize contribution per eligible customer, and protect conversion.','',
           '| Corridor | Screening choice vs current | Independent confirmation |','|---|---:|---|']
    for r in decisions:lines.append(f"| {r['corridor']} | {r['screening_selected_multiplier']-1:+.0%} | {r['outcome']} |")
    lines+=['','The balanced price is the best of the tested discrete prices under the stated guardrail. It is not a continuous global optimum. A confirmatory pass applies only to the independent synthetic follow-up.','',
            'Elasticity is estimated separately for increases and decreases using midpoint percentage changes in conversion and price. Do not assume a single constant elasticity across a nonlinear response curve.','',
            'The confirmatory test checks both positive contribution gain and conversion noninferiority. Inconclusive evidence means retain control and investigate or gather more evidence, not that there is no effect.','',
            'Limits: fixed $300 send amount; one eligible customer observation; fixed processing cost; no repeat behavior, retention, competitor response, complaints or FX volatility. Price is one all-in USD charge rather than separate fee and spread treatments. The 10% relative guardrail is illustrative, not an employer policy.','',
            'Next: agree on real business guardrails before testing; size experiments on contribution variance and conversion margin; use persistent customer assignment; evaluate retention and complaint rates; validate by customer tenure and send amount. Inspect SRM and implementation before interpreting results.']
    (ROOT/'outputs/decision_memo.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(decisions,indent=2))
if __name__=='__main__':main()
