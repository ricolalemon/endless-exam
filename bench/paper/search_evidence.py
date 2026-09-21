"""Audit the frozen search-budget evidence without launching searches or changing reference files."""
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bench"))
from openceiling import FAMILIES, HEADROOM, SEARCH_TYPE, textbook_zero
from family_catalog import CORE_GROUPS, SEARCH_GROUPS, UNCLASSIFIED_GROUPS

SEEDS = (0, 1, 2)
# The original comparison uses seeds 0--2; Shannon has four distinct A3 cases.
FAMILY_SEEDS = {"shannon": (0, 1, 2, 3)}
SEARCH_BUDGET_FAMILIES = tuple(task for group, tasks in CORE_GROUPS.items()
                               if group != "trifference" for task in tasks)


def scoring_zero(family, record):
    F = FAMILIES[family]
    expert = textbook_zero(F, record["params"], record["search"])
    value = expert[0] if expert else record["naive"]
    return (max if F.sense == "max" else min)(value, record["search"])


def log_gain(family, before, after):
    return math.log(after / before if FAMILIES[family].sense == "max" else before / after)


def instance_mean(records, field):
    groups = {}
    for r in records:
        if r.get(field) is not None:
            groups.setdefault((r.get("task"), json.dumps(r["params"], sort_keys=True)), []).append(r[field])
    return statistics.mean(statistics.mean(v) for v in groups.values()) if groups else None


def collect(model_rows=None, tier="A3", ref_dir=None, families=None, grouped=False):
    ref_dir = Path(ref_dir) if ref_dir else ROOT / "bench/refs"
    out = {}
    for family in families or HEADROOM["open"]:
        records = []
        for seed in FAMILY_SEEDS.get(family, SEEDS):
            path = ref_dir / f"{tier}-{family}-{seed}-t10.json"
            if not path.exists(): continue
            r10 = json.loads(path.read_text())
            record = {"task": family, "seed": seed, "params": r10["params"], "naive": r10["naive"],
                      "search10": r10["search"], "zero10": scoring_zero(family, r10)}
            path600 = path.with_name(path.name.replace("-t10.json", "-t600.json"))
            if path600.exists():
                r600 = json.loads(path600.read_text())
                if r10["params"] != r600["params"]:
                    raise ValueError(f"Reference parameter mismatch: {family}:{seed}")
                record.update(search600=r600["search"], zero600=scoring_zero(family, r600))
                record["raw_gain"] = log_gain(family, record["search10"], record["search600"])
                record["zero_gain"] = log_gain(family, record["zero10"], record["zero600"])
            objectives = [r["objective"] for rs in (model_rows or {}).values()
                          if (r := rs.get((family, seed))) and r["feasible"] and r["params"] == r10["params"]]
            if objectives:
                best = (max if FAMILIES[family].sense == "max" else min)(objectives)
                record["model_gain"] = log_gain(family, record["search10"], best)
            records.append(record)
        paired = [r for r in records if "raw_gain" in r]
        out[family] = {"class": "unclassified" if family in UNCLASSIFIED_GROUPS else "search-type" if family in SEARCH_TYPE else "search-resistant", "records": records,
                       "n_pairs": len(paired), "n_instances": len({json.dumps(r['params'], sort_keys=True) for r in paired}),
                       "raw_mean": instance_mean(records, "raw_gain"), "zero_mean": instance_mean(records, "zero_gain"),
                       "model_mean": instance_mean(records, "model_gain"),
                       "raw_max": max((r["raw_gain"] for r in paired), default=None),
                       "zero_max": max((r["zero_gain"] for r in paired), default=None)}
    if not grouped:
        return out
    combined = {}
    for group, tasks in CORE_GROUPS.items():
        if not any(task in out for task in tasks): continue
        records = [r for task in tasks for r in out.get(task, {}).get("records", [])]
        paired = [r for r in records if "raw_gain" in r]
        combined[group] = {"class": "unclassified" if group in UNCLASSIFIED_GROUPS else "search-type" if group in SEARCH_GROUPS else "search-resistant",
                           "records": records, "n_pairs": len(paired),
                           "n_instances": len({(r["task"], json.dumps(r["params"], sort_keys=True)) for r in paired}),
                           **{field+"_mean": instance_mean(records, field+"_gain") for field in ("raw", "zero", "model")},
                           **{field+"_max": max((r[field+"_gain"] for r in paired), default=None) for field in ("raw", "zero")}}
    return combined


def main():
    from figs import SYSTEMS, PRETTY  # also loads frozen version 1
    from report import load
    from formal_cohort import formal_a3_view
    _, rows = formal_a3_view(*load("A3"))
    selected = {(m, c + "#A3"): rows.get((m, c + "#A3"), {}) for m, c, *_ in SYSTEMS}
    data = collect(selected, families=SEARCH_BUDGET_FAMILIES, grouped=True)
    order = [f for f in data if f not in SEARCH_GROUPS] + [f for f in data if f in SEARCH_GROUPS]
    lines = [r"\begin{tabular}{@{}llrrrrrr@{}}", r"\toprule",
             r"family & class & runs & instances & mean $\Delta_r$ & max $\Delta_r$ & mean $\Delta_z$ & max $\Delta_z$ \\", r"\midrule"]
    for f in order:
        r = data[f]
        cells = ["--" if r[k] is None else f"{r[k]:.3f}" for k in ("raw_mean", "raw_max", "zero_mean", "zero_max")]
        label = PRETTY.get(f, f).replace("_", r"\_").replace("–", "--")
        if f == "apfree_q": label = r"$\mathbb{F}_q^n$ AP-free"
        if f == "schur": label = "Schur"
        lines.append(f"{label} & {'S' if f in SEARCH_GROUPS else 'R'} & {r['n_pairs']} & {r['n_instances']} & " + " & ".join(cells) + r" \\")
        if f == [f for f in order if f not in SEARCH_GROUPS][-1]: lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (ROOT / "bench/paper/tables/search_budget_table.tex").write_text("\n".join(lines) + "\n")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
