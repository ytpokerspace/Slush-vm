import unittest

from arc3.arc_agi_runner import candidate_click_points, runner_exit_code


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


if __name__ == "__main__":
    unittest.main()
