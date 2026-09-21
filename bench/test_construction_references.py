"""Construction calibration: witnesses, frozen isolation and unmodified evidence."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import openceiling as O
import freeze_frontier as F
from crosscheck import SECOND

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'bench/reference_calibration/2026-09-16'


class ConstructionReferenceTests(unittest.TestCase):
    def tearDown(self):F.load('v1-trifference')

    def test_retrieved_covering_frontiers_pass_both_verifiers(self):
        from run_ladder import extract_json
        for v,k,t,expected in [(18,7,4,126),(24,6,3,116),(30,6,3,225)]:
            path=ROOT/f'bench/frontier_audits/2026-09-17-covering/covering_{v}_{k}_{t}.json'
            data=json.loads(path.read_text());p={'v':v,'k':k,'t':t}
            self.assertEqual(data['params'],p)
            answer=extract_json(json.dumps({'answer':data['answer']}))
            self.assertEqual(O.verify_with_timeout(O.FAMILIES['covering'],p,answer)[:2],(True,expected))
            self.assertEqual(SECOND['covering'](p,answer),(True,expected))
            F.load('v1-trifference')
            self.assertEqual(O.frontier_ratio(O.FAMILIES['covering'],p,expected,expected,True,expected),(1,'literature'))

    def test_all_calibration_and_formal_objects_have_two_verdicts(self):
        keys=[]
        for phase,expected in [('calibration',17),('formal',20)]:
            data=json.loads((AUDIT/f'{phase}.json').read_text());self.assertEqual(len(data['records']),expected)
            keys.append({F.key(r['family'],r['params']) for r in data['records']})
            for r in data['records']:
                path=ROOT/r['witness'];self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),r['witness_sha256'])
                answer=json.loads(path.read_text())['answer'];family=O.FAMILIES[r['family']]
                self.assertEqual(family.verify(r['params'],answer)[:2],(True,r['objective']))
                self.assertEqual(SECOND[r['family']](r['params'],answer),(True,r['objective']))
        self.assertFalse(keys[0]&keys[1])

    def test_frozen_switch_clears_construction_and_zero_cache(self):
        family=O.FAMILIES['corners'];p={'n':138};k=F.key('corners',p)
        F.load('v1-trifference');self.assertEqual(O.textbook_zero(family,p),(3120,'C'))
        with tempfile.TemporaryDirectory() as directory:
            data={'version':'legacy','entries':{k:{'known_best':None,'anchor':138**2,'anchor_kind':'trivial'}}}
            (Path(directory)/'legacy.json').write_text(json.dumps(data))
            with patch.object(F,'DIR',directory):F.load('legacy')
            self.assertIsNone(O.textbook_zero(family,p))
            self.assertEqual(O.effective_frontier(family,p,2184,2504),(2504,False))
        F.load('v1-trifference')
        self.assertEqual(O.effective_frontier(family,p,2184,2504),(3120,False))
        self.assertEqual(O.frontier_ratio(family,p,2184,3120,True,2504),(1,'textbook'))
        self.assertEqual(O.closed_gap(family,p,2184,3120,True,2504)[0],0)

    def test_applied_scope_sources_and_parent_hashes(self):
        receipt=json.loads((AUDIT/'applied.json').read_text());self.assertEqual(receipt['instances_improved'],8)
        library=json.loads((ROOT/'bench/construction_references.json').read_text())
        self.assertEqual(len(library['entries']),8)
        release_path=ROOT/'RELEASE_MANIFEST.json'
        released=({r['path']:r for r in json.loads(release_path.read_text())['transformed_result_files']}
                  if release_path.exists() else {})
        for path,sha in receipt['unchanged_collection_sha256'].items():
            if path in released:
                self.assertEqual(released[path]['original_sha256'],sha,path)
                sha=released[path]['released_sha256']
            self.assertEqual(hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),sha,path)
        for path in (ROOT/'bench/frontiers').glob('*.json'):
            data=json.loads(path.read_text())
            if data.get('derived_from'):
                parent=ROOT/f"bench/frontiers/{data['derived_from']}.json"
                self.assertEqual(data['source_sha256'],hashlib.sha256(parent.read_bytes()).hexdigest())
            for k,r in library['entries'].items():
                if k in data['entries']:
                    self.assertIsNone(data['entries'][k]['known_best'])
                    self.assertEqual(data['entries'][k]['construction_reference'],r)

    def test_search_budget_comparison_keeps_same_offline_floor(self):
        import sys
        sys.path.insert(0,str(ROOT/'bench/paper'))
        from search_evidence import scoring_zero
        F.load('v1-trifference')
        before={'params':{'d':12,'cos100':36},'naive':24,'search':88}
        after={**before,'search':110}
        self.assertEqual(scoring_zero('kissing_theta',before),152)
        self.assertEqual(scoring_zero('kissing_theta',after),152)
        self.assertEqual(before['search'],88)
        self.assertEqual(after['search'],110)


if __name__=='__main__':unittest.main()
