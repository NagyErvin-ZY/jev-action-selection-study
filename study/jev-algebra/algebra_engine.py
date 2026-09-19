"""Exact affine algebra with explicit local rewrites; no all-purpose solve action."""
from dataclasses import dataclass
from fractions import Fraction as F
from functools import lru_cache
from itertools import combinations
import hashlib
import json

X=('x',)
def N(q):
    q=F(q);return ('n',q.numerator,q.denominator)
def A(*children):return ('add',tuple(children))
def S(q,child):
    q=F(q);return ('scale',q.numerator,q.denominator,child)
def number(node):return F(node[1],node[2])
def mono(q):
    q=F(q)
    return N(0) if q==0 else X if q==1 else S(q,X)
def compact_add(children):
    children=[c for c in children if c!=N(0)]
    return N(0) if not children else children[0] if len(children)==1 else A(*children)
def atomic(node):
    if node[0]=='n':return ('constant',number(node))
    if node==X:return ('variable',F(1))
    if node[0]=='scale' and node[3]==X:return ('variable',number(node))
    return None
def affine(node):
    if node[0]=='n':return F(0),number(node)
    if node==X:return F(1),F(0)
    if node[0]=='scale':
        a,b=affine(node[3]);q=number(node);return q*a,q*b
    aa,bb=F(0),F(0)
    for c in node[1]:
        a,b=affine(c);aa+=a;bb+=b
    return aa,bb
def solution(state):
    al,bl=affine(state[0]);ar,br=affine(state[1]);assert al!=ar
    return (br-bl)/(al-ar)
def fmt(q):
    q=F(q);return str(q.numerator) if q.denominator==1 else f'{q.numerator}/{q.denominator}'
def render(node):
    if node==X:return 'x'
    if node[0]=='n':return fmt(number(node))
    if node[0]=='scale':return f'({fmt(number(node))})*({render(node[3])})'
    return '('+' + '.join(render(c) for c in node[1])+')'
def equation(state):return render(state[0])+' = '+render(state[1])
def count_nodes(node):
    return 1+(sum(count_nodes(c) for c in node[1]) if node[0]=='add' else count_nodes(node[3]) if node[0]=='scale' else 0)
def state_nodes(state):return sum(count_nodes(n) for n in state)
def solved(state):return state[0]==X and state[1][0]=='n'
def canonical(node):
    if node[0]=='add':return ('add',tuple(sorted((canonical(c) for c in node[1]),key=repr)))
    if node[0]=='scale':return (*node[:3],canonical(node[3]))
    return node
def signature(state):return hashlib.sha256(repr(tuple(canonical(n) for n in state)).encode()).hexdigest()
def walk(node,path=()):
    yield path,node
    if node[0]=='scale':yield from walk(node[3],path+(0,))
    elif node[0]=='add':
        for i,c in enumerate(node[1]):yield from walk(c,path+(i,))
def at(node,path):
    if not path:return node
    return at(node[3] if node[0]=='scale' else node[1][path[0]],path[1:])
def replace(node,path,new):
    if not path:return new
    if node[0]=='scale':return (*node[:3],replace(node[3],path[1:],new))
    children=list(node[1]);children[path[0]]=replace(children[path[0]],path[1:],new)
    return A(*children)

@dataclass(frozen=True)
class Action:
    kind:str
    side:int=-1
    path:tuple=()
    i:int=-1
    j:int=-1
    arg:F=F(0)
    def key(self):return (self.kind,self.side,self.path,self.i,self.j,str(self.arg))
    def serial(self):return {'kind':self.kind,'side':self.side,'path':list(self.path),'i':self.i,'j':self.j,'arg':str(self.arg)}

def local_actions(state):
    actions=[]
    for side,node in enumerate(state):
        for path,n in walk(node):
            if n[0]=='scale':
                q=number(n);child=n[3]
                if q in (0,1) or child[0] in ('n','scale'):
                    actions.append(Action('simplify_product',side,path))
                elif child[0]=='add':actions.append(Action('distribute',side,path))
            elif n[0]=='add':
                if len(n[1])<=1 or any(c==N(0) for c in n[1]):actions.append(Action('remove_zero',side,path))
                for i,c in enumerate(n[1]):
                    if c[0]=='add':actions.append(Action('flatten',side,path,i=i))
                atoms=[atomic(c) for c in n[1]]
                for i,j in combinations(range(len(atoms)),2):
                    if atoms[i] and atoms[j] and atoms[i][0]==atoms[j][0]:actions.append(Action('combine',side,path,i,j))
    return actions

def shift_side(node,kind,q):
    children=list(node[1]) if node[0]=='add' else [node]
    for i,c in enumerate(children):
        atom=atomic(c)
        if atom and atom[0]==kind:
            value=atom[1]+q;children[i]=N(value) if kind=='constant' else mono(value)
            return compact_add(children)
    children.append(N(q) if kind=='constant' else mono(q))
    return compact_add(children)

def multiply_side(node,q):
    atom=atomic(node)
    if atom:return N(atom[1]*q) if atom[0]=='constant' else mono(atom[1]*q)
    if node[0]=='scale':return S(number(node)*q,node[3])
    return S(q,node)

def apply(state,action):
    a=action;out=list(state)
    if a.kind=='swap':return (state[1],state[0])
    if a.kind=='shift_constant':return tuple(shift_side(n,'constant',a.arg) for n in state)
    if a.kind=='shift_variable':return tuple(shift_side(n,'variable',a.arg) for n in state)
    if a.kind=='multiply':
        assert a.arg!=0
        return tuple(multiply_side(n,a.arg) for n in state)
    if a.kind in ('reroll','declare_solved'):return state
    node=at(state[a.side],a.path)
    if a.kind=='simplify_product':
        q=number(node);child=node[3]
        if q==0:new=N(0)
        elif q==1:new=child
        elif child[0]=='n':new=N(q*number(child))
        elif child[0]=='scale':new=S(q*number(child),child[3])
        else:raise AssertionError('Bad product rewrite')
    elif a.kind=='distribute':new=A(*(S(number(node),c) for c in node[3][1]))
    elif a.kind=='remove_zero':new=compact_add(list(node[1]))
    elif a.kind=='flatten':
        children=list(node[1]);new=compact_add(children[:a.i]+list(children[a.i][1])+children[a.i+1:])
    elif a.kind=='combine':
        children=list(node[1]);left,right=atomic(children[a.i]),atomic(children[a.j]);assert left[0]==right[0]
        q=left[1]+right[1];children[a.i]=N(q) if left[0]=='constant' else mono(q);children.pop(a.j);new=compact_add(children)
    else:raise AssertionError(a.kind)
    out[a.side]=replace(state[a.side],a.path,new)
    return tuple(out)

def top_atoms(node):
    for c in node[1] if node[0]=='add' else [node]:
        a=atomic(c)
        if a:yield a

def all_actions(state):
    actions=local_actions(state)
    for node in state:
        for kind,q in top_atoms(node):
            if q!=0:actions.append(Action('shift_constant' if kind=='constant' else 'shift_variable',arg=-q))
            if kind=='variable' and q not in (0,1):actions.append(Action('multiply',arg=1/q))
    # Clearing visible rational factors is useful without invoking a solver.
    denoms=set()
    for node in state:
        for _,n in walk(node):
            if n[0] in ('n','scale') and number(n).denominator>1:denoms.add(number(n).denominator)
    if denoms:
        import math
        lcm=math.lcm(*denoms)
        if lcm<=10000:actions.append(Action('multiply',arg=F(lcm)))
    for q in [-3,-2,-1,1,2,3]:actions.append(Action('shift_constant',arg=F(q)))
    for q in [-2,-1,1,2]:actions.append(Action('shift_variable',arg=F(q)))
    for q in [-1,2,F(1,2),3,F(1,3)]:actions.append(Action('multiply',arg=F(q)))
    actions.extend([Action('swap'),Action('declare_solved')])
    seen=set();result=[]
    for a in actions:
        if a.key() in seen:continue
        seen.add(a.key())
        after=apply(state,a)
        if a.kind!='declare_solved' and after==state:continue
        if state_nodes(after)>320 or len(equation(after))>18000:continue
        result.append(a)
    return result

def reference_action(state):
    if solved(state):return None
    local=local_actions(state)
    if local:
        rank={'simplify_product':0,'remove_zero':1,'flatten':2,'combine':3,'distribute':4}
        return min(local,key=lambda a:(-len(a.path),rank[a.kind],a.side,a.path,a.i,a.j))
    al,bl=affine(state[0]);ar,br=affine(state[1])
    if ar:return Action('shift_variable',arg=-ar)
    if bl:return Action('shift_constant',arg=-bl)
    assert al!=0
    if al!=1:return Action('multiply',arg=1/al)
    raise AssertionError('Reference solver could not normalize '+equation(state))

@lru_cache(maxsize=20000)
def distance(state):
    current=state;seen=set()
    for steps in range(1000):
        if solved(current):return steps
        s=signature(current);assert s not in seen,'Reference loop';seen.add(s)
        current=apply(current,reference_action(current))
    raise AssertionError('Reference solver exhausted')

def describe(state,a):
    if a.kind=='shift_constant':
        return f'Add {fmt(a.arg)} to BOTH sides. This preserves equality. It can cancel a constant term; arithmetic with one existing constant on each side is performed exactly.'
    if a.kind=='shift_variable':
        return f'Add ({fmt(a.arg)})*x to BOTH sides. This preserves equality. It can collect variable terms on one side; one matching top-level x term on each side is combined exactly.'
    if a.kind=='multiply':
        return f'Multiply BOTH sides by {fmt(a.arg)}. This factor is nonzero, so solutions are preserved. It can clear denominators or turn an isolated x coefficient into 1. It does not automatically expand brackets.'
    if a.kind=='swap':return 'Swap the left and right sides. Equality is symmetric. This can put an already-isolated x on the left, but swapping repeatedly makes no progress.'
    if a.kind=='declare_solved':return 'Declare completion. Use only when the equation is literally x = a numeric constant. The engine will reject an early declaration; this action performs no algebra.'
    if a.kind=='reroll':return 'Keep the equation unchanged and draw a new menu. Use when none of the ten actions is useful. Each reroll consumes a decision and the limited reroll allowance.'
    target=render(at(state[a.side],a.path));after=render(at(apply(state,a)[a.side],a.path))
    titles={'simplify_product':'Evaluate or combine constant factors in one product',
            'distribute':'Distribute the outside factor across every term of one bracket',
            'remove_zero':'Remove zero terms or an unnecessary single-term sum',
            'flatten':'Remove one redundant nested addition bracket',
            'combine':'Combine two like terms in one sum'}
    purposes={'simplify_product':'Exposes a simpler coefficient without changing the value.',
              'distribute':'Exposes terms that can subsequently be combined; the expression may temporarily grow.',
              'remove_zero':'Removes notation that contributes nothing to the value.',
              'flatten':'Puts terms into the same sum so later collection becomes possible.',
              'combine':'Adds the two numeric constants or x coefficients exactly; other terms stay unchanged.'}
    loc=('LEFT' if a.side==0 else 'RIGHT')+' side, path '+('.'.join(map(str,a.path)) or 'root')
    return f'{titles[a.kind]}. Target: {loc}: {target}. Replacement: {after}. Valid by ordinary rational arithmetic/distributivity. {purposes[a.kind]}'

def equations():
    simple=(A(S(3,X),N(7)),N(22))
    medium=(A(S(F(3,4),A(S(2,X),N(-5))),S(F(-1,3),A(X,N(1)))),N(F(7,4)))
    # Several layers of affine structure; only constant, nonzero denominators.
    u=A(S(F(5,7),A(S(F(-3,4),A(S(2,X),N(-11))),N(F(13,5)))),S(F(2,9),A(X,N(-7))))
    v=A(S(F(-7,5),A(S(F(3,8),u),S(F(-2,3),A(S(4,X),N(9))))),N(F(17,11)))
    left=S(F(11,6),v)
    right_base=S(F(-5,12),A(X,N(-3)))
    root=F(7,3);al,bl=affine(left);ar,br=affine(right_base)
    right=A(right_base,N((al-ar)*root+bl-br))
    return {'simple':simple,'medium':medium,'unholy':(left,right)}

if __name__=='__main__':
    for name,state in equations().items():print(name,'reference steps',distance(state),'nodes',state_nodes(state),'solution',solution(state),'equation',equation(state))
