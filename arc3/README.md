# ARC-AGI-3 Emoji Solver Adapter

This module adds a dependency-free baseline policy and an optional runner for the
official ARC-AGI-3 Python toolkit.

## Status: executable baseline, not a solved benchmark agent

The policy is deterministic and tested. It only chooses among actions supplied as
legal by the caller, tracks attempted actions per exact observation, and can persist
its state across process restarts. It does **not** infer game rules, learn a world
model, or establish ARC-AGI-3 benchmark performance.

## Emoji program surface

```text
📥➡️👁️➡️🧠➡️🧩➡️🎯➡️⚙️➡️📤 ♻️🔁🧠🔍🛑
```

The glyph sequence is the human-facing program surface. Its executable mapping is
implemented in Python: ingest observation, inspect legal actions, choose a legal
action deterministically, and emit diagnostics. Emojis are not machine opcodes until
a parser/runtime maps them to operations.

## Policy protocol

Request JSON:

```json
{
  "observation": {"grid": [[0, 1], [1, 0]]},
  "legal_actions": [{"button": "left"}, {"button": "right"}],
  "history": []
}
```

The response contains `action`, `status`, the emoji `program`, diagnostics, and a
JSON-serializable `solver_state`. Send that `solver_state` back with the next request
to preserve action attempts and repeated-state counters across CLI process restarts.
Alternatively, supply history records containing both `observation` and `action`;
records without both fields are ignored for state reconstruction.

If action objects include numeric `score` or `priority`, the policy ranks those
values while still selecting only from the legal list. Without scores, it tries each
legal action once for a given observation before a deterministic fallback. Repeated
observations are flagged as a possible loop. This policy is a baseline explorer, not
a game-specific strategy.

## Run the policy

From the repository root:

```sh
python3 arc3/emoji_solver.py <<'JSON'
{"observation":{"grid":[[0,1],[1,0]]},"legal_actions":[{"button":"left"},{"button":"right"}]}
JSON
python3 -m unittest discover -s tests -p 'test_arc3_emoji_solver.py' -v
```

## Optional official ARC-AGI-3 SDK runner

Install the official toolkit separately:

```sh
python -m pip install arc-agi
python -m arc3.arc_agi_runner --game-id ls20 --max-actions 100 --render-mode terminal
```

The toolkit documents the `arc_agi.Arcade` / `arcengine` interface and may use an
anonymous API key if `ARC_API_KEY` is not configured. Access to particular games can
vary. To save a run recording, add `--save-recording`.

**Important:** this runner is an integration smoke test, not a competitive agent.
The current policy does not understand game-specific mechanics. For complex click
actions it uses the fixed coordinate `(32, 32)` by default; set `--click-x` and
`--click-y` to change it. It reports a win only when the SDK environment reports
`GameState.WIN`. A nonzero exit status means the run did not report a win or could
not complete.

## Integration boundary and next research steps

A stronger agent needs a perception/modeling layer, goal hypotheses, action-effect
tracking, planning, and evaluation across held-out games/seeds. Keep a baseline
comparison, action budget, run recordings, and scorecard evidence. Do not claim
benchmark success based on unit tests or a single smoke run.

Never pass arbitrary model-generated actions to the environment: validate every
action against the environment's legal action set first. Keep credentials out of
source control.
