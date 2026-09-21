"""Check appendix presentation against original instances and recorded answers."""
from collections import Counter
import json
from pathlib import Path
import re
import sys
import unittest
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent)]
import publication_data as P
from run_ladder import extract_json
from report import load
from openceiling import FAMILIES
from candidate_families import shannon_second

class AppendixChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((HERE/'tables/appendix_catalogue_data.json').read_text())

    def test_formal_parameters_have_one_response_per_instance(self):
        expected=Counter((c['family'],json.dumps(c['params'],sort_keys=True)) for c in P.C.cases())
        shown={(c['task'],json.dumps(c['params'],sort_keys=True)):c['calls'] for c in self.data['parameters']['formal']}
        self.assertEqual(expected,shown)
        self.assertEqual(len(shown),69);self.assertTrue(all(n==1 for n in shown.values()))
        self.assertEqual(len(self.data['illustrations']),14)

    def test_all_64_reference_values_match_the_previous_definition_export(self):
        original=(HERE/'tables/families_def.tex').read_text()
        pattern=r'Baseline: (.*?) \([^)]*\); 10 s search: (.*?)\. Scoring reference: (.*?) \([^)]*\)\. Bound or target: (.*?) \([^)]*\)\.'
        old=list(re.findall(pattern,original))
        def number(text):
            m=re.fullmatch(r'\$(.*?)\\times10\^\{(-?\d+)\}\$',text)
            return float(m[1])*10**int(m[2]) if m else float(text)
        expected=Counter(tuple(number(v) for v in row) for row in old)
        def rounded(v):return float(f'{v:.6g}')
        actual=Counter(tuple(rounded(r[k]) for k in ['baseline','search','reference','anchor']) for r in self.data['catalogue_examples'])
        self.assertEqual(len(old),16);self.assertEqual(expected,actual)

    def test_worked_model_examples_match_the_original_answers(self):
        _,rows=load('L4');s=P.REGISTRY['astra_high'];r=rows[s[1],s[3]+'#L4']['capset',0]
        ans=extract_json(r['content'])
        for factor in ans['product']:
            ok,size,*_=FAMILIES['capset'].verify({'d':6},factor)
            self.assertTrue(ok);self.assertEqual(size,112)
        self.assertEqual(self.data['cases']['capset']['objective'],r['objective'])
        cs=P.C.cases()
        c=next(c for c in cs if (c['family'],c['tier'],c['seed'])==('shannon','A3',0))
        r=P.C.get_row(P.REGISTRY['qwen38'],c);ok,size=shannon_second(c['params'],extract_json(r['content']))
        self.assertTrue(ok);self.assertEqual(size,self.data['cases']['shannon']['objective'])
        c=next(c for c in cs if (c['family'],c['tier'],c['seed'])==('trifference','T1',0))
        r=P.C.get_row(P.REGISTRY['astra_high'],c);matrix=extract_json(r['content'])['linear_code']
        self.assertEqual([list(map(int,s)) for s in matrix],self.data['cases']['trifference']['generator'])
        self.assertEqual(r['objective'],59049);self.assertTrue(r['feasible'])

    def test_ladder_table_retains_every_numeric_cell(self):
        old=(HERE/'tables/ladder_table.tex').read_text().splitlines()
        cells=[[x.strip() for x in r.removesuffix(r'\\').split('&')] for r in old if ' & ' in r and not r.startswith('family')]
        self.assertEqual(cells,self.data['ladder_rows']);self.assertEqual(len(cells),28)

    def test_all_original_experimental_views_remain_in_the_manuscript(self):
        text=(HERE/'main.tex').read_text()+'\n'+'\n'.join(p.read_text() for p in (HERE/'appendix').glob('*.tex'))
        expected={'fig0_framework','fig1_scale','fig2_headline','fig3_tiers','fig4_effort',
                  'fig5_search','fig6_ladder_main','fig7_model_size','fig8_code_scale',
                  'appendix/ladder_designs','appendix/ladder_quartic'}
        present=set(re.findall(r'\\includegraphics(?:\[[^]]*\])?\{figs/([^}]+)\.pdf\}',text))
        self.assertTrue(expected<=present,expected-present)

if __name__=='__main__':unittest.main()
