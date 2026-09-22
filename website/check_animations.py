"""Check every illustrated family against the benchmark's mathematical verifier."""
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bench'))
from openceiling import FAMILIES
import candidate_families
from family_catalog import CORE_GROUPS
source="""
const m=require('./website/dist/animations.js');
process.stdout.write(JSON.stringify({families:m.data,frames:Array.from({length:120},(_,i)=>{
 const points=m.trianglePoints(4+i*23/119);return {points,...m.minimumTriangle(points)};
}),distances:Array.from({length:10},(_,i)=>m.distances(m.data.find(f=>f.id==='degdiam').answer,i))}));
"""
data=json.loads(subprocess.check_output(['node','-e',source],cwd=ROOT,text=True))
assert len(data['families'])==14
assert {f['id'] for f in data['families']}==set(CORE_GROUPS)
for f in data['families']:
    valid,value,message=FAMILIES[f['task']].verify(f['params'],f['answer'])
    assert valid,(f['id'],message)
    assert math.isclose(value,f['objective'],rel_tol=1e-12),(f['id'],value)
for frame in data['frames']:
    valid,area,_=FAMILIES['heilbronn'].verify({'n':7},frame['points'])
    assert valid and math.isclose(area,frame['area'],rel_tol=1e-12)
    assert len(frame['areas'])==35
assert all(max(d)==2 for d in data['distances'])
fixtures={f['id']:f for f in data['families']}
for col,triple in enumerate(fixtures['trifference']['triples']):
    assert {fixtures['trifference']['answer'][i][col] for i in triple}==set('012')
f=fixtures['matmul'];A,B=f['A'],f['B']
assert f['C']==[sum(A[r*2+k]*B[k*2+c] for k in range(2)) for r in range(2) for c in range(2)]
f=fixtures['covering'];pairs={tuple(sorted(p)) for block in f['answer'] for p in itertools.combinations(block,2)}
assert len(pairs)==21
print(json.dumps({'families':14,'all_witnesses_verified':True,'geometry_frames':120,'graph_diameter':2,'code_separation_and_matrix_identity':'passed'}))
