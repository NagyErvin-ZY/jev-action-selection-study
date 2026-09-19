"""Rebuild field-note figures offline from saved evidence. Never edits frozen inputs.

Usage: python tools/build_field_note_figures.py --evidence-root reproduced --output figures
The input is the output of reproduce.py. Source hashes and plotted data are exported.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import statistics
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, MaxNLocator

BLUE='#1766a3'; ORANGE='#b45419'; GREEN='#23795d'; GRAY='#6b7280'; INK='#202731'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.titlesize':12,
    'axes.labelsize':11,'axes.spines.top':False,'axes.spines.right':False,
    'axes.edgecolor':'#c6cbd1','text.color':INK,'axes.labelcolor':INK,
    'xtick.color':INK,'ytick.color':INK,'savefig.facecolor':'white','svg.fonttype':'none'})

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--evidence-root',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); root=args.evidence_root.resolve(); out=args.output.resolve()
    assert not out.is_relative_to(root/'jev-algebra') and not out.is_relative_to(root/'jev-hypotheses')
    out.mkdir(parents=True,exist_ok=True); hashes={}
    def read(p):
        b=p.read_bytes(); hashes[str(p.relative_to(root))]=hashlib.sha256(b).hexdigest(); return json.loads(b)
    pilot=root/'jev-algebra'; campaign=root/'jev-hypotheses'
    sys.path.insert(0,str(pilot))
    import algebra_engine as eng
    from score_action_probabilities import score_distribution, action_from, freeze
    episodes=[read(p) for p in sorted((pilot/'episodes').glob('jev_*.json'))]
    records=[]
    # Recompute all counterfactual costs from the exact state and original response.
    for e in episodes:
        state=freeze(e['initial_ast']); exact_root=eng.solution(state)
        for step in e['trajectory']:
            raw=read(pilot/'raw'/f'{e["episode_id"]}_{step["step_i"]:03d}.json')
            probs=raw['response']['answers']['answer']['probabilities']
            assert set(probs)==set(step['menu'])
            assert raw['response']['answers']['answer']['choice']==step['label']
            options=[]; excluded=[]
            for label,entry in step['menu'].items():
                action=action_from(entry['action']); p=float(probs[label]); assert p>=0
                if action.kind in ('reroll','declare_solved'):
                    excluded.append(dict(label=label,kind=action.kind,probability_raw=p));continue
                after=eng.apply(state,action); assert eng.solution(after)==exact_root
                options.append(dict(label=label,kind=action.kind,description=entry['description'],
                    action=entry['action'],probability_raw=p,D_after=eng.distance(after),selected=label==step['label']))
            score=score_distribution(options)
            records.append(dict(episode_id=e['episode_id'],level=e['level'],seed=e['seed'],
                step_i=step['step_i'],D_before=eng.distance(state),equation=eng.equation(state),
                selected_label=step['label'],excluded=excluded,**score))
            state=freeze(step['after_ast']); assert eng.solution(state)==exact_root
            assert eng.distance(state)==step['reference_steps_after']
    assert len(episodes)==24 and len(records)==689
    assert sum(len(r['options']) for r in records)==6590
    assert sum(r['pair_count'] for r in records)==20915
    stored=[json.loads(s) for s in (pilot/'probability_scores.jsonl').read_text().splitlines()]
    lookup={(r['episode_id'],r['step_i']):r for r in stored}
    fields=['probability_quality','pairwise_alignment','expected_regret_steps','uniform_expected_regret_steps']
    for r in records:
        previous=lookup[r['episode_id'],r['step_i']]
        for f in fields: assert math.isclose(r[f],previous[f],abs_tol=1e-12)
    per_run={e['episode_id']:[r for r in records if r['episode_id']==e['episode_id']] for e in episodes}
    means={f:statistics.mean(statistics.mean(r[f] for r in rs if r['informative']) for rs in per_run.values()) for f in fields}
    assert round(means['probability_quality'],3)==.845
    assert round(means['pairwise_alignment'],3)==.705
    assert round(means['expected_regret_steps'],3)==.572
    assert round(means['uniform_expected_regret_steps'],3)==1.971
    def save(fig,name):
        for ext in ['png','svg']: fig.savefig(out/f'{name}.{ext}',dpi=220,bbox_inches='tight')
        plt.close(fig)
    def grid(ax): ax.grid(axis='y',alpha=.16); ax.set_axisbelow(True)

    # Figure 1: same post-hoc illustrative turn documented in the original report.
    r=next(r for r in records if r['episode_id']=='jev_medium_00' and r['step_i']==13)
    assert r['selected_label']=='reroll' and r['pairwise_alignment']==0
    labels=[]
    for o in r['options']:
        a=o['action']; labels.append({'multiply':f'Multiply both sides by {a["arg"]}',
            'shift_constant':f'Add {a["arg"]} to both sides',
            'shift_variable':f'Add ({a["arg"]})x to both sides'}[a['kind']])
    labels+=['Declare completion','Reroll (selected)']
    opts=r['options']+r['excluded']; y=np.arange(len(opts))
    fig,(ax,bx)=plt.subplots(1,2,figsize=(9.5,8),gridspec_kw={'width_ratios':[3,1]},sharey=True)
    fig.subplots_adjust(left=.34,right=.96,top=.80,bottom=.25,wspace=.28)
    fig.suptitle('A reroll can hide a poorly ranked algebra menu',x=.04,ha='left',y=.99,fontweight='bold',fontsize=16)
    fig.text(.04,.935,'Pilot: medium equation, seed 0, decision 13 | chosen after analysis',fontsize=10)
    fig.text(.04,.887,'18x - 66 + 12(-x/3 - 1/3) = 0'+'   |   reference cost before: 8',fontsize=12)
    colors=[ORANGE if o['D_after']>r['D_before'] else BLUE for o in r['options']]+[GRAY,GRAY]
    ax.barh(y,[o['probability_raw'] for o in opts],color=colors,height=.62)
    ax.set_yticks(y,labels,fontsize=10);ax.invert_yaxis();ax.set_xlim(0,.54)
    ax.xaxis.set_major_formatter(PercentFormatter(1));ax.set_xlabel('Reported probability')
    ax.axhline(8.5,color='#adb5bd',lw=1)
    for i,o in enumerate(opts): ax.text(o['probability_raw']+.008,i,f'{100*o["probability_raw"]:.0f}%',va='center',fontsize=10)
    bx.set_xlim(0,1);bx.set_xticks([]);bx.tick_params(left=False,labelleft=False)
    for spine in bx.spines.values():spine.set_visible(False)
    bx.set_title('Cost after\n(lower is better)',fontsize=10)
    for i,o in enumerate(opts):bx.text(.5,i,str(o['D_after']) if 'D_after' in o else 'excluded',ha='center',va='center',fontsize=11)
    fig.text(.04,.035,f'Conditional algebra scores: quality {r["probability_quality"]:.3f} | pairwise alignment {r["pairwise_alignment"]:.3f}\nExpected reference regret: {r["expected_regret_steps"]:.3f} moves. Algebra probability mass: 53%.\nOrange: increases reference cost. Blue: unchanged. No offered algebra move reduced it.',fontsize=10,linespacing=1.5)
    save(fig,'decision-distribution')

    # Figure 2: all runs, no confidence intervals pretending that 24 runs are 24 problems.
    fig,axs=plt.subplots(3,1,figsize=(8,9));fig.subplots_adjust(left=.16,right=.96,top=.88,bottom=.10,hspace=.66)
    fig.suptitle('The full distribution carries useful signal',x=.04,ha='left',y=.985,fontweight='bold',fontsize=16)
    fig.text(.04,.91,'Pilot: three fixed equations, eight seeds each. Each dot is one run.\nMeans weight runs equally after averaging their informative turns.',fontsize=10,linespacing=1.5)
    level_names=['simple','medium','unholy']; cols=[BLUE,GREEN,ORANGE]
    for ax,field,title in zip(axs,fields[:3],['Probability quality (higher is better)','Pairwise alignment (higher is better)','Expected reference regret (lower is better)']):
        for i,level in enumerate(level_names):
            es=sorted([e for e in episodes if e['level']==level],key=lambda e:e['seed'])
            ys=[statistics.mean(r[field] for r in per_run[e['episode_id']] if r['informative']) for e in es]
            ax.scatter(i+np.linspace(-.12,.12,8),ys,color=cols[i],s=29,alpha=.8)
            ax.scatter(i,statistics.mean(ys),marker='D',s=54,color=INK,zorder=5)
            uf='uniform_expected_regret_steps' if field=='expected_regret_steps' else 'uniform_probability_quality'
            baseline=.5 if field=='pairwise_alignment' else statistics.mean(statistics.mean(r[uf] for r in per_run[e['episode_id']] if r['informative']) for e in es)
            ax.plot([i-.24,i+.24],[baseline,baseline],color=GRAY,ls='--',lw=1.5)
        ax.set_title(title,loc='left');ax.set_xticks(range(3),['Simple','Medium','Complex']);ax.set_xlim(-.45,2.45);grid(ax)
        if field!='expected_regret_steps':ax.set_ylim(-.03,1.05)
        else: ax.set_ylim(bottom=0);ax.set_ylabel('Reference moves')
    fig.text(.04,.02,'Black diamond: mean. Dashed: equal probability on the same offered algebra actions.\nScores condition on algebra actions; reroll and completion mass are excluded. No population intervals.',fontsize=10)
    save(fig,'distribution-summary')

    # Figure 3: a documented example and the sole failed medium run; explicit selection rule.
    chosen=['jev_medium_00','jev_medium_05'];fig,axs=plt.subplots(4,1,figsize=(8,11),sharex=True)
    fig.subplots_adjust(left=.14,right=.96,top=.86,bottom=.11,hspace=.39)
    fig.suptitle('Preferences and progress over the same run',x=.035,ha='left',y=.99,fontweight='bold',fontsize=16)
    fig.text(.035,.935,'Medium pilot equation: seed 0 (solved) and seed 5 (reroll cutoff).\nSeed 0 contains the example above; seed 5 is its only failed repeat.',fontsize=10,linespacing=1.5)
    plotted={}
    for eid,color in zip(chosen,[BLUE,ORANGE]):
        e=next(e for e in episodes if e['episode_id']==eid)
        if e['status']=='cutoff_reroll_streak': assert all(s['action']['kind']=='reroll' for s in e['trajectory'][-3:])
        if e['status']=='solved': assert e['final_reference_steps']==0
        rs=per_run[eid];t=[r['step_i'] for r in rs]
        x=[0]+t;d=[e['initial_reference_steps']]+[s['reference_steps_after'] for s in e['trajectory']]
        label=f'Seed {e["seed"]}: '+('solved' if e['status']=='solved' else 'cutoff')
        axs[0].step(x,d,where='post',color=color,label=label,lw=1.8)
        axs[0].plot(x,np.minimum.accumulate(d),color=color,ls=':',alpha=.8)
        axs[1].plot(t,[r['probability_quality'] for r in rs],color=color,lw=1.5)
        axs[1].plot(t,[r['pairwise_alignment'] for r in rs],color=color,ls=':',lw=1.3)
        cum=np.cumsum([r['expected_regret_steps'] for r in rs]);axs[2].plot([0]+t,[0]+list(cum),color=color,lw=1.8)
        reroll=[next(o['probability_raw'] for o in r['excluded'] if o['kind']=='reroll') for r in rs]
        axs[3].plot(t,reroll,color=color,lw=1.5)
        for j,val in enumerate([d[-1],rs[-1]['probability_quality'],cum[-1],reroll[-1]]):
            axs[j].scatter(t[-1],val,marker='o' if e['status']=='solved' else 'X',s=65,color=color,zorder=6)
        if e['status']!='solved':
            for ax in axs:ax.axvline(t[-1],color=color,ls='--',alpha=.45)
        plotted[eid]=dict(decisions=t,reference_cost=d,cumulative_expected_regret=list(cum),reroll_probability=reroll,status=e['status'])
    for ax in axs:grid(ax);ax.set_xlim(0,24);ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    axs[0].set_title('Remaining reference cost | dotted: best so far',loc='left');axs[0].set_ylabel('Moves');axs[0].set_ylim(bottom=0);axs[0].legend(fontsize=10,loc='upper right')
    axs[1].set_title('Algebra scores | solid: quality; dotted: pairwise alignment',loc='left',fontsize=11);axs[1].set_ylim(-.05,1.05);axs[1].set_ylabel('Score')
    axs[2].set_title('Cumulative expected reference regret',loc='left');axs[2].set_ylabel('Reference moves');axs[2].set_ylim(bottom=0)
    axs[3].set_title('Reported reroll probability',loc='left');axs[3].set_ylim(-.05,1.05);axs[3].yaxis.set_major_formatter(PercentFormatter(1));axs[3].set_xlabel('Decision number (0 is the initial state)')
    fig.text(.035,.025,'X and dashed vertical line: actual cutoff after three consecutive rerolls. Lines stop at termination.\nCumulative regret sums conditional expectations, including reroll turns. It is not executed wasted work.\nReference cost follows a fixed policy; it is not a proven shortest-path distance.',fontsize=9.5,linespacing=1.5)
    save(fig,'progress-and-preferences')

    # Full pilot gallery preserves the user's original three-level trajectory question.
    for level in level_names:
        es=sorted([e for e in episodes if e['level']==level],key=lambda e:e['seed'])
        fig,axs=plt.subplots(8,2,figsize=(12,19));fig.subplots_adjust(hspace=.65,top=.95,bottom=.05,wspace=.24)
        fig.suptitle(f'All {"complex" if level == "unholy" else level} pilot runs: reference cost and distribution scores',fontsize=16,fontweight='bold')
        for row,e in enumerate(es):
            rs=per_run[e['episode_id']];t=[r['step_i'] for r in rs];a,b=axs[row]
            a.step([0]+t,[e['initial_reference_steps']]+[s['reference_steps_after'] for s in e['trajectory']],where='post',color=BLUE)
            b.plot(t,[r['probability_quality'] for r in rs],color=BLUE,label='Quality')
            b.plot(t,[r['pairwise_alignment'] for r in rs],color=GREEN,ls=':',label='Pairwise')
            b.plot(t,[next(o['probability_raw'] for o in r['excluded'] if o['kind']=='reroll') for r in rs],color=GRAY,alpha=.6,label='Reroll p')
            a.set_title(f'Seed {e["seed"]}: {e["status"]}',loc='left',fontsize=10);a.set_ylim(bottom=0);b.set_ylim(-.05,1.05)
            for ax in [a,b]:
                grid(ax);ax.set_xlim(0,max(3,e['steps']+1));ax.xaxis.set_major_locator(MaxNLocator(integer=True))
                if e['status']!='solved':ax.axvline(e['steps'],color=ORANGE,ls='--')
            if row==0:b.legend(fontsize=9,ncol=3)
            if row==7:a.set_xlabel('Decision number');b.set_xlabel('Decision number')
        fig.text(.05,.015,'Left: reference-policy completion cost (moves). Right: conditional algebra scores and raw reroll probability.\nDashed vertical lines mark cutoffs. Runs are repeated seeds on one equation, not independent problems.',fontsize=11)
        save(fig,'all-pilot-'+('complex' if level=='unholy' else level))

    # Figure 4 keeps the local and trajectory populations visibly separate.
    static=read(campaign/'static_summary.json')
    effects=[next(x for x in static['paired_effects'] if x['cohort']=='fresh' and x['policy']==p and x['metric']=='probability_quality' and x['treatment']=='combined') for p in ['reference','shallow_first','cleanup_first']]
    runs=[read(p) for p in sorted((campaign/'rollouts').glob('*.json'))]
    # Read schema rather than assume filename labels describe outcomes.
    counts={p:sum(e['status']=='solved' for e in runs if e['policy']==p) for p in ['original_random','combined_random','combined_coverage']}
    assert list(counts.values())==[13,9,16],counts
    assert all(sum(e['policy']==p for e in runs)==16 for p in counts)
    fig,(ax,bx)=plt.subplots(2,1,figsize=(8,8));fig.subplots_adjust(left=.30,right=.95,top=.83,bottom=.13,hspace=.7)
    fig.suptitle('Local score gains did not ensure more completions',x=.035,ha='left',y=.99,fontweight='bold',fontsize=15)
    fig.text(.035,.91,'Frozen main campaign. These panels evaluate different populations.\nTop: 128 fixed states, eight families. Bottom: eight equations, two seeds.',fontsize=10,linespacing=1.5)
    for i,e in enumerate(effects):
        m=e['effect']['mean'];lo,hi=e['effect']['ci95'];ax.errorbar(m,i,xerr=[[m-lo],[hi-m]],fmt='o',color=BLUE,capsize=4)
    ax.axvline(0,color=GRAY,lw=1);ax.set_yticks(range(3),['Original reference','Shallow-first','Cleanup-first']);ax.invert_yaxis()
    ax.set_title('Combined prompt minus original: probability quality',loc='left',fontsize=10)
    ax.set_xlabel('Score difference; exploratory 95% family-bootstrap interval',fontsize=9)
    ax.set_xlim(-.025,.075);ax.grid(axis='x',alpha=.16)
    vals=list(counts.values());bx.barh(range(3),np.array(vals)/16,color=[BLUE,ORANGE,GREEN],height=.55)
    bx.set_yticks(range(3),['Original prompt\nrandom menus','Combined prompt\nrandom menus','Combined prompt\nassisted menus']);bx.invert_yaxis();bx.set_xlim(0,1.14)
    for i,v in enumerate(vals):bx.text(v/16+.025,i,f'{v}/16',va='center',fontweight='bold')
    bx.set_xticks([0,.25,.5,.75,1]);bx.xaxis.set_major_formatter(PercentFormatter(1));bx.set_xlabel('Completed runs; failures stay in the denominator')
    fig.text(.035,.035,'Assisted menus guarantee a reference-best action using external solver assistance.\nThat 16/16 result is not evidence of a model capability gain. Intervals are pointwise and exploratory.',fontsize=10,linespacing=1.5)
    save(fig,'local-scores-and-completion')
    payload=dict(pilot_means=means,pilot_turns=len(records),counterfactual_actions=6590,pairs=20915,
        example=r,trajectories=plotted,local_effects=effects,completion=counts,
        selection_rules={'example':'Previously documented post-hoc example: medium seed 0 turn 13.',
            'trajectories':'Run containing that example and the only failed repeat of the same equation.',
            'summary':'All 24 pilot runs, equal run weights; no independence implied.'})
    (out/'figure-data.json').write_text(json.dumps(payload,indent=2)+'\n')
    (out/'source-checksums.json').write_text(json.dumps(hashes,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'validated_turns':len(records),'means':means,'completion':counts,'output':str(out)},indent=2))

if __name__=='__main__': main()
