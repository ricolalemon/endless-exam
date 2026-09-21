#!/usr/bin/env python3
"""Figures for the Endless Exam paper.  Run with a Python that has matplotlib (~/.venvs/efpaper).

    ~/.venvs/efpaper/bin/python bench/paper/figs.py            # writes bench/paper/figs/*.pdf and .png

Fig 1  scale (manuscript Figure 2): family means from both tracks relative to references and bounds.
Fig 2  headline: human-frontier ratio with 95 % bootstrap CI, panel 1 (published tables) and panel 2 (table-free).
Fig 3  tiers: mean HFR at A1 / A2 / A3 per system (families available at every tier for that system).
Fig 4  Astra effort comparison at A2: mean relative quality at medium, high and xhigh.
Fig 5  compute-only baseline at A3: 600 s search and the best model, both relative to the 10 s search, per family.
"""
import glob, json, math, os, random, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "bench"))
import freeze_frontier
freeze_frontier.load("v1-trifference")
from openceiling import FAMILIES, HEADROOM, SEARCH_TYPE, frontier_ratio, closed_gap, human_frontier, effective_frontier, anchor, textbook_zero  # noqa: E402
from report import load, ci, split_families as _split_families, system_values  # noqa: E402
from evaluation_outcomes import require_scored
from family_catalog import members, expand_groups, SEARCH_GROUPS

def split_families(ref):
    """The complete publication cohort covers all fourteen families."""
    return _split_families(ref, "core")


OUT = os.path.join(ROOT, "bench", "paper", "figs"); os.makedirs(OUT, exist_ok=True)
from publication_data import SYSTEMS, load_formal, REGISTRY, MODEL_NAMES
import plot_style as S
S.apply()
LEGACY_SYSTEMS = [(REGISTRY[sid][1], REGISTRY[sid][3], REGISTRY[sid][2], S.color(sid))
                  for sid in ("deepseek_low", "deepseek_high", "qwen38", "opus", "fable", "astra_medium", "astra_high")]

PRETTY = {"apfree": "AP-free", "capset": "cap set", "labs": "LABS", "heilbronn": "Heilbronn", "kissing": "kissing", "corners": "corners",
          "unitdist": "unit distance", "kissing_theta": "spherical code", "heilbronn_shape": "Heilbronn (triangle)", "sortnet": "sorting net",
          "matmul": "matrix multiplication", "degdiam": "degree–diameter", "lineq": "linear-equation-free sets", "kakeya": "Kakeya", "apfree_q": "AP-free F_q^n", "mols": "MOLS"}

PRETTY["spherical_code"] = "spherical codes"
PRETTY.update(shannon="Shannon", trifference="trifference", apfree_q=r"$\mathbb{F}_q^n$ AP-free")


def val(x):
    return x[0] if isinstance(x, tuple) else x


def save(fig, name):
    S.save(fig, name)


# ---------------------------------------------------------------- Fig 1: the scale
def scale_reference_values(ref=None):
    """Normalize each fixed instance, then average over the model-point cohort."""
    if ref is None:
        ref, _ = load_formal()
    _, published, construction = split_families(ref)
    groups = {}
    for reference_type, families in [('published', published), ('construction', construction)]:
        for family in families:
            records = []
            for (task, plot_seed), r in sorted(ref.items()):
                if task not in members(family):
                    continue
                fam, params = FAMILIES[task], r['params']
                frontier, is_published = effective_frontier(fam, params, r['naive'], r['objective'])
                if is_published != (reference_type == 'published'):
                    continue
                bound, kind = anchor(fam, params)
                if bound is None or bound <= 0 or frontier <= 0:
                    raise ValueError(f'Missing positive anchor/reference: {task} {params}')
                bound_ratio = bound / frontier if fam.sense == 'max' else frontier / bound
                candidates = [v for v in (val(textbook_zero(fam, params, r['objective'])), r['objective'])
                              if v is not None]
                baseline = (max(candidates) if fam.sense == 'max' else min(candidates)) if candidates else None
                baseline_ratio = ((baseline / frontier if fam.sense == 'max' else frontier / baseline)
                                  if baseline is not None and baseline > 0 else None)
                records.append({'family': task, 'plot_seed': plot_seed,
                                'source_tier': r.get('source_tier'), 'source_seed': r.get('source_seed', plot_seed),
                                'params': params, 'sense': fam.sense, 'reference': frontier,
                                'anchor': bound, 'anchor_kind': kind, 'anchor_ratio': bound_ratio,
                                'baseline': baseline, 'baseline_ratio': baseline_ratio})
            if not records:
                raise ValueError(f'No instances for {family}, {reference_type}')
            n = len(records); kinds = sorted({r['anchor_kind'] for r in records})
            baseline_ratios = [r['baseline_ratio'] for r in records if r['baseline_ratio'] is not None]
            groups[family, reference_type] = {
                'n': n, 'anchor_ratio': sum(r['anchor_ratio'] for r in records) / n,
                'baseline_ratio': sum(baseline_ratios) / n if len(baseline_ratios) == n else None,
                'anchor_kind': kinds[0] if len(kinds) == 1 else 'mixed', 'anchor_kinds': kinds,
                'anchor_is_proven': all(k in ('bound', 'trivial') for k in kinds), 'instances': records,
            }
    return groups


def scale_family_label(family, group):
    """Show field sizes to distinguish the two AP-free reference groups."""
    if family == 'apfree_q':
        spaces = r',\,'.join(rf'\mathbb{{F}}_{{{q}}}^n'
                            for q in sorted({r['params']['q'] for r in group['instances']}))
        return f'AP-free (${spaces}$)'
    return PRETTY.get(family, family)


def draw_scale_anchor(ax, y, ratio, kind, *, xmax=60, color=None, linewidth=3,
                      tick_color='k', tick_size=9):
    """Continuous spans; dashed endpoint ticks identify conjectured targets."""
    color = S.GRID if color is None else color
    if ratio > xmax:
        ax.annotate('', xy=(xmax, y), xytext=(1, y),
                    arrowprops={'arrowstyle': '->', 'color': color, 'lw': linewidth}, zorder=1)
    else:
        ax.plot([1, ratio], [y, y], color=color, lw=linewidth,
                solid_capstyle='butt', zorder=1)
        tick = '|'
        if kind not in ('bound', 'trivial'):
            from matplotlib.path import Path
            # A dashed vertical marker keeps the endpoint's size fixed in points.
            tick = Path([(0, -.5), (0, -.3), (0, -.1), (0, .1), (0, .3), (0, .5)],
                        [Path.MOVETO, Path.LINETO] * 3)
        ax.plot(ratio, y, marker=tick, color=tick_color, ms=tick_size, zorder=2)


def tool_scale_values():
    """Use the same family/reference split as the tool-free points, retaining zeroes."""
    from tool_results import load_all
    values = {}
    for sid, system in load_all().items():
        grouped = {}
        for row in system['cases']:
            key = (row['family_group'], row['reference_type'])
            grouped.setdefault(key, []).append(row['reference_ratio'])
        values[sid] = {
            'label': system['label'], 'baseline_id': system['baseline_id'],
            'groups': {key: {'n': len(xs), 'mean': sum(xs) / len(xs)} for key, xs in grouped.items()},
        }
    return values


def fig_scale(tier="A3"):
    ref, rows = load_formal() if tier == "A3" else load(tier); fams, lit, tf = split_families(ref)
    order = lit + tf
    reference_groups = scale_reference_values(ref)
    tools = tool_scale_values() if tier == 'A3' else {}
    offsets = {'astra_tools': .27, 'luna_tools': -.27}
    tool_handles = []
    fig, ax = plt.subplots(figsize=(S.WIDTH, 4.15))
    for i, f in enumerate(order):
        published = i < len(lit)
        summary = reference_groups[f, 'published' if published else 'construction']
        rb, kind = summary['anchor_ratio'], summary['anchor_kind']
        y = len(order) - i + int(published)
        draw_scale_anchor(ax, y, rb, kind)
        ax.plot(1, y, marker="|", color="k", ms=9, zorder=3)
        for (m, c, name, col) in SYSTEMS:
            v = system_values(rows, ref, m, c + "#" + tier, [f],
                              kind_filter="literature" if published else "textbook").get(f)
            if v:
                mean = float(np.mean(v))
                ax.plot(max(mean, .001), y, S.config_style(m,c)["marker"] if mean >= .001 else "x", color=col, ms=S.MARKER, zorder=4, label=name if i == 0 else None)
        for sid, system in tools.items():
            group = system['groups'][f, 'published' if published else 'construction']
            assert group['n'] == summary['n']
            mean = group['mean']; baseline = system['baseline_id']
            point, = ax.plot(max(mean, .001), y + offsets[sid],
                             marker=S.MARKERS[baseline] if mean >= .001 else 'x',
                             linestyle='none', markerfacecolor='white', markeredgecolor=S.color(baseline),
                             color=S.color(baseline), markeredgewidth=1.05, ms=4.6, zorder=5)
            if i == 0:
                tool_handles.append(point)
    ax.set_yticks([len(order)-i+int(i<len(lit)) for i in range(len(order))])
    ax.set_yticklabels([scale_family_label(f, reference_groups[f, 'published' if i < len(lit) else 'construction'])
                        for i, f in enumerate(order)])
    ax.set_ylim(.25, len(order)+2)
    ax.set_xscale("log"); ax.set_xlim(.0007, 60)
    ax.axvline(1, **S.REFERENCE); ax.text(1.05, len(order)+1.6, "Relative quality = 1", fontsize=S.NOTE)
    ax.axhline(len(order) - len(lit) + .9, color=S.T.MUTED, lw=0.5, ls="--")
    ax.text(.0008, len(order) + 1.6, "Published frontiers", fontsize=S.NOTE, color=S.T.MUTED)
    ax.text(.0008, len(order) - len(lit) + .6, "Construction baselines", fontsize=S.NOTE, color=S.T.MUTED,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": .4})
    ax.set_xlabel("Relative quality (log scale)")
    ax.grid(axis="x")
    S.legend(fig, *ax.get_legend_handles_labels(), ncol=3, y=.048 if tools else .01)
    if tools:
        S.legend(fig, tool_handles, [s['label'] for s in tools.values()], ncol=2, y=.002)
    fig.subplots_adjust(left=.245, right=.965, bottom=.295 if tools else .255, top=.96)
    save(fig, "fig1_scale")
    if tier == 'A3':
        from pathlib import Path
        data = {'grey_span_start_ratio': 1.0, 'aggregation': 'Arithmetic mean of per-instance normalized anchor ratios over the same family/reference group as model points; normalize before averaging and clip only for display.',
                'groups': [{'family': f, 'reference_type': kind, **s}
                           for (f, kind), s in reference_groups.items()]}
        (Path(ROOT) / 'bench/paper/tables/scale_reference_data.json').write_text(json.dumps(data, indent=2) + '\n')


# ---------------------------------------------------------------- Fig 2: headline
def fig_headline(tier="A3"):
    ref, rows = load_formal() if tier == "A3" else load(tier); fams, lit, tf = split_families(ref)
    fig, axes = plt.subplots(1, 2, figsize=(S.WIDTH, 3.3), sharey=True)
    for ax, sub, title in ((axes[0], lit, "Published frontiers\n30 instances"), (axes[1], tf, "Construction baselines\n39 instances")):
        names = []
        for i, (m, c, name, col) in enumerate(SYSTEMS):
            v = [x for xs in system_values(rows, ref, m, c + "#A3", sub,
                 kind_filter="literature" if sub is lit else "textbook").values() for x in xs]
            lo, hi = ci(v);mean = np.mean(v);names.append(name)
            ax.errorbar(mean, i, xerr=[[mean-lo], [hi-mean]], fmt=S.config_style(m,c)["marker"], color=col, ms=S.MARKER, capsize=S.CAP, lw=S.LINE)
        ax.axvline(1, **S.REFERENCE)
        ax.set_yticks(range(len(names)));ax.set_yticklabels(names, fontsize=S.TICK)
        ax.set_xlim(0, 1.4);ax.set_title(title, fontsize=S.TITLE)
        ax.set_xlabel("Mean relative quality (95% CI)", fontsize=S.LABEL)
        ax.grid(axis="x")
    axes[0].invert_yaxis();fig.tight_layout();save(fig, "fig2_headline")


# ---------------------------------------------------------------- Fig 3: tiers
def inst_values(rows, ref, model, cfg, fams, fn=frontier_ratio):
    """{(family, seed): value} for one system."""
    out = {}; tasks = expand_groups(fams)
    for (fm, s), r in sorted(rows.get((model, cfg), {}).items()):
        if fm not in tasks or (fm, s) not in ref: continue
        require_scored(r)
        x = val(fn(FAMILIES[fm], ref[(fm, s)]["params"], ref[(fm, s)]["naive"], r["objective"], r["feasible"], ref[(fm, s)]["objective"]))
        if x is not None: out[(fm, s)] = x
    return out


def fig_tiers():
    tiers = ["A1", "A2", "A3"]; data = {t: load(t) for t in tiers}
    from formal_cohort import formal_a3_view
    data['A3']=formal_a3_view(*data['A3'])
    fig, ax = plt.subplots(figsize=(S.WIDTH, 2.8))
    for (m, c, name, col) in LEGACY_SYSTEMS:
        pts = []
        for t in tiers:
            ref, rows = data[t]; fams, lit, tf = _split_families(ref, "core12")
            iv = system_values(rows, ref, m, c + ("#" + t if t != "A1" else ""), fams)
            values = [x for xs in iv.values() for x in xs]
            pts.append((np.mean(values), len(iv)) if values else (None, 0))
        xs = [i for i, (v, n) in enumerate(pts) if v is not None]
        if len(xs) < 2: continue
        counts = "/".join(str(n) if v is not None else "-" for v,n in pts)
        ax.plot(xs, [pts[i][0] for i in xs], **S.config_style(m,c), label=f"{name} [{counts}]")
    ax.axhline(1, **S.REFERENCE)
    ax.set_xticks(range(3)); ax.set_xticklabels(["A1", "A2", "A3"])
    ax.set_ylabel("Mean relative quality"); ax.set_ylim(0, 1.25);ax.set_xlim(-.12,2.18);ax.set_xlabel("Parameter range");ax.grid(axis="y")
    S.legend(fig, *ax.get_legend_handles_labels(), ncol=2)
    fig.subplots_adjust(left=.135, right=.97, bottom=.40, top=.96)
    save(fig, "fig3_tiers")


# ---------------------------------------------------------------- Fig 4: effort ladder at A2
LADDER = [
    (MODEL_NAMES["gpt-6-astra"], "gpt-6-astra", [("medium", "codex-medium@nocap"), ("high", "codex-high@nocap"), ("xhigh", "codex-xhigh@nocap")], S.color("astra_high")),
]


EFFORTS = ["low", "medium", "high", "xhigh"]


def effort_values(rows, ref, fams, min_rows=20):
    """Common parameter settings across substantive effort runs; repeats averaged within each setting."""
    series = []; tasks = expand_groups(fams)
    for name, model, levels, colour in LADDER:
        eligible = {}
        for level, config in levels:
            selected = [(key, r) for key, r in rows.get((model, config + "#A2"), {}).items()
                        if key[0] in tasks and key in ref]
            if len(selected) < min_rows:
                continue
            grouped = {}
            for (family, seed), row in selected:
                require_scored(row)
                rr = ref[family, seed]
                score = val(frontier_ratio(FAMILIES[family], rr["params"], rr["naive"],
                                           row["objective"], row["feasible"], rr["objective"]))
                if score is not None:
                    key = (family, json.dumps(rr["params"], sort_keys=True))
                    grouped.setdefault(key, []).append((score, float(row["feasible"])))
            eligible[level] = {key: (float(np.mean([v[0] for v in repeats])),
                                     float(np.mean([v[1] for v in repeats]))) for key, repeats in grouped.items()}
        if len(eligible) < 2:
            continue
        common = sorted(set.intersection(*(set(v) for v in eligible.values())))
        if not common:
            continue
        points = {lv: {"hfr": float(np.mean([v[k][0] for k in common])),
                       "valid": float(np.mean([v[k][1] for k in common]))} for lv, v in eligible.items()}
        series.append({"name": name, "model": model, "colour": colour, "n": len(common), "points": points})
    return series


def fig_effort(tier="A2", min_rows=20):
    """Compare Astra effort levels on their shared smaller instances."""
    ref, rows = load_formal() if tier == "A3" else load(tier); fams, lit, tf = split_families(ref)
    fig, ax = plt.subplots(figsize=(S.WIDTH, 2.2))
    series_list = effort_values(rows, ref, fams, min_rows)
    observed = sorted({EFFORTS.index(lv) for series in series_list for lv in series["points"]})
    for series in series_list:
        points = series["points"]; levels = [lv for lv in EFFORTS if lv in points]
        xs = [EFFORTS.index(lv) for lv in levels]
        lab = f"{series['name']} (n = {series['n']})"
        ax.plot(xs, [points[lv]["hfr"] for lv in levels], color=series["colour"],
                marker=S.config_style(series["model"], "")["marker"], ms=S.MARKER, lw=S.LINE, label=lab)
        for x,level in zip(xs,levels):
            below_reference=points[level]["hfr"] < 1
            ax.annotate(f"{points[level]['hfr']:.2f}",(x,points[level]["hfr"]),
                        xytext=(-8,0) if below_reference else (0,7),textcoords="offset points",
                        ha="right" if below_reference else "center",
                        va="center" if below_reference else "bottom",fontsize=S.NOTE)
    ax.set_ylabel("Mean relative quality"); ax.set_ylim(0, 1.25); ax.axhline(1, **S.REFERENCE)
    ax.set_xlabel("Reasoning effort");ax.grid(axis="y")
    ax.set_xticks(observed); ax.set_xticklabels([EFFORTS[i] for i in observed])
    if observed: ax.set_xlim(min(observed) - .3, max(observed) + .3)
    S.legend(fig, *ax.get_legend_handles_labels(), ncol=1)
    fig.tight_layout(rect=[0,.18,1,1], pad=.85)
    save(fig, "fig4_effort")


# ---------------------------------------------------------------- Fig 5: compute-only baseline at A3
def fig_search(tier="A3"):
    from search_evidence import collect, SEARCH_BUDGET_FAMILIES
    _, rows = load_formal() if tier == "A3" else load(tier)
    selected = {(m, c + "#" + tier): rows.get((m, c + "#" + tier), {}) for m, c, *_ in SYSTEMS}
    evidence = collect(selected, tier, families=SEARCH_BUDGET_FAMILIES, grouped=True)
    order = [f for f in evidence if f not in SEARCH_GROUPS] + [f for f in evidence if f in SEARCH_GROUPS]
    fig, ax = plt.subplots(figsize=(S.WIDTH, 2.1))
    x = np.arange(len(order)); width = .24
    for field, offset, colour, label in [
        ("raw_mean", -width, S.METRICS["raw_search"], "Search: 600 s / 10 s"),
        ("zero_mean", 0, S.METRICS["retained_search"], "Baseline: 600 s / 10 s"),
        ("model_mean", width, S.METRICS["best_model"], "Best model / 10 s search"),
    ]:
        values = [evidence[f][field] for f in order]
        ax.bar(x + offset, [v if v is not None else np.nan for v in values], width=width, color=colour, label=label)
        for i, value in enumerate(values):
            if value is None:
                ax.plot(i + offset, 0, "x", color=colour, ms=4, clip_on=False)
    nres = sum(f not in SEARCH_GROUPS for f in order)
    ax.axvline(nres - .5, color=S.T.MUTED, lw=.7, ls="--")
    ax.axhline(0, color="black", lw=.6)
    ax.axhline(math.log(1.1), color=S.T.MUTED, lw=.7, ls=":")
    ax.text(.99, math.log(1.1), "ln 1.1", transform=ax.get_yaxis_transform(), ha="right", va="bottom", fontsize=S.NOTE)
    ax.text((nres - 1)/2, 1.02, f"Search-resistant ({nres})", transform=ax.get_xaxis_transform(), ha="center", fontsize=S.TICK)
    ax.text((nres + len(order) - 1)/2, 1.02, f"Search can help ({len(order)-nres})", transform=ax.get_xaxis_transform(), ha="center", fontsize=S.TICK)
    ax.set_xticks(x)
    labels = {"matmul": "matrix\nmultiplication", "lineq": "linear-equation-\nfree sets"}
    ax.set_xticklabels([labels.get(f, PRETTY.get(f, f)) for f in order], rotation=38, ha="right", fontsize=S.TICK)
    ax.set_ylabel("Log ratio")
    ax.grid(axis="y")
    S.legend(fig, *ax.get_legend_handles_labels(), ncol=3)
    fig.subplots_adjust(left=.12, right=.98, bottom=.49, top=.87)
    save(fig, "fig5_search")


if __name__ == "__main__":
    which = sys.argv[1:] or ["scale", "headline", "tiers", "effort", "search"]
    for w in which:
        try:
            globals()["fig_" + w]()
        except Exception as e:  # keep going; report
            import traceback; traceback.print_exc(); print("FAILED", w, e)
