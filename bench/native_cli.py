"""Tool-free Codex and Claude Code adapters, extracted from the paper collectors.

Native events decide completion/failure. Model-authored text never permits a retry.
No global CLI configuration, authentication or frozen experiment files are edited.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import tempfile
import time

import model_adapters as A
from agent_bridge import NO_TOOLS

TESTED = {'codex': '0.154.0', 'claude-code': '2.1.269'}
CODEX_DISABLED = (
    'shell_tool', 'unified_exec', 'unified_exec_tty', 'multi_agent', 'view_image',
    'sleep_tool', 'tool_suggest', 'plugins', 'apps', 'computer_use', 'browser_use',
    'image_generation', 'code_mode_host', 'skill_search', 'hooks', 'memories',
)
CLAUDE_ENV = {
    'CLAUDE_CODE_MAX_OUTPUT_TOKENS': '128000', 'CLAUDE_CODE_MAX_RETRIES': '4',
    'CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK': '1', 'DISABLE_AUTO_COMPACT': '1',
    'DISABLE_AUTOUPDATER': '1', 'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1',
    'CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK': '1', 'CLAUDE_CODE_DISABLE_FAST_MODE': '1',
}
TOOL_ITEMS = {'command_execution', 'mcp_tool_call', 'web_search', 'file_change',
              'tool_call', 'function_call', 'custom_tool_call'}


def prompt(case):
    return case['prompt'] + NO_TOOLS


def input_record(case):
    return {'prompt': prompt(case), 'system_policy': 'native_cli'}


def preflight(adapter, binary=None, allow_untested=False):
    executable = shutil.which(binary or ('claude' if adapter == 'claude-code' else 'codex'))
    if not executable:
        raise ValueError(f'{adapter} is not installed; install it and sign in before collection')
    executable = str(Path(executable).absolute())
    with tempfile.TemporaryDirectory(prefix='ee-cli-preflight-') as cwd:
        env = environment(adapter)
        result = subprocess.run([executable, '--version'], cwd=cwd, capture_output=True,
                                text=True, timeout=15, check=True, env=env)
        version = re.search(r'\b\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\b', result.stdout)
        if not version:
            raise ValueError(f'Cannot identify the {adapter} version')
        version = version.group()
        if version != TESTED[adapter] and not allow_untested:
            raise ValueError(f'{adapter} {version} is untested; validated version: {TESTED[adapter]}. '
                             'Use that version or explicitly pass --allow-untested-cli.')
        help_args = ['exec', '--help'] if adapter == 'codex' else ['--help']
        help_text = subprocess.check_output([executable, *help_args], cwd=cwd, text=True, timeout=15, env=env)
        required = (['--ignore-user-config', '--ignore-rules', '--strict-config', '--ephemeral', '--json']
                    if adapter == 'codex' else ['--tools', '--strict-mcp-config', '--safe-mode',
                         '--setting-sources', '--disable-slash-commands', '--no-session-persistence'])
        if any(flag not in help_text for flag in required):
            raise ValueError(f'{adapter} lacks required isolation flags')
        if adapter == 'codex':
            listing = subprocess.check_output([executable, 'features', 'list'], cwd=cwd, text=True, timeout=15, env=env)
            features = {line.split()[0] for line in listing.splitlines() if line.strip()}
            if not (set(CODEX_DISABLED) | {'skip_host_skill_discovery'}) <= features:
                raise ValueError('Codex lacks required feature controls')
    return {'binary': executable, 'version': version, 'tested_version': version == TESTED[adapter],
            'executable_sha256': hashlib.sha256(Path(executable).read_bytes()).hexdigest(),
            'request_max_retries': 4, 'stream_max_retries': 5 if adapter == 'codex' else None,
            'retry_policy': 'native CLI only; no automatic outer resubmission',
            'output_budget': 128000,
            'budget_enforcement': ('native output-limit stop plus reported final-turn count'
                                   if adapter == 'codex' else 'native max_tokens and first output-limit stop')}


def environment(adapter, auth='login'):
    env = dict(os.environ)
    if adapter == 'claude-code':
        # Remove nested-session detection. Safe mode disables customizations while
        # preserving the CLI's stored authentication (unlike Claude's --bare).
        env.pop('CLAUDECODE', None)
        if auth == 'login':
            for key in list(env):
                if key.startswith('ANTHROPIC_') or key in {
                    'CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDE_CODE_USE_BEDROCK',
                    'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_USE_FOUNDRY'}:
                    env.pop(key)
        env.update(CLAUDE_ENV)
    elif auth == 'login':
        for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL'):
            env.pop(key, None)
    return env


def command(config, attempt, provider=None):
    binary = config['native']['binary']
    effort = config['effort']
    if config['adapter'] == 'codex':
        if provider is None and config['cli_auth'] == 'environment':
            provider = ('{name="OpenAI",wire_api="responses",requires_openai_auth=false,'
                        'supports_websockets=true,request_max_retries=4,stream_max_retries=5,'
                        'env_key=' + json.dumps(config['api_key_env']) + ',base_url=' + json.dumps(config['base_url']) + '}')
        provider = provider or ('{name="OpenAI",wire_api="responses",requires_openai_auth=true,'
                                'supports_websockets=true,request_max_retries=4,stream_max_retries=5}')
        args = [binary, 'exec', '--ignore-user-config', '--ignore-rules', '--skip-git-repo-check',
                '--ephemeral', '--strict-config', '-m', config['model'], '--sandbox', 'read-only',
                '-c', 'model_provider="endless_exam"', '-c', f'model_providers.endless_exam={provider}',
                '-c', 'project_doc_max_bytes=0', '-c', 'mcp_servers={}', '-c', 'tools.web_search=false',
                '--enable', 'skip_host_skill_discovery']
        for feature in CODEX_DISABLED:
            args.extend(['--disable', feature])
        if effort:
            args.extend(['-c', 'model_reasoning_effort=' + json.dumps(effort)])
        return [*args, '--json', '-o', str(attempt / 'last-message.txt'), '-']
    args = [binary, '-p', '--model', config['model'], '--tools', '', '--strict-mcp-config',
            '--mcp-config', '{"mcpServers":{}}', '--disallowedTools', 'mcp__*',
            '--safe-mode', '--setting-sources', '', '--settings', '{"disableAllHooks":true}',
            '--disable-slash-commands', '--no-chrome', '--prompt-suggestions', 'false',
            '--max-turns', '1', '--output-format', 'stream-json', '--include-partial-messages',
            '--verbose', '--no-session-persistence']
    if effort:
        args.extend(['--effort', effort])
    return args


class CodexMonitor:
    def __init__(self):
        self.failure = None
        self.started = 0
        self.completed = 0
        self.text = ''
        self.first = None
        self.usage = {}
        self.usage_events = []
        self.retries = []
        self.pending_transport = False
        self.models = set()
        self.halt_collection = False
        self.interrupted = False

    def feed(self, line, stderr=False):
        if stderr:
            if not any(s in line.lower() for s in ('codex_core::responses_retry', 'codex_core::client')):
                return
            self.native_error(line)
            return
        e = json.loads(line)
        kind, item = e.get('type'), e.get('item') or {}
        if e.get('model'):
            self.models.add(e['model'])
        if kind in ('error', 'turn.failed') or item.get('type') == 'error':
            self.native_error(str(e.get('message') or e.get('error') or item.get('message') or ''))
        if item.get('type') in TOOL_ITEMS:
            self.failure = 'tool_violation'
        if kind == 'turn.started':
            self.started += 1
            if self.started > 1:
                self.halt_collection = True
                self.failure = self.failure or 'collector_error'
        if kind == 'item.completed' and item.get('type') == 'agent_message':
            self.text = item.get('text') or ''
        if kind == 'turn.completed':
            self.completed += 1
            native_usage = e.get('usage') or {}
            self.usage_events.append(native_usage)
            usage = A.normalise_usage(native_usage)
            if native_usage.get('reasoning_output_tokens') is not None:
                usage['reasoning_tokens'] = A.token_count(native_usage['reasoning_output_tokens'])
            for k, v in usage.items():
                if v is not None:
                    self.usage[k] = self.usage.get(k, 0) + v
            if self.first is None:
                self.first = {'text': self.text, 'usage': usage}
            else:
                self.halt_collection = True
            self.pending_transport = False

    def native_error(self, message):
        low = message.lower()
        if 'max_output_tokens' in low or 'maximum output tokens' in low:
            self.failure = 'length'
        elif any(s in low for s in ('reconnecting...', 'retrying sampling request', 'falling back from websockets')):
            self.retries.append(message)
            self.pending_transport = True
            self.interrupted = True
            if self.first:
                self.halt_collection = True
        elif any(s in low for s in ('quota', 'usage limit', 'rate limit', 'insufficient_quota')):
            self.failure = 'quota'
        else:
            self.pending_transport = True
            self.interrupted = self.interrupted or self.first is None

    def finish(self, returncode):
        reason = self.failure
        if self.first and reason != 'tool_violation':
            reason = 'stop'
        elif reason == 'timeout' and (not self.started or self.pending_transport):
            reason = 'transport_error'
        elif not reason:
            reason = 'transport_error' if self.pending_transport else 'incomplete_turn'
        self.failure = reason
        first = self.first or {}
        usage = {k: self.usage.get(k) for k in ('input_tokens', 'output_tokens', 'reasoning_tokens')}
        complete = bool(self.first) and not self.interrupted and not self.retries and self.completed == 1
        return outcome(reason, first.get('text', ''), usage, first.get('usage', {}).get('output_tokens'),
                       complete, self.models, self.retries, self.halt_collection,
                       {'turns_started': self.started, 'turns_completed': self.completed,
                        'usage_events': self.usage_events, 'returncode': returncode})


class ClaudeMonitor:
    def __init__(self):
        self.failure = None
        self.result = None
        self.messages = []
        self.current = None
        self.first = None
        self.models = set()
        self.retries = []
        self.pending_transport = False
        self.halt_collection = False
        self.interrupted = False

    def model(self, name):
        if name and name != '<synthetic>':
            self.models.add(name)
            if len(self.models) > 1:
                self.failure = 'collector_error'
                self.halt_collection = True

    def update_usage(self, usage):
        if self.current and isinstance(usage, dict):
            self.current['usage'].update(usage)  # cumulative snapshot for this message
            if self.current['usage'].get('output_tokens', 0) > 128000:
                self.failure = 'length'

    def feed(self, line, stderr=False):
        if stderr:
            return
        e = json.loads(line)
        kind = e.get('type')
        if kind == 'system' and e.get('subtype') == 'init':
            self.model(e.get('model'))
            if e.get('tools') or e.get('mcp_servers'):
                self.failure = 'collector_error'
        if kind == 'system' and e.get('subtype') == 'api_retry':
            self.retries.append(e)
            self.pending_transport = True
            if self.first:
                self.halt_collection = True
        if kind == 'rate_limit_event':
            info = e.get('rate_limit_info') or {}
            if info.get('status') == 'rejected' and info.get('overageStatus') not in ('allowed', 'allowed_warning'):
                self.failure = self.failure or 'quota'
        if kind == 'error':
            self.pending_transport = True
            self.interrupted = self.interrupted or self.first is None
        if kind == 'stream_event':
            ev = e.get('event') or {}
            typ = ev.get('type')
            if typ == 'error':
                self.pending_transport = True
                self.interrupted = self.interrupted or self.first is None
            elif typ == 'message_start':
                msg = ev.get('message') or {}
                self.model(msg.get('model'))
                if self.first or (self.current and not self.pending_transport):
                    self.halt_collection = True
                    self.failure = 'collector_error'
                self.current = {'id': msg.get('id'), 'usage': {}, 'blocks': {}, 'closed': [],
                                'stop_reason': None, 'complete': False}
                self.messages.append(self.current)
                self.pending_transport = False
                self.update_usage(msg.get('usage'))
            elif typ == 'content_block_start' and self.current:
                block = ev.get('content_block') or {}
                self.current['blocks'][str(ev['index'])] = {'type': block.get('type'), 'text': block.get('text', '')}
                if block.get('type') in ('tool_use', 'server_tool_use'):
                    self.failure = 'tool_violation'
            elif typ == 'content_block_delta' and self.current:
                delta = ev.get('delta') or {}
                if delta.get('type') == 'text_delta':
                    self.current['blocks'][str(ev['index'])]['text'] += delta.get('text', '')
            elif typ == 'content_block_stop' and self.current:
                self.current['closed'].append(str(ev['index']))
            elif typ == 'message_delta':
                self.update_usage(ev.get('usage'))
                reason = (ev.get('delta') or {}).get('stop_reason')
                if reason and self.current:
                    self.current['stop_reason'] = reason
                if reason in ('max_tokens', 'model_context_window_exceeded'):
                    self.failure = 'length'
            elif typ == 'message_stop' and self.current:
                msg = self.current
                if msg['stop_reason'] is None:
                    self.pending_transport = True
                    self.retries.append({'type': 'incomplete_message_stop', 'message_id': msg['id']})
                else:
                    msg['complete'] = True
                    self.pending_transport = False
                    if msg['stop_reason'] in ('end_turn', 'stop_sequence', 'refusal') and set(msg['blocks']) == set(msg['closed']):
                        if self.first is None:
                            self.first = msg
                        else:
                            self.halt_collection = True
        elif kind == 'assistant':
            msg = e.get('message') or {}
            self.model(msg.get('model'))
            if any(b.get('type') in ('tool_use', 'server_tool_use') for b in msg.get('content', [])):
                self.failure = 'tool_violation'
            if e.get('error') == 'max_output_tokens':
                self.failure = 'length'
            elif e.get('error'):
                self.pending_transport = True
                self.interrupted = self.interrupted or self.first is None
        elif kind == 'result':
            self.result = e
            for name in e.get('modelUsage') or {}:
                self.model(name)
            if e.get('num_turns', 1) > 1:
                self.halt_collection = True
            if e.get('is_error'):
                self.pending_transport = True
                if e.get('api_error_status') == 429:
                    self.failure = self.failure or 'quota'

    def finish(self, returncode):
        reason = self.failure
        if self.first and reason != 'tool_violation':
            reason = 'stop'
        elif reason == 'timeout' and (not self.messages or self.pending_transport):
            reason = 'transport_error'
        elif not reason:
            reason = 'transport_error' if self.pending_transport else 'incomplete_turn'
        self.failure = reason
        def total(key):
            values = [A.token_count(m['usage'].get(key)) for m in self.messages]
            return sum(v for v in values if v is not None) if any(v is not None for v in values) else None
        incoming = total('input_tokens')
        if incoming is not None:
            incoming += (total('cache_read_input_tokens') or 0) + (total('cache_creation_input_tokens') or 0)
        usage = {'input_tokens': incoming, 'output_tokens': total('output_tokens'), 'reasoning_tokens': None}
        # Per-model summary and streaming snapshots cover overlapping tokens.
        # Retain both sources, and use the larger reported aggregate, never their sum.
        summaries = list((self.result or {}).get('modelUsage', {}).values())
        if summaries:
            for key, native in (('input_tokens', 'inputTokens'), ('output_tokens', 'outputTokens')):
                values = [A.token_count(s.get(native)) for s in summaries]
                if all(v is not None for v in values):
                    count = sum(values)
                    if key == 'input_tokens':
                        count += sum((s.get('cacheReadInputTokens') or 0) + (s.get('cacheCreationInputTokens') or 0) for s in summaries)
                    usage[key] = max(usage[key] or 0, count)
        first = self.first or {}
        text = ''.join(b['text'] for _, b in sorted(first.get('blocks', {}).items(), key=lambda p: int(p[0])) if b['type'] == 'text')
        if first and self.result and not self.result.get('is_error') and not self.halt_collection:
            summary_text = self.result.get('result')
            if summary_text and summary_text != text:
                self.halt_collection = True
        complete = bool(self.messages) and not self.interrupted and not self.retries and len(self.messages) == 1 and all(
            m['complete'] and all(k in m['usage'] for k in ('input_tokens', 'output_tokens')) for m in self.messages)
        tokens = (first or self.current or {}).get('usage', {}).get('output_tokens')
        return outcome(reason, text, usage, tokens, complete,
                       self.models, self.retries, self.halt_collection,
                       {'messages': [{k: v for k, v in m.items() if k != 'blocks'} for m in self.messages],
                        'result_usage': (self.result or {}).get('usage'),
                        'model_usage': (self.result or {}).get('modelUsage'), 'returncode': returncode})


def outcome(reason, text, usage, scored_tokens, complete, models, retries, halt, evidence):
    if scored_tokens is not None and scored_tokens > 128000:
        reason = 'length'
    return {'finish_reason': reason, 'scored': reason in A.FINAL_REASONS, 'retryable': False,
            'answer': A.json_answer(A.extract_json(text)), 'content': text,
            'usage': usage, 'output_tokens': scored_tokens,
            'usage_complete': complete and all(usage.get(k) is not None for k in ('input_tokens', 'output_tokens')),
            'response_model': next(iter(models)) if len(models) == 1 else None,
            'reported_models': sorted(models), 'reconnection_events': retries,
            'halt_collection': halt, 'native_evidence': evidence}


def collect(cmd, cwd, attempt, env, input_text, monitor, timeout):
    """Watch stdout/stderr concurrently; stop the group before any continuation."""
    start = time.monotonic()
    # A file avoids a large blocking stdin write while native stdout is waiting.
    (attempt / 'prompt.txt').write_text(input_text)
    with (attempt / 'prompt.txt').open('rb') as inp, (attempt / 'events.jsonl').open('xb', buffering=0) as out, \
            (attempt / 'stderr.txt').open('xb', buffering=0) as err:
        proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdin=inp, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True)
        selector = selectors.DefaultSelector()
        buffers = {}
        for stream, is_error, dest in ((proc.stdout, False, out), (proc.stderr, True, err)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, (is_error, dest))
            buffers[stream] = b''
        killed = False
        try:
            while selector.get_map():
                if time.monotonic() - start >= timeout and not monitor.failure:
                    monitor.failure = 'timeout'
                if (monitor.failure or monitor.halt_collection) and not killed:
                    kill_group(proc)
                    killed = True
                for key, _ in selector.select(.05):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    is_error, dest = key.data
                    if not chunk:
                        line = buffers[key.fileobj]
                        if line.strip():
                            feed(monitor, line, is_error)
                        selector.unregister(key.fileobj)
                        continue
                    dest.write(chunk)
                    buffers[key.fileobj] += chunk
                    while b'\n' in buffers[key.fileobj]:
                        line, buffers[key.fileobj] = buffers[key.fileobj].split(b'\n', 1)
                        if line.strip():
                            feed(monitor, line, is_error)
                        if (monitor.failure or monitor.halt_collection) and not killed:
                            kill_group(proc)
                            killed = True
            try:
                code = proc.wait(timeout=max(.1, timeout - (time.monotonic() - start)))
            except subprocess.TimeoutExpired:
                monitor.failure = monitor.failure or 'timeout'
                kill_group(proc)
                code = proc.wait(timeout=5)
        finally:
            selector.close()
            kill_group(proc)
            proc.wait(timeout=5)
            proc.stdout.close()
            proc.stderr.close()
    return monitor.finish(code)


def feed(monitor, line, stderr):
    try:
        monitor.feed(line.decode(errors='replace'), stderr)
    except (ValueError, TypeError, KeyError, AttributeError):
        monitor.failure = 'malformed_event'
        monitor.halt_collection = True


def kill_group(proc):
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def call_cli(case, config, attempt):
    cmd = command(config, attempt)
    A.write_json(attempt / 'request.json', {**input_record(case), 'argv': cmd,
                 'native': config['native'], 'auth_policy': config['cli_auth'],
                 'environment_overrides': CLAUDE_ENV if config['adapter'] == 'claude-code' else {}})
    monitor = CodexMonitor() if config['adapter'] == 'codex' else ClaudeMonitor()
    # Outside the checkout: no ancestor project instructions or benchmark files.
    with tempfile.TemporaryDirectory(prefix='ee-native-task-') as cwd:
        row = collect(cmd, cwd, attempt, environment(config['adapter'], config['cli_auth']),
                      prompt(case), monitor, config['timeout'])
    row['cli_version'] = config['native']['version']
    row['requested_model'] = config['model']
    if row['reported_models'] and config['model'].startswith(('claude-', 'gpt-')) and row['reported_models'] != [config['model']]:
        row.update(finish_reason='collector_error', scored=False, halt_collection=True,
                   model_mismatch=True)
    A.write_json(attempt / 'native-summary.json', row)
    return row
