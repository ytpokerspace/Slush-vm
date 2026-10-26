import unittest

from arc3.frame_prediction import (
    compare_methods, predict_next_frame, rank_action_forecasts,
    score_frame_prediction, score_sequence,
)


class FramePredictionTests(unittest.TestCase):
    def test_persistence_copies_latest_frame(self):
        history = [[[0, 1], [2, 3]], [[0, 1], [2, 4]]]
        result = predict_next_frame(history)
        self.assertEqual(result["prediction"], history[-1])
        self.assertEqual(result["prediction_method"], "persistence")

    def test_motion_moves_unique_non_background_value(self):
        history = [
            [[0, 0, 0, 0], [0, 2, 0, 0]],
            [[0, 0, 0, 0], [0, 0, 2, 0]],
        ]
        result = predict_next_frame(history, method="motion")
        self.assertEqual(result["prediction"][1], [0, 0, 0, 2])

    def test_top_candidates_are_empirical_frequencies(self):
        history = [[[0]], [[1]], [[1]]]
        cell = predict_next_frame(history)["cells"][0][0]
        self.assertEqual(cell["predicted_value"], 1)
        self.assertAlmostEqual(cell["confidence"], 2 / 3)
        self.assertEqual(cell["top_candidates"][0]["value"], 1)

    def test_frame_scoring_counts_correct_cells(self):
        score = score_frame_prediction([[1, 2], [3, 4]], [[1, 9], [3, 4]])
        self.assertAlmostEqual(score["frame_accuracy"], 0.75)
        self.assertEqual(score["mismatch_count"], 1)
        self.assertTrue(score["shape_match"])

    def test_shape_mismatch_is_penalized(self):
        score = score_frame_prediction([[1, 2]], [[1]])
        self.assertAlmostEqual(score["frame_accuracy"], 0.5)
        self.assertFalse(score["shape_match"])

    def test_sequence_scoring_is_chronological(self):
        frames = [[[0, 0]], [[0, 0]], [[0, 1]]]
        result = score_sequence(frames)
        self.assertEqual(result["frames_scored"], 2)
        self.assertAlmostEqual(result["overall_cell_accuracy"], 0.75)

    def test_compare_methods_uses_same_sequence(self):
        result = compare_methods([[[0, 0]], [[0, 1]], [[0, 0]]])
        self.assertEqual(set(result["results"]), {"persistence", "motion", "change_aware"})
        self.assertTrue(all(v["frames_scored"] == 2 for v in result["results"].values()))

    def test_action_forecasts_rank_by_validation_accuracy(self):
        result = rank_action_forecasts([
            {"action": "left", "validation_accuracy": 0.5, "estimated_reward": 9},
            {"action": "right", "validation_accuracy": 0.8, "estimated_reward": 1},
        ])
        self.assertEqual(result[0]["action"], "right")

    def test_action_forecast_validation(self):
        with self.assertRaises(ValueError):
            rank_action_forecasts([{"action": "left", "validation_accuracy": 2}])

    def test_unknown_method_rejected(self):
        with self.assertRaises(ValueError):
            predict_next_frame([[[0]]], method="magic")

    def test_empty_history_rejected(self):
        with self.assertRaises(ValueError):
            predict_next_frame([])

    def test_top_k_must_be_positive(self):
        with self.assertRaises(ValueError):
            predict_next_frame([[[0]]], top_k=0)


if __name__ == "__main__":
    unittest.main()
