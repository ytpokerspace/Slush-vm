import unittest

from arc3.motion_planner import forecast_motion


class MotionPlannerTests(unittest.TestCase):
    def test_motion_generates_normalized_what_if_scenarios(self):
        previous = {"grid": [[0, 0, 0, 0], [0, 1, 0, 0]]}
        current = {"grid": [[0, 0, 0, 0], [0, 0, 1, 0]]}
        result = forecast_motion(previous, current, horizon=2)
        self.assertEqual(result["status"], "forecast_available")
        self.assertEqual(result["best_scenario"], "continue")
        self.assertEqual(result["best_probability"], 0.60)
        self.assertAlmostEqual(sum(s["probability"] for s in result["scenarios"]), 1.0)
        continued = next(s for s in result["scenarios"] if s["name"] == "continue")
        self.assertEqual(continued["predictions"][0]["predicted_center"], [3.0, 1.0])
        self.assertFalse(result["probabilities_are_calibrated"])

    def test_stationary_scene_reports_no_motion(self):
        observation = {"grid": [[0, 1], [0, 0]]}
        result = forecast_motion(observation, observation)
        self.assertEqual(result["status"], "no_motion_detected")
        self.assertIsNone(result["best_scenario"])

    def test_missing_observation_reports_insufficient_data(self):
        result = forecast_motion(None, {"grid": [[0, 1]]})
        self.assertEqual(result["status"], "insufficient_observations")

    def test_horizon_is_bounded(self):
        with self.assertRaises(ValueError):
            forecast_motion({"grid": [[1]]}, {"grid": [[1]]}, horizon=99)


if __name__ == "__main__":
    unittest.main()
