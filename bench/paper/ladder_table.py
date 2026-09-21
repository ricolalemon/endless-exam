#!/usr/bin/env python3
"""Appendix table of the size ladder: per family and level, the instance, the frontier, the expert zero and every
configuration's ratio to the frontier (mean of the repeats; the count of valid repeats in brackets).

    ~/.venvs/efpaper/bin/python bench/paper/ladder_table.py      -> bench/paper/tables/ladder_table.tex
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "bench")); sys.path.insert(0, HERE)
import freeze_frontier; freeze_frontier.load("v1")   # noqa: E402
from openceiling import FAMILIES, frontier_ratio, effective_frontier, textbook_zero  # noqa: E402
from report import load  # noqa: E402
from evaluation_outcomes import require_scored
from figs import SYSTEMS, val  # noqa: E402
from fig_ladder import FAMS, LEVELS, TIERS_OF  # noqa: E402
OUT = os.path.join(HERE, "tables"); os.makedirs(OUT, exist_ok=True)
SHORT = {"capset": "cap set", "kissing": "kissing", "degdiam": "max. degree 3 graphs", "schur": "Schur", "covering": "covering",
         "apfree": "AP-free (control)"}


def pfmt(p):
    return ", ".join(f"{k}={v}" for k, v in p.items() if k not in ("T", "representation"))


def main():
    data = {lv: load(lv) for lv in LEVELS + [t for ts in TIERS_OF.values() for t in ts]}
    used = [(m, c, name) for (m, c, name, _) in SYSTEMS
            if any(rows.get((m, c + "#" + lv)) for lv, (ref, rows) in data.items())]
    def header(name):
        model, effort = name.rsplit(" ", 1)
        return r"\shortstack{" + model + r"\\" + effort + "}"
    head = "\\begin{tabular}{@{}llrrr" + "r" * len(used) + "@{}}\n\\toprule\nfamily & level & instance & frontier & zero & " + \
           " & ".join(header(n) for _, _, n in used) + " \\\\\n\\midrule\n"
    lines = []
    for famkey, _ in FAMS:
        fam, lvls = (famkey.split(":")[0], TIERS_OF[famkey.split(":")[1]]) if ":" in famkey else (famkey, LEVELS)
        F = FAMILIES[fam]
        for lv in lvls:
            ref, rows = data[lv]; r0 = ref.get((fam, 0))
            if r0 is None: continue
            p = r0["params"]; hf, has = effective_frontier(F, p, r0["naive"], r0["objective"])
            z = textbook_zero(F, p, r0["objective"]); zero = z[0] if z else r0["naive"]
            if r0["objective"] is not None: zero = max(zero, r0["objective"]) if F.sense == "max" else min(zero, r0["objective"])
            cells = []
            for (m, c, _) in used:
                rs = rows.get((m, c + "#" + lv), {}); v, ok = [], 0
                for (fm, s), r in sorted(rs.items()):
                    if fm != fam or (fm, s) not in ref: continue
                    require_scored(r)
                    x = val(frontier_ratio(F, ref[(fm, s)]["params"], ref[(fm, s)]["naive"], r["objective"], r["feasible"], ref[(fm, s)]["objective"]))
                    if x is not None: v.append(x); ok += bool(r["feasible"])
                cells.append(f"{np.mean(v):.2f} ({ok}/{len(v)})" if v else "--")
            label = "max. degree 4 graphs" if famkey.endswith(":M") else SHORT[fam]
            lines.append(f"{label} & {lv} & {pfmt(p)} & {hf:g}{'' if has else '*'} & {zero:g} & " + " & ".join(cells) + " \\\\")
    open(os.path.join(OUT, "ladder_table.tex"), "w").write(head + "\n".join(lines) + "\n\\bottomrule\n\\end{tabular}\n")
    print("wrote ladder_table.tex", len(lines), "rows,", len(used), "systems")


if __name__ == "__main__":
    main()
