# Reproducing the paper

The release includes generators, verifiers, frozen references, final model
responses, parameter lists, figure scripts and the paper source.
The [data guide](DATA.md) describes the files. Start with the
[per-instance result index](../bench/results/published/index.csv) to inspect one outcome
and locate its saved response.

## Install

Use Python 3.10 or later on macOS or Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-paper.txt
```

NumPy is used by the mathematical implementations. Matplotlib is used for
figures. The offline checks and result aggregation do not require model access.

## Reproduce coverage and scores

```bash
python bench/formal_cohort.py
python bench/paper/publication_data.py
python bench/paper/tool_results.py
python bench/paper/gap_closed_table.py
python bench/paper/tables.py
python bench/paper/manuscript_numbers.py
python scripts/index_results.py
```

All fourteen tool-free configurations have one selected response on each of the
same 69 instances. The overall Score, panel means and bootstrap intervals are written
to `bench/paper/tables/publication_data.json`. Claude Opus 5 is a supplementary
comparison on its shared 45-instance subset.

The separate Astra high, Luna high and Opus 5.5 high code-and-web evaluations use the same 69 instances. Their final
objects, prompts, verification results, usage and resource settings are in
`bench/results/tool-assisted/astra-high-v1.json`, `luna-high-v1.json` and `opus55-high-v1.json`. `tool_results.py` recomputes their
scores against the same frozen references and writes `tables/tool_publication_data.json`,
the manuscript macros, family comparisons and individual-instance tables. Tool-free
selections stay in their original files. The combined score/token plot is generated
with `python bench/paper/fig_score_tokens.py --paper`.

Gap closed averages 64 instances with proven bounds, using the same fixed references as the relative quality. The five LABS conjectured-target instances are reported separately in `tables/gap_closed_data.json`.

The main results are generated from saved responses. The released records retain
final answers, validity, objectives and generation metadata. Private reasoning
text and machine logs are omitted.
`RELEASE_MANIFEST.json` records release-file hashes and the transformations used
to prepare the public data. Usage, failure status, collection identifiers and
response-selection evidence are retained.

### Response selection

The formal manifest fixes 69 unique family/parameter settings. Where the historical
data contain repeated draws of the same setting, the main comparison retains the
smallest original numeric seed, with tier and original order as tie-breakers.
The same choice applies to every model and does not depend on answer quality.
`bench/data/formal_suite_v1.json` records the selected cases; explicit replacements
and their provenance are recorded in `bench/data/result_replacements.json`.

The size experiments use two independent responses per setting and configuration.
Their means include zero scores and their whiskers span the two scores. The effort
comparison averages repeated responses within each shared parameter setting.
The smaller trifference table shows four additional instances; its data file also
retains the four Shannon responses already shown in the main code comparison.

### Serving settings

Qwen models use vLLM 0.29.0 with prefix caching disabled. Qwen3.5-4B and 9B use
tensor parallelism 2; the 27B FP8 checkpoints use tensor parallelism 4. Collection
concurrency for these vLLM runs is at most four, or two for the code-family evaluations. Fable high uses independent tool-free sessions with peak collection concurrency 43; its client version, output budget and provenance are recorded in `bench/data/fable_high_publication.json`. Opus 5.5 uses Claude Code 2.1.280 at medium and high effort without tools, and
at high effort with native web search and an isolated MCP shell. It shares the
mathematical prompts and CPU/memory/time limits of the other tool evaluations;
the native system prompt and tool interfaces differ. Its peak concurrency is two
per tool-free effort and fourteen with tools, using disjoint physical CPU groups.
Native CLI models retain their system instructions, while API models receive the mathematical
construction system message. All models receive the same mathematical task and
answer-format instructions. See [evaluation rules](EVALUATING.md) for infrastructure
recovery, terminal failures and token accounting.

## Rebuild figures

```bash
python bench/paper/figs.py
python bench/paper/fig_ladder.py
python bench/paper/fig_code_scale.py
python bench/paper/appendix_redesign.py
```

The figures use a fixed 5.5-inch width. Model colours and page styling are defined
in `bench/paper/visual_theme.py`; typography and line styles are shared through
`bench/paper/plot_style.py`.

## Build the PDF

Install [Tectonic](https://tectonic-typesetting.github.io/) and run:

```bash
python bench/paper/build_publication.py --edition arxiv
```

The complete build regenerates all paper tables and figures and writes
`output/pdf/endless-exam-arxiv.pdf`, the named preprint included in this release.
It uses TeX Gyre Termes and Cursor fonts supplied by TeX Live. Reference and
appendix pagination is checked after rebuilding.

The source also supports an anonymous ICLR edition. Building without `--edition
arxiv` writes `output/pdf/endless-exam.pdf` and checks the nine-page main-text
limit; `--max-main-pages` sets an explicit limit for working drafts. That edition
uses Times New Roman and Courier New, which must be installed or replaced in
the font declarations. The bibliography style and LaTeX packages retain their
original notices.

## Validate constructions

The release includes a reference-matching construction for every one of the 69
formal instances in `bench/data/reference_witnesses/`. Its index records the
instance parameters, reference value and file hash. Check all objects with the
formal scoring entry and independent verifiers:

```bash
python bench/verify_reference_witnesses.py
```

The stored `verification.json` also reports answer lengths under `cl100k_base`
and `o200k_base`. To recompute those counts, install `tiktoken` and add `--tokens`.
The appendix coverage table is generated from this verified collection.

```bash
python bench/test_verifiers.py
python bench/test_gap_closed.py
python bench/test_candidate_families.py
python bench/test_trifference_certificates.py
python bench/test_construction_references.py
python bench/test_publication_data.py
python bench/paper/test_analysis.py
python bench/paper/test_appendix_redesign.py
```

`bench/crosscheck.py` provides independent verifiers for recorded constructions.
Its full corpus check takes longer than the regression tests. The code-family
independent checks also appear in `bench/candidate_families.py`.
