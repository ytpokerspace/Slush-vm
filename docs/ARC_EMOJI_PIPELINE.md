# ARC Emoji Pipeline (experimental)

## Emoji-only instruction sequence

The canonical instruction artifact is `examples/arc_agi_3.emoji`. It contains emoji tokens only:

```text
🧩 🌊 🔍 🧱 🧭 ⚙️ 🌳 📜 🧪 ✅ 🎯 🏁
```

This sequence is a compact prompt/interface, not executable bytecode by itself. An LLM must interpret it, or a separately implemented parser must assign formal opcode semantics. This PR does not claim either behavior is implemented.

## Implemented in this PR

- Rectangular integer-grid validation.
- 4- and 8-connected flood-fill segmentation of non-background cells.
- A deterministic candidate set: identity, horizontal/vertical flip, 180/90/270-degree rotation.
- Exact demonstration-pair consistency filtering and stable tie-breaking.
- Explicit `no_prediction` status when no candidate fits or examples are absent.
- Unit tests and a seeded synthetic benchmark with accuracy, latency, and failure output.

## Not implemented / hypotheses

- Full ARC-AGI-3 interactive environment integration, observations, action APIs, reward handling, and episode management.
- MCTS, learned policy/value functions, general program synthesis, or a general-purpose DSL interpreter.
- Official ARC-AGI-3 evaluation or any claim of benchmark score improvement.
- Automatic interpretation of the emoji sequence into executable VM instructions.

The geometric candidate set is a deliberately narrow baseline. It will fail tasks requiring recoloring, object counting, conditional logic, stateful interaction, or transformations outside the candidate set.

## Run locally

From repository root:

```sh
python -m unittest discover -s tests -p 'test_arc_emoji_solver.py' -v
python tools/benchmark_arc_emoji.py
```

The benchmark uses seed `20261025` and 120 generated square-grid cases. The output includes environment metadata; latency is descriptive, not a portable performance guarantee. The task generator creates demonstrations using the same finite transform family, so the result is a sanity check of this implementation, not evidence of ARC-AGI-3 generalization.

## Failure analysis

- **No matching candidate:** return `no_prediction`; do not silently guess.
- **Ambiguous demonstrations:** the first transform in documented order wins. Symmetric grids can conceal the generating transform.
- **Out-of-family task:** likely no match or an incorrect fit on underconstrained examples.
- **Input shape/type errors:** fail fast with `ValueError`.
- **Interactive tasks:** unsupported until an environment adapter and action loop are implemented.
