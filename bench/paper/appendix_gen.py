#!/usr/bin/env python3
"""Appendix material generated from the code (run with plain python3; writes bench/paper/tables/*.tex).

tiers_table.tex     tier ranges and the drawn A3 instances (from run_ladder.TIERS / instance_a)
families_def.tex    mathematical definitions with representative parameters and scoring references
example_prompt.tex  one complete A3 prompt (cap set, seed 0) verbatim
"""
import json, os, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "bench"))
import freeze_frontier
freeze_frontier.load("v1-trifference")
from openceiling import FAMILIES, HEADROOM, SEARCH_TYPE, COMPACT, anchor, textbook_zero, effective_frontier  # noqa: E402
import run_ladder as L  # noqa: E402
from family_catalog import CORE_GROUPS, GROUP_LABELS, TASK_LABELS
from result_selection import reference_for
OUT = os.path.join(HERE, "tables"); os.makedirs(OUT, exist_ok=True)


def tex(s):
    return (str(s).replace("\\", "\\textbackslash{}").replace("_", "\\_").replace("&", "\\&").replace("%", "\\%")
            .replace("#", "\\#").replace("{", "\\{").replace("}", "\\}").replace("^", "\\^{}").replace("~", "\\~{}")
            .replace("<", "$<$").replace(">", "$>$").replace("|", "$|$"))


def inst(tier, fam, seed):
    L.SIZE_TIER = tier; L.A_RANGES = L.TIERS[tier]
    return L.instance_a(fam, seed)


def ref10(fam, seed, tier="A3"):
    f = reference_for(tier, fam, seed, ROOT)
    return json.load(open(f)) if os.path.exists(f) else None


def pfmt(p):
    return ", ".join(f"c={v/100:g}" if k == "cos100" else f"{k}={v}"
                     for k, v in p.items() if k not in ("T", "representation"))


DEFINITIONS = {
    "capset": r"Maximise $|S|$ for $S\subseteq\mathbb F_3^d$ containing no three distinct points $x,y,z$ with $x+y+z=0$.",
    "labs": r"Choose $s\in\{-1,1\}^N$ to maximise the merit factor $N^2/(2\sum_{k=1}^{N-1}C_k^2)$, where $C_k=\sum_{i=1}^{N-k}s_i s_{i+k}$ is the aperiodic autocorrelation.",
    "heilbronn": r"Place $n$ distinct points in $[0,1]^2$ to maximise the smallest area of a triangle determined by three points. Coordinates are multiples of $10^{-4}$.",
    "heilbronn_shape": r"Place $n$ distinct integer-grid points in a specified triangle $T$ to maximise the smallest triangle area, divided by the area of $T$.",
    "kissing": r"Maximise the number of nonzero vectors whose pairwise angles are at least $60^\circ$. After normalisation these give a kissing configuration. Coordinates are integers in $[-1000,1000]$; at $d=13$, we also allow $a+b\sqrt3$ with integer $|a|,|b|\le1000$.",
    "kissing_theta": r"Maximise the number of nonzero vectors in $\mathbb Z^d$ satisfying $u\cdot v\le c\|u\|\|v\|$ for every distinct pair. Coordinates lie in $[-1000,1000]$, and the prescribed rational value $c=\cos\theta$ is checked exactly.",
    "corners": r"Maximise $|S|$ for $S\subseteq\{0,\ldots,n-1\}^2$ containing no triple $(x,y),(x+t,y),(x,y+t)$ with $t\ne0$, including negative $t$.",
    "matmul": r"Minimise the number $r$ of scalar multiplications in a bilinear algorithm for $A\in\mathbb R^{n\times m}$ and $B\in\mathbb R^{m\times p}$. The identity $AB=\sum_{j=1}^r (u_j\cdot A)(v_j\cdot B)W_j$ must hold for all inputs, with each dot product taken over matrix entries. Coefficients are integers in $[-4,4]$.",
    "degdiam": r"Maximise the number of vertices of a simple connected undirected graph with maximum degree at most $d$ and diameter at most $k$.",
    "lineq": r"Maximise $|S|$ for $S\subseteq\{1,\ldots,n\}$ such that $ax+by=(a+b)z$ has no solution in $S$ except $x=y=z$.",
    "covering": r"Minimise the number of $k$-element blocks drawn from a $v$-element set such that every $t$-element subset is contained in at least one block.",
    "schur": r"Maximise $N$ such that $\{1,\ldots,N\}$ can be coloured with $k$ colours without a monochromatic solution of $x+y=z$. Solutions with $x=y$ are also forbidden.",
    "apfree_q": r"Maximise $|S|$ for $S\subseteq\mathbb F_q^n$ containing no three distinct points satisfying $x+z=2y$.",
    "mols": r"Find as many mutually orthogonal Latin squares of order $n$ as possible. Each symbol appears once in every row and column; superimposing any two squares must give all $n^2$ ordered symbol pairs exactly once.",
    "shannon": r"Maximise the size of a code $C\subseteq\mathbb Z_q^d$ such that every two distinct words differ by cyclic distance at least two in some coordinate. Equivalently, $C$ is an independent set in the $d$-fold strong power of the cycle $C_q$.",
    "trifference": r"Maximise the size of a ternary code $C\subseteq\{0,1,2\}^n$ such that, for every three distinct words, at least $m$ coordinates contain all three symbols.",
}


def math_params(p):
    parts=[]
    for key,value in p.items():
        if key=='representation': continue
        if key=='T':
            vertices=','.join(f'({x},{y})' for x,y in value)
            parts.append(r'T=\operatorname{conv}\{' + vertices + r'\}')
        elif key=='cos100':parts.append(f'c={value}/100')
        else:parts.append(f'{key}={value}')
    return '$' + r',\ '.join(parts) + '$'


def math_number(value):
    if value is None:return '--'
    number=f'{value:.6g}'
    if 'e' not in number:return number
    mantissa,power=number.split('e')
    return rf'${mantissa}\times10^{{{int(power)}}}$'


def tiers_table():
    lines = ["\\begin{longtable}{@{}P{.18\\linewidth}lP{.70\\linewidth}@{}}",
             "\\caption{Evaluated parameter settings. Numbers before colons are random-seed identifiers. A3 and T1--T4 specify the main evaluation; A1/A2 show representative smaller instances.}\\label{tab:tiers}\\\\",
             "\\toprule",
             "family & tier & seeded parameters \\\\", "\\midrule", "\\endfirsthead",
             "\\toprule", "family & tier & seeded parameters \\\\", "\\midrule", "\\endhead"]
    extra = {"capset": [11], "kissing": [6], "matmul": [6], "degdiam": [7, 8, 20], "apfree_q": [6], "mols": [6, 9, 17]}
    for fam in HEADROOM["open"]:
        a3 = list(range(4 if fam in ("shannon", "trifference") else 3 if fam in ("schur", "covering") else 5)) + extra.get(fam, [])
        series = [("A1", range(3)), ("A2", range(3)), ("A3", a3)]
        if fam == "trifference": series = [(f"T{i}", [0]) for i in range(1,5)]
        for tier, seeds in series:
            ps = []
            for s in seeds:
                try: ps.append(f"{s}: " + pfmt(inst(tier, fam, s)[1]))
                except Exception: ps.append("--")
            lines.append(f"{tex(fam).replace('\\_', ' ')} & {tier} & {tex('; '.join(ps))} \\\\")
        lines.append("\\addlinespace")
    lines += ["\\bottomrule", "\\end{longtable}"]
    open(os.path.join(OUT, "tiers_table.tex"), "w").write("\n".join(lines) + "\n"); print("wrote tiers_table.tex")


def families_def():
    out = []
    ordered = [(group, task) for group, tasks in CORE_GROUPS.items() for task in tasks]
    previous = None
    for group, fam in ordered:
        if group != previous:
            out.append(f"\\subsection{{{tex(GROUP_LABELS[group])}}}")
            previous = group
        F = FAMILIES[fam]; tier = "T1" if fam == "trifference" else "A3"
        Fi, p = inst(tier, fam, 0); r = ref10(fam, 0, tier)
        search = r["search"] if r else None
        z = textbook_zero(F, p, search); b, kind = anchor(F, p); hf, has = effective_frontier(F, p, r["naive"] if r else None, search)
        zero = z[0] if z else r["naive"]
        zero = (max(zero, search) if F.sense == "max" else min(zero, search)) if search is not None else zero
        source = "reference search" if zero == search else (
            "offline construction" if z and z[1] == "C" else "expert construction" if z else "naive construction")
        zs = f"{math_number(zero)} ({source})"
        variant={'kissing':r'Fixed angle ($60^\circ$)', 'kissing_theta':'Variable angle',
                 'heilbronn':'Square', 'heilbronn_shape':'Triangle'}.get(fam)
        heading=f'\\paragraph{{{variant}.}} ' if variant else ''
        out.append(heading + DEFINITIONS[fam] + '\n\n' +
                   f"Example: {math_params(p)}. Baseline: {zs}"
                   f"{'; 10 s search: ' + math_number(search) if search is not None else ''}. Scoring reference: "
                   f"{math_number(hf)} ({'published' if has else 'construction baseline'}). "
                   f"Bound or target: {math_number(b)} ({tex(kind or '--')}).")
    open(os.path.join(OUT, "families_def.tex"), "w").write("\n\n".join(out) + "\n"); print("wrote families_def.tex")


def example_prompt():
    Fi, p = inst("A3", "capset", 0)
    prompt = L.prompt_for("capset", Fi, p, "p1", None)
    open(os.path.join(OUT, "example_prompt.tex"), "w").write("\\begin{quote}\\small\\ttfamily\\raggedright " + tex(prompt).replace("\n\n", "\\par ").replace("\n", "\\par ") + "\\end{quote}\n")
    print("wrote example_prompt.tex")


if __name__ == "__main__":
    tiers_table(); families_def(); example_prompt()
