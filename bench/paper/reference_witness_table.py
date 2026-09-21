"""Build the appendix summary from the complete, verified reference library."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DIRECTORY = ROOT/'bench/data/reference_witnesses'


def main():
    index_path = DIRECTORY/'index.json'
    index = json.loads(index_path.read_text())
    checks = json.loads((DIRECTORY/'verification.json').read_text())
    assert checks['index_sha256']==hashlib.sha256(index_path.read_bytes()).hexdigest()
    assert checks['all_dual_verified'] and checks['all_ratios_one']
    assert checks['distinct_instances']==len(index['records'])==69
    assert checks['token_encodings']==['cl100k_base','o200k_base']
    for r in index['records']:
        assert hashlib.sha256((ROOT/r['witness']).read_bytes()).hexdigest()==r['sha256']
    rows=[]
    for kind,label in [('published','Published frontiers'),('construction','Construction baselines')]:
        g=checks['groups'][kind];assert g['verified']==g['instances']
        rows.append(f"{label} & {g['verified']} / {g['instances']} & {g['max_output_tokens']:,}"+r' \\')
    maximum=max(g['max_output_tokens'] for g in checks['groups'].values())
    assert maximum<=128000
    table=[r'\begin{center}\small',r'\begin{tabular}{@{}lrr@{}}',r'\toprule',
           r'Reference group & Verified instances & Largest answer (tokens) \\',r'\midrule',
           *rows,r'\midrule',rf'\textbf{{Total}} & \textbf{{69 / 69}} & \textbf{{{maximum:,}}}'+r' \\',r'\bottomrule',r'\end{tabular}',
           r'\captionof{table}{Reference constructions for all 69 instances. Each object attains relative quality $1$ and passes both verifiers within 60 seconds. Token counts use the larger of \texttt{cl100k\_base} and \texttt{o200k\_base} for the serialised answer.}\label{tab:reference_witnesses}',r'\end{center}']
    (HERE/'tables/reference_witnesses.tex').write_text('\n'.join(table)+'\n')
    print('Reference coverage: 69/69; largest answer:',maximum,'tokens')


if __name__=='__main__':main()
