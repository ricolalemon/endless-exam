"""Plot selected formal responses: Overall score versus reported output tokens.

No inference or publication-selection changes. Run with the paper Python env.
"""
import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator

import publication_data as P
import plot_style as S
import visual_theme as T


def collect():
    summaries = P.summaries()
    cases = P.C.cases()
    cache, sources, systems = {}, {}, []
    for sid in P.ORDER:
        system = P.REGISTRY[sid]
        records = []
        for case in cases:
            row = P.C.get_row(system, case, cache)
            assert row is not None
            path, _ = P.C.source_path(system, case)
            sources[str(path.relative_to(P.ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
            usage = row.get("usage") or {}
            tokens = usage.get("output_tokens", usage.get("completion_tokens"))
            provenance = "provider usage"
            if tokens is None and row.get("provider") == "claude-cli":
                # The legacy bridge used this name for TOTAL output, not reasoning only.
                raw = P.ROOT / "bench/results/headless" / (
                    f"{case['tier']}-{row['base_config']}-{case['family']}-{case['seed']}.json"
                )
                tokens = row.get("reasoning_tokens")
                assert tokens is not None
                provenance = "legacy total-output field (headless_claude.py / agent_bridge.py)"
                if raw.exists():
                    native = json.loads(raw.read_text())
                    assert tokens == (native.get("usage") or {}).get("output_tokens")
                    assert any("fable" in model for model in native.get("modelUsage", {}))
                    sources[str(raw.relative_to(P.ROOT))] = hashlib.sha256(raw.read_bytes()).hexdigest()
                    provenance = "legacy total-output field verified against native usage"
            assert tokens is None or isinstance(tokens, int) and tokens >= 0
            complete = (tokens is not None and row.get("usage_complete") is not False
                        and not row.get("interrupted_usage_unknown", False))
            records.append({"tier": case["tier"], "family": case["family"], "seed": case["seed"],
                            "output_tokens": tokens, "usage_complete": complete,
                            "provenance": provenance if tokens is not None else "not reported"})
        total = sum(r["output_tokens"] for r in records if r["output_tokens"] is not None)
        systems.append({"id": sid, "label": system[2],
                        "overall_score": summaries[sid]["overall"]["score"],
                        "reported_output_tokens": total,
                        "is_lower_bound": any(not r["usage_complete"] for r in records),
                        "known_usage_instances": sum(r["output_tokens"] is not None for r in records),
                        "complete_usage_instances": sum(r["usage_complete"] for r in records),
                        "instances": len(records), "records": records})
    assert len(systems) == len(P.ORDER) and all(s["instances"] == 69 for s in systems)
    # Keep the figure aligned with the current public-facing leaderboard.
    published = json.loads((P.HERE / "tables/publication_data.json").read_text())
    for system in systems:
        assert abs(system["overall_score"] - published["systems"][system["id"]]["overall"]["score"]) < 1e-9
    from tool_results import load_all
    for sid, tool in load_all().items():
        sources[tool['source']] = tool['source_sha256']
        systems.append({'id': sid, 'baseline_id': tool['baseline_id'], 'label': tool['label'],
                        'overall_score': tool['overall']['score'],
                        'reported_output_tokens': tool['usage']['outputTokens'], 'is_lower_bound': False,
                        'known_usage_instances': 69, 'complete_usage_instances': 69, 'instances': 69,
                        'records': [{'tier': r['tier'], 'family': r['family'], 'seed': r['seed'],
                                     'output_tokens': r['usage']['outputTokens'], 'usage_complete': True,
                                     'provenance': 'sum of native response usage over the tool trajectory'}
                                    for r in tool['cases']]})
    return {
        "tracks": ["tool-free", "tool-assisted"], "instances": 69,
        "score_definition": "100 times the mean relative quality over the 69 distinct instances; uncapped",
        "token_definition": "Reported output tokens, including reasoning, for the 69 selected responses. "
                            "Input tokens and earlier failed/superseded submissions are excluded. "
                            "For tools, count all model responses in the selected trajectory. "
                            "Unknown or interrupted usage makes the reported sum a lower bound.",
        "systems": systems, "source_sha256": sources,
    }


def draw(data, out):
    S.apply()
    fig, ax = plt.subplots(figsize=(10.4, 6.7))
    fig.subplots_adjust(left=.095, right=.97, bottom=.18, top=.85)
    fig.text(.095, .948, "Overall score vs. token usage", fontsize=17, weight="bold")
    fig.text(.095, .904, f"69 instances  ·  {len(P.ORDER)} tool-free configurations  ·  Astra and Luna high with code and web",
             fontsize=10.5, color=T.MUTED)

    ax.set(xlim=(0, 7.35), ylim=(0, 160), xlabel="Reported output tokens across 69 instances (millions)",
           ylabel="Overall score")
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.yaxis.set_major_locator(MultipleLocator(20))
    ax.tick_params(labelsize=9)
    ax.xaxis.label.set_size(11)
    ax.yaxis.label.set_size(11)
    ax.xaxis.labelpad = 10
    ax.yaxis.labelpad = 10
    ax.grid(axis="y", linewidth=.65)
    ax.axhline(100, color=T.OCHRE, linewidth=.9, linestyle=(0, (4, 4)), alpha=.7)
    ax.text(7.28, 101.5, "Reference parity = 100", ha="right", va="bottom", fontsize=9, color=T.MUTED)

    offsets = {
        "astra_tools": (10, 12, "left"), "luna_tools": (10, 10, "left"),
        "astra_high": (9, 10, "left"), "astra_medium": (9, 10, "left"),
        "fable": (10, 10, "left"), "fable_high": (10, -10, "left"), "luna_high": (10, 12, "left"),
        "luna_medium": (10, 12, "left"), "deepseek_low": (0, 12, "center"),
        "deepseek_high": (0, 12, "center"), "qwen38": (0, -20, "center"),
    }
    # Separate the three closely spaced Qwen3.5 labels with light leader lines.
    leaders = {"qwen35": (3.35, 24.5, "right"), "qwen9": (4.45, 17.5, "left"),
               "qwen4": (4.15, 5.5, "left")}
    annotations = []
    for system in data["systems"]:
        sid = system["id"]
        x, y = system["reported_output_tokens"] / 1e6, system["overall_score"]
        tool = 'baseline_id' in system; style_id = system.get('baseline_id', sid)
        color = S.color(style_id)
        ax.scatter(x, y, s=100 if tool else 77, marker=S.MARKERS[style_id], facecolor='white' if tool else color,
                   edgecolor=color if tool else "white", linewidth=1.5 if tool else .9, zorder=5)
        text = system["label"] + (r"$^{*}$" if system["is_lower_bound"] else "")
        if sid in leaders:
            tx, ty, ha = leaders[sid]
            label = ax.annotate(text, xy=(x, y), xytext=(tx, ty),
                                textcoords="data", ha=ha, va="center", fontsize=9.4,
                                arrowprops={"arrowstyle": "-", "color": T.NEUTRAL,
                                            "lw": .9, "shrinkA": 4, "shrinkB": 7})
        else:
            dx, dy, ha = offsets[sid]
            label = ax.annotate(text, xy=(x, y), xytext=(dx, dy),
                                textcoords="offset points", ha=ha, va="center", fontsize=9.4)
        annotations.append(label)

    fig.text(.095, .066, "Includes reasoning. * Some usage was not reported; plotted totals are lower bounds.",
             fontsize=8.5, color=T.MUTED)
    fig.text(.095, .035, "Overall score is uncapped, with reference parity at 100.",
             fontsize=9, color=T.MUTED)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for label in annotations:
        box = label.get_window_extent(renderer)
        assert fig.bbox.contains(box.x0, box.y0) and fig.bbox.contains(box.x1, box.y1), label.get_text()
    for ext in ("png", "svg"):
        fig.savefig(out / f"overall-score-vs-tokens.{ext}", dpi=200, facecolor="white")
    plt.close(fig)


def draw_paper(data):
    """Paper-width vector figure; the LaTeX caption carries the explanatory note."""
    S.apply()
    fig, ax = plt.subplots(figsize=(S.WIDTH, 2.40))
    fig.subplots_adjust(left=.10, right=.985, bottom=.17, top=.965)
    ax.set(xlim=(0, 7.5), ylim=(0, 160), xlabel="Reported output tokens (millions)",
           ylabel="Overall score")
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.yaxis.set_major_locator(MultipleLocator(20))
    ax.grid(axis="y")
    ax.axhline(100, color=T.OCHRE, linewidth=.8, linestyle=(0, (4, 4)), alpha=.7)
    ax.text(7.4, 101.5, "Reference parity", ha="right", fontsize=6.5, color=T.MUTED)
    positions = {
        "astra_tools": (.68, 143, "left"), "luna_tools": (1.10, 120, "left"),
        "astra_high": (1.23, 89, "left"), "astra_medium": (.49, 66, "left"),
        "fable": (2.85, 73, "left"), "fable_high": (5.62, 42, "left"), "luna_medium": (.47, 18, "left"),
        "luna_high": (1.27, 37, "left"), "deepseek_low": (3.49, 48, "center"),
        "deepseek_high": (5.1, 56, "center"), "qwen38": (7.15, 28, "right"),
        "qwen35": (4.55, 23.5, "left"), "qwen9": (4.55, 13.5, "left"),
        "qwen4": (4.55, 5.5, "left"),
    }
    for system in data["systems"]:
        sid = system["id"]
        x, y = system["reported_output_tokens"] / 1e6, system["overall_score"]
        tool = 'baseline_id' in system; style_id = system.get('baseline_id', sid)
        color = S.color(style_id)
        ax.scatter(x, y, s=48 if tool else 33, marker=S.MARKERS[style_id], facecolor='white' if tool else color,
                   edgecolor=color if tool else "white", linewidth=1.1 if tool else .65, zorder=5)
        model, effort = system["label"].rsplit(" ", 1)
        text = model if sid.startswith("qwen") else f"{model}\n{effort}"
        if tool:
            text = system['label'].replace(' high + tools', '\nhigh + tools')
        if system["is_lower_bound"]:
            text += r"$^{*}$"
        tx, ty, ha = positions[sid]
        kwargs = {}
        if sid in ("qwen4", "qwen9", "qwen35"):
            kwargs["arrowprops"] = {"arrowstyle": "-", "color": T.NEUTRAL,
                                    "lw": .7, "shrinkA": 3, "shrinkB": 5}
        ax.annotate(text, xy=(x, y), xytext=(tx, ty), fontsize=6.8,
                    ha=ha, va="center", linespacing=1.1, **kwargs)
    S.save(fig, "fig_score_tokens")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=P.ROOT / "output/figures/score-vs-tokens")
    parser.add_argument("--paper", action="store_true", help="Also generate the paper-width PDF and PNG")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    data = collect()
    (args.out / "data.json").write_text(json.dumps(data, indent=2) + "\n")
    draw(data, args.out)
    if args.paper:
        draw_paper(data)
    for s in data["systems"]:
        print(s["label"], f"score={s['overall_score']:.2f}",
              f"tokens={'≥' if s['is_lower_bound'] else ''}{s['reported_output_tokens']:,}")
    print(args.out / "overall-score-vs-tokens.png")


if __name__ == "__main__":
    main()
