"""Small, tool-free transports. No benchmark references cross this boundary."""
import http.client
import json
import os
from pathlib import Path
import signal
import subprocess
import urllib.error
import urllib.request

from run_ladder import extract_json

FINAL_REASONS = {'stop', 'length', 'timeout', 'refusal', 'tool_violation'}
MISSING_REASONS = {'transport_error', 'server_error', 'rate_limit', 'quota',
                   'cli_error', 'collector_error', 'incomplete_turn', 'malformed_event'}
API_OPTIONS = {'temperature', 'top_p', 'seed', 'reasoning_effort', 'reasoning',
               'thinking', 'service_tier', 'response_format', 'text'}


def write_json(path, value):
    """Atomic local artifact write; credentials are never passed to this helper."""
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def messages(case):
    return [{'role': 'system', 'content': case['system']},
            {'role': 'user', 'content': case['prompt']}]


def json_answer(value):
    """Non-finite JSON-like model output is an invalid answer, not a retry."""
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError):
        return None
    return value


def request_body(case, config):
    options = config['options']
    if set(options) - API_OPTIONS:
        raise ValueError('Unsupported API options: ' + ', '.join(sorted(set(options) - API_OPTIONS)))
    body = {'model': config['model'], 'stream': False, **options}
    if config['adapter'] == 'responses':
        body.update(input=messages(case), max_output_tokens=128000, store=False)
        if config['effort']:
            body['reasoning'] = {**body.get('reasoning', {}), 'effort': config['effort']}
    else:
        body.update(messages=messages(case), n=1)
        body[config['token_parameter']] = 128000
        if config['effort']:
            body['reasoning_effort'] = config['effort']
    return body


def missing(reason, retryable=False, **details):
    return {'answer': None, 'finish_reason': reason, 'scored': False,
            'retryable': retryable, 'usage': {}, 'usage_complete': False, **details}


def token_count(value):
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError('Token counts must be nonnegative integers or null')
    return value


def normalise_usage(usage, chat=False):
    if not isinstance(usage, dict):
        raise ValueError('usage must be an object')
    output = token_count(usage.get('completion_tokens' if chat else 'output_tokens'))
    incoming = token_count(usage.get('prompt_tokens' if chat else 'input_tokens'))
    details = usage.get('completion_tokens_details' if chat else 'output_tokens_details') or {}
    reasoning = token_count(details.get('reasoning_tokens', usage.get('reasoning_tokens')))
    # Reasoning is a subset of output, not another quantity to add to it.
    return {'input_tokens': incoming, 'output_tokens': output, 'reasoning_tokens': reasoning}


def parse_api(data, adapter):
    if not isinstance(data, dict):
        return missing('malformed_event')
    usage = normalise_usage(data.get('usage') or {}, chat=adapter == 'chat-completions')
    common = {'usage': usage, 'usage_complete': all(usage[k] is not None for k in
              ('input_tokens', 'output_tokens')), 'response_model': data.get('model'),
              'response_id': data.get('id'), 'service_tier': data.get('service_tier'),
              'system_fingerprint': data.get('system_fingerprint')}
    if data.get('error'):
        code = (data['error'].get('code') if isinstance(data['error'], dict) else None)
        return missing('quota' if code == 'insufficient_quota' else 'server_error', **common)
    if adapter == 'chat-completions':
        choices = data.get('choices', [])
        if len(choices) != 1:
            return missing('malformed_event', **common)
        choice = choices[0]
        message = choice.get('message') or {}
        reason = choice.get('finish_reason')
        if message.get('tool_calls') or message.get('function_call'):
            reason = 'tool_violation'
        elif reason == 'content_filter' or message.get('refusal'):
            reason = 'refusal'
        elif reason not in {'stop', 'length'}:
            return missing('incomplete_turn', **common)
        content = message.get('content') or ''
        if not isinstance(content, str):
            return missing('malformed_event', **common)
    else:
        status = data.get('status')
        detail = (data.get('incomplete_details') or {}).get('reason')
        if status == 'incomplete' and detail == 'max_output_tokens':
            reason = 'length'
        elif status == 'incomplete' and detail == 'content_filter':
            reason = 'refusal'
        elif status == 'completed':
            reason = 'stop'
        else:
            return missing('incomplete_turn', **common)
        output = data.get('output', [])
        if any(item.get('type') not in {'message', 'reasoning'} for item in output):
            reason = 'tool_violation'
        blocks = [block for item in output if item.get('type') == 'message'
                  for block in item.get('content', [])]
        if any(b.get('type') == 'refusal' for b in blocks):
            reason = 'refusal'
        content = '\n'.join(b['text'] for b in blocks if b.get('type') == 'output_text')
    return {'answer': json_answer(extract_json(content)), 'content': content, 'finish_reason': reason,
            'scored': True, 'retryable': False, **common}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward bearer credentials to a redirected endpoint.


def call_api(case, config, attempt):
    body = request_body(case, config)
    write_json(attempt / 'request.json', body)
    key = os.environ.get(config['api_key_env'], '') if config['api_key_env'] else ''
    headers = {'Content-Type': 'application/json'}
    if key:
        headers['Authorization'] = 'Bearer ' + key
    endpoint = config['base_url'].rstrip('/') + ('/responses' if config['adapter'] == 'responses'
                                                else '/chat/completions')
    request = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=config['timeout']) as response:
            raw = response.read()
        (attempt / 'response.json').write_bytes(raw)
        return parse_api(json.loads(raw), config['adapter'])
    except urllib.error.HTTPError as error:
        raw = error.read()
        error.close()
        (attempt / 'http-error.txt').write_bytes(raw)
        # Status/code are transport metadata, never phrases in generated answers.
        try:
            payload = json.loads(raw)
            code = (payload.get('error') or {}).get('code')
            usage = normalise_usage(payload.get('usage') or {}, config['adapter'] == 'chat-completions')
        except (ValueError, TypeError, AttributeError):
            code, usage = None, {}
        reason = ('quota' if code == 'insufficient_quota' else 'rate_limit' if error.code == 429
                  else 'server_error' if error.code >= 500 else 'collector_error')
        return missing(reason, retryable=reason in {'server_error', 'rate_limit'},
                       http_status=error.code, usage=usage)
    except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException):
        # A client timeout cannot prove that the provider exhausted a model budget.
        return missing('transport_error', retryable=True)
    except (ValueError, KeyError, TypeError, AttributeError):
        return missing('malformed_event')


def normalise_custom(data):
    if not isinstance(data, dict) or data.get('finish_reason') not in FINAL_REASONS | MISSING_REASONS:
        raise ValueError('Custom harness must supply a recognised finish_reason')
    reason = data['finish_reason']
    if reason == 'stop' and 'answer' not in data and not isinstance(data.get('content'), str):
        raise ValueError('A completed custom response needs answer (possibly null) or content')
    usage = normalise_usage(data.get('usage') or {})
    complete = all(usage[k] is not None for k in ('input_tokens', 'output_tokens'))
    if 'usage_complete' in data and type(data['usage_complete']) is not bool:
        raise ValueError('usage_complete must be a boolean')
    return {**data, 'answer': json_answer(data.get('answer', extract_json(data.get('content', '')))),
            'usage': usage, 'usage_complete': complete and data.get('usage_complete', True),
            'scored': reason in FINAL_REASONS, 'retryable': False}


def call_command(case, config, attempt):
    """Trusted harness wrapper. Its model must not receive this whole request."""
    request = {'schema_version': 1, 'call_id': case['call_id'], 'instance_id': case['instance_id'],
               'messages': messages(case), 'model': config['model'], 'effort': config['effort'],
               'track': 'tool-free', 'max_output_tokens': 128000,
               'settings': config['options']}
    write_json(attempt / 'request.json', request)
    argv = [arg.replace('{request}', str(attempt / 'request.json'))
            .replace('{response}', str(attempt / 'response.json')) for arg in config['argv']]
    workspace = attempt / 'workspace'
    workspace.mkdir()
    with (attempt / 'stdout.log').open('wb') as out, (attempt / 'stderr.log').open('wb') as err:
        proc = subprocess.Popen(argv, cwd=workspace, stdin=subprocess.DEVNULL,
                                stdout=out, stderr=err, start_new_session=True)
        try:
            code = proc.wait(timeout=config['timeout'])
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            # The wrapper may have stalled; only its trusted native evidence can
            # classify a genuine model deadline. Never manufacture a model zero.
            return missing('collector_error', detail='Harness exceeded the process timeout')
        finally:
            # Reap background writers before reading a supposedly final response.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    if code != 0:
        return missing('cli_error', exit_code=code)
    return normalise_custom(json.loads((attempt / 'response.json').read_text()))
