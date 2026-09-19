"""Offline, pre-specified paired analysis of the Jev static campaign.

No API calls. --allow-partial produces explicitly provisional development output.
All bootstrap intervals resample whole template/source-equation clusters, not turns.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
BASE='n0_s0_g0'; COMBINED='n1_s1_g1'
POLICIES=['reference','shallow_first','cleanup_first']
FACTORS=['neutral','structured','guided']
STRUCTURES={'nesting':'deep','branch_width':'wide','magnitude':'large','numeric_regime':'rational'}
BOOT=4000

def mean(values):
    values=[float(v) for v in values if v is not None and np.isfinite(v)]
    return float(np.mean(values)) if values else None

def cluster(case):
    return case['family']  # Fresh template or original saved equation: only 3 saved clusters.

def cohort(case,name):
    if name=='fresh':return case['origin']=='fresh'
    if name=='saved':return case['origin']=='saved'
    return case['origin']=='fresh' and case['split']==name

def estimate(records, cases):
    """Equal-cluster mean; rows are case-level estimates, repeats already reduced."""
    groups=defaultdict(list)
    for ident,value in records:
        if value is not None and np.isfinite(value):groups[cluster(cases[ident])].append(float(value))
    values={k:mean(v) for k,v in sorted(groups.items())}
    arr=np.array(list(values.values()),dtype=float)
    if not len(arr):return {'mean':None,'ci95':None,'clusters':0,'cases':0,'cluster_values':{}}
    rng=np.random.default_rng(20260919)
    samples=rng.choice(arr,size=(BOOT,len(arr)),replace=True).mean(axis=1)
    return {'mean':float(arr.mean()),'ci95':np.quantile(samples,[.025,.975]).tolist() if len(arr)>1 else None,
            'clusters':len(arr),'cases':sum(len(v) for v in groups.values()),'cluster_values':values}

def distance_distributions(p,q):
    keys=set(p)|set(q);a=np.array([p.get(k,0) for k in keys]);b=np.array([q.get(k,0) for k in keys])
    a=a/a.sum();b=b/b.sum();m=(a+b)/2
    def kl(x):
        mask=x>0
        return float(np.sum(x[mask]*np.log2(x[mask]/m[mask])))
    return {'tv':float(np.abs(a-b).sum()/2),'js_bits':(kl(a)+kl(b))/2}

def semdist(row,job):
    return {json.dumps(job['menu'][label],sort_keys=True):float(p) for label,p in row['probabilities'].items()}

def chosen_semantic(row,job):return json.dumps(job['menu'][row['choice']],sort_keys=True)

def value(row,policy,metric):
    if metric=='input_tokens':return row.get('usage',{}).get('input_tokens',row.get('usage',{}).get('prompt_tokens'))
    if metric=='reroll_probability':return row.get('reroll_probability')
    return row.get('evaluators',{}).get(policy,{}).get(metric)

def pair_value(rows,policy,metric):
    vals=[value(r,policy,metric) for r in rows]
    return None if len(vals)!=2 or any(v is None for v in vals) else mean(vals)

def comparisons(rows,cases,index,cohorts):
    output=[]
    for co in cohorts:
      ids=[ident for ident,c in cases.items() if cohort(c,co)]
      for policy in POLICIES:
       for metric in ['probability_quality','expected_regret_steps','full_pool_regret']:
        for treatment in ['combined']+FACTORS:
         effects=[];baseline=[];treated=[]
         for ident in ids:
          arms={cond:index.get((ident,'core',cond),[]) for cond in [f'n{n}_s{s}_g{g}' for n in range(2) for s in range(2) for g in range(2)]}
          if treatment=='combined':
           pairs=[arms[BASE],arms[COMBINED]]
           if any(len(v)!=2 for v in pairs):continue
           a,b=[pair_value(pair,policy,metric) for pair in pairs]
          else:
           if any(len(v)!=2 for v in arms.values()):continue
           low=[];high=[]
           for pair in arms.values():
            v=pair_value(pair,policy,metric)
            (high if pair[0]['variant'][treatment] else low).append(v)
           if any(v is None for v in low+high):continue
           a,b=mean(low),mean(high)
          if a is None or b is None:continue
          effects.append((ident,b-a));baseline.append((ident,a));treated.append((ident,b))
         output.append({'cohort':co,'policy':policy,'metric':metric,'treatment':treatment,
                        'effect':estimate(effects,cases),'baseline':estimate(baseline,cases),'treated':estimate(treated,cases)})
    return output

def structures(cases,index):
    output=[]
    for policy in POLICIES:
     for factor,high in STRUCTURES.items():
      for metric in ['probability_quality','expected_regret_steps']:
       for outcome in ['baseline','combined_effect']+FACTORS:
        cell=[]
        for ident,c in cases.items():
         if c['origin']!='fresh':continue
         arms={cond:index.get((ident,'core',cond),[]) for cond in [f'n{n}_s{s}_g{g}' for n in range(2) for s in range(2) for g in range(2)]}
         if outcome=='baseline':
          if len(arms[BASE])!=2:continue
          v=pair_value(arms[BASE],policy,metric)
         elif outcome=='combined_effect':
          if len(arms[BASE])!=2 or len(arms[COMBINED])!=2:continue
          a,b=[pair_value(arms[k],policy,metric) for k in [BASE,COMBINED]]
          v=None if a is None or b is None else b-a
         else:
          if any(len(rs)!=2 for rs in arms.values()):continue
          low=[pair_value(rs,policy,metric) for rs in arms.values() if not rs[0]['variant'][outcome]]
          highv=[pair_value(rs,policy,metric) for rs in arms.values() if rs[0]['variant'][outcome]]
          v=None if any(v is None for v in low+highv) else mean(highv)-mean(low)
         if v is not None:cell.append((ident,v))
        # Match all other structural factors within a template before taking differences.
        pairs=defaultdict(dict)
        for ident,v in cell:
         c=cases[ident];key=(c['family'],tuple((f,c['factors'][f]) for f in STRUCTURES if f!=factor))
         pairs[key][c['factors'][factor]==high]=(ident,v)
        differences=[(p[True][0],p[True][1]-p[False][1]) for p in pairs.values() if False in p and True in p]
        output.append({'factor':factor,'high_level':high,'outcome':outcome,'policy':policy,'metric':metric,
                       'effect':estimate(differences,cases)})
    return output

def sidearms(cases,index,jobs):
    output=[];sensitivity=[]
    conditions=sorted({(kind,cond) for ident,kind,cond in index if kind!='core'})
    for kind,condition in conditions:
     for co in ['fresh','saved']:
      for policy in POLICIES:
       metrics=['full_pool_regret','reroll_probability'] if kind=='menu' else ['probability_quality','expected_regret_steps','reroll_probability','input_tokens']
       for metric in metrics:
        diff=[];ba=[];tr=[]
        for ident,c in cases.items():
         if not cohort(c,co):continue
         a=index.get((ident,'core',BASE),[]);b=index.get((ident,kind,condition),[])
         if len(a)!=2 or len(b)!=2:continue
         av,bv=[pair_value(rs,policy,metric) for rs in (a,b)]
         if av is None or bv is None:continue
         diff.append((ident,bv-av));ba.append((ident,av));tr.append((ident,bv))
        output.append({'kind':kind,'condition':condition,'cohort':co,'policy':policy,'metric':metric,
                       'effect':estimate(diff,cases),'baseline':estimate(ba,cases),'treated':estimate(tr,cases)})
    # Compare all four cross-treatment replicate pairs to baseline repeat noise.
    for condition in ['identical_repeat','reverse','words','words_reverse']:
     for co in ['fresh','saved']:
      values=defaultdict(list)
      for ident,c in cases.items():
       if not cohort(c,co):continue
       a=index.get((ident,'core',BASE),[])
       if len(a)!=2:continue
       if condition=='identical_repeat':
        if len(index.get((ident,'labels','reverse'),[]))!=2:continue
        pairs=[(a[0],a[1])]
       else:
        b=index.get((ident,'labels',condition),[])
        if len(b)!=2:continue
        pairs=[(ar,br) for ar in a for br in b]
       scored=[]
       for ar,br in pairs:
        ap,bp=jobs[ar['id']],jobs[br['id']]
        d=distance_distributions(semdist(ar,ap),semdist(br,bp))
        d['choice_flip']=float(chosen_semantic(ar,ap)!=chosen_semantic(br,bp));scored.append(d)
       for metric in ['tv','js_bits','choice_flip']:values[metric].append((ident,mean(d[metric] for d in scored)))
      for metric,rs in values.items():sensitivity.append({'condition':condition,'cohort':co,'metric':metric,'estimate':estimate(rs,cases)})
    return output,sensitivity

def confidence_analysis(cases,index):
    output=[]
    for condition in [BASE,COMBINED]:
     for policy in POLICIES:
      for co in ['fresh','saved']:
       details=[];observations=defaultdict(list)
       for ident,c in cases.items():
        if not cohort(c,co):continue
        rows=index.get((ident,'core',condition),[])
        if len(rows)!=2:continue
        for r in rows:
         opts=r['evaluators'][policy]['options'];selected=next((o for o in opts if o['selected']),None)
         if selected is None:continue
         prob=float(r['selected_probability']);error=float(selected['D_after']>min(o['D_after'] for o in opts))
         details.append({'id':ident,'confidence':prob,'error':error});observations[ident].append((prob,error))
       for lo,hi in [(0,.5),(.5,.8),(.8,1.000001)]:
        rates=[];count=0
        for ident,rs in observations.items():
         err=[err for p,err in rs if lo<=p<hi];count+=len(err)
         if err:rates.append((ident,mean(err)))
        output.append({'condition':condition,'policy':policy,'cohort':co,'confidence_bin':[lo,min(hi,1)],
                       'suboptimal_rate':estimate(rates,cases),'selected_algebra_observations':count})
    return output

def correlations(cases,index):
    # Descriptive within-template association, with no claimed independent causal interpretation.
    output=[]
    for condition in [BASE,COMBINED]:
     for feature in ['ast_depth','nodes','reference_steps','input_tokens']:
      groups=defaultdict(list)
      for ident,c in cases.items():
       if c['origin']!='fresh':continue
       rows=index.get((ident,'core',condition),[])
       if len(rows)!=2:continue
       y=mean(value(r,'reference','probability_quality') for r in rows)
       x=mean(value(r,'reference','input_tokens') for r in rows) if feature=='input_tokens' else c['derived'].get(feature)
       if x is not None and y is not None:groups[c['family']].append((float(x),y,ident))
      vals=[]
      for family,rs in groups.items():
       x=np.array([r[0] for r in rs]);y=np.array([r[1] for r in rs])
       if len(x)>2 and np.std(x)>0 and np.std(y)>0:vals.append((rs[0][2],float(np.corrcoef(x,y)[0,1])))
      output.append({'condition':condition,'feature':feature,'within_template_pearson':estimate(vals,cases)})
    return output

def menu_availability(cases,index):
    output=[]
    for factor,high in STRUCTURES.items():
      for level in [False,True]:
       metrics=defaultdict(list)
       for ident,c in cases.items():
        if c['origin']!='fresh' or (c['factors'][factor]==high)!=level:continue
        rows=index.get((ident,'core',BASE),[])
        if len(rows)!=2:continue
        opts=rows[0]['evaluators']['reference']['options'];d=c['derived']['reference_steps']
        useful=sum(o['D_after']<d for o in opts)
        metrics['any_improving'].append((ident,float(useful>0)))
        metrics['fraction_improving'].append((ident,useful/len(opts)))
       output.append({'factor':factor,'high_level':level,**{k:estimate(v,cases) for k,v in metrics.items()}})
    return output

def evaluator_disagreement(cases,index):
    output=[]
    for alt in POLICIES[1:]:
     pairs=ties=discordant=0;case_rates=[]
     for ident,c in cases.items():
      rows=index.get((ident,'core',BASE),[])
      if len(rows)!=2:continue
      ref={o['action_key']:o['D_after'] for o in rows[0]['evaluators']['reference']['options']}
      other={o['action_key']:o['D_after'] for o in rows[0]['evaluators'][alt]['options']}
      n=d=0;keys=sorted(ref)
      for i,a in enumerate(keys):
       for b in keys[i+1:]:
        x=np.sign(ref[a]-ref[b]);y=np.sign(other[a]-other[b])
        if not x or not y:
         ties+=int(x!=y);continue
        n+=1;d+=int(x!=y)
      pairs+=n;discordant+=d
      if n:case_rates.append((ident,d/n))
     output.append({'alternative':alt,'strict_pairs':pairs,'reversed_strict_pairs':discordant,
                    'tie_disagreements':ties,'equal_cluster_reversal_rate':estimate(case_rates,cases)})
    return output

def format_est(e,scale=1):
    if e['mean'] is None:return 'unavailable'
    val=f'{e["mean"]*scale:+.3f}'
    if e['ci95'] and e['ci95'][0]==e['ci95'][1]:
        return val+' (degenerate bootstrap; uncertainty unresolved)'
    return val+(f' [{e["ci95"][0]*scale:+.3f}, {e["ci95"][1]*scale:+.3f}]' if e['ci95'] else '')

def plots(summary):
    folder=OUT/'figures';folder.mkdir(exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':140,'savefig.dpi':260})
    def save(fig,name):
        fig.savefig(folder/(name+'.png'),bbox_inches='tight');fig.savefig(folder/(name+'.svg'),bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,4.8),sharey=True)
    for ax,policy in zip(axes,POLICIES):
      for i,treatment in enumerate(FACTORS+['combined']):
       row=next(r for r in summary['paired_effects'] if r['cohort']=='fresh' and r['policy']==policy and r['metric']=='probability_quality' and r['treatment']==treatment)
       e=row['effect'];v=e['mean']
       if v is not None:
        ci=e['ci95'];err=None if ci is None else np.array([[max(0,v-ci[0])],[max(0,ci[1]-v)]])
        ax.errorbar(v,i,xerr=err,fmt='o',color=['#0072B2','#009E73','#D55E00','#CC79A7'][i],capsize=4)
      ax.axvline(0,color='.6',lw=1);ax.set_title(policy.replace('_',' ').title());ax.set_xlabel('Paired change in probability quality')
      ax.set_yticks(range(4),['Remove benefits','Node table','Precedence guidance','All three']);ax.grid(axis='x',alpha=.15)
    axes[0].invert_yaxis();fig.suptitle('Prompt effects on fresh states: equal-template means and 95% cluster bootstrap intervals')
    fig.text(.5,.005,'128 states in only 8 template clusters; all three evaluators measure reference-policy work, not optimal distance.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.035,1,.94]);save(fig,'static_01_prompt_effects')
    fig,axes=plt.subplots(1,3,figsize=(13,4.8),sharey=True)
    for ax,policy in zip(axes,POLICIES):
      array=np.full((4,5),np.nan)
      for i,factor in enumerate(STRUCTURES):
       for j,outcome in enumerate(['baseline']+FACTORS+['combined_effect']):
        r=next(r for r in summary['structural_effects'] if r['factor']==factor and r['outcome']==outcome and r['policy']==policy and r['metric']=='probability_quality')
        if r['effect']['mean'] is not None:array[i,j]=r['effect']['mean']
      im=ax.imshow(array,cmap='RdBu',vmin=-.3,vmax=.3,aspect='auto')
      for i in range(4):
       for j in range(5):
        if np.isfinite(array[i,j]):ax.text(j,i,f'{array[i,j]:+.2f}',ha='center',va='center',fontsize=9,color='white' if abs(array[i,j])>.21 else 'black')
      ax.set_xticks(range(5),['Baseline','Neutral','Table','Guide','Combined'],rotation=45,ha='right');ax.set_yticks(range(4),['Deep − shallow','Wide − narrow','Large − small','Rational − integer']);ax.set_title(policy.replace('_',' '))
    fig.suptitle('Structure effects and prompt × structure interactions (probability-quality points)')
    fig.text(.5,.015,'Baseline column: structural main effect. Other columns: difference in prompt treatment effect between structural levels.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.06,.94,.94]);fig.colorbar(im,ax=axes.ravel().tolist(),fraction=.025,pad=.02);save(fig,'static_02_structure_interactions')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    for co,col in [('fresh','#0072B2'),('saved','#D55E00')]:
     offset=-.08 if co=='fresh' else .08
     for i,cond in enumerate(['cover_best','cover_four','omit_improving']):
      rs=[r for r in summary['side_effects'] if r['kind']=='menu' and r['condition']==cond and r['cohort']==co and r['policy']=='reference' and r['metric']=='full_pool_regret']
      if rs and rs[0]['effect']['mean'] is not None:
       e=rs[0]['effect'];v=e['mean'];ci=e['ci95'];err=None if ci is None else np.array([[max(0,v-ci[0])],[max(0,ci[1]-v)]])
       axes[0].errorbar(v,i+offset,xerr=err,fmt='o',color=col,capsize=3,label=co if i==0 else None)
     for i,cond in enumerate(['identical_repeat','reverse','words','words_reverse']):
      rs=[r for r in summary['label_sensitivity'] if r['condition']==cond and r['cohort']==co and r['metric']=='tv']
      if rs and rs[0]['estimate']['mean'] is not None:axes[1].plot(rs[0]['estimate']['mean'],i+offset,'o',color=col,label=co if i==0 else None)
    axes[0].axvline(0,color='.6');axes[0].set_yticks(range(3),['Cover best','Cover four useful','Omit improving']);axes[0].set_xlabel('Change in full-pool regret (reference steps; lower better)');axes[0].set_title('Menu intervention: paired same-state effects')
    axes[1].set_yticks(range(4),['Identical-repeat noise','Reverse order','Random-word labels','Words + reverse']);axes[1].set_xlabel('Semantic probability total variation (0–1)');axes[1].set_title('Sensitivity after aligning action identities');axes[1].set_xlim(left=0)
    for ax in axes:ax.invert_yaxis();ax.legend();ax.grid(axis='x',alpha=.15)
    fig.suptitle('Controller-menu constraints and representation sensitivity');fig.tight_layout(rect=[0,0,1,.94]);save(fig,'static_03_menu_labels')
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    conditions=['none','padding_2000_prefix','padding_2000_suffix','padding_6000_prefix','padding_6000_suffix']
    for co,col in [('fresh','#0072B2'),('saved','#D55E00')]:
      offset=-.08 if co=='fresh' else .08
      for i,condition in enumerate(conditions):
       for ax,metric in zip(axes,['probability_quality','input_tokens']):
        rs=[r for r in summary['side_effects'] if r['kind']=='history' and r['condition']==condition and r['cohort']==co and r['policy']=='reference' and r['metric']==metric]
        if rs and rs[0]['effect']['mean'] is not None:
         e=rs[0]['effect'];v=e['mean'];ci=e['ci95'];err=None if ci is None else np.array([[max(0,v-ci[0])],[max(0,ci[1]-v)]])
         ax.errorbar(v,i+offset,xerr=err,fmt='o',color=col,capsize=3,label=co if i==1 else None)
    for ax in axes:ax.set_yticks(range(5),['Remove history','2k words prefix','2k words suffix','6k words prefix','6k words suffix']);ax.invert_yaxis();ax.axvline(0,color='.6');ax.legend();ax.grid(axis='x',alpha=.15)
    axes[0].set_xlabel('Paired change in probability quality');axes[1].set_xlabel('Paired change in billed input tokens')
    fig.suptitle('History and irrelevant archival-prose controls');fig.text(.5,.005,'Padding varies content and placement along with length; it does not isolate a pure token-count effect.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.035,1,.94]);save(fig,'static_04_history_length')

def report(s):
    lines=['# Static controlled hypothesis experiment','',
      '**'+('PROVISIONAL PARTIAL ANALYSIS' if s['audit']['missing_jobs'] else 'All frozen static jobs have terminal records')+'**. '+
      f"{s['audit']['successful_jobs']}/{s['audit']['expected_jobs']} jobs returned scored results; {s['audit']['missing_jobs']} missing and {s['audit']['failed_jobs']} failed/cut off.", '',
      'All effects below average the two repeats within a state, then average states within templates, then weight templates equally. Intervals resample whole templates (4,000 bootstrap samples). There are only eight fresh template clusters, four in each predesignated split, so intervals are exploratory and may understate uncertainty about unseen equation families. No model was trained and no treatment was selected using held-out results. Saved states are a diagnostic selection from earlier runs, not a representative fresh benchmark. Saved-state means weight the three original equations (simple, medium, unholy) equally, and intervals resample those three source-equation clusters. These saved intervals are especially fragile; fifteen episodes do not provide fifteen independent problem clusters.', '',
      '## Paired prompt effects','',
      'Main effects average across the other two prompt factors. Combined compares all three interventions with the original prompt. Positive quality changes favour the treatment; negative regret changes favour it. Quality excludes reroll/completion and renormalizes algebra-action probabilities, so reroll mass is analysed separately. Equal-quality menus have undefined quality and are omitted rather than assigned a score.', '',
      '| Cohort | Evaluator | Treatment | Δ probability quality [95% cluster interval] | Δ regret, steps |',
      '|---|---|---|---:|---:|']
    for co in ['fresh','diagnostic','heldout','saved']:
     for policy in POLICIES:
      for treatment in (FACTORS+['combined'] if co=='fresh' else ['combined']):
       rs=[r for r in s['paired_effects'] if r['cohort']==co and r['policy']==policy and r['treatment']==treatment]
       q=next(r for r in rs if r['metric']=='probability_quality');r=next(r for r in rs if r['metric']=='expected_regret_steps')
       lines.append(f'| {co} | {policy} | {treatment} | {format_est(q["effect"])} | {format_est(r["effect"])} |')
    lines+=['','## Structure and prompt interactions','',
      'Structural comparisons match the other three assigned factors within a template. Baseline is the structural effect under the original prompt; other columns measure how that structural contrast changes the prompt treatment effect. Depth also changes node count and horizon; width has template-dependent meaning. Each structural state has its own action pool and one independently generated menu, so contrasts also include induced menu availability and scoring-scale changes. They cannot identify a pure depth or internal-representation mechanism. Magnitude and rational regime change literal values, and rational regime also changes the constructed root. These factors therefore identify the defined interventions, not isolated internal mechanisms.','',
      '| Factor (high − low) | Evaluator | Baseline quality difference | Interaction with combined prompt |','|---|---|---:|---:|']
    for f in STRUCTURES:
     for p in POLICIES:
      rows=[r for r in s['structural_effects'] if r['factor']==f and r['policy']==p and r['metric']=='probability_quality']
      a=next(r for r in rows if r['outcome']=='baseline');b=next(r for r in rows if r['outcome']=='combined_effect')
      lines.append(f'| {f} | {p} | {format_est(a["effect"])} | {format_est(b["effect"])} |')
    lines+=['','Baseline-menu availability helps assess one structural confound. Equal-template summaries use the original reference evaluator; they are descriptive, not controls that make menus identical.','',
            '| Factor | Level | Fraction of menus with an improving move | Mean fraction of algebra moves improving |',
            '|---|---|---:|---:|']
    for r in s['menu_availability_by_structure']:
        if r.get('any_improving',{}).get('mean') is None:continue
        lines.append(f'| {r["factor"]} | {"high" if r["high_level"] else "low"} | {r["any_improving"]["mean"]:.3f} | {r["fraction_improving"]["mean"]:.3f} |')
    lines+=['','## Menus, history, and padding','',
      'Menu changes are assessed against the best move in the full available action pool, not the best offered move. This prevents an easier or weaker offered menu from manufacturing a normalized-quality improvement. The cover-best intervention guarantees an original-reference-best move, not the optimum under every evaluator. Full-pool regret is conditional on algebra moves and cannot by itself value the future benefit of reroll. Padding changes archival content and attention placement as well as length. Removing history is evaluated only on saved states with nonempty history.','',
      '| Kind / condition | Cohort | Δ full-pool regret (menu) or Δ quality (history) | Δ reroll probability |','|---|---|---:|---:|']
    for kind in ['menu','history']:
     for cond in sorted({r['condition'] for r in s['side_effects'] if r['kind']==kind}):
      for co in ['fresh','saved']:
       rs=[r for r in s['side_effects'] if r['kind']==kind and r['condition']==cond and r['cohort']==co and r['policy']=='reference']
       a=next((r for r in rs if r['metric']==('full_pool_regret' if kind=='menu' else 'probability_quality')),None);b=next((r for r in rs if r['metric']=='reroll_probability'),None)
       if a and a['effect']['mean'] is not None:lines.append(f'| {kind}: {cond} | {co} | {format_est(a["effect"])} | {format_est(b["effect"])} |')
    lines+=['','## Labels and identical-repeat noise','',
      'All distribution comparisons use the full reported distribution and map labels back to exact semantic action keys, including reroll/completion. Each label treatment averages all four baseline-versus-treatment repeat pairs. Identical-repeat noise uses the two baseline responses on exactly the same side-test cases; unknown provider caching means this is observed repeat variability, not a pure estimate of intrinsic model stochasticity; averaging distributions before comparing would artificially suppress this noise. Total variation is 0 for identical distributions and 1 for disjoint distributions; Jensen–Shannon divergence uses base-2 logarithms. Fresh identical-repeat choices flipped on 0 of 16 states. Its degenerate bootstrap interval does not establish zero underlying variation: a tiny sample with no observed event cannot estimate rare-event uncertainty through ordinary resampling.','',
      '| Condition | Cohort | Semantic total variation | Choice-flip rate |','|---|---|---:|---:|']
    for cond in ['identical_repeat','reverse','words','words_reverse']:
     for co in ['fresh','saved']:
      rs=[r for r in s['label_sensitivity'] if r['condition']==cond and r['cohort']==co]
      if not rs:continue
      a=next(r for r in rs if r['metric']=='tv');b=next(r for r in rs if r['metric']=='choice_flip')
      lines.append(f'| {cond} | {co} | {format_est(a["estimate"])} | {format_est(b["estimate"])} |')
    lines+=['','## Confidence is not correctness calibration','',
      'The following is the rate of selecting an algebra action with worse reference cost than another offered action. It excludes reroll and completion selections. Bins condition on the probability assigned to the selected action; they are an error association, not calibration against a true target probability distribution. The number of eligible observations and contributing clusters changes by bin.','',
      '| Prompt | Cohort | Selected probability bin | Suboptimal rate [cluster interval] | Algebra observations |','|---|---|---|---:|---:|']
    for r in s['confidence_error']:
     if r['policy']=='reference':lines.append(f'| {r["condition"]} | {r["cohort"]} | {r["confidence_bin"]} | {format_est(r["suboptimal_rate"])} | {r["selected_algebra_observations"]} |')
    lines+=['','## Evaluator and measurement limits','',
      'All three evaluators are deterministic policies, not general shortest-path oracles. A prompt effect that changes sign across evaluators is strategy-sensitive evidence. Strict pair reversals and tie disagreements below quantify this sensitivity; the separate oracle audit additionally tests tractable bounded shortest paths. These external behavioural tests cannot identify a specific internal architectural cause.','',
      '| Alternative evaluator | Strict pair reversals / comparable pairs | Equal-cluster reversal rate | Tie disagreements |','|---|---:|---:|---:|']
    for r in s['evaluator_disagreement']:lines.append(f'| {r["alternative"]} | {r["reversed_strict_pairs"]}/{r["strict_pairs"]} | {format_est(r["equal_cluster_reversal_rate"])} | {r["tie_disagreements"]} |')
    lines+=['','## Audit','',f'```json\n{json.dumps(s["audit"],indent=2)}\n```','',
      'All condition summaries, cluster contributions, structural interactions, actual input-token changes, and evaluator variants are retained in `static_summary.json`. No p-values or data-dependent significance filtering are used. Successful paired measurements alone enter effects; missing, failed, and cutoff responses stay in the audit. No missing result is imputed. Analyses with incomplete repeat pairs are omitted. The reports cover the frozen hypotheses; they do not establish performance over algebra generally.','']
    (OUT/'STATIC_REPORT.md').write_text('\n'.join(lines))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--allow-partial',action='store_true');args=parser.parse_args()
    cases={c['id']:c for c in json.loads((OUT/'cases.json').read_text())}
    jobs={j['id']:j for j in map(json.loads,(OUT/'jobs.jsonl').read_text().splitlines())}
    rows=[];missing=[]
    for ident in jobs:
        p=OUT/'responses'/(ident+'.json')
        if p.exists():rows.append(json.loads(p.read_text()))
        else:missing.append(ident)
    if missing and not args.allow_partial:raise SystemExit(f'{len(missing)} frozen jobs lack terminal records; use --allow-partial only for development.')
    assert len({r['id'] for r in rows})==len(rows)
    successful=[r for r in rows if r['status']=='ok'];index=defaultdict(list)
    for r in successful:index[(r['case_id'],r['kind'],r['condition'])].append(r)
    for group in index.values():group.sort(key=lambda r:r['repeat'])
    input_tokens=[value(r,'reference','input_tokens') for r in successful];input_tokens=[v for v in input_tokens if v is not None]
    audit={'expected_jobs':len(jobs),'terminal_jobs':len(rows),'successful_jobs':len(successful),
           'failed_jobs':len(rows)-len(successful),'missing_jobs':len(missing),
           'statuses':dict(Counter(r['status'] for r in rows)),
           'statuses_by_kind':{k:dict(Counter(r['status'] for r in rows if r['kind']==k)) for k in ['core','menu','labels','history']},
           'incomplete_successful_repeat_pairs':sum(len(v)!=2 for v in index.values()),
           'undefined_quality_by_evaluator':{p:sum(value(r,p,'probability_quality') is None for r in successful) for p in POLICIES},
           'billed_input_token_range': [min(input_tokens),max(input_tokens)] if input_tokens else None,
           'billed_input_token_median':mean([float(np.median(input_tokens))]) if input_tokens else None,
           'static_response_cost_usd':sum(r.get('usage',{}).get('cost',0) or 0 for r in successful),
           'cost_note':'Successful response cost only. Shared budget ledger is authoritative and also includes failures/retries and rollouts.',
           'missing_ids':missing,'failed_ids':[r['id'] for r in rows if r['status']!='ok']}
    sides,labels=sidearms(cases,index,jobs)
    summary={'audit':audit,'bootstrap':{'samples':BOOT,'unit':'template for fresh; original source equation for saved (3 clusters)','weighting':'equal cluster','seed':20260919},
             'paired_effects':comparisons(successful,cases,index,['fresh','diagnostic','heldout','saved']),
             'structural_effects':structures(cases,index),'side_effects':sides,'label_sensitivity':labels,
             'confidence_error':confidence_analysis(cases,index),'descriptive_correlations':correlations(cases,index),
             'evaluator_disagreement':evaluator_disagreement(cases,index),'menu_availability_by_structure':menu_availability(cases,index),
             'analysis_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'static_summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n');report(summary);plots(summary)
    print(json.dumps(audit,indent=2))
    print('Offline static analysis completed; wrote static_summary.json, STATIC_REPORT.md, and four PNG/SVG figures.')

if __name__=='__main__':main()
