"""Generate the certified-scale results and verifier performance table."""
import json
from pathlib import Path
import publication_data as P
HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'results/pilots/astra-medium-trifference-scaling'


def selected_cases():
    cases=[]
    for c in P.C.cases():
        if c['family']!='trifference':continue
        row=P.C.get_row(P.REGISTRY['astra_medium'],c)
        if row is None:raise ValueError(f"Missing Astra medium trifference evaluation: {c['tier']}")
        row=P.strict(row)
        reference=json.loads((P.ROOT/c['reference_path']).read_text())['search']
        cases.append({'tier':c['tier'],'params':c['params'],'reference':reference,
                      'objective':row['objective'],'ratio':row['objective']/reference,
                      'latency_s':row['latency_s'],'valid':row['feasible'],
                      'source':P.selected_source('astra_medium',c['tier'],'trifference',c['seed'],'codes')})
    assert len(cases)==4
    return sorted(cases,key=lambda c:c['params']['n'])


def main():
    cases=selected_cases();profile=json.loads((OUT/'verifier_profile.json').read_text())
    lines=[r'\begin{center}\begin{minipage}{\linewidth}\centering\small',r'\begin{tabular}{@{}lrrrrr@{}}',r'\toprule',
           r'instance & length & reference words & verified words & \shortstack{Relative\\quality} & generation (s) \\',r'\midrule']
    for c in cases:
        lines.append(f"{c['tier']} & {c['params']['n']} & {c['reference']:,} & {c['objective']:,} & {c['ratio']:.3f} & {c['latency_s']:.1f}"+r' \\')
    lines += [r'\bottomrule',r'\end{tabular}',r'\captionof{table}{GPT-6 Astra at medium effort on four trifference lengths. The evaluator checks each submitted construction and computes its exact size. Ratios use the construction baselines; invalid or budget-exhausted responses score zero.}',r'\label{tab:trifference_scaling}',r'\end{minipage}\end{center}']
    (HERE/'tables/trifference_scaling.tex').write_text('\n'.join(lines)+'\n')
    (HERE/'tables/trifference_scaling_data.json').write_text(json.dumps({'cases':cases},indent=2)+'\n')
    lines=[r'\begin{center}\begin{minipage}{\linewidth}\centering\small',r'\begin{tabular}{@{}lrrr@{}}',r'\toprule',
           r'test construction & words & primary (s) & independent (s) \\',r'\midrule']
    for name,label in [('linear-rank-12','rank 12, $m=1$'),('linear-rank-12-m3','rank 12, $m=3$'),('reference-1024','concatenation, $n=1024$')]:
        c=next(v for v in profile if v['name']==name);M=c['objective']
        value=f'{M:,}' if M<10**10 else f'${M/10**(len(str(M))-1):.3f}\\times10^{{{len(str(M))-1}}}$'
        fmt=lambda x:f'{x:.2f}' if x>=.01 else '$<0.01$'
        lines.append(f"{label} & {value} & {fmt(c['primary_s'])} & {fmt(c['secondary_s'])}"+r' \\')
    lines += [r'\bottomrule',r'\end{tabular}',r'\captionof{table}{Measured verification times for reference constructions. Both implementations check the certificate and exact code size. The length-1024 example illustrates verification at a scale beyond the evaluated model answers.}',r'\label{tab:trifference_verifier}',r'\end{minipage}\end{center}']
    (HERE/'tables/trifference_verifier.tex').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':main()
