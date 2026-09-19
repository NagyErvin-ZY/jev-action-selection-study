"""Frozen parallel hypothesis campaign. Paid calls require --execute.

One process owns the billable transport. All conditions and rollout policies are
fixed before inference. Previous algebra exposure is imported into a stricter
$2 total cap, below the user's GBP2 ceiling. --resume never resets spending.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import threading
import time
import httpx
import numpy as np

OUT=Path(__file__).resolve().parent;OLD=OUT.parent/'jev-algebra'
sys.path.insert(0,str(OLD))
from algebra_engine import *
from score_action_probabilities import score_distribution
from new_cases import build_cases,build_rollout_cases
from prompt_arms import VARIANTS,make_payload
from oracle_audit import alternative_distance

POLICIES=['reference','shallow_first','cleanup_first']
BASE=next(v for v in VARIANTS if not v['neutral'] and not v['structured'] and not v['guided'])
COMBINED=next(v for v in VARIANTS if v['neutral'] and v['structured'] and v['guided'])
REPEATS=2
LIMITS={'combined_cap_usd':'2.00','reservation_usd':'0.002','concurrency':8,
        'attempt_cap':10000,'deadline_seconds':2400,'request_bytes':100000,
        'request_timeout_seconds':60,'max_attempts_per_request':2,
        'consecutive_errors':12,'reroll_streak':3,'reroll_total':8,'state_visits':3,
        'premature_claims':2,'rollout_seconds':600}
WORDS='''Duck Car Ball Furnace Apple River Cloud Spoon Tiger Piano
Window Rocket Basket Lemon Chair Mountain Pencil Ocean Rabbit Hammer
Garden Candle Bridge Feather Clock Castle Button Forest Mirror Turtle
Velvet Copper Lantern Pebble Violin Anchor Mango Ladder Pillow Falcon
Meadow Kettle Marble Cactus Ribbon Compass Walnut Glacier Helmet Dolphin
Apricot Tunnel Saddle Biscuit Planet Needle Carpet Sparrow Bucket Volcano
Jacket Acorn Diamond Tractor Tulip Coral Drum Otter Socket Papaya
Igloo Magnet Teapot Badger Cobalt Hammock Orchid Waffle Sailboat Quartz
Pumpkin Zebra Shovel Coconut Tinsel Parrot Canyon Mittens Radish Whistle
Cricket Faucet Honeycomb Sapphire Turnip Wagon Oyster Puddle Salmon Notebook'''.split()

def stamp():return datetime.now(timezone.utc).isoformat()
def sha(x):return hashlib.sha256(x.encode() if isinstance(x,str) else x).hexdigest()
def seed(x):return int(sha(str(x))[:12],16)
def freeze(x):return tuple(freeze(v) for v in x) if isinstance(x,list) else x
def write(path,obj):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2));tmp.replace(path)
def restore(a):return Action(a['kind'],a['side'],tuple(a['path']),a['i'],a['j'],F(a['arg']))
def key(a):return json.dumps(a.serial(),sort_keys=True)
def serialize_menu(menu):return {label:a.serial() for label,a in menu.items()}
def restore_menu(menu):return {label:restore(a) for label,a in menu.items()}

def costs(state):
    output={}
    for a in all_actions(state):
        if a.kind=='declare_solved':continue
        nxt=apply(state,a);assert solution(nxt)==solution(state)
        ds={'reference':distance(nxt)}
        for p in POLICIES[1:]:
            d=alternative_distance(nxt,p);assert isinstance(d,int),f'Oracle failure: {p} {d}'
            ds[p]=d
        output[key(a)]={'kind':a.kind,'costs':ds,'node_count_after':state_nodes(nxt)}
    return output

def sample_menu(state,rng,mode='random'):
    pool=all_actions(state);useful=[a for a in pool if a.kind!='declare_solved' and distance(apply(state,a))<distance(state)]
    if mode=='omit_improving':
        pool=[a for a in pool if a not in useful]
        if len(pool)<10:return None
        chosen=rng.sample(pool,10)
    else:
        forced=[]
        if mode=='cover_best':
            legal=[a for a in pool if a.kind!='declare_solved'];best=min(distance(apply(state,a)) for a in legal)
            forced=[rng.choice([a for a in legal if distance(apply(state,a))==best])]
        elif mode=='cover_four':forced=rng.sample(useful,min(4,len(useful)))
        chosen=forced+rng.sample([a for a in pool if a not in forced],10-len(forced))
    rng.shuffle(chosen)
    return {f'move_{i+1:02d}':a for i,a in enumerate(chosen)}|{'reroll':Action('reroll')}

def saved_cases():
    scored={(r['episode_id'],r['step_i']):r for r in map(json.loads,(OLD/'probability_scores.jsonl').read_text().splitlines())}
    by_level={l:[] for l in ['simple','medium','unholy']}
    for f in sorted((OLD/'episodes').glob('jev_*.json')):
        episode=json.loads(f.read_text());state=freeze(episode['initial_ast']);history=[]
        for row in episode['trajectory']:
            raw=json.loads((OLD/'raw'/f'{episode["episode_id"]}_{row["step_i"]:03d}.json').read_text())
            by_level[episode['level']].append({'id':f'saved_{episode["episode_id"]}_{row["step_i"]:03d}',
                'family':'saved_'+episode['level'],'split':'saved_diagnostic','origin':'saved',
                'state':state,'history':history[-6:].copy(),
                'menu':{k:restore(v['action']) for k,v in row['menu'].items()},
                'factors':{},'derived':{'reference_steps':distance(state),'nodes':state_nodes(state)},
                'selection_quality':scored[(episode['episode_id'],row['step_i'])]['probability_quality']})
            history.append({'action':row['action_text'],'result':row['after']});state=freeze(row['after_ast'])
    selected=[]
    for level,rows in by_level.items():
        unique={}
        for r in rows:unique.setdefault((signature(r['state']),tuple(key(a) for a in r['menu'].values())),r)
        ordered=sorted(unique.values(),key=lambda r:(r['selection_quality'],r['id']))
        assert len(ordered)>=8
        selected.extend(ordered[i] for i in np.linspace(0,len(ordered)-1,8).round().astype(int))
    return selected

def prepare():
    assert not (OUT/'protocol.json').exists(),'Frozen campaign already exists; use --execute or --resume'
    cases=saved_cases()
    for c in build_cases():
        cases.append({**c,'origin':'fresh','history':[],
                      'menu':sample_menu(c['state'],random.Random(seed(c['id'])))})
    for c in cases:c['candidate_costs']=costs(c['state'])
    side_ids={c['id'] for c in cases if c['origin']=='saved'}
    fresh=[c for c in cases if c['origin']=='fresh']
    for family in sorted({c['family'] for c in fresh}):
        group=sorted([c for c in fresh if c['family']==family],key=lambda c:c['id'])
        side_ids.update([group[0]['id'],group[-1]['id']])
    jobs=[];omitted=[]
    def add(c,variant,kind,condition,menu=None):
        menu=menu if menu is not None else c['menu']
        payload=make_payload(c['state'],menu,c['history'],variant)
        assert len(json.dumps(payload).encode())<=LIMITS['request_bytes']
        for rep in range(REPEATS):
            jobs.append({'id':f'{kind}__{c["id"]}__{condition}__r{rep}',
              'case_id':c['id'],'kind':kind,'condition':condition,'variant':variant,
              'repeat':rep,'menu':serialize_menu(menu),'request':payload})
    for c in cases:
        for variant in VARIANTS:add(c,variant,'core',variant['id'])
        if c['id'] not in side_ids:continue
        for condition in ['cover_best','cover_four','omit_improving']:
            menu=sample_menu(c['state'],random.Random(seed(c['id']+condition)),condition)
            if menu is None:omitted.append({'case_id':c['id'],'condition':condition,'reason':'fewer_than_ten_nonimproving_actions'});continue
            add(c,BASE,'menu',condition,menu)
        originals=[(k,a) for k,a in c['menu'].items() if a.kind!='reroll']
        words=random.Random(seed(c['id']+'words')).sample(WORDS,len(originals))
        for condition in ['reverse','words','words_reverse']:
            pairs=[(words[i] if 'words' in condition else k,a) for i,(k,a) in enumerate(originals)]
            if 'reverse' in condition:pairs.reverse()
            add(c,BASE,'labels',condition,dict(pairs)|{'reroll':Action('reroll')})
        if c['history']:add(c,{**BASE,'history_mode':'none'},'history','none')
        for size in [2000,6000]:
            for position in ['prefix','suffix']:
                add(c,{**BASE,'history_mode':'padding','padding_words':size,'padding_position':position},
                    'history',f'padding_{size}_{position}')
    random.Random(20260919).shuffle(jobs)
    rollout_cases=build_rollout_cases();rollout_tasks=[]
    for c in rollout_cases:
        for policy in ['original_random','combined_random','combined_coverage']:
            for rep in range(2):rollout_tasks.append({'case_id':c['id'],'policy':policy,'repeat':rep})
    random.Random(19202609).shuffle(rollout_tasks)
    budget=json.loads((OLD/'budget.json').read_text());prior=sum(Decimal(a['accounted_usd']) for a in budget['attempts'].values())
    assert all(a['status']=='settled' for a in budget['attempts'].values())
    write(OUT/'prior_budget.json',budget)
    write(OUT/'cases.json',[{**c,'menu':serialize_menu(c['menu'])} for c in cases])
    write(OUT/'rollout_cases.json',rollout_cases)
    write(OUT/'rollout_tasks.json',rollout_tasks)
    with (OUT/'jobs.jsonl').open('w') as f:
        for job in jobs:f.write(json.dumps(job)+'\n')
    frozen=['campaign.py','new_cases.py','prompt_arms.py','oracle_audit.py','cases.json','jobs.jsonl','rollout_cases.json','rollout_tasks.json']
    protocol={'created_at':stamp(),'model':'typesafe/jev-1.13','limits':LIMITS,
        'prior_algebra_exposure_usd':str(prior),'core_cases':len(cases),'fresh_cases':len(fresh),
        'saved_cases':len(cases)-len(fresh),'template_clusters':len({c['family'] for c in fresh}),
        'variants':VARIANTS,'repeats':REPEATS,'static_jobs':len(jobs),'side_case_count':len(side_ids),
        'job_counts':dict(Counter(j['kind'] for j in jobs)),'omitted_conditions':omitted,
        'rollout_tasks':len(rollout_tasks),'rollout_policies':['original_random','combined_random','combined_coverage'],
        'evaluators':POLICIES,'primary_comparisons':'Paired same-state factorial main effects and combined-vs-original; report all3 evaluators. Full-pool expected regret for menu changes. Equal-template summaries for fresh families; source-equation clustering for saved states.',
        'heldout':'Four of eight fresh template families designated in new_cases.py before model calls. No treatment selection uses their responses.',
        'secondary':'Order/label sensitivity vs identical-repeat variability; padding/history; confidence/error association. Fresh rollout solve rate, actual decisions, cutoffs.',
        'limits_of_inference':'Eight templates, not128 independent domains. Depth changes node count/horizon. Added guidance adds information. Structure representation changes length. Padding changes content/placement, not only token count. Three reference policies are not general optimal oracles.',
        'source_sha256':{n:sha((OUT/n).read_bytes()) for n in frozen},
        'engine_sha256':sha((OLD/'algebra_engine.py').read_bytes())}
    write(OUT/'protocol.json',protocol)
    print(json.dumps({k:v for k,v in protocol.items() if k in ['static_jobs','job_counts','core_cases','fresh_cases','saved_cases','side_case_count','rollout_tasks','prior_algebra_exposure_usd']},indent=2),flush=True)

class Stop(Exception):pass
class Budget:
    def __init__(self):
        self.path=OUT/'budget.json';self.lock=threading.Lock()
        prior=json.loads((OUT/'protocol.json').read_text())['prior_algebra_exposure_usd']
        self.data=json.loads(self.path.read_text()) if self.path.exists() else {'prior_exposure_usd':prior,'combined_cap_usd':'2.00','attempts':{},'halted':False}
    def exposure(self):return Decimal(self.data['prior_exposure_usd'])+sum((Decimal(a['accounted_usd']) for a in self.data['attempts'].values()),Decimal(0))
    def reserve(self,k):
        with self.lock:
            if self.data['halted'] or self.exposure()+Decimal('.002')>Decimal('2') or len(self.data['attempts'])>=LIMITS['attempt_cap']:raise Stop('global_budget_or_attempt_limit')
            assert k not in self.data['attempts']
            self.data['attempts'][k]={'accounted_usd':'.002','status':'reserved','time':stamp()};write(self.path,self.data)
    def settle(self,k,cost):
        with self.lock:
            a=self.data['attempts'][k]
            if cost is None:a['status']='uncertain_charge'
            else:
                d=Decimal(str(cost));assert d>=0
                a.update(accounted_usd=str(d),actual_usd=str(d),status='settled')
                if d>Decimal('.002'):self.data['halted']=True
            write(self.path,self.data)

class API:
    def __init__(self,budget):
        self.budget=budget;self.start=time.monotonic();self.sem=threading.Semaphore(LIMITS['concurrency']);self.errors=0;self.lock=threading.Lock()
        self.client=httpx.Client(timeout=httpx.Timeout(60,connect=15),limits=httpx.Limits(max_connections=8),
            headers={'Authorization':'Bearer '+os.environ['OPENROUTER_API_KEY'],'Content-Type':'application/json','X-Title':'Jev controlled hypothesis campaign'})
    def call(self,ident,payload):
        p=OUT/'raw'/f'{ident}.json';digest=sha(json.dumps(payload,sort_keys=True))
        if p.exists():
            rec=json.loads(p.read_text());assert rec['request_sha256']==digest
            return rec.get('response'),rec
        rec={'request':payload,'request_sha256':digest,'started_at':stamp(),'attempts':[]}
        for attempt in range(LIMITS['max_attempts_per_request']):
            with self.sem:
                if time.monotonic()-self.start>LIMITS['deadline_seconds']:raise Stop('global_time')
                if self.errors>=LIMITS['consecutive_errors']:raise Stop('api_circuit_breaker')
                k=f'{ident}__attempt{attempt}';self.budget.reserve(k);t=time.monotonic();body={};status=None
                try:
                    response=self.client.post('https://openrouter.ai/api/alpha/decisions',json=payload);status=response.status_code
                    try:body=response.json()
                    except ValueError:body={'non_json':response.text[:1000]}
                    a={'http_status':status,'response':body,'seconds':time.monotonic()-t}
                except httpx.TransportError as error:a={'transport_error':type(error).__name__,'seconds':time.monotonic()-t}
                self.budget.settle(k,body.get('usage',{}).get('cost'));rec['attempts'].append(a)
                valid=status==200 and 'error' not in body and 'answers' in body
                with self.lock:self.errors=0 if valid else self.errors+1
                if valid:rec['response']=body;write(p,rec);return body,rec
                write(p,rec)
            if status not in (None,408,429,500,502,503,504,524,529):break
            if attempt==0:time.sleep(1)
        return None,rec

def score_response(state,menu,body,profiles):
    answer=body.get('answers',{}).get('answer',{});prob=answer.get('probabilities',{});selected=answer.get('choice')
    assert set(prob)==set(menu) and selected in menu
    output={}
    for policy in POLICIES:
        opts=[]
        for label,a in menu.items():
            if a.kind in ('reroll','declare_solved'):continue
            opts.append({'label':label,'action_key':key(a),'kind':a.kind,'probability_raw':float(prob[label]),
                         'D_after':profiles[key(a)]['costs'][policy],'selected':label==selected})
        s=score_distribution(opts);s.pop('pairs')
        pool_best=min(v['costs'][policy] for v in profiles.values())
        s['full_pool_best_D']=pool_best;s['full_pool_regret']=None if s['expected_D_after'] is None else s['expected_D_after']-pool_best
        output[policy]=s
    return {'choice':selected,'selected_kind':menu[selected].kind,'selected_probability':prob[selected],
        'reroll_probability':prob.get('reroll',0),'probabilities':prob,'evaluators':output}

def static_job(job,cases,api):
    path=OUT/'responses'/f'{job["id"]}.json'
    if path.exists():return json.loads(path.read_text())
    case=cases[job['case_id']];menu=restore_menu(job['menu']);state=freeze(case['state'])
    result={k:job[k] for k in ['id','case_id','kind','condition','variant','repeat']}
    try:
        body,raw=api.call(job['id'],job['request'])
        if body is None:result['status']='api_failure'
        else:result.update(status='ok',**score_response(state,menu,body,case['candidate_costs']),usage=body.get('usage',{}),resolved_model=body.get('model'))
    except Stop as error:result['status']='cutoff_'+str(error)
    write(path,result);return result

def rollout(task,cases,api):
    ident=f'rollout__{task["case_id"]}__{task["policy"]}__r{task["repeat"]}';path=OUT/'rollouts'/f'{ident}.json'
    if path.exists():return json.loads(path.read_text())
    initial=freeze(cases[task['case_id']]['state']);state=initial;root=solution(state);d0=distance(state)
    maxsteps=min(120,max(24,4*d0+12));stagnation=min(30,max(12,d0));best=d0;last_best=0
    rng=random.Random(seed(task['case_id'])+task['repeat']);history=[];rows=[];visits=Counter({signature(state):1})
    streak=total_rerolls=premature=0;status=None;started=time.monotonic()
    while status is None:
        step=len(rows)+1
        if time.monotonic()-started>LIMITS['rollout_seconds']:status='cutoff_time';break
        mode='cover_best' if task['policy']=='combined_coverage' else 'random'
        menu=sample_menu(state,rng,mode);variant=BASE if task['policy']=='original_random' else COMBINED
        payload=make_payload(state,menu,history[-6:],variant,{'step':step,'decisions':maxsteps,'rerolls':total_rerolls,'reroll_total':8,'streak':streak,'reroll_streak':3})
        if len(json.dumps(payload).encode())>LIMITS['request_bytes']:status='cutoff_context';break
        try:body,raw=api.call(f'{ident}__s{step:03d}',payload)
        except Stop as error:status='cutoff_'+str(error);break
        if body is None:status='api_failure';break
        label=body.get('answers',{}).get('answer',{}).get('choice')
        if label not in menu:status='invalid_label';break
        a=menu[label];before=state;state=apply(state,a);assert solution(state)==root;d=distance(state)
        if a.kind=='reroll':streak+=1;total_rerolls+=1
        else:streak=0
        if a.kind=='declare_solved':premature+=1
        if a.kind not in ('reroll','declare_solved'):visits[signature(state)]+=1
        if d<best:best=d;last_best=step
        if solved(state):status='solved'
        elif streak>=3:status='cutoff_reroll_streak'
        elif total_rerolls>=8:status='cutoff_reroll_total'
        elif visits[signature(state)]>=3:status='cutoff_repeated_state'
        elif premature>=2:status='cutoff_premature_completion'
        elif step-last_best>=stagnation:status='cutoff_stagnation'
        elif step>=maxsteps:status='cutoff_decisions'
        rows.append({'step':step,'before':equation(before),'after':equation(state),'after_ast':state,
            'action':a.serial(),'choice':label,'D_before':distance(before),'D_after':d,'best_D':best,
            'cost_usd':body.get('usage',{}).get('cost'),'status':status})
        history.append({'action':describe(before,a),'result':equation(state)})
        write(OUT/'rollout_checkpoints'/f'{ident}.json',{'rows':rows})
    result={'id':ident,**task,'initial_D':d0,'final_D':distance(state),'best_D':best,'status':status,
       'steps':len(rows),'rerolls':total_rerolls,'max_decisions':maxsteps,'stagnation_limit':stagnation,
       'initial_equation':equation(initial),'final_equation':equation(state),'exact_root':str(root),'trajectory':rows}
    write(path,result);print(json.dumps({'rollout':ident,'status':status,'steps':len(rows)}),flush=True);return result

def execute():
    protocol=json.loads((OUT/'protocol.json').read_text())
    for n,h in protocol['source_sha256'].items():assert sha((OUT/n).read_bytes())==h,'Frozen source changed: '+n
    assert sha((OLD/'algebra_engine.py').read_bytes())==protocol['engine_sha256']
    for name in ['raw','responses','rollouts','rollout_checkpoints']:(OUT/name).mkdir(exist_ok=True)
    budget=Budget();api=API(budget);cases={c['id']:c for c in json.loads((OUT/'cases.json').read_text())}
    rollcases={c['id']:c for c in json.loads((OUT/'rollout_cases.json').read_text())}
    jobs=[json.loads(line) for line in (OUT/'jobs.jsonl').read_text().splitlines()]
    rollout_tasks=json.loads((OUT/'rollout_tasks.json').read_text());counts=Counter();start=time.monotonic()
    with ThreadPoolExecutor(max_workers=8) as static_pool,ThreadPoolExecutor(max_workers=3) as roll_pool:
        futures={static_pool.submit(static_job,job,cases,api):'static' for job in jobs}
        futures.update({roll_pool.submit(rollout,t,rollcases,api):'rollout' for t in rollout_tasks})
        for future in as_completed(futures):
            result=future.result();counts[futures[future]]+=1
            if sum(counts.values())%100==0:
                progress={'completed':dict(counts),'seconds':round(time.monotonic()-start,1),'total_exposure_usd':str(budget.exposure())}
                write(OUT/'progress.json',progress);print(json.dumps(progress),flush=True)
    api.client.close();write(OUT/'completed.json',{'finished_at':stamp(),'completed':dict(counts),'seconds':time.monotonic()-start,'total_exposure_usd':str(budget.exposure())})

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--execute',action='store_true');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
    lock=(OUT/'campaign.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.prepare:prepare()
    if args.execute or args.resume:execute()
    if not (args.prepare or args.execute or args.resume):print('Use --prepare to freeze the protocol; --execute to run. No model calls made.')

if __name__=='__main__':main()
