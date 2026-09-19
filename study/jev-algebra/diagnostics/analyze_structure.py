"""Exploratory, offline failure localisation. No API calls; no causal claims."""
import json
from pathlib import Path
import statistics
import sys
from collections import Counter
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from algebra_engine import state_nodes,walk
from analyze_and_plot import plt
from scipy.stats import spearmanr

OUT=Path(__file__).resolve().parent
def freeze(x):return tuple(freeze(v) for v in x) if isinstance(x,list) else x
def average(rows,key):return statistics.mean(r[key] for r in rows)

def main():
    scores={(r['episode_id'],r['step_i']):r for r in map(json.loads,(ROOT/'probability_scores.jsonl').read_text().splitlines())}
    features=[]
    for file in sorted((ROOT/'episodes').glob('jev_*.json')):
        episode=json.loads(file.read_text());state=freeze(episode['initial_ast'])
        for step in episode['trajectory']:
            scored=scores[(episode['episode_id'],step['step_i'])]
            raw=json.loads((ROOT/'raw'/f'{episode["episode_id"]}_{step["step_i"]:03d}.json').read_text())
            selected=next((o for o in scored['options'] if o['selected']),None)
            nodes=[(path,node) for side in state for path,node in walk(side)]
            features.append({'episode':episode['episode_id'],'level':episode['level'],'step':step['step_i'],
                'nodes':state_nodes(state),'depth':max(len(path) for path,node in nodes),
                'input_tokens':raw['response']['usage']['input_tokens'],
                'quality':scored['probability_quality'],'pair_alignment':scored['pairwise_alignment'],
                'remaining_work':scored['D_before'],
                'improving_actions_offered':sum(o['delta_D']>0 for o in scored['options']),
                'expected_regret':scored['expected_regret_steps'],'selected_kind':scored['selected_kind'],
                'selected_target_depth':len(step['action']['path']),
                'selected_regret':selected['regret_steps'] if selected else None,
                'selected_probability':selected['probability_raw'] if selected else None,
                'selected_delta':selected['delta_D'] if selected else None,
                'node_change':state_nodes(freeze(step['after_ast']))-state_nodes(state)})
            state=freeze(step['after_ast'])
    groups={
        'Outermost distribution':[r for r in features if r['selected_kind']=='distribute' and r['selected_target_depth']==0],
        'Nested distribution':[r for r in features if r['selected_kind']=='distribute' and r['selected_target_depth']>0],
        'Multiply both sides':[r for r in features if r['selected_kind']=='multiply'],
        'Simplify one product':[r for r in features if r['selected_kind']=='simplify_product'],
        'Combine like terms':[r for r in features if r['selected_kind']=='combine']}
    stats={k:{'n':len(rows),'non_best_choices':sum(r['selected_regret']>0 for r in rows),
              'non_best_fraction':sum(r['selected_regret']>0 for r in rows)/len(rows),
              'increased_remaining_work':sum(r['selected_delta']<0 for r in rows),
              'mean_selected_regret':average(rows,'selected_regret'),
              'mean_node_change':average(rows,'node_change')} for k,rows in groups.items()}
    correlations={}
    for level in ['medium','unholy']:
        rows=[r for r in features if r['level']==level]
        correlations[level]={'n_turns':len(rows),'spearman_with_probability_quality':{
            k:float(spearmanr([r[k] for r in rows],[r['quality'] for r in rows]).statistic)
            for k in ['nodes','depth','input_tokens','remaining_work','improving_actions_offered','step']}}
    high=[r for r in features if r['selected_probability'] is not None and r['selected_probability']>=.8]
    result={'status':'Exploratory, post-hoc descriptive analysis; no p-values or causal attribution.',
        'extra_api_calls':0,'extra_cost_usd':0,'turns':len(features),'independent_problem_templates':3,
        'operation_groups':stats,'within_level_correlations':correlations,
        'high_reported_probability':{'threshold':.8,'n':len(high),'non_best_choices':sum(r['selected_regret']>0 for r in high)},
        'menus_without_immediate_improvement':sum(r['improving_actions_offered']==0 for r in features),
        'rerolls':sum(r['selected_kind']=='reroll' for r in features),
        'rerolls_without_improving_option':sum(r['selected_kind']=='reroll' and r['improving_actions_offered']==0 for r in features),
        'input_token_range':[min(r['input_tokens'] for r in features),max(r['input_tokens'] for r in features)]}
    (OUT/'structure_summary.json').write_text(json.dumps(result,indent=2))
    with (OUT/'turn_features.jsonl').open('w') as f:
        for r in features:f.write(json.dumps(r)+'\n')

    fig,axs=plt.subplots(1,2,figsize=(12,5.5));fig.subplots_adjust(top=.77,bottom=.28,left=.24,right=.96,wspace=.62)
    fig.suptitle('Exploratory weakness signals in the saved Jev traces',y=.97,fontweight='bold')
    fig.text(.5,.89,'Associations under the frozen reference metric; these do not establish model-internal causes.',ha='center',fontsize=10)
    names=list(stats);ys=list(range(len(names)));vals=[stats[n]['non_best_fraction'] for n in names]
    axs[0].barh(ys,vals,color=['#D55E00','#D55E00','#CC79A7','#0072B2','#0072B2'],alpha=.8)
    axs[0].set_yticks(ys,names,fontsize=9);axs[0].invert_yaxis();axs[0].set_xlim(0,1.18)
    axs[0].set_xlabel('Fraction with a better offered move');axs[0].set_title('Action chosen, then compared with alternatives',fontsize=10)
    for i,n in enumerate(names):axs[0].text(vals[i]+.025,i,f'{stats[n]["non_best_choices"]}/{stats[n]["n"]}',va='center',fontsize=9)
    c=correlations['unholy']['spearman_with_probability_quality'];keys=['depth','nodes','input_tokens']
    axs[1].barh(range(3),[c[k] for k in keys],color=['#009E73','#009E73','#777777'],alpha=.8)
    axs[1].set_yticks(range(3),['Expression depth','Expression nodes','Prompt tokens'],fontsize=9);axs[1].invert_yaxis()
    axs[1].set_xlim(-.42,.08);axs[1].axvline(0,color='#555555',lw=.8)
    axs[1].set_xlabel('Spearman correlation with probability quality');axs[1].set_title('Unholy equation: 484 observed turns',fontsize=10)
    for i,k in enumerate(keys):axs[1].text(c[k]-.014,i,f'{c[k]:.3f}',ha='right',va='center',fontsize=9)
    fig.text(.12,.10,'Left: conditional on the chosen operation; action groups visit different states. Better means lower reference workload, not a proven shorter path.\nRight: turns within trajectories are correlated. Depth, stage and expression size also covary. No independent prompt intervention was run.\nThe reference policy itself prefers inner simplification, so its operation-order bias must be tested before attributing a model weakness.',fontsize=9)
    for ext in ['png','svg']:fig.savefig(OUT/f'structure_diagnostics.{ext}',dpi=300,bbox_inches='tight')
    plt.close(fig)
    report(result)
    print(json.dumps(result,indent=2))

def report(result):
    lines=['# Locating behavioural weaknesses in Jev: exploratory analysis','',
        'This analysis reuses the completed algebra experiment. It makes no new model calls and adds no model charges. It can generate hypotheses and identify observable risk conditions; it cannot uniquely identify an internal architectural cause.','',
        '## What the saved data shows','',
        '| Selected operation | Choices | A lower-work alternative was offered | Fraction |',
        '|---|---:|---:|---:|']
    for k,s in result['operation_groups'].items():lines.append(f'| {k} | {s["n"]} | {s["non_best_choices"]} | {s["non_best_fraction"]:.1%} |')
    lines += ['',
        'This localizes disagreement with the reference policy primarily to the order and scope of transformations. It does not establish that all of these actions were globally poor: the reference policy itself prioritizes inner simplification, and an expansion can be useful over multiple steps. The percentages are conditional on actions Jev chose in different states, not randomized comparisons of operation types.','',
        '**Reported probability is not a sufficient guard.** Of 218 selected algebra moves assigned probability at least 0.8, 36 had an offered alternative requiring fewer reference steps. This threshold is an exploratory slice, not a calibrated risk rule.','',
        '**Structure and prompt length are different hypotheses.** Within the 484 turns of the unholy equation, probability-quality Spearman correlations are −0.317 with expression depth, −0.252 with node count, and −0.023 with input-token count. This supports investigating structural decision difficulty; it does not prove a causal depth effect or rule out prompt semantics. The dataset spans only 1,135–3,621 input tokens and cannot establish long-context limits.','',
        '**The environment contributes failures.** 77/689 menus had no immediate reference-work improvement. Of 35 rerolls, 33 occurred on those menus. All three actual reroll cutoffs followed three menus without an immediately improving action. These outcomes cannot be attributed entirely to the model.','',
        '![Exploratory structure diagnostics](structure_diagnostics.png)','',
        '## Why causal attribution is not yet possible','',
        'There are 689 sequential observations but only three original equations, one prompt design, and one action-generator design. The same trajectories link depth, solve stage, remaining work, recent history, action types, and prompt size. Counterfactual algebra outcomes are known for every offered action, but the model’s counterfactual response to different wording is not. Our fixed reference policy also embeds a preference about operation order.','',
        'A weak score may therefore reflect a model preference, a misleading description, mismatch with the supplied strategy, insufficient menu coverage, or the reference metric. Multiple internal mechanisms can generate the same observed behaviour. Avoid claims such as a specific attention failure, context saturation, or a model capacity ceiling from these traces alone.','',
        '## Controlled follow-up design','',
        '1. Audit the evaluator first. Use proven shortest paths where tractable on small states, and additional fixed reference policies or explicitly bounded lookahead for larger states. Report disagreement between evaluators; do not treat an unfinished search as proof that an action is bad.',
        '2. Freeze diagnostic states and legal menus. Include high/low scores, nested and flat forms, early/late stages, and scarce/abundant useful moves. Replaying fixed states prevents changed trajectories from confounding prompt comparisons.',
        '3. Vary wording while keeping mathematical information fixed: current action descriptions versus neutral operation descriptions, concise versus verbose presentation, and equivalent equation renderings with unambiguous target locations. Shuffle labels/order independently and repeat requests to estimate output variability.',
        '4. Test added strategic support separately. Explicit precedence rules or dependency annotations add information, so an improvement should be described as a benefit from scaffolding rather than merely better wording.',
        '5. Generate new equation families with separately varied nesting depth, branching, coefficient magnitude, signs/fractions, and required horizon. Match menu composition and reference-quality gaps where possible. Keep some entire equation templates held out.',
        '6. Analyse paired changes in expected regret, ranking, reroll mass and distribution shift at the same state. Cluster uncertainty by source equation/run rather than treating individual turns as independent. For any predictive failure model, split by equation family, not random turns.',
        '7. Confirm a promising change in fresh end-to-end rollouts. Static decision improvements may not translate into fewer steps or fewer cutoffs once the trajectory changes.','',
        'Interpretation: a formatting rescue implicates representation sensitivity; a wording rescue implicates description sensitivity; a rescue only with added precedence guidance indicates dependence on planning support; persistent depth-related degradation across these controls establishes a behavioural capability boundary under those tested conditions. None alone uniquely identifies an internal mechanism.','',
        'The first targeted comparison should be **outer expansion versus inner cleanup on identical saved states**, with neutral/current descriptions and an independent evaluator. This directly tests the strongest observed pattern at low experimental scope.','',
        '## Artifacts','',
        '- `turn_features.jsonl`: structural, prompt-length, menu and outcome features for each observed turn.',
        '- `structure_summary.json`: exact counts and descriptive correlations.',
        '- `structure_diagnostics.png` / `.svg`: exploratory figure.',
        '- `analyze_structure.py`: reproducible offline analysis; requires the parent experiment files and scipy in addition to its plotting dependencies.','']
    (OUT/'REPORT.md').write_text('\n'.join(lines))

if __name__=='__main__':main()
