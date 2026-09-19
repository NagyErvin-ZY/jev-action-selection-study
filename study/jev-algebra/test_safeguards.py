"""Offline checks for spending reservations and non-progress termination."""
import tempfile
from pathlib import Path
from run_experiment import *

def main():
    state=equations()['simple'];d=distance(state)
    g=Guard('simple',state)
    for i in range(3):status=g.advance(Action('reroll'),state,d)
    assert status=='cutoff_reroll_streak' and g.visits[signature(state)]==1
    g=Guard('simple',state)
    for i in range(4):
        state=apply(state,Action('swap'));status=g.advance(Action('swap'),state,distance(state))
    assert status=='cutoff_repeated_state'
    g=Guard('simple',state)
    assert g.advance(Action('declare_solved'),state,distance(state)) is None
    assert g.advance(Action('declare_solved'),state,distance(state))=='cutoff_premature_completion'
    state=equations()['simple'];g=Guard('simple',state)
    for i in range(12):
        state=apply(state,Action('shift_constant',arg=F(1)))
        status=g.advance(Action('shift_constant',arg=F(1)),state,distance(state))
    assert status=='cutoff_stagnation'
    state=equations()['medium'];g=Guard('medium',state)
    for i in range(8):
        state=apply(state,Action('shift_constant',arg=F(1)))
        g.advance(Action('shift_constant',arg=F(1)),state,distance(state))
        status=g.advance(Action('reroll'),state,distance(state))
    assert status=='cutoff_reroll_total'
    state=equations()['simple'];g=Guard('simple',state);g.limits=dict(g.limits,decisions=3)
    for i in range(3):
        state=apply(state,Action('shift_constant',arg=F(1)))
        status=g.advance(Action('shift_constant',arg=F(1)),state,distance(state))
    assert status=='cutoff_decisions'
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'budget.json';b=Budget(path,'0.004','0.002')
        b.book('one');b.book('two')
        try:b.book('three');raise AssertionError('Budget allowed overspend')
        except BudgetStop:pass
        b.settle('one',None)
        assert b.exposure()==Decimal('0.004')
        b.settle('two','0.0001');assert b.exposure()==Decimal('0.0021')
        resumed=Budget(path,'0.004','0.002');assert resumed.exposure()==b.exposure()
        try:resumed.book('three');raise AssertionError('Restart lost reservation')
        except BudgetStop:pass
    print('PASS: reroll streak/total, cycle, stagnation, decisions, premature completion and persistent global spending guards.')

if __name__=='__main__':main()
