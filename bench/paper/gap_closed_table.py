"""Publish proven-bound progress and separate LABS conjecture progress."""
import json
import publication_data as P
from tool_results import load_all


def generate():
    systems = {**P.summaries(), **load_all()}
    for s in systems.values():
        g = s["gap_closed"]
        assert (g["n"], g["published"]["n"], g["construction"]["n"], s["target_progress"]["n"]) == (64, 30, 34, 5)
        assert abs(g["mean"] - (30*g["published"]["mean"] + 34*g["construction"]["mean"])/64) < 1e-12
    data = {"definition": "Logarithmic progress from the fixed scoring reference; proven bounds and conjectured targets are reported separately.",
            "systems": {sid: {"label": s["label"], "gap_closed": s["gap_closed"],
                              "target_progress": s["target_progress"]} for sid, s in systems.items()}}
    (P.HERE/"tables/gap_closed_data.json").write_text(json.dumps(data, indent=2)+"\n")
    lines = [r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
             r"& \multicolumn{3}{c}{Gap closed to proven bounds} & LABS target \\",
             r"\cmidrule(lr){2-4}",
             r"Configuration & All 64 & Published 30 & Construction 34 & 5 instances \\", r"\midrule"]
    for sid, s in systems.items():
        if sid == "astra_tools": lines.append(r"\midrule")
        g = s["gap_closed"]
        lines.append(f"{s['label']} & {g['mean']:.3f} & {g['published']['mean']:.3f} & "
                     f"{g['construction']['mean']:.3f} & {s['target_progress']['mean']:.3f}" + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    (P.HERE/"tables/gap_closed_breakdown.tex").write_text("\n".join(lines)+"\n")


if __name__ == "__main__":
    generate()
