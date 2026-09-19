"""Offline analysis of all frozen fresh-equation confirmation trajectories.

No network or model calls. Use --allow-partial only for development: all output
is then prominently labelled partial, and denominator counts reflect observed
episodes. By default require the exact 48 frozen tasks with no missing/extras.
"""
from pathlib import Path
import argparse
import json
import sys
from collections import Counter
from decimal import Decimal
from fractions import Fraction
import statistics as st

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parent / 'jev-algebra'))
import algebra_engine as e
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

POLICIES = ['original_random', 'combined_random', 'combined_coverage']
NAMES = {'original_random': 'Original prompt · random menu',
         'combined_random': 'Combined prompt · random menu',
         'combined_coverage': 'Combined prompt · best move covered'}
COLORS = dict(zip(POLICIES, ['#2878B5', '#E68120', '#289777']))


def freeze(value):
    return tuple(freeze(v) for v in value) if isinstance(value, list) else value


def restore(a):
    return e.Action(a['kind'], a['side'], tuple(a['path']), a['i'], a['j'], Fraction(a['arg']))


def validate_episode(row, case):
    state = freeze(case['state'])
    root = e.solution(state)
    initial_D = e.distance(state)
    assert row['exact_root'] == str(root), row['id']
    assert row['initial_D'] == initial_D, row['id']
    assert row['steps'] == len(row['trajectory']), row['id']
    assert row['initial_equation'] == e.equation(state), row['id']
    best_D = initial_D
    for i, step in enumerate(row['trajectory'], 1):
        assert step['step'] == i, row['id']
        assert step['before'] == e.equation(state), row['id']
        assert step['D_before'] == e.distance(state), row['id']
        action = restore(step['action'])
        assert action.kind == 'reroll' or action in e.all_actions(state), (row['id'], i)
        nxt = e.apply(state, action)
        assert nxt == freeze(step['after_ast']), (row['id'], i)
        assert e.solution(nxt) == root, (row['id'], i)
        assert step['after'] == e.equation(nxt), (row['id'], i)
        assert step['D_after'] == e.distance(nxt), (row['id'], i)
        best_D = min(best_D, step['D_after'])
        assert step['best_D'] == best_D, (row['id'], i)
        state = nxt
    assert row['final_D'] == e.distance(state), row['id']
    assert row['best_D'] == best_D, row['id']
    assert row['final_equation'] == e.equation(state), row['id']
    if row['status'] == 'solved':
        assert state[0] == e.X and state[1][0] == 'n', row['id']
        assert e.number(state[1]) == root, row['id']
        assert e.solved(state) and e.distance(state) == 0, row['id']
    else:
        assert not e.solved(state), row['id']
    return {
        'id': row['id'], 'case_id': row['case_id'], 'family': case['family'],
        'split': case['split'], 'policy': row['policy'], 'repeat': row['repeat'],
        'solved': row['status'] == 'solved', 'status': row['status'],
        'decisions_to_stop': row['steps'], 'max_decisions': row['max_decisions'],
        'solved_decisions': row['steps'] if row['status'] == 'solved' else None,
        'completion_budget_score': row['steps'] if row['status'] == 'solved' else row['max_decisions'],
        'initial_D': initial_D, 'final_D': row['final_D'], 'best_D': best_D,
        'final_progress': 1 - row['final_D'] / initial_D,
        'best_progress': 1 - best_D / initial_D,
        'algebra_edits': sum(r['action']['kind'] not in ('reroll', 'declare_solved') for r in row['trajectory']),
        'rerolls': row['rerolls'],
        'recorded_decision_cost_usd': float(sum((Decimal(str(r['cost_usd'] or 0)) for r in row['trajectory']), Decimal(0))),
    }


def average(values):
    return st.mean(values) if values else None


def median(values):
    return st.median(values) if values else None


def summarize_group(rows):
    successes = [r for r in rows if r['solved']]
    return {
        'episodes': len(rows), 'distinct_cases': len({r['case_id'] for r in rows}),
        'solved': len(successes), 'solve_rate': len(successes) / len(rows) if rows else None,
        'status_counts': dict(Counter(r['status'] for r in rows)),
        'mean_decisions_to_stop_all': average([r['decisions_to_stop'] for r in rows]),
        'median_decisions_to_stop_all': median([r['decisions_to_stop'] for r in rows]),
        'mean_decisions_successful_only': average([r['decisions_to_stop'] for r in successes]),
        'median_decisions_successful_only': median([r['decisions_to_stop'] for r in successes]),
        'mean_completion_budget_score': average([r['completion_budget_score'] for r in rows]),
        'mean_final_progress': average([r['final_progress'] for r in rows]),
        'mean_best_progress': average([r['best_progress'] for r in rows]),
        'recorded_decision_cost_usd': sum(r['recorded_decision_cost_usd'] for r in rows),
    }


def compare(rows, control, treatment):
    lookup = {(r['case_id'], r['repeat'], r['policy']): r for r in rows}
    pairs = []
    for case_id, rep in sorted({(r['case_id'], r['repeat']) for r in rows}):
        a = lookup.get((case_id, rep, control)); b = lookup.get((case_id, rep, treatment))
        if a is None or b is None:
            continue
        assert a['max_decisions'] == b['max_decisions']
        pairs.append({
            'case_id': case_id, 'repeat': rep, 'split': a['split'],
            'control_solved': a['solved'], 'treatment_solved': b['solved'],
            'solve_difference': int(b['solved']) - int(a['solved']),
            'joint_success_step_difference': b['solved_decisions'] - a['solved_decisions'] if a['solved'] and b['solved'] else None,
            'completion_budget_score_difference': b['completion_budget_score'] - a['completion_budget_score'],
        })
    case_differences = []
    for case_id in sorted({p['case_id'] for p in pairs}):
        group = [p for p in pairs if p['case_id'] == case_id]
        case_differences.append({'case_id': case_id, 'paired_repeats': len(group),
            'mean_solve_difference': average([p['solve_difference'] for p in group]),
            'mean_completion_budget_score_difference': average([p['completion_budget_score_difference'] for p in group])})
    jointly_solved = [p['joint_success_step_difference'] for p in pairs if p['joint_success_step_difference'] is not None]
    return {
        'control': control, 'treatment': treatment, 'matched_pairs': len(pairs),
        'rescued_pairs': sum(p['solve_difference'] == 1 for p in pairs),
        'regressed_pairs': sum(p['solve_difference'] == -1 for p in pairs),
        'both_solved_pairs': sum(p['control_solved'] and p['treatment_solved'] for p in pairs),
        'neither_solved_pairs': sum(not p['control_solved'] and not p['treatment_solved'] for p in pairs),
        'cases_with_any_rescue': len({p['case_id'] for p in pairs if p['solve_difference'] == 1}),
        'cases_with_any_regression': len({p['case_id'] for p in pairs if p['solve_difference'] == -1}),
        'cases_net_improved': sum(p['mean_solve_difference'] > 0 for p in case_differences),
        'cases_net_regressed': sum(p['mean_solve_difference'] < 0 for p in case_differences),
        'case_equal_mean_solve_difference': average([p['mean_solve_difference'] for p in case_differences]),
        'mean_step_difference_joint_success_only': average(jointly_solved),
        'median_step_difference_joint_success_only': median(jointly_solved),
        'case_equal_mean_completion_budget_score_difference': average([p['mean_completion_budget_score_difference'] for p in case_differences]),
        'pairs': pairs, 'case_differences': case_differences,
    }


def save_figure(fig, name):
    target = OUT / 'figures'
    target.mkdir(exist_ok=True)
    for suffix in ['png', 'svg']:
        fig.savefig(target / f'{name}.{suffix}', dpi=240, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def plots(episodes, rows, cases, partial):
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True,
        'grid.alpha': 0.18, 'svg.fonttype': 'none'})
    prefix = 'PARTIAL — ' if partial else ''
    ordered = sorted(cases)
    fig, axes = plt.subplots(4, 2, figsize=(13, 14), constrained_layout=True)
    for ax, case_id in zip(axes.flat, ordered):
        case = cases[case_id]
        group = [r for r in episodes if r['case_id'] == case_id]
        maxstep = max([r['steps'] for r in group] or [1])
        for r in sorted(group, key=lambda r: (r['policy'], r['repeat'])):
            x = [0] + [s['step'] for s in r['trajectory']]
            y = [1.0] + [s['D_after'] / r['initial_D'] for s in r['trajectory']]
            color = COLORS[r['policy']]
            ax.plot(x, y, color=color, lw=1.6, alpha=.82,
                    linestyle='-' if r['repeat'] == 0 else '--')
            ax.scatter([x[-1]], [y[-1]], color=color, s=48, zorder=5,
                       marker='o' if r['status'] == 'solved' else 'X', edgecolors='white', linewidth=.4)
            for s in r['trajectory']:
                if s['action']['kind'] == 'reroll':
                    ax.scatter(s['step'], s['D_after'] / r['initial_D'], marker='|', s=70, color=color, alpha=.7)
        ax.axhline(0, color='#555555', linewidth=.6)
        ax.axhline(1, color='#888888', linewidth=.6, linestyle=':')
        ax.set_xlim(0, maxstep + 1)
        ax.set_ylim(bottom=-.06)
        ax.set_title(f'{case["family"].replace("_", " ")}  [{case["split"]}]', loc='left', fontsize=11)
        ax.set_xlabel('Decision step (rerolls included)')
        ax.set_ylabel('Remaining reference steps / initial')
    handles = [plt.Line2D([0], [0], color=COLORS[p], lw=2, label=NAMES[p]) for p in POLICIES]
    handles += [plt.Line2D([0], [0], color='#555555', marker='o', linestyle='', label='Solved'),
                plt.Line2D([0], [0], color='#555555', marker='X', linestyle='', label='Cutoff / failure')]
    fig.legend(handles=handles, loc='outside lower center', ncol=3, frameon=False)
    fig.suptitle(prefix + 'Fresh equation trajectories: all observed runs\nSolid / dashed = repeat 0 / 1; vertical ticks = rerolls; no trajectories extended beyond stopping', fontsize=14)
    save_figure(fig, 'rollout_trajectories')

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)
    ax = axes[0]
    maximum = max([r['max_decisions'] for r in rows] or [1])
    for p in POLICIES:
        group = [r for r in rows if r['policy'] == p]
        if not group:
            continue
        x = np.arange(maximum + 1)
        y = [sum(r['solved'] and r['decisions_to_stop'] <= t for r in group) / len(group) for t in x]
        ax.step(x, y, where='post', color=COLORS[p], label=NAMES[p], lw=2)
    ax.set(xlabel='Decision allowance', ylabel='Fraction of episodes solved', ylim=(-.025, 1.05), title='Observed cumulative completions')
    ax.text(.03, .95, 'All episodes remain in denominator.\nEarly failures never count as fast solves.', transform=ax.transAxes, va='top', fontsize=9)
    ax = axes[1]
    xs = np.arange(3)
    for j, split in enumerate(['diagnostic', 'heldout']):
        rates = []
        for p in POLICIES:
            group = [r for r in rows if r['policy'] == p and r['split'] == split]
            rates.append(sum(r['solved'] for r in group) / len(group) if group else 0)
        bars = ax.bar(xs + (j-.5)*.34, rates, width=.32, color=[COLORS[p] for p in POLICIES], alpha=1 if j else .48, hatch='//' if j else None)
        for bar, p in zip(bars, POLICIES):
            group = [r for r in rows if r['policy'] == p and r['split'] == split]
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+.025, f'{sum(r["solved"] for r in group)}/{len(group)}', ha='center', fontsize=9)
    ax.set(xticks=xs, xticklabels=['Original\nrandom', 'Combined\nrandom', 'Combined\ncoverage'], ylim=(0, 1.17), ylabel='Solved / observed episodes', title='Template-held-out confirmation')
    ax.text(.02, .96, 'Faded: diagnostic · hatched: held-out', transform=ax.transAxes, fontsize=9, va='top')
    ax = axes[2]
    for k, (a, b) in enumerate([('original_random', 'combined_random'), ('combined_random', 'combined_coverage')]):
        comp = compare(rows, a, b)
        diffs = [r['mean_completion_budget_score_difference'] for r in comp['case_differences']]
        jitter = np.linspace(-.12, .12, len(diffs))
        ax.scatter(np.full(len(diffs), k)+jitter, diffs, color=COLORS[b], s=42, alpha=.85)
        if diffs:
            ax.plot([k-.18, k+.18], [st.mean(diffs)]*2, color='#222222', lw=2)
    ax.axhline(0, color='#666666', lw=.8)
    ax.set(xticks=[0,1], xticklabels=['Combined − original\nsame random policy', 'Coverage − random\nsame combined prompt'], ylabel='Difference in completion-budget score', title='Paired case means (lower is better)')
    ax.text(.02, .04, 'Unsolved = common case decision cap.\nDots: cases; bars: equal-case means.', transform=ax.transAxes, fontsize=9)
    fig.suptitle(prefix + 'Fresh rollout outcomes — 8 equations × 3 policies × 2 repeats', fontsize=14)
    save_figure(fig, 'rollout_outcomes')


def number(value, digits=2):
    return '—' if value is None else f'{value:.{digits}f}'


def report(summary):
    lines = ['# Fresh equation rollout confirmation', '',
        '**PARTIAL DEVELOPMENT OUTPUT.**' if summary['partial'] else '**Complete frozen confirmation set: 48 episodes on eight fresh equations.**', '',
        'All completed trajectories were replayed from their frozen starting AST. Every action preserved the exact rational root. Every reported solution ended literally `x = exact_root`. This validation checks the algebra engine and outcome records; the model selects operations and the engine performs arithmetic.', '',
        'Three policies were fixed before inference: original prompt with random menus, combined prompt with random menus, and combined prompt with one best-reference-cost action guaranteed in each menu. The combined prompt joins neutral operation wording, structured expression presentation, and explicit strategy guidance. It was prespecified rather than chosen as the best arm after looking at results.', '',
        '| Policy | Solved | Mean decisions to stop, all | Median decisions, successes only | Mean completion-budget score |',
        '|---|---:|---:|---:|---:|']
    for p in POLICIES:
        s = summary['policies'][p]
        lines.append(f'| {NAMES[p]} | {s["solved"]}/{s["episodes"]} | {number(s["mean_decisions_to_stop_all"])} | {number(s["median_decisions_successful_only"])} | {number(s["mean_completion_budget_score"])} |')
    lines += ['', '**An early cutoff is not a fast solution.** Decisions to stop describe resources consumed, including failed attempts. Successful-only step counts condition on success and can be selection-biased. Completion-budget score assigns each solved episode its actual decisions and each unsolved episode its common, predeclared case decision cap. It is a conservative evaluation penalty, not invented continuation data or an estimate of how many steps a failed run would eventually need.', '',
        '## Paired comparisons', '', 'Pairs share the same case and repeat seed. Menus are coupled only while states and random-menu generation remain identical; once actions diverge, future menus differ. The coverage policy deliberately changes the menu generator.', '']
    for c in summary['comparisons']:
        lines += [f'### {NAMES[c["treatment"]]} versus {NAMES[c["control"]]}', '',
            f'- Matched episodes: **{c["matched_pairs"]}**. Rescued failures: **{c["rescued_pairs"]}**. Regressed successes: **{c["regressed_pairs"]}**. Both solved: **{c["both_solved_pairs"]}**. Neither solved: **{c["neither_solved_pairs"]}**.',
            f'- Cases with at least one rescue: **{c["cases_with_any_rescue"]}**; at least one regression: **{c["cases_with_any_regression"]}**. These sets can overlap across repeats. Net improved cases: **{c["cases_net_improved"]}**; net regressed cases: **{c["cases_net_regressed"]}**.',
            f'- Equal-case mean solve-rate difference: **{number(100*c["case_equal_mean_solve_difference"] if c["case_equal_mean_solve_difference"] is not None else None)} percentage points**.',
            f'- Mean treatment minus control decisions among jointly solved pairs: **{number(c["mean_step_difference_joint_success_only"])}** (negative favours treatment).',
            f'- Equal-case mean completion-budget-score difference: **{number(c["case_equal_mean_completion_budget_score_difference"])}** (negative favours treatment).', '']
    lines += ['## Held-out templates', '', '| Policy | Diagnostic solved | Held-out solved |', '|---|---:|---:|']
    for p in POLICIES:
        d = summary['by_split']['diagnostic'][p]; h = summary['by_split']['heldout'][p]
        lines.append(f'| {NAMES[p]} | {d["solved"]}/{d["episodes"]} | {h["solved"]}/{h["episodes"]} |')
    lines += ['', 'There are eight distinct equations and eight template clusters, four reserved as held-out before model calls. Two repeats per equation are not two independent equation families. Descriptive paired counts and equal-case means are primary here; these small samples do not justify a broad-domain capability claim.', '',
        '## Stopping reasons', '', '| Policy | Reason | Episodes |', '|---|---|---:|']
    for p in POLICIES:
        for reason, count in sorted(summary['policies'][p]['status_counts'].items()):
            lines.append(f'| {NAMES[p]} | {reason} | {count} |')
    lines += ['', '## Interpretation', '']
    c = summary['comparisons'][0]
    delta = c['case_equal_mean_solve_difference']
    if delta is None:
        lines.append('Insufficient paired episodes to compare the combined and original prompts.')
    elif delta > 0:
        lines.append('The combined prompt improved observed fresh-equation solve rate under the same random-menu policy in this confirmation set. This is evidence for useful external scaffolding under these conditions; it does not identify an internal mechanism or establish a general capability gain.')
    elif delta < 0:
        lines.append('The combined prompt reduced observed fresh-equation solve rate under the same random-menu policy in this confirmation set. A stronger local distribution score would therefore not, on its own, establish a better end-to-end controller.')
    else:
        lines.append('The combined prompt did not change aggregate observed fresh-equation solve rate under the same random-menu policy. Paired rescues, regressions, jointly solved step counts, and cutoffs still describe differences concealed by equal aggregate rates.')
    lines += ['', 'The guaranteed-coverage policy uses the reference evaluator to ensure a best-scored action is offered. Any rescue in that arm demonstrates the value of algorithmic menu support. It must not be attributed to an improvement in the model itself, and comparison with the combined-random arm isolates the change in menu policy more directly than comparison with the original prompt.', '',
        'Reference distance is remaining work under a fixed deterministic strategy, not a proven globally shortest path. Trajectory plots show every observed decision, including rerolls; they stop at actual terminal points and use explicit failure markers. The cumulative-completion chart keeps failures in the denominator and reports observed completion fractions, not a Kaplan–Meier estimate relying on independent censoring.', '',
        '## Files and cost', '',
        f'Recorded valid-decision cost: **${summary["recorded_decision_cost_usd"]:.8f}**. This would exclude any charged request without a logged action; the final campaign audit reconciles all requests. See the campaign budget for the global charge and reservation audit.', '',
        f'Rollout-related budget exposure found at analysis time: **{summary["rollout_budget_exposure_usd"]} USD**, including any uncertain/reserved charges. This value is an exposure accounting measure, not necessarily final settled billing.', '',
        '- [All trajectories](figures/rollout_trajectories.png) ([SVG](figures/rollout_trajectories.svg))',
        '- [Outcome and paired-comparison charts](figures/rollout_outcomes.png) ([SVG](figures/rollout_outcomes.svg))',
        '- [Machine-readable summary](rollout_summary.json)',
        '- [Offline regeneration script](analyze_rollouts.py)', '']
    (OUT / 'ROLLOUT_REPORT.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    cases = {r['id']: r for r in json.loads((OUT / 'rollout_cases.json').read_text())}
    tasks = json.loads((OUT / 'rollout_tasks.json').read_text())
    expected = {(t['case_id'], t['policy'], t['repeat']) for t in tasks}
    assert len(expected) == 48 and len(cases) == 8
    episodes = [json.loads(p.read_text()) for p in sorted((OUT / 'rollouts').glob('*.json'))]
    observed = [(r['case_id'], r['policy'], r['repeat']) for r in episodes]
    assert len(observed) == len(set(observed)), 'Duplicate episode keys'
    assert set(observed) <= expected, 'Unexpected rollout task'
    missing = expected - set(observed)
    if missing and not args.allow_partial:
        raise SystemExit(f'Expected all 48 episodes; found {len(episodes)}. Still missing {len(missing)}. Use --allow-partial only for development.')
    rows = [validate_episode(r, cases[r['case_id']]) for r in episodes]
    comparisons = [compare(rows, a, b) for a, b in [
        ('original_random', 'combined_random'),
        ('combined_random', 'combined_coverage'),
        ('original_random', 'combined_coverage')]]
    exposure = None
    budget_file = OUT / 'budget.json'
    if budget_file.exists():
        attempts = json.loads(budget_file.read_text())['attempts']
        exposure = str(sum((Decimal(a['accounted_usd']) for k, a in attempts.items() if k.startswith('rollout__')), Decimal(0)))
    summary = {
        'partial': bool(missing), 'expected_episodes': 48, 'observed_episodes': len(rows),
        'missing_tasks': [list(t) for t in sorted(missing)],
        'independent_equations': 8, 'template_clusters': 8, 'heldout_template_clusters': 4,
        'validation': 'Every observed action replayed; exact root preserved; all solved claims checked literally.',
        'policies': {p: summarize_group([r for r in rows if r['policy'] == p]) for p in POLICIES},
        'by_split': {split: {p: summarize_group([r for r in rows if r['policy'] == p and r['split'] == split]) for p in POLICIES} for split in ['diagnostic', 'heldout']},
        'comparisons': comparisons, 'episode_metrics': rows,
        'recorded_decision_cost_usd': sum(r['recorded_decision_cost_usd'] for r in rows),
        'rollout_budget_exposure_usd': exposure,
        'inferential_limits': ['Eight cases, repeated twice per policy; not 48 independent problems.',
            'Combined guidance adds strategic information; coverage uses external reference-scored menu support.',
            'Failure cutoffs are informative; no independent-censoring survival inference used.',
            'Reference distance is not the proven minimum number of legal moves.'],
    }
    (OUT / 'rollout_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    report(summary)
    plots(episodes, rows, cases, bool(missing))
    print(json.dumps({k: summary[k] for k in ['partial', 'observed_episodes', 'policies', 'recorded_decision_cost_usd']}, indent=2))


if __name__ == '__main__':
    main()
