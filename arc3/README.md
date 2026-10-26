# ARC-AGI-3 Emoji Solver Adapter

This module adds a dependency-free baseline policy and an optional runner for the
official ARC-AGI-3 Python toolkit.

## Status: executable exploration baseline, not a solved benchmark agent

The policy is deterministic and tested. It only chooses actions supplied as legal by
the caller, tracks attempted actions per exact observation, and can persist its state
across process restarts. It does **not** infer game rules, learn a complete world
model, or establish ARC-AGI-3 benchmark performance.

## Emoji program surface

```text
📥➡️👁️➡️🧠➡️🧩➡️🎯➡️⚙️➡️📤 ♻️🔁🧠🔍🛑
```

The glyph sequence is the human-facing program surface. Its executable mapping is
implemented in Python: ingest observation, inspect legal actions, choose a legal
action deterministically, and emit diagnostics. Emojis are not machine opcodes until
a parser/runtime maps them to operations.

## Run the policy without the SDK

From the repository root:

```sh
python3 arc3/emoji_solver.py <<'JSON'
{"observation":{"grid":[[0,1],[1,0]]},"legal_actions":[{"button":"left"},{"button":"right"}]}
JSON
python -m unittest discover -s tests -p 'test_arc3_emoji_solver.py' -v
```

The response contains `action`, `status`, the emoji `program`, diagnostics, and a
JSON-serializable `solver_state`. Send `solver_state` back with the next request to
preserve action attempts and repeated-state counters across CLI process restarts.
Alternatively, supply history records containing both `observation` and `action`.

## Run against the official ARC-AGI-3 toolkit

Install the official toolkit separately (the GitHub source currently documents Python 3.12+):

```sh
python -m pip install "git+https://github.com/arcprize/ARC-AGI.git"
python -m arc3.arc_agi_runner --game-id ls20 --max-actions 20 --save-recording
```

The GitHub source is used because the published PyPI package installed in the first integration attempt did not provide the documented `arcengine` import. The runner uses the documented `arc_agi.Arcade`, `env.action_space`,
`env.observation_space`, `env.step()`, and `GameState` interface. It now includes an
observation-only visual navigation heuristic: it looks for a large moving-object
candidate, a smaller shared-color target, and a traversable-color path. When that
pattern cannot be inferred, it falls back to deterministic action exploration. An API key is
optional for basic access; a registered key can enable access to additional games.
Keep credentials out of source control.

Complex actions use a bounded exploration strategy:
- `--click-strategy foreground` (default): sample up to 32 nonzero cells from the
  observed frame layers.
- `--click-strategy scan`: sample an 8-by-8 coordinate lattice.
- `--click-strategy center`: use only the configured center coordinate.
- `--click-x` and `--click-y` set the center/fallback coordinate.
- `--max-click-points` bounds the number of candidate clicks.

Foreground mode now prefers nonzero cells that changed since the previous frame,
then falls back to visible foreground cells when no motion is detected. This is a
motion-salience heuristic, not semantic object recognition. The policy does not
understand game-specific mechanics, and a non-winning run is not a failure of the
runner itself. The JSON result distinguishes `won` from whether the run executed.

## Partitioned level completion and planning memory

The runner maintains separate partitions for:
- `level_progress`: explicitly reported levels completed, reported total, and completion signal.
- `scene_state`: bounded frame shape and current reported state.
- `goal_hypotheses`: evidence behind a candidate target, labeled as heuristic.
- `active_plan`: the current proposed action and target.
- `action_outcomes`: whether the observation changed after an action.
- `uncertainties`: why the visual planner could not propose a reliable route.

This is a lightweight bookkeeping and planning-memory layer, not a learned world model.
It avoids declaring level completion unless the observation reports progress or a win
signal. The runner also forecasts motion using three explicit what-if branches:
continue current motion, stop, or reverse. The current heuristic priors are 0.60,
0.25, and 0.15 respectively; they are normalized engineering defaults, **not measured
or calibrated probabilities**. The forecast lists predicted color-centroids and marks
the highest-prior scenario, but should not be trusted as a real likelihood until
validated against subsequent frames. The final runner JSON includes `planning_memory`
and `motion_forecast`. Run the focused
unit tests with:

```sh
python -m unittest discover -s tests -p 'test_arc3_*.py' -v
```

## Live smoke workflow

The GitHub Actions workflow `ARC-AGI-3 Live Benchmark` installs the official SDK,
runs a bounded live test, and uploads the JSON result plus any recording. It can be
manually dispatched with a game ID, action budget, and seed list. The automatic push
trigger is intentionally limited to changes to the workflow file so ordinary code
pushes do not unexpectedly consume live benchmark time. A failed environment
connection is reported as a CI failure; a completed run can succeed even if the
baseline did not win.

## Integration boundary and next research steps

The visual heuristic is an early hypothesis-driven baseline, not a general solution:
it can misidentify objects and only handles simple grid-aligned paths. A stronger
agent needs robust frame perception, action-effect tracking, goal hypotheses,
planning, and evaluation across held-out games and seeds. Record action
budgets, outcomes, levels completed, scorecards, and recordings. Do not claim
benchmark success based on unit tests or a single smoke run.

Every chosen action is matched back to the environment's legal action list before
execution. Arbitrary model-generated actions are never passed through unvalidated.
