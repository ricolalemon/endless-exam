# Evaluating a model

Version 1 consists of **69 distinct instances, evaluated once each**. The 14 families
have 16 task variants. Each configuration is evaluated on the same call list.

## 1. Export the tasks

```bash
python bench/exam.py export --output prompts.jsonl
python bench/exam.py prompt a3-capset-0
```

Each JSONL record contains `call_id`, `instance_id`, the mathematical parameters,
`system` and `prompt`, the frozen reference, and the resource limits. Each record
has a unique `call_id` and `instance_id`.

The four certified trifference calls have IDs `t1-trifference-0` through
`t4-trifference-0`, with lengths 64, 96, 144 and 192. They are part of the formal
suite. The older short-code experiments are supplementary data.

## 2. Collect the first scorable outcome per call

Send the exported system message and prompt to your model. Use a tool-free
configuration with no web browsing, file access, code execution or verifier
queries. Allow up to **128,000 output tokens, including reasoning**. Record the
model version, effort and harness settings. Invalid answers and exhausted token
or evaluation-time budgets are final zero-score outcomes. Calls interrupted by
network or service errors may be resubmitted after recovery. Retain every attempt
and its available usage; never repeat a call to improve answer quality.
Automatic transport reconnection is allowed. Record its settings and events;
unreported usage on interrupted generations remains unknown.

Save one JSON object per line in `answers.jsonl`:

```json
{"call_id":"a3-capset-0","answer":{"product":[["00","01","10","11"],["00","01","10","11"],["00","01","10","11"],["00","01","10","11"],["00","01","10","11"]]},"finish_reason":"stop","output_tokens":1500}
```

This is a small example construction for the ten-dimensional cap-set call. The
`answer` field contains the actual object or certificate, not a claimed score.
It can also retain the outer `{"answer": ...}` envelope returned by the model.
Use the token count reported by the provider or harness; the example count above
only illustrates the file format.

Record failures explicitly:

```json
{"call_id":"a3-capset-11","finish_reason":"length","output_tokens":128000}
```

Budget exhaustion (`length`), an evaluation deadline (`timeout`), and an output
above the budget score zero. Network and service errors such as `transport_error`
or `server_error` remain missing evaluations. A normal completion at exactly the limit is not treated as truncation
unless the provider reports a budget stop. Retain the full generation metadata
with your submission so the stated conditions can be checked.

## 3. Verify and score

```bash
python bench/exam.py score answers.jsonl --output scores.json
```

The scorer checks each construction with the benchmark verifier, including its
compact-format expansion or certificate. Verification has a 60-second wall-clock
limit on macOS/Linux. It rejects duplicate and unknown call IDs. A full Score
requires all 69 scored outcomes; include invalid and budget-exhausted calls.
Resolve infrastructure failures before reporting a full Score.

For a work-in-progress subset:

```bash
python bench/exam.py score answers.jsonl --allow-partial --output partial-scores.json
```

The output labels this `subset_score`, reports missing call IDs and uses the
observed distinct instances as its denominator. Infrastructure failures are
listed separately and remain in the missing-call list.

## Scoring

For a valid maximisation construction, the relative quality is objective divided
by reference. For minimisation it is reference divided by objective. Invalid,
empty, timed-out and truncated answers score zero.

The scorer averages the 69 instance ratios and multiplies by 100. Each instance
has one response. **100 is reference parity, not a
ceiling.** It also reports mean relative quality separately for published frontiers
and construction baselines, alongside validity and per-call results. See [the specification](../SPEC.md).

## Other parameters

The family implementations can generate further tasks beyond the fixed suite:

```bash
python bench/openceiling.py gen --family capset --seed 7
python bench/exam.py verify --family capset --params '{"d":2}' --answer examples/capset.json
```

Use separate evaluation sets for changed dimensions or other parameters. Their
results describe an extension of the benchmark rather than the version-1 Score.
