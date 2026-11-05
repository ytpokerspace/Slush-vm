"""Tests for ARC-AGI-3 brainstorming strategy synthesis and shallow MCTS."""
from __future__ import annotations

import unittest

from arc3.cognitive_agent import Arc3CognitiveAgent
from arc3.shallow_mcts import ShallowMCTS
from arc3.strategy_studio import brainstorm_action_priors
from arc3.world_model import WorldModel, action_signature, state_signature


class StrategyStudioTests(unittest.TestCase):
    def test_runs_two_generation_rounds_and_four_refinement_passes(self):
        model = WorldModel()
        actions = [{"name": "LEFT"}, {"name": "RIGHT"}]
        result = brainstorm_action_priors(actions, {"action": "RIGHT"}, model, set())
        self.assertEqual(result["generation_rounds"], 2)
        self.assertEqual(result["refinement_passes"], 4)
        self.assertEqual(result["candidate_count"], 2)
        self.assertAlmostEqual(sum(result["priors"].values()), 1.0)
        self.assertIn("not probability", result["prior_semantics"])

    def test_visual_route_is_a_prior_not_a_success_probability(self):
        model = WorldModel()
        actions = [{"name": "LEFT"}, {"name": "RIGHT"}]
        result = brainstorm_action_priors(actions, {"action": "RIGHT"}, model, set())
        ranked = result["candidates"]
        self.assertEqual(ranked[0]["family"], "RIGHT")
        self.assertGreater(result["priors"][action_signature(actions[1])],
                           result["priors"][action_signature(actions[0])])


class ShallowMCTSTests(unittest.TestCase):
    def test_only_uses_observed_transitions_and_legal_actions(self):
        model = WorldModel()
        before = {"room": 0}
        after = {"room": 1}
        actions = [{"name": "MOVE"}, {"name": "WAIT"}]
        model.observe(before)
        model.register_legal_actions(before, actions)
        model.record_transition(actions[0], before, after)
        model.observe(after)
        model.register_legal_actions(after, [{"name": "EXIT"}])
        search = ShallowMCTS(model, depth=3, simulations=32, seed=7)
        result = search.search(
            before, actions,
            {action_signature(actions[0]): 0.8, action_signature(actions[1]): 0.2},
        )
        self.assertIn(result["action"], actions)
        self.assertEqual(result["diagnostics"]["depth_limit"], 3)
        self.assertEqual(result["diagnostics"]["simulations"], 32)
        self.assertIn("observed transitions", result["diagnostics"]["model_boundary"])

    def test_progress_posterior_uses_actual_edge_outcomes(self):
        model = WorldModel()
        before = {"room": 0, "__arc3_levels_completed": 0}
        after = {"room": 1, "__arc3_levels_completed": 1}
        action = {"name": "MOVE"}
        model.record_transition(action, before, after)
        stats = model.edge_stats_by_ids(state_signature(before), action)
        self.assertEqual(stats["attempts"], 1)
        self.assertEqual(stats["verified_progress_or_win"], 1)
        self.assertEqual((stats["verified_progress_or_win"] + 1) /
                         (stats["attempts"] + 2), 2 / 3)

    def test_unknown_transition_is_not_fabricated(self):
        model = WorldModel()
        observation = {"room": 0}
        actions = [{"name": "UNKNOWN"}]
        result = ShallowMCTS(model, depth=3, simulations=8).search(
            observation, actions, {action_signature(actions[0]): 1.0}
        )
        self.assertIsNone(model.sampled_successor(
            state_signature(observation), actions[0], __import__("random").Random(0)
        ))
        self.assertEqual(result["action"], actions[0])


class CognitiveAgentMCTSTests(unittest.TestCase):
    def test_agent_exposes_brainstorm_and_mcts_diagnostics(self):
        agent = Arc3CognitiveAgent(mcts_depth=3, mcts_simulations=16)
        legal = [{"name": "LEFT"}, {"name": "RIGHT"}]
        result = agent.select_action({"grid": [[0, 1]]}, legal, {"action": "RIGHT"})
        self.assertIn(result["action"], legal)
        diagnostics = result["diagnostics"]
        self.assertEqual(diagnostics["strategy_studio"]["generation_rounds"], 2)
        self.assertEqual(diagnostics["strategy_studio"]["refinement_passes"], 4)
        self.assertEqual(diagnostics["mcts"]["simulations"], 16)
        self.assertIn("posterior mean", diagnostics["mcts"]["probability_semantics"])

    def test_agent_avoids_repeating_same_action_after_unchanged_state(self):
        agent = Arc3CognitiveAgent()
        observation = {"room": 0}
        legal = [{"name": "LEFT"}, {"name": "RIGHT"}]
        first = agent.select_action(observation, legal, {"action": "LEFT"})
        agent.record_transition(first["action"], observation, observation)
        second = agent.select_action(observation, legal, {"action": "LEFT"})
        self.assertNotEqual(second["action"]["name"], "LEFT")


if __name__ == "__main__":
    unittest.main()
