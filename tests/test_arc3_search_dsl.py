import unittest

from arc3.search_dsl import SearchConfig, compile_dsl, search


class SearchDSLTests(unittest.TestCase):
    def test_topk_directive_compiles(self):
        config = compile_dsl("MCTS 12\nTOPK 3\nDEPTH 3\n")
        self.assertEqual(config.top_k, 3)
        self.assertEqual(config.iterations, 12)

    def test_mcts_returns_action_from_top_three_candidates(self):
        graph = {
            0: [1, 2, 3, 4],
            1: [],
            2: [],
            3: [],
            4: [],
        }
        values = {0: 0.0, 1: 3.0, 2: 4.0, 3: 5.0, 4: -10.0}
        cfg = SearchConfig(
            iterations=24, depth=3, beam_width=3, branching_limit=4,
            max_nodes=80, max_children=4, top_k=3, seed=11,
        )
        result = search(
            0,
            lambda state: graph[state],
            lambda state, action: action,
            lambda state: values[state],
            lambda state: False,
            lambda state: state,
            cfg,
        )
        self.assertIn(result.action, {1, 2, 3})
        self.assertGreater(result.iterations, 0)
        self.assertLessEqual(result.nodes_created, cfg.max_nodes)

    def test_invalid_topk_is_rejected(self):
        with self.assertRaises(ValueError):
            SearchConfig(top_k=0)


if __name__ == "__main__":
    unittest.main()
