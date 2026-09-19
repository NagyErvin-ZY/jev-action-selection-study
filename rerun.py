"""Explicit opt-in rerun of the frozen main design, with isolated accounting."""
from pathlib import Path
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse, json, os, sys, threading
from reproduce import extract,ROOT

MODEL='typesafe/jev-1.13-20260917'

def verify_response(body,budget,stop_type):
    if body and (body.get('model')!=MODEL or body.get('provider')!='TypeSafe'):
        budget.halt();raise stop_type('unexpected_model_or_provider')

class Budget:
    def __init__(self,path,cap,stop_type):
        self.path=path;self.cap=Decimal(cap);self.lock=threading.Lock();self.stop_type=stop_type
        self.data={'cap_usd':str(self.cap),'reservation_usd':'0.002','attempts':{},'halted':False}
        self.save()
    def save(self):
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.data,indent=2));tmp.replace(self.path)
    def exposure(self):return sum((Decimal(v['accounted_usd']) for v in self.data['attempts'].values()),Decimal(0))
    def reserve(self,key):
        with self.lock:
            if self.data['halted'] or self.exposure()+Decimal('.002')>self.cap:raise self.stop_type('new_run_budget')
            assert key not in self.data['attempts']
            self.data['attempts'][key]={'status':'reserved','accounted_usd':'0.002'};self.save()
    def settle(self,key,cost):
        with self.lock:
            row=self.data['attempts'][key]
            if cost is None:row['status']='uncertain_charge'
            else:
                cost=Decimal(str(cost));assert cost.is_finite() and cost>=0
                row.update(status='settled',accounted_usd=str(cost),actual_usd=str(cost))
                if cost>Decimal('.002'):self.data['halted']=True
            self.save()
    def halt(self):
        with self.lock:self.data['halted']=True;self.save()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute',action='store_true');ap.add_argument('--output',type=Path)
    ap.add_argument('--cap-usd');args=ap.parse_args()
    if not args.execute:
        print('No calls made. A new run requires --execute --output NEW_DIRECTORY --cap-usd AMOUNT.');return
    if args.output is None or args.cap_usd is None:ap.error('Explicit output and cap required.')
    try:cap=Decimal(args.cap_usd)
    except Exception:ap.error('Invalid cap.')
    if not cap.is_finite() or cap<=0:ap.error('Cap must be finite and positive.')
    if not os.environ.get('OPENROUTER_API_KEY'):ap.error('OPENROUTER_API_KEY is required for explicit execution.')
    output=args.output.resolve()
    if output.exists():ap.error('Output must be new; no archive or previous run is overwritten.')
    output.mkdir(parents=True)
    snapshot=extract(output/'frozen-input')
    sys.path.insert(0,str(snapshot/'jev-hypotheses'))
    import campaign as c
    work=output/'new-results';work.mkdir();c.OUT=work
    for name in ['raw','responses','rollouts','rollout_checkpoints']:(work/name).mkdir()
    budget=Budget(work/'budget.json',cap,c.Stop)
    class PinnedAPI(c.API):
        def call(self,ident,payload):
            payload={**payload,'model':MODEL}
            body,record=super().call(ident,payload)
            verify_response(body,budget,c.Stop)
            return body,record
    api=PinnedAPI(budget)
    src=snapshot/'jev-hypotheses'
    jobs=[json.loads(v) for v in (src/'jobs.jsonl').read_text().splitlines()]
    cases={v['id']:v for v in json.loads((src/'cases.json').read_text())}
    rollout_cases={v['id']:v for v in json.loads((src/'rollout_cases.json').read_text())}
    tasks=json.loads((src/'rollout_tasks.json').read_text())
    c.write(work/'new-run-protocol.json',{'model':MODEL,'provider':'TypeSafe','cap_usd':str(cap),
            'note':'New responses to the frozen main design, including saved pilot states. No new equation families. Later six-cell follow-up not repeated.',
            'archive_sha256':__import__('hashlib').sha256((ROOT/'evidence.zip').read_bytes()).hexdigest(),
            'started_at':c.stamp(),'wrapper_sha256':c.sha(Path(__file__).read_bytes())})
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            pending=[pool.submit(c.static_job,j,cases,api) for j in jobs]
            pending += [pool.submit(c.rollout,t,rollout_cases,api) for t in tasks]
            for f in as_completed(pending):f.result()
    finally:api.client.close()
    print('New results: '+str(work)+'; accounted USD '+str(budget.exposure()))

if __name__=='__main__':main()
