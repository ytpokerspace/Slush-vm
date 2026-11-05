import unittest

from arc_emoji.solver import flood_fill_components, normalize_grid, predict, grid_to_lists


class GridValidationTests(unittest.TestCase):
    def test_rejects_empty_grid(self):
        with self.assertRaises(ValueError):
            normalize_grid([])

    def test_rejects_ragged_grid(self):
        with self.assertRaises(ValueError):
            normalize_grid([[1, 2], [3]])

    def test_rejects_boolean_cells(self):
        with self.assertRaises(ValueError):
            normalize_grid([[True]])


class FloodFillTests(unittest.TestCase):
    def test_four_connected_components_and_background(self):
        grid = [[0, 1, 0], [1, 0, 2], [0, 0, 2]]
        comps = flood_fill_components(grid)
        self.assertEqual([(c["color"], c["size"]) for c in comps], [(1, 1), (1, 1), (2, 2)])

    def test_eight_connectivity_merges_diagonal(self):
        comps = flood_fill_components([[1, 0], [0, 1]], connectivity=8)
        self.assertEqual(len(comps), 1)
        self.assertEqual(comps[0]["size"], 2)

    def test_invalid_connectivity(self):
        with self.assertRaises(ValueError):
            flood_fill_components([[1]], connectivity=6)


class PredictionTests(unittest.TestCase):
    def test_infers_horizontal_flip(self):
        train = [([[1, 2], [3, 4]], [[2, 1], [4, 3]])]
        result = predict(train, [[5, 6], [7, 8]])
        self.assertEqual(result.status, "predicted")
        self.assertEqual(result.transform, "horizontal_flip")
        self.assertEqual(grid_to_lists(result.grid), [[6, 5], [8, 7]])

    def test_no_match_is_explicit(self):
        result = predict([([[1, 2], [3, 4]], [[9]])], [[1, 2], [3, 4]])
        self.assertEqual(result.status, "no_prediction")
        self.assertIsNone(result.grid)

    def test_empty_training_is_explicit(self):
        result = predict([], [[1]])
        self.assertEqual(result.status, "no_prediction")
        self.assertIn("no training", result.reason)

    def test_deterministic_tie_break(self):
        train = [([[1, 1], [1, 1]], [[1, 1], [1, 1]])]
        self.assertEqual(predict(train, [[1, 1], [1, 1]]).transform, "identity")


if __name__ == "__main__":
    unittest.main()
