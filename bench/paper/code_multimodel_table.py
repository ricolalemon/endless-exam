"""Code-family breakdown for all complete formal configurations."""
import json
from pathlib import Path
from publication_data import ORDER, REGISTRY, code_data
HERE = Path(__file__).resolve().parent

def ratio(x): return '$<0.001$' if 0 < x < .001 else f'{x:.3f}'
def count(x):
    if x < 10**6: return f'{x:,}'
    power = len(str(x))-1
    return f'${x/10**power:.2f}\\times10^{{{power}}}$'

def main():
    cases, rows = code_data();index = {(r['system'], r['tier'], r['family'], r['seed']): r for r in rows}
    table = [r'\begin{tabular}{@{}lrrrrr@{}}', r'\toprule',
             r'configuration & \shortstack{Shannon\\relative quality} & valid & \shortstack{Trifference\\relative quality} & valid & words at $n=192$ \\', r'\midrule']
    # Models on rows avoids narrow model columns in the per-instance table.
    detail = [r'\begin{tabular}{@{}lrrrrrrrr@{}}', r'\toprule',
              r' & \multicolumn{4}{c}{Shannon $(q,d)$} & \multicolumn{4}{c}{trifference length $n$} \\',
              r'configuration & $(7,24)$ & $(7,40)$ & $(9,48)$ & $(9,64)$ & 64 & 96 & 144 & 192 \\', r'\midrule']
    for sid in ORDER:
        selected = [index[sid, c['tier'], c['family'], c['seed']] for c in cases]
        cells = []
        for family in ('shannon', 'trifference'):
            group = [r for r in selected if r['family'] == family]
            assert len(group) == 4
            cells.extend([ratio(sum(r['ratio'] for r in group)/4), f"{sum(r['valid'] for r in group)}/4"])
        cells.append(count(selected[-1]['objective']))
        table.append(' & '.join([REGISTRY[sid][2], *cells]) + r' \\')
        detail.append(' & '.join([REGISTRY[sid][2], *[ratio(r['ratio']) + ('' if r['valid'] else r'$^\dagger$') for r in selected]]) + r' \\')
    for name, lines in [('code_multimodel', table), ('code_multimodel_detail', detail)]:
        (HERE / f'tables/{name}.tex').write_text('\n'.join(lines + [r'\bottomrule', r'\end{tabular}']) + '\n')
    print(f'wrote code tables: {len(cases)*len(ORDER)} outcomes, {len(ORDER)} configurations')

if __name__ == '__main__': main()
