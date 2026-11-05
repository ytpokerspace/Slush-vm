"""Tests for ARC-AGI-3 benchmark result accounting."""
import unittest

from arc3.benchmark import extract_result, summarize_results


class BenchmarkHarnessTests(unittest.TestCase):
    def test_extracts_runner_result_after_sdk_logs(self):
        output = 'SDK startup log\n{"game_id":"ls20","steps":3,"won":false}\n'
        self.assertEqual(
            extract_result(output),
            {"game_id": "ls20", "steps": 3, "won": False},
        )

    def test_counts_completed_losses_as_valid_runs(self):
        report = summarize_results([
            {"game_id": "ls20", "seed": 0, "steps": 4, "won": False,
             "levels_completed": 1, "win_levels": 3},
            {"game_id": "ls20", "seed": 1, "steps": 6, "won": True,
             "levels_completed": 3, "win_levels": 3},
        ])
        self.assertEqual(report["runs_requested"], 2)
        self.assertEqual(report["runs_executed"], 2)
        self.assertEqual(report["runs_failed"], 0)
        self.assertEqual(report["wins"], 1)
        self.assertEqual(report["win_rate"], 0.5)
        self.assertEqual(report["total_actions"], 10)
        self.assertAlmostEqual(report["level_completion_fraction"], 4 / 6)

    def test_separates_infrastructure_failures_from_executed_runs(self):
        report = summarize_results([
            {"game_id": "ls20", "seed": 0, "steps": 0, "won": False,
             "error": "runner timed out"},
            {"game_id": "ls20", "seed": 1, "steps": 2, "won": False},
        ])
        self.assertEqual(report["runs_requested"], 2)
        self.assertEqual(report["runs_executed"], 1)
        self.assertEqual(report["runs_failed"], 1)
        self.assertEqual(report["wins"], 0)
        self.assertEqual(report["win_rate"], 0.0)

    def test_empty_result_set_has_defined_zero_metrics(self):
        report = summarize_results([])
        self.assertEqual(report["runs_requested"], 0)
        self.assertEqual(report["runs_executed"], 0)
        self.assertEqual(report["win_rate"], 0.0)
        self.assertEqual(report["level_completion_fraction"], 0.0)


if __name__ == "__main__":
    unittest.main()
