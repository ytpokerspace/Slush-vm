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
