"""Reconstruct selected published Schur constructions on one fixed reference.

Literature illustration only: these are not model runs or changes to version 1.
The 2021 entry dates the cited exposition, not a claim of first discovery.
"""
import json
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASELINE = 3 * 1680 + 1
MILESTONES = [
    {"label": "Recursive extension", "citation": "fredricksen2000schur",
     "formula": r"3\cdot1680+1", "value": 3 * 1680 + 1,
     "source": "https://www.combinatorics.org/ojs/index.php/eljc/article/view/v7i1r32",
     "evidence": "p. 1 Eq. (1), S(k)>=3S(k-1)+1; p. 2, S(7)>=1680. The k=8 value is derived here."},
    {"label": "Rowley template", "citation": "rowley2021templates",
     "formula": r"33\cdot160+6", "value": 33 * 160 + 6,
     "source": "https://arxiv.org/abs/2107.03560",
     "evidence": "p. 4 gives S(k+3)>=33S(k)+6; use the published S(5)>=160. Year is the cited exposition."},
    {"label": "Shifted template", "citation": "bengone2026schur",
     "formula": r"10\cdot536+2", "value": 10 * 536 + 2,
     "source": "https://arxiv.org/abs/2607.15034",
     "evidence": "Section IV explicitly derives S(8)>=10*536+2=5362."},
]


def main():
    rows = []
    for m in MILESTONES:
        ratio = Fraction(m["value"], BASELINE)
        rows.append(dict(m, family="schur", parameters={"k": 8},
                         historical_reference=BASELINE, ratio=float(ratio),
                         exact_ratio=f"{ratio.numerator}/{ratio.denominator}",
                         breakthrough=int(m["value"] > BASELINE)))
    assert [r["value"] for r in rows] == [5041, 5286, 5362]
    assert [r["breakthrough"] for r in rows] == [0, 1, 1]
    assert rows[1]["ratio"] < rows[2]["ratio"]
    table = [r"\begin{tabular}{@{}lrrr@{}}", r"\toprule",
             r"Published construction & $N$ & $N/5041$ & $\mathbf{1}\{N>5041\}$ \\",
             r"\midrule"]
    for r in rows:
        table.append(f"{r['label']}~\\citep{{{r['citation']}}} & {r['value']:,} & "
                     f"{r['ratio']:.3f} & {r['breakthrough']}" + r" \\")
    table += [r"\bottomrule", r"\end{tabular}"]
    (HERE/'tables/historical_progress.tex').write_text('\n'.join(table)+'\n')
    (HERE/'tables/historical_progress.json').write_text(json.dumps({
        "kind": "literature_reconstruction", "model_calls": 0,
        "scope": "Selected published constructions at fixed k=8; not an exhaustive record chronology.",
        "verification": "Construction existence follows from cited papers; this script checks scoring arithmetic, not the original colorings.",
        "changes_to_frozen_frontiers": False, "rows": rows}, indent=2)+'\n')
    print('Historical Schur illustration:', [(r['value'], round(r['ratio'], 3)) for r in rows])


if __name__ == '__main__':
    main()
