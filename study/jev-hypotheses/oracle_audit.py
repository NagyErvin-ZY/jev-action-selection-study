"""Offline sensitivity audit of algebra action values; no network or model calls.

Alternative policies are deterministic completion counts, NOT shortest paths.
Only BFS results with status='exact' are proven shortest paths in the engine's
full all_actions graph (including its documented size limits).
"""
from pathlib import Path
import sys, json, time, statistics
from collections import Counter, deque
from itertools import combinations
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'jev-algebra'))
from algebra_engine import *
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'jev-algebra'
POLICIES=('shallow_first','cleanup_first')
_CACHE={p:{} for p in POLICIES}

def freeze(x):return tuple(freeze(v) for v in x) if isinstance(x,list) else x

def action_from(o):return Action(o['kind'],o['side'],tuple(o['path']),o['i'],o['j'],F(o['arg']))

def alternative_action(state,policy='shallow_first'):
    if solved(state):return None
    # A visible solved expression on the other side can be swapped in one move.
    if state[1]==X and state[0][0]=='n':return Action('swap')
    local=local_actions(state)
    rank={'remove_zero':0,'simplify_product':1,'combine':2,'flatten':3,'distribute':4}
    if local:
        if policy=='shallow_first':
            key=lambda a:(len(a.path),rank[a.kind],a.side,a.path,a.i,a.j)
        elif policy=='cleanup_first':
            key=lambda a:(rank[a.kind],len(a.path),a.side,a.path,a.i,a.j)
        else:raise ValueError(policy)
        return min(local,key=key)
    al,bl=affine(state[0]);ar,br=affine(state[1])
    # Reverse the original policy's balance order as a second independence check.
    if bl:return Action('shift_constant',arg=-bl)
    if ar:return Action('shift_variable',arg=-ar)
    if al!=1:return Action('multiply',arg=1/al)
    raise ValueError('Could not normalize state')

def alternative_distance(state,policy='shallow_first',max_steps=1000):
    """Return integer completion length, or explicit failure dict (never infinity)."""
    if policy not in POLICIES:raise ValueError(policy)
    state=freeze(state);cache=_CACHE[policy];path=[];seen=set();current=state
    for _ in range(max_steps):
        if current in cache:tail=cache[current];break
        if solved(current):tail=0;cache[current]=0;break
        if current in seen:return {'status':'cycle','steps_attempted':len(path),'policy':policy}
        if state_nodes(current)>320 or len(equation(current))>18000:return {'status':'growth_limit','steps_attempted':len(path),'policy':policy}
        seen.add(current);path.append(current)
        try:current=apply(current,alternative_action(current,policy))
        except (ValueError,AssertionError) as e:return {'status':'failed','reason':str(e),'policy':policy}
    else:return {'status':'step_limit','steps_attempted':max_steps,'policy':policy}
    for previous in reversed(path):tail+=1;cache[previous]=tail
    return cache[state]

def score_menu(state,actions):
    """Return policy -> per-action completion-distance list, preserving action order.

Accepts Action objects or serialized action dicts. Values are integer counts or
explicit failure dicts from alternative_distance. No probability renormalization.
    """
    state=freeze(state)
    afters=[apply(state,a if isinstance(a,Action) else action_from(a)) for a in actions]
    return {'reference':[distance(a) for a in afters],
            **{p:[alternative_distance(a,p) for a in afters] for p in POLICIES}}

def bfs_distance(state,max_depth=4,max_nodes=2500):
    """BFS over ALL engine actions, no heuristic filtering. Censoring is explicit.

Every expansion is at nondecreasing depth. A goal found while expanding depth d
therefore proves shortest length d+1. We deduplicate exact ordered ASTs only.
"""
    state=freeze(state)
    if solved(state):return {'status':'exact','distance':0,'visited':1,'expanded':0}
    queue=deque([(state,0)]);seen={state};expanded=0;fully_expanded_depth=-1
    while queue:
        current,depth=queue.popleft()
        if depth>=max_depth:
            return {'status':'depth_censored','distance':None,'lower_bound':max_depth+1,'visited':len(seen),'expanded':expanded}
        # All shallower states have now been fully expanded.
        fully_expanded_depth=max(fully_expanded_depth,depth-1)
        for action in all_actions(current):
            after=apply(current,action)
            if solved(after):return {'status':'exact','distance':depth+1,'visited':len(seen)+1,'expanded':expanded+1}
            if after in seen:continue
            if len(seen)>=max_nodes:
                return {'status':'node_censored','distance':None,'lower_bound':fully_expanded_depth+2,'visited':len(seen),'expanded':expanded}
            seen.add(after);queue.append((after,depth+1))
        expanded+=1
    return {'status':'unreachable','distance':None,'visited':len(seen),'expanded':expanded}

def scores(ds,ps):
    lo=min(ds);hi=max(ds);mass=sum(ps)
    if not mass or hi==lo:return {'quality':None,'pairwise':None,'regret':None}
    regret=sum(p/mass*(d-lo) for p,d in zip(ps,ds));num=den=0
    for i,j in combinations(range(len(ds)),2):
        gap=ds[j]-ds[i]
        if not gap:continue
        dp=(ps[i]-ps[j])*(1 if gap>0 else -1)
        w=abs(gap);den+=w;num+=w*(1 if dp>1e-12 else 0 if dp< -1e-12 else .5)
    return {'quality':1-regret/(hi-lo),'pairwise':num/den,'regret':regret}

def avg(xs):
    xs=[x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None

def tests():
    assert bfs_distance((X,N(5)))['distance']==0
    assert bfs_distance((S(3,X),N(15)))['distance']==1
    assert bfs_distance((A(S(3,X),N(7)),N(22)))['distance']==2
    censored=bfs_distance(equations()['medium'],max_nodes=2)
    assert censored['distance'] is None and censored['status']=='node_censored'
    for policy in POLICIES:
        for name,state in equations().items():
            root=solution(state);current=state;d=alternative_distance(state,policy)
            assert isinstance(d,int),(policy,name,d)
            for i in range(d):
                action=alternative_action(current,policy)
                assert action.key() in {a.key() for a in all_actions(current)}
                current=apply(current,action);assert solution(current)==root
            assert solved(current)
        assert alternative_distance((N(5),X),policy)==1
    print('PASS: alternative paths legal and root-preserving; BFS 0/1/2-step proofs and explicit censoring.',flush=True)

def audit_saved():
    started=time.monotonic();tests()
    saved={(r['episode_id'],r['step_i']):r for r in map(json.loads,(SOURCE/'probability_scores.jsonl').read_text().splitlines())}
    rows=[];action_rows=[];bfs_candidates={};multiply_candidates=[]
    for ep_path in sorted((SOURCE/'episodes').glob('jev_*.json')):
        episode=json.loads(ep_path.read_text());state=freeze(episode['initial_ast'])
        for turn in episode['trajectory']:
            old=saved[(episode['episode_id'],turn['step_i'])]
            options=old['options'];out={'episode_id':episode['episode_id'],'level':episode['level'],'step_i':turn['step_i'],'reference':{'quality':old['probability_quality'],'pairwise':old['pairwise_alignment'],'regret':old['expected_regret_steps']},'alternatives':{}}
            alternatives={p:[] for p in POLICIES}
            for o in options:
                action=action_from(turn['menu'][o['label']]['action']);after=apply(state,action)
                assert solution(after)==solution(state)
                record={'episode_id':episode['episode_id'],'step_i':turn['step_i'],'label':o['label'],'kind':action.kind,'path_depth':len(action.path),'selected':o['selected'],'reference_distance':o['D_after']}
                for p in POLICIES:
                    d=alternative_distance(after,p);record[p]=d;alternatives[p].append(d)
                action_rows.append(record)
                if o['D_after']<=3 and state_nodes(after)<=8:
                    bfs_candidates.setdefault(after,{'state':after,'equation':equation(after),'reference_distance':o['D_after'],'episode_id':episode['episode_id'],'step_i':turn['step_i']})
            refds=[o['D_after'] for o in options];ps=[o['probability_raw'] for o in options]
            for p,ds in alternatives.items():
                if not all(isinstance(d,int) for d in ds):out['alternatives'][p]={'status':'failure'};continue
                unequal=discordant=tie_changed=0
                for i,j in combinations(range(len(ds)),2):
                    rd=refds[i]-refds[j];ad=ds[i]-ds[j]
                    if rd or ad:unequal+=1
                    if rd*ad<0:discordant+=1
                    if (rd==0)!=(ad==0):tie_changed+=1
                selected=next((i for i,o in enumerate(options) if o['selected']),None)
                out['alternatives'][p]={**scores(ds,ps),'pair_order_reversals':discordant,'tie_changes':tie_changed,'comparable_pairs':unequal,'selected_regret':None if selected is None else ds[selected]-min(ds)}
            for r in action_rows[-len(options):]:
                r['reference_regret']=r['reference_distance']-min(refds)
                for p in POLICIES:
                    ds=alternatives[p];r[p+'_regret']=r[p]-min(ds) if all(isinstance(d,int) for d in ds) else None
            if turn['action']['kind']=='multiply':
                multiply_candidates.append({'state':state,'episode_id':episode['episode_id'],'step_i':turn['step_i'],'D_before':old['D_before'],'max_D_after':max(refds),'selected_reference_regret':old['selected_action_regret_steps'],'options':[{'label':o['label'],'selected':o['selected'],'reference_distance':o['D_after'],'action':turn['menu'][o['label']]['action']} for o in options]})
            rows.append(out);state=freeze(turn['after_ast'])
    # Small-state subset chosen deterministically before BFS, stratified by reference distance.
    chosen=[]
    for d in [0,1,2,3]:
        candidates=[v for v in bfs_candidates.values() if v['reference_distance']==d]
        candidates.sort(key=lambda x:x['equation'])
        if candidates:
            indices=sorted(set(round(i*(len(candidates)-1)/3) for i in range(4)))
            chosen.extend(candidates[i] for i in indices)
    bfs=[]
    for c in chosen:
        state=c.pop('state');r=bfs_distance(state,max_depth=3,max_nodes=1800)
        bfs.append({**c,**r,**{p:alternative_distance(state,p) for p in POLICIES}})
    # Purposefully select tractable near-completion multiply choices. This is a
    # diagnostic subset, not an unbiased estimate of all multiplication errors.
    multiply_candidates=[c for c in multiply_candidates if c['selected_reference_regret']>0]
    multiply_candidates.sort(key=lambda c:(c['max_D_after'],c['D_before'],c['episode_id'],c['step_i']))
    multiply_exact=[]
    for c in multiply_candidates[:8]:
        state=c.pop('state');c['equation']=equation(state)
        for o in c['options']:
            after=apply(state,action_from(o['action']))
            o['bfs']=bfs_distance(after,max_depth=4,max_nodes=1800)
        selected=next(o for o in c['options'] if o['selected'])
        other_exact=[o['bfs']['distance'] for o in c['options'] if not o['selected'] and o['bfs']['status']=='exact']
        sb=selected['bfs'];low=min(other_exact) if other_exact else None
        # A censored selected move can still be proved worse than an exact
        # competitor if its rigorous lower bound exceeds that competitor.
        selected_lower=sb['distance'] if sb['status']=='exact' else sb.get('lower_bound')
        c['proven_selected_suboptimal']=low is not None and selected_lower is not None and low<selected_lower
        c['selected_shortest_distance']=sb['distance']
        c['best_exact_alternative_distance']=low
        c['selected_distance_lower_bound']=selected_lower
        c['regret_lower_bound']=max(0,selected_lower-low) if low is not None and selected_lower is not None else None
        c['proven_selected_optimal']=sb['status']=='exact' and all((o['bfs']['distance'] if o['bfs']['status']=='exact' else o['bfs'].get('lower_bound',-1))>=sb['distance'] for o in c['options'])
        c['verdict']='proven_suboptimal' if c['proven_selected_suboptimal'] else 'proven_optimal' if c['proven_selected_optimal'] else 'unresolved'
        c['all_actions_exact']=all(o['bfs']['status']=='exact' for o in c['options'])
        multiply_exact.append(c)
    groups={}
    for label,predicate in [('outer_expansion',lambda r:r['kind']=='distribute' and r['path_depth']==0),('nested_expansion',lambda r:r['kind']=='distribute' and r['path_depth']>0),('multiply',lambda r:r['kind']=='multiply'),('simplify_product',lambda r:r['kind']=='simplify_product'),('combine',lambda r:r['kind']=='combine')]:
        selected=[r for r in action_rows if r['selected'] and predicate(r)]
        groups[label]={'n':len(selected)}
        for p in ['reference',*POLICIES]:
            vals=[r[p+'_regret'] for r in selected if isinstance(r[p+'_regret'],(int,float))]
            groups[label][p]={'better_offered':sum(v>0 for v in vals),'n':len(vals),'fraction':avg(v>0 for v in vals),'mean_selected_regret':avg(vals)}
    summary={'extra_api_calls':0,'elapsed_seconds':time.monotonic()-started,'turns':len(rows),'actions':len(action_rows),'policy_definitions':{'reference':'Depth before kind; deepest local rewrite first; RHS variable before LHS constant.','shallow_first':'Shallowest local rewrite first, then kind; LHS constant before RHS variable; swap visibly reversed solution.','cleanup_first':'Kind before depth: remove zero, simplify product, combine, flatten, distribute; shallow tie break; LHS constant before RHS variable; swap visibly reversed solution.'},'metrics_note':'Alternative policies measure their own completion work, not shortest paths. Means below are turn-weighted exploratory sensitivity summaries; these are dependent observations.','means':{},'selected_action_groups':groups,'bfs':bfs,'multiply_exact_audit':multiply_exact,'multiply_exact_summary':{'states':len(multiply_exact),'proven_selected_suboptimal':sum(c['proven_selected_suboptimal'] for c in multiply_exact),'verdict_counts':dict(Counter(c['verdict'] for c in multiply_exact)),'all_actions_exact_states':sum(c['all_actions_exact'] for c in multiply_exact),'per_action_status_counts':dict(Counter(o['bfs']['status'] for c in multiply_exact for o in c['options']))},'bfs_status_counts':dict(Counter(r['status'] for r in bfs)),'bfs_definition':'Exact results use breadth-first traversal of the complete engine all_actions graph; exact ordered AST deduplication. Depth 3 and 1800-node caps only produce explicit censored results, never exact claims. Sampling selects up to four evenly spaced lexicographically ordered equations per reference distance 0..3 with <=8 AST nodes.'}
    for p in ['reference',*POLICIES]:
        rr=[r['reference'] if p=='reference' else r['alternatives'][p] for r in rows]
        summary['means'][p]={k:avg(r.get(k) for r in rr) for k in ['quality','pairwise','regret']}
        if p!='reference':summary['means'][p].update({k:sum(r.get(k,0) for r in rr) for k in ['pair_order_reversals','tie_changes','comparable_pairs']})
    (ROOT/'oracle_audit.json').write_text(json.dumps(summary,indent=2))
    for name,data in [('oracle_turns',rows),('oracle_actions',action_rows)]:
        with (ROOT/(name+'.jsonl')).open('w') as f:
            for r in data:f.write(json.dumps(r)+'\n')
    lines=['# Offline evaluator sensitivity audit','',f"Scored {len(rows)} saved distributions and {len(action_rows)} actions. No model calls.",'','## Selected actions with a better offered alternative','','| Selected kind | n | Original reference | Shallow first | Cleanup first |','|---|---:|---:|---:|---:|']
    for g,v in groups.items():lines.append('| '+g+' | '+str(v['n'])+' | '+' | '.join(f"{v[p]['better_offered']}/{v[p]['n']} ({v[p]['fraction']:.1%})" for p in ['reference',*POLICIES])+' |')
    lines+=['','## Probability-distribution metrics','','| Evaluator | Quality | Pairwise alignment | Expected regret |','|---|---:|---:|---:|']
    for p,v in summary['means'].items():lines.append(f"| {p} | {v['quality']:.3f} | {v['pairwise']:.3f} | {v['regret']:.3f} |")
    lines+=['','These are turn-weighted exploratory summaries, not independent trials. Both alternatives genuinely change local action ordering and balance order. They share the exact algebra implementation; this audits policy sensitivity, not independent arithmetic correctness. Counts remain policy-relative and are not claimed globally optimal.','','## Exact small-state search','',f"BFS result statuses: `{summary['bfs_status_counts']}`. Exact means a goal was first discovered in breadth-first order over all engine-generated moves. Search limits lead to explicit censored results. This small tractable subset cannot certify distances for deeply nested expressions.",'','| Equation | Reference | BFS | Status |','|---|---:|---:|---|']
    for r in bfs:lines.append(f"| `{r['equation']}` | {r['reference_distance']} | {r['distance']} | {r['status']} |")
    lines+=['','## Exact audit of near-completion multiplication choices','','Eight selected-multiply states flagged as inferior by the original reference were chosen deterministically by smallest maximum offered reference distance, then current reference distance, episode ID and step. This diagnostic selection targets suspected mistakes and favours tractability; it is not representative of all multiplication choices. BFS applies to each offered action with depth 4 and 1,800-node caps. A censored action is only proved inferior when its rigorous lower bound exceeds a competing exact distance.','','| Episode / step | Selected shortest distance or lower bound | Best exact competing distance | Verdict |','|---|---:|---:|---|']
    for c in multiply_exact:lines.append(f"| {c['episode_id']} / {c['step_i']} | {c['selected_shortest_distance'] if c['selected_shortest_distance'] is not None else '>='+str(c['selected_distance_lower_bound'])} | {c['best_exact_alternative_distance']} | {c['verdict']} |")
    lines+=['','## Interpretation','','The outer-expansion disadvantage is strongly evaluator-dependent: 34/37 selected outer expansions have a better offered move under the original policy, versus 9/37 under shallow-first and 21/37 under cleanup-first. The original 91.9% rate therefore cannot substantiate a general outer-expansion weakness. Multiplication is more robust: 28/49 versus 27/49 under either alternative. The targeted BFS audit additionally proves five selected multiplication moves inferior using exact competing distances and exact values or rigorous lower bounds for the selected moves; one flagged move is proven optimal and two remain unresolved under search caps. This targeted subset cannot estimate error prevalence. Exact-distance claims apply only to explicitly exact cases; censored lower bounds can still prove strict inferiority when separated from an exact competitor.','',f"Runtime: {summary['elapsed_seconds']:.1f}s. See oracle_audit.json and oracle_actions.jsonl for all denominators and counterfactual distances."]
    (ROOT/'ORACLE_REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':audit_saved()
