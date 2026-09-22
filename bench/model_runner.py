"""Resumable tool-free collection with immutable attempt journals."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

import model_adapters as A


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


@contextmanager
def run_lock(root):
    with (root / 'run.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another controller holds this run directory') from None
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def add_parser(commands):
    p = commands.add_parser('run', help='Collect tool-free answers with an API or your own harness')
    p.add_argument('--adapter', choices=['chat-completions', 'responses', 'command'], default='chat-completions')
    p.add_argument('--model', required=True)
    p.add_argument('--effort')
    p.add_argument('--base-url', default='https://api.openai.com/v1')
    p.add_argument('--api-key-env', default='OPENAI_API_KEY', help='Environment variable name; empty for an unauthenticated local server')
    p.add_argument('--token-parameter', choices=['max_completion_tokens', 'max_tokens'], default='max_completion_tokens')
    p.add_argument('--options', type=Path, help='JSON object of provider-specific generation settings')
    p.add_argument('--command-file', type=Path, help='JSON argv array with {request} and {response} paths')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--timeout', type=float, default=7200, help='Transport/process timeout in seconds; not a scored model deadline')
    p.add_argument('--retries', type=int, default=4, help='Additional HTTP attempts for transient transport failures')
    p.add_argument('--only', nargs='+', help='Subset of call IDs; results are labelled partial')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--retry-infrastructure', action='store_true', help='With --resume, recollect terminal infrastructure failures')
    p.add_argument('--dry-run', action='store_true', help='Write manifest/request previews without invoking a model or harness')


def configuration(args):
    if args.workers < 1 or args.retries < 0 or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError('workers/timeout must be positive and retries nonnegative')
    if args.retry_infrastructure and not args.resume:
        raise ValueError('--retry-infrastructure requires --resume')
    options = json.loads(args.options.read_text()) if args.options else {}
    if not isinstance(options, dict):
        raise ValueError('--options must contain a JSON object')
    argv = json.loads(args.command_file.read_text()) if args.command_file else None
    if args.adapter == 'command':
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise ValueError('--command-file must contain a nonempty JSON argv array')
        if not all(any(field in x for x in argv) for field in ('{request}', '{response}')):
            raise ValueError('Command argv must include {request} and {response}')
    elif argv is not None:
        raise ValueError('--command-file is only used by --adapter command')
    parsed = urlsplit(args.base_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use a base URL without credentials, query or fragment')
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in {'localhost', '127.0.0.1', '::1'}):
        raise ValueError('Use HTTPS, or HTTP on a loopback host')
    return {'adapter': args.adapter, 'model': args.model, 'effort': args.effort,
            'base_url': args.base_url.rstrip('/'), 'api_key_env': args.api_key_env,
            'token_parameter': args.token_parameter, 'options': options, 'argv': argv,
            'timeout': args.timeout, 'retries': args.retries, 'workers': args.workers}


def history(root, cases):
    """Completed outcomes survive a crash between the journal and summary writes."""
    selected, failed, attempts = {}, {}, []
    for case in cases:
        key = case['call_id']
        for path in sorted((root / 'attempts' / key).glob('*')):
            if not path.is_dir():
                continue
            if not (path / 'outcome.json').is_file():
                raise ValueError(f'Incomplete attempt blocks collection: {path}. Inspect saved evidence before recovery.')
            row = json.loads((path / 'outcome.json').read_text())
            if key in selected:
                raise ValueError(f'Attempt exists after a scored outcome: {key}')
            attempts.append(row)
            if row['scored']:
                selected[key] = row
                failed.pop(key, None)
            else:
                failed[key] = row
    return selected, failed, attempts


def collect(case, config, root):
    parent = root / 'attempts' / case['call_id']
    parent.mkdir(parents=True, exist_ok=True)
    count = len(list(parent.iterdir()))
    for retry in range(config['retries'] + 1):
        attempt = parent / f'{count + retry + 1:04d}'
        attempt.mkdir()
        started = now()
        A.write_json(attempt / 'started.json', {'call_id': case['call_id'], 'started_at': started,
                     'messages_sha256': digest(A.messages(case))})
        start = time.monotonic()
        try:
            row = (A.call_command if config['adapter'] == 'command' else A.call_api)(case, config, attempt)
        except Exception as error:
            # Leave raw evidence and a terminal collector failure; no automatic repeat.
            row = A.missing('collector_error', exception_type=type(error).__name__)
        row.update(call_id=case['call_id'], attempt=str(attempt.relative_to(root)),
                   started_at=started, completed_at=now(), seconds=time.monotonic() - start)
        row['output_tokens'] = row.get('usage', {}).get('output_tokens')
        A.write_json(attempt / 'outcome.json', row)
        if row['scored'] or not row.get('retryable') or retry == config['retries']:
            return row
        time.sleep(min(2 ** retry, 30))


def reports(root, cases, state):
    import exam
    selected, failed, attempts = history(root, cases)
    rows = [selected.get(c['call_id'], failed.get(c['call_id'])) for c in cases]
    rows = [r for r in rows if r is not None]
    path = root / 'answers.jsonl'
    tmp = path.with_suffix('.tmp')
    tmp.write_text(''.join(json.dumps(r, ensure_ascii=False, allow_nan=False) + '\n' for r in rows))
    tmp.replace(path)
    # Verifiers use a signal deadline, so they run here on the main thread.
    report = exam.score_submission(path, allow_partial=True) if rows else exam.aggregate([], False)
    A.write_json(root / 'scores.json', report)
    usage = {'attempts': len(attempts), 'scored_outcomes': len(selected),
             'unknown_usage_attempts': sum(not r.get('usage_complete', False) for r in attempts)}
    for key in ('input_tokens', 'output_tokens', 'reasoning_tokens'):
        values = [r.get('usage', {}).get(key) for r in attempts]
        usage[key] = {'reported_total': sum(v for v in values if v is not None),
                      'unknown_attempts': sum(v is None for v in values),
                      'complete': all(v is not None for v in values) and
                                  all(r.get('usage_complete', False) for r in attempts)}
    A.write_json(root / 'usage.json', usage)
    A.write_json(root / 'status.json', {'state': state, 'updated_at': now(), 'selected': len(selected),
                 'requested': len(cases), 'infrastructure_missing': sorted(failed),
                 'untouched': [c['call_id'] for c in cases if c['call_id'] not in selected | failed]})
    return report


def run(args):
    import exam
    config = configuration(args)
    all_cases = exam.suite()
    known = {c['call_id'] for c in all_cases}
    if args.only and (set(args.only) - known or len(args.only) != len(set(args.only))):
        raise ValueError('--only contains unknown or duplicate call IDs')
    cases = [c for c in all_cases if not args.only or c['call_id'] in args.only]
    if config['adapter'] != 'command':
        for case in cases:
            A.request_body(case, config)  # Validate before any requests.
    manifest = {'schema_version': 1, 'track': 'tool-free', 'config': config,
                'suite_sha256': digest(all_cases), 'call_ids': [c['call_id'] for c in cases],
                'runner_sha256': digest([Path(p).read_text() for p in
                                         (__file__, A.__file__, exam.__file__)]),
                'command_file_hashes': {arg: hashlib.sha256(Path(arg).read_bytes()).hexdigest()
                                       for arg in (config['argv'] or [])
                                       if Path(arg).is_absolute() and Path(arg).is_file()},
                'messages_sha256': {c['call_id']: digest(A.messages(c)) for c in cases}}
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with run_lock(root):
        existing = root / 'manifest.json'
        if existing.exists():
            if not args.resume:
                raise ValueError('Output already has a manifest; use --resume with identical settings')
            if json.loads(existing.read_text()) != manifest:
                raise ValueError('Run settings, prompts or runner code differ from the saved manifest')
        elif args.resume:
            raise ValueError('--resume requires an existing manifest')
        else:
            if any(p.name != 'run.lock' for p in root.iterdir()):
                raise ValueError('New run requires an empty output directory')
            A.write_json(existing, manifest)
        if args.dry_run:
            A.write_json(root / 'request-preview.json',
                         A.request_body(cases[0], config) if config['adapter'] != 'command' else
                         {'messages': A.messages(cases[0]), 'track': 'tool-free'})
            return {'state': 'dry_run', 'calls': len(cases), 'output': str(root), 'model_calls': 0}
        selected, failed, _ = history(root, cases)
        unresolved = [key for key, row in failed.items() if row['finish_reason'] not in
                      {'transport_error', 'server_error', 'rate_limit', 'quota'}]
        if unresolved:
            reports(root, cases, 'needs_attention')
            raise ValueError('Saved collector/protocol failures require evidence repair, not regeneration: ' +
                             ', '.join(unresolved))
        if failed and not args.retry_infrastructure:
            reports(root, cases, 'needs_attention')
            raise ValueError('Infrastructure failures remain; inspect attempts, then use --resume --retry-infrastructure')
        pending = [c for c in cases if c['call_id'] not in selected]
        if pending and config['adapter'] != 'command' and config['api_key_env'] and not os.environ.get(config['api_key_env']):
            raise ValueError(f"Set the {config['api_key_env']} environment variable; its value is not written to logs")
        A.write_json(root / 'status.json', {'state': 'running', 'started_at': now(),
                     'selected': len(selected), 'requested': len(cases), 'pid': os.getpid()})
        stopped = False
        iterator = iter(pending)
        with ThreadPoolExecutor(max_workers=config['workers']) as pool:
            active = {}
            def fill():
                while not stopped and len(active) < config['workers']:
                    case = next(iterator, None)
                    if case is None:
                        break
                    active[pool.submit(collect, case, config, root)] = case['call_id']
            fill()
            while active:
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    key = active.pop(future)
                    outcome = future.result()
                    stopped = stopped or not outcome['scored']
                    print(f"{key}: {outcome['finish_reason']}", flush=True)
                fill()
                A.write_json(root / 'status.json', {'state': 'draining' if stopped else 'running',
                             'updated_at': now(), 'active': list(active.values()), 'pid': os.getpid()})
        result = reports(root, cases, 'needs_attention' if stopped else 'complete')
        if stopped:
            raise ValueError(f'Collection paused after infrastructure failure; inspect {root / "status.json"}')
        return {'state': 'complete', 'calls': result['calls'], 'complete_suite': result['complete'],
                'output': str(root), 'score' if result['complete'] else 'subset_score':
                result.get('score', result.get('subset_score'))}
