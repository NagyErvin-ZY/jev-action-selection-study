"""Deterministic checks of pairing, clustering, and semantic distribution alignment."""
from collections import defaultdict
from itertools import product
from analyze_static import *


def main():
    a={'a':.8,'b':.2};b={'a':.2,'b':.8}
    assert abs(distance_distributions(a,b)['tv']-.6)<1e-12
    assert distance_distributions(a,a)=={'tv':0.,'js_bits':0.}
    assert distance_distributions({'a':1},{'b':1})=={'tv':1.,'js_bits':1.}
    job1={'menu':{'Duck':{'kind':'swap'},'Car':{'kind':'reroll'}}}
    job2={'menu':{'Furnace':{'kind':'reroll'},'Ball':{'kind':'swap'}}}
    row1={'probabilities':{'Duck':.7,'Car':.3},'choice':'Duck'}
    row2={'probabilities':{'Furnace':.3,'Ball':.7},'choice':'Ball'}
    assert semdist(row1,job1)==semdist(row2,job2)
    assert chosen_semantic(row1,job1)==chosen_semantic(row2,job2)
    cases={'a':{'id':'a','origin':'fresh','family':'one','split':'diagnostic'},
           'b':{'id':'b','origin':'fresh','family':'one','split':'diagnostic'},
           'c':{'id':'c','origin':'fresh','family':'two','split':'heldout'}}
    e=estimate([('a',0),('b',0),('c',1)],cases)
    assert e['mean']==.5 and e['clusters']==2 and e['cases']==3
    saved_cases={
        'saved_jev_simple_00_001':{'id':'saved_jev_simple_00_001','origin':'saved','family':'saved_simple'},
        'saved_jev_simple_07_005':{'id':'saved_jev_simple_07_005','origin':'saved','family':'saved_simple'},
        'saved_jev_medium_01_002':{'id':'saved_jev_medium_01_002','origin':'saved','family':'saved_medium'},
    }
    es=estimate([(ident,0 if c['family']=='saved_simple' else 1) for ident,c in saved_cases.items()],saved_cases)
    assert es['clusters']==2 and es['mean']==.5, 'Saved episodes must cluster by original equation, not seed/episode.'
    index=defaultdict(list)
    for ident in cases:
        for n,s,g in product([0,1],repeat=3):
            cond=f'n{n}_s{s}_g{g}'
            for repeat in range(2):
                index[(ident,'core',cond)].append({'variant':{'neutral':bool(n),'structured':bool(s),'guided':bool(g)},
                    'evaluators':{p:{'probability_quality':.4+.1*g,'expected_regret_steps':2-g,'full_pool_regret':3-g} for p in POLICIES}})
    results=comparisons([],cases,index,['fresh'])
    for r in results:
        expected=(.1 if r['metric']=='probability_quality' else -1) if r['treatment'] in ('guided','combined') else 0
        assert abs(r['effect']['mean']-expected)<1e-12
    index[('a','core',BASE)].pop()
    result=next(r for r in comparisons([],cases,index,['fresh']) if r['metric']=='probability_quality' and r['treatment']=='combined')
    assert result['effect']['cases']==2
    print('PASS: semantic relabelling invariance, distribution distances, equal-cluster weighting, factorial pairing, and incomplete-repeat exclusion.')


if __name__=='__main__':main()
