"""Offline payload construction for a frozen 2 x 2 x 2 prompt experiment.

No model/network calls and no reference-solver calls. The structured renderer
preserves the expression tree, including zeros and nested addition boundaries.
"""
from itertools import product
from pathlib import Path
import json
import sys

ALGEBRA = Path(__file__).resolve().parents[1] / 'jev-algebra'
if str(ALGEBRA) not in sys.path:
    sys.path.insert(0, str(ALGEBRA))
from algebra_engine import Action, at, apply, describe, equation, fmt, number, render, walk
from run_experiment import GUIDE

VARIANTS = [
    {'id': f'n{int(neutral)}_s{int(structured)}_g{int(guided)}',
     'neutral': neutral, 'structured': structured, 'guided': guided}
    for neutral, structured, guided in product([False, True], repeat=3)
]

PRECEDENCE_GUIDE = '''Additional general planning guidance (strategy scaffolding):
Distinguish local cleanup from transformations that duplicate unfinished work. When a product contains another product or numeric factor, evaluate those factors before expanding a surrounding bracket. When a sum contains a nested sum or two directly combinable terms, flatten or combine locally when doing so avoids repeating that work after distribution. An outer expansion can copy its coefficient onto several unfinished branches, so inspect whether inner cleanup should come first. Expand a bracket when its contents are ready to expose terms for collection. Once a side is flat, collect like terms, remove variable terms from the right and constants from the left, and divide the remaining nonzero coefficient of x. These are general preferences, not an instruction to take a particular displayed action; judge the actual expression and avoid undoing recent work.'''


def node_id(side, path=()):
    return ('L' if side == 0 else 'R') + '.' + ('.'.join(map(str, path)) or 'root')


def structure_records(state):
    """A lossless node table; children refer to their exact engine paths."""
    result = []
    for side, root in enumerate(state):
        for path, node in walk(root):
            item = {'id': node_id(side, path), 'kind': node[0]}
            if node[0] == 'n':
                item['value'] = fmt(number(node))
            elif node[0] == 'scale':
                item.update(factor=fmt(number(node)), child=node_id(side, path + (0,)))
            elif node[0] == 'add':
                item['children'] = [node_id(side, path + (i,)) for i in range(len(node[1]))]
            elif node[0] != 'x':
                raise ValueError('Unknown expression node kind')
            result.append(item)
    return result


def structured_equation(state):
    lines = ['CURRENT EQUATION: L.root = R.root',
             'Exact expression-node table: n is a number, x is the variable, '
             'scale multiplies its child by its factor, and add sums its listed children. '
             'IDs are side and engine path: L = LEFT, R = RIGHT; scale has child 0; '
             'add children are numbered 0, 1, ... in order. No simplification is implicit.']
    lines.extend(json.dumps(row, separators=(',', ':')) for row in structure_records(state))
    return '\n'.join(lines)


def neutral_description(state, action):
    """Delete generic benefit clauses only; never add operational information."""
    text = describe(state, action)
    removals = {
        'shift_constant': 'It can cancel a constant term; ',
        'shift_variable': 'It can collect variable terms on one side; ',
        'multiply': ' It can clear denominators or turn an isolated x coefficient into 1.',
        'swap': ' This can put an already-isolated x on the left, but swapping repeatedly makes no progress.',
        'simplify_product': ' Exposes a simpler coefficient without changing the value.',
        'distribute': ' Exposes terms that can subsequently be combined;',
        'remove_zero': ' Removes notation that contributes nothing to the value.',
        'flatten': ' Puts terms into the same sum so later collection becomes possible.',
    }
    # The distribution clause about temporary expression growth and the combine
    # sentence specifying exact arithmetic are factual mechanics, so retain them.
    if action.kind in removals:
        phrase = removals[action.kind]
        if phrase not in text:
            raise ValueError('Original action description changed; re-audit neutral deletion')
        text = text.replace(phrase, '', 1)
    return text


def make_payload(state, menu, history, variant, budgets=None):
    """Build an API-ready dict, preserving menu order and semantic action identity.

    budgets accepts step, decisions, rerolls, reroll_total, streak, reroll_streak.
    History is passed through unchanged, using its last six entries by default.
    Extra variant keys history_mode = recent|none|padding, padding_words, and
    padding_position = prefix|suffix support labelled history/length controls.
    """
    budgets = budgets or {}
    if not any(action.kind == 'reroll' for action in menu.values()):
        raise ValueError('Every experimental menu must offer reroll')
    description = neutral_description if variant.get('neutral', False) else describe
    criteria = {}
    for label, action in menu.items():
        text = description(state, action)
        if variant.get('structured', False) and action.side in (0, 1):
            text += ' Exact target ID: ' + node_id(action.side, action.path) + '.'
        criteria[label] = text
    guide = GUIDE
    if variant.get('guided', False):
        guide += '\n\n' + PRECEDENCE_GUIDE
    equation_text = structured_equation(state) if variant.get('structured', False) else 'CURRENT EQUATION: ' + equation(state)
    history_mode = variant.get('history_mode', 'recent')
    if history_mode not in ('recent', 'none', 'padding'):
        raise ValueError('Unknown history_mode')
    history_text = '\nRecent actions (oldest first): ' + json.dumps(history[-6:] if history_mode != 'none' else [])
    padding_text = ''
    if history_mode == 'padding':
        count = int(variant.get('padding_words', 512))
        if count < 0 or count > 6000:
            raise ValueError('padding_words must be between 0 and 6000')
        vocabulary = ('Archival background: Libraries store books and catalogues. '
                      'A catalogue can list titles and authors. Paper documents can be kept in folders. '
                      'Maps represent geographic features. Photographs record visual appearances. '
                      'A notebook can contain observations about plants and weather. '
                      'Historical collections may contain letters and diaries. '
                      'The arrangement of a collection can be described in an inventory.').split()
        padding_text = ('\nIrrelevant context-length control, unrelated to the equation or actions: '
                        + ' '.join(vocabulary[i % len(vocabulary)] for i in range(count)))
    budget_text = (f'\nDecision {budgets.get("step", 1)} of {budgets.get("decisions", 160)}. '
                   f'Rerolls used {budgets.get("rerolls", 0)} of {budgets.get("reroll_total", 8)}; '
                   f'consecutive rerolls {budgets.get("streak", 0)} of {budgets.get("reroll_streak", 3)}.')
    state_text = guide + '\n\n' + equation_text + history_text + budget_text
    padding_position = variant.get('padding_position', 'suffix')
    if padding_position not in ('prefix', 'suffix'):
        raise ValueError('Unknown padding_position')
    state_text = padding_text + '\n\n' + state_text if padding_position == 'prefix' else state_text + padding_text
    return {
        'model': 'typesafe/jev-1.13',
        'state': state_text,
        'questions': {'answer': {
            'type': 'choice',
            'instructions': 'Select the single most useful next operation toward x = a numeric constant, or reroll if no operation helps. Read the operation explanations carefully.',
            'criteria': criteria,
        }},
        'provider': {'allow_fallbacks': False, 'max_price': {'prompt': '0.042', 'completion': '0'}},
    }
