import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "assemble_benchmark_results", ROOT / "tools/assemble_benchmark_results.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class AssembleBenchmarkResultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raw = Path(self.tmp.name) / "raw.jsonl"
        self.tasks = ROOT / "benchmarks/shush_20_tasks.json"

    def make_rows(self, count=60):
        dataset = json.loads(self.tasks.read_text(encoding="utf-8"))
        rows = []
        for task in dataset["tasks"]:
            for variant in MODULE.VARIANTS:
                rows.append({
                    "task_id": task["task_id"],
                    "variant": variant,
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "correct": True,
                    "latency_ms": 5.0,
                    "model_returned": "test-model",
                    "measurement_source": "provider_usage_metadata",
                    "system_prompt": "fixed",
                })
        return rows[:count]

    def write_rows(self, rows):
        self.raw.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )

    def test_assembles_all_variants_into_reporter_schema(self):
        self.write_rows(self.make_rows())
        result = MODULE.assemble(str(self.raw), str(self.tasks))
        self.assertEqual(result["task_count"], 20)
        self.assertEqual(result["status"], "measured_provider_results")
        self.assertEqual(set(result["tasks"][0]["variants"]), set(MODULE.VARIANTS))

    def test_rejects_incomplete_run(self):
        self.write_rows(self.make_rows(59))
        with self.assertRaisesRegex(ValueError, "exactly one record"):
            MODULE.assemble(str(self.raw), str(self.tasks))

    def test_rejects_duplicate_measurement(self):
        rows = self.make_rows()
        rows.append(dict(rows[0]))
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "duplicate measurement"):
            MODULE.assemble(str(self.raw), str(self.tasks))

    def test_rejects_estimated_token_counts(self):
        rows = self.make_rows()
        rows[0]["measurement_source"] = "estimated"
        self.write_rows(rows)
        with self.assertRaisesRegex(ValueError, "provider usage metadata"):
            MODULE.assemble(str(self.raw), str(self.tasks))

if __name__ == "__main__":
    unittest.main()
