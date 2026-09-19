"""Read-only accounting and result-integrity audit after the campaign completes."""
import hashlib
import json
from pathlib import Path
from decimal import Decimal
from collections import Counter
import statistics
import sys
import platform
import importlib.metadata as metadata
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import campaign as c

def main():
    protocol=json.loads((ROOT/'protocol.json').read_text())
    assert (ROOT/'completed.json').exists(),'Campaign still running'
    followup_count=0
    if (ROOT/'factorial_rollout_protocol.json').exists():
        import factorial_rollouts as followup
        assert (ROOT/'factorial_rollout_completed.json').exists(),'Follow-up still running'
        followup.check_hashes()
        followup_count=len(list((ROOT/'factorial_rollouts').glob('*.json')))
        assert followup_count==96
        assert (ROOT/'factorial_rollout_summary.json').exists(),'Follow-up replay analysis missing'
    for name,h in protocol['source_sha256'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    assert hashlib.sha256((c.OLD/'algebra_engine.py').read_bytes()).hexdigest()==protocol['engine_sha256']
    ledger=json.loads((ROOT/'budget.json').read_text());attempts=ledger['attempts']
    jobs={j['id']:j for j in map(json.loads,(ROOT/'jobs.jsonl').read_text().splitlines())}
    cases={v['id']:v for v in json.loads((ROOT/'cases.json').read_text())}
    responses={p.stem:json.loads(p.read_text()) for p in (ROOT/'responses').glob('*.json')}
    assert set(responses)==set(jobs)
    raw={p.stem:json.loads(p.read_text()) for p in (ROOT/'raw').glob('*.json')}
    accounted=set();cost=Decimal(0);models=Counter();providers=Counter();http=Counter();tokens=[];latencies=[];cost_by_arm=Counter()
    for ident,record in raw.items():
        assert record['request_sha256']==c.sha(json.dumps(record['request'],sort_keys=True))
        for i,a in enumerate(record['attempts']):
            k=f'{ident}__attempt{i}';assert k in attempts;accounted.add(k)
            usd=a.get('response',{}).get('usage',{}).get('cost')
            if usd is not None:
                exact=Decimal(str(usd));assert Decimal(attempts[k]['actual_usd'])==exact
                cost+=exact;cost_by_arm[ident.split('__')[0]]+=float(exact)
            http[str(a.get('http_status','transport_error'))]+=1;latencies.append(a['seconds'])
        body=record.get('response',{})
        if body:
            models[body.get('model','unknown')]+=1;providers[body.get('provider','unknown')]+=1
            tokens.append(body.get('usage',{}).get('input_tokens',0))
    assert accounted==set(attempts),'Unmatched budget reservation or raw response'
    assert all(a['status']!='reserved' for a in attempts.values())
    assert cost==sum((Decimal(a.get('actual_usd','0')) for a in attempts.values()),Decimal(0))
    exposure=Decimal(ledger['prior_exposure_usd'])+sum((Decimal(a['accounted_usd']) for a in attempts.values()),Decimal(0))
    assert exposure<=Decimal(ledger['combined_cap_usd'])
    scored=0
    for ident,r in responses.items():
        job=jobs[ident]
        if r['status']!='ok':continue
        assert raw[ident]['request']==job['request']
        case=cases[r['case_id']]
        check=c.score_response(c.freeze(case['state']),c.restore_menu(job['menu']),raw[ident]['response'],case['candidate_costs'])
        assert check['choice']==r['choice'] and check['probabilities']==r['probabilities']
        assert check['evaluators']==r['evaluators'];scored+=1
    fx=json.loads((c.OLD/'fx.json').read_text());rate=Decimal(str(fx['rates']['USD']))
    out={'passed':True,'static_records':len(responses),'static_statuses':dict(Counter(r['status'] for r in responses.values())),
        'static_scores_recomputed':scored,'rollout_records':len(list((ROOT/'rollouts').glob('*.json'))),
        'followup_rollout_records':followup_count,
        'requests':len(raw),'attempts':len(attempts),'http_statuses':dict(http),'models':dict(models),'providers':dict(providers),
        'new_cost_usd':str(cost),'prior_cost_usd':ledger['prior_exposure_usd'],
        'combined_accounted_exposure_usd':str(exposure),'combined_cost_gbp_estimate':float(exposure/rate),
        'new_cost_gbp_estimate':float(cost/rate),'fx_gbp_usd':float(rate),'cost_by_arm_usd':dict(cost_by_arm),
        'unsettled_or_unknown_costs':sum(a['status']!='settled' for a in attempts.values()),
        'input_tokens_min':min(tokens),'input_tokens_max':max(tokens),'input_tokens_total':sum(tokens),
        'request_seconds_median':statistics.median(latencies),
        'checks':['frozen source and data hashes','all static jobs have terminal records','all responses match frozen requests',
                  'all three evaluator scores independently recomputed from saved probabilities and costs',
                  'every budget entry reconciled against raw attempts','combined spending cap includes prior experiment']}
    c.write(ROOT/'audit.json',out)
    c.write(ROOT/'environment.json',{'python':platform.python_version(),'packages':{n:metadata.version(n) for n in ['httpx','numpy','matplotlib','scipy']}})
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
