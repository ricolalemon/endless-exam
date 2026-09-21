#!/usr/bin/env python3
"""Enlarged Shannon panels with upper bounds on both scoring and growth axes."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

from fig_code_scale import ORDER, OUT, STYLE, prepare, rate
import plot_style as S


def main():
    cases = prepare()
    S.apply()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.edgecolor": S.T.NEUTRAL, "pdf.fonttype": 42})
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.3))
    fig.subplots_adjust(left=.09, right=.965, top=.75, bottom=.11, hspace=.46, wspace=.24)
    fig.text(.09, .956, "Shannon: mathematical upper bounds", fontsize=23,
             fontweight="bold", color=S.T.HEADING)
    fig.text(.09, .916, f"Upper bounds on both rows · four common instances across {len(ORDER)} configurations",
             fontsize=10.5, color=S.T.MUTED)
    handles = [Line2D([], [], color=STYLE[s][1], marker=STYLE[s][2], markersize=6,
                      markerfacecolor="none", lw=1.5, ls=STYLE[s][4], label=STYLE[s][0]) for s in ORDER]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.082, .896), ncol=4,
               frameon=False, fontsize=9, handlelength=2.3, columnspacing=1.2)
    fig.text(.09, .79, "Dotted: proven bound       Black dashed: frozen reference       ×: failed attempt",
             fontsize=10.3, color=S.BOUND["color"])
    for col, q in enumerate((7, 9)):
        group = sorted([c for c in cases if c["family"] == "shannon" and c["params"]["q"] == q],
                       key=lambda c: c["params"]["d"])
        xs = np.array([c["params"]["d"] for c in group])
        br = [c["bound"] / c["reference"] for c in group]
        bg = [rate(c["bound"], c) for c in group]
        rg = [rate(c["reference"], c) for c in group]
        score_ax, rate_ax = axes[:, col]
        score_ax.set_title(f"C{chr(0x2080 + q)}", loc="left", fontsize=16, fontweight="bold", color=S.T.HEADING)
        for ax in (score_ax, rate_ax):
            ax.set_xticks(xs)
            ax.set_xlim(xs[0] - 2, xs[-1] + 2)
            ax.set_xlabel("dimension d")
            ax.grid(axis="y", color=S.GRID, lw=.7)
            ax.set_axisbelow(True)
        score_ax.axhline(1, color=S.INK, ls="--", lw=2)
        score_ax.fill_between(xs, 1, br, color=S.BOUND["color"], alpha=.07)
        score_ax.plot(xs, br, color=S.BOUND["color"], lw=2.6, ls=S.BOUND["linestyle"], marker="_", ms=10)
        for x, y in zip(xs, br):
            score_ax.annotate(f"upper bound {y:.3f}", (x, y), xytext=(0, 14), textcoords="offset points",
                              ha="left" if x == xs[0] else "right", fontsize=10.4,
                              color=S.BOUND["color"], fontweight="bold", bbox={"facecolor":"white","edgecolor":"none","alpha":.8,"pad":1})
        rate_ax.plot(xs, rg, color=S.INK, ls="--", lw=2)
        rate_ax.fill_between(xs, rg, bg, color=S.BOUND["color"], alpha=.07)
        rate_ax.plot(xs, bg, color=S.BOUND["color"], ls=S.BOUND["linestyle"], lw=2.6)
        rate_ax.annotate(f"Lovász upper bound {bg[0]:.4f}", (xs[0], bg[0]), xytext=(0, 9),
                         textcoords="offset points", fontsize=11, fontweight="bold", color=S.BOUND["color"])
        for sid in ORDER:
            rows = [next(r for r in c["measurements"] if r["system"] == sid) for c in group]
            _, color, marker, ms, ls = STYLE[sid]
            for ax, ys in ((score_ax, [r["ratio"] for r in rows]),
                           (rate_ax, [rate(r["objective"], c) if r["valid"] else np.nan
                                      for r, c in zip(rows, group)])):
                ax.plot(xs, ys, color=color, ls=ls, lw=1.6)
                for x, y, r in zip(xs, ys, rows):
                    if np.isfinite(y):
                        ax.plot(x, y, color=color, marker=marker if r["valid"] else "x",
                                ms=ms, markerfacecolor="none", markeredgewidth=1.5)
        score_ax.set_ylabel("Relative quality")
        score_ax.set_ylim(-.06, 2.4)
        score_ax.set_yticks([0, .5, 1, 1.5, 2])
        rate_ax.set_ylabel(r"Per-coordinate growth: $M^{1/d}$")
        rate_ax.set_ylim((2.97, 3.38) if q == 7 else (3.97, 4.43))
    fig.text(.09, .035, "Each point is one attempt. Growth rates omit failed answers. Proven upper bounds need not be attainable.",
             color=S.T.MUTED, fontsize=9.8)
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        path = OUT / f"shannon_bounds_detail.{ext}"
        fig.savefig(path, dpi=200, facecolor="white")
        print(path)
    plt.close(fig)


if __name__ == "__main__":
    main()
