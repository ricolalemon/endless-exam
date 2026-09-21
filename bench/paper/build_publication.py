"""Rebuild the formal-cohort manuscript and figures; never launch model calls."""
from pathlib import Path
import argparse
import re
import shutil
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / 'bench/paper'
LOG = ROOT / 'tmp/pdfs/build'
STEPS = [
    ('visual_theme.py', []),
    ('publication_data.py', []), ('tool_results.py', []), ('gap_closed_table.py', []), ('tables.py', []), ('manuscript_numbers.py', []),
    ('fig_score_tokens.py', ['--paper']),
    ('reference_witness_table.py', []),
    ('historical_progress.py', []), ('fig_framework.py', []),
    ('code_extension_table.py', []), ('trifference_scaling_table.py', []),
    ('code_multimodel_table.py', []), ('publication_diagnostics.py', []),
    ('appendix_gen.py', []), ('search_evidence.py', []), ('selection_comparison.py', []),
    ('figs.py', []), ('fig_ladder.py', []), ('ladder_table.py', []),
    ('fig_code_scale.py', []), ('fig_code_scale.py', ['--bounds']), ('fig_shannon_bounds.py', []),
    ('appendix_redesign.py', []),
]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--edition', choices=['iclr', 'arxiv'], default='iclr')
    parser.add_argument('--max-main-pages', type=int,
                        help='Working-draft page limit; ICLR defaults to nine, arXiv has no default limit')
    args = parser.parse_args()
    stem = 'arxiv' if args.edition == 'arxiv' else 'main'
    LOG.mkdir(parents=True,exist_ok=True)
    for i,(name,step_args) in enumerate(STEPS):
        dest=LOG/f'{i:02d}-{Path(name).stem}.txt'
        print('Building',name,*step_args,flush=True)
        with dest.open('w') as log:
            subprocess.run([sys.executable,str(HERE/name),*step_args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        if 'FAILED ' in dest.read_text():raise RuntimeError(f'Figure generation failed: {dest}')
    with (LOG/'tectonic.txt').open('w') as log:
        subprocess.run(['tectonic','-X','compile',str(HERE/f'{stem}.tex'),'--keep-intermediates'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    aux=(HERE/f'{stem}.aux').read_text()
    match=re.search(r'\\newlabel\{page:mainend\}\{\{[^}]+\}\{(\d+)\}',aux)
    limit=args.max_main_pages if args.max_main_pages is not None else (9 if args.edition=='iclr' else None)
    assert match,'main-text page marker is missing'
    if limit is not None:assert int(match[1])<=limit,f'main text exceeds {limit} pages'
    filename = 'endless-exam-arxiv.pdf' if args.edition == 'arxiv' else 'endless-exam.pdf'
    output=ROOT/'output/pdf'/filename;output.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(HERE/f'{stem}.pdf',output)
    print('Built',output,'; main text:',match[1],'pages. Render and inspect before distribution.')

if __name__=='__main__':main()
