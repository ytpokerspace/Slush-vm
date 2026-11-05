import unittest

from arc3.object_value_planner import arbitrate_objectives, score_objective


class ObjectValuePlannerTests(unittest.TestCase):
    def test_risky_goal_is_deferred_but_preserved(self):
        result = score_objective({
            "objective_id": "cross-hazard",
            "goal_value": 1.0,
            "success_probability": 0.1,
            "information_value": 0.0,
            "risk": 0.9,
            "action_cost": 0.7,
        })
        self.assertEqual(result["decision"], "defer")

    def test_safe_information_gathering_can_be_preparation(self):
        result = score_objective({
            "objective_id": "inspect",
            "goal_value": 0.1,
            "success_probability": 0.2,
            "information_value": 0.9,
            "risk": 0.1,
            "action_cost": 0.2,
        })
        self.assertEqual(result["decision"], "prepare")

    def test_global_controller_selects_viable_goal_and_keeps_deferred_goal(self):
        result = arbitrate_objectives([
            {"objective_id": "fragile", "goal_value": 1, "success_probability": 0.1,
             "information_value": 0, "risk": 0.9, "action_cost": 0.8},
            {"objective_id": "steady", "goal_value": 0.7, "success_probability": 0.8,
             "information_value": 0.1, "risk": 0.1, "action_cost": 0.1},
        ])
        self.assertEqual(result["active_objective"], "steady")
        self.assertIn("fragile", result["deferred_objectives"])

    def test_invalid_probability_is_rejected(self):
        with self.assertRaises(ValueError):
            score_objective({"success_probability": 1.1})

    def test_threshold_is_validated(self):
        with self.assertRaises(ValueError):
            score_objective({}, feasibility_threshold=1.1)


if __name__ == "__main__":
    unittest.main()
