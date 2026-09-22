# Use your own evaluation harness

Endless Exam defines tasks and verifies submitted constructions. You can use your
own model client, agent framework, scheduler or compute environment. Its output
connects to the same scorer; adopting the default runner is optional.

For tool-free Codex and Claude Code, use the [built-in CLI adapters](EVALUATING.md#run-with-codex-or-claude-code).
The custom wrapper interface below is for other harnesses or protocols.

## Simplest integration: tasks in, answers out

```bash
python bench/exam.py export --model-inputs-only --output prompts.jsonl
# Run your harness over the exported tasks.
python bench/exam.py score answers.jsonl --output scores.json
```

Each exported task contains `call_id`, `instance_id`, `system` and `prompt`. Send
only `system` and `prompt` as messages. Return one JSONL row per task:

```json
{"call_id":"a3-capset-0","answer":{"product":[["00","01","10","11"],["00","01","10","11"],["00","01","10","11"],["00","01","10","11"],["00","01","10","11"]]},"finish_reason":"stop","output_tokens":null}
```

Use the actual reported output count, including reasoning; `null` means unknown.
Completed malformed answers should be represented as `answer: null`, with their
original text retained in your logs. They score zero. Valid-looking model claims
about a score, elapsed time or network failure are not trusted metadata.

Retain the first scorable response and all preceding infrastructure attempts.
Never choose the best of retries or regenerate an invalid completed answer.
Keep raw usage, exact model identifiers, effort, harness/version, tool access,
resource limits, timestamps and reconnection history with the run. Describe
changes to prompts or resource settings when reporting a result. The mathematical
scorer checks answers; it does not certify how an external model was run.

## Plug a tool-free harness into the default runner

The `command` adapter invokes an executable once per task. It uses an argv array,
not a shell command. Save this array in `harness-command.json`, using absolute
paths for your executable and script:

```json
["python", "/absolute/path/to/my_harness.py", "{request}", "{response}"]
```

```bash
python bench/exam.py run --adapter command --model YOUR_MODEL --effort high \
  --command-file harness-command.json --workers 4 --output output/custom-model
```

The runner substitutes two absolute file paths. Your program reads the request
and writes the response, then exits with code 0. It runs in an empty per-attempt
working directory. This is **not a security sandbox**: your trusted wrapper is
responsible for disabling model tools, repository access, plugins, memory and
extra turns. Do not give the request file itself to an agent as its prompt.

The request has this shape:

```json
{
  "schema_version": 1,
  "call_id": "a3-capset-0",
  "instance_id": "capset-…",
  "messages": [{"role":"system","content":"…"},{"role":"user","content":"…"}],
  "model": "YOUR_MODEL",
  "effort": "high",
  "track": "tool-free",
  "max_output_tokens": 128000,
  "settings": {}
}
```

Only `messages` belongs in the model context. `settings` comes from `--options`;
it configures your harness and must contain no secrets. Your wrapper may use a
provider SDK or another CLI. Native CLI system instructions differ
from API system messages, so record that distinction and the exact CLI version.
Disable any automatic continuation after a completed answer or output-limit stop;
transport reconnection is allowed if its events and usage are retained.

Write the response as:

```json
{
  "answer": null,
  "finish_reason": "stop",
  "response_model": "ACTUAL_MODEL_OR_SNAPSHOT",
  "usage": {"input_tokens": null, "output_tokens": null, "reasoning_tokens": null},
  "usage_complete": false
}
```

Instead of `answer`, the wrapper can return the final model text in `content`;
the runner uses the benchmark's existing JSON extraction. Status and usage must
come from trusted native events, **not from that text**. Aggregate all generated
responses, without summing repeated cumulative usage snapshots. Preserve raw
native events beside `response.json`. Missing interrupted usage makes
`usage_complete` false even when the last response reports its tokens.

Scored `finish_reason` values are `stop`, `length`, `timeout`, `refusal` and
`tool_violation`. Here `timeout` means a genuine model evaluation deadline verified
by your harness. Infrastructure values include `transport_error`, `server_error`,
`rate_limit`, `quota`, `cli_error`, `collector_error`, `incomplete_turn` and
`malformed_event`. A nonzero program exit is a missing evaluation. There are no
automatic command retries; inspect and explicitly recover transport failures.
The outer process timeout is a collector failure, not an automatic zero.

[`examples/mock_harness.py`](../examples/mock_harness.py) is an executable, offline
example of this interface. It deliberately submits an invalid answer with unknown
usage; it does not call a model. Substitute its absolute path above to test wiring.

## Tool-assisted harnesses

Use your own agent executor with code and optional web access. Export the same
mathematical prompts with the paper's single file-submission instruction:

```bash
python bench/exam.py export --track tool-assisted --model-inputs-only \
  --output tool-prompts.jsonl
```

These records contain IDs and `prompt`. The prompt appends only:

> Save your final answer as a single JSON object to /workspace/answer.json.

The agent keeps its native system instructions. No reference value, strategy,
score target or budget reminder is added. For comparison with the paper, each
trajectory has four CPU threads, 16 GiB RAM, 128 processes, a two-hour deadline,
no GPU or subagents, and no cumulative output-token cap. It starts without
benchmark source, references, witnesses or previous answers. Use separate
workspaces, stop all writers at completion/deadline, and collect the saved file
within the 32 MiB submission limit. Your executor must enforce these limits;
the default API/command runner does not provide this tool sandbox.

Return the saved object's JSON as `answer`, not the final chat message. Include:

```json
{"call_id":"a3-capset-0","track":"tool-assisted","answer":null,"finish_reason":"timeout","submission_within_deadline":false,"output_tokens":null}
```

`submission_within_deadline` is required for every scored row. Set it to true only
if your harness has confirmed a saved, timely submission. A missing or late file
scores zero. An answer saved before the deadline is checked even when the run
ends with `timeout`, `resource_limit` or `length`. Report network/service failures
as missing; do not recast them as deadline or memory exhaustion. Record the actual
file hash, file size, deadline/resource evidence, tool history and complete or
unknown usage separately for audit.

```bash
python bench/exam.py score tool-answers.jsonl --track tool-assisted \
  --output tool-scores.json
```

This scoring mode removes the tool-free token cap and checks the saved answer.
It **does not validate external CPU/RAM isolation or timestamps**. Publish the
harness and resource evidence alongside results, and label configurations with
different tools or budgets separately. Use `--allow-partial` during collection.

## API reference

The built-in transports follow the official [text-generation request and response
format](https://developers.openai.com/api/docs/guides/text) and [output-token
accounting](https://developers.openai.com/api/docs/guides/token-counting#understand-output-token-counts).
Provider compatibility, supported effort values and model output limits vary;
check the exact endpoint before a full run.
