import json
import tempfile
import unittest
from pathlib import Path

from arc3.glyph_game_memory import GlyphGameplayMemory, scene_manifest


class GlyphGameplayMemoryTests(unittest.TestCase):
    def test_scene_checksum_changes_when_grid_changes(self):
        a = {"frame": [[0, 1], [0, 0]]}
        b = {"frame": [[0, 0], [0, 1]]}
        self.assertNotEqual(scene_manifest(a)["grid_sha256"], scene_manifest(b)["grid_sha256"])

    def test_event_records_action_outcome_and_spatial_manifest(self):
        memory = GlyphGameplayMemory(chunk_size=4)
        before = {"frame": [[0, 1], [0, 0]], "__arc3_state": "RUNNING"}
        after = {"frame": [[0, 0], [0, 1]], "__arc3_state": "RUNNING"}
        event = memory.record_transition(
            {"name": "ACTION2", "data": {"x": 1, "y": 1}},
            before, after,
            perception={"objects": [{
                "object_id": "obj_1", "dominant_color": 1, "shape": "single_cell",
                "area": 1, "bbox": {"x": 1, "y": 1, "width": 1, "height": 1},
                "cells": [[1, 1]],
            }]},
        )
        self.assertEqual(event["outcome"], "state_changed_unclassified")
        self.assertIn("🔄", event["glyph"])
        self.assertEqual(event["objects"][0]["bbox"]["x"], 1)
        self.assertEqual(len(event["grid_checksum"]), 64)

    def test_chunk_and_rollup_hierarchically_compress_events(self):
        memory = GlyphGameplayMemory(chunk_size=2, chunks_per_rollup=2)
        for index in range(4):
            before = {"frame": [[0, index]]}
            after = {"frame": [[0, index + 1]]}
            memory.record_transition({"name": "ACTION1"}, before, after)
        self.assertEqual(len(memory.chunks), 2)
        self.assertEqual(len(memory.rollups), 1)
        self.assertEqual(memory.chunks[0]["action_outcomes"]["ACTION1"]["state_changed_unclassified"], 2)
        self.assertIn("🧱", memory.chunks[0]["glyph"])
        self.assertIn("🗂️", memory.rollups[0]["glyph"])
        self.assertEqual(memory.rollups[0]["first_step"], 1)
        self.assertEqual(memory.rollups[0]["last_step"], 4)
        self.assertEqual(memory.rollups[0]["action_outcomes"]["ACTION1"]["state_changed_unclassified"], 4)

    def test_verified_progress_and_no_change_are_distinguished(self):
        memory = GlyphGameplayMemory()
        unchanged = {"frame": [[0]], "__arc3_state": "RUNNING"}
        no_change = memory.record_transition({"name": "ACTION1"}, unchanged, unchanged)
        progress = memory.record_transition(
            {"name": "ACTION2"},
            {"frame": [[0]], "__arc3_levels_completed": 0},
            {"frame": [[1]], "__arc3_levels_completed": 1},
            explicit_progress=True,
        )
        self.assertEqual(no_change["outcome"], "no_visible_change")
        self.assertEqual(progress["outcome"], "verified_progress")

    def test_jsonl_persistence_reloads_records(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "memory.jsonl")
            first = GlyphGameplayMemory(chunk_size=1, log_path=path)
            first.record_transition({"name": "ACTION1"}, {"frame": [[0]]}, {"frame": [[1]]})
            second = GlyphGameplayMemory(chunk_size=1, log_path=path)
            self.assertEqual(second.step_count, 1)
            self.assertEqual(len(second.events), 1)
            self.assertEqual(len(second.chunks), 1)
            records = [json.loads(line) for line in Path(path).read_text().splitlines()]
            self.assertEqual([row["record_type"] for row in records], ["event", "chunk"])


if __name__ == "__main__":
    unittest.main()
