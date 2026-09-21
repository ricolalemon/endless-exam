"""Explicit publication replacements, retaining every historical result row."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'bench/data/result_replacements.json'


def manifest(root=ROOT):
    path = Path(root) / MANIFEST
    return json.loads(path.read_text()) if path.exists() else {'replacements': [], 'references': []}


def source_for(model, config, tier, family, seed, root=ROOT):
    """Return the selected file and actual configuration, including failed replacements."""
    matches = [r for r in manifest(root)['replacements']
               if (r['model'], r['source_config'], r['tier'], r['family'], r['seed'])
               == (model, config + '#' + tier, tier, family, seed)]
    if len(matches) > 1:
        raise ValueError('Ambiguous replacement selection')
    if matches:
        return Path(root) / matches[0]['result_path'], matches[0]['config']
    return Path(root) / f"bench/results/{model.replace('/', '_')}-{config}#{tier}.jsonl", config + '#' + tier


def reference_for(tier, family, seed, root=ROOT):
    matches = [r for r in manifest(root)['references']
               if (r['tier'], r['family'], r['seed']) == (tier, family, seed)]
    if len(matches) > 1:
        raise ValueError('Ambiguous reference selection')
    path = matches[0]['reference_path'] if matches else f'bench/refs/{tier}-{family}-{seed}-t10.json'
    return Path(root) / path


def parameters_for(tier, family, seed, original, root=ROOT):
    for entry in manifest(root)['references']:
        if (entry['tier'], entry['family'], entry['seed']) == (tier, family, seed):
            return json.loads((Path(root)/entry['reference_path']).read_text())['params']
    return original


def overlay(tier, ref, rows, root=ROOT):
    """Select matching references and new outcomes under the model's display group."""
    data = manifest(root)
    for entry in data['references']:
        if entry['tier'] != tier:
            continue
        frozen = json.loads((Path(root) / entry['reference_path']).read_text())
        key = entry['family'], entry['seed']
        ref[key] = {**frozen, 'model': 'search', 'tier': tier,
                    'family': key[0], 'seed': key[1], 'objective': frozen['search']}
    for entry in data['replacements']:
        if entry['tier'] != tier:
            continue
        key = entry['family'], entry['seed']
        new = rows.get((entry['model'], entry['config']), {}).get(key)
        if new is None:
            raise ValueError(f"Missing activated replacement: {entry['case_id']}")
        if new['params'] != ref[key]['params']:
            raise ValueError(f"Replacement/reference mismatch: {entry['case_id']}")
        rows.setdefault((entry['model'], entry['source_config']), {})[key] = new
