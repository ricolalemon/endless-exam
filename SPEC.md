# The Endless Exam: version-1 specification

## Scope

Version 1 evaluates fourteen mathematical construction families through sixteen
task variants. The fixed suite has **69 distinct instances, with one response per instance**:
30 with published frontiers and 39 with verified construction baselines.
Spherical codes include fixed and variable angles; Heilbronn includes square
and triangular domains.

Export the exact suite with:

```bash
python bench/exam.py export --output prompts.jsonl
```

Each call carries its mathematical parameters, prompt, objective direction,
reference and scoring anchor. Both `call_id` and `instance_id` are unique.
Identical parameter draws use the smallest original seed, with the same choice
for every model and no selection by answer quality. The certified trifference
instances use lengths 64, 96, 144 and 192 with
separation multiplicity 1.

## Generation protocol

Each configuration contributes the first scorable outcome for each call. Browsing, code
execution, file access and verifier queries are disabled. The output budget is
128,000 tokens, including reasoning. Invalid answers and generations that exhaust
the token or evaluation-time budget receive zero and are not retried. Network or
service failures are missing evaluations and may be resubmitted after recovery.
Automatic transport reconnection is allowed. Retain all attempt records and reported
usage; unreported usage on interrupted generations remains unknown. Model version, effort, harness settings
and generation dates accompany results.

The answer is a mathematical object or a supported compact construction, wrapped
as `{"answer": ...}`. Accepted compact formats include products, vector orbits,
digit constructions, Cayley graphs, Shannon factors, ternary generator matrices
and Reed–Solomon concatenation certificates. The verifier checks the stated
property and computes the objective. A claimed objective is never used as a score.

Expansion and verification have a 60-second wall-clock budget on macOS/Linux.
Each answer format also has explicit bounds on dimensions, literal elements or
certificate size. See the task prompt and paper appendix for those limits.

### Exact quadratic coordinates

Kissing instances with `representation: "quadratic"` additionally accept exact
coordinates `a + b*sqrt(3)`. An answer has the form
`{"quadratic_vectors":{"radicand":3,"vectors":V}}`, where each vector in `V`
contains `d` integer pairs `[a,b]`. Coefficients lie in `[-1000,1000]`, dimensions
in `1..16`, and at most 20,000 vectors are accepted. Integer lists and their
existing orbit format remain available. Both verifiers compare angles exactly,
including at 60 degrees; decimals and symbolic strings are not accepted.

This permission is explicit in the instance parameters and prompt. The formal
thirteen-dimensional kissing instance and its problem-size evaluations use this
format. All reported configurations were evaluated with the same permissions.

## Relative quality and total Score

Let `a` be the verified objective and `h` the instance's fixed reference:

- Maximisation: `ratio = a / h`.
- Minimisation: `ratio = h / a`.
- Invalid, empty, budget-exhausted or truncated answer: `ratio = 0`.
- Network or service failure: missing, with no ratio.

Relative quality 1 matches the reference, and every improvement raises the
score. All instances use this same metric. Thirty use published frontiers for
direct comparison with existing mathematical results. The other 39 use parameters
outside published construction tables to reduce direct retrieval of ready-made
answers and test adaptation of known methods. Their construction baselines take
the best value from verified constructions and the ten-second reference search.

Each instance contributes one response. The total is
`Score = 100 × mean(instance ratios)` across all 69 instances. Reference parity
is 100; the total is uncapped. Mean relative quality is also reported separately for instances with published
frontiers and those with construction baselines. The main paper gives uncertainty intervals over
distinct instances.

A complete comparable result includes all 69 calls, with explicit failed records.
Partial submissions receive a labelled subset score over their observed distinct
instances. They are not assigned a full-suite Score.

## Gap closed and mathematical bounds

The supplementary gap-closed metric measures logarithmic progress beyond the
same fixed reference `h` used for relative quality, toward a proven bound `b`.
For maximisation it is `max(0, log(a/h) / log(b/h))`; minimisation uses
`max(0, log(h/a) / log(h/b))`. Matching or failing to improve on the reference
scores zero, as do invalid answers. Reaching the bound scores one.

Only positive reference-to-bound gaps with proven bounds (including proven
trivial bounds) enter the aggregate. Each eligible instance has equal weight:
the current suite has 64 such instances, comprising 30 published-frontier and
34 construction-baseline instances. Their means are not combined with equal
group weights. A bound need not be tight or attainable, so this metric measures
progress toward the stated bound, not a certified fraction of the distance to
the unknown optimum.

The five LABS instances use a conjectured merit-factor target. Progress toward
that target uses the same reference-based formula and is reported separately,
not included in the 64-instance gap-closed mean. A conjectured target may be
exceeded. Verified results beyond a proven bound are flagged for investigation.
Bounds and targets do not cap relative quality or Overall score.

## Families and extension

The fourteen families are cap sets, spherical codes, Heilbronn triangles, LABS,
corner-free sets, matrix multiplication, degree–diameter graphs,
linear-equation-free sets, finite-field progression-free sets, MOLS, Schur
colourings, covering designs, Shannon codes and trifference codes.

Their parameters include dimensions, field sizes, graph degrees and diameters,
sequence lengths and design parameters. Changing these values defines new tasks
under the same property and objective. Size curves evaluate how construction
quality scales. New parameters form a separate evaluation set; published
version-1 results continue to use the fixed suite and references.

For the tested reference searches, eight families are search-resistant: cap sets,
spherical codes, corners, linear-equation-free sets, finite-field AP-free sets,
MOLS, Schur and Shannon codes. Five support direct search: LABS, Heilbronn,
degree–diameter graphs, matrix multiplication and coverings. These thirteen
families have paired ten- and 600-second measurements. Trifference remains
unclassified: its baseline procedure selects and combines existing codes
without using the search-time budget.

## Records and versioning

An answer above a published frontier is a record candidate. Record recognition
requires an independent verification and a literature check. Improvements over
construction baselines measure progress beyond those baselines. References
remain fixed within a public version. Future reference updates and expanded
suites receive a new version.

The internal snapshot filename is `bench/frontiers/v1-trifference.json`.
`bench/paper/tables/publication_data.json` records the aggregation and source
hashes. Earlier snapshot files support historical comparisons. The public
benchmark release is called **version 1**.
