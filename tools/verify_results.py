"""Reconstruct every main/follow-up trajectory request and assert article claims."""
from pathlib import Path
from collections import Counter
from decimal import Decimal
import json, random, sys

OUT=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(OUT/'jev-hypotheses'))
import campaign as c
from prompt_arms import VARIANTS,make_payload

def read(name):return json.loads((OUT/'jev-hypotheses'/name).read_text())
cases={r['id']:r for r in read('rollout_cases.json')}
variants={v['id']:v for v in VARIANTS}
decisions=0;totals=Counter()
for folder in ['rollouts','factorial_rollouts']:
    for path in sorted((OUT/'jev-hypotheses'/folder).glob('*.json')):
        ep=json.loads(path.read_text());state=c.freeze(cases[ep['case_id']]['state']);root=c.solution(state)
        rng=random.Random(c.seed(ep['case_id'])+ep['repeat']);history=[]
        variant=variants[ep['variant_id']] if folder=='factorial_rollouts' else (c.BASE if ep['policy']=='original_random' else c.COMBINED)
        mode='cover_best' if ep['policy']=='combined_coverage' else 'random'
        visits=Counter({c.signature(state):1});streak=rerolls=premature=lastbest=0;best=c.distance(state)
        maxsteps=min(120,max(24,4*best+12));stagnation=min(30,max(12,best));terminal=None
        for row in ep['trajectory']:
            assert terminal is None,'Continued after cutoff'
            step=row['step'];menu=c.sample_menu(state,rng,mode)
            payload=make_payload(state,menu,history[-6:],variant,{'step':step,'decisions':maxsteps,'rerolls':rerolls,'reroll_total':8,'streak':streak,'reroll_streak':3})
            raw=read('raw/'+ep['id']+f'__s{step:03d}.json')
            assert raw['request']==payload,'Request differs from frozen mechanics'
            label=raw['response']['answers']['answer']['choice'];action=menu[label]
            assert action.serial()==row['action'] and label==row['choice']
            before=state;state=c.apply(state,action)
            assert c.solution(state)==root and c.freeze(row['after_ast'])==state
            d=c.distance(state);assert row['D_before']==c.distance(before) and row['D_after']==d
            if action.kind=='reroll':streak+=1;rerolls+=1
            else:streak=0
            if action.kind=='declare_solved':premature+=1
            if action.kind not in ('reroll','declare_solved'):visits[c.signature(state)]+=1
            if d<best:best=d;lastbest=step
            if c.solved(state):terminal='solved'
            elif streak>=3:terminal='cutoff_reroll_streak'
            elif rerolls>=8:terminal='cutoff_reroll_total'
            elif visits[c.signature(state)]>=3:terminal='cutoff_repeated_state'
            elif premature>=2:terminal='cutoff_premature_completion'
            elif step-lastbest>=stagnation:terminal='cutoff_stagnation'
            elif step>=maxsteps:terminal='cutoff_decisions'
            assert terminal==row['status']
            history.append({'action':c.describe(before,action),'result':c.equation(state)})
            decisions+=1
        assert terminal==ep['status'];totals[terminal]+=1
assert decisions==2747 and sum(totals.values())==144
roll=read('rollout_summary.json');full=read('factorial_rollout_summary.json');audit=read('audit.json')
counts={k:v['solved'] for k,v in full['arms'].items()}
assert list(counts.values())==[13,13,8,4,9,14,11,9],counts
assert full['coverage_separate']['solved']==16
assert audit['requests']==6025 and audit['static_records']==3278
assert Decimal(audit['new_cost_usd'])==Decimal('0.540718080')
assert Decimal(audit['combined_accounted_exposure_usd'])==Decimal('0.608268318')
assert abs(full['factor_main_effects']['structured']['solve_rate_difference']+.265625)<1e-12
effects=full['factor_main_effects']['structured']['case_effects']
assert sum(r['solve_rate_difference']<0 for r in effects)==7
assert sum(r['solve_rate_difference']==0 for r in effects)==1
static=read('static_summary.json')
for condition,expected in [('reverse',.1875),('words',.0625)]:
    result=next(r for r in static['label_sensitivity'] if r['condition']==condition and r['cohort']=='fresh' and r['metric']=='choice_flip')
    assert abs(result['estimate']['mean']-expected)<1e-12
    assert result['estimate']['cases']==16
allcases=read('cases.json')
assert sum(r['origin']=='fresh' for r in allcases)==128
assert sum(r['origin']=='saved' for r in allcases)==24
assert len({r['family'] for r in allcases if r['origin']=='fresh'})==8
headline={'requests':6025,'static_requests':3278,'trajectory_decisions':decisions,'trajectory_attempts':144,
          'families':8,'initial_policy_solved':{'original_random':13,'combined_random':9,'combined_coverage':16},
          'prompt_cells_solved':counts,'structured_main_effect_percentage_points':-26.5625,
          'new_cost_usd':audit['new_cost_usd'],'including_pilot_usd':audit['combined_accounted_exposure_usd'],
          'all_trajectory_statuses':dict(totals),'verification':'Complete requests, choices, roots and cutoff conditions reconstructed offline.'}
(OUT/'headlines.json').write_text(json.dumps(headline,indent=2)+'\n')

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(2,1,figsize=(9,8),constrained_layout=True)
policies=['original_random','combined_random','combined_coverage']
labels=['Original prompt','Combined prompt','Combined + menu coverage'];colors=['#286391','#be6435','#247d65']
episodes=[json.loads(p.read_text()) for p in (OUT/'jev-hypotheses/rollouts').glob('*.json')]
for policy,label,color in zip(policies,labels,colors):
    group=[r for r in episodes if r['policy']==policy];assert len(group)==16
    cap=max(r['max_decisions'] for r in group)
    x=list(range(cap+1));y=[sum(r['status']=='solved' and r['steps']<=t for r in group)/16 for t in x]
    axes[0].step(x,y,where='post',color=color,lw=2.5,label=label)
    axes[1].barh(label,sum(r['status']=='solved' for r in group),color=color)
for i,count in enumerate([13,9,16]):axes[1].text(count+.25,i,f'{count}/16',va='center',fontweight='bold')
axes[0].set(xlabel='Decision allowance (including rerolls)',ylabel='Fraction of all runs solved',ylim=(-.025,1.08),title='Completion as the decision allowance increases')
axes[0].legend(loc='lower right',frameon=False,fontsize=10);axes[0].grid(alpha=.15)
axes[1].set(xlabel='Completed runs',xlim=(0,18),xticks=[0,4,8,12,16],title='Final outcomes: eight equations, two seeds per policy');axes[1].invert_yaxis()
fig.suptitle('Jev choosing algebra actions',fontsize=18,fontweight='bold')
fig.supxlabel('Failures remain in the denominator. Coverage uses an external reference solver.\nThese are 16 runs per policy, not 16 independent equation families.',fontsize=10)
for ext in ['png','svg']:fig.savefig(OUT/f'article-completion.{ext}',dpi=200,bbox_inches='tight')
plt.close(fig)
print(json.dumps(headline,indent=2))
