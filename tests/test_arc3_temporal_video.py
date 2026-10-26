import unittest

from arc3.temporal_video import (
    analyze_clip, backward_change_analysis, evaluate_midpoint, transition_summary,
)


class TemporalVideoTests(unittest.TestCase):
    def setUp(self):
        self.frames = [
            [[0, 0, 0, 0], [0, 2, 0, 0]],
            [[0, 0, 0, 0], [0, 0, 2, 0]],
            [[0, 0, 0, 0], [0, 0, 0, 2]],
            [[0, 0, 0, 0], [0, 0, 0, 2]],
        ]
        self.timestamps = [0.0, 1.0, 2.5, 5.0]

    def test_midpoint_uses_only_earlier_frames(self):
        result = evaluate_midpoint(self.frames, self.timestamps, method="motion")
        self.assertEqual(result["task"], "midpoint_forecast")
        self.assertEqual(result["target_timestamp_seconds"], 2.5)
        self.assertEqual(result["context_timestamps_seconds"], [0.0, 1.0])
        self.assertEqual(result["actual_frame"], self.frames[2])
        self.assertIn("frame_accuracy", result["score"])

    def test_backward_analysis_orders_transitions_latest_first(self):
        result = backward_change_analysis(self.frames, self.timestamps)
        self.assertEqual(result["direction"], "latest_to_earliest")
        self.assertEqual(result["transitions"][0]["from_timestamp_seconds"], 5.0)
        self.assertEqual(result["transitions"][0]["to_timestamp_seconds"], 2.5)

    def test_transition_summary_reports_differences_without_cause(self):
        result = transition_summary([[0, 1]], [[0, 0]])
        self.assertEqual(result["changed_cells"], 1)
        self.assertEqual(result["changes"][0], {"x": 1, "y": 0, "before": 1, "after": 0})
        self.assertIn("cause", result["interpretation"])

    def test_combined_analysis_is_explicitly_baseline(self):
        result = analyze_clip(self.frames, self.timestamps, method="persistence")
        self.assertEqual(result["status"], "baseline_complete")
        self.assertEqual(result["frame_count"], 4)
        self.assertIn("backward_analysis", result)

    def test_bad_timestamps_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_midpoint(self.frames, [0, 1, 1, 5])

    def test_missing_prior_frame_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_midpoint([self.frames[0], self.frames[1]], [2.5, 5.0])


if __name__ == "__main__":
    unittest.main()
