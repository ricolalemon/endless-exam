"""Prepare/freeze and report the eight admitted A3 code-family calls; performs no model calls itself."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ["BENCH_TIER"] = "A3"
import run_ladder as L
from openceiling import FAMILIES, expand_answer, verify_with_timeout
from agent_bridge import NO_TOOLS
from candidate_families import shannon_second, trifference_second, zarank_second

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "bench/results/pilots/astra-medium-codes-A3"
RESULT = ROOT / "bench/results/gpt-6-astra-codex-medium@nocap#A3.jsonl"
CHECKS = {"shannon": shannon_second, "trifference": trifference_second, "zarank": zarank_second}
CODE_FILES = ["bench/candidate_families.py", "bench/openceiling.py", "bench/run_ladder.py",
              "bench/headless_codex.py", "bench/agent_bridge.py", "bench/code_extension.py",
              "bench/data/shannon_c7_base.json", "bench/data/trifference_references.json", "bench/scripts/build_code_references.py"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jobs():
    return [(name,seed) for name in L.CODE_INSTANCES for seed in range(4)]


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "manifest.json"
    if path.exists():
        validate_manifest()
        print("A3 manifest and frozen inputs already verified", flush=True)
        return
    cases = []
    for name,seed in jobs():
        F,p = L.instance_a(name,seed)
        naive = F.naive(p)
        primary = verify_with_timeout(F,p,naive)
        second = CHECKS[name](p,naive)
        if not primary[0] or primary[:2] != second:
            raise RuntimeError((name,seed,"naive disagreement",primary,second))
        t = time.monotonic()
        ref = L.reference(name,seed,10)
        elapsed = time.monotonic()-t
        if ref["params"] != p:
            raise RuntimeError((name,seed,"reference parameters differ"))
        a = ref["search_answer"]
        if verify_with_timeout(F,p,a)[:2] != (True,ref["search"]) or CHECKS[name](p,a) != (True,ref["search"]):
            raise RuntimeError((name,seed,"reference disagreement"))
        if not 0 < ref["naive"] <= ref["search"] <= ref["bound"] or ref["bound"] / ref["search"] < 1.4:
            raise RuntimeError((name,seed,"reference/bound inconsistency"))
        ref_path = ROOT / f"bench/refs/A3-{name}-{seed}-t10.json"
        prompt = L.prompt_for(name,F,p,"p1",None) + NO_TOOLS
        cases.append({"family":name,"seed":seed,"params":p,"naive":ref["naive"],"search10":ref["search"],
                      "bound":ref["bound"],"reference":str(ref_path.relative_to(ROOT)),"reference_sha256":digest(ref_path),
                      "prompt_sha256":hashlib.sha256(prompt.encode()).hexdigest(),"preparation_wall_s":round(elapsed,3)})
        print(f"A3 {name}:{seed} {p}: expert={ref['naive']}, search10={ref['search']}, bound={ref['bound']}; both checkers agree",flush=True)
    manifest = {"created_utc":datetime.now(timezone.utc).isoformat(),"status":"prepared","tier":"A3",
                "model":"gpt-6-astra","effort":"medium","config":"codex-medium@nocap#A3",
                "protocol":"p1; tools disabled", "scoring_output_budget":128000,"wall_timeout_s":7200,
                "workers":2,"single_attempt":True,"frontier_kind":"verified construction stand-in; no global record claims",
                "cases":cases,"code_sha256":{p:digest(ROOT/p) for p in CODE_FILES}}
    path.write_text(json.dumps(manifest,indent=2)+"\n")
    print("Frozen:",path,flush=True)


def validate_manifest():
    manifest = json.loads((OUT/"manifest.json").read_text())
    for path,sha in manifest["code_sha256"].items():
        if digest(ROOT/path) != sha:
            raise RuntimeError(f"Code changed after A3 freeze: {path}")
    for case in manifest["cases"]:
        if digest(ROOT/case["reference"]) != case["reference_sha256"]:
            raise RuntimeError(f"A3 reference changed: {case['reference']}")
        F,p=L.instance_a(case["family"],case["seed"])
        prompt=L.prompt_for(case["family"],F,p,"p1",None)+NO_TOOLS
        if p != case["params"] or hashlib.sha256(prompt.encode()).hexdigest() != case["prompt_sha256"]:
            raise RuntimeError("A3 prompt changed")
    return manifest


def report():
    manifest=validate_manifest()
    rows={}
    if RESULT.exists():
        for line in RESULT.read_text().splitlines():
            r=json.loads(line);key=(r["family"],r["seed"])
            if key in rows:
                raise RuntimeError(f"Duplicate attempt: {key}")
            rows[key]=r
    rows = {k:r for k,r in rows.items() if k[0] in L.CODE_INSTANCES}
    if set(rows) != set(jobs()):
        raise RuntimeError(f"A3 incomplete/unexpected: missing={set(jobs())-set(rows)}, extra={set(rows)-set(jobs())}")
    details=[]
    lines=["# Astra medium: A3 候选家族试跑", "", "8 个预先固定的 A3 实例，每题一次，无工具；评分输出预算 128k。",
           "参照是本轮验证过的构造与 10 秒搜索的较优值，超过参照不等同于刷新全球纪录。", "",
           "| 家族 | 参数 | 专家构造 | 10 秒搜索 | 模型目标值 | 有效 | 参照比值 | 用时（秒） |",
           "|---|---|---:|---:|---:|:---:|---:|---:|"]
    for case in manifest["cases"]:
        name,seed=case["family"],case["seed"];r=rows[name,seed];F=FAMILIES[name];p=case["params"]
        if r["params"] != p or r["model"] != manifest["model"] or r["config"] != manifest["config"]:
            raise RuntimeError(f"Row identity differs: {name}:{seed}")
        raw_path = ROOT / f"bench/results/headless/gpt-6-astra/A3-codex-medium@nocap-{name}-{seed}.json"
        cli = json.loads(raw_path.read_text())
        if cli["result"] != r["content"] and r["finish_reason"] != "timeout":
            raise RuntimeError((name,seed,"raw content mismatch"))
        if cli.get("tool_attempts"):
            raise RuntimeError((name,seed,"tool attempts need review"))
        if r["finish_reason"] == "timeout":
            first=(False,0)
        else:
            raw=L.extract_json(r["content"])
            first=verify_with_timeout(F,p,raw)[:2]
            expanded=expand_answer(F,p,raw)
            second=CHECKS[name](p,expanded)
            if first != second:
                raise RuntimeError((name,seed,"model checker disagreement",first,second))
        if first != (r["feasible"],r["objective"]):
            raise RuntimeError((name,seed,"stored verdict differs"))
        valid=r["feasible"] and r["finish_reason"] != "length" and (r.get("reasoning_tokens") or 0) <= 128000
        objective=r["objective"] if valid else 0
        reference=max(case["naive"],case["search10"])
        ratio=objective/reference
        if objective > case["bound"]:
            raise RuntimeError((name,seed,"model beyond proven bound"))
        d={**case,"objective":objective,"mathematically_feasible":r["feasible"],"strict_feasible":valid,
           "reference_ratio":ratio,"latency_s":r["latency_s"],"output_tokens":r["reasoning_tokens"],
           "finish_reason":r["finish_reason"],"verify_msg":r["verify_msg"],"law":F.law(p,objective) if valid else None}
        details.append(d)
        lines.append(f"| {name} | {json.dumps(p)} | {case['naive']} | {case['search10']} | {objective} | {'是' if valid else '否'} | {ratio:.3f} | {r['latency_s']:.1f} |")
    lines += ["", "## 各家族", ""]
    for name in L.CODE_INSTANCES:
        subset=[d for d in details if d["family"]==name]
        lines.append(f"- {name}: 有效 {sum(d['strict_feasible'] for d in subset)}/4；平均参照比值 {sum(d['reference_ratio'] for d in subset)/4:.3f}。")
    lines += ["", "## 无效答案", ""]
    lines.extend(f"- {d['family']}:{d['seed']}: {d['finish_reason']}; {d['verify_msg']}" for d in details if not d["strict_feasible"])
    lines += ["", "检查：全部模型答案与记录复核；非超时答案由两套属性检查器交叉核对。", ""]
    (OUT/"summary.json").write_text(json.dumps({"completed_utc":datetime.now(timezone.utc).isoformat(),"cases":details},indent=2)+"\n")
    (OUT/"summary.md").write_text("\n".join(lines))
    print("\n".join(lines),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["prepare","validate","report"])
    action=parser.parse_args().action
    {"prepare":prepare,"validate":validate_manifest,"report":report}[action]()
