"""Exact certificates against exhaustive small codes, malformed proofs and legacy protocol hashes."""
import hashlib,json,random,unittest
from itertools import product
from pathlib import Path
from candidate_families import Trifference,trifference_second
from openceiling import verify_with_timeout
from trifference_certificates import irreducible,second_irreducible,linear_verify,second_linear


def span(rows):
    n=len(rows[0]);out={(0,)*n}
    for row in rows:
        out={tuple((x+t*int(y))%3 for x,y in zip(w,row)) for w in out for t in range(3)}
    return [''.join(map(str,w)) for w in sorted(out)]


def brute(words,m):
    from itertools import combinations
    return all(sum(len({a,b,c})==3 for a,b,c in zip(*triple))>=m for triple in combinations(words,3))

class CertificateTests(unittest.TestCase):
    def test_hyperplanes_match_exhaustive_triples(self):
        rng=random.Random(721)
        for k in range(1,5):
            for _ in range(35):
                n=rng.randint(k,15);rows=[''.join(rng.choice('012') for _ in range(n)) for _ in range(k)]
                words=span(rows)
                for m in (1,2,3):
                    if m>n:continue
                    p={'n':n,'m':m,'representation':'certified'};a={'linear_code':rows}
                    expected=(True,len(words)) if brute(words,m) else (False,0)
                    self.assertEqual(linear_verify(p,a)[:2],expected,(p,rows))
                    self.assertEqual(second_linear(p,a),expected,(p,rows))
        for m in (1,2,3):
            p={'n':3,'m':m,'representation':'certified'}
            self.assertEqual(linear_verify(p,{'linear_code':['000','000']})[:2],(True,1))

    def test_valid_projective_codes_and_puncturings(self):
        from candidate_families import _projective_code
        from trifference_scaling import rows_of_words
        _,words=_projective_code(3)
        rows=rows_of_words([''.join(map(str,w)) for w in words])
        for repeats in (1,2,3):
            for deleted in (0,1,2,3,4):
                selected=[(w*repeats)[deleted:] for w in rows];code=span(selected)
                for m in (1,2,3):
                    p={'n':len(selected[0]),'m':m,'representation':'certified'}
                    expected=(True,len(code)) if brute(code,m) else (False,0)
                    self.assertEqual(linear_verify(p,{'linear_code':selected})[:2],expected)
                    self.assertEqual(second_linear(p,{'linear_code':selected}),expected)

    def test_field_checks_agree_exhaustively(self):
        for d in range(1,6):
            for c in product(range(3),repeat=d):
                f=[*c,1];self.assertEqual(irreducible(f),second_irreducible(f),f)
        self.assertTrue(irreducible([1,2,0,1]))
        self.assertFalse(irreducible([1,0,1,0,1]))

    def test_reed_solomon_certificate_and_exact_small_expansion(self):
        F=Trifference();p={'n':16,'m':1,'representation':'certified'}
        inner={'linear_code':['1011','0112']}
        a={'rs_concat':{'inner':inner,'inner_n':4,'inner_m':1,'field':[1,0,1],'length':4,'dimension':2}}
        self.assertEqual(verify_with_timeout(F,p,a)[:2],(True,81))
        self.assertEqual(trifference_second(p,a),(True,81))
        # Independent GF9 multiplication: t^2=-1, with lexicographically sorted inner words.
        code=span(inner['linear_code'])
        def mul(a,b):
            x,y=a%3,a//3;u,v=b%3,b//3
            return (x*u-y*v)%3+3*((x*v+y*u)%3)
        def add(a,b):return (a%3+b%3)%3+3*((a//3+b//3)%3)
        words=[ ''.join(code[add(c,mul(s,x))] for x in range(4)) for c in range(9) for s in range(9)]
        self.assertEqual(len(set(words)),81);self.assertTrue(brute(words,1))
        self.assertFalse(brute(words,2))
        self.assertFalse(verify_with_timeout(F,dict(p,m=2),a)[0])

    def test_nonlinear_literal_inner_code(self):
        from candidate_families import _is_linear
        inner=[w+str(int(w[0])*int(w[1])%3) for w in span(['1011','0112'])]
        self.assertFalse(_is_linear(inner));self.assertTrue(brute(inner,1))
        p={'n':20,'m':1,'representation':'certified'}
        a={'rs_concat':{'inner':inner,'inner_n':5,'inner_m':1,'field':[1,0,1],'length':4,'dimension':2}}
        self.assertEqual(verify_with_timeout(Trifference(),p,a)[:2],(True,81))
        self.assertEqual(trifference_second(p,a),(True,81))

    def test_multiplicity_and_padding(self):
        F=Trifference();inner={'linear_code':['10111011','01120112']}
        a={'rs_concat':{'inner':inner,'inner_n':8,'inner_m':2,'field':[1,0,1],'length':4,'dimension':2}}
        p={'n':37,'m':2,'representation':'certified'}
        self.assertEqual(verify_with_timeout(F,p,a)[:2],(True,81));self.assertEqual(trifference_second(p,a),(True,81))
        self.assertFalse(verify_with_timeout(F,dict(p,m=3),a)[0])

    def test_certificate_rejections_and_actual_rank(self):
        F=Trifference();p={'n':16,'m':1,'representation':'certified'}
        base={'inner':{'linear_code':['1011','0112']},'inner_n':4,'inner_m':1,'field':[1,0,1],'length':4,'dimension':2}
        bad=[{}, {'linear_code':[]},{'linear_code':['0'*15]}, {'linear_code':[False]},
             {'linear_code':['0121','1011'],'count':99}]
        for change in [{'field':[2,0,1]}, {'field':[True,0,1]}, {'length':10}, {'dimension':3},
                       {'dimension':True},{'inner_n':5},{'inner_m':2},{'count':99},
                       {'inner':{'rs_concat':base}},{'inner':{'linear_code':['0000','0000']}}]:
            bad.append({'rs_concat':dict(base,**change)})
        for a in bad:
            self.assertEqual(verify_with_timeout(F,p,a)[:2],(False,0),a)
            self.assertEqual(trifference_second(p,a),(False,0),a)
        a={'linear_code':['1111','2222','0000','1111']};p={'n':4,'m':3,'representation':'certified'}
        self.assertEqual(verify_with_timeout(F,p,a)[:2],(True,3));self.assertEqual(trifference_second(p,a),(True,3))
        self.assertFalse(verify_with_timeout(F,{'n':4,'m':1},a)[0])

    def test_original_a3_prompts_are_unchanged(self):
        import run_ladder as L
        from agent_bridge import NO_TOOLS
        L.SIZE_TIER='A3';L.A_RANGES=L.TIERS['A3']
        root=Path(__file__).parent
        data=json.loads((root/'results/pilots/astra-medium-codes-A3/manifest.json').read_text())
        for c in data['cases']:
            f,p=L.instance_a(c['family'],c['seed'])
            self.assertEqual(p,c['params'])
            self.assertEqual(hashlib.sha256((L.prompt_for(c['family'],f,p,'p1',None)+NO_TOOLS).encode()).hexdigest(),c['prompt_sha256'])
            self.assertEqual(hashlib.sha256((root.parent/c['reference']).read_bytes()).hexdigest(),c['reference_sha256'])

if __name__=='__main__':unittest.main()
