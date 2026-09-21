#!/usr/bin/env python3
"""Export version-1 prompts, verify constructions, and score a new submission."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import freeze_frontier
freeze_frontier.load('v1-trifference')
import formal_cohort as C
import run_ladder as L
from family_catalog import CORE_GROUPS, GROUP_LABELS, group_for
from openceiling import FAMILIES, anchor, effective_frontier, verify_with_timeout
from evaluation_outcomes import infrastructure_reason, require_scored

TOKEN_LIMIT = 128000


def suite():
    """The 69 unique paper instances and their frozen references."""
    result = []
    for c in C.cases():
        family, params = c['family'], c['params']
        ref = json.loads((ROOT / c['reference_path']).read_text())
        fam = FAMILIES[family]
        reference, published = effective_frontier(fam, params, ref['naive'], ref['search'])
        bound, kind = anchor(fam, params)
        identity = json.dumps([family, params], sort_keys=True, separators=(',', ':'))
        L.SIZE_TIER = c['tier']
        result.append({
            'call_id': f"{c['tier'].lower()}-{family}-{c['seed']}",
            'instance_id': family + '-' + hashlib.sha256(identity.encode()).hexdigest()[:12],
            'family': family, 'family_group': group_for(family), 'params': params,
            'tier': c['tier'], 'seed': c['seed'], 'sense': fam.sense,
            'reference': reference, 'reference_type': 'published' if published else 'construction',
            'anchor': bound, 'anchor_kind': kind, 'max_output_tokens': TOKEN_LIMIT,
            'verification_seconds': 60, 'system': L.SYSTEM,
            'prompt': L.prompt_for(family, fam, params, protocol='p1'),
        })
    assert len(result) == len({c['call_id'] for c in result}) == 69
    assert len({c['instance_id'] for c in result}) == 69
    return result


def verify(family, params, answer):
    if isinstance(answer, dict) and 'answer' in answer:
        answer = answer['answer']
    try:
        valid, objective, message = verify_with_timeout(FAMILIES[family], params, answer)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError) as error:
        valid, objective, message = False, 0, f'Malformed construction: {type(error).__name__}'
    return {'valid': bool(valid), 'objective': objective if valid else 0, 'message': message}


def score_record(case, record):
    require_scored(record)
    tokens = record.get('output_tokens')
    if tokens is not None and (type(tokens) is not int or tokens < 0):
        raise ValueError('output_tokens must be a nonnegative integer or null')
    if record.get('finish_reason', 'stop') != 'stop':
        checked = {'valid': False, 'objective': 0, 'message': 'Generation did not finish normally'}
    elif tokens is not None and tokens > TOKEN_LIMIT:
        checked = {'valid': False, 'objective': 0, 'message': 'Output exceeded the 128k token budget'}
    else:
        checked = verify(case['family'], case['params'], record.get('answer'))
    objective = checked['objective']
    ratio = ((objective / case['reference'] if case['sense'] == 'max'
              else case['reference'] / objective) if checked['valid'] and objective > 0 else 0.0)
    return {**{k: case[k] for k in ['call_id', 'instance_id', 'family', 'params', 'reference', 'reference_type']},
            **checked, 'ratio': ratio,
            'published_breakthrough': case['reference_type'] == 'published' and ratio > 1 + 1e-9}


def aggregate(rows, complete):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['instance_id']].append(row)
    if any(len(rs)!=1 for rs in grouped.values()):
        raise ValueError('Duplicate instance: the formal suite uses one response per instance')
    instances = [{
        'instance_id': key, 'family': rs[0]['family'], 'reference_type': rs[0]['reference_type'],
        'calls': 1, 'ratio': rs[0]['ratio'],
    } for key, rs in grouped.items()]
    mean = lambda xs: sum(xs) / len(xs) if xs else None
    overall = mean([r['ratio'] for r in instances])
    return {
        'version': '1', 'complete': complete, 'calls': len(rows), 'expected_calls': 69,
        'distinct_instances': len(instances), 'expected_instances': 69,
        'score' if complete else 'subset_score': 100 * overall if overall is not None else None,
        'published_hfr': mean([r['ratio'] for r in instances if r['reference_type'] == 'published']),
        'construction_reference_ratio': mean([r['ratio'] for r in instances if r['reference_type'] == 'construction']),
        'valid_fraction': mean([int(r['valid']) for r in rows]),
        'reference_parity_score': 100, 'score_capped': False,
        'instances': instances, 'calls_scored': rows,
    }


def score_submission(path, allow_partial=False):
    cases = {c['call_id']: c for c in suite()}
    records = {}
    with Path(path).open() as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f'Line {line_number}: expected a JSON object')
            call_id = record.get('call_id')
            if not isinstance(call_id, str) or call_id not in cases:
                raise ValueError(f'Line {line_number}: unknown call_id {call_id!r}')
            if call_id in records:
                raise ValueError(f'Duplicate call_id: {call_id}')
            if 'answer' not in record and record.get('finish_reason', 'stop') == 'stop':
                raise ValueError(f'{call_id}: provide answer or a failed finish_reason')
            records[call_id] = record
    if not records:
        raise ValueError('Submission contains no calls')
    unavailable={key:record for key,record in records.items() if infrastructure_reason(record)}
    missing = sorted((set(cases) - set(records)) | set(unavailable))
    if missing and not allow_partial:
        raise ValueError(f'Missing {len(missing)} of 69 calls; use --allow-partial for a labelled subset score')
    rows = [score_record(cases[key], record) for key, record in records.items() if key not in unavailable]
    report = aggregate(rows, not missing)
    report['missing_call_ids'] = missing
    report['infrastructure_failures'] = [
        {'call_id':key,'reason':infrastructure_reason(record),'ratio':None}
        for key,record in sorted(unavailable.items())]
    return report


def emit(value, output=None):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if output:
        Path(output).write_text(text)
    else:
        print(text, end='')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('families', help='List the fourteen headline families')
    export = commands.add_parser('export', help='Export the 69 unique formal instances as JSONL')
    export.add_argument('--output', type=Path, required=True)
    prompt = commands.add_parser('prompt', help='Show the prompt and metadata of one formal call')
    prompt.add_argument('call_id')
    check = commands.add_parser('verify', help='Verify a construction without making a model call')
    target = check.add_mutually_exclusive_group(required=True)
    target.add_argument('--call-id')
    target.add_argument('--family', choices=sorted(FAMILIES))
    check.add_argument('--params', help='JSON parameter object, required with --family')
    check.add_argument('--answer', type=Path, required=True)
    score = commands.add_parser('score', help='Verify and score a JSONL submission')
    score.add_argument('submission', type=Path)
    score.add_argument('--output', type=Path)
    score.add_argument('--allow-partial', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'families':
            emit([{'family': g, 'name': GROUP_LABELS[g], 'task_variants': list(fs)} for g, fs in CORE_GROUPS.items()])
        elif args.command == 'export':
            args.output.write_text(''.join(json.dumps(c, ensure_ascii=False, allow_nan=False) + '\n' for c in suite()))
            print(f'Exported 69 calls / 69 distinct instances to {args.output}')
        elif args.command == 'prompt':
            found = next((c for c in suite() if c['call_id'] == args.call_id), None)
            if found is None:
                raise ValueError(f'Unknown call_id: {args.call_id}')
            emit(found)
        elif args.command == 'verify':
            answer = json.loads(args.answer.read_text())
            if args.call_id:
                case = next((c for c in suite() if c['call_id'] == args.call_id), None)
                if case is None:
                    raise ValueError(f'Unknown call_id: {args.call_id}')
                emit(score_record(case, {'answer': answer}))
            else:
                if not args.params:
                    raise ValueError('--params is required with --family')
                params = json.loads(args.params)
                if not isinstance(params, dict):
                    raise ValueError('--params must be a JSON object')
                emit(verify(args.family, params, answer))
        else:
            emit(score_submission(args.submission, args.allow_partial), args.output)
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.exit(2, f'Error: {error}\n')


if __name__ == '__main__':
    main()
