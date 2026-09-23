# Data and provenance

## Main evaluation

The [result index](../bench/results/published/index.csv) lists all 1,173 published outcomes:
17 configurations on 69 instances. It links each result to its saved response,
including zero-score outcomes. A [JSONL version](../bench/results/published/index.jsonl)
provides the same information for analysis.

[formal_suite_v1.json](../bench/data/formal_suite_v1.json) defines the common
instances. [publication_data.json](../bench/paper/tables/publication_data.json)
contains the tool-free aggregates and
[tool_publication_data.json](../bench/paper/tables/tool_publication_data.json)
contains the tool-assisted comparisons. See [Reproducing the paper](REPRODUCING.md)
to regenerate them from saved responses.

## Response selection and usage

The formal suite selects unique parameter settings without looking at model
scores. [result_replacements.json](../bench/data/result_replacements.json)
records the explicit selections made after representation corrections and
infrastructure recovery. Source rows, configuration identifiers and prior
responses remain available; the main comparison uses the selected outcomes.
An invalid completed answer or tool-free generation-budget stop is final.
Network and service failures are missing evaluations. Recovery retains the first
scorable outcome, without choosing between answers by quality.

Reported usage and flags for unknown interrupted usage remain in the source
records, together with collection identifiers, available attempt metadata and
evidence hashes. Private reasoning text and machine logs are not included.
A retained evidence hash identifies an original artifact; it does not imply that
the artifact itself is included.
[RELEASE_MANIFEST.json](../RELEASE_MANIFEST.json) records hashes of released
files and the transformations applied to source records.

Opus 5.5 collection settings and output-file hashes are recorded in
[opus55_publication.json](../bench/data/opus55_publication.json). Its two tool-free
efforts use complete provider token reports, including final usage on output-budget
stops. The tool-assisted total includes native web-search model usage where reported;
one deadline-stopped instance lacks that aggregate, so its token total remains a
lower bound. No answer is regenerated to recover missing usage.

## References and witnesses

[frontiers/v1-trifference.json](../bench/frontiers/v1-trifference.json) is the
scoring snapshot for version 1. Its filename is a persistent identifier.
[reference_witnesses/index.json](../bench/data/reference_witnesses/index.json)
links all 69 scoring references to constructions, sources and verification
results. The primary and independent checkers can replay every object:

```bash
python bench/verify_reference_witnesses.py
```

The `bench/refs/` files provide reference objects and timed-search results for
the main and supplementary experiments. Source receipts and finite ingredients
for published constructions are retained in `bench/frontier_audits/`.

## Construction baselines

[construction_references.json](../bench/construction_references.json) records
the adopted algebraic baselines. The corresponding objects and calibration
results are retained in `bench/reference_calibration/2026-09-16/`.
The [construction protocol](CONSTRUCTION_BASELINES.md) describes the methods.
The 17 calibration parameter settings are disjoint from the 20 formal settings
to which the procedures were applied. Calibration occurred after model response
collection; the same resulting references are used for every model.

[calibration.json](../bench/reference_calibration/2026-09-16/calibration.json)
and [formal.json](../bench/reference_calibration/2026-09-16/formal.json) report
the objects and both verifier results. [applied.json](../bench/reference_calibration/2026-09-16/applied.json)
retains the before/after values, the eight improved references and the hashes of
the unchanged response collections. These records support checking the baseline
selection and its separation from response collection.

## Supplementary experiments

The paper also reports smaller-instance, size, reasoning-effort and control
experiments. Their saved records use the original tier identifiers: A1/A2 for
smaller instances, L1-L4 for size series, M1-M4 for the additional graph series,
and T1-T4 for certified trifference instances. The manifests in
`bench/results/pilots/` supply the code-family instance definitions and verifier
timings used in the paper. The main suite contains 69 instances.

Source identifiers make the analysis and selection records traceable. The result
index supplies the model names and instance IDs used for comparison.
