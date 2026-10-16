"""Тесты метрик, датасета и генератора синтетических тестов."""

import tempfile
import unittest
from pathlib import Path

from kodolog.analyzer import analyze_file
from kodolog.dataset import build_dataset, issue_cooccurrence, load_jsonl, to_jsonl
from kodolog.llm import MockLLMClient
from kodolog.metrics import compute_metrics, overall_pass_rate, to_markdown
from kodolog.models import TestReport
from kodolog.synth import extract_functions, generate_tests, save_tests

ROOT = Path(__file__).resolve().parent.parent
SUBMISSIONS = ROOT / "examples" / "submissions"
TEST_FILE = ROOT / "examples" / "test_submissions.py"


class TestMetrics(unittest.TestCase):
    def _reports(self):
        return [analyze_file(path) for path in sorted(SUBMISSIONS.glob("*.py"))]

    def test_summary_over_three_files(self):
        summary = compute_metrics(self._reports())
        self.assertEqual(summary.files, 3)
        self.assertGreater(summary.total_issues, 0)
        self.assertIn("W001", summary.top_issue_codes)

    def test_overall_pass_rate(self):
        reports = [TestReport(path="a", total=5, passed=4), TestReport(path="b", total=5, passed=5)]
        self.assertEqual(overall_pass_rate(reports), 0.9)

    def test_overall_pass_rate_empty(self):
        self.assertIsNone(overall_pass_rate([]))

    def test_markdown_render(self):
        summary = compute_metrics(self._reports())
        text = to_markdown(summary)
        self.assertIn("Файлов: **3**", text)


class TestDataset(unittest.TestCase):
    def test_build_dataset(self):
        records = build_dataset(SUBMISSIONS)
        self.assertEqual(len(records), 3)
        names = {record.file for record in records}
        self.assertEqual(names, {"good_solve.py", "bad_solve.py", "buggy_solve.py"})

    def test_jsonl_roundtrip(self):
        records = build_dataset(SUBMISSIONS)
        with tempfile.TemporaryDirectory() as tmp:
            out = to_jsonl(records, Path(tmp) / "ds.jsonl")
            loaded = load_jsonl(out)
            self.assertEqual(loaded, records)

    def test_cooccurrence(self):
        records = build_dataset(SUBMISSIONS)
        matrix = issue_cooccurrence(records)
        # В bad_solve.py точно встречаются вместе W001 и W002.
        self.assertGreaterEqual(matrix.get("W001", {}).get("W002", 0), 1)


class TestSynth(unittest.TestCase):
    def test_extract_functions(self):
        code = (SUBMISSIONS / "good_solve.py").read_text(encoding="utf-8")
        functions = extract_functions(code)
        self.assertEqual([f.name for f in functions], ["solve", "count_words"])
        self.assertTrue(all(f.docstring for f in functions))

    def test_generate_offline_smoke_tests(self):
        tests = generate_tests(SUBMISSIONS / "good_solve.py", client=MockLLMClient())
        self.assertEqual(len(tests), 2)
        self.assertEqual({t.origin for t in tests}, {"template"})
        for test in tests:
            self.assertIn("import unittest", test.code)
            self.assertIn(f"from good_solve import {test.function}", test.code)

    def test_save_tests_writes_files(self):
        tests = generate_tests(SUBMISSIONS / "good_solve.py", client=MockLLMClient())
        with tempfile.TemporaryDirectory() as tmp:
            written = save_tests(tests, tmp)
            self.assertEqual(len(written), 2)
            for path in written:
                self.assertTrue(path.exists())
                self.assertTrue(path.read_text(encoding="utf-8").startswith('"""'))


if __name__ == "__main__":
    unittest.main()
