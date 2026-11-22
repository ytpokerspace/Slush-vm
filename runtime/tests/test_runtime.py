# Copyright (c) 2026 William Gunnell Cox
# SPDX-License-Identifier: MIT

import base64
import hashlib
import unittest

from shushos_runtime import (
    CapabilityError,
    _reply,
    arc2_fit_program,
    arc3_validate_action,
    csc_lch_compress,
    csc_lch_hydrate,
    csc_lch_ingest,
    csc_lch_reconstruct,
    glyphic_create_path,
    glyphic_hybridize_paths,
    glyphic_retrieve_paths,
    glyphic_verify_path,
    qbs_rank_hypotheses,
)


class Arc2AdapterTests(unittest.TestCase):
    def test_calls_authoritative_primitive_solver_and_requires_exact_fit(self):
        result = arc2_fit_program({
            "training_pairs": [
                {"input": [[0, 1], [0, 0]], "output": [[1, 0], [0, 0]]}
            ],
            "candidate_cap": 5000,
            "max_depth": 1,
        })
        self.assertTrue(result["exact_fit"])
        self.assertIsNotNone(result["program"])
        self.assertFalse(result["mcts_used"])
        self.assertIsNone(result["official_benchmark_score"])

    def test_bad_grid_is_reported_as_input_error(self):
        with self.assertRaises(CapabilityError):
            arc2_fit_program({"training_pairs": [{"input": [[1], [1, 2]], "output": [[1]]}]})


class Arc3BoundaryTests(unittest.TestCase):
    def test_action_must_be_in_environment_legal_action_list(self):
        result = arc3_validate_action({
            "game_id": "demo",
            "turn_id": "turn-1",
            "state_digest": "sha256:example",
            "available_actions": ["up", "down"],
            "proposed_action": "up",
        })
        self.assertTrue(result["valid"])
        self.assertFalse(result["environment_executed"])
        self.assertEqual(result["policy_status"], "externally_proposed")

    def test_rejects_unlisted_action(self):
        with self.assertRaises(CapabilityError) as ctx:
            arc3_validate_action({
                "game_id": "demo",
                "turn_id": "turn-1",
                "state_digest": "sha256:example",
                "available_actions": ["up", "down"],
                "proposed_action": "launch",
            })
        self.assertEqual(ctx.exception.code, "E_ACTION_NOT_ALLOWED")


class QbsTests(unittest.TestCase):
    def test_keeps_metrics_separate_and_builds_pareto_fronts(self):
        base = {
            "probability": 0.7, "feasibility": 0.8, "reasonability": 0.8,
            "expected_success": 0.6, "cost": 0.5, "risk": 0.4,
        }
        better = {
            "probability": 0.8, "feasibility": 0.9, "reasonability": 0.9,
            "expected_success": 0.7, "cost": 0.4, "risk": 0.3,
        }
        result = qbs_rank_hypotheses({"hypotheses": [
            {"id": "baseline", **base},
            {"id": "better", **better},
            {"id": "blocked", **better, "hard_constraints_met": False},
        ]})
        self.assertEqual(result["fronts"][0]["hypotheses"][0]["id"], "better")
        self.assertEqual(result["excluded"][0]["id"], "blocked")
        self.assertIsNone(result["aggregate_score"])
        self.assertFalse(result["probabilities_calibrated"])

    def test_rejects_duplicate_ids(self):
        item = {"id": "same", "probability": .5, "feasibility": .5, "reasonability": .5,
                "expected_success": .5, "cost": .5, "risk": .5}
        with self.assertRaises(CapabilityError):
            qbs_rank_hypotheses({"hypotheses": [item, item]})


class GlyphicTests(unittest.TestCase):
    def test_create_verify_retrieve_and_hybridize(self):
        created = glyphic_create_path({
            "path_id": "path-a",
            "codebook_version": "1.0.0",
            "codebook": {"observe": "👁️", "transform": "🔧", "verify": "🧪"},
            "events": [{"type": "observe"}, {"type": "transform"}],
            "tags": ["ARC", "grid"],
            "evidence": "original evidence",
        })
        record = created["record"]
        self.assertTrue(glyphic_verify_path(record)["valid"])
        retrieved = glyphic_retrieve_paths({"records": [record], "query_tags": ["arc"]})
        self.assertEqual(retrieved["matches"][0]["record"]["path_id"], "path-a")

        right = glyphic_create_path({
            "path_id": "path-b",
            "codebook_version": "1.0.0",
            "events": [{"type": "transform", "glyph": "🔧"}, {"type": "verify", "glyph": "🧪"}],
            "tags": ["validation"],
            "evidence": "second evidence",
        })["record"]
        hybrid = glyphic_hybridize_paths({"left": record, "right": right, "new_path_id": "path-h"})
        self.assertEqual(hybrid["record"]["overlap_events"], 1)
        self.assertEqual(len(hybrid["record"]["events"]), 3)
        self.assertEqual(hybrid["record"]["status"], "hypothesis")
        self.assertFalse(hybrid["verified"])

    def test_tampering_is_detected_and_duplicate_ids_rejected(self):
        record = glyphic_create_path({
            "path_id": "p", "events": [{"type": "x", "glyph": "❎"}], "evidence": "safe"
        })["record"]
        record["evidence_b64"] = base64.b64encode(b"changed").decode("ascii")
        self.assertFalse(glyphic_verify_path(record)["valid"])
        with self.assertRaises(CapabilityError):
            glyphic_create_path({"path_id": "p", "records": [record],
                                 "events": [{"type": "x", "glyph": "❎"}]})


class CscLchTests(unittest.TestCase):
    def test_ingest_compress_hydrate_and_exact_reconstruct(self):
        source = "ARC 🧠 grid\n"
        raw = source.encode("utf-8")
        record = csc_lch_ingest({
            "source_id": "source-1",
            "source_text": source,
            "nodes": [
                {"id": "n1", "tags": ["arc"], "tier": "T1", "start": 0, "end": len(raw),
                 "neighbors": ["n2"]},
                {"id": "n2", "tags": ["memory"], "tier": "Archive", "start": 0, "end": len(raw),
                 "neighbors": ["n1"]},
            ],
        })["record"]
        compressed = csc_lch_compress({"record": record, "retain_weight_at_least": .4})
        self.assertEqual(len(compressed["active_nodes"]), 1)
        self.assertEqual(len(compressed["stubs"]), 1)
        self.assertEqual(compressed["total_bytes"], compressed["source_bytes"] + compressed["graph_bytes"])

        hydrated = csc_lch_hydrate({
            "record": record, "query_tags": ["arc"], "budget_bytes": len(raw), "max_hops": 1
        })
        self.assertTrue(hydrated["source_integrity_verified"])
        self.assertEqual(hydrated["hydrated_bytes"], len(raw))
        rebuilt = csc_lch_reconstruct({"record": record})
        self.assertTrue(rebuilt["exact_reconstruction"])
        self.assertEqual(base64.b64decode(rebuilt["source_b64"]), raw)
        self.assertEqual(record["source_sha256"], hashlib.sha256(raw).hexdigest())

    def test_duplicate_ids_and_corruption_fail_closed(self):
        first = csc_lch_ingest({"source_id": "dup", "source_text": "hello"})["record"]
        with self.assertRaises(CapabilityError):
            csc_lch_ingest({"source_id": "dup", "records": [first], "source_text": "again"})
        corrupted = dict(first, source_b64=base64.b64encode(b"tampered").decode("ascii"))
        with self.assertRaises(CapabilityError) as ctx:
            csc_lch_reconstruct({"record": corrupted})
        self.assertEqual(ctx.exception.code, "E_INTEGRITY_FAILURE")


class McpProtocolTests(unittest.TestCase):
    def test_lists_tools_and_returns_structured_result(self):
        listing = _reply({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertGreaterEqual(len(listing["result"]["tools"]), 10)
        call = _reply({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {
                "name": "arc3_validate_action",
                "arguments": {"game_id": "g", "turn_id": "t", "state_digest": "d",
                              "available_actions": ["wait"], "proposed_action": "wait"},
            },
        })
        self.assertFalse(call["result"]["isError"])
        self.assertTrue(call["result"]["structuredContent"]["valid"])


if __name__ == "__main__":
    unittest.main()
