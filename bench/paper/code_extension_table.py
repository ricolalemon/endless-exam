"""Present the smaller trifference instances from the selected code responses."""
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from openceiling import FAMILIES
import publication_data as P


def number(n):
    if n<1000000:return str(n)
    exponent=len(str(n))-1
    return rf"${n/10**exponent:.3f}\times10^{{{exponent}}}$"


def selected_cases():
    manifest=json.loads((HERE.parent/'results/pilots/astra-medium-codes-A3/manifest.json').read_text())
    values=[]
    for case in manifest['cases']:
        f,s=case['family'],case['seed'];p=case['params']
        selected={**case,'tier':'A3','block':'core12'}
        r=P.C.get_row(P.REGISTRY['astra_medium'],selected)
        if r is None:raise ValueError(f'Missing preliminary Astra evaluation: {f}:{s}')
        r=P.strict(r)
        if r['params']!=p:raise ValueError('parameter mismatch')
        ref=max(case['naive'],case['search10']);obj=r['objective'] if r['feasible'] else 0
        values.append({'family':f,'seed':s,'params':p,'reference':ref,'objective':obj,'valid':r['feasible'],'ratio':obj/ref,
                       'normalized':FAMILIES[f].law(p,obj) if r['feasible'] else None,
                       'source':P.selected_source('astra_medium','A3',f,s,'core')})
    assert len(values)==8
    return values


def main():
    values=selected_cases()
    shown=[case for case in values if case['family']=='trifference']
    lines=[r'\begin{center}\begin{minipage}{\linewidth}\centering\small',r'\begin{tabular}{@{}rrrrrc@{}}',r'\toprule',
           r'Length $n$ & Separation $m$ & Reference & Model & \shortstack{Relative\\quality} & Valid \\',r'\midrule']
    for case in shown:
        p=case['params'];ref=case['reference']
        cells=[number(case['objective']),f"{case['ratio']:.3f}",'yes' if case['valid'] else 'no']
        lines.append(' & '.join([str(p['n']),str(p['m']),number(ref),*cells])+r' \\')
    lines += [r'\bottomrule',r'\end{tabular}',
              r'\captionof{table}{GPT-6 Astra at medium effort on four smaller trifference instances. Code sizes are compared with construction baselines.}',
              r'\label{tab:codes}',r'\end{minipage}\end{center}']
    (HERE/'tables/code_extension.tex').write_text('\n'.join(lines)+'\n')
    (HERE/'tables/code_extension_data.json').write_text(json.dumps({'cases':values},indent=2)+'\n')
    print(f'wrote code_extension.tex: {len(shown)} trifference instances; all {len(values)} selected code responses retained in the data')

if __name__=='__main__':main()
