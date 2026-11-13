"""Regression tests for progress-aware action selection."""
from __future__ import annotations

import unittest

from arc3.action_glyph_scorer import ActionProbabilityScorer
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

    def test_repeated_click_without_progress_loses_to_new_coordinate(self):
        model = WorldModel()
        before = {"frame": [[0, 1]], "__arc3_levels_completed": 0}
        after = {"frame": [[1, 0]], "__arc3_levels_completed": 0}
        target = {"name": "ACTION6", "data": {"x": 12, "y": 2}}
        alternate = {"name": "ACTION6", "data": {"x": 40, "y": 20}}
        model.record_transition(target, before, after)

        scores = ActionProbabilityScorer().score(
            {"frame": [[1, 0]], "__arc3_levels_completed": 0},
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


if __name__ == "__main__":
    unittest.main()
