"""Public CLI checks: coverage, prompt fidelity, validity and aggregation."""
import json
from pathlib import Path
import tempfile
import unittest
import exam


class PublicExamTests(unittest.TestCase):
    def test_frozen_suite_and_code_scales(self):
        calls = exam.suite()
        self.assertEqual(len(calls), 69)
        self.assertEqual(len({c['instance_id'] for c in calls}), 69)
        self.assertEqual(len({c['instance_id'] for c in calls if c['reference_type'] == 'published'}), 30)
        self.assertEqual([c['params']['n'] for c in calls if c['family'] == 'trifference'], [64, 96, 144, 192])
        self.assertTrue(all(c['params']['representation'] == 'certified' for c in calls if c['family'] == 'trifference'))

    def test_valid_and_invalid_caps(self):
        self.assertEqual(exam.verify('capset', {'d': 2}, ['00', '01', '10', '11'])['objective'], 4)
        self.assertFalse(exam.verify('capset', {'d': 2}, ['00', '01', '02'])['valid'])
        self.assertFalse(exam.verify('capset', {'d': 2}, ['00', '00'])['valid'])

    def test_budget_failures_and_uncapped_ratio(self):
        case = {'call_id': 'test', 'instance_id': 'cap2', 'family': 'capset', 'params': {'d': 2},
                'reference': 2, 'reference_type': 'construction', 'sense': 'max'}
        record = {'answer': ['00', '01', '10', '11']}
        self.assertEqual(exam.score_record(case, record)['ratio'], 2)
        self.assertEqual(exam.score_record(case, {**record, 'finish_reason': 'length'})['ratio'], 0)
        self.assertEqual(exam.score_record(case, {**record, 'output_tokens': 128001})['ratio'], 0)

    def test_duplicate_instances_are_rejected(self):
        rows = [{'instance_id': key, 'family': 'capset', 'reference_type': 'published', 'ratio': ratio, 'valid': True}
                for key, ratio in [('a', 0), ('a', 2), ('b', 3)]]
        with self.assertRaisesRegex(ValueError,'Duplicate instance'):
            exam.aggregate(rows, False)
        result = exam.aggregate([rows[0],rows[-1]],False)
        self.assertEqual(result['subset_score'], 150)
        self.assertNotIn('score', result)

    def test_duplicate_and_partial_submissions(self):
        row = {'call_id': exam.suite()[0]['call_id'], 'finish_reason': 'timeout'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'answers.jsonl'
            path.write_text(json.dumps(row) + '\n')
            with self.assertRaisesRegex(ValueError, 'Missing'):
                exam.score_submission(path)
            self.assertFalse(exam.score_submission(path, True)['complete'])
            path.write_text((json.dumps(row) + '\n') * 2)
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                exam.score_submission(path, True)

    def test_network_failure_is_missing_in_public_scores(self):
        cases=exam.suite();record={'call_id':cases[0]['call_id'],'finish_reason':'transport_error'}
        with self.assertRaisesRegex(ValueError,'Unscored infrastructure failure'):
            exam.score_record(cases[0],record)
        rows=[{'call_id':c['call_id'],'finish_reason':'length','output_tokens':128000} for c in cases]
        rows[0]=record
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'answers.jsonl'
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'Missing 1 of 69'):
                exam.score_submission(path)
            partial=exam.score_submission(path,True)
            self.assertNotIn('score',partial);self.assertEqual(partial['calls'],68)
            self.assertEqual(partial['missing_call_ids'],[record['call_id']])
            self.assertIsNone(partial['infrastructure_failures'][0]['ratio'])
            self.assertEqual(partial['subset_score'],0)

    def test_tool_scoring_uses_saved_answer_not_tool_free_token_cap(self):
        case = {'call_id': 'test', 'instance_id': 'cap2', 'family': 'capset', 'params': {'d': 2},
                'reference': 2, 'reference_type': 'construction', 'sense': 'max'}
        row = {'answer': ['00', '01', '10', '11'], 'output_tokens': 200000,
               'finish_reason': 'timeout', 'submission_within_deadline': True}
        self.assertEqual(exam.score_record(case, row, 'tool-assisted')['ratio'], 2)
        self.assertEqual(exam.score_record(case, row)['ratio'], 0)
        row['submission_within_deadline'] = False
        self.assertEqual(exam.score_record(case, row, 'tool-assisted')['ratio'], 0)
        row.pop('submission_within_deadline')
        with self.assertRaisesRegex(ValueError, 'submission_within_deadline'):
            exam.score_record(case, row, 'tool-assisted')
        row.update(finish_reason='transport_error', submission_within_deadline=True)
        with self.assertRaisesRegex(ValueError, 'Unscored infrastructure'):
            exam.score_record(case, row, 'tool-assisted')


if __name__ == '__main__':
    unittest.main()
