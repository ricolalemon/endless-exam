"""Publication summaries for audited code-and-web evaluations on 69 instances."""
from collections import defaultdict
import hashlib
import json
from pathlib import Path

import publication_data as P
from openceiling import FAMILIES, closed_gap, effective_frontier, frontier_ratio

SYSTEMS = {
    'astra_tools': ('astra-high-v1.json', 'astra_high', 'GPT-6 Astra high + tools'),
    'luna_tools': ('luna-high-v1.json', 'luna_high', 'GPT-5.6 Luna high + tools'),
}
LABELS = {'capset': 'cap set', 'labs': 'LABS', 'heilbronn': 'Heilbronn',
          'spherical_code': 'spherical codes', 'corners': 'corners',
          'matmul': 'matrix multiplication', 'degdiam': 'degree--diameter',
          'lineq': 'linear-equation-free', 'apfree_q': r'$\mathbb F_q^n$ AP-free',
          'mols': 'MOLS', 'schur': 'Schur', 'covering': 'covering',
          'shannon': 'Shannon', 'trifference': 'trifference'}


def load(sid='astra_tools'):
    filename, baseline, label = SYSTEMS[sid]
    source = P.ROOT / 'bench/results/tool-assisted' / filename
    data = json.loads(source.read_text())
    assert data['model'] == P.REGISTRY[baseline][1] and data['effort'] == 'high'
    assert hashlib.sha256((P.ROOT / data['reference_snapshot']).read_bytes()).hexdigest() == data['reference_snapshot_sha256']
    assert hashlib.sha256((P.ROOT / 'bench/data/formal_suite_v1.json').read_bytes()).hexdigest() == data['formal_suite_sha256']
    formal = {(c['tier'], c['family'], c['seed']): c for c in P.C.cases()}
    seen, rows, gap_records, cache = set(), [], [], {}
    for r in data['cases']:
        key = r['tier'], r['family'], r['seed']
        assert key in formal and key not in seen
        seen.add(key)
        case = formal[key]
        assert case['params'] == r['params']
        canonical = json.dumps(r['submission'], sort_keys=True, separators=(',', ':'))
        assert hashlib.sha256(canonical.encode()).hexdigest() == r['submission_sha256']
        assert r['verification']['agree'] and r['usage_complete']
        if r['submission'] is None:
            assert not r['valid'] and r['objective'] == 0
            assert r['finish_reason'] == 'resource_budget' and r['resource_result'] == 'oom-kill'
        ref = json.loads((P.ROOT / case['reference_path']).read_text())
        fam = FAMILIES[r['family']]
        reference, _ = effective_frontier(fam, r['params'], ref['naive'], ref['search'])
        assert reference == r['reference']
        assert bool(r['verification']['primary'][0]) == r['valid']
        assert r['verification']['primary'][1] == r['objective']
        assert r['verification']['independent'][:2] == [r['valid'], r['objective']]
        ratio, kind = frontier_ratio(fam, r['params'], ref['naive'], r['objective'], r['valid'], ref['search'])
        assert abs(ratio - r['reference_ratio']) < 1e-12
        assert (kind == 'literature') == (r['reference_type'] == 'published')
        old = P.strict(P.C.get_row(P.REGISTRY[baseline], case, cache))
        old_ratio, _ = frontier_ratio(fam, r['params'], ref['naive'], old['objective'], old['feasible'], ref['search'])
        gap_records.append((fam, r['params'], ref['naive'], r['objective'], r['valid'], ref['search']))
        rows.append({k: v for k, v in r.items() if k not in ('submission', 'prompt')}
                    | {'without_tools_ratio': old_ratio, 'without_tools_valid': bool(old['feasible'])})
    assert seen == set(formal) and len(rows) == 69
    panels = {}
    for name, kind in [('p1', 'published'), ('p2', 'construction')]:
        group = [r for r in rows if r['reference_type'] == kind]
        ratios = [r['reference_ratio'] for r in group]
        panels[name] = {'n': len(group), 'mean': sum(ratios) / len(group), 'ci': P.ci(ratios),
                        'above': sum(x > 1 + 1e-9 for x in ratios),
                        'equal': sum(abs(x - 1) < 1e-9 for x in ratios)}
    assert panels['p1']['n'] == 30 and panels['p2']['n'] == 39
    usage = {k: sum(r['usage'][k] for r in rows) for k in rows[0]['usage']}
    return {'id': sid, 'baseline_id': baseline, 'label': label, 'model': data['model'], 'effort': data['effort'],
            'track': 'tool-assisted', 'overall': P.overall_score([r['reference_ratio'] for r in rows]),
            **panels, 'valid': sum(r['valid'] for r in rows) / len(rows),
            'accepted': sum(r['valid'] for r in rows), **P.summarize_gaps(gap_records),
            'improved': sum(r['reference_ratio'] > r['without_tools_ratio'] + 1e-9 for r in rows),
            'tied': sum(abs(r['reference_ratio'] - r['without_tools_ratio']) <= 1e-9 for r in rows),
            'declined': sum(r['reference_ratio'] < r['without_tools_ratio'] - 1e-9 for r in rows),
            'without_tools_score': 100 * sum(r['without_tools_ratio'] for r in rows) / len(rows),
            'usage': usage, 'protocol': data['protocol'], 'cases': rows,
            'source': str(source.relative_to(P.ROOT)), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}


def load_all():
    systems = {sid: load(sid) for sid in SYSTEMS}
    first = next(iter(systems.values()))
    identities = [(r['instance_id'], r['params'], r['reference_type'], r['reference']) for r in first['cases']]
    for s in systems.values():
        assert [(r['instance_id'], r['params'], r['reference_type'], r['reference']) for r in s['cases']] == identities
        assert s['protocol'] == first['protocol']
    return systems


def generate():
    systems = load_all()
    data = systems['astra_tools']
    luna = systems['luna_tools']
    out = P.HERE / 'tables'
    paired = list(zip(data['cases'], luna['cases']))
    comparison = {'luna_above_astra': sum(l['reference_ratio'] > a['reference_ratio'] + 1e-9 for a, l in paired),
                  'equal': sum(abs(l['reference_ratio'] - a['reference_ratio']) <= 1e-9 for a, l in paired),
                  'luna_below_astra': sum(l['reference_ratio'] < a['reference_ratio'] - 1e-9 for a, l in paired)}
    (out / 'tool_publication_data.json').write_text(json.dumps(
        {'instances': 69, 'published_instances': 30, 'construction_instances': 39,
         'systems': systems, 'comparison': comparison}, indent=2) + '\n')
    tri = next(r for r in data['cases'] if r['family'] == 'trifference' and r['params']['n'] == 64)
    luna_both_valid = [r for r in luna['cases'] if r['without_tools_valid'] and r['valid']]
    macros = {'ToolScore': f"{data['overall']['score']:.2f}",
              'ToolPublishedHFR': f"{data['p1']['mean']:.3f}",
              'ToolConstructionRatio': f"{data['p2']['mean']:.3f}",
              'ToolPublishedMatched': data['p1']['equal'], 'ToolPublishedAbove': data['p1']['above'],
              'ToolConstructionAbove': data['p2']['above'], 'ToolImproved': data['improved'],
              'ToolTied': data['tied'], 'ToolValid': data['accepted'],
              'ToolGapClosedPct': f"{100 * data['gap_closed']['mean']:.1f}",
              'ToolTriWords': f"{tri['objective']:,}".replace(',', '{,}'),
              'ToolTriRatio': f"{tri['reference_ratio']:.0f}"}
    macros.update({'LunaToolScore': f"{luna['overall']['score']:.2f}",
                   'LunaToolFreeScore': f"{luna['without_tools_score']:.2f}",
                   'LunaToolPublishedHFR': f"{luna['p1']['mean']:.3f}",
                   'LunaToolConstructionRatio': f"{luna['p2']['mean']:.3f}",
                   'LunaToolPublishedMatched': luna['p1']['equal'],
                   'LunaToolConstructionAbove': luna['p2']['above'],
                   'LunaToolValid': luna['accepted'], 'LunaToolImproved': luna['improved'],
                   'LunaToolTied': luna['tied'], 'LunaToolDeclined': luna['declined'],
                   'LunaToolBeatsAstra': comparison['luna_above_astra'],
                   'LunaToolFreeValid': sum(r['without_tools_valid'] for r in luna['cases']),
                   'LunaBothValidN': len(luna_both_valid),
                   'LunaBothValidFreeQuality': f"{sum(r['without_tools_ratio'] for r in luna_both_valid) / len(luna_both_valid):.2f}",
                   'LunaBothValidToolQuality': f"{sum(r['reference_ratio'] for r in luna_both_valid) / len(luna_both_valid):.2f}",
                   'LunaToolGapClosedPct': f"{100 * luna['gap_closed']['mean']:.1f}"})
    (out / 'tool_numbers.tex').write_text('% Generated by tool_results.py.\n' + ''.join(
        rf'\newcommand{{\{name}}}{{{value}}}' + '\n' for name, value in macros.items()))
    groups = defaultdict(list)
    for row in data['cases']:
        groups[row['family_group']].append(row)
    luna_groups = defaultdict(list)
    for row in luna['cases']:
        luna_groups[row['family_group']].append(row)
    lines = [r'\begin{tabularx}{\linewidth}{@{}Xrrrrr@{}}', r'\toprule',
             r'& & \multicolumn{2}{c}{Astra high} & \multicolumn{2}{c}{Luna high} \\',
             r'\cmidrule(lr){3-4}\cmidrule(lr){5-6}',
             r'Family & Instances & Tool-free & Tools & Tool-free & Tools \\', r'\midrule']
    for fam, group in groups.items():
        old = sum(r['without_tools_ratio'] for r in group) / len(group)
        new = sum(r['reference_ratio'] for r in group) / len(group)
        lg = luna_groups[fam]
        lo = sum(r['without_tools_ratio'] for r in lg) / len(lg)
        ln = sum(r['reference_ratio'] for r in lg) / len(lg)
        lines.append(f"{LABELS.get(fam, fam)} & {len(group)} & {old:.3f} & {new:.3f} & {lo:.3f} & {ln:.3f}" + r' \\')
    lines += [r'\bottomrule', r'\end{tabularx}']
    (out / 'tool_families.tex').write_text('\n'.join(lines) + '\n')
    stats = [('Input tokens', 'inputTokens'), ('Cached input tokens (included above)', 'cachedInputTokens'),
             ('Output tokens', 'outputTokens'), ('Reasoning tokens (included above)', 'reasoningOutputTokens')]
    lines = [r'\begin{tabular}{@{}lrr@{}}', r'\toprule', r'Measure & Astra high & Luna high \\', r'\midrule']
    for label, key in stats:
        lines.append(f"{label} & {data['usage'][key]:,} & {luna['usage'][key]:,}".replace(',', r'{,}') + r' \\')
    lines += [r'\bottomrule', r'\end{tabular}']
    (out / 'tool_usage.tex').write_text('\n'.join(lines) + '\n')
    from appendix_gen import math_params
    triangles = {json.dumps(c['params'], sort_keys=True): i + 1
                 for i, c in enumerate(c for c in P.C.cases() if 'T' in c['params'])}
    header = (r'\toprule & & & \multicolumn{2}{c}{Astra high} & \multicolumn{2}{c}{Luna high} \\ '
              r'\cmidrule(lr){4-5}\cmidrule(lr){6-7} Family & Parameters & Ref. & Tool-free & Tools & Tool-free & Tools \\ \midrule ')
    lines = [r'\begin{longtable}{@{}P{.24\linewidth}P{.23\linewidth}rrrrr@{}}',
             r'\caption{Per-instance relative quality for GPT-6 Astra and GPT-5.6 Luna at high effort. P: published frontier; C: construction baseline. A dagger marks an evaluation assigned zero under the protocol in Section~\ref{sec:protocol}.}\label{tab:tool_instances}\\',
             header + r'\endfirsthead', header + r'\endhead',
             r'\bottomrule \endfoot']
    group_order = {name: i for i, name in enumerate(groups)}
    parameter_order = ('d', 'n', 'N', 'q', 'k', 'm', 'v', 't', 'a', 'b', 'cos100')
    displayed = sorted(data['cases'], key=lambda r: (
        group_order[r['family_group']], r['family'],
        tuple(r['params'][key] for key in parameter_order if key in r['params']), r['seed']))
    previous_group = None
    luna_cases = {r['instance_id']: r for r in luna['cases']}
    def cell(value, valid):
        return f"{value:.3f}" + (r'$^{\dagger}$' if not valid else '')
    for r in displayed:
        if previous_group is not None and r['family_group'] != previous_group:
            lines.append(r'\addlinespace[2pt]')
        previous_group = r['family_group']
        params = math_params({k: v for k, v in sorted(r['params'].items()) if k != 'T'})
        if 'T' in r['params']:
            params += rf", $T_{{{triangles[json.dumps(r['params'], sort_keys=True)]}}}$"
        label = LABELS.get(r['family_group'], r['family_group'])
        if r['family'] == 'heilbronn_shape':
            label += ' (triangle)'
        elif r['family'] == 'heilbronn':
            label += ' (square)'
        ref = 'P' if r['reference_type'] == 'published' else 'C'
        l = luna_cases[r['instance_id']]
        values = [cell(r['without_tools_ratio'], r['without_tools_valid']), cell(r['reference_ratio'], r['valid']),
                  cell(l['without_tools_ratio'], l['without_tools_valid']), cell(l['reference_ratio'], l['valid'])]
        lines.append(f"{label} & {params} & {ref} & " + ' & '.join(values) + r' \\')
    lines += [r'\end{longtable}']
    (out / 'tool_instances.tex').write_text('\n'.join(lines) + '\n')
    print(json.dumps({sid: {k: s[k] for k in ('overall', 'p1', 'p2', 'valid', 'headroom', 'improved', 'tied', 'declined', 'usage')}
                      for sid, s in systems.items()}, indent=2))


if __name__ == '__main__':
    generate()
