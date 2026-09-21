# Benchmark implementation

Start with the [repository README](../README.md), [evaluation guide](../docs/EVALUATING.md)
and [version-1 specification](../SPEC.md).
Use the [result index](results/published/index.csv) to find a published outcome and its
saved response. The [data guide](../docs/DATA.md) explains the reference and
selection records.

## Entry points

| Command | Purpose |
|---|---|
| `python bench/exam.py families` | List the fourteen families |
| `python bench/exam.py export --output prompts.jsonl` | Export the 69 unique instances |
| `python bench/exam.py prompt a3-capset-0` | Inspect one formal call |
| `python bench/exam.py score answers.jsonl --output scores.json` | Verify and aggregate a submission |
| `python bench/formal_cohort.py` | Check coverage of the released model results |
| `python bench/paper/publication_data.py` | Recompute the paper's scores |

Run commands from the repository root. Verification and result analysis are
offline and need no model credentials.

## Mathematical interface

A family in `openceiling.FAMILIES` provides `params(rng)`, `statement(params)`,
`verify(params, answer)`, a construction baseline, and its objective direction.
`verify_with_timeout` expands supported compact descriptions and verifies the
result under the wall-clock limit. The Shannon and trifference implementations
also check certificates without materialising every codeword.

The fixed call list is assembled by `formal_cohort.cases()`. Each task variant
and parameter setting defines one distinct instance. `exam.suite()` exposes
stable call and instance IDs, exact prompts and frozen reference values.
`family_catalog.py` groups the sixteen task variants into fourteen families.

## Reference and response data

`frontiers/v1-trifference.json` is the scoring snapshot used for public version 1.
The earlier snapshots and supplementary parameter sets support the paper's
historical and sensitivity comparisons. `refs/` contains reference objects and
timed-search results. `results/*.jsonl` contains final responses and evaluation
metadata. The configuration strings and tier tags identify the original runs.

The paper uses twelve complete configurations, each with one response on 69
instances. Its thirty published-frontier and thirty-nine construction-reference
instances have equal weights, with one selected response per instance.
See [reproduction instructions](../docs/REPRODUCING.md) for all build commands.
