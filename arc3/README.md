# ARC-AGI-3 Emoji Solver Adapter

This module adds an initial, dependency-free action-policy seam for integrating the
SHUSH emoji pipeline with an ARC-AGI-3 environment.

## Status: baseline adapter, not a solved benchmark agent

The adapter is executable and tested as a deterministic policy component. It does
**not** include the official ARC-AGI-3 environment SDK, game-specific perception,
a learned policy, or a claim of ARC-AGI-3 benchmark performance. An environment
adapter must supply observations and the legal actions exposed by that environment.

## Emoji program surface

```text
📥➡️👁️➡️🧠➡️🧩➡️🎯➡️⚙️➡️📤 ♻️🔁🧠🔍🛑
```

The glyph sequence is the human-facing program surface. Its executable mapping is
implemented in Python: ingest observation, inspect legal actions, choose a legal
action deterministically, and emit diagnostics. Emojis are not themselves machine
opcodes until a parser/runtime maps them to operations.

## Request/response protocol

Request JSON:

```json
{
  "observation": {"grid": [[0, 1], [1, 0]]},
  "legal_actions": [{"button": "left"}, {"button": "right"}],
  "history": []
}
```

Response JSON includes `action`, `status`, the emoji `program`, and diagnostic
metadata. If an action object has numeric `score` or `priority`, the adapter
ranks those supplied values, while still selecting only from the legal action list.
Without scores, it tries each legal action once per exact observation before using a
deterministic fallback. Repeated observations are flagged as a possible loop.

## Run

From the repository root:

```sh
python3 arc3/emoji_solver.py <<'JSON'
{"observation":{"grid":[[0,1],[1,0]]},"legal_actions":[{"button":"left"},{"button":"right"}]}
JSON
python3 -m unittest discover -s tests -p 'test_arc3_emoji_solver.py' -v
```

## Integration boundary

A real ARC-AGI-3 runner should:
1. Call the official environment to obtain the current observation and legal actions.
2. Normalize that data into the request protocol above.
3. Call the policy and pass its returned `action` back to the environment.
4. Persist policy state/history across turns (or instantiate a long-lived solver).
5. Stop on environment terminal status, action budget, or repeated-state limits.
6. Report task-level success only from the environment's own success signal.

Do not pass arbitrary model-generated actions directly to an environment. Validate
against the environment's legal action set first. Keep credentials and network access
outside this module.
