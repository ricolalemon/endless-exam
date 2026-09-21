#!/usr/bin/env python3
"""Index the 966 published outcomes and their saved responses; no model calls."""
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'bench'), str(ROOT / 'bench/paper')]
import publication_data as P
import tool_results as T
import exam


def generate():
    cases = P.C.cases()
    identities = {(c['family'], json.dumps(c['params'], sort_keys=True)): c['instance_id']
                  for c in exam.suite()}
    refs, selected = P.load_formal()
    hashes, locations, records = {}, {}, []

    def digest(path):
        if path not in hashes:
            hashes[path] = hashlib.sha256(path.read_bytes()).hexdigest()
        return hashes[path]

    for sid in P.ORDER:
        system = P.REGISTRY[sid]
        for case in cases:
            key = P.case_key(case)
            row = selected[system[1], system[3] + '#A3'][key]
            ref = refs[key]
            family = P.FAMILIES[case['family']]
            reference, published = P.effective_frontier(family, case['params'], ref['naive'], ref['search'])
            ratio, _ = P.frontier_ratio(family, case['params'], ref['naive'], row['objective'], row['feasible'], ref['search'])
            source, configuration = P.C.source_path(system, case)
            if source not in locations:
                locations[source] = {(r['family'], r['seed']): i for i, r in
                                     enumerate(map(json.loads, source.read_text().splitlines()), 1)}
            records.append({
                'configuration_id': sid, 'configuration': system[2], 'track': 'tool-free',
                'instance_id': identities[case['family'], json.dumps(case['params'], sort_keys=True)],
                'family': case['family'], 'params': case['params'],
                'reference_type': 'published' if published else 'construction', 'reference': reference,
                'valid': bool(row['feasible']), 'objective': row['objective'], 'relative_quality': ratio,
                'source_file': str(source.relative_to(ROOT)), 'source_sha256': digest(source),
                'source_line': locations[source][case['family'], case['seed']],
                'source_configuration': configuration,
            })

    for sid, data in T.load_all().items():
        source = ROOT / data['source']
        for index, row in enumerate(data['cases']):
            records.append({
                'configuration_id': sid, 'configuration': data['label'], 'track': 'tool-assisted',
                'instance_id': row['instance_id'], 'family': row['family'], 'params': row['params'],
                'reference_type': row['reference_type'], 'reference': row['reference'],
                'valid': row['valid'], 'objective': row['objective'], 'relative_quality': row['reference_ratio'],
                'source_file': str(source.relative_to(ROOT)), 'source_sha256': digest(source),
                'source_pointer': f'/cases/{index}',
            })

    assert len(records) == 14 * 69
    assert len({(r['configuration_id'], r['instance_id']) for r in records}) == len(records)
    out = ROOT / 'bench/results/published'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'index.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))
    fields = ['configuration_id', 'configuration', 'track', 'instance_id', 'family', 'params',
              'reference_type', 'reference', 'valid', 'objective', 'relative_quality',
              'source_file', 'source_sha256', 'source_line', 'source_pointer', 'source_configuration']
    with (out / 'index.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows({**r, 'params': json.dumps(r['params'], sort_keys=True)} for r in records)
    print(f'Indexed {len(records)} outcomes across 14 configurations and 69 instances.')


if __name__ == '__main__':
    generate()
