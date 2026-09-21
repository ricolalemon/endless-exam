"""Verify a reference-matching construction for every formal instance, offline."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import time

for variable in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ.setdefault(variable, '1')

import exam
from crosscheck import SECOND
from openceiling import FAMILIES, expand_answer
from run_ladder import extract_json

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT/'bench/data/reference_witnesses/index.json'


def equal(a,b):
    return a==b if isinstance(a,int) and isinstance(b,int) else math.isclose(a,b,rel_tol=1e-12,abs_tol=0)


def verify(tokens=False):
    index = json.loads(INDEX.read_text())
    cases = {c['instance_id']:c for c in exam.suite()}
    assert len(cases)==len(index['records'])==69
    assert set(cases)=={r['instance_id'] for r in index['records']}
    encodings = {}
    if tokens:
        import tiktoken
        encodings = {name:tiktoken.get_encoding(name) for name in ['cl100k_base','o200k_base']}
    checked = []
    for r in index['records']:
        path = ROOT/r['witness'];raw = path.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['sha256'],r['witness']
        data=json.loads(raw);case=cases[r['instance_id']]
        assert all(data[k]==case[k] for k in ['family','params','reference','reference_type'])
        payload=json.dumps({'answer':data['answer']},sort_keys=True,separators=(',',':'),ensure_ascii=False)
        answer=extract_json(payload);assert answer==data['answer']
        counts={name:len(e.encode(payload)) for name,e in encodings.items()}
        if counts:assert max(counts.values())<=128000
        start=time.monotonic()
        scored=exam.score_record(case,{'answer':answer,'finish_reason':'stop','output_tokens':max(counts.values()) if counts else None})
        primary_seconds=time.monotonic()-start
        assert scored['valid'] and equal(scored['objective'],case['reference']) and equal(scored['ratio'],1),r['instance_id']
        def timeout(*args):raise TimeoutError(r['instance_id'])
        old=signal.signal(signal.SIGALRM,timeout);signal.alarm(60);start=time.monotonic()
        try:
            secondary=SECOND[case['family']](case['params'],expand_answer(FAMILIES[case['family']],case['params'],answer))
        finally:
            secondary_seconds=time.monotonic()-start
            signal.alarm(0);signal.signal(signal.SIGALRM,old)
        assert secondary[0] and equal(secondary[1],case['reference']),r['instance_id']
        assert max(primary_seconds,secondary_seconds)<60
        checked.append({**r,'primary_objective':scored['objective'],'independent_objective':secondary[1],
                        'ratio':scored['ratio'],'primary_seconds':primary_seconds,'independent_seconds':secondary_seconds,
                        'output_tokens':counts,'json_bytes':len(payload.encode())})
    groups={}
    for kind in ['published','construction']:
        rows=[r for r in checked if r['reference_type']==kind]
        groups[kind]={'instances':len(rows),'verified':len(rows),
                      'max_output_tokens':max((max(r['output_tokens'].values()) for r in rows),default=None) if tokens else None}
    assert groups['published']['instances']==30 and groups['construction']['instances']==39
    return {'index_sha256':hashlib.sha256(INDEX.read_bytes()).hexdigest(),'groups':groups,
            'distinct_instances':69,'all_ratios_one':True,'all_dual_verified':True,
            'token_encodings':list(encodings),'output_token_limit':128000,'verification_seconds_per_checker':60,
            'records':checked}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tokens',action='store_true',help='Count answer tokens; requires tiktoken')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=verify(args.tokens)
    if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'},indent=2))


if __name__=='__main__':main()
