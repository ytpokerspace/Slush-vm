import unittest

from arc3.arc_agi_runner import runner_exit_code


class RunnerFailureTests(unittest.TestCase):
    def test_missing_step_observation_is_failure(self):
        self.assertEqual(runner_exit_code(1, "environment_returned_no_observation"), 1)

    def test_completed_nonwinning_run_is_successful_execution(self):
        self.assertEqual(runner_exit_code(3, "action_limit"), 0)

    def test_zero_step_run_is_failure(self):
        self.assertEqual(runner_exit_code(0, "no_legal_actions"), 1)


if __name__ == "__main__":
    unittest.main()
