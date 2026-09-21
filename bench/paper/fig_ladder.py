#!/usr/bin/env python3
"""Size-quality curves at a fixed 128k budget, with actual parameter values on the axes.

    ~/.venvs/efpaper/bin/python bench/paper/fig_ladder.py

x = sampled parameter setting, y = ratio to the effective frontier (published value where one exists, else the better of the
expert construction and the 10 s search), one line per configuration, one panel per family; two repeats per size."""
import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "bench")); sys.path.insert(0, HERE)
from figs import SYSTEMS, save, val  # noqa: E402  (loads the frozen frontier before importing anchor)
from openceiling import FAMILIES, frontier_ratio, human_frontier, effective_frontier, textbook_zero, anchor  # noqa: E402
import math
from report import load  # noqa: E402
from evaluation_outcomes import require_scored
from matplotlib.ticker import MaxNLocator
import plot_style as S
S.apply()

LEVELS = ["L1", "L2", "L3", "L4"]
# growth-law rate: the family's scale-free constant, the same quantity at every size
from math import comb
RATE = {"capset": lambda o, p: o ** (1 / p["d"]), "kissing": lambda o, p: math.log2(o) / p["d"],
        "degdiam": lambda o, p: o ** (1 / p["k"]), "apfree": lambda o, p: math.log(o) / math.log(p["n"]),
        "schur": lambda o, p: o ** (1 / p["k"]), "covering": lambda o, p: o * comb(p["k"], p["t"]) / comb(p["v"], p["t"])}
RATE_LABEL = {"capset": "$|S|^{1/d}$", "kissing": "$\\log_2 K / d$", "degdiam": "$N^{1/k}$", "apfree": "$\\ln|S| / \\ln n$",
              "schur": "$N^{1/k}$", "covering": r"$B\binom{k}{t}/\binom{v}{t}$" + "\n(lower is better)"}
FAMS = [("capset", "Cap sets"), ("kissing", "Spherical codes (60°)"),
        ("degdiam", "Max. degree 3 graphs"), ("schur", "Schur colourings"),
        ("covering", "Covering $C(v,6,3)$"),
        ("degdiam:M", "Max. degree 4 graphs"), ("apfree", "Integer AP-free sets")]
SIZE_PARAM = {"capset": "d", "kissing": "d", "degdiam": "k", "schur": "k", "covering": "v", "apfree": "n"}
SIZE_LABEL = {"capset": "Dimension $d$", "kissing": "Dimension $d$", "degdiam": "Diameter $k$",
              "schur": "Number of colours $k$", "covering": "Set size $v$", "apfree": "Interval size $n$"}
TIERS_OF = {"M": ["M1", "M2", "M3", "M4"]}   # a family key 'fam:X' reads tiers X1..X4 instead of L1..L4


def main(fams=None, outname="fig6_ladder", mark_no_valid=False):
    global FAMS
    if fams is not None: FAMS = fams
    data = {lv: load(lv) for lv in LEVELS + [t for ts in TIERS_OF.values() for t in ts]}
    ncol = min(3,len(FAMS)) if len(FAMS) <= 6 else 4; nblk = (len(FAMS) + ncol - 1) // ncol
    shown=set()
    no_valid_shown = False
    height = 3.15 if outname == "fig6_ladder_main" else 3.45 * nblk
    fig, grid = plt.subplots(2 * nblk, ncol, figsize=(S.WIDTH, height), squeeze=False)
    for j in range(len(FAMS), nblk * ncol):                       # hide unused slots
        grid[2 * (j // ncol)][j % ncol].axis("off"); grid[2 * (j // ncol) + 1][j % ncol].axis("off")
    axes = [grid[2 * (j // ncol)][j % ncol] for j in range(len(FAMS))]; axes2 = [grid[2 * (j // ncol) + 1][j % ncol] for j in range(len(FAMS))]
    for j, (famkey, title) in enumerate(FAMS):
        fam, lvls = (famkey.split(":")[0], TIERS_OF[famkey.split(":")[1]]) if ":" in famkey else (famkey, LEVELS)
        ax = axes[j]
        F = FAMILIES[fam]
        for (m, c, name, col) in SYSTEMS:
            ys, es, ok = [], [], []
            for lv in lvls:
                ref, rows = data[lv]; rs = rows.get((m, c + "#" + lv), {})
                v, valid = [], []
                for (fm, s), r in sorted(rs.items()):
                    if fm != fam or (fm, s) not in ref: continue
                    require_scored(r)
                    x = val(frontier_ratio(F, ref[(fm, s)]["params"], ref[(fm, s)]["naive"], r["objective"], r["feasible"], ref[(fm, s)]["objective"]))
                    if x is not None: v.append(x); valid.append(bool(r["feasible"]))
                ys.append(np.mean(v) if v else np.nan); es.append((max(v) - min(v)) / 2 if len(v) > 1 else 0); ok.append(all(valid) if valid else False)
            if all(np.isnan(ys)): continue
            shown.add(name)
            line = S.config_style(m,c)
            ax.errorbar(range(4), ys, yerr=es, fmt="none", color=col, lw=S.LINE, capsize=S.CAP)
            ax.plot(range(4), ys, color=col, ls=line["linestyle"], lw=S.LINE, label=name)
            for i in range(4):
                if not np.isnan(ys[i]):
                    ax.plot(i, ys[i], line["marker"], color=col, ms=S.MARKER, markerfacecolor=(col if ok[i] else "white"), markeredgewidth=.8)
        # textbook zero (better of the expert construction and the 10 s search) as a fraction of the frontier: the free part
        zs = []
        for i, lv in enumerate(lvls):
            ref, _ = data[lv]; r0 = ref.get((fam, 0))
            if r0 is None: zs.append(np.nan); continue
            p = r0["params"]; hf, has = effective_frontier(F, p, r0["naive"], r0["objective"])
            z = textbook_zero(F, p, r0["objective"]); zero = z[0] if z else r0["naive"]
            if r0["objective"] is not None: zero = max(zero, r0["objective"]) if F.sense == "max" else min(zero, r0["objective"])
            zs.append((zero / hf if F.sense == "max" else hf / zero) if hf else np.nan)
        ax.plot(range(4), zs, **S.EXPERT, label="Baseline")
        ax.axhline(1, **S.REFERENCE); ax.set_title(title, fontsize=S.TITLE)
        ax.set_xticks(range(4)); ax.set_xticklabels([]); ax.set_ylim(0, 1.3);ax.set_yticks([0,.5,1]);ax.grid(axis="y")
        lvl_labels = [f"{data[lv][0][fam, 0]['params'][SIZE_PARAM[fam]]:,}" for lv in lvls]
        if j % ncol: ax.set_yticklabels([])
        # bottom row: growth-law rate with the proven bound, the frontier, the expert construction and the systems
        R = RATE[fam]; ax2 = axes2[j]; bl, fl, el = [], [], []
        for i, lv in enumerate(lvls):
            ref, rows = data[lv]; r0 = ref.get((fam, 0)); p = r0["params"]
            b, kind = anchor(F, p); hf, has = effective_frontier(F, p, r0["naive"], r0["objective"])
            z = textbook_zero(F, p, r0["objective"]); zero = z[0] if z else r0["naive"]
            if r0["objective"] is not None: zero = max(zero, r0["objective"]) if F.sense == "max" else min(zero, r0["objective"])
            bl.append(R(b, p) if b and kind == "bound" else np.nan); fl.append(R(hf, p)); el.append(R(zero, p))
        ax2.plot(range(4), bl, **S.BOUND, label="Proven bound"); ax2.plot(range(4), fl, **S.REFERENCE, label="Reference")
        ax2.plot(range(4), el, **S.EXPERT)
        for (m, c, name, col) in SYSTEMS:
            ys, es = [], []
            for i, lv in enumerate(lvls):
                ref, rows = data[lv]; rs = rows.get((m, c + "#" + lv), {}); p = ref[(fam, 0)]["params"]
                responses = [r for (fm, s), r in sorted(rs.items()) if fm == fam]
                v = [R(r["objective"], p) for r in responses if r["feasible"] and r["objective"] > 0]
                ys.append(np.mean(v) if v else np.nan); es.append((max(v) - min(v)) / 2 if len(v) > 1 else 0)
                if mark_no_valid and responses and not any(r["feasible"] for r in responses):
                    # Status below the axis, with no invented transformed-size value.
                    ax2.annotate("×", (i, 0), xycoords=ax2.get_xaxis_transform(),
                                 xytext=(0, -18), textcoords="offset points",
                                 ha="center", va="center", color=col,
                                 fontsize=9, annotation_clip=False)
                    no_valid_shown = True
            if all(np.isnan(ys)): continue
            ax2.errorbar(range(4), ys, yerr=es, **S.config_style(m,c), capsize=S.CAP)
        ax2.set_xticks(range(4)); ax2.set_xticklabels(lvl_labels); ax2.set_title(RATE_LABEL[fam], fontsize=S.TITLE, pad=4)
        ax2.set_xlabel(SIZE_LABEL[fam])
        ax2.yaxis.set_major_locator(MaxNLocator(nbins=3));ax2.grid(axis="y")
    for b in range(nblk):
        axes[b * ncol].set_ylabel("Relative quality"); axes2[b * ncol].set_ylabel("Transformed size")
    used = [(m,c,name) for m,c,name,_ in SYSTEMS if name in shown]
    H = [S.Line2D([], [], **S.config_style(m,c)) for m,c,_ in used]
    Lb = [name for _,_,name in used]
    for handle,label in S.reference_handles(expert=True): H.append(handle);Lb.append(label)
    if no_valid_shown:
        H.append(S.Line2D([], [], color=S.T.MUTED, marker="x", linestyle="none", markersize=S.MARKER))
        Lb.append("No valid construction")
    S.legend(fig, H, Lb, ncol=3)
    fig.tight_layout(rect=[0, .78/fig.get_figheight(), 1, .99], pad=.7, h_pad=1.2, w_pad=.7)
    save(fig, outname)


if __name__ == "__main__":
    ALL = list(FAMS)
    main(ALL, "fig6_ladder")            # all families (appendix)
    main(ALL[:3], "fig6_ladder_main", mark_no_valid=True)   # cap set, kissing, cubic graphs (main text)
