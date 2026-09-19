"""Regenerate the scientific figures, statistics and step viewer without API calls.

Usage: python analyze_and_plot.py
Only reads the frozen protocol, raw responses, episodes and budget ledger.
"""
from collections import Counter
import hashlib
import html
import json
import math
from pathlib import Path
import statistics
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, PercentFormatter

ROOT=Path(__file__).resolve().parent
FIG=ROOT/'figures';FIG.mkdir(exist_ok=True)
LEVELS=['simple','medium','unholy']
NAMES={'simple':'Simple','medium':'Medium','unholy':'Unholy'}
COLORS={'simple':'#0072B2','medium':'#D55E00','unholy':'#009E73'}
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,
 'axes.labelsize':10,'figure.titlesize':16,'axes.spines.top':False,'axes.spines.right':False,
 'axes.grid':True,'grid.alpha':.18,'svg.fonttype':'none','savefig.facecolor':'white',
 'axes.axisbelow':True,'lines.linewidth':1.9,'text.parse_math':False})

def save(fig,name):
    fig.savefig(FIG/(name+'.png'),dpi=300,bbox_inches='tight')
    fig.savefig(FIG/(name+'.svg'),bbox_inches='tight');plt.close(fig)
def wilson(k,n):
    z=1.959963984540054;p=k/n;den=1+z*z/n
    mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [mid-half,mid+half]
def path(e,field,initial=0):return [initial]+[r[field] for r in e['trajectory']]
def ending(ax,e,x,y,annotate=False):
    ok=e['status']=='solved'
    ax.scatter([x],[y],marker='o' if ok else 'X',s=68 if ok else 110,
               color=COLORS[e['level']] if ok else '#A32232',edgecolor='white',linewidth=.7,zorder=6)
    if annotate and not ok:
        ax.axvline(x,color='#A32232',linestyle=':',alpha=.65)
        ax.annotate(e['status'].replace('cutoff_','').replace('_',' '),(x,y),xytext=(5,12),
                    textcoords='offset points',color='#A32232',fontsize=8)

def main():
    protocol=json.loads((ROOT/'protocol.json').read_text())
    episodes=[json.loads(p.read_text()) for p in sorted((ROOT/'episodes').glob('*.json'))]
    assert len(episodes)==48,'Wait for all 24 Jev and 24 random baseline episodes'
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==sha for n,sha in protocol['source_sha256'].items()),'Frozen experiment source changed'
    jev=[e for e in episodes if e['policy']=='jev'];baseline=[e for e in episodes if e['policy']=='random']
    representative={l:next(e for e in jev if e['level']==l and e['seed']==protocol['representative_seed']) for l in LEVELS}
    budget=json.loads((ROOT/'budget.json').read_text());fx=json.loads((ROOT/'fx.json').read_text())
    rate=fx['rates']['USD'];charged=sum(float(v.get('actual_usd',0)) for v in budget['attempts'].values())
    reserved=sum(float(v['accounted_usd']) for v in budget['attempts'].values())
    raw=[json.loads(p.read_text()) for p in sorted((ROOT/'raw').glob('*.json'))]
    latencies=[r['seconds'] for r in raw];steps=[r for e in jev for r in e['trajectory']]
    result={'scope':'Three fixed equations, eight menu seeds per equation; conditional controller experiment, not a general algebra benchmark.',
        'cost_usd':charged,'cost_gbp_estimate':charged/rate,'budget_exposure_usd':reserved,
        'hard_cap_usd':float(budget['cap_usd']),'hard_cap_gbp_estimate':float(budget['cap_usd'])/rate,
        'gbp_usd_rate':rate,'fx_date':fx['time_last_update_utc'],'api_attempts':len(raw),
        'missing_cost_attempts':sum('actual_usd' not in a for a in budget['attempts'].values()),
        'resolved_models':dict(Counter(r.get('response',{}).get('model','unknown') for r in raw)),
        'providers':dict(Counter(r.get('response',{}).get('provider','unknown') for r in raw)),
        'latency_seconds':{'median':float(np.median(latencies)),'p95':float(np.percentile(latencies,95))},
        'input_tokens':sum(r.get('response',{}).get('usage',{}).get('input_tokens',0) for r in raw),
        'output_tokens':sum(r.get('response',{}).get('usage',{}).get('output_tokens',0) for r in raw),
        'levels':{},'policy_action_counts':dict(Counter(r['action']['kind'] for r in steps)),
        'step_progress_counts':dict(Counter('improved' if r['delta_reference_steps']>0 else 'worsened' if r['delta_reference_steps']<0 else 'unchanged' for r in steps)),
        'rerolls_when_improving_action_offered':sum(r['action']['kind']=='reroll' and r['improving_action_offered'] for r in steps),
        'total_rerolls':sum(r['action']['kind']=='reroll' for r in steps),
        'observed_cutoffs':dict(Counter(e['status'] for e in jev if e['status']!='solved'))}
    for level in LEVELS:
        result['levels'][level]={}
        for policy in ['jev','random']:
            es=[e for e in episodes if e['level']==level and e['policy']==policy];success=[e for e in es if e['status']=='solved']
            result['levels'][level][policy]={
                'n':len(es),'solved':len(success),'solve_rate':len(success)/len(es),'wilson_95':wilson(len(success),len(es)),
                'median_decisions_all_runs':statistics.median(e['steps'] for e in es),
                'median_decisions_successful_runs':statistics.median(e['steps'] for e in success) if success else None,
                'range_decisions_successful_runs':[min(e['steps'] for e in success),max(e['steps'] for e in success)] if success else None,
                'mean_final_fraction_progress':statistics.mean(1-e['final_reference_steps']/e['initial_reference_steps'] for e in es),
                'mean_best_fraction_progress':statistics.mean(1-e['best_reference_steps']/e['initial_reference_steps'] for e in es),
                'cost_usd':sum(e['cost_usd'] for e in es),'outcomes':dict(Counter(e['status'] for e in es))}
    result['failed_run_audit']=[{
        'episode_id':e['episode_id'],'stop_step':e['steps'],
        'final_reference_steps':e['final_reference_steps'],
        'final_equation':e['final_equation'],
        'last_three_menus_had_improving_action':[r['improving_action_offered'] for r in e['trajectory'][-3:]],
        'last_three_selected_actions':[r['action']['kind'] for r in e['trajectory'][-3:]]}
        for e in jev if e['status']!='solved']
    (ROOT/'results.json').write_text(json.dumps(result,indent=2))

    # Three series, a prespecified seed: terminal values are not carried forward.
    fig,ax=plt.subplots(figsize=(10,5.5));fig.subplots_adjust(top=.80,bottom=.16)
    fig.suptitle('Does each decision bring the equation closer to solved?',y=.97,fontweight='bold')
    fig.text(.5,.90,'Jev 1.13 · preselected menu seed 0 · one trajectory per difficulty',ha='center',color='#444444')
    for level,e in representative.items():
        x=list(range(e['steps']+1));y=path(e,'fraction_remaining',1)
        ax.plot(x,y,color=COLORS[level],label=f'{NAMES[level]} · reference starts at {e["initial_reference_steps"]} steps')
        ending(ax,e,x[-1],y[-1],True)
    ax.axhline(0,color='#222222',lw=.8);ax.axhline(1,color='#777777',lw=.8,ls='--')
    ax.set(xlabel='Decision step i (rerolls included)',ylabel='Remaining reference work Dᵢ / D₀\n0 = solved; 1 = initial state')
    ax.legend(loc='upper right',frameon=True,fontsize=9);ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    fig.text(.125,.035,'D is the exact step count of a fixed reference policy, not the shortest possible solution. Lines end at the actual stop.',fontsize=9)
    save(fig,'01_three_trajectories')

    fig,axs=plt.subplots(2,3,figsize=(13,8),sharex='col');fig.subplots_adjust(top=.83,bottom=.14,hspace=.27,wspace=.25)
    fig.suptitle('All runs, including every failure and cutoff',y=.97,fontweight='bold')
    fig.text(.5,.919,'Eight menu seeds per cell · curves stop when the run stops · no extrapolated or carried-forward results',ha='center',fontsize=10)
    for col,level in enumerate(LEVELS):
        for row,policy in enumerate(['jev','random']):
            ax=axs[row,col]
            for e in [e for e in episodes if e['policy']==policy and e['level']==level]:
                x=list(range(e['steps']+1));y=path(e,'fraction_remaining',1)
                ax.plot(x,y,color=COLORS[level],alpha=.85 if e['seed']==0 else .33,lw=1.9 if e['seed']==0 else 1.2)
                ending(ax,e,x[-1],y[-1])
            s=result['levels'][level][policy]
            ax.set_title(f'{NAMES[level]} · {"Jev" if policy=="jev" else "Random"} · {s["solved"]}/{s["n"]} solved')
            ax.axhline(1,color='#888888',ls='--',lw=.8);ax.axhline(0,color='#333333',lw=.8)
            ymax=max(max(path(e,'fraction_remaining',1)) for e in episodes if e['policy']==policy and e['level']==level)
            ax.set_ylim(-.08,ymax*1.08);ax.xaxis.set_major_locator(MaxNLocator(integer=True,nbins=5))
            if col==0:ax.set_ylabel('Remaining work Dᵢ / D₀')
            if row==1:ax.set_xlabel('Decision step i')
    handles=[Line2D([0],[0],color='#666666',marker='o',lw=0,label='Solved (exactly verified)'),
             Line2D([0],[0],color='#A32232',marker='X',lw=0,label='Stopped without solving')]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.048),ncol=2,frameon=False)
    fig.text(.5,.018,'Vertical scales differ by panel to show each complete trajectory. Random baseline uses the same action generator and guards.',ha='center',fontsize=9)
    save(fig,'02_all_runs_and_cutoffs')

    fig,axs=plt.subplots(1,3,figsize=(14,4.8));fig.subplots_adjust(top=.76,bottom=.23,wspace=.30)
    fig.suptitle('Cumulative changes: activity is not the same as progress',y=.97,fontweight='bold')
    fig.text(.5,.89,'Jev 1.13 · preselected seed 0 · three complementary views of the same decisions',ha='center')
    fields=[('cumulative_net_progress_steps','Net progress (D₀ − Dᵢ) / D₀',True),
            ('cumulative_absolute_reference_movement','Total movement Σ|Dⱼ − Dⱼ₋₁| / D₀',True),
            ('cumulative_transformations','Executed algebra transformations',False)]
    for ax,(field,title,normalize) in zip(axs,fields):
        for level,e in representative.items():
            y=np.array(path(e,field),dtype=float)/(e['initial_reference_steps'] if normalize else 1)
            x=list(range(e['steps']+1));ax.plot(x,y,color=COLORS[level],label=NAMES[level]);ending(ax,e,x[-1],y[-1])
        ax.set_title(title,fontsize=10);ax.set_xlabel('Decision step i');ax.xaxis.set_major_locator(MaxNLocator(integer=True,nbins=5))
    axs[0].axhline(1,color='#777777',ls='--',lw=.8);axs[0].set_ylabel('Cumulative value')
    axs[0].legend(fontsize=9)
    fig.text(.5,.06,'Net progress can fall; total movement only grows. Transformations count edits even when D is unchanged; rerolls count as decisions but not edits.',ha='center',fontsize=9)
    save(fig,'03_cumulative_changes')

    fig,ax=plt.subplots(figsize=(12,9));fig.subplots_adjust(left=.16,right=.74,top=.86,bottom=.12)
    fig.suptitle('Where each Jev run stopped',y=.96,fontweight='bold')
    fig.text(.5,.91,'Every executed decision is shown; red crosses are hard cutoffs, not successful completion.',ha='center')
    ordered=sorted(jev,key=lambda e:(LEVELS.index(e['level']),e['seed']))
    for i,e in enumerate(ordered):
        color=COLORS[e['level']];ax.hlines(i,0,e['steps'],color=color,alpha=.65,lw=4)
        rerolls=[r['step_i'] for r in e['trajectory'] if r['action']['kind']=='reroll']
        ax.scatter(rerolls,[i]*len(rerolls),marker='|',color='#222222',s=65,zorder=5)
        ok=e['status']=='solved';ax.scatter(e['steps'],i,marker='o' if ok else 'X',color=color if ok else '#A32232',s=55 if ok else 95,zorder=6)
        label=f'{e["steps"]} · '+('solved' if ok else e['status'].replace('cutoff_','').replace('_',' '))
        ax.text(1.02,i,label,transform=ax.get_yaxis_transform(),va='center',fontsize=9,color='#333333' if ok else '#A32232')
    ax.set_yticks(range(len(ordered)),[f'{NAMES[e["level"]]} / seed {e["seed"]}' for e in ordered],fontsize=9)
    ax.invert_yaxis();ax.set_xlabel('Decision step i');ax.grid(axis='y',visible=False)
    fig.text(.16,.045,'Black ticks = rerolls. Limits: 3 consecutive / 8 total rerolls; 3 visits to a state; stagnation 12 / 18 / 30 decisions.\nDecision caps: 24 / 70 / 160 for Simple / Medium / Unholy. The earliest applicable stop wins.',fontsize=9)
    save(fig,'04_stop_timeline')

    fig,axs=plt.subplots(1,2,figsize=(11,5));fig.subplots_adjust(top=.79,bottom=.22,wspace=.30)
    fig.suptitle('Success and spending under the frozen protocol',y=.97,fontweight='bold')
    fig.text(.5,.89,'Eight runs per difficulty and policy; interval uncertainty concerns menu seeds on these fixed equations.',ha='center',fontsize=10)
    for j,policy in enumerate(['jev','random']):
        x=np.arange(3)+(j-.5)*.17;ys=[];lo=[];hi=[]
        for level in LEVELS:
            s=result['levels'][level][policy];ys.append(s['solve_rate']);lo.append(s['solve_rate']-s['wilson_95'][0]);hi.append(s['wilson_95'][1]-s['solve_rate'])
        axs[0].errorbar(x,ys,yerr=[lo,hi],fmt='o' if policy=='jev' else 's',capsize=4,color='#0072B2' if policy=='jev' else '#777777',label='Jev' if policy=='jev' else 'Random')
    axs[0].set_xticks(range(3),[NAMES[l] for l in LEVELS]);axs[0].set_ylim(-.08,1.08)
    axs[0].yaxis.set_major_formatter(PercentFormatter(1));axs[0].set_ylabel('Solved, with 95% Wilson interval');axs[0].legend()
    costs=[result['levels'][l]['jev']['cost_usd']/rate for l in LEVELS]
    axs[1].bar(range(3),costs,color=[COLORS[l] for l in LEVELS]);axs[1].set_xticks(range(3),[NAMES[l] for l in LEVELS]);axs[1].set_ylabel('Model usage charge (GBP equivalent)')
    for i,c in enumerate(costs):axs[1].annotate(f'£{c:.4f}',(i,c),xytext=(0,5),textcoords='offset points',ha='center',fontsize=10)
    axs[1].set_ylim(0,max(costs)*1.25)
    fig.text(.5,.065,f'Total billed: ${charged:.6f} ≈ £{charged/rate:.4f} · hard cap: $2.00 ≈ £{2/rate:.2f} · user ceiling: £2.00\nFX: £1 = ${rate:.6f}; conversion excludes any card fees. The baseline runs locally without model charges.',ha='center',fontsize=9)
    save(fig,'05_success_and_cost')

    failures=[e for e in jev if e['status']!='solved']
    fig,ax=plt.subplots(figsize=(10,5.3));fig.subplots_adjust(top=.80,bottom=.20,right=.94)
    fig.suptitle('The three failed runs: stopped by the reroll guard',y=.97,fontweight='bold')
    fig.text(.5,.905,'All nine terminal reroll menus lacked an action that immediately reduced reference work D.',ha='center',fontsize=10)
    for level in LEVELS:
        for e in [e for e in failures if e['level']==level]:
            x=list(range(e['steps']+1));y=path(e,'fraction_remaining',1)
            ax.plot(x,y,color=COLORS[level],label=f'{NAMES[level]} · seed {e["seed"]}')
            ending(ax,e,x[-1],y[-1]);ax.axvline(x[-1],color=COLORS[level],ls=':',alpha=.55,lw=1.4)
            ax.annotate(f'STOP: step {e["steps"]}',(x[-1],y[-1]),xytext=(-7,14),textcoords='offset points',ha='right',color=COLORS[level],fontsize=9,fontweight='bold')
    ax.set(xlabel='Decision step i',ylabel='Remaining reference work Dᵢ / D₀',ylim=(0,1.75))
    ax.legend(loc='upper right',fontsize=9);ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    fig.text(.125,.055,'Each cutoff followed 3 consecutive rerolls. A menu can lack an immediate improvement yet permit a useful multi-step detour.\nThese are failures under the frozen menu and stopping rules, not proof that Jev could not solve with different options.',fontsize=9)
    save(fig,'06_failed_run_detail')

    # JSONL: one row per decision with exactly the three difficulty-series keys.
    trajectories={l:representative[l] for l in LEVELS}
    with (ROOT/'three_series_by_step.jsonl').open('w') as f:
        for i in range(1,max(e['steps'] for e in trajectories.values())+1):
            row={'step_i':i}
            for l,e in trajectories.items():
                r=e['trajectory'][i-1] if i<=e['steps'] else None
                row[l]=None if r is None else {k:r[k] for k in ['reference_steps_after','fraction_remaining','fraction_progress','cumulative_absolute_reference_movement','cumulative_transformations','cumulative_rerolls','cumulative_cost_usd','status']}
            f.write(json.dumps(row)+'\n')
    create_viewer(episodes)
    create_report(protocol,result,episodes,representative)
    print(json.dumps(result,indent=2))

def create_viewer(episodes):
    # Self-contained local viewer: no network access or API calls.
    data=json.dumps(episodes).replace('</','<\\/')
    template='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Jev algebra — every decision</title>
<style>body{font:16px system-ui;max-width:1100px;margin:36px auto;padding:0 20px;color:#18212d;background:#f9fafc}h1{font-size:30px}select,button{font:inherit;padding:8px}input{width:100%}.metrics{display:flex;gap:12px;flex-wrap:wrap}.metric{background:white;border:1px solid #dce1e8;border-radius:8px;padding:14px;min-width:130px}.value{font-size:25px;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#fff;padding:16px;border:1px solid #dce1e8;border-radius:8px;line-height:1.5}.small{color:#526071;font-size:14px}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{border-bottom:1px solid #dde3ea;text-align:left;padding:10px;vertical-align:top}.chosen{background:#e6f4ec}#status{font-weight:650}summary{cursor:pointer;font-weight:650}</style>
<h1>Jev algebra: inspect the complete trajectory</h1><p>Choose a run, then move through its decisions. All displayed values come from saved results. No model calls are made.</p>
<label>Run <select id="run"></select></label><p id="status"></p><label>Decision <strong id="step"></strong><input id="slider" type="range" min="0" value="0"></label><div class="metrics" id="metrics"></div>
<h2>Current equation</h2><pre id="equation"></pre><h2>Selected action</h2><pre id="action"></pre><p class="small" id="extra"></p>
<details><summary>The entire action menu for this decision</summary><table><thead><tr><th>Label</th><th>Operation and explanation</th></tr></thead><tbody id="menu"></tbody></table></details>
<p class="small">D = steps required by the fixed reference solver, not the shortest possible path. D = 0 means literally x = a number. The model never sees D or the hidden solution. Cumulative movement is Σ|ΔD|; cumulative transformations counts actual algebra edits. Negative progress means the current state needs more reference work than the initial state.</p>
<script>const data=__DATA__;const $=id=>document.getElementById(id);for(const [i,e] of data.entries()){const o=document.createElement('option');o.value=i;o.textContent=`${e.policy} / ${e.level} / seed ${e.seed} — ${e.status}`;$('run').appendChild(o)}
function render(){const e=data[+$('run').value],i=+$('slider').value,r=i?e.trajectory[i-1]:null;$('step').textContent=`${i} / ${e.steps}`;$('status').textContent=`Final outcome: ${e.status} · ${e.steps} decisions · $${e.cost_usd.toFixed(6)}`;$('equation').textContent=r?r.after:e.initial_equation;$('action').textContent=r?`${r.label}: ${r.action_text}`:'Initial state; no action yet';const d=r?r.reference_steps_after:e.initial_reference_steps;const entries=[['Remaining steps D',d],['Progress',`${(100*(1-d/e.initial_reference_steps)).toFixed(1)}%`],['Cumulative movement',r?r.cumulative_absolute_reference_movement:0],['Transformations',r?r.cumulative_transformations:0],['Rerolls',r?r.cumulative_rerolls:0],['Cost',`$${(r?r.cumulative_cost_usd:0).toFixed(6)}`]];$('metrics').replaceChildren();for(const [k,v] of entries){const box=document.createElement('div');box.className='metric';const title=document.createElement('div');title.textContent=k;const value=document.createElement('div');value.className='value';value.textContent=v;box.append(title,value);$('metrics').appendChild(box)}$('extra').textContent=r?`Step ΔD = ${r.delta_reference_steps} (positive is improvement). Model selected probability: ${r.selected_probability??'not applicable'}. Improving action offered: ${r.improving_action_offered}. Status after step: ${r.status??'continuing'}.`:'Reference work at the starting equation: '+e.initial_reference_steps;$('menu').replaceChildren();if(r)for(const [label,m] of Object.entries(r.menu)){const tr=document.createElement('tr');if(label===r.label)tr.className='chosen';for(const v of [label,m.description]){const td=document.createElement('td');td.textContent=v;tr.appendChild(td)}$('menu').appendChild(tr)}}
$('run').onchange=()=>{$('slider').max=data[+$('run').value].steps;$('slider').value=0;render()};$('slider').oninput=render;$('run').onchange();</script></html>'''
    (ROOT/'step_viewer.html').write_text(template.replace('__DATA__',data))

def create_report(protocol,result,episodes,representative):
    nsolved=sum(e['status']=='solved' for e in episodes if e['policy']=='jev')
    lines=['# Jev as an algebra controller: bounded trajectory experiment','',
      f'Jev solved **{nsolved}/24** runs across three fixed linear equations and eight menu seeds per equation. Total model usage cost was **${result["cost_usd"]:.6f}**, approximately **£{result["cost_gbp_estimate"]:.4f}**. No charge is missing from the ledger.' if not result['missing_cost_attempts'] else f'Jev solved {nsolved}/24 runs; see results.json for charged and conservatively reserved spending.','',
      'This tests whether Jev can choose a sequence of useful tool operations when exact arithmetic is supplied by the environment. It does not test whether Jev can independently calculate all intermediate expressions.','',
      '## Results','',
      '| Difficulty | Initial reference steps | Jev solved | Decisions, successful runs: median (range) | Random solved | Jev cost, USD |',
      '|---|---:|---:|---|---:|---:|']
    for l in LEVELS:
        a=result['levels'][l]['jev'];b=result['levels'][l]['random'];r=a['range_decisions_successful_runs']
        dec='—' if r is None else f'{a["median_decisions_successful_runs"]:g} ({r[0]}–{r[1]})'
        lines.append(f'| {NAMES[l]} | {protocol["equations"][l]["initial_reference_steps"]} | {a["solved"]}/{a["n"]} | {dec} | {b["solved"]}/{b["n"]} | ${a["cost_usd"]:.6f} |')
    lines+=['','The decision medians above exclude failures; every failed run is included in the outcome table and the trajectory plots. A decision includes a reroll or premature completion claim.','',
      '![Three representative trajectories](figures/01_three_trajectories.png)','',
      '![All trajectories and cutoffs](figures/02_all_runs_and_cutoffs.png)','',
      '## What the distance means','',
      'Let D(s) be the number of legal transformations a fixed, deterministic reference policy needs to turn the current expression state s into literally `x = number`. The reference normalizes the deepest available subexpressions first, using a fixed tie-break order; after expansion and collection it removes x terms from the right, constants from the left, and divides by the remaining x coefficient. It is deliberately a reference workload, **not an optimal or shortest-path distance**. Different valid forms can have different D values.','',
      '- Remaining fraction at step i: `D_i / D_0`. Zero is solved; one is the starting workload; above one means more work remains than initially.',
      '- Net cumulative progress: `(D_0 - D_i) / D_0`. This may decrease or become negative.',
      '- Best progress reached: `1 - min(D_0, ..., D_i) / D_0`.',
      '- Cumulative movement: `sum(abs(D_j - D_(j-1)))`, also charted after dividing by D_0. It increases for both helpful and harmful changes; it is not itself success.',
      '- Cumulative transformations: number of executed algebra edits, excluding rerolls and completion declarations. This counts edits whose D change is zero.','',
      'A numerical residual at the true root would be zero throughout every run, because all legal actions preserve the solution. It would therefore be useless as a progress score here. D is evaluated offline for logging and for the stagnation cutoff; neither D, the hidden answer, nor reference-action identity is sent to Jev.','',
      '![Cumulative changes](figures/03_cumulative_changes.png)','',
      '## Frozen protocol','',
      f'- Model: `{protocol["model"]}`. Resolved versions: `{json.dumps(result["resolved_models"])}`. Provider: `{json.dumps(result["providers"])}`.',
      '- Three unique equations; seeds 0–7 for each. Seed 0 was selected for the three-series plots before any model calls. Each policy has 24 episodes.',
      '- Each decision samples exactly ten distinct executable operations uniformly without replacement, shuffles them, labels them move_01 … move_10, and appends reroll. Reroll is deliberately a stable affordance in the last position. No useful option is guaranteed and no option is filtered using the progress metric.',
      '- The operation pool includes local expansion/collection, balance operations, reversible distractions, swap, and a completion declaration. Some distinct operations can have similar effects. Choice among menu entries is the experimental unit.',
      '- Prompts give a strategy guide, exact current equation, last six selected actions and their resulting equations, and decision/reroll allowances. Each action explains what it does, its legality, and when it can help. Local rewrites show their exact replacement, so arithmetic is intentionally supplied by the engine.',
      '- Fractions are exact; denominators are nonzero constants. Every executed transformation is checked to preserve the unique root. Success requires x literally isolated on the left with a numeric constant on the right, verified by the engine.',
      '- No whole-equation solve/simplify operation, retries, restarts, hidden best-run selection, or tuning after seeing results.',
      '- The random controller samples uniformly from the same eleven options. It uses the same menu-generator seed and stopping rules. Its first menu matches Jev for a given seed; later menus can differ because the states diverge. It is an operational baseline, not a matched-state causal comparison.',
      '- The sequential environment uses a dedicated Python runner because each next menu depends on the preceding action; it is not a static multiple-choice evaluation. Three model episodes run concurrently.','',
      '## Safeguards and actual stopping points','',
      '| Guard | Stop rule |','|---|---|',
      '| Reroll loop | 3 consecutive rerolls, or 8 total |',
      '| Repeated state | Third visit to the same structural equation; addition-term order is ignored. Rerolls and rejected declarations do not count as revisits. |',
      '| Stagnation | No strict new best D for 12 / 18 / 30 decisions, by difficulty |',
      '| Decision cap | 24 / 70 / 160, by difficulty |',
      '| Premature completion | Second incorrect completion declaration |',
      '| Time | 240 / 480 / 900 seconds per episode; 1,800 seconds global model-run dispatch deadline; an in-flight request can finish after a time deadline |',
      '| Growth/context | Exclude candidate results above 320 AST nodes or 18,000 expression characters; stop before a request above 30,000 serialized bytes |',
      '| API errors | Preserve response/charge; stop the affected episode, without automatic retry |',
      '| Global spending | Persistent locked ledger; reserve $0.002 before each request; maximum $2 exposure and 2,200 attempts |','',
      'The first applicable guard stops the episode. A valid solved state takes precedence. Guards are deliberately conservative; a cutoff establishes failure within this protocol, not mathematical inability to solve with a longer allowance.','',
      '**Failure audit:** each of the three Jev cutoffs followed three consecutive menus with no action that immediately reduced D. This does not prove that every offered action was useless over a longer horizon. It does mean these failures combine random-menu coverage and the strict reroll limit; they are not cases where Jev repeatedly ignored an available immediate improvement. The simple failed run stopped at `3*x = 15`, one reference step from completion, because the cancelling division was absent from all three terminal menus.','',
      '![Failed-run detail](figures/06_failed_run_detail.png)','',
      '![Actual stop timeline](figures/04_stop_timeline.png)','',
      '| Run | Outcome | Decisions | Final D / initial D | Best progress | Rerolls |',
      '|---|---|---:|---:|---:|---:|']
    for e in sorted([e for e in episodes if e['policy']=='jev'],key=lambda e:(LEVELS.index(e['level']),e['seed'])):
        lines.append(f'| {e["level"]}, seed {e["seed"]} | {e["status"]} | {e["steps"]} | {e["final_reference_steps"]} / {e["initial_reference_steps"]} | {1-e["best_reference_steps"]/e["initial_reference_steps"]:.1%} | {e["rerolls"]} |')
    lines+=['','## Decision-level diagnostics','',
      f'- Progress by the reference metric: `{json.dumps(result["step_progress_counts"])}`.',
      f'- Jev rerolled {result["total_rerolls"]} times. In {result["rerolls_when_improving_action_offered"]} of those decisions, at least one offered action would have strictly reduced D immediately. This diagnostic uses the evaluator and was not shown to Jev.',
      f'- Model request latency: median {result["latency_seconds"]["median"]:.3f}s; 95th percentile {result["latency_seconds"]["p95"]:.3f}s. These include network/provider time and are descriptive, not a controlled hardware benchmark.',
      f'- API calls: {result["api_attempts"]}; reported input tokens: {result["input_tokens"]:,}; reported output tokens: {result["output_tokens"]:,}. Output usage is reported by the service even though this model’s output price is zero.','',
      '## Spending and reproducibility','',
      f'The ledger reports ${result["cost_usd"]:.9f} billed and ${result["budget_exposure_usd"]:.9f} total accounted exposure. The stricter $2 cap corresponds to approximately £{result["hard_cap_gbp_estimate"]:.2f}, below the user’s £2 ceiling. Provider routing is constrained to a maximum input price of $0.042 per million tokens and zero output price. Each attempt reserves $0.002, above the cost of a full 32K input context at that rate. An unknown charge keeps the full reservation; an unexpectedly larger charge halts further dispatch.',
      '',f'GBP estimates use £1 = ${result["gbp_usd_rate"]:.6f}, dated {result["fx_date"]}, from [ExchangeRate-API](https://open.er-api.com/v6/latest/GBP); the retrieved response is saved as `fx.json`. Actual card conversion and fees are not measured. Current model details: [OpenRouter Jev 1.13](https://openrouter.ai/typesafe/jev-1.13).','',
      '![Success and cost](figures/05_success_and_cost.png)','',
      'The protocol records SHA-256 hashes of the engine and runner before model calls. Analysis checks those hashes. All completed requests and responses, candidate menus, selected probabilities, exact AST states, per-step costs, and terminal outcomes are retained. Offline tests checked reference trajectories, all candidate transformations along sampled random walks, and the major spending/loop guards.','',
      '## Limitations','',
      '- Only one fixed equation per difficulty was tested. Eight repeated menu seeds do not constitute eight independent algebra problems. This is a mechanism demonstration, not evidence of broad algebra competence.',
      '- The three difficulties vary expression size and rewrite depth, not mathematical class: all are linear in one variable. Quadratics, domain restrictions, identities, contradictions, and branching solution sets were not tested.',
      '- The reference policy is not optimal, and its D changes reflect representation and tie-breaking. A model action can improve the true planning problem without reducing D immediately, or reduce D by more than one through a different valid route.',
      '- Supplied action explanations, replacements, legality checks, memory, and guarded termination are substantial scaffolding. This supports conclusions about Jev as a controller inside this environment, not standalone arithmetic or unrestricted tool use.',
      '- The model sees recent history and budgets but not explicit feedback about D. Stagnation stopping nevertheless uses that evaluator metric. A real deployment would need a similarly trustworthy progress check.',
      '- 95% Wilson intervals describe uncertainty from these repeated menu/model trials conditional on each fixed equation and protocol. They should not be read as population-level confidence bounds for arbitrary equations.',
      '- Model outputs need not be deterministic even with fixed menus. Rerunning the analysis reproduces the figures; fresh API calls may give different trajectories.','',
      '## Files and use','',
      '- `step_viewer.html`: open locally to select any of the 48 runs and inspect every step and its complete menu.',
      '- `three_series_by_step.jsonl`: three difficulty entries per decision index for prespecified seed 0. Entries become null after termination; no artificial continuation.',
      '- `steps/*.jsonl`: full per-step records; `episodes/*.json`: complete episode summaries and trajectories.',
      '- `raw/*.json`: exact requests and responses, without credentials. `budget.json`: persistent global ledger.',
      '- `results.json`: machine-readable statistics. `figures/*.png`: 300 dpi plots; `figures/*.svg`: scalable editable figures.',
      '- `analyze_and_plot.py`: regenerate every chart/report locally without model calls: `python analyze_and_plot.py`.',
      '- `algebra_engine.py`, `run_experiment.py`, `test_engine.py`, `test_safeguards.py`: frozen controller environment and offline checks. The runner refuses to overwrite an existing protocol; it never launches billable calls without `--execute`.','',
      '## Equations and hidden solutions','',
      'These answers are disclosed here for audit; they were never included in the model request.','']
    for l in LEVELS:
        e=protocol['equations'][l]
        lines += [f'### {NAMES[l]}', '',f'```text\n{e["equation"]}\n```','',f'Exact solution: `x = {e["hidden_solution"]}`. Initial reference workload: {e["initial_reference_steps"]} transformations.','']
    (ROOT/'REPORT.md').write_text('\n'.join(lines))

if __name__=='__main__':main()
