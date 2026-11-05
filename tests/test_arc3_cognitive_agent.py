"""Tests for the integrated ARC-AGI-3 cognitive agent."""
from __future__ import annotations

import unittest

from arc3.cognitive_agent import Arc3CognitiveAgent
from arc3.hypothesis_engine import HypothesisEngine
from arc3.world_model import WorldModel, state_signature


class WorldModelTests(unittest.TestCase):
    def test_state_signature_is_stable_for_mapping_order(self):
        self.assertEqual(state_signature({"a": 1, "b": 2}), state_signature({"b": 2, "a": 1}))

    def test_records_change_without_claiming_goal_progress(self):
        model = WorldModel()
        before = {"grid": [[0]], "__arc3_levels_completed": 0}
        after = {"grid": [[1]], "__arc3_levels_completed": 0}
        event = model.record_transition({"name": "ACTION1"}, before, after)
        self.assertTrue(event["observation_changed"])
        self.assertFalse(event["explicit_progress_observed"])
        stats = model.action_stats({"name": "ACTION1"})
        self.assertEqual(stats["changed"], 1)
        self.assertEqual(stats["explicit_progress"], 0)

    def test_exact_transition_lookup_does_not_generalize(self):
        model = WorldModel()
        before = {"room": 1}
        after = {"room": 2}
        action = {"name": "ACTION1"}
        model.record_transition(action, before, after)
        self.assertEqual(model.predict_exact(before, action), state_signature(after))
        self.assertIsNone(model.predict_exact({"room": 9}, action))

    def test_explicit_level_progress_is_recorded(self):
        model = WorldModel()
        event = model.record_transition(
            {"name": "ACTION2"},
            {"__arc3_levels_completed": 0},
            {"__arc3_levels_completed": 1},
        )
        self.assertTrue(event["explicit_progress_observed"])


class HypothesisEngineTests(unittest.TestCase):
    def test_only_explicit_win_marks_completion_verified(self):
        engine = HypothesisEngine()
        engine.observe({"__arc3_state": "ACTIVE"})
        self.assertFalse(engine.hypotheses)
        engine.observe({"__arc3_state": "WIN"})
        snapshot = engine.snapshot()
        completion = next(item for item in snapshot["hypotheses"] if item["id"] == "terminal-win")
        self.assertEqual(completion["status"], "explicitly_verified")

    def test_visual_navigation_remains_heuristic(self):
        engine = HypothesisEngine()
        engine.observe({"grid": [[0]]}, {"target_center": [2, 3]})
        item = engine.snapshot()["hypotheses"][0]
        self.assertEqual(item["source"], "visual_heuristic")
        self.assertEqual(item["status"], "supported_but_unverified")


class CognitiveAgentTests(unittest.TestCase):
    def test_selects_only_a_supplied_legal_action(self):
        agent = Arc3CognitiveAgent()
        legal = [{"name": "LEFT"}, {"name": "RIGHT"}]
        result = agent.select_action({"grid": [[0]]}, legal)
        self.assertIn(result["action"], legal)

    def test_prefers_navigation_candidate_but_explores_ties(self):
        agent = Arc3CognitiveAgent()
        observation = {"grid": [[0, 1]]}
        legal = [
            {"name": "ACTION1", "score": 100.0},
            {"name": "ACTION2", "score": 0.0},
        ]
        first = agent.select_action(observation, legal, {"action": "ACTION1"})
        self.assertEqual(first["action"]["name"], "ACTION1")
        second = agent.select_action(observation, legal, {"action": "ACTION1"})
        self.assertEqual(second["action"]["name"], "ACTION2")

    def test_observed_noop_history_penalizes_repeated_action_family(self):
        agent = Arc3CognitiveAgent()
        before = {"room": 1}
        for _ in range(3):
            agent.record_transition({"name": "WAIT"}, before, before)
        result = agent.select_action(
            before, [{"name": "WAIT"}, {"name": "MOVE"}]
        )
        self.assertEqual(result["action"]["name"], "MOVE")

    def test_transition_updates_world_model_and_hypothesis_ledger(self):
        agent = Arc3CognitiveAgent()
        before = {"room": 1}
        after = {"room": 2}
        event = agent.record_transition({"name": "MOVE"}, before, after)
        self.assertTrue(event["observation_changed"])
        snapshot = agent.snapshot()
        self.assertEqual(snapshot["world_model"]["transition_count"], 1)
        self.assertTrue(snapshot["hypothesis_engine"]["hypotheses"])

    def test_no_legal_actions_is_reported(self):
        result = Arc3CognitiveAgent().select_action({"room": 1}, [])
        self.assertIsNone(result["action"])
        self.assertEqual(result["status"], "no_legal_actions")

    def test_action_scores_are_not_reported_as_probabilities(self):
        result = Arc3CognitiveAgent().select_action(
            {"room": 1}, [{"name": "MOVE", "score": 4}]
        )
        self.assertIn("not a calibrated probability", result["diagnostics"]["score_semantics"])


if __name__ == "__main__":
    unittest.main()
