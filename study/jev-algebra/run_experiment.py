"""Auditable Jev algebra controller experiment. No calls unless --execute is supplied.

Run once in this output directory. The persistent, locked budget includes every
attempt, and uncertain charges retain their full reservation. Never reset it to
resume an interrupted experiment. Requires OPENROUTER_API_KEY in the environment.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import random
import threading
import time
import httpx
from algebra_engine import *

OUT=Path(__file__).resolve().parent
MODEL='typesafe/jev-1.13'
SEEDS=list(range(8))
LIMITS={
 'simple':{'decisions':24,'stagnation':12,'seconds':240},
 'medium':{'decisions':70,'stagnation':18,'seconds':480},
 'unholy':{'decisions':160,'stagnation':30,'seconds':900}}
GUARDS={'reroll_streak':3,'reroll_total':8,'state_visits':3,'premature_declarations':2,
        'request_bytes':30000,'global_seconds':1800,'global_attempts':2200,
        'hard_cap_usd':'2.00','reservation_usd':'0.002','price_cap_usd_per_million':'0.042'}
GUIDE='''You control an exact-arithmetic algebra engine. Your goal is to transform the CURRENT equation into literally x = a numeric constant, using few decisions.
All expressions use exact rational arithmetic: (a/b)*(...) means multiplication by the fraction a/b, and + -k means subtract k. Paths identify a subexpression, starting at 0 within each bracket. You do not compute replacements yourself: the engine executes the selected operation exactly as described.
Useful strategy: evaluate nested constant products, distribute coefficients across brackets when needed, flatten nested sums, combine like terms, collect x terms on the left and constants on the right, then divide by the coefficient of x. A local expansion may temporarily lengthen an expression but enable later collection. Prefer a direct cancellation or isolation when available. Arbitrary additions, multiplications, and swaps can undo progress; avoid reversing recent actions. You can work on either side.
You receive ten randomly sampled operations and one reroll. There may be several useful choices, or none. Reroll only if all displayed operations are unhelpful; rerolls and total decisions are limited. Completion is automatically detected after a transformation; declaring completion early is an error. Choose based on the operation, not its label or position. No action solves the whole equation automatically.'''

def stamp():return datetime.now(timezone.utc).isoformat()
def write_json(path,obj):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False));tmp.replace(path)

class BudgetStop(Exception):pass
class Budget:
    def __init__(self,path,cap='2.00',reserve='0.002'):
        self.path=Path(path);self.lock=threading.Lock();self.cap=Decimal(cap);self.reserve=Decimal(reserve)
        self.data=json.loads(self.path.read_text()) if self.path.exists() else {'cap_usd':cap,'reservation_usd':reserve,'attempts':{},'halted':False}
        assert self.data['cap_usd']==cap and self.data['reservation_usd']==reserve
    def exposure(self):
        return sum((Decimal(a['accounted_usd']) for a in self.data['attempts'].values()),Decimal(0))
    def book(self,key):
        with self.lock:
            if self.data['halted'] or self.exposure()+self.reserve>self.cap or len(self.data['attempts'])>=GUARDS['global_attempts']:raise BudgetStop('Global spending/attempt limit')
            assert key not in self.data['attempts'],'Do not repeat an already reserved request'
            self.data['attempts'][key]={'accounted_usd':str(self.reserve),'status':'reserved','created_at':stamp()}
            write_json(self.path,self.data)
    def settle(self,key,cost):
        with self.lock:
            a=self.data['attempts'][key]
            if cost is None:a['status']='uncertain_charge';write_json(self.path,self.data);return
            cost=Decimal(str(cost));assert cost>=0
            a.update(accounted_usd=str(cost),actual_usd=str(cost),status='settled')
            if cost>self.reserve:self.data['halted']=True
            write_json(self.path,self.data)

class Guard:
    def __init__(self,level,state):
        self.limits=LIMITS[level];self.steps=0;self.best=distance(state);self.last_improved=0
        self.rerolls=0;self.streak=0;self.premature=0;self.visits=Counter({signature(state):1})
    def advance(self,a,state,d):
        self.steps+=1
        if a.kind=='reroll':self.rerolls+=1;self.streak+=1
        else:self.streak=0
        if a.kind=='declare_solved' and not solved(state):self.premature+=1
        if a.kind not in ('reroll','declare_solved'):self.visits[signature(state)]+=1
        if d<self.best:self.best=d;self.last_improved=self.steps
        if solved(state):return 'solved'
        if self.streak>=GUARDS['reroll_streak']:return 'cutoff_reroll_streak'
        if self.rerolls>=GUARDS['reroll_total']:return 'cutoff_reroll_total'
        if self.visits[signature(state)]>=GUARDS['state_visits']:return 'cutoff_repeated_state'
        if self.premature>=GUARDS['premature_declarations']:return 'cutoff_premature_completion'
        if self.steps-self.last_improved>=self.limits['stagnation']:return 'cutoff_stagnation'
        if self.steps>=self.limits['decisions']:return 'cutoff_decisions'
        return None

def build_menu(state,rng):
    pool=all_actions(state);chosen=rng.sample(pool,10);rng.shuffle(chosen)
    return pool,{f'move_{i+1:02d}':a for i,a in enumerate(chosen)}|{'reroll':Action('reroll')}

class API:
    def __init__(self,budget):
        self.budget=budget
        self.client=httpx.Client(timeout=httpx.Timeout(60,connect=15),headers={
            'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY'],
            'Content-Type':'application/json','X-Title':'Bounded Jev algebra controller experiment'})
    def call(self,key,payload):
        rawpath=OUT/'raw'/(key+'.json')
        self.budget.book(key)
        record={'request':payload,'started_at':stamp()};t=time.perf_counter();body={}
        try:
            r=self.client.post('https://openrouter.ai/api/alpha/decisions',json=payload)
            record['http_status']=r.status_code
            try:body=r.json()
            except ValueError:body={'non_json':r.text[:2000]}
            record['response']=body
        except httpx.TransportError as e:record['error']=type(e).__name__
        record['seconds']=time.perf_counter()-t
        # All response charges, including non-200 responses, are accounted for.
        cost=body.get('usage',{}).get('cost');self.budget.settle(key,cost)
        write_json(rawpath,record)
        if record.get('http_status')!=200 or 'error' in body:return None,record
        return body,record

def run_episode(policy,level,seed,initial,api,global_start):
    ident=f'{policy}_{level}_{seed:02d}';path=OUT/'episodes'/(ident+'.json')
    assert not path.exists(),'An episode already exists; refusing to overwrite results'
    state=initial;root=solution(initial);rng=random.Random(seed);chooser=random.Random(seed+987654)
    guard=Guard(level,state);d0=distance(state);history=[];rows=[];start=time.perf_counter()
    cumulative_cost=0.;cumulative_movement=0;transformations=0;status=None
    while status is None:
        if time.perf_counter()-start>guard.limits['seconds']:status='cutoff_episode_time';break
        if policy=='jev' and time.perf_counter()-global_start>GUARDS['global_seconds']:status='cutoff_global_time';break
        step=guard.steps+1;before=state;d_before=distance(state)
        pool,menu=build_menu(state,rng)
        criteria={label:describe(state,a) for label,a in menu.items()}
        payload={'model':MODEL,'state':GUIDE+'\n\nCURRENT EQUATION: '+equation(state)+
                 '\nRecent actions (oldest first): '+json.dumps(history[-6:])+
                 f'\nDecision {step} of {guard.limits["decisions"]}. Rerolls used {guard.rerolls} of {GUARDS["reroll_total"]}; consecutive rerolls {guard.streak} of {GUARDS["reroll_streak"]}.',
                 'questions':{'answer':{'type':'choice','instructions':'Select the single most useful next operation toward x = a numeric constant, or reroll if no operation helps. Read the operation explanations carefully.','criteria':criteria}},
                 'provider':{'allow_fallbacks':False,'max_price':{'prompt':GUARDS['price_cap_usd_per_million'],'completion':'0'}}}
        if len(json.dumps(payload).encode())>GUARDS['request_bytes']:status='cutoff_context';break
        body={};latency=0.;cost=0.;selected_prob=None
        if policy=='jev':
            try:body,record=api.call(f'{ident}_{step:03d}',payload)
            except BudgetStop:status='cutoff_global_budget';break
            latency=record['seconds']
            if body is None:status='api_failure';break
            answer=body.get('answers',{}).get('answer',{});label=answer.get('choice')
            probs=answer.get('probabilities',{})
            selected_prob=probs.get(label) if isinstance(probs,dict) else None
            cost=body.get('usage',{}).get('cost') or 0.;cumulative_cost+=cost
        else:label=chooser.choice(list(menu))
        if label not in menu:status='invalid_model_label';break
        a=menu[label];state=apply(state,a)
        assert solution(state)==root,'Mathematical validity invariant violated'
        d_after=distance(state);delta=d_before-d_after
        cumulative_movement+=abs(delta)
        transformations+=int(a.kind not in ('reroll','declare_solved'))
        status=guard.advance(a,state,d_after)
        history.append({'action':criteria[label],'result':equation(state)})
        row={'step_i':step,'label':label,'action':a.serial(),'action_text':criteria[label],
             'before':equation(before),'after':equation(state),'after_ast':state,
             'reference_steps_before':d_before,'reference_steps_after':d_after,
             'reference_steps_best':guard.best,'delta_reference_steps':delta,
             'fraction_remaining':d_after/d0,'fraction_progress':1-d_after/d0,
             'cumulative_net_progress_steps':d0-d_after,
             'cumulative_absolute_reference_movement':cumulative_movement,
             'cumulative_transformations':transformations,'cumulative_rerolls':guard.rerolls,
             'decisions_without_new_best':step-guard.last_improved,
             'selected_probability':selected_prob,'cost_usd':cost,'cumulative_cost_usd':cumulative_cost,
             'latency_seconds':latency,'status':status,'pool_size':len(pool),
             'reference_action_offered':reference_action(before) in menu.values(),
             'improving_action_offered':any(distance(apply(before,c))<d_before for c in menu.values()),
             'menu':{k:{'action':v.serial(),'description':criteria[k]} for k,v in menu.items()}}
        rows.append(row)
        # A crash leaves all completed decisions and the persistent budget auditable.
        with (OUT/'steps'/f'{ident}.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    result={'episode_id':ident,'policy':policy,'level':level,'seed':seed,'status':status,
        'initial_equation':equation(initial),'initial_ast':initial,'solution':str(root),
        'initial_reference_steps':d0,'final_equation':equation(state),
        'final_reference_steps':distance(state),'best_reference_steps':guard.best,
        'steps':guard.steps,'transformations':transformations,'rerolls':guard.rerolls,
        'seconds':time.perf_counter()-start,'cost_usd':cumulative_cost,'trajectory':rows}
    write_json(path,result)
    print(json.dumps({k:v for k,v in result.items() if k in ('episode_id','status','steps','final_reference_steps','cost_usd')}),flush=True)
    return result

def protocol():
    eqs=equations()
    return {'created_at':stamp(),'model':MODEL,'seeds':SEEDS,'representative_seed':0,
        'limits':LIMITS,'guards':GUARDS,'guide':GUIDE,
        'equations':{k:{'equation':equation(v),'ast':v,'hidden_solution':str(solution(v)),
                        'initial_reference_steps':distance(v)} for k,v in eqs.items()},
        'menu':'Uniformly sample 10 distinct executable actions without replacement; reshuffle; add reroll. No progress-based filtering or guaranteed useful action.',
        'metric':'Number of rewrites remaining under a fixed deterministic normalization policy; NOT shortest-path distance. No value is given to Jev.',
        'baseline':'Uniform random choice among the same 11 menu entries, same guards. Equal seeds share the initial menu; subsequent states and menus may diverge.',
        'stopping':'No retries, restarts, cherry-picking, or adaptive retuning after model results. A spent reservation is retained if a charge is unknown.',
        'source_sha256':{n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ['algebra_engine.py','run_experiment.py']}}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');args=parser.parse_args()
    if not args.execute:print(json.dumps(protocol(),indent=2));return
    assert not (OUT/'protocol.json').exists(),'Existing experiment found: refusing a second billable run'
    for name in ['raw','episodes','steps']:(OUT/name).mkdir(exist_ok=True)
    write_json(OUT/'protocol.json',protocol())
    budget=Budget(OUT/'budget.json',GUARDS['hard_cap_usd'],GUARDS['reservation_usd']);api=API(budget)
    start=time.perf_counter();results=[];eqs=equations()
    # Three simultaneous episodes: API exposure reservations are serialized.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(run_episode,'jev',level,seed,initial,api,start)
                 for seed in SEEDS for level,initial in eqs.items()]
        for future in as_completed(futures):results.append(future.result())
    api.client.close()
    for seed in SEEDS:
        for level,initial in eqs.items():results.append(run_episode('random',level,seed,initial,None,start))
    write_json(OUT/'run_manifest.json',{'finished_at':stamp(),'episode_count':len(results),
                                     'seconds':time.perf_counter()-start,'protocol_sha256':hashlib.sha256((OUT/'protocol.json').read_bytes()).hexdigest()})

if __name__=='__main__':main()
