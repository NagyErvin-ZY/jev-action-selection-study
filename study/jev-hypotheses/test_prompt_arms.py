"""Offline semantic tests; never contacts a model provider."""
from fractions import Fraction
import json
import random
from prompt_arms import *
from algebra_engine import equations, all_actions, N, X, S, A


def reconstruct(records, ident):
    table = {row['id']: row for row in records}
    def visit(key):
        row = table[key]
        if row['kind'] == 'n': return N(Fraction(row['value']))
        if row['kind'] == 'x': return X
        if row['kind'] == 'scale': return S(Fraction(row['factor']), visit(row['child']))
        return A(*(visit(child) for child in row['children']))
    return visit(ident)


def main():
    checks = 0
    for name, state in equations().items():
        records = structure_records(state)
        assert (reconstruct(records, 'L.root'), reconstruct(records, 'R.root')) == state
        assert len({row['id'] for row in records}) == len(records)
        for action in all_actions(state):
            original = describe(state, action)
            neutral = neutral_description(state, action)
            # Pure deletion: every retained character has the same order as in
            # the original, and no new operational statement was introduced.
            original_chars = iter(original)
            assert all(any(c == retained for c in original_chars) for retained in neutral)
            assert 'Valid by ordinary rational arithmetic/distributivity.' not in original or 'Valid by ordinary rational arithmetic/distributivity.' in neutral
            if action.kind == 'distribute':
                assert 'the expression may temporarily grow.' in neutral
            if action.kind == 'combine':
                assert neutral == original
            menu = {'test_action': action, 'reroll': Action('reroll')}
            for variant in VARIANTS:
                payload = make_payload(state, menu, [{'action': 'constant history', 'result': 'same history'}], variant)
                text = payload['questions']['answer']['criteria']['test_action']
                assert list(payload['questions']['answer']['criteria']) == list(menu)
                assert 'same history' in payload['state']
                if not variant['neutral'] and not variant['structured']:
                    assert text == describe(state, action)
                if action.side in (0, 1):
                    assert render(at(state[action.side], action.path)) in text
                    assert render(at(apply(state, action)[action.side], action.path)) in text
                    if variant['structured']:
                        assert node_id(action.side, action.path) in {row['id'] for row in records}
                if variant['guided']:
                    assert PRECEDENCE_GUIDE in payload['state']
                assert 'reference_steps' not in json.dumps(payload)
                assert 'hidden_solution' not in json.dumps(payload)
                checks += 1
        menu = {'reroll': Action('reroll')}
        p = make_payload(state, menu, [{'action': 'sentinel_history'}], dict(VARIANTS[0], history_mode='none'))
        assert 'sentinel_history' not in p['state']
        p = make_payload(state, menu, [], dict(VARIANTS[0], history_mode='padding', padding_words=32))
        assert 'Libraries store books' in p['state']
        for count in (2000, 6000):
            p = make_payload(state, menu, [], dict(VARIANTS[0], history_mode='padding', padding_words=count, padding_position='prefix'))
            assert p['state'].index('Libraries store books') < p['state'].index(GUIDE)
    print(f'PASS: {checks} factorial payload/action checks; lossless AST reconstruction on all equation levels; history controls.')


if __name__ == '__main__':
    main()
