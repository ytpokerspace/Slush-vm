import unittest

from arc3.physics_forecast import forecast_trajectory


class PhysicsForecastTests(unittest.TestCase):
    def setUp(self):
        self.track = [
            {"t": 0.0, "x": 0.0, "y": 0.0},
            {"t": 0.5, "x": 5.0, "y": 1.25},
            {"t": 1.0, "x": 10.0, "y": 5.0},
        ]

    def test_forecast_estimates_motion_and_returns_hypotheses(self):
        result = forecast_trajectory(self.track, horizon_seconds=0.5, step_seconds=0.25)
        self.assertEqual(result["schema"], "physics_trajectory_hypotheses_v1")
        self.assertAlmostEqual(result["estimated_state"]["vx_px_per_second"], 10.0)
        self.assertEqual(result["hypotheses"][0]["name"], "constant_velocity")
        self.assertEqual(len(result["hypotheses"][0]["states"]), 2)
        self.assertIn("rankings, not probabilities", result["limitations"][3])

    def test_ground_contact_adds_bounce_hypothesis(self):
        result = forecast_trajectory(self.track, horizon_seconds=0.5, step_seconds=0.25, gravity_px_s2=9.8, ground_y=20.0)
        names = [item["name"] for item in result["hypotheses"]]
        self.assertIn("gravity_with_ground_contact", names)

    def test_rejects_non_increasing_timestamps(self):
        with self.assertRaises(ValueError):
            forecast_trajectory([{"t": 1, "x": 0, "y": 0}, {"t": 1, "x": 1, "y": 1}])

    def test_rejects_invalid_horizon(self):
        with self.assertRaises(ValueError):
            forecast_trajectory(self.track, horizon_seconds=0)

    def test_requires_two_observations(self):
        with self.assertRaises(ValueError):
            forecast_trajectory([{"t": 0, "x": 1, "y": 1}])


if __name__ == "__main__":
    unittest.main()
