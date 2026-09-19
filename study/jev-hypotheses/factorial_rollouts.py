"""LABELLED FOLLOW-UP: complete the prompt-factorial trajectory experiment.

The original 48 trajectory results were seen before this extension was proposed.
Six remaining prompt cells are run on the SAME eight equations and two seeds.
This is mechanistic follow-up, not a new independent confirmation/holdout set.
No paid calls except with explicit --execute. Transport and the persistent global
$2 ledger are reused from campaign.py; this script does not reset spending.
"""
from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import fcntl
import json
import random
import time
import statistics as st
import numpy as np

import campaign as c
from prompt_arms import VARIANTS, make_payload
from analyze_rollouts import validate_episode, summarize_group

OUT = Path(__file__).resolve().parent
PROTOCOL = OUT / 'factorial_rollout_protocol.json'
TASKS = OUT / 'factorial_rollout_tasks.json'
VARIANT_MAP = {v['id']: v for v in VARIANTS}
BASE_ID = c.BASE['id']
COMBINED_ID = c.COMBINED['id']
REMAINING = [v for v in VARIANTS if v['id'] not in (BASE_ID, COMBINED_ID)]
NOTICE = ('LABELLED FOLLOW-UP initiated after the original 48 rollout outcomes were observed. '
          'The same eight equations and two seeds are reused. This is not an independent '
          'confirmation or a fresh holdout; no winning arm is automatically confirmed.')


def prepare():
    assert not PROTOCOL.exists(), 'Follow-up protocol already frozen; do not overwrite it.'
    originals = list((OUT / 'rollouts').glob('*.json'))
    assert len(originals) == 48, 'Expected completed original 48 episodes before follow-up.'
    tasks = [{'case_id': case['id'], 'variant_id': variant['id'], 'repeat': rep}
             for case in json.loads((OUT / 'rollout_cases.json').read_text())
             for variant in REMAINING for rep in range(2)]
    assert len(tasks) == 96
    random.Random(2026091902).shuffle(tasks)
    c.write(TASKS, tasks)
    protected = ['factorial_rollouts.py', 'factorial_rollout_tasks.json', 'campaign.py',
                 'prompt_arms.py', 'rollout_cases.json', 'protocol.json']
    protocol = {
        'created_at': c.stamp(), 'notice': NOTICE, 'followup_after_original_results': True,
        'new_tasks': 96, 'reused_original_prompt_episodes': 32,
        'full_prompt_factorial_episodes': 128, 'coverage_episodes_reported_separately': 16,
        'cases': 8, 'repeats': 2, 'workers': 8, 'variants': VARIANTS,
        'remaining_variants': REMAINING, 'menu_policy': 'random',
        'guard_policy': 'Exactly the original campaign rollout guards, decision caps and RNG.',
        'shared_budget_path': str(OUT / 'budget.json'), 'combined_cap_usd': '2.00',
        'analysis': 'Paired full-factorial main effects and interactions on solve rate and '
                    'completion-budget score; case-cluster bootstrap is exploratory.',
        'source_sha256': {name: c.sha((OUT / name).read_bytes()) for name in protected},
        'original_rollout_sha256': {p.name: c.sha(p.read_bytes()) for p in originals},
        'engine_sha256': c.sha((c.OLD / 'algebra_engine.py').read_bytes()),
    }
    c.write(PROTOCOL, protocol)
    print(json.dumps({'new_tasks': 96, 'notice': NOTICE}, indent=2), flush=True)


def rollout(task, cases, api):
    ident = f'factorialrollout__{task["case_id"]}__{task["variant_id"]}__r{task["repeat"]}'
    path = OUT / 'factorial_rollouts' / f'{ident}.json'
    if path.exists():
        return json.loads(path.read_text())
    initial = c.freeze(cases[task['case_id']]['state'])
    state = initial; root = c.solution(state); d0 = c.distance(state)
    maxsteps = min(120, max(24, 4*d0+12)); stagnation = min(30, max(12, d0))
    best = d0; last_best = 0
    rng = random.Random(c.seed(task['case_id']) + task['repeat'])
    history = []; rows = []; visits = Counter({c.signature(state): 1})
    streak = total_rerolls = premature = 0; status = None; started = time.monotonic()
    variant = VARIANT_MAP[task['variant_id']]
    while status is None:
        step = len(rows) + 1
        if time.monotonic()-started > c.LIMITS['rollout_seconds']:
            status = 'cutoff_time'; break
        menu = c.sample_menu(state, rng, 'random')
        payload = make_payload(state, menu, history[-6:], variant,
            {'step': step, 'decisions': maxsteps, 'rerolls': total_rerolls,
             'reroll_total': 8, 'streak': streak, 'reroll_streak': 3})
        if len(json.dumps(payload).encode()) > c.LIMITS['request_bytes']:
            status = 'cutoff_context'; break
        try:
            body, raw = api.call(f'{ident}__s{step:03d}', payload)
        except c.Stop as error:
            status = 'cutoff_' + str(error); break
        if body is None:
            status = 'api_failure'; break
        label = body.get('answers', {}).get('answer', {}).get('choice')
        if label not in menu:
            status = 'invalid_label'; break
        action = menu[label]; before = state; state = c.apply(state, action)
        assert c.solution(state) == root
        d = c.distance(state)
        if action.kind == 'reroll':
            streak += 1; total_rerolls += 1
        else:
            streak = 0
        if action.kind == 'declare_solved':
            premature += 1
        if action.kind not in ('reroll', 'declare_solved'):
            visits[c.signature(state)] += 1
        if d < best:
            best = d; last_best = step
        if c.solved(state): status = 'solved'
        elif streak >= 3: status = 'cutoff_reroll_streak'
        elif total_rerolls >= 8: status = 'cutoff_reroll_total'
        elif visits[c.signature(state)] >= 3: status = 'cutoff_repeated_state'
        elif premature >= 2: status = 'cutoff_premature_completion'
        elif step-last_best >= stagnation: status = 'cutoff_stagnation'
        elif step >= maxsteps: status = 'cutoff_decisions'
        rows.append({'step': step, 'before': c.equation(before), 'after': c.equation(state),
            'after_ast': state, 'action': action.serial(), 'choice': label,
            'D_before': c.distance(before), 'D_after': d, 'best_D': best,
            'cost_usd': body.get('usage', {}).get('cost'), 'status': status})
        history.append({'action': c.describe(before, action), 'result': c.equation(state)})
        c.write(OUT / 'factorial_rollout_checkpoints' / f'{ident}.json', {'rows': rows})
    result = {'id': ident, **task, 'policy': task['variant_id'], 'variant': variant,
        'followup_after_original_results': True, 'initial_D': d0,
        'final_D': c.distance(state), 'best_D': best, 'status': status,
        'steps': len(rows), 'rerolls': total_rerolls, 'max_decisions': maxsteps,
        'stagnation_limit': stagnation, 'initial_equation': c.equation(initial),
        'final_equation': c.equation(state), 'exact_root': str(root), 'trajectory': rows}
    c.write(path, result)
    print(json.dumps({'followup_rollout': ident, 'status': status, 'steps': len(rows)}), flush=True)
    return result


def check_hashes():
    protocol = json.loads(PROTOCOL.read_text())
    for name, digest in protocol['source_sha256'].items():
        assert c.sha((OUT / name).read_bytes()) == digest, 'Frozen source changed: ' + name
    for name, digest in protocol['original_rollout_sha256'].items():
        assert c.sha((OUT / 'rollouts' / name).read_bytes()) == digest, 'Original episode changed: ' + name
    assert c.sha((c.OLD / 'algebra_engine.py').read_bytes()) == protocol['engine_sha256']


def execute():
    check_hashes()
    for directory in ['raw', 'factorial_rollouts', 'factorial_rollout_checkpoints']:
        (OUT / directory).mkdir(exist_ok=True)
    budget = c.Budget(); api = c.API(budget)
    cases = {r['id']: r for r in json.loads((OUT / 'rollout_cases.json').read_text())}
    tasks = json.loads(TASKS.read_text())
    started = time.monotonic(); done = 0
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(rollout, task, cases, api) for task in tasks]
            for future in as_completed(futures):
                future.result(); done += 1
                if done % 8 == 0:
                    c.write(OUT / 'factorial_rollout_progress.json', {'completed': done,
                        'seconds': time.monotonic()-started,
                        'global_exposure_usd': str(budget.exposure())})
    finally:
        api.client.close()
    c.write(OUT / 'factorial_rollout_completed.json', {'completed': done,
        'seconds': time.monotonic()-started, 'global_exposure_usd': str(budget.exposure()),
        'finished_at': c.stamp(), 'notice': NOTICE})


def bootstrap(values):
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(2026091903)
    samples = values[rng.integers(0, len(values), size=(20000, len(values)))].mean(axis=1)
    return [float(x) for x in np.quantile(samples, [.025, .975])]


def factor_effects(rows):
    """Average paired case/seed toggle differences over all other factor cells."""
    results = {}
    factors = ['neutral', 'structured', 'guided']
    for factor in factors:
        case_effects = []
        for case_id in sorted({r['case_id'] for r in rows}):
            groups = {flag: [r for r in rows if r['case_id'] == case_id and r['variant'][factor] == flag]
                      for flag in (False, True)}
            assert len(groups[False]) == len(groups[True]) == 8
            case_effects.append({'case_id': case_id,
                'solve_rate_difference': st.mean(int(r['solved']) for r in groups[True]) - st.mean(int(r['solved']) for r in groups[False]),
                'completion_budget_score_difference': st.mean(r['completion_budget_score'] for r in groups[True]) - st.mean(r['completion_budget_score'] for r in groups[False])})
        result = {'case_effects': case_effects}
        for metric in ['solve_rate_difference', 'completion_budget_score_difference']:
            values = [r[metric] for r in case_effects]
            result[metric] = st.mean(values)
            result[metric + '_case_bootstrap_95'] = bootstrap(values)
        results[factor] = result
    interactions = {}
    for i, first in enumerate(factors):
        for second in factors[i+1:]:
            values = []
            for case_id in sorted({r['case_id'] for r in rows}):
                cells = {(a,b): [r for r in rows if r['case_id'] == case_id and r['variant'][first] == a and r['variant'][second] == b]
                         for a in (False,True) for b in (False,True)}
                assert all(len(v) == 4 for v in cells.values())
                effects = {}
                for metric in ['solved', 'completion_budget_score']:
                    means = {k: st.mean(float(r[metric]) for r in group) for k, group in cells.items()}
                    effects[metric] = means[(True,True)] - means[(False,True)] - means[(True,False)] + means[(False,False)]
                values.append({'case_id': case_id, **effects})
            interactions[first + '_x_' + second] = {'case_effects': values,
                'solve_difference_in_differences': st.mean(r['solved'] for r in values),
                'completion_score_difference_in_differences': st.mean(r['completion_budget_score'] for r in values)}
    return results, interactions


def plots(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans', 'font.size':10,
        'axes.spines.top':False, 'axes.spines.right':False, 'svg.fonttype':'none'})
    folder = OUT / 'figures'; folder.mkdir(exist_ok=True)
    ids = [v['id'] for v in VARIANTS]
    labels = [f'N{int(v["neutral"])} S{int(v["structured"])} G{int(v["guided"])}' for v in VARIANTS]
    fig, axes = plt.subplots(1,2,figsize=(13,5),constrained_layout=True)
    counts = [summary['arms'][v]['solved'] for v in ids]
    colors = ['#3979AF' if v in (BASE_ID, COMBINED_ID) else '#8F63A6' for v in ids]
    axes[0].bar(range(8), np.array(counts)/16, color=colors)
    for i, count in enumerate(counts):
        axes[0].text(i,count/16+.025,f'{count}/16',ha='center')
    axes[0].set(ylim=(0,1.12),ylabel='Observed solve fraction',title='All eight prompt cells · random menus')
    axes[1].bar(range(8),[summary['arms'][v]['mean_completion_budget_score'] for v in ids],color=colors)
    axes[1].set(ylabel='Mean completion-budget score (lower better)',title='Failures assigned the same case decision cap')
    for ax in axes:
        ax.set_xticks(range(8),labels,rotation=40,ha='right');ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    fig.suptitle('FOLLOW-UP on the same equations after initial results were observed\nN: neutral wording · S: structure table · G: strategy guidance',fontsize=13)
    fig.supxlabel('Blue: reused original cells · purple: six additional cells · 8 cases × 2 repeats per cell',fontsize=10)
    for ext in ['png','svg']:
        fig.savefig(folder/f'factorial_rollout_cells.{ext}',dpi=240,bbox_inches='tight')
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.7),constrained_layout=True)
    factors=['neutral','structured','guided']; names=['Neutral wording','Structure table','Strategy guidance']
    for ax,metric,scale in [(axes[0],'solve_rate_difference',100),(axes[1],'completion_budget_score_difference',1)]:
        for i,factor in enumerate(factors):
            data=summary['factor_main_effects'][factor];mean=data[metric]*scale
            lo,hi=[x*scale for x in data[metric+'_case_bootstrap_95']]
            ax.errorbar(mean,i,xerr=np.array([[mean-lo],[hi-mean]]),fmt='o',color='#3979AF',capsize=5,lw=2)
        ax.axvline(0,color='#777777',lw=.8);ax.set_yticks(range(3),names);ax.invert_yaxis();ax.grid(axis='x',alpha=.18)
    axes[0].set(xlabel='Solve-rate change (percentage points; higher better)',title='Toggle effect averaged over other prompt factors')
    axes[1].set(xlabel='Completion-budget-score change (lower better)',title='Same paired case / seed factorial comparisons')
    fig.suptitle('Exploratory follow-up main effects · eight case clusters\nIntervals: case-cluster bootstrap, unadjusted; no new holdout confirmation',fontsize=13)
    for ext in ['png','svg']:
        fig.savefig(folder/f'factorial_rollout_effects.{ext}',dpi=240,bbox_inches='tight')
    plt.close(fig)


def analyze():
    check_hashes()
    tasks = json.loads(TASKS.read_text())
    expected = {(t['case_id'], t['variant_id'], t['repeat']) for t in tasks}
    new = [json.loads(p.read_text()) for p in sorted((OUT/'factorial_rollouts').glob('*.json'))]
    keys = [(r['case_id'],r['variant_id'],r['repeat']) for r in new]
    assert len(keys)==96 and len(set(keys))==96 and set(keys)==expected, f'Need exactly96new episodes, found{len(keys)}'
    cases={r['id']:r for r in json.loads((OUT/'rollout_cases.json').read_text())}
    rows=[];coverage=[]
    for path in sorted((OUT/'rollouts').glob('*.json')):
        raw=json.loads(path.read_text());row=validate_episode(raw,cases[raw['case_id']])
        if raw['policy']=='combined_coverage':coverage.append(row);continue
        row['variant_id']=BASE_ID if raw['policy']=='original_random' else COMBINED_ID
        row['variant']=VARIANT_MAP[row['variant_id']];row['source']='original_campaign';rows.append(row)
    for raw in new:
        row=validate_episode(raw,cases[raw['case_id']]);row.update(variant_id=raw['variant_id'],
            variant=VARIANT_MAP[raw['variant_id']],source='followup');rows.append(row)
    assert len(rows)==128 and len(coverage)==16
    assert all(sum(r['variant_id']==v['id'] for r in rows)==16 for v in VARIANTS)
    effects,interactions=factor_effects(rows)
    summary={'notice':NOTICE,'prompt_factorial_episodes':128,'new_episodes':96,'reused_original_episodes':32,
        'distinct_cases':8,'template_clusters':8,'genuinely_new_holdout_cases':0,
        'arms':{v['id']:summarize_group([r for r in rows if r['variant_id']==v['id']]) for v in VARIANTS},
        'by_original_split':{split:{v['id']:summarize_group([r for r in rows if r['variant_id']==v['id'] and r['split']==split]) for v in VARIANTS} for split in ['diagnostic','heldout']},
        'factor_main_effects':effects,'two_factor_interactions':interactions,
        'coverage_separate':summarize_group(coverage),'episode_metrics':rows,
        'new_recorded_decision_cost_usd':sum(r['recorded_decision_cost_usd'] for r in rows if r['source']=='followup'),
        'validation':'All128prompt trajectories replayed with exactroot checks;16coverage episodes also revalidated.'}
    c.write(OUT/'factorial_rollout_summary.json',summary)
    lines=['# Labelled follow-up: full prompt-factorial trajectories','', '**'+NOTICE+'**','',
        'The six missing prompt combinations were added to the original two random-menu combinations. This gives 128 episodes: eight prompt cells × eight equations × two seeds. The 16 guaranteed-coverage episodes remain separate because they change the menu algorithm. All actions were replayed, exact roots checked, and every solved claim verified as a literal `x = exact_root`.', '',
        '| Neutral | Structured | Guided | Solved | Mean stop decisions | Median successful decisions | Mean completion-budget score |',
        '|---|---|---|---:|---:|---:|---:|']
    for v in VARIANTS:
        a=summary['arms'][v['id']]
        med=a['median_decisions_successful_only']
        lines.append(f'| {int(v["neutral"])} | {int(v["structured"])} | {int(v["guided"])} | {a["solved"]}/16 | {a["mean_decisions_to_stop_all"]:.2f} | {med if med is not None else "—"} | {a["mean_completion_budget_score"]:.2f} |')
    lines += ['', 'Stop decisions include failures and do not measure speed to a correct solution. Successful-only counts condition on success. Completion-budget score uses actual decisions for solved episodes and the predeclared common case limit for failures; lower is better. This is a transparent failure penalty, not an imputed continuation.', '',
        '## Paired factorial main effects','',
        'Each effect compares a factor enabled versus disabled, averaged across the other four combinations, then the two repeats, within each equation. Case means receive equal weight. Intervals resample the eight case clusters 20,000 times; they are exploratory, unadjusted for multiple comparisons, and cannot create independence from the reused equations.', '',
        '| Toggle | Solve-rate difference, percentage points (95% case-bootstrap interval) | Completion-budget-score difference (95% interval) |',
        '|---|---:|---:|']
    for factor,effect in effects.items():
        lo,hi=effect['solve_rate_difference_case_bootstrap_95'];cl,ch=effect['completion_budget_score_difference_case_bootstrap_95']
        lines.append(f'| {factor} | {100*effect["solve_rate_difference"]:+.2f} ({100*lo:+.2f}, {100*hi:+.2f}) | {effect["completion_budget_score_difference"]:+.2f} ({cl:+.2f}, {ch:+.2f}) |')
    lines += ['', '## Two-factor interactions','',
        'Interactions are differences in differences, averaged over the third factor and repeats. A nonzero result indicates that the effect of one prompt change depends on the other; with eight reused cases these remain exploratory.', '',
        '| Factors | Solve difference in differences, percentage points | Completion-score difference in differences |',
        '|---|---:|---:|']
    for name,value in interactions.items():
        lines.append(f'| {name} | {100*value["solve_difference_in_differences"]:+.2f} | {value["completion_score_difference_in_differences"]:+.2f} |')
    lines += ['', '## Limits and interpretation','',
        'The original four-template holdout designation is preserved as metadata, but these follow-up results are not a new held-out confirmation: all eight equation trajectories had already been seen before this extension. Arm rankings can generate a hypothesis for genuinely new equations; selecting the best observed arm does not establish that it will be best elsewhere.', '',
        'All prompt cells use random menus with the same case/seed generator, root-preserving engine, and stopping safeguards. Their first menus match; later menus diverge when controller choices change the state. Eight cases and repeated trajectories do not establish an architectural limitation or a broad-domain conclusion. Neutral wording, structured representation, and added strategy guidance can interact. Guidance adds useful information, and the structure table also changes prompt length.', '',
        f'The separate combined-prompt/coverage policy solved **{len([r for r in coverage if r["solved"]])}/16**. Coverage uses deterministic reference scoring to guarantee a best-scored move is offered, so its success is external algorithmic support rather than an improved model.', '',
        f'Additional logged-decision cost: **${summary["new_recorded_decision_cost_usd"]:.8f}**. The unchanged shared campaign budget remains the authoritative global exposure ledger; any uncertain request charges are retained there.', '',
        '- [All eight prompt cells](figures/factorial_rollout_cells.png) ([SVG](figures/factorial_rollout_cells.svg))',
        '- [Factorial main effects](figures/factorial_rollout_effects.png) ([SVG](figures/factorial_rollout_effects.svg))',
        '- [Machine-readable summary](factorial_rollout_summary.json)', '']
    (OUT/'FACTORIAL_ROLLOUT_REPORT.md').write_text('\n'.join(lines))
    plots(summary)
    print(json.dumps({'arms':summary['arms'],'factor_main_effects':effects,
        'new_recorded_decision_cost_usd':summary['new_recorded_decision_cost_usd']},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--execute',action='store_true')
    parser.add_argument('--analyze',action='store_true');args=parser.parse_args()
    lock=(OUT/'campaign.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.prepare:prepare()
    if args.execute:execute()
    if args.analyze:analyze()
    if not any([args.prepare,args.execute,args.analyze]):print('No work requested. --prepare and --analyze are offline; only --execute calls the model.')


if __name__=='__main__':main()
