"""Offline counterfactual scoring of Jev's complete saved choice distributions.

No API calls. Every legal offered action is executed on a copy of the state and
scored using the frozen reference policy. Reroll and completion are excluded.
"""
from collections import Counter
import json
import math
from pathlib import Path
import statistics
from itertools import combinations
import numpy as np
from algebra_engine import *
from analyze_and_plot import plt, save, LEVELS, NAMES, COLORS

ROOT=Path(__file__).resolve().parent
def freeze(x):return tuple(freeze(v) for v in x) if isinstance(x,list) else x
def action_from(obj):return Action(obj['kind'],obj['side'],tuple(obj['path']),obj['i'],obj['j'],F(obj['arg']))
def mean(xs):
    xs=[x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None

def score_distribution(options):
    """options must contain label, probability_raw and D_after. Does not mutate."""
    options=[dict(o) for o in options];mass=sum(o['probability_raw'] for o in options)
    low=min(o['D_after'] for o in options);high=max(o['D_after'] for o in options);span=high-low
    for o in options:
        o['probability_conditional']=o['probability_raw']/mass if mass>0 else None
        o['regret_steps']=o['D_after']-low
        o['normalized_quality']=(high-o['D_after'])/span if span else None
        o['best_offered']=o['D_after']==low
    pairs=[]
    for a,b in combinations(options,2):
        if a['D_after']==b['D_after']:continue
        better,worse=(a,b) if a['D_after']<b['D_after'] else (b,a)
        dp=better['probability_raw']-worse['probability_raw']
        credit=1. if dp>1e-12 else 0. if dp< -1e-12 else .5
        weight=worse['D_after']-better['D_after']
        pairs.append({'better_label':better['label'],'worse_label':worse['label'],
          'reference_gap_steps':weight,'probability_difference':dp,'ranking_credit':credit,
          'weighted_credit':weight*credit})
    informative=span>0 and mass>0
    weight_total=sum(p['reference_gap_steps'] for p in pairs)
    expected_regret=sum(o['probability_conditional']*o['regret_steps'] for o in options) if mass else None
    uniform_regret=statistics.mean(o['regret_steps'] for o in options)
    return {'options':options,'pairs':pairs,'legal_probability_mass':mass,
        'best_D_after':low,'worst_D_after':high,'quality_span_steps':span,
        'informative':informative,'uninformative_reason':None if informative else 'zero_legal_probability' if not mass else 'all_actions_equal_reference_work',
        'expected_regret_steps':expected_regret,'uniform_expected_regret_steps':uniform_regret,
        'expected_D_after':None if expected_regret is None else low+expected_regret,
        'probability_quality':1-expected_regret/span if informative else None,
        'uniform_probability_quality':1-uniform_regret/span if span else None,
        'quality_lift_vs_uniform':(uniform_regret-expected_regret)/span if informative else None,
        'pairwise_alignment':sum(p['weighted_credit'] for p in pairs)/weight_total if informative else None,
        'pairwise_alignment_unweighted':statistics.mean(p['ranking_credit'] for p in pairs) if informative else None,
        'probability_mass_on_best':sum(o['probability_conditional'] for o in options if o['best_offered']) if mass else None,
        'pair_count':len(pairs),'pair_weight_total':weight_total}

def tests():
    base=[{'label':'best','probability_raw':1.,'D_after':2},{'label':'worst','probability_raw':0.,'D_after':6}]
    r=score_distribution(base);assert r['probability_quality']==1 and r['pairwise_alignment']==1 and r['expected_regret_steps']==0
    r=score_distribution([dict(base[0],probability_raw=0),dict(base[1],probability_raw=1)])
    assert r['probability_quality']==0 and r['pairwise_alignment']==0 and r['expected_regret_steps']==4
    r=score_distribution([dict(o,probability_raw=.5) for o in base]);assert r['probability_quality']==.5 and r['pairwise_alignment']==.5
    r=score_distribution([dict(o,D_after=2) for o in base]);assert r['probability_quality'] is None and not r['pairs']
    r=score_distribution([dict(o,probability_raw=0) for o in base]);assert not r['informative'] and r['expected_regret_steps'] is None
    r=score_distribution([dict(base[0],probability_raw=.1),dict(base[1],probability_raw=0)]);assert r['probability_quality']==1 and r['legal_probability_mass']==.1
    print('PASS: perfect/reversed/uniform distributions, equal-quality ties, zero mass, conditional normalization.')

def main():
    tests();episodes=[json.loads(p.read_text()) for p in sorted((ROOT/'episodes').glob('jev_*.json'))]
    records=[]
    for e in episodes:
        state=freeze(e['initial_ast'])
        for r in e['trajectory']:
            raw=json.loads((ROOT/'raw'/f'{e["episode_id"]}_{r["step_i"]:03d}.json').read_text())
            probabilities=raw['response']['answers']['answer']['probabilities'];assert set(probabilities)==set(r['menu'])
            options=[];excluded=[]
            for label,m in r['menu'].items():
                a=action_from(m['action']);p=float(probabilities[label]);assert p>=0
                if a.kind in ('reroll','declare_solved'):
                    excluded.append({'label':label,'kind':a.kind,'probability_raw':p});continue
                after=apply(state,a);assert solution(after)==solution(state)
                d=distance(after)
                options.append({'label':label,'kind':a.kind,'description':m['description'],
                    'probability_raw':p,'D_after':d,'delta_D':distance(state)-d,
                    'equation_after':equation(after),'selected':label==r['label']})
            scored=score_distribution(options)
            assert len(options) in (9,10)
            rec={'episode_id':e['episode_id'],'level':e['level'],'seed':e['seed'],'step_i':r['step_i'],
                 'D_before':distance(state),'equation_before':equation(state),'selected_label':r['label'],
                 'selected_kind':r['action']['kind'],'terminal_status':r['status'],
                 'reroll_probability_raw':probabilities['reroll'],'excluded':excluded,
                 'total_probability_raw':sum(probabilities.values()),**scored}
            rec['probability_mass_on_improving']=sum(o['probability_conditional'] for o in rec['options'] if o['delta_D']>0) if rec['legal_probability_mass'] else None
            rec['selected_action_regret_steps']=next((o['regret_steps'] for o in rec['options'] if o['selected']),None)
            records.append(rec);state=freeze(r['after_ast'])
    with (ROOT/'probability_scores.jsonl').open('w') as f:
        for r in records:f.write(json.dumps(r)+'\n')
    fields=['pairwise_alignment','probability_quality','quality_lift_vs_uniform','expected_regret_steps','uniform_expected_regret_steps','probability_mass_on_best']
    per_episode=[]
    for e in episodes:
        rows=[r for r in records if r['episode_id']==e['episode_id']]
        per_episode.append({'episode_id':e['episode_id'],'level':e['level'],'seed':e['seed'],'status':e['status'],
             'decisions':len(rows),'informative_turns':sum(r['informative'] for r in rows),
             **{field:mean(r[field] for r in rows if r['informative']) for field in fields}})
    summary={'definitions':{
      'quality':'q_a = -[1 + D(T(s,a))]. All offered legal algebra moves cost one decision; ranking therefore uses D_after.',
      'probability':'p_a = reported probability / sum(reported probability on legal algebra moves). Reroll and completion declaration excluded.',
      'pairwise_alignment':'For every pair with unequal D_after: credit 1 if the better move has higher p, 0 if lower, 0.5 if equal. Weight by the absolute difference in D_after and divide by total pair weight.',
      'probability_quality':'1 - sum_a p_a*(D_after_a - min(D_after))/(max(D_after)-min(D_after)). 1 means all conditional mass is on the best offered moves; 0 means all mass on the worst.',
      'expected_regret_steps':'sum_a p_a*(D_after_a - min(D_after)); extra reference work relative to the best offered move.',
      'uniform_baseline':'Identical counterfactual action set; assign equal probability to each legal algebra action. Its pairwise alignment is 0.5. Its probability-quality baseline is menu-dependent.',
      'ties':'Equal reference quality pairs are excluded; equal probabilities on unequal-quality pairs get half credit. All-equal-quality menus and zero legal mass are uninformative and omitted from score means.',
      'interpretation':'Offline alignment with a specified reference policy, not probability calibration, a true target PDF, or guaranteed shortest-path optimality.'},
      'extra_api_calls':0,'extra_cost_usd':0,'turns':len(records),
      'counterfactual_actions_scored':sum(len(r['options']) for r in records),
      'unequal_quality_pairs_scored':sum(r['pair_count'] for r in records),
      'informative_turns':sum(r['informative'] for r in records),
      'uninformative_reasons':dict(Counter(r['uninformative_reason'] for r in records if not r['informative'])),
      'raw_probability_sum_range':[min(r['total_probability_raw'] for r in records),max(r['total_probability_raw'] for r in records)],
      'turn_weighted_means':{field:mean(r[field] for r in records if r['informative']) for field in fields},
      'episode_weighted_means':{field:mean(e[field] for e in per_episode) for field in fields},
      'levels':{},'episodes':per_episode}
    for level in LEVELS:
        rows=[r for r in records if r['level']==level and r['informative']];es=[e for e in per_episode if e['level']==level]
        summary['levels'][level]={'informative_turns':len(rows),'total_turns':sum(r['level']==level for r in records),
          'turn_weighted_means':{field:mean(r[field] for r in rows) for field in fields},
          'episode_weighted_means':{field:mean(e[field] for e in es) for field in fields},
          'mean_reroll_probability_raw':mean(r['reroll_probability_raw'] for r in records if r['level']==level)}
    (ROOT/'probability_summary.json').write_text(json.dumps(summary,indent=2))
    figures(records,episodes,summary);viewer(records,episodes);report(summary,records)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('episodes','definitions')},indent=2))

def figures(records,episodes,summary):
    fig,axs=plt.subplots(2,1,figsize=(11,7.5),sharex=True);fig.subplots_adjust(top=.83,bottom=.15,hspace=.26,right=.95)
    fig.suptitle('Does the entire choice distribution favour better algebra moves?',y=.97,fontweight='bold')
    fig.text(.5,.915,'Jev 1.13 · prespecified seed 0 · all offered legal moves scored offline · reroll/completion excluded',ha='center',fontsize=10)
    for ax,field,title in zip(axs,['probability_quality','pairwise_alignment'],['Probability-weighted action quality','Pairwise ranking alignment, weighted by reference-step gap']):
        for level in LEVELS:
            rows=[r for r in records if r['level']==level and r['seed']==0]
            ax.plot([r['step_i'] for r in rows],[float('nan') if r[field] is None else r[field] for r in rows],color=COLORS[level],label=NAMES[level],lw=1.5,alpha=.9)
        ax.set_title(title,fontsize=11);ax.set_ylim(-.03,1.05);ax.set_ylabel('Score (higher is better)')
    axs[1].axhline(.5,color='#777777',ls='--',lw=.9);axs[1].text(40,.515,'Equal-probability ranking baseline = 0.5',fontsize=8,color='#555555')
    axs[0].legend(loc='lower right',ncol=3,fontsize=9);axs[1].set_xlabel('Decision step i (score evaluates the menu presented at this step)')
    fig.text(.125,.045,'Top: 1 = all conditional mass on best offered moves; 0 = all on worst. Bottom: 1 = correct order for every unequal-quality pair.\nD is reference-policy work, not shortest-path distance. These are action-quality scores, not calibrated probabilities of correctness.',fontsize=9)
    save(fig,'07_probability_alignment_trajectories')

    fig,ax=plt.subplots(figsize=(13,8.5));fig.subplots_adjust(left=.15,right=.92,top=.85,bottom=.15)
    fig.suptitle('Probability-weighted quality at every Jev decision',y=.97,fontweight='bold')
    fig.text(.5,.916,'All 24 runs · brighter cells put more probability on lower-work actions · × marks an actual cutoff',ha='center')
    ordered=sorted(episodes,key=lambda e:(LEVELS.index(e['level']),e['seed']));maxsteps=max(e['steps'] for e in ordered)
    matrix=np.full((24,maxsteps),np.nan)
    lookup={(r['episode_id'],r['step_i']):r for r in records}
    for i,e in enumerate(ordered):
        for step in range(1,e['steps']+1):
            value=lookup[(e['episode_id'],step)]['probability_quality']
            if value is not None:matrix[i,step-1]=value
    cmap=plt.get_cmap('viridis').copy();cmap.set_bad('#eeeeee')
    im=ax.imshow(matrix,aspect='auto',interpolation='nearest',cmap=cmap,vmin=0,vmax=1,extent=(.5,maxsteps+.5,23.5,-.5))
    for i,e in enumerate(ordered):
        if e['status']!='solved':ax.scatter(e['steps'],i,marker='X',color='#E64B35',edgecolor='white',s=85,linewidth=.7)
    ax.set_yticks(range(24),[f'{NAMES[e["level"]]} / {e["seed"]}' for e in ordered],fontsize=9)
    ax.set_xlabel('Decision step i');ax.grid(False)
    for y in [7.5,15.5]:ax.axhline(y,color='white',lw=2)
    cb=fig.colorbar(im,ax=ax,pad=.02,fraction=.025);cb.set_label('Probability-weighted action quality')
    fig.text(.15,.065,'Gray = run already ended, or menu uninformative; never treated as zero quality. Reroll/completion probability is removed\nand legal-move probabilities are renormalized. This evaluates the conditional distribution even on turns when Jev chose reroll.',fontsize=9)
    save(fig,'08_probability_quality_all_turns')

    fig,axs=plt.subplots(1,3,figsize=(13,4.8));fig.subplots_adjust(top=.79,bottom=.24,wspace=.30)
    fig.suptitle('Alignment across runs: each point is one episode',y=.97,fontweight='bold')
    fig.text(.5,.89,'Mean of informative turns within each episode; black diamonds average episodes equally.',ha='center',fontsize=10)
    for ax,field,title in zip(axs,['pairwise_alignment','probability_quality','quality_lift_vs_uniform'],['Pairwise alignment','Probability-weighted quality','Quality advantage over uniform']):
        for i,l in enumerate(LEVELS):
            es=sorted([e for e in summary['episodes'] if e['level']==l],key=lambda e:e['seed'])
            ys=[e[field] for e in es if e[field] is not None];x=i+np.linspace(-.12,.12,len(ys))
            ax.scatter(x,ys,color=COLORS[l],s=33,alpha=.8);ax.scatter(i,statistics.mean(ys),marker='D',color='#222222',s=52,zorder=5)
        ax.set_title(title,fontsize=11);ax.set_xticks(range(3),[NAMES[l] for l in LEVELS]);ax.set_xlim(-.5,2.5)
        if field=='pairwise_alignment':ax.axhline(.5,color='#777777',ls='--',lw=.9);ax.set_ylim(0,1.05)
        elif field=='probability_quality':ax.set_ylim(0,1.05)
        else:ax.axhline(0,color='#777777',ls='--',lw=.9)
    fig.text(.5,.065,'Uniform uses the identical offered legal actions at each observed state. Its quality baseline varies with the menu; its pairwise score is 0.5.\nThree fixed equations, eight seeds each. Descriptive comparison only; these scores do not establish general domain mastery.',ha='center',fontsize=9)
    save(fig,'09_probability_alignment_by_run')

def viewer(records,episodes):
    groups=[]
    for e in sorted(episodes,key=lambda e:(LEVELS.index(e['level']),e['seed'])):
        groups.append({'name':f'{e["level"]} / seed {e["seed"]} — {e["status"]}',
                       'rows':[r for r in records if r['episode_id']==e['episode_id']]})
    data=json.dumps(groups).replace('</','<\\/')
    template='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jev probabilities and action quality</title><style>body{font:16px system-ui;max-width:1200px;margin:32px auto;padding:0 20px;color:#18212d;background:#f8fafc}select{font:inherit;padding:8px}input{width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:white;border:1px solid #dce3ea;border-radius:8px;padding:16px}.metrics{display:flex;flex-wrap:wrap;gap:10px}.card{border:1px solid #dce3ea;background:white;border-radius:8px;padding:12px;min-width:145px}.number{font-size:24px;font-weight:650}table{width:100%;border-collapse:collapse;background:white;font-size:14px}th,td{text-align:left;vertical-align:top;padding:9px;border-bottom:1px solid #dde3ea}.best{background:#e6f4ec}.selected{outline:2px solid #0072b2;outline-offset:-2px}.small{color:#516174;font-size:14px}summary{cursor:pointer;font-weight:650}h1{font-size:30px}.wrap{overflow:auto}</style>
<h1>Score the complete action distribution</h1><p>Each candidate was executed on a copy of the equation and scored with the frozen symbolic reference solver. This viewer makes no model calls.</p><label>Run <select id="run"></select></label><p><label>Decision <strong id="step"></strong><input id="slider" type="range" min="1" value="1"></label></p><div id="metrics" class="metrics"></div><h2>Equation before the decision</h2><pre id="equation"></pre><p id="selection"></p>
<h2>Every legal candidate</h2><p class="small">Green = best offered reference workload. Blue outline = selected. Lower D-after and regret are better. Conditional probabilities renormalize after removing reroll and completion. Actions are sorted by D-after, then probability.</p><div class="wrap"><table><thead><tr><th>Action</th><th>Reported p</th><th>Conditional p</th><th>D after</th><th>Regret steps</th><th>Operation</th></tr></thead><tbody id="actions"></tbody></table></div><p class="small" id="excluded"></p>
<details><summary>Every pair contributing to the ranking score</summary><div class="wrap"><table><thead><tr><th>Better action</th><th>Worse action</th><th>D gap / weight</th><th>p(better) − p(worse)</th><th>Credit</th></tr></thead><tbody id="pairs"></tbody></table></div></details><p class="small">Pairwise alignment weights correct probability orderings by the reference-step gap; reversed pairs get 0 and equal probabilities get 0.5. Equal-quality pairs are excluded. Quality = 1 − expected regret / offered quality range. These are utility-alignment metrics, not probability calibration or a unique true PDF. The reference solver is deterministic, but does not guarantee the shortest path.</p>
<script>const data=__DATA__,$=id=>document.getElementById(id);const fmt=(v,d=3)=>v==null?'N/A':v.toFixed(d);for(const [i,g] of data.entries()){const o=document.createElement('option');o.value=i;o.textContent=g.name;$('run').appendChild(o)}
function render(){const g=data[+$('run').value],r=g.rows[+$('slider').value-1];$('step').textContent=`${r.step_i} / ${g.rows.length}`;$('equation').textContent=r.equation_before;$('selection').textContent=`Selected: ${r.selected_label} (${r.selected_kind}). Remaining reference work before action: ${r.D_before}. Status after action: ${r.terminal_status??'continuing'}.`;$('metrics').replaceChildren();for(const [title,value] of [['Pairwise alignment',fmt(r.pairwise_alignment)],['Probability quality',fmt(r.probability_quality)],['Uniform quality',fmt(r.uniform_probability_quality)],['Expected regret',fmt(r.expected_regret_steps)+' steps'],['Reroll probability',fmt(r.reroll_probability_raw)],['Legal move mass',fmt(r.legal_probability_mass)]]){const box=document.createElement('div');box.className='card';const label=document.createElement('div');label.textContent=title;const v=document.createElement('div');v.className='number';v.textContent=value;box.append(label,v);$('metrics').appendChild(box)}$('actions').replaceChildren();for(const o of [...r.options].sort((a,b)=>a.D_after-b.D_after||b.probability_raw-a.probability_raw)){const tr=document.createElement('tr');tr.className=(o.best_offered?'best ':'')+(o.selected?'selected':'');for(const value of [o.label,fmt(o.probability_raw),fmt(o.probability_conditional),o.D_after,o.regret_steps,o.description]){const td=document.createElement('td');td.textContent=value;tr.appendChild(td)}$('actions').appendChild(tr)}$('excluded').textContent='Excluded: '+r.excluded.map(o=>`${o.label} (${o.kind}), reported p=${fmt(o.probability_raw)}`).join('; ')+'. '+(r.informative?'':'This turn is uninformative: '+r.uninformative_reason);$('pairs').replaceChildren();for(const p of r.pairs){const tr=document.createElement('tr');for(const value of [p.better_label,p.worse_label,p.reference_gap_steps,fmt(p.probability_difference),p.ranking_credit]){const td=document.createElement('td');td.textContent=value;tr.appendChild(td)}$('pairs').appendChild(tr)}}$('run').onchange=()=>{$('slider').max=data[+$('run').value].rows.length;$('slider').value=1;render()};$('slider').oninput=render;$('run').onchange();</script></html>'''
    (ROOT/'probability_viewer.html').write_text(template.replace('__DATA__',data))

def report(summary,records):
    lines=['# Scoring the whole Jev action distribution','',
       'This follow-up reuses all saved responses from the algebra experiment. **No additional API calls or model charges.** It evaluates every offered legal algebra action, including actions Jev did not choose.','',
       f'Scored {summary["turns"]} turns, {summary["counterfactual_actions_scored"]:,} counterfactual moves, and {summary["unequal_quality_pairs_scored"]:,} unequal-quality action pairs. Informative turns: {summary["informative_turns"]}/{summary["turns"]}.','',
       '## Two complementary scores','',
       'For each state s and legal candidate a, execute a on a copy and compute `d_a = D(T(s,a))`. D is the frozen reference solver’s remaining step count. If counting the current action too, its one-step lookahead cost is `1 + d_a`; that common +1 does not change candidate rankings or regret.','',
       'Remove reroll and completion declarations, then normalize the remaining reported probability mass to sum to one. The excluded mass is kept separately in the data and viewer. This is a **conditional** evaluation: it does not decide whether Jev should have rerolled. A turn with zero probability on legal moves cannot be scored this way.','',
       '**1. Pairwise ranking alignment.** For each pair with different remaining work, identify the better move. Award 1 if it has higher probability, 0 if lower, and 0.5 if tied. Weight the pair by the absolute difference in remaining reference steps, then divide by total weight. Equal-quality pairs contribute nothing. A score of 1 correctly orders every unequal-quality pair; 0 reverses every pair; equal probabilities give 0.5. It evaluates ranking, not probability calibration.','',
       '```text\nPairAlignment = Σ_pairs |d_a − d_b| × ordering_credit(a,b) / Σ_pairs |d_a − d_b|\n```','',
       '**2. Probability-weighted action quality.** Let `d_best` and `d_worst` be the smallest and largest reference workload among this menu’s legal moves. Expected regret is the extra reference work under Jev’s conditional distribution compared with choosing the best offered move.','',
       '```text\nExpectedRegret = Σ_a p_a × (d_a − d_best)\nProbabilityQuality = 1 − ExpectedRegret / (d_worst − d_best)\n```','',
       'Quality 1 puts all probability on best offered moves; quality 0 puts it all on worst offered moves. Unlike a ranking score, this responds to how much probability is assigned. Menus with identical action quality are uninformative for both normalized scores. The data also retains raw expected regret in reference-step units.','',
       'These metrics answer different questions. A distribution can concentrate almost all mass on a good move while poorly ordering tiny-probability alternatives. Conversely, it can rank moves correctly while spreading considerable mass onto poor ones. They should be displayed together rather than blended with an arbitrary weight.','',
       '## Results','',
       'Each row below first averages informative turns within a run and then averages the eight runs equally. This prevents a long, inefficient run from dominating the summary.','',
       '| Difficulty | Informative / total turns | Pair alignment | Probability quality | Quality lift vs uniform | Expected regret, steps |',
       '|---|---:|---:|---:|---:|---:|']
    for l in LEVELS:
        s=summary['levels'][l];m=s['episode_weighted_means']
        lines.append(f'| {NAMES[l]} | {s["informative_turns"]}/{s["total_turns"]} | {m["pairwise_alignment"]:.3f} | {m["probability_quality"]:.3f} | {m["quality_lift_vs_uniform"]:+.3f} | {m["expected_regret_steps"]:.3f} |')
    m=summary['episode_weighted_means']
    lines += [f'| All runs, equal weight | {summary["informative_turns"]}/{summary["turns"]} | {m["pairwise_alignment"]:.3f} | {m["probability_quality"]:.3f} | {m["quality_lift_vs_uniform"]:+.3f} | {m["expected_regret_steps"]:.3f} |','',
       'Uniform comparison uses exactly the same menu and state, with equal probability on legal moves. Its pairwise ranking score is always 0.5; its probability-quality score varies with the offered action costs. This is a stronger matched-state comparison than comparing independent random-controller trajectories.','',
       'Expected regret is a diagnostic expectation under the returned conditional distribution. It is not a claim that Jev sampled actions from that distribution or actually wasted that many executed steps.','',
       '![Distribution trajectories](figures/07_probability_alignment_trajectories.png)','',
       '![All decision quality scores](figures/08_probability_quality_all_turns.png)','',
       '![Per-run alignment](figures/09_probability_alignment_by_run.png)','',
       '## What this reveals beyond the chosen action','',
       'An illustrative turn selected after analysis is **medium, seed 0, decision 13**. Jev selected reroll, and no offered algebra action immediately reduced D. But among the remaining legal choices, it assigned approximately **67.9%** conditional probability to a multiplication that would increase reference work from **8 to 11**. Several alternatives would have kept D at 8. Its probability-quality score was **0.239**, and its pairwise alignment was **0.000**: it reversed every unequal-quality comparison in that menu.','',
       'The final answer alone would miss this: that run eventually solved the equation. The actual reroll avoided executing the poorly ranked multiplication. The conditional scoring therefore exposes a preference failure without misreporting it as an executed algebra error.','',
       '## Interpretation and limits','',
       '- D is a deterministic reference-policy workload, not guaranteed minimal remaining moves. Calling this alignment with a true minimal-move surface would overstate what was measured. A shortest-path oracle would be a separate experiment requiring a bounded state/action graph or another proven optimality method.',
       '- Deterministic action costs do not define a unique correct probability distribution. A softmax target would require a chosen temperature and assumptions about exploration. Therefore these results measure utility alignment and expected regret, **not calibration against a true PDF**.',
       '- Reroll and completion mass is removed. If Jev assigns 99% to reroll and the remaining 1% to a good legal move, its conditional action-quality score can be high. The excluded mass must be inspected alongside that score.',
       '- Returned probabilities are recorded at limited precision; many zero/equal values create pairwise ties. We score those ties explicitly rather than inventing extra precision. Raw probability sums range from '+f'{summary["raw_probability_sum_range"][0]:.3f} to {summary["raw_probability_sum_range"][1]:.3f}'+', so conditional normalization also removes rounding-related sum differences.',
       '- The normalization range depends on the menu. An extremely poor distractor can inflate normalized quality; raw expected regret and the matched uniform comparison are included so this is visible.',
       '- Pairwise ranking treats two zero-probability alternatives as tied, even if one is better. Thus a perfectly optimal one-hot decision can have less than perfect ranking alignment over the rest of its menu. This is why probability quality is the main measure of useful probability allocation.',
       '- Counterfactual evaluation scores only offered moves at the states actually visited. It does not claim those states represent the whole algebra domain. Three fixed equations remain a small, heavily scaffolded evaluation.',
       '- All-equal-quality menus and zero-legal-mass turns are omitted from normalized-score averages, not assigned zero. Counts are retained. Uninformative reasons: `'+json.dumps(summary['uninformative_reasons'])+'`.','',
       '## Inspect or reproduce','',
       '- `probability_viewer.html`: every turn, every counterfactual action, probability, regret, and contributing pair.',
       '- `probability_scores.jsonl`: one record per turn with all candidate-level and pair-level scores.',
       '- `probability_summary.json`: formulas, per-run/per-difficulty statistics, turn-weighted and episode-weighted rollups.',
       '- `score_action_probabilities.py`: recreate the analysis, viewer and figures with `python score_action_probabilities.py`; it makes no model calls.',
       '- Figures 07–09 are saved as 300 dpi PNG and scalable SVG.','']
    (ROOT/'PROBABILITY_REPORT.md').write_text('\n'.join(lines))

if __name__=='__main__':main()
