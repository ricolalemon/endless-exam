"""Deterministic, bounded offline construction calibration; never reads model answers.

These are construction references, not timings for the original 10/600 s search.
All candidates are checked by both existing verifiers before becoming references.
"""
from itertools import combinations, product
from pathlib import Path
import argparse
import hashlib
import json
import math
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'bench/reference_calibration/2026-09-16'
CALIBRATION = {
    'corners': [{'n': n} for n in (96, 120, 174, 210)],
    'kissing_theta': [dict(d=d, cos100=c) for d,c in ((10,28),(10,40),(13,30),(13,42))],
    'lineq': [dict(a=a,b=b,n=n) for a,b,n in ((1,2,4096),(2,5,10000),(3,4,8000))],
    'apfree_q': [dict(q=7,n=n) for n in (2,3)],
    'trifference': [dict(n=n,m=1,representation='certified') for n in (48,80,112,160)],
}


def corners(p):
    n = p['n']; domain = np.arange(1-n,n); weights = n-np.abs(domain)
    best, method = [], ''
    def retain(ds, label):
        nonlocal best, method
        if sum(n-abs(int(d)) for d in ds) > sum(n-abs(d) for d in best):
            best, method = sorted(map(int,ds)), label
    # Translate the whole AP-free digit set, then intersect with the grid's differences.
    digits = [0]
    for j in range(math.ceil(math.log(2*n,3))):
        digits += [d+3**j for d in digits]
    for shift in range(1-n-max(digits),n):
        retain([d+shift for d in digits if abs(d+shift)<n], 'translated ternary digit set')
    # Weighted greedy AP-free differences. A forbidden triple blocks all three roles.
    for alpha in (0,1,2,4):
        for seed in range(8):
            priority = np.random.default_rng(seed).exponential(size=len(domain))/(weights/float(n))**alpha
            blocked = np.zeros(len(domain), dtype=bool); chosen = []
            for at in np.argsort(priority,kind='stable'):
                if blocked[at]: continue
                x = int(domain[at]); ys=np.array(chosen,dtype=np.int64)
                values = np.concatenate((2*x-ys,2*ys-x,(x+ys)[(x+ys)%2==0]//2))
                values=values[(values> -n)&(values<n)]
                blocked[values+n-1] = True; chosen.append(x)
            retain(chosen,f'weighted AP-free greedy alpha={alpha} seed={seed}')
    answer=[[x,y] for x in range(n) for y in range(n) if x-y in set(best)]
    return answer, {'method':method,'difference_set':best}


def signed_pool(d,weight):
    rows=[]
    for support in combinations(range(d),weight):
        for signs in product((-1,1),repeat=weight):
            v=[0]*d
            for i,s in zip(support,signs):v[i]=s
            rows.append(v)
    return np.array(rows,dtype=np.int32)


def spherical(p):
    d,c=p['d'],p['cos100']; best=[]; method=''
    axes=np.concatenate((np.eye(d,dtype=np.int32),-np.eye(d,dtype=np.int32)))
    # Predetermined pools and starts; no fit to formal model constructions.
    pools=[(f'signed weight {w}',signed_pool(d,w)) for w in (3,4,5)]
    pools.append(('binary sign code',np.array(list(product((-1,1),repeat=d)),dtype=np.int32)))
    for label, pool in pools:
        pool=np.concatenate((axes,pool))
        for seed in range(8):
            order=np.arange(len(pool)) if seed==0 else np.random.default_rng(seed).permutation(len(pool))
            candidates=pool[order]; norms=(candidates*candidates).sum(axis=1); chosen=[]
            while len(candidates):
                v=candidates[0]; nv=int(v@v); chosen.append(v.tolist())
                dots=candidates@v
                keep=(dots<=0)|(10000*dots*dots <= c*c*norms*nv)
                candidates=candidates[keep]; norms=norms[keep]
            if len(chosen)>len(best):best,method=chosen,f'{label}, greedy seed={seed}'
    return best,{'method':method}


def lineq(p):
    a,b,n=p['a'],p['b'],p['n']; c=a+b; best=[]; method=''
    for seed in range(-2,16):
        order=range(1,n+1) if seed==-2 else range(n,0,-1) if seed==-1 else np.random.default_rng(seed).permutation(n)+1
        blocked=np.zeros(n+1,dtype=bool); chosen=[]
        for item in order:
            x=int(item)
            if blocked[x]:continue
            ys=np.array(chosen,dtype=np.int64)
            for nums,den in ((a*x+b*ys,c),(a*ys+b*x,c),(c*x-a*ys,b),(c*ys-a*x,b),(c*x-b*ys,a),(c*ys-b*x,a)):
                vals=nums[nums%den==0]//den; vals=vals[(vals>=1)&(vals<=n)]
                blocked[vals]=True
            chosen.append(x)
        if len(chosen)>len(best):best,method=chosen,f'blocked-triple greedy order={seed}'
    return sorted(best),{'method':method}


def finite_ap_greedy(q,n,restarts=64):
    points=np.array(list(product(range(q),repeat=n)),dtype=np.int64)
    powers=q**np.arange(n-1,-1,-1); best=[]; bestseed=None
    for seed in range(restarts):
        order=np.arange(len(points)) if seed==0 else np.random.default_rng(seed).permutation(len(points))
        blocked=np.zeros(len(points),dtype=bool); chosen=[]
        for idx in order:
            if blocked[idx]:continue
            x=points[idx]; ys=np.array(chosen,dtype=np.int64).reshape(-1,n)
            vals=np.concatenate(((2*x-ys)%q,(2*ys-x)%q,((x+ys)*pow(2,-1,q))%q))
            blocked[vals@powers]=True;chosen.append(x.tolist())
        if len(chosen)>len(best):best,bestseed=chosen,seed
    return best,bestseed


def apfree(p):
    q,n=p['q'],p['n'];best,seed=finite_ap_greedy(q,n)
    method=f'finite-field blocked-triple greedy seed={seed}'
    if n>=4 and n%2==0:
        small,seed=finite_ap_greedy(q,2)
        candidate=[sum(t,[]) for t in product(small,repeat=n//2)]
        if len(candidate)>len(best):best,method=candidate,f'product of 2D greedy set seed={seed}, size={len(small)}'
    return [''.join(map(str,row)) for row in best],{'method':method}


def trifference(p):
    # Audit the existing pool plus a canonical PG(1,3) ingredient. Do not read
    # formal answers or retrofit their constructions into a baseline.
    from trifference_scaling import reference_certificate, field_polynomial
    from candidate_families import Trifference
    F=Trifference();best=reference_certificate(p);value=F.verify(p,best)[1]
    rows=['1011','0112'];improved=False
    for N in range(1,min(9,p['n']//4)+1):
        K=min(N,(N+3-p['m'])//3)
        if K<1:continue
        candidate={'rs_concat':{'inner':{'linear_code':rows},'inner_n':4,'inner_m':1,
                               'field':field_polynomial(2),'length':N,'dimension':K}}
        ok,size,_=F.verify(p,candidate)
        assert ok
        if size>value:best,value,improved=candidate,size,True
    return best,{'method':'existing frozen pool + PG(1,3) Reed-Solomon composition audit',
                 'new_ingredient_improved':improved}


BUILDERS={'corners':corners,'kissing_theta':spherical,'lineq':lineq,'apfree_q':apfree,'trifference':trifference}


def run(phase):
    import openceiling as O
    from crosscheck import SECOND
    if phase=='calibration':cases=[(f,p) for f,ps in CALIBRATION.items() for p in ps]
    else:
        if not (OUT/'calibration.json').exists():raise RuntimeError('calibrate before applying to formal parameters')
        import formal_cohort as C
        unique={(c['family'],json.dumps(c['params'],sort_keys=True)) for c in C.cases()
                if c['family'] in BUILDERS and O.known_best(O.FAMILIES[c['family']],c['params']) is None}
        cases=[(f,json.loads(s)) for f,s in sorted(unique)]
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    for i,(family,p) in enumerate(cases):
        t=time.monotonic();answer,info=BUILDERS[family](p)
        first=O.FAMILIES[family].verify(p,answer)[:2];second=SECOND[family](p,answer)
        assert first==second and first[0],(family,p,first,second)
        name=f'{phase}-{i:02d}-{family}.json'
        record={'family':family,'params':p,'objective':first[1],**info,
                'primary_verified':True,'independent_verified':True,'elapsed_s':time.monotonic()-t}
        witness={**record,'answer':answer};path=OUT/name
        path.write_text(json.dumps(witness,separators=(',',':'))+'\n')
        record.update(witness=str(path.relative_to(ROOT)),witness_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        records.append(record);print(family,p,first[1],info,f'{record["elapsed_s"]:.1f}s',flush=True)
    result={'phase':phase,'algorithm_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'records':records}
    (OUT/f'{phase}.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=('calibration','formal'))
    run(parser.parse_args().phase)
