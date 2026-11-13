"""Hierarchical emoji memory for ARC-AGI-3 gameplay.

Stores compact, checksummed scene manifests and outcome-linked glyph records.
Glyphs are indexes/mnemonics; structured payloads remain authoritative.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=repr)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _layers(observation: Any) -> list[list[list[Any]]]:
    if not isinstance(observation, dict):
        return []
    frame = observation.get("frame", observation.get("grid", observation.get("board")))
    if not isinstance(frame, list) or not frame:
        return []
    if isinstance(frame[0], list) and frame[0] and not isinstance(frame[0][0], list):
        return [frame]
    if isinstance(frame[0], list) and frame[0] and isinstance(frame[0][0], list):
        return [layer for layer in frame if isinstance(layer, list)]
    return []


def scene_manifest(observation: Any, perception: dict[str, Any] | None = None,
                   tracks: dict[str, Any] | None = None) -> dict[str, Any]:
    """Describe exact grid contents by digest plus spatial object summaries."""
    layers = _layers(observation)
    layer_shapes = [[len(layer), max((len(row) for row in layer if isinstance(row, list)), default=0)]
                    for layer in layers]
    cell_payload = [[list(row) for row in layer] for layer in layers]
    object_rows = []
    objects = (perception or {}).get("objects", [])
    for obj in objects:
        box = obj.get("bbox", {})
        object_rows.append({
            "id": obj.get("object_id"),
            "color": obj.get("dominant_color"),
            "shape": obj.get("shape"),
            "area": obj.get("area"),
            "bbox": {key: box.get(key) for key in ("x", "y", "width", "height", "x2", "y2")},
            "cells": sorted([list(cell) for cell in obj.get("cells", [])]),
        })
    track_rows = []
    for track in (tracks or {}).get("tracks", []):
        track_rows.append({
            "id": track.get("track_id"),
            "center": track.get("center"),
            "motion": track.get("motion_delta"),
            "missed": track.get("missed_frames", 0),
            "color": track.get("dominant_color"),
        })
    return {
        "grid_shape": layer_shapes,
        "grid_sha256": _digest(cell_payload),
        "grid_cell_count": sum(len(row) for layer in layers for row in layer if isinstance(row, list)),
        "objects": object_rows,
        "tracks": track_rows,
        "scene_sha256": _digest({"shape": layer_shapes, "grid": cell_payload,
                                 "objects": object_rows, "tracks": track_rows}),
    }


@dataclass
class GlyphGameplayMemory:
    """Bounded recent event memory plus recursive summaries and optional JSONL persistence."""
    chunk_size: int = 4
    chunks_per_rollup: int = 4
    max_events: int = 256
    max_chunks: int = 128
    log_path: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    rollups: list[dict[str, Any]] = field(default_factory=list)
    step_count: int = 0
    _pending: list[dict[str, Any]] = field(default_factory=list)
    _pending_chunks: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.chunk_size < 1 or self.chunks_per_rollup < 2:
            raise ValueError("chunk_size must be positive and chunks_per_rollup at least 2")
        if self.log_path:
            self._load_log()

    def _append_disk(self, record: dict[str, Any]) -> None:
        if not self.log_path:
            return
        path = Path(self.log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical(record) + "\n")

    def _load_log(self) -> None:
        path = Path(self.log_path or "")
        if not path.exists():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            kind = record.get("record_type")
            if kind == "event":
                self.events.append(record)
                self.step_count = max(self.step_count, int(record.get("step", 0)))
            elif kind == "chunk":
                self.chunks.append(record)
            elif kind == "rollup":
                self.rollups.append(record)
        self.events = self.events[-self.max_events:]
        self.chunks = self.chunks[-self.max_chunks:]

    @staticmethod
    def _outcome(before: Any, after: Any, explicit_progress: bool) -> tuple[str, str]:
        state = str(after.get("__arc3_state", "")).upper() if isinstance(after, dict) else ""
        if state == "WIN":
            return "🏆", "verified_win"
        if state in {"GAME_OVER", "LOSE", "LOSS"}:
            return "💥", "terminal_failure"
        if explicit_progress:
            return "📈", "verified_progress"
        if scene_manifest(before)["grid_sha256"] == scene_manifest(after)["grid_sha256"]:
            return "⏸️", "no_visible_change"
        return "🔄", "state_changed_unclassified"

    def record_transition(self, action: Any, before: Any, after: Any, *,
                          perception: dict[str, Any] | None = None,
                          tracks: dict[str, Any] | None = None,
                          before_perception: dict[str, Any] | None = None,
                          before_tracks: dict[str, Any] | None = None,
                          navigation: dict[str, Any] | None = None,
                          explicit_progress: bool = False) -> dict[str, Any]:
        """Record one observed transition; predicted states must never be passed as observations."""
        self.step_count += 1
        scene_before = scene_manifest(before, before_perception, before_tracks)
        scene_after = scene_manifest(after, perception, tracks)
        glyph, outcome = self._outcome(before, after, explicit_progress)
        action_name = action.get("name", "unknown") if isinstance(action, dict) else str(action)
        coords = action.get("data") if isinstance(action, dict) else None
        event_core = {
            "step": self.step_count,
            "action": action_name,
            "coordinates": coords,
            "before_scene": scene_before["scene_sha256"],
            "after_scene": scene_after["scene_sha256"],
            "before_grid_checksum": scene_before["grid_sha256"],
            "grid_checksum": scene_after["grid_sha256"],
            "before_grid_shape": scene_before["grid_shape"],
            "grid_shape": scene_after["grid_shape"],
            "before_objects": scene_before["objects"],
            "objects": scene_after["objects"],
            "before_tracks": scene_before["tracks"],
            "tracks": scene_after["tracks"],
            "outcome": outcome,
            "explicit_progress": bool(explicit_progress),
            "navigation_target": (navigation or {}).get("target_center"),
        }
        event_id = _digest(event_core)
        event = {
            "record_type": "event",
            "event_id": event_id,
            "glyph": f"🎮{self.step_count} {glyph}{action_name} 🧭{len(scene_after['objects'])}obj 🔐{scene_after['scene_sha256'][:12]}",
            **event_core,
        }
        self.events.append(event)
        self.events = self.events[-self.max_events:]
        self._pending.append(event)
        self._append_disk(event)
        if len(self._pending) >= self.chunk_size:
            self._seal_chunk()
        return event

    def _seal_chunk(self) -> dict[str, Any] | None:
        if not self._pending:
            return None
        rows = self._pending
        self._pending = []
        outcomes = Counter(row["outcome"] for row in rows)
        actions = Counter(row["action"] for row in rows)
        action_outcomes: dict[str, Counter[str]] = {}
        for row in rows:
            action_outcomes.setdefault(row["action"], Counter())[row["outcome"]] += 1
        positions = [{"before": row.get("before_objects", []), "after": row.get("objects", [])}
                     for row in rows]
        core = {
            "first_step": rows[0]["step"],
            "last_step": rows[-1]["step"],
            "event_ids": [row["event_id"] for row in rows],
            "outcomes": dict(sorted(outcomes.items())),
            "actions": dict(sorted(actions.items())),
            "action_outcomes": {name: dict(sorted(counts.items())) for name, counts in sorted(action_outcomes.items())},
            "scene_sequence": [row["after_scene"] for row in rows],
            "position_sequence": positions,
            "worked": outcomes.get("verified_win", 0) + outcomes.get("verified_progress", 0),
            "did_not_work": outcomes.get("no_visible_change", 0) + outcomes.get("terminal_failure", 0),
        }
        checksum = _digest(core)
        glyphs = "".join("🏆" if row["outcome"] == "verified_win" else
                         "📈" if row["outcome"] == "verified_progress" else
                         "⏸️" if row["outcome"] == "no_visible_change" else
                         "💥" if row["outcome"] == "terminal_failure" else "🔄"
                         for row in rows)
        chunk = {
            "record_type": "chunk",
            "glyph": f"🧱{core['first_step']}-{core['last_step']} {glyphs} 🔐{checksum[:16]}",
            "checksum": checksum,
            **core,
        }
        self.chunks.append(chunk)
        self.chunks = self.chunks[-self.max_chunks:]
        self._pending_chunks.append(chunk)
        self._append_disk(chunk)
        if len(self._pending_chunks) >= self.chunks_per_rollup:
            self._seal_rollup()
        return chunk

    def _seal_rollup(self) -> dict[str, Any] | None:
        if not self._pending_chunks:
            return None
        rows = self._pending_chunks
        self._pending_chunks = []
        action_outcomes: dict[str, Counter[str]] = {}
        for row in rows:
            for action, outcomes in row.get("action_outcomes", {}).items():
                action_outcomes.setdefault(action, Counter()).update(outcomes)
        core = {
            "first_step": rows[0]["first_step"],
            "last_step": rows[-1]["last_step"],
            "chunk_checksums": [row["checksum"] for row in rows],
            "outcomes": dict(sorted(sum_counters(row["outcomes"] for row in rows).items())),
            "actions": dict(sorted(sum_counters(row["actions"] for row in rows).items())),
            "action_outcomes": {name: dict(sorted(counts.items())) for name, counts in sorted(action_outcomes.items())},
        }
        checksum = _digest(core)
        rollup = {
            "record_type": "rollup",
            "glyph": f"🗂️{core['first_step']}-{core['last_step']} 🧠{len(rows)}chunks 🔐{checksum[:20]}",
            "checksum": checksum,
            **core,
        }
        self.rollups.append(rollup)
        self._append_disk(rollup)
        return rollup

    def flush(self) -> dict[str, Any]:
        """Seal partial summaries at end of a run without losing their event references."""
        chunk = self._seal_chunk() if self._pending else None
        rollup = self._seal_rollup() if len(self._pending_chunks) >= self.chunks_per_rollup else None
        return {"chunk": chunk, "rollup": rollup}

    def snapshot(self) -> dict[str, Any]:
        return {
            "steps_recorded": self.step_count,
            "recent_event_count": len(self.events),
            "chunk_count": len(self.chunks),
            "rollup_count": len(self.rollups),
            "pending_events": len(self._pending),
            "pending_chunks": len(self._pending_chunks),
            "recent_glyphs": [row["glyph"] for row in self.events[-12:]],
            "recent_chunks": [row["glyph"] for row in self.chunks[-8:]],
            "recent_rollups": [row["glyph"] for row in self.rollups[-4:]],
            "persistence": self.log_path or "memory_only",
            "checksum_algorithm": "SHA-256 over canonical JSON",
            "glyph_semantics": "glyphs are compact indexes; structured manifests and checksums remain authoritative",
        }


def sum_counters(rows: Any) -> Counter[str]:
    total: Counter[str] = Counter()
    for row in rows:
        total.update(row)
    return total
