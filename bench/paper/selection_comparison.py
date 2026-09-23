"""Recompute original/core selections on the same saved answers; emit the manuscript sensitivity table."""
import hashlib
import json
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from figs import SYSTEMS
import freeze_frontier
from report import load, split_families, system_values, ci
from openceiling import closed_gap
from family_catalog import expand_groups, CORE12_GROUPS
from formal_cohort import formal_a3_view

ROOT = HERE.parents[1]
EXTRA = []


def main():
    ref, rows = formal_a3_view(*load("A3"),keep_controls=('kakeya',))
    result = {"aggregation": "One response per formal instance; the separate Kakeya control retains its original repeat aggregation.",
              "core_groups": CORE12_GROUPS, "snapshots": {}, "systems": {}}
    for selection, snapshot in [("legacy15", "v1"), ("core12", "v1-core")]:
        freeze_frontier.load(snapshot)
        path = ROOT / f"bench/frontiers/{snapshot}.json"
        result["snapshots"][selection] = {"file": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        fams, lit, tf = split_families(ref, selection)
        # Formal-only collections have no additional Kakeya controls. Keep this
        # historical sensitivity analysis restricted to its paired observations.
        control_systems=[s for s in SYSTEMS if any(family=='kakeya'
                         for family,seed in rows.get((s[0],s[1]+'#A3'),{}))]
        for model, config, name, _ in [*control_systems, *EXTRA]:
            cfg = config + "#A3"
            selected = [r for (f, _), r in rows.get((model,cfg), {}).items() if f in expand_groups(fams,selection)]
            if not selected: continue
            key = model + ":" + config
            system = result["systems"].setdefault(key, {"name": name, "in_paper": any(m==model and c==config for m,c,*_ in SYSTEMS)})
            values = {}
            for panel, fs, kind in [("published", lit, "literature"), ("stand_in", tf, "textbook")]:
                grouped = system_values(rows,ref,model,cfg,fs,kind_filter=kind,selection=selection)
                flat = [v for vs in grouped.values() for v in vs]
                values[panel] = {"n":len(flat),"mean":statistics.mean(flat),"ci":ci(flat),
                                 "records":sum(v>1+1e-9 for v in flat) if panel=="published" else None,
                                 "family_balanced_mean":statistics.mean(statistics.mean(vs) for vs in grouped.values())}
            gap = [v for vs in system_values(rows,ref,model,cfg,fams,fn=closed_gap,selection=selection).values() for v in vs]
            values.update(calls=len(selected),valid=sum(r["feasible"] for r in selected)/len(selected),headroom=statistics.mean(gap))
            system["core" if selection=="core12" else selection] = values
    for system in result["systems"].values():
        assert system["legacy15"]["published"] == system["core"]["published"]
        assert system["legacy15"]["calls"] - system["core"]["calls"] == 5
    freeze_frontier.load("v1-core")
    out = HERE / "tables/selection_comparison.json"
    out.write_text(json.dumps(result,indent=2)+"\n")
    md = ["# 家族精简重算", "", "原 15 家族与 12 家族核心集合使用相同答案；球面码和 Heilbronn 的子任务均保留。",
          "合并标签不改变实例权重。两套集合的差别是将 Kakeya 移至对照。已发表前沿面板的均值、区间及记录数完全相同。", "",
          "| 配置 | 旧参照面板 | 核心参照面板 | 旧 headroom | 核心 headroom | 核心调用数 |", "|---|---:|---:|---:|---:|---:|"]
    tex = [r"\begin{tabular}{@{}lrrrr@{}}",r"\toprule",r"configuration & \shortstack{Relative quality\\$+K$} & \shortstack{Relative quality\\$-K$} & \shortstack{Gap closed\\$+K$} & \shortstack{Gap closed\\$-K$} \\",r"\midrule"]
    for system in result["systems"].values():
        old,new=system["legacy15"],system["core"]
        md.append(f"| {system['name']} | {old['stand_in']['mean']:.3f} | {new['stand_in']['mean']:.3f} | {old['headroom']:.3f} | {new['headroom']:.3f} | {new['calls']} |")
        if system["in_paper"]:
            name=system["name"]
            tex.append(f"{name} & {old['stand_in']['mean']:.3f} & {new['stand_in']['mean']:.3f} & {old['headroom']:.3f} & {new['headroom']:.3f}" + r" \\")
    tex += [r"\bottomrule",r"\end{tabular}"]
    md += ["", "此敏感性分析使用当前十一配置的原十二家族与 Kakeya 对照；完整十四家族主表另含两种码家族。JSON 同时保留每组等权的辅助敏感性数值；正式汇总继续采用实例等权。", ""]
    (HERE/"tables/selection_comparison.tex").write_text("\n".join(tex)+"\n")
    (out.with_suffix(".md")).write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
