"""Frozen reference pool and four fresh trifference scale instances; no model calls in this module."""
from datetime import datetime,timezone
import argparse,hashlib,json,math,os,random,sys,time
from itertools import combinations,product
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bench'))
from candidate_families import Trifference,trifference_second
from trifference_certificates import rref,irreducible,second_irreducible
POOL=ROOT/'bench/data/trifference_certificate_pool.json'
OUT=ROOT/'bench/results/pilots/astra-medium-trifference-scaling'
TIERS=('T1','T2','T3','T4')
CODE_FILES=['bench/trifference_certificates.py','bench/candidate_families.py','bench/run_ladder.py',
            'bench/openceiling.py','bench/headless_codex.py','bench/agent_bridge.py','bench/trifference_scaling.py',
            'bench/data/trifference_certificate_pool.json']


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows_of_words(words):
    planes=[(sum((c=='1')<<i for i,c in enumerate(w)),sum((c=='2')<<i for i,c in enumerate(w))) for w in words]
    return [''.join(str(((a>>i)&1)+2*((b>>i)&1)) for i in range(len(words[0]))) for a,b in rref(planes)]


def graph_rows(k):
    columns=[]
    for i in range(k):
        v=[0]*k;v[i]=1;columns.append(v)
    for i,j in combinations(range(k),2):
        for a in (1,2):
            v=[0]*k;v[i]=1;v[j]=a;columns.append(v)
    return [''.join(str(c[i]) for c in columns) for i in range(k)]


def field_polynomial(r):
    for low in product(range(3),repeat=r):
        f=[*low,1]
        if irreducible(f):
            assert second_irreducible(f)
            return f
    raise AssertionError(r)


def build_pool():
    F=Trifference();items=[]
    def add(rows,m,source,puncture=False):
        rows=rows_of_words(rows)
        if not rows:return
        # Column deletion is an offline, deterministic reference construction, not model answer repair.
        if puncture:
            for column in range(len(rows[0])-1,-1,-1):
                candidate=[w[:column]+w[column+1:] for w in rows]
                p={'n':len(candidate[0]),'m':m,'representation':'certified'}
                if F.verify(p,{'linear_code':candidate})[0]:rows=candidate
        n=len(rows[0]);p={'n':n,'m':m,'representation':'certified'};a={'linear_code':rows}
        first=F.verify(p,a)[:2];second=trifference_second(p,a)
        assert first==second==(True,3**len(rows)),(p,first,second)
        items.append({'n':n,'m':m,'rank':len(rows),'size':first[1],'rows':rows,'source':source,
                      'punctured_offline':puncture})
    # Already frozen construction references, not C1 model answers.
    for seed in (0,1):
        path=ROOT/f'bench/refs/C1-trifference-{seed}-t10.json'
        r=json.loads(path.read_text());add(rows_of_words(r['search_answer']),1,str(path.relative_to(ROOT)),True)
    # Reproduce a 14-coordinate, rank-four code from projective columns.
    from candidate_families import _projective_code
    _,words=_projective_code(4)
    full=rows_of_words([''.join(map(str,w)) for w in words]);best=full
    for seed in range(32):
        rows=full;keep=list(range(40));order=keep[:];random.Random(seed).shuffle(order)
        for col in order:
            at=keep.index(col);candidate=[w[:at]+w[at+1:] for w in rows]
            if F.verify({'n':len(candidate[0]),'m':1,'representation':'certified'},{'linear_code':candidate})[0]:
                rows=candidate;keep.remove(col)
        if len(rows[0])<len(best[0]):best=rows
        if len(best[0])==14:break
    add(best,1,'PG(3,3) coordinate puncturing; first successful seed among 0..31')
    old=json.loads((ROOT/'bench/data/trifference_references.json').read_text())
    for c in old['codes']:
        if len(c['rows'])<=8:
            add(c['rows'],c['m'],'verified reference pool from ba535c1')
    # Previous model-generated construction is explicitly a source of the NEW stand-in.
    path=ROOT/'bench/results/gpt-6-astra-codex-medium@nocap#A3.jsonl'
    candidates=[r for r in map(json.loads,path.read_text().splitlines()) if r['family']=='trifference' and r['seed']==3]
    assert len(candidates)==1 and candidates[0]['params']=={'n':56,'m':1}
    from run_ladder import extract_json
    a=extract_json(candidates[0]['content'])
    add(a['linear'],1,'A3 Astra medium n=56 result; content SHA256 '+hashlib.sha256(candidates[0]['content'].encode()).hexdigest(),True)
    for k in (9,10,11,12):add(graph_rows(k),1,'projective columns of weight one or two')
    data={'status':'verified construction pool; includes explicitly attributed previous model output; not global records',
          'codes':items,'fields':{str(r):field_polynomial(r) for r in sorted({i['rank'] for i in items})}}
    content=json.dumps(data,indent=2)+'\n'
    if POOL.exists() and POOL.read_text()!=content:raise RuntimeError('refusing to replace a different pool')
    POOL.write_text(content)
    print([(i['n'],i['m'],i['rank']) for i in items],flush=True)


def reference_certificate(p):
    data=json.loads(POOL.read_text());n,m=p['n'],p['m'];best,bestsize=None,0
    for c in data['codes']:
        if c['n']<=n and c['m']>=m and c['size']>bestsize:
            best={'linear_code':[w+'0'*(n-c['n']) for w in c['rows']]};bestsize=c['size']
        for N in range(1,min(c['size'],n//c['n'])+1):
            K=min(N,(N+3-math.ceil(m/c['m']))//3)
            if K<1:continue
            size=c['size']**K
            if size>bestsize:
                best={'rs_concat':{'inner':{'linear_code':c['rows']},'inner_n':c['n'],'inner_m':c['m'],
                                   'field':data['fields'][str(c['rank'])],'length':N,'dimension':K}}
                bestsize=size
    if best is None:raise ValueError('no admitted reference')
    return best


def set_tier(tier):
    import run_ladder as L
    L.SIZE_TIER=tier;L.A_RANGES=L.TIERS[tier]
    return L


def prepare():
    from agent_bridge import NO_TOOLS
    from openceiling import verify_with_timeout
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/'manifest.json').exists():validate();return
    cases=[]
    for tier in TIERS:
        L=set_tier(tier);F,p=L.instance_a('trifference',0)
        ref=L.reference('trifference',0,10);ans=ref['search_answer']
        assert verify_with_timeout(F,p,ans)[:2]==trifference_second(p,ans)==(True,ref['search'])
        assert ref['search']>=ref['naive']>0 and ref['bound']/ref['search']>=1.4
        path=f'bench/refs/{tier}-trifference-0-t10.json'
        prompt=L.prompt_for('trifference',F,p,'p1',None)+NO_TOOLS
        cases.append({'tier':tier,'family':'trifference','seed':0,'params':p,'naive':ref['naive'],'reference':ref['search'],
                      'bound':ref['bound'],'reference_path':path,'reference_sha256':digest(ROOT/path),
                      'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest()})
        print(tier,p,'reference',ref['search'],flush=True)
    data={'created_utc':datetime.now(timezone.utc).isoformat(),'model':'gpt-6-astra','effort':'medium',
          'protocol':'p1; tools disabled; certified representation; single attempt on four fresh lengths',
          'wall_timeout_s':7200,'scoring_output_budget':128000,'workers':2,'cases':cases,
          'code_sha256':{f:digest(ROOT/f) for f in CODE_FILES}}
    (OUT/'manifest.json').write_text(json.dumps(data,indent=2)+'\n')


def validate():
    from agent_bridge import NO_TOOLS
    data=json.loads((OUT/'manifest.json').read_text())
    for path,sha in data['code_sha256'].items():
        if digest(ROOT/path)!=sha:raise ValueError('source changed after freeze: '+path)
    for c in data['cases']:
        L=set_tier(c['tier']);F,p=L.instance_a(c['family'],c['seed'])
        prompt=L.prompt_for(c['family'],F,p,'p1',None)+NO_TOOLS
        if p!=c['params'] or hashlib.sha256(prompt.encode()).hexdigest()!=c['prompt_sha256']:raise ValueError('prompt changed')
        if digest(ROOT/c['reference_path'])!=c['reference_sha256']:raise ValueError('reference changed')
    return data


def report():
    from openceiling import verify_with_timeout,expand_answer
    data=validate();cases=[]
    for c in data['cases']:
        tier=c['tier'];L=set_tier(tier);F,p=L.instance_a('trifference',0)
        path=ROOT/f'bench/results/gpt-6-astra-codex-medium@nocap#{tier}.jsonl'
        rows=[r for r in map(json.loads,path.read_text().splitlines()) if r['family']=='trifference' and r['seed']==0]
        if len(rows)!=1:raise ValueError('missing or duplicate attempts')
        r=rows[0];assert r['params']==p
        rawpath=ROOT/f'bench/results/headless/gpt-6-astra/{tier}-codex-medium@nocap-trifference-0.json'
        raw=json.loads(rawpath.read_text());assert raw['result']==r['content'] or r['finish_reason']=='timeout'
        assert not raw['tool_attempts']
        a=L.extract_json(r['content']);first=verify_with_timeout(F,p,a)[:2]
        second=trifference_second(p,expand_answer(F,p,a)) if a is not None else (False,0)
        assert first==second==(r['feasible'],r['objective'])
        valid=r['feasible'] and r['finish_reason']!='length' and (r.get('reasoning_tokens') or 0)<=128000
        value=r['objective'] if valid else 0
        shape=next(iter(a)) if isinstance(a,dict) else 'literal'
        cases.append({**c,'valid':valid,'objective':value,'ratio':value/c['reference'],'format':shape,
                      'generator_rank_limit_reached':bool(shape=='linear_code' and value==3**12),
                      'latency_s':r['latency_s'],'tokens':r['reasoning_tokens'],'verify_msg':r['verify_msg'],
                      'raw_sha256':digest(rawpath)})
    (OUT/'summary.json').write_text(json.dumps({'completed_utc':datetime.now(timezone.utc).isoformat(),'cases':cases},indent=2)+'\n')
    lines=['# Trifference：证书表示的规模阶梯','','| tier | n | 参照 | 模型 | 比值 | 有效 | 表示 |','|---|---:|---:|---:|---:|---|---|']
    for c in cases:lines.append(f"| {c['tier']} | {c['params']['n']} | {c['reference']} | {c['objective']} | {c['ratio']:.3f} | {c['valid']} | {c['format']} |")
    lines+=['','旧 A3 的答案和分数保持不变；本表使用四个新长度和预先冻结的新协议。','']
    (OUT/'summary.md').write_text('\n'.join(lines));print('\n'.join(lines))

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['build-pool','prepare','validate','report']);a=ap.parse_args()
    {'build-pool':build_pool,'prepare':prepare,'validate':validate,'report':report}[a.action]()
