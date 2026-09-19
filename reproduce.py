"""Offline evidence verification and regeneration. No credentials or model calls."""
from pathlib import Path
import argparse, hashlib, json, os, subprocess, sys, zipfile

ROOT=Path(__file__).resolve().parent
def sha(b):return hashlib.sha256(b).hexdigest()

def extract(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise SystemExit('Choose a new output directory; existing output is never overwritten.')
    destination.mkdir(parents=True)
    manifest=json.loads((ROOT/'public-manifest.json').read_text())
    with zipfile.ZipFile(ROOT/'evidence.zip') as z:
        assert set(z.namelist())==set(manifest),'Archive inventory mismatch'
        for name,item in manifest.items():
            p=destination/name
            assert p.resolve().is_relative_to(destination),'Unsafe archive path'
            b=z.read(name);assert sha(b)==item['public_sha256'],name
            p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
            if name.endswith('.py'):
                assert (ROOT/'study'/name).read_bytes()==b,'Frozen source mirror differs: '+name
    return destination

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT/'reproduced')
    args=ap.parse_args();out=extract(args.output)
    # Every analysis subprocess has socket access disabled, including with a key set.
    guard=out/'network_guard';guard.mkdir()
    (guard/'sitecustomize.py').write_text('import socket\ndef blocked(*a, **k):\n    raise RuntimeError("Network disabled during offline reproduction")\nsocket.socket.connect=blocked\nsocket.socket.connect_ex=blocked\nsocket.create_connection=blocked\n')
    env={k:v for k,v in os.environ.items() if 'API_KEY' not in k and k not in ['OPENAI_API_KEY','OPENROUTER_API_KEY']}
    env.update(PYTHONPATH=str(guard),MPLCONFIGDIR=str(out/'matplotlib-cache'),PYTHONHASHSEED='0',MPLBACKEND='Agg')
    commands=[('jev-algebra','test_engine.py',[]),('jev-algebra','test_safeguards.py',[]),
              ('jev-algebra','analyze_and_plot.py',[]),('jev-algebra','score_action_probabilities.py',[]),
              ('jev-hypotheses','oracle_audit.py',[]),('jev-hypotheses','test_analyze_static.py',[]),
              ('jev-hypotheses','analyze_static.py',[]),('jev-hypotheses','analyze_rollouts.py',[]),
              ('jev-hypotheses','factorial_rollouts.py',['--analyze']),('jev-hypotheses','audit_campaign.py',[])]
    logs=out/'logs';logs.mkdir()
    for folder,script,extra in commands:
        print('Rebuilding '+script,flush=True)
        with (logs/(script+'.log')).open('w') as log:
            subprocess.run([sys.executable,str(out/folder/script),*extra],cwd=out/folder,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    subprocess.run([sys.executable,str(ROOT/'tools/verify_results.py'),str(out)],env=env,check=True)
    print('Verified. Article numbers: '+str(out/'headlines.json'))
    print('Article figure: '+str(out/'article-completion.png'))

if __name__=='__main__':main()
