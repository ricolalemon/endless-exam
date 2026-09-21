#!/usr/bin/env python3
"""Plot formal code-family answers across all publication configurations; never launch model calls.

Run: ~/.venvs/efpaper/bin/python bench/paper/fig_code_scale.py
The fixed-block curves are descriptive baselines, not new scoring references.
"""
import copy
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "bench"))
from candidate_families import Shannon, Trifference, shannon_second, trifference_second

DATA = ROOT / "bench/results/pilots/code-multimodel-2026-09-15"
OUT = ROOT / "output/figures"
from publication_data import ORDER, REGISTRY, COLORS, code_data
import plot_style as S
STYLE = {sid: (REGISTRY[sid][2], S.color(sid), S.MARKERS[sid], 6.5,
               S.style(sid)["linestyle"]) for sid in ORDER}
PANELS = [
    ("shannon", 7, "Shannon · C₇", "codeword length d", "d"),
    ("shannon", 9, "Shannon · C₉", "codeword length d", "d"),
    ("trifference", None, "Trifference · m = 1", "length n", "n"),
]


def identity(row):
    return row["tier"], row["family"], row["seed"]


def rate(value, case):
    if value <= 0:
        return float("nan")
    p = case["params"]
    return math.exp(math.log(value) / p["d"]) if case["family"] == "shannon" else math.log(value, 3) / p["n"]


def fixed_block(case):
    """Use one fixed inner building block throughout each panel, with padding."""
    p = case["params"]
    if case["family"] == "shannon":
        q, d = p["q"], p["d"]
        size = 2 if q == 7 else 3
        bases = Shannon.bases(q)
        parts = [{"words": bases[size], "power": d // size}]
        if d % size:
            parts.append({"words": bases[1], "power": d % size})
        answer = {"factors": parts}
        first = Shannon().verify(p, answer)[:2]
        second = shannon_second(p, answer)
    else:
        original = json.loads((ROOT / "bench/refs/T1-trifference-0-t10.json").read_text())
        rc = copy.deepcopy(original["search_answer"]["rs_concat"])
        rc["length"] = min(27, p["n"] // 9)
        rc["dimension"] = (rc["length"] + 2) // 3
        answer = {"rs_concat": rc}
        first = Trifference().verify(p, answer)[:2]
        second = trifference_second(p, answer)
    assert first == second and first[0], (identity(case), first, second)
    return first[1], answer


def prepare():
    _, measurements = code_data()
    summary = {"complete": True, "cases": measurements}
    manifest = json.loads((DATA / "manifest.json").read_text())
    assert summary["complete"] and len(summary["cases"]) == 8*len(ORDER)
    indexed = {(r["system"], identity(r)): r for r in summary["cases"]}
    assert len(indexed) == 8*len(ORDER)
    cases = []
    for case in manifest["cases"]:
        path = ROOT / case["reference_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == case["reference_sha256"]
        family = Shannon() if case["family"] == "shannon" else Trifference()
        assert family.upper(case["params"]) == case["bound"]
        assert case["reference"] <= case["bound"]
        baseline, certificate = fixed_block(case)
        rows = [indexed[(sid, identity(case))] for sid in ORDER]
        assert all(r["reference"] == case["reference"] and r["params"] == case["params"] for r in rows)
        assert all(math.isclose(r["ratio"], r["objective"] / case["reference"]) for r in rows)
        cases.append({**case, "fixed_block_objective": baseline, "fixed_block_certificate": certificate,
                      "measurements": rows})
    return cases


def main(show_bounds=False):
    cases = prepare()
    S.apply()
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.labelcolor": S.INK, "xtick.color": S.T.AXIS,
                         "ytick.color": S.T.AXIS, "axes.edgecolor": S.T.NEUTRAL,
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    fig = plt.figure(figsize=(14.0, 13.0), facecolor="white")
    grid = fig.add_gridspec(3, 3, height_ratios=[2.55, 2.45, 3.3],
                           left=.13, right=.97, top=.805, bottom=.115, wspace=.29, hspace=.65)
    title = "Code families: scale, quality and upper bounds" if show_bounds else "Code families: scale and construction quality"
    fig.text(.13, .959, title, fontsize=23,
             fontweight="bold", color=S.T.HEADING)
    fig.text(.13, .925, f"{len(ORDER)} configurations · 8 common instances · one scored response per instance · 128k output budget",
             fontsize=11.2, color=S.T.MUTED)
    handles = [Line2D([], [], color=STYLE[s][1], marker=STYLE[s][2], markersize=6,
                      markerfacecolor="none", lw=1.6, ls=STYLE[s][4], label=STYLE[s][0]) for s in ORDER]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.124, .9),
               ncol=4, frameon=False, fontsize=9.5, columnspacing=1.6, handlelength=2.8)
    key = ("Dark dotted: proven bound     Black dashed: frozen reference     Gray dash-dot: fixed block     ×: failed attempt"
           if show_bounds else "Black dashed: frozen reference     Gray dash-dot: fixed-block construction     ×: failed attempt")
    fig.text(.13, .84, key,
             color=S.T.MUTED, fontsize=9.7)

    for col, (family, q, title, xlabel, dimension) in enumerate(PANELS):
        group = sorted([c for c in cases if c["family"] == family and
                        (q is None or c["params"]["q"] == q)], key=lambda c: c["params"][dimension])
        xs = np.array([c["params"][dimension] for c in group])
        score_ax = fig.add_subplot(grid[0, col])
        rate_ax = fig.add_subplot(grid[1, col])
        score_ax.set_title(title + ("  ·  2 sizes" if q else "  ·  4 sizes"),
                           loc="left", fontsize=13, fontweight="bold", pad=13, color=S.T.HEADING)
        baseline_ratio = [c["fixed_block_objective"] / c["reference"] for c in group]
        baseline_rate = [rate(c["fixed_block_objective"], c) for c in group]
        ref_rate = [rate(c["reference"], c) for c in group]
        bound_rate = [rate(c["bound"], c) for c in group]
        for ax in (score_ax, rate_ax):
            ax.set_xticks(xs)
            ax.set_xlabel(xlabel)
            ax.set_xlim(xs[0] - .12 * (xs[-1] - xs[0]), xs[-1] + .12 * (xs[-1] - xs[0]))
            ax.grid(axis="y", color=S.GRID, lw=.7)
            ax.set_axisbelow(True)
        score_ax.axhline(1, color=S.INK, ls=(0, (7, 3)), lw=2.7, zorder=1)
        score_ax.plot(xs, baseline_ratio, color=S.EXPERT["color"], ls=S.EXPERT["linestyle"], lw=2, zorder=2)
        rate_ax.plot(xs, ref_rate, color=S.INK, ls=(0, (7, 3)), lw=2.7, zorder=1)
        rate_ax.plot(xs, baseline_rate, color=S.EXPERT["color"], ls=S.EXPERT["linestyle"], lw=2, zorder=2)
        if show_bounds:
            rate_ax.fill_between(xs, ref_rate, bound_rate, color=S.BOUND["color"], alpha=.055, zorder=0)
            rate_ax.plot(xs, bound_rate, color=S.BOUND["color"], ls=S.BOUND["linestyle"], lw=1.8, zorder=2)
        for sid in ORDER:
            rows = [next(r for r in c["measurements"] if r["system"] == sid) for c in group]
            _, color, marker, ms, ls = STYLE[sid]
            ys = [r["ratio"] for r in rows]
            rs = [rate(r["objective"], c) if r["valid"] else np.nan for r, c in zip(rows, group)]
            # Missing rates break the line; no imputation or bridging failed responses.
            score_ax.plot(xs, ys, color=color, ls=ls, lw=1.7, alpha=.95)
            rate_ax.plot(xs, rs, color=color, ls=ls, lw=1.7, alpha=.95)
            for x, y, rr, row in zip(xs, ys, rs, rows):
                score_ax.plot(x, y, marker=marker if row["valid"] else "x", color=color,
                              ms=ms, markerfacecolor="none", markeredgewidth=1.5)
                if row["valid"]:
                    rate_ax.plot(x, rr, marker=marker, color=color, ms=ms,
                                 markerfacecolor="none", markeredgewidth=1.5)
        score_ax.set_yscale("symlog", linthresh=.001, linscale=.4)
        score_ax.set_ylim(-.00024, 3.6 if q is None else 1.4)
        ticks = [0, .001, .01, .1, 1] + ([3] if q is None else [])
        score_ax.set_yticks(ticks, labels=[f"{t:g}" for t in ticks])
        score_ax.set_ylabel("Relative quality")
        if q:
            rate_ax.set_ylabel(r"Per-coordinate growth: $M^{1/d}$")
            rate_ax.set_ylim((2.97, 3.36 if show_bounds else 3.32) if q == 7 else (3.97, 4.40 if show_bounds else 4.38))
        else:
            rate_ax.set_ylabel(r"Ternary rate: $\log_3 M\,/\,n$")
            rate_ax.set_ylim(.06 if show_bounds else .071, .41 if show_bounds else .17)
        if show_bounds:
            bound_text = (r"Lovász $\vartheta(C_7)$ bound" if q == 7 else
                          r"Lovász $\vartheta(C_9)$ bound" if q == 9 else
                          r"Universal bound: $M\leq 2(3/2)^n$")
            rate_ax.annotate(bound_text, (xs[0], bound_rate[0]), xytext=(0, 6),
                             textcoords="offset points", color=S.BOUND["color"], fontsize=8.3)
            if q is None:
                zoom = rate_ax.inset_axes([.36, .45, .60, .35])
                zoom.set_facecolor(S.T.PAPER)
                zoom.plot(xs, ref_rate, color=S.INK, ls=(0, (7, 3)), lw=1.5)
                for sid in ORDER:
                    rows = [next(r for r in c["measurements"] if r["system"] == sid) for c in group]
                    rr = [rate(r["objective"], c) if r["valid"] else np.nan for r, c in zip(rows, group)]
                    _, color, marker, ms, ls = STYLE[sid]
                    zoom.plot(xs, rr, color=color, ls=ls, lw=1, marker=marker,
                              ms=ms*.55, markerfacecolor="none", markeredgewidth=.8)
                zoom.set_ylim(.071, .17)
                zoom.set_xticks([64, 192])
                zoom.set_yticks([.08, .14])
                zoom.tick_params(labelsize=6.5, pad=1, length=2)
                zoom.set_title("Model detail (same points)", fontsize=7.1, pad=3, color=S.T.MUTED)
                for spine in zoom.spines.values():
                    spine.set_color(S.T.NEUTRAL)
        note = {7: "Fixed block: 10 words / 2 coordinates",
                9: "Reference = 81-word / 3-coordinate block + padding",
                None: "Reference = fixed 27-word / 9-coordinate inner code + RS"}[q]
        rate_ax.text(0, 1.08, note, transform=rate_ax.transAxes, fontsize=8.1, color=S.T.MUTED)

    # The outcome grid keeps coincident zero scores distinguishable by configuration.
    ax = fig.add_subplot(grid[2, :])
    ax.set_title("Outcome at every measured size", loc="left", fontsize=11.5,
                 color=S.T.HEADING, fontweight="bold", pad=31)
    labels = ["C₇ · 24", "C₇ · 40", "C₉ · 48", "C₉ · 64", "n = 64", "n = 96", "n = 144", "n = 192"]
    for i, sid in enumerate(ORDER):
        for j, case in enumerate(cases):
            row = next(r for r in case["measurements"] if r["system"] == sid)
            outcome = ("OK" if row["valid"] else "BUDGET" if row["outcome"] == "length" else
                       "NO FINAL" if row["outcome"] == "empty_final" else "FORMAT"
                       if any(s in (row.get("verify_msg") or "") for s in ("length or alphabet", "malformed", "must contain"))
                       else "API" if row["outcome"] in ("transport_error", "quota_error") else "PROPERTY")
            ax.add_patch(Rectangle((j - .48, i - .43), .96, .86,
                                  color=S.T.PANEL_TITLE if row["valid"] else S.T.RESULT_TITLE, lw=0))
            ax.text(j, i, outcome, ha="center", va="center", fontsize=8.3,
                    color=S.INK if row["valid"] else S.T.OCHRE)
    ax.set_xlim(-.5, 7.5)
    ax.set_ylim(len(ORDER)-.5, -.5)
    ax.set_yticks(range(len(ORDER)), [REGISTRY[s][2] for s in ORDER], fontsize=9)
    for tick, sid in zip(ax.get_yticklabels(), ORDER):
        tick.set_color(STYLE[sid][1])
    ax.set_xticks(range(8), labels, fontsize=9)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(.13, .06, "Top: ratios use a log scale above 0.001 and a linear band around zero. Bottom curves: valid answers only.",
             fontsize=9.2, color=S.T.MUTED)
    fig.text(.13, .037, "Lines connect observed points only; there are no repeat estimates. Fixed-block baselines do not change official scores.",
             fontsize=9.2, color=S.T.MUTED)
    OUT.mkdir(parents=True, exist_ok=True)
    name = "code_scale_curves_bounds" if show_bounds else "code_scale_curves"
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=200, facecolor="white")
    plt.close(fig)
    evidence = {
        "source_summary_sha256": hashlib.sha256((HERE / "tables/publication_data.json").read_bytes()).hexdigest(),
        "source_manifest_sha256": hashlib.sha256((DATA / "manifest.json").read_bytes()).hexdigest(),
        "new_model_calls": 0,
        "official_scores_changed": False,
        "mathematical_upper_bounds_shown": show_bounds,
        "bounds_match_frozen_manifest_and_verifier_formula": True,
        "fixed_block_baselines_primary_and_independent_verified": True,
        "trifference_reference_equals_fixed_inner_baseline_at_all_sizes": all(
            c["reference"] == c["fixed_block_objective"] for c in cases if c["family"] == "trifference"),
        "points": [{k: c[k] for k in ("tier", "family", "seed", "params", "reference", "bound",
                                     "fixed_block_objective", "fixed_block_certificate", "measurements")} for c in cases],
    }
    data_name = "scale_curve_bounds_data.json" if show_bounds else "scale_curve_data.json"
    (HERE / "tables" / data_name).write_text(json.dumps(evidence, indent=2) + "\n")
    paper_figure(cases)
    print(OUT / f"{name}.png")
    print(OUT / f"{name}.pdf")


def paper_figure(cases):
    """Same measurements as the standalone views, at the paper's exact text width."""
    S.apply()
    fig, axes = plt.subplots(2, 3, figsize=(S.WIDTH, 4.4))
    for col, (family, q, title, xlabel, dimension) in enumerate(PANELS):
        group = sorted([c for c in cases if c["family"] == family and (q is None or c["params"]["q"] == q)], key=lambda c: c["params"][dimension])
        xs = [c["params"][dimension] for c in group];top, bottom = axes[:, col]
        top.axhline(1, **S.REFERENCE)
        bottom.plot(xs, [rate(c["reference"], c) for c in group], **S.REFERENCE)
        bottom.plot(xs, [rate(c["bound"], c) for c in group], **S.BOUND)
        for sid in ORDER:
            rows = [next(r for r in c["measurements"] if r["system"] == sid) for c in group]
            opts = S.style(sid)
            top.plot(xs, [r["ratio"] for r in rows], **opts, label=REGISTRY[sid][2])
            bottom.plot(xs, [rate(r["objective"], c) if r["valid"] else np.nan for r,c in zip(rows,group)], **opts)
        top.set_yscale("symlog", linthresh=.001, linscale=.4)
        top.set_ylim(-.00015, 4 if q is None else 1.6)
        ticks = [0,.001,.1,1] + ([3] if q is None else [])
        top.set_yticks(ticks, labels=[f"{t:g}" for t in ticks])
        top.set_title(f"Shannon $C_{q}$\n2 sizes" if q else "Trifference\n4 sizes ($m=1$)")
        top.set_ylabel("Relative quality")
        bottom.set_title("$M^{1/d}$" if q else "$\\log_3 M/n$")
        if col == 0: bottom.set_ylabel("Transformed code size")
        if q == 7: bottom.set_ylim(2.98,3.37)
        elif q == 9: bottom.set_ylim(3.98,4.4)
        else: bottom.set_ylim(.065,.41)
        for ax in (top,bottom):
            ax.set_xticks(xs);ax.set_xlabel("Codeword length $d$" if q else "Codeword length $n$")
            ax.grid(axis="y")
    handles, labels = axes[0,0].get_legend_handles_labels()
    for handle, label in S.reference_handles(): handles.append(handle);labels.append(label)
    S.legend(fig, handles, labels, ncol=3)
    fig.subplots_adjust(left=.12, right=.98, bottom=.285, top=.90, wspace=.53, hspace=.85)
    S.save(fig,"fig8_code_scale")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bounds", action="store_true", help="show frozen mathematical upper bounds in the rate panels")
    main(parser.parse_args().bounds)
