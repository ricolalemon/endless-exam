"""Endless Exam headline report: human-frontier ratio (HFR) with a records counter, two panels, plus reference-to-bound gap closed.

    python3 bench/report.py --tier A3 --systems "gpt-6-astra:codex-high@nocap#A3" "claude-fable-5-1:headless-medium@128k#A3" ...

Panel 1 -- families with a published human frontier: HFR = answer / best published construction (1 = parity,
> 1 = verified record).  Panel 2 -- table-free families (random parameters, deformations): ratio to the best expert
construction or reference search when no published frontier is recorded. Supplement -- gap closed to proven bounds; progress toward conjectured targets is separate.
Formal A3 comparisons use the selected unique slots. Auxiliary repeated
experiments average within parameters. Complete formal-suite scores are generated
by bench/paper/publication_data.py or the public bench/exam.py interface."""
import argparse, glob, json, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "bench"))
from openceiling import FAMILIES, HEADROOM, frontier_ratio, closed_gap, conjectured_gap, human_frontier, anchor  # noqa: E402
from family_catalog import groups as family_groups, members, expand_groups
from result_selection import overlay
from evaluation_outcomes import require_scored
BUDGET = 128000          # strict protocol: replies cut off at the budget, or longer than it, score 0 at the scoring entry
STRICT_ZEROED = []       # (model, config, family, seed, reason) rows zeroed by the strict rule
MISMATCH = []            # model rows whose params differ from the reference row's (skipped, printed)


def load(tier):
    ref, rows = {}, {}
    for f in glob.glob(os.path.join(ROOT, "bench", "results", "*.jsonl")):
        for l in open(f):
            r = json.loads(l)
            if r.get("tier", "A1") != tier:
                continue
            if r["model"] == "search":
                ref[(r["family"], r["seed"])] = r
            elif r["model"] not in ("naive", "garbage"):
                if r.get("feasible") and (r.get("finish_reason") == "length" or (r.get("reasoning_tokens") or 0) > BUDGET):
                    r = dict(r, feasible=False, objective=0)
                    STRICT_ZEROED.append((r["model"], r["config"], r["family"], r["seed"], r.get("finish_reason"), r.get("reasoning_tokens")))
                rows.setdefault((r["model"], r["config"]), {}).setdefault((r["family"], r["seed"]), r)
    overlay(tier, ref, rows, ROOT)
    # a model row must describe the same instance as its reference row (guards against stale references)
    for key, rs in rows.items():
        for (fm, s), r in list(rs.items()):
            if (fm, s) in ref and json.dumps(ref[(fm, s)]["params"], sort_keys=True) != json.dumps(r["params"], sort_keys=True):
                MISMATCH.append((key[0], key[1], fm, s, r["params"], ref[(fm, s)]["params"])); del rs[(fm, s)]
    return ref, rows


def ci(vals, B=2000, seed=0):
    vals = sorted(vals)  # identical samples give identical CIs in the report, tables and figures
    rnd = random.Random(seed); n = len(vals); ms = []
    for _ in range(B):
        ms.append(sum(rnd.choice(vals) for _ in range(n)) / n)
    ms.sort(); return ms[int(0.025 * B)], ms[int(0.975 * B)]


def split_families(ref, selection="core"):
    groups = family_groups(selection)
    present = {f for f, _ in ref}
    fams = [g for g, tasks in groups.items() if present.intersection(tasks)]
    def has_kind(group, want):
        return any(human_frontier(FAMILIES[f], r["params"], r["naive"], r["objective"])[1] == want
                   for (f, _), r in ref.items() if f in groups[group])
    return fams, [g for g in fams if has_kind(g, True)], [g for g in fams if has_kind(g, False)]


def system_values(rows, ref, model, cfg, fams, fn=frontier_ratio, kind_filter=None, selection="core"):
    """Distinct-instance means within each group; merged tasks retain their separate identities."""
    task_to_group = {f: g for g in fams for f in members(g, selection)}
    per = {}
    for (task, seed), row in sorted(rows.get((model, cfg), {}).items()):
        if task not in task_to_group or (task, seed) not in ref:
            continue
        r = ref[task, seed]
        if row["params"] != r["params"]:
            continue
        require_scored(row)
        result = fn(FAMILIES[task], r["params"], r["naive"], row["objective"], row["feasible"], r["objective"])
        value, kind = result if isinstance(result, tuple) else (result, None)
        if kind_filter and kind != kind_filter:
            continue
        if value is not None:
            key = (task_to_group[task], task, json.dumps(r["params"], sort_keys=True))
            per.setdefault(key, []).append(value)
    out = {}
    for (group, _, _), values in per.items():
        out.setdefault(group, []).append(sum(values)/len(values))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="A3"); ap.add_argument("--systems", nargs="+", required=True, help="model:config, in row order")
    ap.add_argument("--names", nargs="*", default=None, help="display names, same order")
    ap.add_argument("--spec", default=None, help="frozen frontier table version (bench/frontiers/<v>.json); default: newest; 'code' = live tables")
    ap.add_argument("--selection", choices=["core", "core12", "legacy15"], default="core")
    a = ap.parse_args()
    if a.spec != "code":
        import freeze_frontier
        v = freeze_frontier.load(a.spec or ({"core":"v1-trifference", "core12":"v1-core", "legacy15":"v1"}[a.selection]))
        if v: print(f"(frontier and anchor tables: frozen spec {v})")
    ref, rows = load(a.tier)
    if a.tier=='A3' and a.selection in ('core','core12'):
        from formal_cohort import formal_a3_view
        ref,rows=formal_a3_view(ref,rows)
    WARN = []
    print(f"# Endless Exam -- tier {a.tier}, selection {a.selection} (records = Beyond the Frontier board)")
    fams, lit, tf = split_families(ref, a.selection)
    names = a.names or [s.split(":")[1] for s in a.systems]

    def panel(title, sub, fn):
        print(f"\n### {title}\n")
        print("| system | " + " | ".join(sub) + " | mean [95% CI] over distinct instances | n | records |")
        print("|---|" + "---|" * len(sub) + "---|---|---|")
        for name, spec in zip(names, a.systems):
            m, c = spec.split(":", 1); rs = rows.get((m, c), {})
            cells, allv, rec = [], [], 0
            for f in sub:
                per = {}                                   # distinct instance (params) -> values of its repeats
                for (fm, s), r in sorted(rs.items()):
                    if fm not in members(f, a.selection) or (fm, s) not in ref: continue
                    require_scored(r)
                    out = fn(FAMILIES[fm], ref[(fm, s)]["params"], ref[(fm, s)]["naive"], r["objective"], r["feasible"], ref[(fm, s)]["objective"])
                    x, kind = (out if isinstance(out, tuple) else (out, None))
                    if kind and kind.endswith("!"): WARN.append(f"{name} {fm} seed {s}: verified objective {r['objective']} beyond the quoted bound ({kind})")
                    if x is None:
                        if fn is closed_gap and kind in ("bound", "trivial"): WARN.append(f"{name} {fm} seed {s}: no positive reference-to-bound gap; instance skipped")
                        continue
                    if fn is frontier_ratio and ((sub is lit and kind != "literature") or (sub is tf and kind == "literature")):
                        continue                           # an instance belongs to the panel of its own frontier kind
                    per.setdefault((fm, json.dumps(ref[(fm, s)]["params"], sort_keys=True)), []).append(x)
                v = [sum(xs) / len(xs) for xs in per.values()]   # repeats of one instance count once (rule fixed 2026-09-14)
                if fn is frontier_ratio and sub is lit:
                    rec += sum(x > 1.0 + 1e-9 for x in v)
                allv.extend(v)
                cells.append(f"{sum(v)/len(v):.2f}" if v else "-")
            if allv:
                lo, hi = ci(allv)
                print(f"| {name} | " + " | ".join(cells) + f" | {sum(allv)/len(allv):.2f} [{lo:.2f}, {hi:.2f}] | {len(allv)} | {rec if sub is lit else '-'} |")
            else:
                print(f"| {name} | " + " | ".join(cells) + " | - | 0 | - |")

    panel("Panel 1 -- human-frontier ratio (1 = parity with the best published construction; > 1 = verified record)", lit, frontier_ratio)
    walls = []
    for group in lit:
        for (task, seed), r in sorted(ref.items()):
            if task not in members(group, a.selection): continue
            F = FAMILIES[task]
            hf, published = human_frontier(F, r["params"], r["naive"], r["objective"])
            b, kind = anchor(F, r["params"])
            if published and b and hf:
                walls.append(f"{group} {(b/hf if F.sense == 'max' else hf/b):.1f}x")
                break
    if walls:
        print("\nAnchor / frontier at the first published-reference instance: " + ", ".join(walls))
    panel("Panel 2 -- stand-in references: ratio to the expert construction / 10 s search (no records counted)", tf, frontier_ratio)
    panel("Supplement -- gap closed from the fixed reference to a proven bound", fams, closed_gap)
    panel("Supplement -- progress toward conjectured targets (separate)", fams, conjectured_gap)
    if STRICT_ZEROED:
        print(f"\nStrict-budget rule applied: {len(STRICT_ZEROED)} row(s) zeroed (finish_reason=length or > {BUDGET} output tokens): " + "; ".join(f"{m} {c} {f} s{s}" for m, c, f, s, *_ in STRICT_ZEROED))
    for w in sorted(set(WARN)):
        print("WARNING:", w)
    for m in MISMATCH:
        print(f"WARNING: {m[0]} {m[1]} {m[2]} seed {m[3]}: row params {m[4]} differ from the reference {m[5]}; row skipped")


if __name__ == "__main__":
    main()
