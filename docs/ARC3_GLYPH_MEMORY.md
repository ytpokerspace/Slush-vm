# ARC-AGI-3 Hierarchical Glyph Gameplay Memory

## Purpose

Keep an evidence-linked memory of what happened, where objects were, which actions were tried, and whether they produced verified progress, no visible change, or terminal failure. This is a runner-side memory layer and works with both legacy and glyph policies.

## Memory levels

1. **Event records:** one record per observed action transition. Includes action and coordinates, before/after scene digests, exact before/after grid SHA-256 values, grid dimensions, before/after object cell coordinates and bounding boxes, tracked positions, navigation target, run context (game, seed, policy), level counters, and outcome classification.
2. **Chunk summaries:** by default, every four events are summarized into a glyph string, outcome/action counts, scene sequence, position sequence, and checksum.
3. **Rollups:** every four chunks are summarized again into a higher-level glyph with aggregated outcome/action counts and the constituent chunk checksums.

The structured records remain authoritative. Emoji glyphs are compact mnemonics and indexes, not lossless encodings. The SHA-256 checksum detects content changes; it does not reconstruct a scene. Spatial manifests preserve the object coordinates needed to inspect positions.

## Outcome semantics

- 🏆 = environment explicitly reports WIN.
- 📈 = runner observes explicit level progress.
- ⏸️ = before/after observations are identical.
- 💥 = environment explicitly reports game over/loss.
- 🔄 = observation changed but the outcome is not yet classified as progress or success.

No predicted transition is written as an observed event.

## Persistence

By default, the runner appends JSONL records to `arc3_memory/<game-id>.jsonl`. Override with `--memory-log PATH`; use `--no-persistent-memory` for in-memory-only operation. The log is append-only. Each line is independently parseable JSON.

Example:

```bash
python -m arc3.arc_agi_runner --policy glyph --game-id ls20 --memory-log arc3_memory/ls20.jsonl
```

## Integrity and limitations

- Scene hashes cover the normalized grid layers. Object manifests retain observed component cells and boxes when perception provides them.
- If a game exposes non-grid state, the record still has a deterministic scene digest but no inferred spatial object map.
- A checksum verifies identity/integrity; it is not a substitute for source observations.
- Summaries are emitted after four events by default. A final partial chunk is sealed at run end.
- Reload restores recorded events/chunks/rollups for inspection; the active pending chunk begins fresh after process restart.
- No learned rule is treated as fact unless it came from an observed transition.
