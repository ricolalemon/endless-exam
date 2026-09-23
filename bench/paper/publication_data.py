"""One publication view of the 69 unique formal instances.

Original result rows and tier identifiers stay immutable. Trifference T1--T4 are
indexed as four separate plotting keys, replacing the earlier literal A3 pilot.
"""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "bench"))
import formal_cohort as C
from evaluation_outcomes import require_scored
import freeze_frontier
freeze_frontier.load("v1-trifference")
from report import system_values, split_families, ci
from openceiling import FAMILIES, closed_gap, conjectured_gap, frontier_ratio, effective_frontier
from result_selection import source_for

ORDER = ["qwen4", "qwen9", "qwen35", "qwen38", "luna_medium", "luna_high",
         "deepseek_low", "deepseek_high", "fable", "fable_high", "opus55_medium", "opus55_high", "astra_medium", "astra_high"]
MODEL_NAMES = {
    "gpt-6-astra": "GPT-6 Astra",
    "gpt-5.6-luna": "GPT-5.6 Luna",
    "claude-fable-5-1": "Claude Fable 5.1",
    "claude-opus-5": "Claude Opus 5",
    "claude-opus-5-5": "Claude Opus 5.5",
    "deepseek-flash": "DeepSeek V4.1 Flash",
    "Qwen/Qwen3.8-27B-FP8": "Qwen3.8-27B",
    "Qwen/Qwen3.5-27B-FP8": "Qwen3.5-27B",
    "Qwen/Qwen3.5-9B": "Qwen3.5-9B",
    "Qwen/Qwen3.5-4B": "Qwen3.5-4B",
}
# Presentation labels include model versions; collection identities stay intact.
REGISTRY = {s[0]: (s[0], s[1], f"{MODEL_NAMES[s[1]]} {s[2].split()[-1]}", *s[3:])
            for s in C.SYSTEMS}
from visual_theme import MODEL_COLORS as COLORS
SYSTEMS = [(REGISTRY[s][1], REGISTRY[s][3], REGISTRY[s][2], COLORS[s]) for s in ORDER]
KEY_TO_ID = {(s[1], s[3]): s[0] for s in C.SYSTEMS}


def case_key(c):
    return c["family"], int(c["tier"][1:]) - 1 if c["family"] == "trifference" else c["seed"]


def selected_source(sid, tier, family, seed, block):
    """Resolve publication provenance through the same explicit replacement map."""
    system=REGISTRY[sid]
    config=system[3] if block in ('core','core12') else system[4]
    path,actual_config=source_for(system[1],config,tier,family,seed,ROOT)
    return {'model':system[1],'configuration':actual_config,'tier':tier,
            'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def strict(row):
    require_scored(row)
    # Same scoring-entry rule as report.load; no edit to the source result.
    if row.get("finish_reason") == "length" or (row.get("reasoning_tokens") or 0) > 128000:
        return dict(row, feasible=False, objective=0)
    return dict(row)


def binary_breakthrough(family, params, naive, objective, feasible, reference):
    """Binarize individual calls before applying the usual repeat aggregation."""
    value, kind = frontier_ratio(family, params, naive, objective, feasible, reference)
    return float(feasible and value is not None and value > 1 + 1e-9), kind


def overall_score(instance_ratios):
    """Score on the evaluated set: 100 times its distinct-instance mean ratio.

    Inputs contain one response per instance and include failures as zero. Reference
    parity is 100; improvements remain uncapped. Subsets use their own size.
    """
    return {"n": len(instance_ratios), "score": 100 * sum(instance_ratios) / len(instance_ratios),
            "ci": tuple(100 * x for x in ci(instance_ratios))}


def load_formal(ids=None, cases=None):
    ids = ORDER if ids is None else ids
    cases = C.cases() if cases is None else cases
    ref, rows, cache = {}, {}, {}
    for c in cases:
        key = case_key(c);assert key not in ref
        frozen = json.loads((ROOT / c["reference_path"]).read_text())
        assert frozen["params"] == c["params"]
        ref[key] = {**frozen, "family": c["family"], "params": c["params"],
                    "objective": frozen["search"], "source_tier": c["tier"], "source_seed": c["seed"]}
        for sid in ids:
            s = REGISTRY[sid];row = C.get_row(s, c, cache)
            if row is None: raise ValueError(f"Missing formal result: {sid} {c}")
            rows.setdefault((s[1], s[3] + "#A3"), {})[key] = strict(row)
    return ref, rows


def summarize_gaps(records):
    """Equal instance weights; proven-bound gaps and conjectured targets stay separate.

    Each record is (family, params, naive, objective, valid, reference_search).
    Eligibility depends on the instance, so invalid responses remain in the mean.
    """
    groups = {"published": [], "construction": []}
    targets = []
    for fam, params, naive, objective, valid, search in records:
        gap, kind = closed_gap(fam, params, naive, objective, valid, search)
        if kind and kind.endswith("!"):
            raise ValueError(f"Verified objective exceeds proven bound: {fam.name} {params}")
        if gap is not None:
            _, published = effective_frontier(fam, params, naive, search)
            groups["published" if published else "construction"].append(gap)
        target, _ = conjectured_gap(fam, params, naive, objective, valid, search)
        if target is not None:
            targets.append(target)
    def mean(values):
        return {"n": len(values), "mean": sum(values)/len(values) if values else None}
    summary = {**mean(groups["published"] + groups["construction"]),
               **{name: mean(values) for name, values in groups.items()}}
    return {"gap_closed": summary, "target_progress": mean(targets),
            "headroom": summary["mean"], "headroom_instances": summary["n"]}


def summaries(ids=None, cases=None):
    ids = ORDER if ids is None else ids
    ref, rows = load_formal(ids, cases);fams, lit, stand = split_families(ref, "core")
    result = {}
    for sid in ids:
        s = REGISTRY[sid];model, config = s[1], s[3] + "#A3"
        panels = {};all_ratios = []
        for label, groups, kind in (("p1", lit, "literature"), ("p2", stand, "textbook")):
            values = [x for xs in system_values(rows, ref, model, config, groups, kind_filter=kind).values() for x in xs]
            panels[label] = {"n": len(values), "mean": sum(values)/len(values), "ci": ci(values),
                             "records": sum(x > 1 + 1e-9 for x in values) if label == "p1" else None}
            all_ratios.extend(values)
        binary = [x for xs in system_values(rows, ref, model, config, lit,
                  fn=binary_breakthrough, kind_filter="literature").values() for x in xs]
        assert len(binary) == panels["p1"]["n"]
        panels["p1"]["binary_breakthrough_rate"] = sum(binary) / len(binary)
        rs = list(rows[model, config].values())
        gaps = summarize_gaps((FAMILIES[r0["family"]], r0["params"], r0["naive"],
                               rows[model, config][key]["objective"], rows[model, config][key]["feasible"],
                               r0["objective"]) for key, r0 in ref.items())
        result[sid] = {"label": s[2], "model": model, "source_core_config": s[3], "source_code_config": s[4],
                       **panels, "overall": overall_score(all_ratios),
                       "calls": len(rs), "accepted": sum(r["feasible"] for r in rs),
                       "valid": sum(r["feasible"] for r in rs)/len(rs), **gaps}
    return result


def code_data():
    manifest = json.loads((ROOT / "bench/results/pilots/code-multimodel-2026-09-15/manifest.json").read_text())
    cases = manifest["cases"];rows = [];cache = {}
    for sid in ORDER:
        for c in cases:
            row = C.get_row(REGISTRY[sid], {**c, "block": "codes"}, cache);assert row is not None
            r = strict(row)
            outcome = "valid" if r["feasible"] else r.get("finish_reason") if r.get("finish_reason") != "stop" else "empty_final" if not r["content"] else "rejected_answer"
            rows.append({"system": sid, "label": REGISTRY[sid][2],
                         **{k: c[k] for k in ("tier", "family", "seed", "params", "reference")},
                         "valid": r["feasible"], "objective": r["objective"], "ratio": r["objective"]/c["reference"],
                         "tokens": r.get("reasoning_tokens"), "latency_s": r.get("latency_s"),
                         "finish_reason": r.get("finish_reason"), "verify_msg": r.get("verify_msg"), "outcome": outcome})
    return cases, rows


def export():
    result = summaries();cases, codes = code_data()
    assert len(result) == len(ORDER) == 14
    assert all((s["calls"], s["p1"]["n"], s["p2"]["n"]) == (69, 30, 39) for s in result.values())
    assert all(s["overall"]["n"] == 69 for s in result.values())
    snapshot = "bench/frontiers/v1-trifference.json"
    sources = {snapshot: hashlib.sha256((ROOT / snapshot).read_bytes()).hexdigest()}
    # The snapshot stores the values; include their independently verified objects
    # and the scoring implementation in the publication provenance as well.
    frontier = json.loads((ROOT / snapshot).read_text())
    construction_files = {e["construction_reference"]["witness"] for e in frontier["entries"].values()
                          if "construction_reference" in e}
    for p in sorted(construction_files | {"bench/openceiling.py", "bench/quadratic_kissing.py", "bench/freeze_frontier.py", "bench/paper/publication_data.py",
                                         "bench/construction_references.json", "bench/formal_cohort.py",
                                         "bench/result_selection.py", "bench/evaluation_outcomes.py", "bench/exam.py",
                                         "bench/data/formal_suite_v1.json", "bench/data/fable_high_publication.json", "bench/data/opus55_publication.json"}):
        sources[p] = hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
    selection = ROOT / 'bench/data/result_replacements.json'
    if selection.exists():
        sources[str(selection.relative_to(ROOT))] = hashlib.sha256(selection.read_bytes()).hexdigest()
        witness = 'bench/data/kissing13_quadratic.json'
        sources[witness] = hashlib.sha256((ROOT / witness).read_bytes()).hexdigest()
        selected = json.loads(selection.read_text())
        replacement_files = {r['result_path'] for r in selected['replacements']}
        replacement_files.update(r['reference_path'] for r in selected['references'])
        for p in replacement_files:
            sources[p] = hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
    for c in C.cases():
        sources[c["reference_path"]] = hashlib.sha256((ROOT / c["reference_path"]).read_bytes()).hexdigest()
        for sid in ORDER:
            path, _ = C.source_path(REGISTRY[sid], c)
            p = str(path.relative_to(ROOT))
            if p not in sources: sources[p] = hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
    data = {"families": 14, "task_variants": 16, "calls_per_configuration": 69, "distinct_instances": 69,
            "published_instances": 30, "stand_in_instances": 39, "snapshot": "v1-trifference",
            "systems": result, "code_cases": codes, "source_sha256": sources,
            "overall_score": {"definition": "100 times the mean relative quality over all 69 distinct instances.",
                              "reference_parity": 100, "clipped": False,
                              "panel_weights": {"published": 30, "stand_in": 39}},
            "gap_closed_definition": {"start": "same fixed reference as the relative quality",
                "endpoint": "proven mathematical bound, including proven trivial bounds",
                "formula": "max(0, log(a/h)/log(b/h)); invert both ratios for minimisation",
                "instances": 64, "published_instances": 30, "construction_instances": 34,
                "conjectured_target_instances_separately": 5},
            "aggregation": "One selected response per instance; equal weight over the 69 unique instances."}
    if selection.exists():
        data['result_selection'] = str(selection.relative_to(ROOT))
    (HERE / "tables/publication_data.json").write_text(json.dumps(data, indent=2) + "\n")
    return data


if __name__ == "__main__":
    data = export()
    for sid, s in data["systems"].items():
        print(sid, f"Score={s['overall']['score']:.2f} HFR={s['p1']['mean']:.3f} stand-in={s['p2']['mean']:.3f} valid={s['valid']:.3f} headroom={s['headroom']:.3f}")
