import json
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from arc3.benchmark import run_episode, summarize_policy_comparison


class Arc3BenchmarkComparisonTests(unittest.TestCase):
    def test_paired_summary_compares_identical_game_seed(self):
        rows = [
            {"game_id": "ls20", "seed": 0, "policy": "legacy",
             "steps": 20, "won": False, "levels_completed": 1},
            {"game_id": "ls20", "seed": 0, "policy": "glyph",
             "steps": 15, "won": True, "levels_completed": 2},
        ]
        result = summarize_policy_comparison(rows)
        self.assertEqual(result["paired_summary"]["pairs_valid"], 1)
        self.assertEqual(result["paired_summary"]["glyph_wins_not_legacy"], 1)
        self.assertEqual(result["paired_summary"]["mean_glyph_minus_legacy_steps"], -5)

    def test_invalid_pair_is_not_used_for_step_delta(self):
        rows = [
            {"game_id": "ls20", "seed": 1, "policy": "legacy",
             "steps": 20, "won": False, "levels_completed": 0},
            {"game_id": "ls20", "seed": 1, "policy": "glyph",
             "steps": 0, "won": False, "error": "timeout"},
        ]
        result = summarize_policy_comparison(rows)
        self.assertEqual(result["paired_summary"]["pairs_valid"], 0)
        self.assertIsNone(result["paired_summary"]["mean_glyph_minus_legacy_steps"])

    @patch("arc3.benchmark.subprocess.run")
    def test_run_episode_passes_selected_policy(self, run):
        run.return_value = SimpleNamespace(
            stdout=json.dumps({"game_id": "ls20", "seed": 0, "steps": 2, "won": False}),
            stderr="", returncode=0,
        )
        result = run_episode("ls20", 0, 12, "foreground", 8, False, 120, policy="glyph")
        command = run.call_args.args[0]
        self.assertIn("--policy", command)
        self.assertEqual(command[command.index("--policy") + 1], "glyph")
        self.assertEqual(result["policy"], "glyph")


if __name__ == "__main__":
    unittest.main()
