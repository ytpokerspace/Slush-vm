import unittest

from arc3.action_glyph_scorer import ActionProbabilityScorer, encode_action
from arc3.world_model import WorldModel


class ActionGlyphScorerTests(unittest.TestCase):
    def test_directional_action_maps_to_glyph(self):
        encoded = encode_action({"name": "MOVE_RIGHT"})
        self.assertEqual(encoded["glyph"], "➡️")
        self.assertEqual(encoded["action_name"], "MOVE_RIGHT")

    def test_coordinate_payload_maps_to_click_glyph(self):
        encoded = encode_action({"name": "ACTION1", "data": {"x": 4, "y": 7}})
        self.assertEqual(encoded["glyph"], "🖱️")
        self.assertEqual(encoded["payload"], {"x": 4, "y": 7})

    def test_unknown_action_stays_environment_action(self):
        encoded = encode_action({"name": "SPECIAL_17"})
        self.assertEqual(encoded["glyph"], "🎮")
        self.assertEqual(encoded["legal_source"], "current_environment_action_space")

    def test_empirical_probability_uses_exact_state_action_evidence(self):
        model = WorldModel()
        before = {"frame": [[0, 1]], "__arc3_levels_completed": 0}
        after = {"frame": [[0, 2]], "__arc3_levels_completed": 1}
        action = {"name": "MOVE_RIGHT"}
        model.observe(before)
        model.record_transition(action, before, after)
        ranked = ActionProbabilityScorer().score(
            before, [action, {"name": "MOVE_LEFT"}], model
        )
        right = next(row for row in ranked if row["action_name"] == "MOVE_RIGHT")
        left = next(row for row in ranked if row["action_name"] == "MOVE_LEFT")
        self.assertEqual(right["probability"]["status"], "evidence_backed")
        self.assertGreater(right["probability"]["verified_progress_or_win"],
                           left["probability"]["verified_progress_or_win"])
        self.assertEqual(left["probability"]["status"], "prior_only")

    def test_no_legal_action_is_invented(self):
        model = WorldModel()
        actions = [{"name": "MOVE_UP"}]
        ranked = ActionProbabilityScorer().score({"frame": [[0]]}, actions, model)
        self.assertEqual([row["action_name"] for row in ranked], ["MOVE_UP"])


if __name__ == "__main__":
    unittest.main()
