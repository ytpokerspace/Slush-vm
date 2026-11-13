import unittest

from arc3.arc_agi_runner import candidate_click_points, runner_exit_code
from arc3.visual_policy import score_navigation_candidates


class RunnerFailureTests(unittest.TestCase):
    def test_missing_step_observation_is_failure(self):
        self.assertEqual(runner_exit_code(1, "environment_returned_no_observation"), 1)

    def test_completed_nonwinning_run_is_successful_execution(self):
        self.assertEqual(runner_exit_code(3, "action_limit"), 0)

    def test_scan_points_cover_the_full_playfield_with_small_budget(self):
        points = candidate_click_points({}, strategy="scan", max_points=16)
        xs = {point["x"] for point in points}
        ys = {point["y"] for point in points}
        self.assertEqual(len(points), 16)
        self.assertEqual((min(xs), max(xs)), (4, 60))
        self.assertEqual((min(ys), max(ys)), (4, 60))
        self.assertGreaterEqual(len(xs), 4)
        self.assertGreaterEqual(len(ys), 4)

    def test_scan_respects_requested_cap(self):
        points = candidate_click_points({}, strategy="scan", max_points=7)
        self.assertEqual(len(points), 7)

    def test_zero_step_run_is_failure(self):
        self.assertEqual(runner_exit_code(0, "no_legal_actions"), 1)

    def test_foreground_clicks_exclude_dominant_background_colors(self):
        frame = [
            [5, 5, 5, 5],
            [5, 9, 9, 9],
            [5, 4, 4, 4],
            [5, 8, 2, 12],
        ]
        points = candidate_click_points({"frame": frame}, max_points=16)
        self.assertEqual(
            points,
            [{"x": 1, "y": 3}, {"x": 2, "y": 3}, {"x": 3, "y": 3}],
        )

    def test_navigation_target_is_included_even_when_it_is_background(self):
        frame = [[5] * 4 for _ in range(4)]
        navigation = {"action": "ACTION1", "target_center": [2, 2]}
        points = candidate_click_points(
            {"frame": frame}, max_points=4, navigation=navigation
        )
        self.assertIn({"x": 2, "y": 2}, points)

    def test_navigation_hint_scores_legal_click_at_target(self):
        records = [
            {"name": "ACTION6", "data": {"x": 1, "y": 1}},
            {"name": "ACTION6", "data": {"x": 8, "y": 9}},
        ]
        navigation = {"action": "ACTION1", "target_center": [8, 9]}
        scored = score_navigation_candidates(records, navigation)
        self.assertEqual(scored[0]["score"], 0.0)
        self.assertEqual(scored[1]["score"], 100.0)


if __name__ == "__main__":
    unittest.main()
