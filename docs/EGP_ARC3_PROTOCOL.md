# EGP-ARC3: Emoji Glyph Protocol

**Version:** 1.0  
**Status:** Experimental, opt-in DSL and dynamic diagnostic renderer.

## Purpose

EGP turns ARC-AGI-3 solver instructions into a typed domain-specific language with an emoji surface syntax. Glyphs are stable aliases for canonical operation identifiers. Parameters are structured values. A compiled program is inspectable and can be passed to explicitly registered handlers.

The glyph stream is not executable by itself, and emoji are not a lossless encoding of source data. Structured instruction records, observations and checksummed memory remain authoritative.

## Protocol vocabulary

| Glyph | Operation | Contract |
|---|---|---|
| 👁️ | OBSERVE | Read a real environment observation |
| 🔍 | SEGMENT | Detect candidate objects and regions |
| 🧩 | RELATE | Compute spatial relationships |
| 📐 | GEOMETRY | Describe shapes, bounds and topology |
| 🧭 | ORIENT | Infer grid coordinate orientation |
| ↔️ | TRACK | Associate objects across frames |
| ⚙️ | PHYSICS | Use evidence-gated discrete motion models |
| 🔦 | ATTEND | Prioritize player, goals, hazards and unknowns |
| 🧠 | HYPOTHESIZE | Maintain candidate mechanics |
| 🔮 | PREDICT | Generate explicitly labeled predictions |
| 📊 | PROBABILITY | Estimate success from comparable observed outcomes |
| 🏆 | REWARD | Prioritize wins and verified bonuses |
| ⛔ | RISK | Represent hazards and uncertainty |
| 🧮 | VALUE | Score progress, rewards, risk and action cost |
| 🧪 | PROBE | Select informative legal experiments |
| 🧱 | BEAM | Retain a bounded set of candidate plans |
| 🌳 | MCTS | Evaluate uncertain alternatives with bounded tree search |
| ⚡ | PARALLEL | Configure independent search workers |
| 🎯 | SELECT | Select only a legal candidate |
| ▶️ | ACT | Cross the environment action boundary |
| ✔️ | VERIFY | Compare actual observation with prediction |
| 💾 | MEMORIZE | Record verified evidence |
| 🔐 | CHECKSUM | Hash canonicalized scene records |
| 📦 | COMPRESS | Build hierarchical summaries while retaining source records |
| 🗃️ | MEMORY | Configure persistence and memory partitioning |
| 🧬 | LEARN | Update from verified observed transitions |
| 🔁 | REPLAN | Re-evaluate after new observations |
| ↩️ | UNDO | Use only when the environment explicitly supplies an undo action |

## Example program

```text
EGP {
👁️ OBSERVE(frame)
🔍 SEGMENT(objects)
🧩 RELATE(objects)
📐 GEOMETRY(objects)
🧭 ORIENT(grid, coordinate_system=infer)
↔️ TRACK(objects)
⚙️ PHYSICS(model=evidence_gated)
🔦 ATTEND(player,goals,hazards,unknowns)
🧠 HYPOTHESIZE(mechanics)
🔮 PREDICT(legal_actions)
📊 PROBABILITY(calibration=empirical)
🏆 REWARD(bonus=verified_only,win_priority=absolute)
⛔ RISK(unknown_is_not_safe=true)
🧮 VALUE(minimize_actions=true)
🧪 PROBE(information_gain)
🧱 BEAM(width=12,horizon=4)
🌳 MCTS(depth=2,simulations=32)
⚡ PARALLEL(mode=root,workers=auto)
🎯 SELECT(best_legal_action)
▶️ ACT(best_legal_action)
✔️ VERIFY(actual_observation)
💾 MEMORIZE(verified_transition)
🔐 CHECKSUM(algorithm=sha256)
📦 COMPRESS(event_chunk=4,chunks_per_rollup=4)
🗃️ MEMORY(persist=true)
🧬 LEARN(verified_observed_transitions)
🔁 REPLAN(after_every_observation=true)
}
```

## Syntax

- One instruction per line.
- Each instruction begins with exactly one registered glyph.
- Optional operation label follows the glyph.
- Parentheses hold a positional argument and/or comma-separated `key=value` parameters.
- Scalars support integers, decimals, booleans, null, quoted strings and simple lists.
- Unknown glyphs, malformed parameters and invalid control-flow order are rejected.

Example override:

```text
🧱 BEAM(width=7,horizon=3)
🌳 MCTS(depth=2,simulations=48,exploration=1.2)
⚡ PARALLEL(mode=root,workers=4)
```

## Compilation and safety semantics

`parse_program` parses glyph source. `validate_program` checks ordering. `compile_program` merges protocol defaults with user overrides and produces structured instructions. `execute_program` only invokes operations for which the caller explicitly registered handlers. It does not call an environment by itself. ACT and UNDO are marked as side-effecting operations and must be explicitly wired by the host.

Validation requires OBSERVE before reasoning, SELECT before ACT/UNDO, and VERIFY after an action before MEMORIZE. This prevents a predicted result from being silently stored as an observed outcome.

## Dynamic action glyphs and probability scoring

`arc3.action_glyph_scorer` converts every candidate supplied by the current legal action space into a structured EGP action token. Known directional actions map to arrows; click/tap actions and coordinate-bearing payloads map to 🖱️; wait/no-op maps to ⏳; undo maps to ↩️. Unknown actions map to 🎮 while preserving the exact environment action name and payload. The encoder never invents a legal action or changes its payload.

Each legal candidate receives separate evidence fields:
- **Verified progress-or-win estimate:** Beta-binomial smoothed estimate from observed outcomes.
- **Observation-change estimate:** smoothed estimate of whether the action changed the state.
- **Evidence scope:** exact state/action evidence when available; otherwise action-family history.
- **Search factors:** MCTS mean value, strategy prior and a separately reported information-gain exploration bonus.
- **Utility score:** a transparent weighted ranking heuristic, not a probability of winning.

With no observations, the probability fields are prior-only and must not be interpreted as learned confidence. As outcomes accumulate, the estimates update on subsequent decisions. Exact state/action evidence takes precedence over broader action-family evidence. Only verified transitions update the world model.

## Environment execution runtime

`arc3.egp_runtime.EGPEnvironmentRuntime` is the explicit bridge from a selected EGP action to the ARC environment. The runner uses it only when `--policy glyph` is selected; legacy policy behavior is unchanged. The bridge:

1. Confirms the selected action is present in the environment's current legal action list.
2. Confirms the selected action record names that same legal action.
3. Passes structured coordinates/data for complex actions, using a fallback only when the runner explicitly supplies one.
4. Calls the environment's `step` method exactly once.
5. Returns the actual environment observation unchanged and records an execution trace for reporting.

A missing observation is not treated as a verified transition. The runner verifies the returned frame, records the observed transition, updates gameplay memory, checks terminal state, and then plans again from the new observation. The runtime does not fabricate actions, bypass the legal-action list, or assume undocumented mechanics. The host environment remains responsible for rendering and game rules.

## Dynamic rendering

`render_protocol(context)` produces:
- the current glyph stream;
- ordered stages with context-specific structured fields;
- a SHA-256 digest of the rendered context.

The glyph stream is suitable for compact logs or a user interface. Structured stage fields are the authoritative dynamic values.

The ARC3 glyph agent includes the compiled program and a context-specific protocol rendering in its decision diagnostics.

## Default search and memory profile

Defaults are initial engineering settings, not benchmark-proven optima:
- Beam width 12, horizon 4.
- MCTS depth 2, 32 simulations, exploration 1.2.
- Root-parallel search with worker count selected by the host.
- Memory summaries every 4 events; rollups every 4 chunks.
- SHA-256 scene checksums.
- Only verified rewards count as bonuses; win completion has absolute priority.
- Success probabilities must be empirically calibrated and separated by context.

## Integrity and limitations

- Checksums detect changes; they do not reconstruct the grid.
- Glyph summaries are indexes/mnemonics, not lossless compression.
- Physics and enemy motion models must be learned from observations; do not assume gravity, momentum or enemy rules without evidence.
- A success estimate is not calibrated merely because it is represented as a probability.
- The DSL defines contracts and dynamic rendering. It does not imply that every listed operation is already connected to a production-quality implementation.
- Benchmark performance must be measured separately against identical games, seeds and action budgets.


## Separate game-dynamics memory and conservative bonus gating

`arc3.game_dynamics_memory.GameDynamicsMemory` is an additional memory partition. It does not replace or mutate the world model, exact transition learner, or checksummed hierarchical gameplay log. It records predicted-versus-observed object-position comparisons as a separate history.

The current one-step object forecast extrapolates each visible track's last observed displacement. Separately, each legal action is passed through the existing transition learner, which can produce candidate-specific next-scene predictions only when an observed template matches. Predicted scenes are re-perceived to report object centers and bounds. These are evidence-backed template predictions, not a generalized learned physics engine or calibrated probabilities. Actual next-frame positions are compared against forecasts; only actual frames remain observations.

Bonus candidates are evaluated only when the caller supplies:
- a measurable positive score gain;
- evidence-backed collection probability;
- extra-step count;
- completion probability before and after the detour;
- the signature of the legal action that starts the bonus route; and
- provenance marked `verified_history` or `environment_metadata`.

A detour is rejected if it lowers estimated completion probability, has no measurable net gain, lacks evidence, or has extra steps without a configured score-to-step exchange rate. The exchange rate defaults to unset rather than inventing a scoring conversion. A viable bonus route receives only a small capped preference among already-legal actions; it cannot create actions or bypass the environment action space.

The runner currently reads optional `__arc3_bonus_candidates` observation metadata. Generic object perception does not identify a bonus by color or shape alone. If a game supplies no bonus metadata and no verified bonus history, the correct behavior is to skip bonus pursuit rather than guess.

For minimum-step progress, the partition also runs breadth-first search over the bounded transition graph already observed by the world model. It identifies the shortest known route to a state with verified progress or a terminal win, and gives a small preference to the first action only if that exact action is still legal. Its optimality claim is strictly limited to the retained observed graph; it cannot guarantee a globally shortest route through unobserved game states. Full generalized planning still requires game-specific movement, collision, goal and reward semantics to be established from observations or explicit environment metadata.
