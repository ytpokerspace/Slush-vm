import unittest
from tools.benchmark_report import BenchmarkError, summarize

def r(i, o, c, ms):
    return {"input_tokens": i, "output_tokens": o, "correct": c, "latency_ms": ms}

class BenchmarkReportTests(unittest.TestCase):
    def test_three_way_summary(self):
        data = {"tasks": [{"task_id": "t1", "variants": {
            "conventional": r(10, 5, True, 20),
            "emoji_shorthand": r(8, 4, False, 18),
            "semantic_refs": r(4, 2, True, 10)}}]}
        out = summarize(data)
        self.assertEqual(out["variants"]["conventional"]["total_tokens"], 15)
        self.assertEqual(out["variants"]["semantic_refs"]["total_tokens"], 6)
        self.assertEqual(out["variants"]["semantic_refs"]["accuracy"], 1.0)
        self.assertAlmostEqual(out["variants"]["semantic_refs"]["token_reduction_vs_conventional"], 0.6)

    def test_missing_variant_rejected_by_loader(self):
        import json, tempfile
        from pathlib import Path
        from tools.benchmark_report import load_records
        data = {"tasks": [{"task_id": "t1", "variants": {"conventional": r(1,1,True,1)}}]}
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "input.json"
            p.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(BenchmarkError):
                load_records(p)

if __name__ == "__main__":
    unittest.main()
