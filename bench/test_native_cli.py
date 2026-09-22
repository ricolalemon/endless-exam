"""Native event guards and fake-process integration; never call a model service.

Set EE_NATIVE_LOOPBACK=1 to also exercise installed CLIs against localhost SSE
fixtures. Those optional tests use dummy credentials, never a provider endpoint.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import argparse
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import exam
import model_runner as R
import native_cli as N


def event(mon, typ, **data):
    mon.feed(json.dumps({'type': 'stream_event', 'event': {'type': typ, **data}}))


def start(mon, ident='msg1'):
    event(mon, 'message_start', message={'id': ident, 'model': 'claude-fable-5-1',
          'usage': {'input_tokens': 10, 'cache_read_input_tokens': 100, 'output_tokens': 1}})


def complete(mon, text='{"answer": []}', tokens=5, reason='end_turn'):
    event(mon, 'content_block_start', index=0, content_block={'type': 'text', 'text': ''})
    event(mon, 'content_block_delta', index=0, delta={'type': 'text_delta', 'text': text})
    event(mon, 'content_block_stop', index=0)
    event(mon, 'message_delta', delta={'stop_reason': reason}, usage={'output_tokens': tokens})
    event(mon, 'message_stop')


def codex_complete(mon, text='{"answer": []}', tokens=5):
    for e in [{'type': 'turn.started'}, {'type': 'item.completed',
              'item': {'type': 'agent_message', 'text': text}},
              {'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': tokens}}]:
        mon.feed(json.dumps(e))


class EventTests(unittest.TestCase):
    def test_model_text_never_controls_failure_classification(self):
        for kind in ('codex', 'claude-code'):
            m = N.CodexMonitor() if kind == 'codex' else N.ClaudeMonitor()
            if kind == 'codex':
                codex_complete(m, 'network error; max_output_tokens; retry me')
            else:
                start(m); complete(m, 'network error; max_output_tokens; retry me')
            row = m.finish(0)
            self.assertTrue(row['scored']); self.assertEqual(row['finish_reason'], 'stop')
            self.assertIsNone(row['answer']); self.assertFalse(row['retryable'])

    def test_claude_snapshots_cache_and_summary_not_double_counted(self):
        m = N.ClaudeMonitor(); start(m); complete(m, tokens=20)
        m.feed(json.dumps({'type': 'result', 'is_error': False, 'result': '{"answer": []}',
               'modelUsage': {'claude-fable-5-1': {'inputTokens': 10, 'cacheReadInputTokens': 100, 'outputTokens': 20}}}))
        row = m.finish(0)
        self.assertEqual(row['usage']['output_tokens'], 20)
        self.assertEqual(row['usage']['input_tokens'], 110)
        self.assertEqual(row['output_tokens'], 20)
        self.assertTrue(row['usage_complete'])

    def test_claude_reconnection_keeps_all_usage_and_final_budget_separate(self):
        m = N.ClaudeMonitor(); start(m)
        event(m, 'message_delta', usage={'output_tokens': 20000})
        m.feed(json.dumps({'type': 'system', 'subtype': 'api_retry', 'attempt': 1}))
        start(m, 'msg2'); complete(m, tokens=120000)
        row = m.finish(0)
        self.assertTrue(row['scored']); self.assertFalse(row['usage_complete'])
        self.assertEqual(row['usage']['output_tokens'], 140000)
        self.assertEqual(row['output_tokens'], 120000)
        self.assertEqual(row['finish_reason'], 'stop')

    def test_claude_incomplete_stop_is_missing_and_can_resume(self):
        m = N.ClaudeMonitor(); start(m); event(m, 'message_stop')
        row = m.finish(1)
        self.assertFalse(row['scored'])
        m.failure = None; start(m, 'msg2'); complete(m)
        row = m.finish(0)
        self.assertEqual(row['finish_reason'], 'stop'); self.assertFalse(row['usage_complete'])

    def test_budget_stop_is_permanent_zero(self):
        m = N.ClaudeMonitor(); start(m); complete(m, tokens=128000, reason='max_tokens')
        row = m.finish(-9)
        self.assertEqual(row['finish_reason'], 'length'); self.assertTrue(row['scored'])
        self.assertEqual(row['usage']['output_tokens'], 128000)
        self.assertTrue(row['usage_complete'])
        m = N.CodexMonitor()
        m.feed('{"type":"error","message":"response incomplete: max_output_tokens"}')
        row = m.finish(-9)
        self.assertTrue(row['scored']); self.assertFalse(row['usage_complete'])

    def test_first_completed_answer_survives_extra_turn_and_queue_stops(self):
        m = N.ClaudeMonitor(); start(m); complete(m, '{"answer": [1]}')
        start(m, 'msg2'); complete(m, '{"answer": [2,3]}')
        row = m.finish(-9)
        self.assertEqual(row['answer'], [1]); self.assertTrue(row['halt_collection'])
        m = N.CodexMonitor(); codex_complete(m, '{"answer": [1]}'); codex_complete(m, '{"answer": [2,3]}')
        row = m.finish(-9)
        self.assertEqual(row['answer'], [1]); self.assertTrue(row['halt_collection'])

    def test_codex_reconnection_is_allowed_but_usage_incomplete(self):
        m = N.CodexMonitor()
        m.feed('{"type":"error","message":"Reconnecting... 1/5 (stream disconnected)"}')
        codex_complete(m)
        row = m.finish(0)
        self.assertEqual(row['finish_reason'], 'stop'); self.assertFalse(row['usage_complete'])
        self.assertIsNone(row['response_model'])  # never invent backend identification

    def test_deadline_distinguishes_active_generation_from_transport(self):
        for active, network, want in [(False, False, 'transport_error'), (True, False, 'timeout'),
                                      (True, True, 'transport_error')]:
            m = N.ClaudeMonitor()
            if active: start(m)
            m.pending_transport = network; m.failure = 'timeout'
            self.assertEqual(m.finish(-9)['finish_reason'], want)

    def test_tools_and_paid_allowance(self):
        m = N.ClaudeMonitor(); start(m)
        event(m, 'content_block_start', index=0, content_block={'type': 'tool_use', 'name': 'Bash'})
        self.assertEqual(m.finish(-9)['finish_reason'], 'tool_violation')
        m = N.ClaudeMonitor()
        m.feed('{"type":"system","subtype":"init","tools":["Read"]}')
        self.assertEqual(m.failure, 'collector_error')
        for status, want in [('allowed', None), ('rejected', 'quota')]:
            m = N.ClaudeMonitor()
            m.feed(json.dumps({'type': 'rate_limit_event', 'rate_limit_info': {'status': 'rejected', 'overageStatus': status}}))
            self.assertEqual(m.failure, want)

    def test_no_auth_values_in_config_or_global_changes(self):
        fake = {'ANTHROPIC_API_KEY': 'fake-api', 'ANTHROPIC_BASE_URL': 'fake-url',
                'OPENAI_API_KEY': 'fake-openai', 'CLAUDECODE': 'nested'}
        with patch.dict(os.environ, fake):
            env = N.environment('claude-code')
            self.assertNotIn('ANTHROPIC_API_KEY', env); self.assertNotIn('CLAUDECODE', env)
            self.assertEqual(N.environment('claude-code', 'environment')['ANTHROPIC_API_KEY'], 'fake-api')
            self.assertNotIn('OPENAI_API_KEY', N.environment('codex'))
            self.assertEqual(os.environ['ANTHROPIC_API_KEY'], 'fake-api')

    def test_budget_signal_kills_process_before_continuation(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            script = ('import json,time,pathlib;print(json.dumps({"type":"error","message":"max_output_tokens"}),flush=True);'
                      'time.sleep(5);pathlib.Path("continued").touch()')
            t = time.monotonic()
            row = N.collect([sys.executable, '-u', '-c', script], p, p, os.environ.copy(), 'fixture', N.CodexMonitor(), 10)
            self.assertLess(time.monotonic() - t, 2)
            self.assertEqual(row['finish_reason'], 'length'); self.assertFalse((p / 'continued').exists())

    def test_runner_native_adapter_resume_preserves_scored_count(self):
        p = argparse.ArgumentParser(); R.add_parser(p.add_subparsers())
        with tempfile.TemporaryDirectory() as d, patch.object(N, 'preflight', return_value={
                'binary': '/mock/codex', 'version': '0.154.0'}), patch.object(N, 'call_cli') as call:
            args = p.parse_args(['run', '--adapter', 'codex', '--model', 'gpt-6-astra', '--effort', 'high', '--output', d,
                                 '--only', 'a3-capset-0'])
            call.return_value = {'answer': None, 'finish_reason': 'stop', 'scored': True, 'retryable': False,
                                 'output_tokens': 120000, 'usage': {'output_tokens': 140000}, 'usage_complete': False}
            with patch('sys.stdout', new_callable=io.StringIO):
                R.run(args); args.resume = True; R.run(args)
            self.assertEqual(call.call_count, 1)
            saved = json.loads((Path(d) / 'answers.jsonl').read_text())
            self.assertEqual(saved['output_tokens'], 120000)
            self.assertEqual(saved['usage']['output_tokens'], 140000)

    def test_both_native_adapters_collect_full_suite_with_fixture_executables(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for adapter in ('codex', 'claude-code'):
                script = root / adapter
                script.write_text('#!' + sys.executable + '\n' + '''
import sys,json
from pathlib import Path
kind=Path(sys.argv[0]).name
if '--version' in sys.argv:
 print('0.154.0' if kind=='codex' else '2.1.269');sys.exit(0)
if '--help' in sys.argv:
 print('--ignore-user-config --ignore-rules --strict-config --ephemeral --json --tools --strict-mcp-config --safe-mode --setting-sources --disable-slash-commands --no-session-persistence');sys.exit(0)
if 'features' in sys.argv:
 print(''' + repr('\n'.join(N.CODEX_DISABLED + ('skip_host_skill_discovery',))) + ''');sys.exit(0)
prompt=sys.stdin.read()
assert 'Rules for this task: you have NO tools' in prompt
def send(e):print(json.dumps(e),flush=True)
if kind=='codex':
 send({'type':'turn.started'})
 send({'type':'item.completed','item':{'type':'agent_message','text':'{"answer": null}'}})
 send({'type':'turn.completed','usage':{'input_tokens':10,'output_tokens':5,'reasoning_output_tokens':2}})
else:
 def ev(typ,**fields):send({'type':'stream_event','event':{'type':typ,**fields}})
 ev('message_start',message={'id':'one','model':'claude-fable-5-1','usage':{'input_tokens':10,'output_tokens':1}})
 ev('content_block_start',index=0,content_block={'type':'text','text':'{"answer": null}'})
 ev('content_block_stop',index=0)
 ev('message_delta',delta={'stop_reason':'end_turn'},usage={'output_tokens':5})
 ev('message_stop')
''')
                script.chmod(0o755)
                p = argparse.ArgumentParser(); R.add_parser(p.add_subparsers())
                output = root / (adapter + '-run')
                args = p.parse_args(['run', '--adapter', adapter, '--model',
                       'gpt-6-astra' if adapter == 'codex' else 'claude-fable-5-1',
                       '--effort', 'high', '--cli-binary', str(script), '--output', str(output)])
                with patch('sys.stdout', new_callable=io.StringIO):
                    result = R.run(args)
                    args.resume = True
                    R.run(args)
                self.assertTrue(result['complete_suite'])
                self.assertEqual(len(list(output.glob('attempts/*/*/outcome.json'))), 69)
                usage = json.loads((output / 'usage.json').read_text())
                self.assertEqual(usage['output_tokens']['reported_total'], 69 * 5)
                self.assertTrue(usage['output_tokens']['complete'])


@unittest.skipUnless(os.environ.get('EE_NATIVE_LOOPBACK') == '1', 'opt-in installed CLI tests')
class NativeLoopbackTests(unittest.TestCase):
    def exercise(self, adapter, mode):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                self.send_response(200); self.end_headers(); self.wfile.write(b'{"data":[],"models":[]}')
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
                if '/messages' not in self.path and '/responses' not in self.path:
                    self.send_response(200); self.end_headers(); self.wfile.write(b'{}'); return
                requests.append(body)
                if mode == 'retry' and len(requests) == 1:
                    self.send_response(503); self.end_headers(); self.wfile.write(b'{"type":"error","error":{"type":"overloaded_error","message":"fixture"}}'); return
                self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
                def send(typ, **data):
                    try:
                        self.wfile.write(('event: ' + typ + '\ndata: ' + json.dumps({'type': typ, **data}) + '\n\n').encode()); self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError): pass
                if adapter == 'claude-code':
                    send('message_start', message={'id': 'msg1', 'type': 'message', 'role': 'assistant', 'model': 'claude-fable-5-1',
                         'content': [], 'stop_reason': None, 'stop_sequence': None, 'usage': {'input_tokens': 10, 'output_tokens': 1}})
                    send('content_block_start', index=0, content_block={'type': 'text', 'text': ''})
                    send('content_block_delta', index=0, delta={'type': 'text_delta', 'text': '{"answer": []}'})
                    send('content_block_stop', index=0)
                    send('message_delta', delta={'stop_reason': 'max_tokens' if mode == 'length' else 'end_turn', 'stop_sequence': None},
                         usage={'output_tokens': 128000 if mode == 'length' else 5})
                    send('message_stop')
                else:
                    response = {'id': 'resp1', 'object': 'response', 'status': 'in_progress', 'output': []}
                    send('response.created', response=response)
                    if mode == 'length':
                        send('response.incomplete', response={**response, 'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}})
                    else:
                        item = {'id': 'm1', 'type': 'message', 'role': 'assistant', 'status': 'completed',
                                'content': [{'type': 'output_text', 'text': '{"answer": []}', 'annotations': []}]}
                        send('response.output_item.added', output_index=0, item={**item, 'status': 'in_progress', 'content': []})
                        send('response.output_text.delta', item_id='m1', output_index=0, content_index=0, delta='{"answer": []}')
                        send('response.output_item.done', output_index=0, item=item)
                        send('response.completed', response={**response, 'status': 'completed', 'output': [item],
                             'usage': {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15}})
                self.close_connection = True
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as d:
                path = Path(d)
                config = {'adapter': adapter, 'model': 'gpt-6-astra' if adapter == 'codex' else 'claude-fable-5-1',
                          'effort': 'high', 'native': N.preflight(adapter), 'cli_auth': 'login'}
                env = N.environment(adapter)
                for k in list(env):
                    if any(part in k for part in ('OAUTH', 'AUTH_TOKEN', 'API_KEY')):
                        env.pop(k)
                if adapter == 'claude-code':
                    env.update(ANTHROPIC_API_KEY='offline-dummy', ANTHROPIC_BASE_URL=f'http://127.0.0.1:{server.server_port}',
                               CLAUDE_CONFIG_DIR=str(path / 'config'))
                    cmd, monitor = N.command(config, path), N.ClaudeMonitor()
                else:
                    provider = ('{name="Fixture",wire_api="responses",requires_openai_auth=false,supports_websockets=false,'
                                'request_max_retries=4,stream_max_retries=0,base_url="http://127.0.0.1:' + str(server.server_port) + '/v1"}')
                    cmd, monitor = N.command(config, path, provider), N.CodexMonitor()
                row = N.collect(cmd, path, path, env, 'Offline protocol fixture only.', monitor, 30)
                evidence = {'row': row, 'stderr': (path / 'stderr.txt').read_text()[-1800:], 'requests': len(requests)}
                self.assertEqual(row['finish_reason'], 'length' if mode == 'length' else 'stop', evidence)
                self.assertEqual(len(requests), 2 if mode == 'retry' else 1, evidence)
                for req in requests:
                    self.assertEqual(req.get('tools', []), [], evidence)
                    self.assertEqual(req['model'], config['model'])
                    if adapter == 'claude-code':
                        self.assertEqual(req['max_tokens'], 128000)
                        self.assertEqual(req['output_config']['effort'], 'high')
                    else:
                        self.assertEqual(req['reasoning']['effort'], 'high')
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_codex_success(self): self.exercise('codex', 'success')
    def test_codex_budget_stop(self): self.exercise('codex', 'length')
    def test_codex_request_retry(self): self.exercise('codex', 'retry')
    def test_claude_success(self): self.exercise('claude-code', 'success')
    def test_claude_budget_stop(self): self.exercise('claude-code', 'length')
    def test_claude_request_retry(self): self.exercise('claude-code', 'retry')


if __name__ == '__main__':
    unittest.main()
