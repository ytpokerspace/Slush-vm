import unittest

from arc3.game_dynamics_memory import GameDynamicsMemory
from arc3.world_model import action_signature


class GameDynamicsMemoryTests(unittest.TestCase):
    def test_predicts_next_position_from_observed_track_delta(self):
        memory = GameDynamicsMemory()
        result = memory.predict_object_positions({
            "tracks": [{
                "track_id": "p1", "center": [4, 5],
                "motion_delta": [1, -1], "missed_frames": 0,
            }]
        })
        self.assertEqual(result["objects"][0]["predicted_next_position"], [5.0, 4.0])
        self.assertFalse(result["predictions_are_observations"])

    def test_bonus_requires_measurable_evidence_and_no_completion_risk(self):
        memory = GameDynamicsMemory(step_cost_per_step=0.5)
        signature = action_signature({"name": "MOVE_RIGHT"})
        result = memory.evaluate_bonus_candidates([{
            "score_gain": 10,
            "collection_probability": 0.9,
            "extra_steps": 2,
            "completion_probability_before": 0.8,
            "completion_probability_after": 0.8,
            "action_signature": signature,
            "evidence": "verified_history",
        }])
        self.assertEqual(result[0]["status"], "viable")
        self.assertAlmostEqual(result[0]["net_gain"], 8.0)

    def test_bonus_is_rejected_when_completion_odds_drop(self):
        memory = GameDynamicsMemory()
        result = memory.evaluate_bonus_candidates([{
            "score_gain": 100, "collection_probability": 1.0,
            "extra_steps": 0, "completion_probability_before": 0.9,
            "completion_probability_after": 0.89,
            "action_signature": "legal-action", "evidence": "verified_history",
        }])
        self.assertEqual(result[0]["status"], "rejected_completion_risk")

    def test_bonus_is_rejected_without_evidence(self):
        result = GameDynamicsMemory().evaluate_bonus_candidates([{
            "score_gain": 10, "collection_probability": 0.9,
            "extra_steps": 1, "completion_probability_before": 0.8,
            "completion_probability_after": 0.8,
            "action_signature": "legal-action", "evidence": "visual_guess",
        }])
        self.assertEqual(result[0]["status"], "rejected_insufficient_evidence")

    def test_zero_or_negative_net_gain_is_rejected(self):
        memory = GameDynamicsMemory(step_cost_per_step=10.0)
        result = memory.evaluate_bonus_candidates([{
            "score_gain": 5, "collection_probability": 0.5,
            "extra_steps": 1, "completion_probability_before": 0.8,
            "completion_probability_after": 0.8,
            "action_signature": "legal-action", "evidence": "environment_metadata",
        }])
        self.assertEqual(result[0]["status"], "rejected_no_measurable_net_gain")


if __name__ == "__main__":
    unittest.main()
