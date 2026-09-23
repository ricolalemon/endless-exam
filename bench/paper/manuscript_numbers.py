#!/usr/bin/env python3
"""Generate the manuscript's result macros from the same frozen data and aggregation as its figures."""
import json
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from figs import SYSTEMS, split_families, system_values, effort_values
from report import load, ci
from publication_data import load_formal, summaries as formal_summaries, ORDER, REGISTRY
from openceiling import HEADROOM, FAMILIES, closed_gap, frontier_ratio, anchor, human_frontier, effective_frontier
from family_catalog import expand_groups, CORE_GROUPS
from evaluation_outcomes import require_scored


def generate():
    ref, rows = load_formal()
    fams, lit, tf = split_families(ref)
    by_id = formal_summaries()
    summaries = {REGISTRY[sid][1] + ":" + REGISTRY[sid][3]: v for sid, v in by_id.items()}
    high, medium = by_id["astra_high"], by_id["astra_medium"]
    # The main-text zero-breakthrough observation is a rescore of the same calls.
    if any(s["p1"]["binary_breakthrough_rate"] > 0 for s in by_id.values()):
        raise ValueError('New results include published-frontier breakthroughs. Revise the zero-breakthrough prose before rebuilding; retain the new outcomes.')
    vals = {"FamilyCount": 14, "EvaluatedFamilyCount": 14, "ModelCount": len({REGISTRY[s][1] for s in ORDER}), "ConfigCount": len(ORDER),
            "AThreeCalls": 69, "PanelOneN": 30, "PanelTwoN": 39, "DistinctN": 69,
            "POneMin": f"{min(s['p1']['mean'] for s in by_id.values()):.2f}",
            "POneMax": f"{max(s['p1']['mean'] for s in by_id.values()):.2f}",
            "ScoreMin": f"{min(s['overall']['score'] for s in by_id.values()):.2f}",
            "ScoreMax": f"{max(s['overall']['score'] for s in by_id.values()):.2f}",
            "AstraHighScore": f"{high['overall']['score']:.2f}",
            "AstraMedScore": f"{medium['overall']['score']:.2f}",
            "FableScore": f"{by_id['fable']['overall']['score']:.2f}",
            "FableHighScore": f"{by_id['fable_high']['overall']['score']:.2f}",
            "OpusHighScore": f"{by_id['opus55_high']['overall']['score']:.2f}",
            "OpusMediumScore": f"{by_id['opus55_medium']['overall']['score']:.2f}",
            "OpusHighValid": by_id['opus55_high']['accepted'],
            "OpusMediumValid": by_id['opus55_medium']['accepted'],
            "OpusHighBudgetStops": sum(r.get('finish_reason')=='length' for r in rows[REGISTRY['opus55_high'][1],REGISTRY['opus55_high'][3]+'#A3'].values()),
            "FableHighBudgetStops": sum(r.get('finish_reason')=='length' for r in rows[REGISTRY['fable_high'][1],REGISTRY['fable_high'][3]+'#A3'].values()),
            "BinaryBreakthroughMaxPct": f"{100*max(s['p1']['binary_breakthrough_rate'] for s in by_id.values()):.0f}",
            "PTwoMin": f"{min(s['p2']['mean'] for s in by_id.values()):.2f}",
            "PTwoMax": f"{max(s['p2']['mean'] for s in by_id.values()):.2f}",
            "AstraHighPOne": f"{high['p1']['mean']:.2f}", "AstraMedPOne": f"{medium['p1']['mean']:.2f}",
            "AstraHighPTwo": f"{high['p2']['mean']:.2f}", "AstraMedPTwo": f"{medium['p2']['mean']:.2f}",
            "AstraHighCILow": f"{high['p1']['ci'][0]:.2f}", "AstraHighCIHigh": f"{high['p1']['ci'][1]:.2f}",
            "AstraMedValidPct": f"{100*medium['valid']:.0f}", "AstraHighValidPct": f"{100*high['valid']:.0f}",
            "AstraMedValidCalls": medium['accepted'], "AstraHighValidCalls": high['accepted'],
            "HeadroomMaxPct": f"{100*max(s['headroom'] for s in by_id.values()):.1f}",
            "LunaMedPOne": f"{by_id['luna_medium']['p1']['mean']:.2f}",
            "LunaHighPOne": f"{by_id['luna_high']['p1']['mean']:.2f}",
            "FablePOne": f"{by_id['fable']['p1']['mean']:.2f}"}
    graph_key = next(key for key, r in ref.items()
                     if key[0] == "degdiam" and r["params"] == {"d": 4, "k": 5})
    graph_ref = ref[graph_key]
    graph = rows[(REGISTRY["astra_high"][1], REGISTRY["astra_high"][3] + "#A3")][graph_key]
    graph_reference, published = effective_frontier(
        FAMILIES["degdiam"], graph_ref["params"], graph_ref["naive"], graph_ref["objective"])
    assert graph["feasible"] and published
    vals.update({"TaskGraphVertices": int(graph["objective"]),
                 "TaskGraphReference": int(graph_reference),
                 "TaskGraphRatio": f"{graph['objective'] / graph_reference:.3f}"})
    vals.update({"GapN": high["gap_closed"]["n"],
                 "GapPublishedN": high["gap_closed"]["published"]["n"],
                 "GapConstructionN": high["gap_closed"]["construction"]["n"],
                 "TargetN": high["target_progress"]["n"]})
    for macro,sid in [('QwenFourPOne','qwen4'),('QwenNinePOne','qwen9'),('QwenTwentySevenPOne','qwen35')]:
        vals[macro]=f"{by_id[sid]['p1']['mean']:.2f}"
    for macro, family in [("SchurBoundRatio", "schur"), ("APBoundRatio", "apfree_q")]:
        rr = ref[family, 0]
        bound, kind = anchor(FAMILIES[family], rr["params"])
        frontier, published = human_frontier(FAMILIES[family], rr["params"], rr["naive"], rr["objective"])
        assert kind == "bound" and published
        vals[macro] = f"{bound / frontier:.1f}"
    ladder = {}
    for tier in ["L1", "L2", "L3", "L4", "M1", "M2", "M3", "M4"]:
        rr, data = load(tier)
        for model, config in [("gpt-6-astra", "codex-high@nocap"), ("deepseek-flash", "think-low@128k"),
                              ("Qwen/Qwen3.8-27B-FP8", "think-high@128k"),
                              ("gpt-5.6-luna", "codex-high@128k.once-full")]:
            selected = data.get((model, config + "#" + tier), {})
            for family in ["capset", "kissing", "degdiam", "schur", "covering", "apfree"]:
                rs = [(k, r) for k, r in selected.items() if k[0] == family]
                if not rs:
                    continue
                for _,row in rs:require_scored(row)
                scores = [frontier_ratio(FAMILIES[family], rr[k]["params"], rr[k]["naive"], r["objective"],
                                         r["feasible"], rr[k]["objective"])[0] for k, r in rs]
                ladder[model, tier, family] = {"mean": float(np.mean(scores)), "calls": len(rs),
                                               "valid": sum(r["feasible"] for _, r in rs)}
                if model == 'gpt-6-astra' and family == 'capset' and tier in ('L1','L4'):
                    assert len(rs)==2 and all(r['feasible'] for _,r in rs)
                    objectives={r['objective'] for _,r in rs};assert len(objectives)==1
                    objective=objectives.pop();reference_row=rr[rs[0][0]]
                    reference,published=effective_frontier(FAMILIES[family],reference_row['params'],
                                                           reference_row['naive'],reference_row['objective'])
                    bound,kind=anchor(FAMILIES[family],reference_row['params'])
                    assert published and kind=='bound'
                    if tier=='L1':
                        assert objective==reference==bound==112
                        vals['CapLOneSize']=f'{int(objective):,}'
                    else:
                        from run_ladder import extract_json
                        for _,row in rs:
                            factors=extract_json(row['content'])['product']
                            assert len(factors)==2 and all(len(f)==112 and len(f[0])==6 for f in factors)
                        assert objective==112**2
                        vals.update(CapLFourSize=f'{int(objective):,}',
                                    CapLFourReference=f'{int(reference):,}',
                                    CapLFourBound=f'{int(bound):,}',
                                    CapLFourBoundPct=f'{100*objective/bound:.1f}')
    for macro, tier, family in [("CapLThree", "L3", "capset"), ("CapLFour", "L4", "capset"),
                                ("CubicLTwo", "L2", "degdiam"), ("CubicLFour", "L4", "degdiam"),
                                ("QuarticMTwo", "M2", "degdiam"), ("QuarticMFour", "M4", "degdiam")]:
        vals[macro] = f"{ladder['gpt-6-astra', tier, family]['mean']:.2f}"
    for prefix,model in [('Luna','gpt-5.6-luna'),('Qwen','Qwen/Qwen3.8-27B-FP8'),
                         ('DS','deepseek-flash'),('Astra','gpt-6-astra')]:
        assert ladder[model,'L4','degdiam']['mean'] < ladder[model,'L1','degdiam']['mean']
        assert ladder[model,'L4','kissing']['mean'] < ladder[model,'L2','kissing']['mean']
        vals['CubicLFour'+prefix]=f"{ladder[model,'L4','degdiam']['mean']:.2f}"
    for macro, model in [("LadderValidAstra", "gpt-6-astra"), ("LadderValidDS", "deepseek-flash"),
                          ("LadderValidQwen", "Qwen/Qwen3.8-27B-FP8"), ("LadderValidLuna", "gpt-5.6-luna")]:
        vals[macro] = sum(v["valid"] for (m, t, f), v in ladder.items() if m == model and t.startswith("L"))
    vals["LadderCalls"] = sum(v["calls"] for (m, t, f), v in ladder.items() if m == "gpt-6-astra" and t.startswith("L"))
    a2ref, a2rows = load("A2")
    effort = effort_values(a2rows, a2ref, split_families(a2ref)[0])
    for series in effort:
        assert series["model"] == "gpt-6-astra"
        prefix = "Astra"
        vals[prefix + "EffN"] = series["n"]
        for level, p in series["points"].items():
            stem = prefix + {"medium": "Med", "high": "High", "xhigh": "Xhigh"}[level]
            vals[stem + "ATwoHFR"] = f"{p['hfr']:.2f}"
            vals[stem + "ATwoValidPct"] = f"{100*p['valid']:.0f}"
    dest = HERE / "tables/result_numbers.tex"
    dest.write_text("% Generated by bench/paper/manuscript_numbers.py; frozen version 1.\n" +
                    "".join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in vals.items()))
    print(json.dumps({"macros": vals, "headline": summaries, "effort": effort}, indent=2))
    print("wrote", dest)


if __name__ == "__main__":
    generate()
