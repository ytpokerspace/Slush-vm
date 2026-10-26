import unittest

from arc3.frame_benchmark import run_benchmark, synthetic_scenarios


class FrameBenchmarkTests(unittest.TestCase):
    def test_scenarios_are_deterministic_and_nonempty(self):
        first = synthetic_scenarios()
        second = synthetic_scenarios()
        self.assertEqual(first, second)
        self.assertEqual(set(first), {"stationary_object", "single_object_motion", "alternating_cell"})
        self.assertTrue(all(len(frames) >= 2 for frames in first.values()))

    def test_benchmark_reports_all_methods_for_each_scenario(self):
        result = run_benchmark()
        self.assertFalse(result["requires_network"])
        self.assertFalse(result["requires_credentials"])
        expected = {"persistence", "motion", "change_aware"}
        self.assertEqual(len(result["summary"]), 9)
        for scenario in result["scenarios"].values():
            self.assertEqual({r["method"] for r in scenario["comparison"]}, expected)

    def test_benchmark_disclaims_real_task_accuracy(self):
        self.assertIn("must not be reported as ARC-AGI-3", run_benchmark()["interpretation"])


if __name__ == "__main__":
    unittest.main()
