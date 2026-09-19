"""Frozen, deterministic fresh algebra states for hypothesis testing.

No API calls. Eight equation templates each receive a full 2^4
factorial: nesting, width, magnitude, and rational coefficients.
Main-effect columns are independently assigned. Changing nesting also changes
reference horizon and node count. Signs vary by template and coefficient role.
Eight templates are eight template clusters, NOT 128 independent families.
"""
from pathlib import Path
import sys
import json
from itertools import product
from fractions import Fraction as F

ENGINE_DIR = Path(__file__).resolve().parents[1] / 'jev-algebra'
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))
import algebra_engine as e

FAMILIES = (
    'nested_chain', 'parallel_branches', 'variables_both_sides',
    'repeated_subexpression', 'signed_enclosure', 'constant_subtree',
    'asymmetric_sides', 'outer_collection',
)
HELDOUT = {'signed_enclosure', 'constant_subtree', 'asymmetric_sides', 'outer_collection'}


def _coefficients(family_i, magnitude, rational):
    # Numeric values are fixed before inference; large values do not add terms.
    values = [2 + (family_i + j * 3) % 5 for j in range(12)]
    scale = 17 if magnitude else 1
    return [F(v * scale, (2 + j % 3) if rational else 1)
            for j, v in enumerate(values)]


def _chain(c, branch, depth):
    node = e.A(e.S(c[branch % 12], e.X), e.N(c[(branch + 1) % 12]))
    for layer in range(depth):
        factor = c[(branch + layer + 2) % 12]
        offset = c[(branch + layer + 3) % 12]
        node = e.S(factor, e.A(node, e.N(-offset if layer % 2 else offset)))
    return node


def _make_state(family_i, deep, wide, large, rational, compact=False):
    c = _coefficients(family_i, large, rational)
    depth = (2 if deep else 0) if not compact else (1 if deep else 0)
    width = (4 if wide else 2) if not compact else (2 if wide else 1)
    branches = [_chain(c, j, depth) for j in range(width)]
    core = branches[0]
    block = e.A(*branches)
    f = FAMILIES[family_i]
    right_base = e.N(0)
    if f == 'nested_chain':
        left = e.S(c[8], e.A(core, *(e.N(c[j]) for j in range(1, width))))
    elif f == 'parallel_branches':
        left = block
    elif f == 'variables_both_sides':
        left = block
        right_base = e.S(-c[7], e.A(e.S(c[8], e.X), e.N(c[9])))
    elif f == 'repeated_subexpression':
        left = e.A(*(e.S(c[j + 3], core) for j in range(width)))
    elif f == 'signed_enclosure':
        left = e.S(-c[8], e.A(block, e.S(-c[9], e.A(e.X, e.N(c[10])))))
    elif f == 'constant_subtree':
        left = e.A(block, e.S(-c[7], e.A(e.N(c[8]), e.N(c[9]))))
    elif f == 'asymmetric_sides':
        left = e.A(block, e.N(c[8]))
        right_base = e.S(-c[6], e.A(e.X, e.N(-c[7])))
    elif f == 'outer_collection':
        left = e.A(e.S(c[6], block), e.S(c[7], e.X), e.N(-c[8]))
        right_base = e.S(-c[9], e.X)
    root = F(family_i + 2, 3 if rational else 1)
    al, bl = e.affine(left)
    ar, br = e.affine(right_base)
    if al == ar:
        # Deterministic tie avoidance; recorded in the exact expression.
        left = e.A(left, e.X)
        al, bl = e.affine(left)
    adjustment = (al - ar) * root + bl - br
    right = e.N(adjustment) if right_base == e.N(0) else e.A(right_base, e.N(adjustment))
    return (left, right)


def _features(state):
    nodes = [n for side in state for _, n in e.walk(side)]
    depth = max(len(p) for side in state for p, _ in e.walk(side))
    nums = [e.number(n) for n in nodes if n[0] in ('n', 'scale')]
    return {
        'nodes': e.state_nodes(state), 'ast_depth': depth,
        'max_add_arity': max([len(n[1]) for n in nodes if n[0] == 'add'] or [0]),
        'reference_steps': e.distance(state),
        'negative_literal_count': sum(q < 0 for q in nums),
        'rational_literal_count': sum(q.denominator > 1 for q in nums),
        'max_abs_literal': str(max(abs(q) for q in nums)),
        'expression_characters': len(e.equation(state)),
    }


def build_cases():
    """Return 128 fixed initial states; 64 diagnostic and 64 held-out states."""
    result = []
    for family_i, family in enumerate(FAMILIES):
        for deep, wide, large, rational in product((0, 1), repeat=4):
            state = _make_state(family_i, deep, wide, large, rational)
            result.append({
                'id': f'fresh_{family_i:02d}_d{deep}w{wide}m{large}r{rational}',
                'family': family,
                'split': 'heldout' if family in HELDOUT else 'diagnostic',
                'state': state,
                'factors': {
                    'nesting': 'deep' if deep else 'shallow',
                    'branch_width': 'wide' if wide else 'narrow',
                    'magnitude': 'large' if large else 'small',
                    'numeric_regime': 'rational' if rational else 'integer',
                    'design_cell': [deep, wide, large, rational],
                },
                'derived': _features(state),
            })
    return result


def build_rollout_cases():
    """Eight compact fresh equations, one per template, for end-to-end runs.

    Distinct from all 128 diagnostic states, so longitudinal confirmation does
    not simply rerun states used for selecting an intervention.
    """
    result = []
    for i, family in enumerate(FAMILIES):
        state = _make_state(i, deep=i % 2, wide=0, large=0,
                            rational=(i // 2) % 2, compact=True)
        # A fixed extra constant shift guarantees a new exact AST and root.
        state = (state[0], e.shift_side(state[1], 'constant', F(11 + i)))
        result.append({
            'id': f'rollout_{i:02d}_{family}', 'family': family,
            'split': 'heldout' if family in HELDOUT else 'diagnostic',
            'state': state,
            'factors': {'purpose': 'fresh_longitudinal_confirmation'},
            'derived': _features(state),
        })
    return result


def validate(cases):
    checked_actions = 0
    for case in cases:
        state = case['state']
        root = e.solution(state)
        assert not e.solved(state)
        actions = e.all_actions(state)
        assert len(actions) >= 10, case['id']
        for a in actions:
            assert e.solution(e.apply(state, a)) == root, (case['id'], a)
            checked_actions += 1
        horizon = e.distance(state)
        for _ in range(horizon):
            a = e.reference_action(state)
            assert a in e.all_actions(state), (case['id'], a)
            state = e.apply(state, a)
            assert e.solution(state) == root, case['id']
        assert e.solved(state), case['id']
    return checked_actions


def _json_case(case):
    return {**case, 'equation': e.equation(case['state']),
            'hidden_root_for_audit_only': str(e.solution(case['state']))}


if __name__ == '__main__':
    out = Path(__file__).resolve().parent
    cases = build_cases()
    rollouts = build_rollout_cases()
    checked = validate(cases + rollouts)
    assert len({e.signature(c['state']) for c in cases + rollouts}) == 136
    for name, rows in [('fresh_cases.json', cases), ('fresh_rollout_cases.json', rollouts)]:
        (out / name).write_text(json.dumps([_json_case(c) for c in rows], indent=2) + '\n')
    report = {
        'case_count': len(cases), 'rollout_count': len(rollouts),
        'template_count': len(FAMILIES), 'heldout_templates': sorted(HELDOUT),
        'checked_initial_actions': checked,
        'reference_step_range': [min(c['derived']['reference_steps'] for c in cases),
                                 max(c['derived']['reference_steps'] for c in cases)],
        'rollout_reference_steps': {c['id']: c['derived']['reference_steps'] for c in rollouts},
        'factor_design': 'full 2^4: depth, width, magnitude, rational regime',
        'limits': [
            'Only eight template clusters; 128 states are not 128 independent families.',
            'Depth changes node count and reference horizon; these are derived correlates.',
            'Width manipulates template-specific branch/term repetition, not identical AST arity everywhere.',
            'Rational coefficients can simplify to integers; actual rational count is recorded.',
            'Sign prevalence is template-dependent and is not independently randomized.',
            'Root magnitude/regime changes with numeric regime; no isolated root-size effect.',
        ],
    }
    (out / 'fresh_cases_validation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
