# Paper and analysis

The paper compares 12 tool-free configurations and two tool-assisted
configurations on 69 instances from fourteen families. Thirty instances use
published frontiers and 39 use construction baselines.

## Reproduce the results

Run these commands from the repository root after installing
`requirements-paper.txt`:

```bash
python bench/paper/publication_data.py
python bench/paper/tool_results.py
python scripts/index_results.py
```

`publication_data.py` supplies the tool-free tables and figures.
`tool_results.py` supplies the tool-assisted comparisons and usage statistics.
The [result index](../results/published/index.csv) identifies every main-evaluation
outcome and its saved response. Both tracks use the same mathematical instances
and references, with their respective resource limits described in the paper.

The supplementary analyses include model-size and reasoning-effort comparisons,
size-quality curves, computational search budgets and the matched Opus subset.
The [data guide](../../docs/DATA.md) describes their source records.

## Rebuild the paper

Install Tectonic, then run:

```bash
python bench/paper/build_publication.py --edition arxiv
```

This regenerates tables and figures from saved responses and builds
`output/pdf/endless-exam-arxiv.pdf`. The preprint uses TeX Gyre Termes and Cursor
fonts supplied by TeX Live. No model calls are made.

See [Reproducing the paper](../../docs/REPRODUCING.md) for verification commands,
serving settings and the optional anonymous ICLR build.

## Figure data

Figure 1 illustrates a five-point AP-free set in two dimensions over five
symbols, compared with the six-point optimum. Its points and checks are recorded
in `tables/framework_example.json`.

Figure 2 averages model ratios and mathematical bounds over the same instances
within each family/reference group. Its reference endpoints are recorded in
`tables/scale_reference_data.json`. `tables/scale_curve_data.json` records the
model points. Display clipping does not change the scores.

Model versions and effort levels are identified in the figure legends or
captions. Styling is defined in `visual_theme.py` and `plot_style.py`.
