"""A failed new attempt must replace an old success in every publication view."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import formal_cohort as C
import result_selection as S


class SelectionTests(unittest.TestCase):
    def test_failure_replaces_success_in_formal_and_ladder_views(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'bench/data').mkdir(parents=True)
            (root/'bench/results').mkdir()
            old = {'model': 'model', 'config': 'old#A3', 'family': 'kissing', 'tier': 'A3',
                   'seed': 6, 'params': {'d': 13}, 'feasible': True, 'objective': 1000}
            new = {**old, 'config': 'new#A3', 'params': {'d': 13, 'representation': 'quadratic'},
                   'feasible': False, 'objective': 0, 'finish_reason': 'length'}
            for name, row in [('old', old), ('new', new)]:
                (root/f'bench/results/model-{name}#A3.jsonl').write_text(json.dumps(row)+'\n')
            reference = {'params': new['params'], 'naive': 312, 'search': 568, 'bound': 2064}
            (root/'bench/data/ref.json').write_text(json.dumps(reference))
            entry = {'model': 'model', 'source_config': 'old#A3', 'config': 'new#A3',
                     'tier': 'A3', 'family': 'kissing', 'seed': 6, 'case_id': 'fixture',
                     'result_path': 'bench/results/model-new#A3.jsonl'}
            (root/S.MANIFEST).write_text(json.dumps({'replacements': [entry], 'references': [
                {'tier': 'A3', 'family': 'kissing', 'seed': 6, 'reference_path': 'bench/data/ref.json'}]}))
            system = ('fixture', 'model', 'Label', 'old', 'old', False)
            case = {'block': 'core12', **{k: new[k] for k in ['tier', 'family', 'seed', 'params']}}
            with patch.object(C, 'ROOT', root):
                self.assertEqual(C.get_row(system, case), new)
            self.assertEqual(S.parameters_for('A3', 'kissing', 6, old['params'], root), new['params'])
            self.assertEqual(S.parameters_for('A3', 'kissing', 0, {'d': 14}, root), {'d': 14})
            refs = {('kissing', 6): {'params': old['params']}}
            rows = {('model', 'old#A3'): {('kissing', 6): old}, ('model', 'new#A3'): {('kissing', 6): new}}
            S.overlay('A3', refs, rows, root)
            self.assertEqual(rows['model', 'old#A3']['kissing', 6], new)
            self.assertEqual(refs['kissing', 6]['params'], new['params'])
            self.assertEqual(json.loads((root/'bench/results/model-old#A3.jsonl').read_text()), old)
            with self.assertRaises(ValueError):
                S.overlay('A3', refs, {('model', 'old#A3'): {('kissing', 6): old}}, root)

    def test_network_failure_is_missing_without_rewriting_legacy_row(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'bench/results').mkdir(parents=True)
            row={'model':'model','config':'old#A3','family':'capset','tier':'A3','seed':0,
                 'params':{'d':2},'feasible':False,'objective':0,'finish_reason':'transport_error'}
            path=root/'bench/results/model-old#A3.jsonl';path.write_text(json.dumps(row)+'\n')
            system=('fixture','model','Label','old','old',False)
            case={'block':'core12',**{k:row[k] for k in ['tier','family','seed','params']}}
            with patch.object(C,'ROOT',root):
                self.assertIsNone(C.get_row(system,case))
                view=C.get_row(system,case,include_unscored=True)
                self.assertFalse(view['scored']);self.assertIsNone(view['objective'])
            self.assertEqual(json.loads(path.read_text()),row)


if __name__ == '__main__':
    unittest.main()
