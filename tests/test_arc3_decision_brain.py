"""Regression tests for progress-aware action selection."""
from __future__ import annotations

import unittest

from arc3.action_glyph_scorer import ActionProbabilityScorer
from arc3.glyph_agent import GlyphArc3Agent
from arc3.strategy_studio import brainstorm_action_priors
from arc3.world_model import WorldModel, action_signature


class ExactActionMemoryTests(unittest.TestCase):
    def test_click_coordinates_have_separate_episode_history(self):
        model = WorldModel()
        before = {"frame": [[0, 1]], "__arc3_levels_completed": 0}
        after = {"frame": [[1, 0]], "__arc3_levels_completed": 0}
        first = {"name": "ACTION6", "data": {"x": 3, "y": 4}}
        second = {"name": "ACTION6", "data": {"x": 8, "y": 9}}

        model.record_transition(first, before, after)

        self.assertEqual(model.action_signature_stats(first)["attempts"], 1)
        self.assertEqual(model.action_signature_stats(second)["attempts"], 0)
        self.assertEqual(model.action_stats(first)["attempts"], 1)

    def test_state_action_evidence_overrides_episode_history(self):
        model = WorldModel()
        action = {"name": "ACTION1"}
        state_a = {"scene": "a", "__arc3_levels_completed": 0}
        after_a = {"scene": "a-after", "__arc3_levels_completed": 0}
        state_b = {"scene": "b", "__arc3_levels_completed": 0}
        after_b = {"scene": "b-after", "__arc3_levels_completed": 1}

        model.record_transition(action, state_a, after_a)
        model.record_transition(action, state_b, after_b)

        rows = ActionProbabilityScorer().score(state_b, [action], model)
        probability = rows[0]["probability"]
        self.assertEqual(probability["evidence_scope"], "exact_state_action")
        self.assertEqual(probability["evidence_attempts"], 1)
        self.assertEqual(probability["verified_progress_or_win_count"], 1)
        self.assertEqual(rows[0]["factors"]["repeat_penalty"], 0.0)

    def test_repeat_penalty_is_local_to_the_current_state(self):
        model = WorldModel()
        state = {"frame": [[0, 1]], "__arc3_levels_completed": 0}
        target = {"name": "ACTION6", "data": {"x": 12, "y": 2}}
        alternate = {"name": "ACTION6", "data": {"x": 40, "y": 20}}
        model.record_transition(target, state, state)

        scores = ActionProbabilityScorer().score(
            state,
            [target, alternate],
            model,
            strategy_priors={
                action_signature(target): 0.9,
                action_signature(alternate): 0.1,
            },
        )

        self.assertEqual(scores[0]["payload"], alternate["data"])
        repeated = next(row for row in scores if row["payload"] == target["data"])
        self.assertGreater(repeated["factors"]["repeat_penalty"], 0)
        self.assertEqual(repeated["probability"]["evidence_scope"], "exact_state_action")


class ProgressAwareStrategyTests(unittest.TestCase):
    def test_untried_action_family_beats_repeated_nonprogress_action(self):
        model = WorldModel()
        before = {"room": 0, "__arc3_levels_completed": 0}
        for index in range(4):
            after = {"room": index + 1, "__arc3_levels_completed": 0}
            model.record_transition({"name": "ACTION1"}, before, after)

        actions = [{"name": "ACTION1"}, {"name": "ACTION2"}]
        result = brainstorm_action_priors(actions, None, model)

        self.assertEqual(result["candidates"][0]["family"], "ACTION2")
        self.assertIn("not yet been tested", " ".join(result["candidates"][0]["evidence"]))

    def test_glyph_agent_passes_state_local_attempt_history(self):
        agent = GlyphArc3Agent(simulations=1, depth=1)
        observation = {"frame": [[0]], "__arc3_levels_completed": 0}
        action = {"name": "ACTION1"}
        agent.record_transition(action, observation, observation)

        result = agent.select_action(observation, [action])
        candidate = result["diagnostics"]["strategy_studio"]["candidates"][0]
        self.assertEqual(candidate["repeat_cost"], 0.75)
        self.assertIn("exact action or click location was tried", candidate["evidence"])
        self.assertNotIn("not yet tried in this exact state", candidate["evidence"])

    def test_progress_or_win_is_counted_once_per_attempt(self):
        model = WorldModel()
        action = {"name": "ACTION6", "data": {"x": 2, "y": 3}}
        before = {"__arc3_levels_completed": 0}
        after = {"__arc3_levels_completed": 1, "__arc3_state": "WIN"}

        model.record_transition(action, before, after)
        first = ActionProbabilityScorer().score({"unseen": 1}, [action], model)[0]["probability"]
        self.assertEqual(first["evidence_attempts"], 1)
        self.assertEqual(first["verified_progress_or_win_count"], 1)

        model.record_transition(action, after, after)
        second = ActionProbabilityScorer().score({"unseen": 2}, [action], model)[0]["probability"]
        self.assertEqual(second["evidence_attempts"], 2)
        self.assertEqual(second["verified_progress_or_win_count"], 2)


if __name__ == "__main__":
    unittest.main()
