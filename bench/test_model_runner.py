"""Offline HTTP/command integration tests. Never contact a model service."""
import argparse
from contextlib import contextmanager
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import exam
import model_adapters as A
import model_runner as R


@contextmanager
def server(responses):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            seen.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length']))),
                         self.headers.get('Authorization')))
            status, data = responses[min(len(seen) - 1, len(responses) - 1)]
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{httpd.server_port}/v1', seen
    finally:
        httpd.shutdown()
        thread.join()
        httpd.server_close()


def chat(content, finish='stop'):
    return {'model': 'test-model-snapshot', 'choices': [{'message': {'content': content}, 'finish_reason': finish}],
            'usage': {'prompt_tokens': 20, 'completion_tokens': 100,
                      'completion_tokens_details': {'reasoning_tokens': 70}}}


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = exam.suite()
        cls.cap = next(c for c in cls.cases if c['call_id'] == 'a3-capset-0')
        cls.answer = {'product': [['00', '01', '10', '11']] * 5}

    def args(self, directory, *extra):
        p = argparse.ArgumentParser()
        R.add_parser(p.add_subparsers())
        return p.parse_args(['run', '--model', 'test-model', '--output', str(directory),
                             '--api-key-env', '', '--only', self.cap['call_id'], *extra])

    def run_quietly(self, args):
        with patch('sys.stdout', new_callable=io.StringIO):
            return R.run(args)

    def test_http_prompt_privacy_score_and_resume(self):
        with tempfile.TemporaryDirectory() as d, server([(200, chat(json.dumps(self.answer)))]) as (url, seen):
            args = self.args(d, '--base-url', url, '--api-key-env', 'EE_TEST_KEY')
            with patch.dict(os.environ, {'EE_TEST_KEY': 'test-secret-do-not-log'}):
                result = self.run_quietly(args)
                args.resume = True
                self.run_quietly(args)
            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0][1]['messages'], A.messages(self.cap))
            self.assertEqual(seen[0][1]['max_completion_tokens'], 128000)
            self.assertNotIn('tools', seen[0][1])
            self.assertFalse(result['complete_suite'])
            scored = json.loads((Path(d) / 'scores.json').read_text())
            self.assertEqual(scored['calls_scored'][0]['objective'], 1024)
            usage = json.loads((Path(d) / 'usage.json').read_text())
            self.assertEqual(usage['output_tokens']['reported_total'], 100)  # not 170
            for path in Path(d).rglob('*'):
                if path.is_file():
                    self.assertNotIn(b'test-secret-do-not-log', path.read_bytes())

    def test_invalid_and_budget_outcomes_never_repeat(self):
        for content, finish in [('Network error; please retry', 'stop'), (json.dumps(self.answer), 'length')]:
            with self.subTest(finish=finish), tempfile.TemporaryDirectory() as d, server([(200, chat(content, finish))]) as (url, seen):
                args = self.args(d, '--base-url', url)
                self.run_quietly(args)
                args.resume = args.retry_infrastructure = True
                self.run_quietly(args)
                self.assertEqual(len(seen), 1)
                self.assertEqual(json.loads((Path(d) / 'scores.json').read_text())['subset_score'], 0)

    def test_retry_preserves_unknown_usage_and_all_attempts(self):
        with tempfile.TemporaryDirectory() as d, server([(503, {'error': {'code': 'overloaded'}}),
                                                         (200, chat(json.dumps(self.answer)))]) as (url, seen):
            with patch.object(R.time, 'sleep'):
                self.run_quietly(self.args(d, '--base-url', url, '--retries', '1'))
            self.assertEqual(len(seen), 2)
            self.assertEqual(len(list(Path(d).glob('attempts/*/*/outcome.json'))), 2)
            usage = json.loads((Path(d) / 'usage.json').read_text())
            self.assertEqual(usage['unknown_usage_attempts'], 1)
            self.assertFalse(usage['output_tokens']['complete'])
            self.assertEqual(usage['output_tokens']['reported_total'], 100)

    def test_exhausted_infrastructure_stays_missing_then_explicit_recovery(self):
        with tempfile.TemporaryDirectory() as d, server([(503, {}), (200, chat(json.dumps(self.answer)))]) as (url, seen):
            args = self.args(d, '--base-url', url, '--retries', '0')
            with self.assertRaisesRegex(ValueError, 'paused'):
                self.run_quietly(args)
            report = json.loads((Path(d) / 'scores.json').read_text())
            self.assertEqual(report['calls'], 0)
            self.assertIsNone(report['subset_score'])
            args.resume = True
            with self.assertRaisesRegex(ValueError, 'Infrastructure failures'):
                self.run_quietly(args)
            self.assertEqual(len(seen), 1)
            args.retry_infrastructure = True
            self.run_quietly(args)
            self.assertEqual(len(seen), 2)

    def test_dry_run_and_orphan_prevent_model_calls(self):
        with tempfile.TemporaryDirectory() as d, server([(200, chat('null'))]) as (url, seen):
            args = self.args(d, '--base-url', url, '--dry-run')
            self.run_quietly(args)
            self.assertEqual(seen, [])
            orphan = Path(d) / 'attempts' / self.cap['call_id'] / '0001'
            orphan.mkdir(parents=True)
            (orphan / 'started.json').write_text('{}')
            args.resume, args.dry_run = True, False
            with self.assertRaisesRegex(ValueError, 'Incomplete attempt'):
                self.run_quietly(args)
            self.assertEqual(seen, [])

    def test_changed_settings_and_lock_block_duplicate_controller(self):
        with tempfile.TemporaryDirectory() as d:
            args = self.args(d, '--dry-run')
            self.run_quietly(args)
            args.resume, args.model = True, 'different-model'
            with self.assertRaisesRegex(ValueError, 'differ'):
                self.run_quietly(args)
            with R.run_lock(Path(d)), self.assertRaisesRegex(ValueError, 'Another controller'):
                self.run_quietly(args)

    def test_responses_native_stop_and_tool_detection(self):
        data = {'status': 'completed', 'model': 'model-snapshot',
                'output': [{'type': 'reasoning'}, {'type': 'message', 'content': [
                    {'type': 'output_text', 'text': json.dumps(self.answer)}]}],
                'usage': {'input_tokens': 4, 'output_tokens': 12, 'output_tokens_details': {'reasoning_tokens': 8}}}
        self.assertEqual(A.parse_api(data, 'responses')['answer'], self.answer)
        data.update(status='incomplete', incomplete_details={'reason': 'max_output_tokens'})
        self.assertEqual(A.parse_api(data, 'responses')['finish_reason'], 'length')
        data.update(status='completed', output=[{'type': 'web_search_call'}])
        self.assertEqual(A.parse_api(data, 'responses')['finish_reason'], 'tool_violation')

    def test_responses_http_shape(self):
        response = {'status': 'completed', 'output': [], 'usage': {'input_tokens': 3, 'output_tokens': 8}}
        with tempfile.TemporaryDirectory() as d, server([(200, response)]) as (url, seen):
            self.run_quietly(self.args(d, '--base-url', url, '--adapter', 'responses', '--effort', 'high'))
            self.assertEqual(seen[0][0], '/v1/responses')
            self.assertEqual(seen[0][1]['input'], A.messages(self.cap))
            self.assertEqual(seen[0][1]['reasoning'], {'effort': 'high'})
            self.assertEqual(seen[0][1]['max_output_tokens'], 128000)

    def test_custom_command_and_bad_protocol_no_regeneration(self):
        with tempfile.TemporaryDirectory() as d:
            command = Path(d) / 'command.json'
            example = Path(__file__).resolve().parents[1] / 'examples/mock_harness.py'
            command.write_text(json.dumps([sys.executable, str(example), '{request}', '{response}']))
            args = self.args(Path(d) / 'run', '--adapter', 'command', '--command-file', str(command))
            result = self.run_quietly(args)
            self.assertEqual(result['subset_score'], 0)
            args.resume = True
            self.run_quietly(args)
            self.assertEqual(len(list((Path(d) / 'run').glob('attempts/*/*/outcome.json'))), 1)
        with self.assertRaises(ValueError):
            A.normalise_custom({'answer': {}, 'finish_reason': 'made_up'})

    def test_concurrency_limit_and_stop_dispatch(self):
        active, peak, called = 0, 0, []
        lock = threading.Lock()
        def mock(case, config, attempt):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                called.append(case['call_id'])
                first = len(called) == 1
            time.sleep(.03 if first else .1)
            with lock:
                active -= 1
            return A.missing('server_error') if first else A.normalise_custom({'answer': None, 'finish_reason': 'stop'})
        with tempfile.TemporaryDirectory() as d, patch.object(A, 'call_api', side_effect=mock):
            args = self.args(d, '--workers', '2', '--retries', '0')
            args.only = [c['call_id'] for c in self.cases[:5]]
            with self.assertRaisesRegex(ValueError, 'paused'):
                self.run_quietly(args)
            self.assertEqual(peak, 2)
            self.assertEqual(len(called), 2)

    def test_no_tools_or_prompt_override_in_provider_options(self):
        with tempfile.TemporaryDirectory() as d:
            config = R.configuration(self.args(d))
            for key in ('messages', 'input', 'tools', 'max_tokens', 'n', 'api_key'):
                config['options'] = {key: 'not allowed'}
                with self.assertRaisesRegex(ValueError, 'Unsupported API options'):
                    A.request_body(self.cap, config)

    def test_malformed_protocol_cannot_be_retried_as_a_better_answer(self):
        with tempfile.TemporaryDirectory() as d, server([(200, {'choices': []})]) as (url, seen):
            args = self.args(d, '--base-url', url)
            with self.assertRaisesRegex(ValueError, 'paused'):
                self.run_quietly(args)
            args.resume = args.retry_infrastructure = True
            with self.assertRaisesRegex(ValueError, 'repair, not regeneration'):
                self.run_quietly(args)
            self.assertEqual(len(seen), 1)

    def test_nonfinite_completed_answer_is_invalid_not_missing(self):
        row = A.parse_api(chat('{"answer": [NaN]}'), 'chat-completions')
        self.assertTrue(row['scored'])
        self.assertIsNone(row['answer'])

    def test_complete_suite_uses_all_69_once(self):
        def mock(case, config, attempt):
            return A.normalise_custom({'answer': None, 'finish_reason': 'length',
                                      'usage': {'input_tokens': 1, 'output_tokens': 128000}})
        with tempfile.TemporaryDirectory() as d, patch.object(A, 'call_api', side_effect=mock) as call:
            args = self.args(d)
            args.only = None
            result = self.run_quietly(args)
            args.resume = True
            self.run_quietly(args)
            self.assertEqual(call.call_count, 69)
            self.assertTrue(result['complete_suite'])
            self.assertEqual(result['score'], 0)
            self.assertEqual(len((Path(d) / 'answers.jsonl').read_text().splitlines()), 69)


if __name__ == '__main__':
    unittest.main()
