# Evaluating a model

Version 1 consists of **69 distinct instances, evaluated once each**. The 14 families
have 16 task variants. Each configuration is evaluated on the same call list.

This guide covers the **tool-free track**. Use the default API runner below, or
collect responses with your own client and follow the export/score workflow.
[Custom harnesses and tool-assisted scoring](HARNESSES.md) are documented separately.
The mathematical tasks and references are the same across harnesses.

## Run with Codex or Claude Code

Install the CLI, sign in normally, and choose the model and effort explicitly:

```bash
python bench/exam.py run --adapter codex --model gpt-6-astra --effort high \
  --workers 4 --output output/codex-astra

python bench/exam.py run --adapter claude-code --model claude-fable-5-1 --effort high \
  --workers 4 --output output/claude-fable
```

Use an exact model identifier available to your account. Replace the example
models as needed. No API key is required when the CLI already has a working
stored login. Add `--dry-run` first to check the installed CLI and inspect the
exact prompt and command without generating an answer. To start that prepared
run, repeat the command with `--resume` in place of `--dry-run`.

The validated versions are **Codex CLI 0.154.0** and **Claude Code 2.1.269**.
`--cli-binary /path/to/executable` selects another installation. The runner records
its version and executable hash; it never installs/upgrades a CLI or edits global
settings. Other versions require `--allow-untested-cli` and must still provide the
required isolation flags. That option records an untested configuration, not a
compatibility guarantee. Pin the CLI and its dependencies for the whole run.

Both adapters use the same mathematical prompt plus the paper's no-tools
instruction. They retain each CLI's native system instructions instead of adding
the API system message. Prompts contain no reference values or budget reminders.
Each invocation starts in an empty temporary directory outside the checkout.
Tools, MCP, skills/plugins, memory and user/project customizations are disabled;
Codex additionally uses a read-only sandbox. Claude's native initialization is
checked for unexpected tools/MCP. Administrative policies can still affect a CLI;
protocol violations pause collection for inspection.

**Budget and completion.** The scored output budget is 128,000 tokens, including
reasoning. Claude receives this limit through its native output setting, and the
adapter stops at the first native output-limit signal to prevent continuation.
Codex uses native output-limit events and the reported final-turn count; it has
no adapter-supplied hard `max_output_tokens` request parameter. An over-budget
completed turn scores zero. Unknown counts remain unknown, and each model may
also have its own native limit. `--timeout` is the native CLI evaluation deadline,
default two hours. An active generation reaching it scores zero; startup failures
and interrupted transport remain missing. No partial answer is scored after a
tool-free deadline.

**Recovery and accounting.** Codex's isolated provider enables four request and
five stream retries; Claude enables four native request retries and retains any
native stream-recovery events. There are no automatic outer CLI resubmissions.
After an exhausted infrastructure failure, inspect its logs and explicitly use
`--resume --retry-infrastructure`. Completed invalid answers and genuine budget
zeroes are never regenerated. Extra turns after completion trigger a protocol
alert while preserving the first completed answer.

`events.jsonl`, `stderr.txt`, `prompt.txt`, `request.json` and
`native-summary.json` are retained for each attempt. Token accounting includes
all reported generations, including interrupted ones. The scored response's
`output_tokens` is kept separately from aggregate attempt `usage.output_tokens`,
so known tokens from a network-interrupted generation do not reduce the next
generation's scored allowance. Interrupted usage stays incomplete. Claude's
overlapping streaming and summary counters are not added twice. Its input total
includes cache-read and cache-creation tokens. Codex reasoning counts are retained
when reported, as a subset of output.

Claude's reported model ID is checked against a requested full identifier. Codex
may not expose a backend model ID in its JSON events; in that case `response_model`
stays null and the requested ID is recorded separately. CLI versions and requested
names do not prove an undisclosed backend deployment fingerprint.

The default `--cli-auth login` removes provider-key/routing environment overrides
for the child process and uses the CLI's stored authentication. To deliberately
use environment-based credentials/routing, add `--cli-auth environment`:
Codex uses the key named by `--api-key-env` and the Responses endpoint under
`--base-url`; Claude uses its native `ANTHROPIC_*` environment settings. This may
use API billing. Values of credentials are not copied to manifests. Authentication
files remain under the CLI's control and are not copied by the runner.

These adapters cover the **tool-free track**. Use the [external tool-assisted
harness interface](HARNESSES.md#tool-assisted-harnesses) for code and web access.
For installation and CLI behavior, see the official [Codex non-interactive
reference](https://learn.chatgpt.com/docs/developer-commands#codex-exec) and
[Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference).

## Run with an API

Set `OPENAI_API_KEY` in your environment, then:

```bash
python bench/exam.py run --model YOUR_MODEL --effort high \
  --workers 4 --output output/your-model
```

Omit `--effort` for models that do not support it. No effort is imposed by default.
The command uses a non-streaming Chat Completions-compatible endpoint. Use
`--base-url https://YOUR_PROVIDER/v1` and `--api-key-env YOUR_KEY_VARIABLE` for
another provider. For an unauthenticated local server use, for example,
`--base-url http://127.0.0.1:8000/v1 --api-key-env ''`.

For the Responses API:

```bash
python bench/exam.py run --adapter responses --model YOUR_MODEL \
  --effort high --workers 4 --output output/your-model-responses
```

Before collecting, append `--dry-run` to either command. It writes the configuration
and one request preview, with **zero model calls**. Remove `--dry-run` and add
`--resume` to start that prepared run. The preview contains only the original
system and mathematical prompt as model messages; references, bounds and resource
settings are never appended to those messages.

The runner requests **128,000 total output tokens**, including reasoning. It uses
`max_completion_tokens` for Chat Completions and `max_output_tokens` for Responses.
For compatible servers that require the older field, specify
`--token-parameter max_tokens`. Confirm that the provider counts reasoning inside
that limit. Unsupported settings stop collection; the runner never silently
reduces the budget or switches models. A model with a smaller native output limit
requires a separately documented configuration. Provider-specific settings can
be supplied as a JSON object with `--options settings.json`, for example
`{"thinking":{"type":"enabled"}}`. Only generation settings are accepted;
message, tool, model and token-limit overrides are rejected.

The default runner offers no tools and makes no continuation requests. A provider
must expose a tool-free endpoint; an API alias that secretly invokes its own
agent cannot be made tool-free by this client. This is a new-model evaluation
interface, not a byte-for-byte reproduction of each paper model's native harness.

### Resume and failures

Repeat the **same command and settings**, adding `--resume`. Completed outcomes
are reused, including invalid answers, refusals and token-limit zeroes. A lock
prevents two controllers from using one output directory. Changing the model,
prompts, settings or runner code requires another directory.

HTTP connection failures, rate limits and server errors receive up to four
additional attempts by default (`--retries 4`). Every attempt is retained.
Authentication/configuration errors and exhausted retries stop new dispatch;
already-running requests drain. Network failures remain missing, not model
zeroes. After inspecting the terminal failure and resolving it, resume with
`--retry-infrastructure`. This only recollects confirmed transport/service failures;
malformed responses, collector errors and unfinished journals require inspection
and repair of saved evidence before collection can proceed.

`--timeout` is a socket/process timeout (default 7,200 seconds), **not evidence of
model budget exhaustion**. A timed-out request may still be running on the server;
retrying can cause another underlying generation. The first scorable outcome is
kept, with unknown usage for any interrupted generation. This runner does not
enforce a provider-side two-hour evaluation deadline. A custom harness can do so
and record genuine deadline exhaustion explicitly.

### Output files

| File | Contents |
| --- | --- |
| `manifest.json` | Model, settings, cohort and prompt/code hashes |
| `attempts/<call_id>/<number>/` | Request, raw response, timestamps and normalised outcome for every attempt |
| `answers.jsonl` | First scorable response per call; unresolved infrastructure failures are labelled |
| `scores.json` | Overall and reference-group scores, validity and per-instance verification |
| `usage.json` | Reported token totals across **all** attempts and counts with unknown usage |
| `status.json` | Collection state and missing/untouched calls |

Scores and usage are rebuilt when the batch finishes or drains. Native reasoning
tokens are a subset of output tokens and are not added twice. Unknown usage remains
unknown, so an incomplete reported total is a lower bound. `--only CALL_ID ...`
runs a subset and produces `subset_score`; a full Score still requires all 69.
Credentials are read from the named environment variable and never written to
requests or manifests. Keep credentials out of option files and URLs. Raw provider
responses may include reasoning or diagnostics; inspect them before sharing.

## Use your own client

### 1. Export the tasks

```bash
python bench/exam.py export --output prompts.jsonl
python bench/exam.py prompt a3-capset-0
```

Each JSONL record contains `call_id`, `instance_id`, the mathematical parameters,
`system` and `prompt`, the frozen reference, and the resource limits. Each record
has a unique `call_id` and `instance_id`.

Prefer `export --model-inputs-only` when feeding an external harness: it omits
scoring metadata entirely and retains only the IDs, `system` and `prompt`.

The four certified trifference calls have IDs `t1-trifference-0` through
`t4-trifference-0`, with lengths 64, 96, 144 and 192. They are part of the formal
suite. The older short-code experiments are supplementary data.

### 2. Collect the first scorable outcome per call

Send only the exported `system` and `prompt` fields to your model. The remaining
fields support evaluation; reference values, mathematical bounds and resource
metadata must not be added to the model's messages. Use a tool-free
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

### 3. Verify and score

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
