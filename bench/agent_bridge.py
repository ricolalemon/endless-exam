#!/usr/bin/env python3
"""Bridge for models reached as chat subagents (no API): emit the Track-A prompts, then score a reply.

    python3 bench/agent_bridge.py prompts --seeds 0            # JSON list of {family, seed, prompt}
    python3 bench/agent_bridge.py score --model claude-opus-5 --config agent-notools --family golomb --seed 0 --reply-file r.txt
"""
import argparse, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "bench"))
import run_ladder as L
from openceiling import FAMILIES

NO_TOOLS = ("\n\nRules for this task: you have NO tools for this task -- do not run code, do not browse, do not read or "
            "write files, do not call any tool. Work it out by reasoning alone. Your entire final reply must be the single "
            "JSON object and nothing else.")

def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompts"); p.add_argument("--seeds", type=int, nargs="*", default=[0]); p.add_argument("--families", nargs="*", default=list(L.A_RANGES))
    s = sub.add_parser("score"); s.add_argument("--model", required=True); s.add_argument("--config", required=True)
    s.add_argument("--family", required=True); s.add_argument("--seed", type=int, required=True); s.add_argument("--reply-file", required=True)
    s.add_argument("--latency", type=float, default=None); s.add_argument("--ref-time", type=float, default=10.0)
    s.add_argument("--error", default=None, help="record a failed call (e.g. 'max_output_tokens@64k'); reply-file may be empty")
    s.add_argument("--finish-reason", choices=["stop", "length", "timeout"], default=None)
    s.add_argument("--reasoning-tokens", type=int, default=None, help="output tokens consumed (from the agent transcript)")
    s.add_argument("--provider", default="subagent", help="subagent (Agent tool) or claude-cli (headless claude -p)")
    s.add_argument("--response-model", default=None, help="model id actually reported by the provider")
    s.add_argument("--fingerprint", default=None, help="provider/tool version string, stored as system_fingerprint (e.g. 'claude-cli 2.1.269')")
    a = ap.parse_args()
    if a.cmd == "prompts":
        out = []
        for f in a.families:
            for seed in a.seeds:
                fam, p = L.instance_a(f, seed)
                out.append({"family": f, "seed": seed, "params": p, "prompt": L.prompt_for(f, fam, p) + NO_TOOLS})
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    fam, p = L.instance_a(a.family, a.seed)
    ref = L.reference(a.family, a.seed, a.ref_time)
    text = open(a.reply_file).read()
    if a.finish_reason == "timeout":
        text = ""                      # a wall-clock timeout never scores a partial or stale answer
    ans = L.extract_json(text)
    from openceiling import verify_with_timeout
    if a.finish_reason == "timeout":
        feasible, obj, msg = False, 0, a.error or "wall-clock timeout"
    else:
        feasible, obj, msg = verify_with_timeout(fam, p, ans)
    label = a.config if L.SIZE_TIER == "A1" else f"{a.config}#{L.SIZE_TIER}"     # same convention as run_ladder
    out = os.path.join(ROOT, "bench", "results", f"{a.model}-{label}.jsonl")
    if os.path.exists(out):
        for line in open(out):
            r = json.loads(line)
            if r["family"] == a.family and r["seed"] == a.seed:
                print(f"already scored: {a.family} s{a.seed}"); return
    rec = {"track": "A", "tier": L.SIZE_TIER, "family": a.family, "seed": a.seed, "params": p, "provider": a.provider,
           "model": a.model, "config": label, "base_config": a.config, "max_tokens": None, "feasible": feasible,
           "objective": obj, **L.score(fam, ref, feasible, obj), "naive": ref["naive"], "reference": ref["search"],
           "beats_reference": bool(feasible and ((obj > ref["search"]) if fam.sense == "max" else (obj < ref["search"]))),
           "bound": ref["bound"], "sense": fam.sense, "verify_msg": msg, "error": a.error,
           "law": (fam.law(p, obj) if feasible else None), "answer_len": (len(ans) if isinstance(ans, (list, str)) else None),
           "usage": None, "system_fingerprint": a.fingerprint, "response_model": a.response_model or a.model, "latency_s": a.latency,
           "finish_reason": a.finish_reason or ("length" if a.error and "max_output" in a.error else ("stop" if ans is not None else None)),
           "reasoning_tokens": a.reasoning_tokens, "reasoning_chars": 0, "content_chars": len(text),
           "request_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "content": text}
    open(out, "a").write(json.dumps(rec) + "\n")
    print(f"{a.model} {a.family} s{a.seed} feasible={feasible} obj={obj} ref={ref['search']} gain={rec['gain']:.2f} {msg}")

if __name__ == "__main__":
    main()
