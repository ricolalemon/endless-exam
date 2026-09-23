#!/usr/bin/env python3
"""LaTeX tables for the Endless Exam paper (run with ~/.venvs/efpaper/bin/python; writes bench/paper/tables/*.tex).

families_table.tex   The fourteen headline families.
headline_table.tex   A3 scores, response validity and per-panel coverage.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "bench")); sys.path.insert(0, HERE)
from report import load, ci, split_families as all_families  # noqa: E402
from figs import SYSTEMS, split_families, system_values  # noqa: E402
from openceiling import FAMILIES, HEADROOM, SEARCH_TYPE, COMPACT, anchor, frontier_ratio, closed_gap, human_frontier  # noqa: E402
from family_catalog import members, expand_groups, SEARCH_GROUPS, UNCLASSIFIED_GROUPS
from publication_data import ORDER, REGISTRY, load_formal, summaries

OUT = os.path.join(HERE, "tables"); os.makedirs(OUT, exist_ok=True)

DESC = {
    "shannon": (r"code in $\{0,\ldots,q-1\}^d$", "every pair separates on the cycle", "$|C|$"),
    "trifference": ("ternary code of length $n$", "every triple has at least $m$ coordinates with three distinct symbols", "$|C|$"),  # family -> (object, property the verifier checks, objective)
    "spherical_code": ("vectors with exact coordinates", "pairwise angle $\\ge\\theta$; $60^\\circ$ or variable", "count"),
    "apfree": ("$S \\subseteq \\{1..n\\}$", "no $k$-term arithmetic progression", "$|S|$"),
    "capset": ("$S \\subseteq \\mathbb{F}_3^d$", "no three collinear points (cap set)", "$|S|$"),
    "labs": ("$\\pm1$ sequence of length $N$", "well-formed sequence", "merit factor $N^2/(2\\sum_k C_k^2)$"),
    "heilbronn": ("$n$ points in a square or triangle", "distinct points in the domain", "min triangle area"),
    "kissing": ("vectors with exact coordinates", "pairwise angle $\\ge 60^\\circ$", "count"),
    "corners": ("$S \\subseteq [n]^2$", "no corner $(x,y),(x{+}d,y),(x,y{+}d)$", "$|S|$"),
    "unitdist": ("$n$ integer points in the plane", "distinct points", "pairs at the most frequent distance"),
    "kissing_theta": ("integer vectors in $\\mathbb{Z}^d$", "pairwise angle $\\ge \\theta$, random $\\cos\\theta$", "count"),
    "heilbronn_shape": ("$n$ points in a triangle (integer grid)", "points inside the triangle", "min triangle area"),
    "sortnet": ("comparator network on $n$ wires", "sorts every 0/1 input", "comparators (min)"),
    "matmul": ("bilinear scheme for $(n{\\times}m)(m{\\times}p)$", "computes the product exactly", "rank $r$ (min)"),
    "degdiam": ("graph with max degree $d$", "diameter $\\le k$", "vertices"),
    "lineq": ("$S \\subseteq \\{1..n\\}$", "no solution of $ax+by=(a{+}b)z$, random $(a,b)$", "$|S|$"),
    "kakeya": ("$K \\subseteq \\mathbb{F}_q^n$", "a full line in every direction", "$|K|$ (min)"),
    "apfree_q": ("$S \\subseteq \\mathbb{F}_q^n$, $q\\in\\{5,7\\}$", "no 3-term progression", "$|S|$"),
    "mols": ("Latin squares of order $n$, $n$ not a prime power", "pairwise orthogonal", "number of squares"),
    "schur": ("$k$-colouring of $\\{1..N\\}$", "no monochromatic $x, y, x{+}y$", "$N$"),
    "covering": ("$k$-subsets (blocks) of $[v]$", "every $t$-subset lies in a block", "blocks (min)"),
}
KIND = {"bound": "proven bound", "lit": "literature", "literature": "literature", "conj": "conjecture", "conjecture": "conjectured target", "trivial": "trivial bound", "T": "trivial bound", "L": "literature", "C": "conjecture"}


def families_table():
    ref, rows = load_formal(); fams, lit, tf = all_families(ref)
    lines = ["\\begin{tabularx}{\\linewidth}{@{}P{.16\\linewidth}YP{.12\\linewidth}P{.09\\linewidth}P{.22\\linewidth}@{}}", "\\toprule",
             "family & construction & objective & class & reference; bound or target \\\\", "\\midrule"]
    labels = {"shannon": "Shannon", "capset": "cap set", "kissing_theta": "spherical code", "heilbronn_shape": "Heilbronn (triangle)",
              "apfree_q": "$\\mathbb{F}_q^n$ AP-free", "degdiam": "degree--diameter", "lineq": "linear-equation-free",
              "matmul": "matrix multiplication", "schur": "Schur", "mols": "MOLS", "labs": "LABS", "heilbronn": "Heilbronn"}
    for f in lit + [f for f in tf if f not in lit]:
        task = members(f)[0]; fam = FAMILIES[task]; p = ref[(task, 0)]["params"]; b, kind = anchor(fam, p)
        obj, prop, o = DESC[f]
        if f == "labs": o = "merit factor"
        if f == "corners": prop = "no corner"
        if f == "lineq": prop = "no non-trivial solution of the specified linear equation"
        if f == "matmul": obj = "bilinear scheme for $(n\\times m)$ by $(m\\times p)$ matrices"
        cls = "search" if f in SEARCH_TYPE else "resist."
        frontier = "mixed" if f in lit and f in tf else ("published" if f in lit else "construction")
        label = "spherical codes" if f == "spherical_code" else labels.get(f, f)
        label = rf"\hyperref[family:{f}]{{{label}}}"
        lines.append(f"{label} & {obj}; {prop} & {o} & {'U' if f in UNCLASSIFIED_GROUPS else 'S' if f in SEARCH_GROUPS else 'R'} & {frontier}; {KIND.get(kind, kind)} \\\\")
        if f == lit[-1]: lines.append("\\midrule")
    lines += ["\\bottomrule", "\\end{tabularx}"]
    open(os.path.join(OUT, "families_table.tex"), "w").write("\n".join(lines) + "\n"); print("wrote families_table.tex")


def headline_table(tier="A3"):
    data = summaries()
    lines = [r"\begin{tabular}{@{}lrrrrr@{}}", r"\toprule",
             r"& & \multicolumn{2}{c}{Mean relative quality} & & \\",
             r"\cmidrule(lr){3-4}",
             r"configuration & \shortstack{Overall\\score} & \shortstack{Published\\frontiers (30)} & \shortstack{Construction\\baselines (39)} & \shortstack{Valid\\fraction} & \shortstack{Gap\\closed} \\", r"\midrule"]
    best = max(s["overall"]["score"] for s in data.values())
    for sid in ORDER:
        s = data[sid]
        def cell(p):
            lo, hi = s[p]["ci"]
            return f"{s[p]['mean']:.2f} [{lo:.2f}, {hi:.2f}]"
        total = f"{s['overall']['score']:.2f}"
        if s["overall"]["score"] == best: total = r"\textbf{" + total + "}"
        lines.append(f"{s['label']} & {total} & {cell('p1')} & {cell('p2')} & {s['valid']:.2f} & {s['headroom']:.3f}" + r" \\")
    from tool_results import load_all
    tools = load_all()
    best_tool = max(t['overall']['score'] for t in tools.values())
    def tool_cell(tool, panel, digits=2):
        p = tool[panel]; lo, hi = p['ci']
        return f"{p['mean']:.{digits}f} [{lo:.{digits}f}, {hi:.{digits}f}]"
    lines.append(r"\midrule")
    for tool in tools.values():
        score = f"{tool['overall']['score']:.2f}"
        if tool['overall']['score'] == best_tool:
            score = r'\textbf{' + score + '}'
        lines.append(f"{tool['label']} & {score} & {tool_cell(tool, 'p1', 3)} & "
                     f"{tool_cell(tool, 'p2')} & {tool['valid']:.2f} & {tool['headroom']:.3f}" + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    open(os.path.join(OUT, "headline_table.tex"), "w").write("\n".join(lines) + "\n")
    print(f"wrote headline_table.tex: {len(ORDER)} tool-free and {len(tools)} tool-assisted configurations")


if __name__ == "__main__":
    families_table(); headline_table()
