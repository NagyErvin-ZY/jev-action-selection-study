"""Offline validation before any model call; exact arithmetic and safeguard tests."""
import random
from fractions import Fraction as F
from algebra_engine import *

def main():
    count=0
    for name,initial in equations().items():
        root=solution(initial);current=initial;d0=distance(initial)
        for i in range(d0):
            action=reference_action(current)
            assert action in all_actions(current)
            current=apply(current,action)
            assert solution(current)==root
            assert distance(current)==d0-i-1
        assert solved(current) and number(current[1])==root
        # Random walks exercise legal but counterproductive operations as well.
        for seed in range(5):
            state=initial;rng=random.Random(seed)
            for step in range(12):
                actions=all_actions(state)
                assert len(actions)>=10
                for action in actions:
                    nxt=apply(state,action)
                    assert solution(nxt)==root
                    if action.side>=0:assert describe(state,action)
                    count+=1
                state=apply(state,rng.choice(actions))
                assert distance(state)>=0
                if solved(state):break
    assert distance((X,N(F(7,3))))==0
    assert apply((A(S(3,X),N(7)),N(22)),Action('shift_constant',arg=F(-7)))==(S(3,X),N(15))
    print('PASS: reference trajectories, exact equivalence, action descriptions, random walks;',count,'action applications checked.')

if __name__=='__main__':main()
