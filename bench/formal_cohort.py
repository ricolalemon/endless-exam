"""Current publication comparison: one response on each of 69 instances.

Original A3 core12 + four Shannon A3 instances + four certified trifference scales.
Internal tier names are preserved; no historical parameter list is overwritten.
"""
import argparse
import fcntl
import json
from pathlib import Path
from result_selection import source_for
from evaluation_outcomes import scored_view

ROOT = Path(__file__).resolve().parents[1]
SYSTEMS = [
    ("astra_medium", "gpt-6-astra", "Astra medium", "codex-medium@nocap", "codex-medium@nocap", False),
    ("astra_high", "gpt-6-astra", "Astra high", "codex-high@nocap", "codex-high@128k.once", False),
    ("deepseek_low", "deepseek-flash", "DeepSeek low", "think-low@128k", "think-low@128k", False),
    ("deepseek_high", "deepseek-flash", "DeepSeek high", "think-high@128k", "think-high@128k", False),
    ("qwen38", "Qwen/Qwen3.8-27B-FP8", "Qwen3.8-27B high", "think-high@128k", "think-high@128k", False),
    ("qwen35", "Qwen/Qwen3.5-27B-FP8", "Qwen3.5-27B high", "think-high@128k", "think-high@128k", False),
    ("qwen9", "Qwen/Qwen3.5-9B", "Qwen3.5-9B high", "think-high@128k", "think-high@128k", False),
    ("qwen4", "Qwen/Qwen3.5-4B", "Qwen3.5-4B high", "think-high@128k", "think-high@128k", False),
    ("luna_medium", "gpt-5.6-luna", "Luna medium", "codex-medium@128k.once-full", "codex-medium@128k.once-full", False),
    ("luna_high", "gpt-5.6-luna", "Luna high", "codex-high@128k.once-full", "codex-high@128k.once-full", False),
    ("opus", "claude-opus-5", "Opus medium", "headless-medium@128k", "headless-medium@128k", True),
    ("fable", "claude-fable-5-1", "Fable medium", "headless-medium@128k", "headless-medium@128k", False),
    ("fable_high", "claude-fable-5-1", "Fable high", "headless-high@128k.frozen69", "headless-high@128k.frozen69", False),
    ("opus55_medium", "claude-opus-5-5", "Opus 5.5 medium", "headless-medium@128k.frozen69", "headless-medium@128k.frozen69", False),
    ("opus55_high", "claude-opus-5-5", "Opus 5.5 high", "headless-high@128k.frozen69", "headless-high@128k.frozen69", False),
]


def distinct_cases(calls):
    """Choose the smallest original seed without inspecting any model outcome."""
    selected={}
    for index,c in enumerate(calls):
        key=c['family'],json.dumps(c['params'],sort_keys=True)
        order=c['seed'],c['tier'],index
        if key not in selected or order<selected[key][0]:selected[key]=(order,index,c)
    return [c for _,_,c in sorted(selected.values(),key=lambda item:item[1])]


def cases():
    result = json.loads((ROOT / "bench/data/formal_suite_v1.json").read_text())["calls"]
    assert len(result) == 69
    assert len({(c["family"], json.dumps(c["params"], sort_keys=True)) for c in result}) == 69
    return result


def formal_a3_view(ref,rows,keep_controls=()):
    """Use the same unique formal slots in auxiliary A3 comparisons."""
    keys={(c['family'],c['seed']) for c in cases() if c['tier']=='A3'}
    keys.update(key for key in ref if key[0] in keep_controls)
    return ({key:value for key,value in ref.items() if key in keys},
            {system:{key:value for key,value in values.items() if key in keys}
             for system,values in rows.items()})


def source_path(system, case):
    sid, model, label, core_config, code_config, held = system
    config = core_config if case["block"] == "core12" else code_config
    return source_for(model, config, case['tier'], case['family'], case['seed'], ROOT)


def get_row(system, case, cache=None, include_unscored=False):
    path, config = source_path(system, case)
    if cache is None: cache = {}
    if path not in cache:
        if not path.exists(): cache[path] = []
        else:
            with path.open() as f:
                fcntl.flock(f, fcntl.LOCK_SH);cache[path] = list(map(json.loads, f))
    rows = [r for r in cache[path] if r["family"] == case["family"] and r["seed"] == case["seed"]]
    assert len(rows) <= 1, (system[0], case)
    if rows:
        assert rows[0]["params"] == case["params"]
        assert rows[0]["config"] == config
        assert rows[0]["model"] == system[1]
        row = scored_view(rows[0])
        if row['scored']:return rows[0]
        return row if include_unscored else None


def coverage():
    cohort = cases();systems = [];cache = {}
    for s in SYSTEMS:
        present = [c for c in cohort if get_row(s, c, cache) is not None]
        systems.append({"id": s[0], "label": s[2], "is_claude": s[1].startswith("claude-"),
                        "claude_on_hold": s[5], "completed": len(present),
                        "core12": sum(c["block"] == "core12" for c in present),
                        "codes": sum(c["block"] == "codes" for c in present), "expected": len(cohort),
                        "missing": [{k: c[k] for k in ("tier", "family", "seed")} for c in cohort if get_row(s, c, cache) is None]})
    return {"families": 14, "task_variants": 16, "calls_per_configuration": 69, "distinct_instances": 69,
            "all_non_claude_complete": all(s["completed"] == 69 for s in systems if not s["is_claude"]),
            "systems": systems}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__);p.add_argument("--output", type=Path);a = p.parse_args()
    result = coverage()
    if a.output: a.output.write_text(json.dumps(result, indent=2) + "\n")
    public = {k: result[k] for k in ["families", "task_variants", "calls_per_configuration", "distinct_instances"]}
    public["complete_configurations"] = sum(s["completed"] == s["expected"] for s in result["systems"])
    public["systems"] = [{**{k: s[k] for k in ["id", "label", "completed", "core12", "codes", "expected"]},
                          "historical_subset": s["completed"] < s["expected"]} for s in result["systems"]]
    print(json.dumps(public, indent=2))
