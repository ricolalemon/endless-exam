# Evaluation results

Start with [index.csv](published/index.csv) or [index.jsonl](published/index.jsonl). They contain one
row for each published configuration and instance: 12 tool-free configurations
and two tool-assisted configurations, each evaluated on the same 69 instances.
The index reports validity, objective value and relative quality, including
scored zeroes. It does not select results by score.

Each row identifies the saved response by file and SHA-256 hash. For JSONL
sources, `source_line` is one-based; the record's `content` contains the model's
final response. For tool-assisted JSON sources, `source_pointer` identifies a
case whose `submission` contains the scored object. The source records also
retain token usage, completion status and available recovery metadata.

## Other experiments

The source files also support the paper's size, reasoning-effort and control
experiments. Their original configuration and tier identifiers are retained so
that selection records and file hashes remain traceable. Use the index for the
main comparison; the [data guide](../../docs/DATA.md) explains the supplementary
experiments and reference evidence.

To rebuild the index from the saved source records:

```bash
python scripts/index_results.py
```
