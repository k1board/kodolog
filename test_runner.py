"""Тесты раннера: изоляция через subprocess, таймауты, парсинг результатов."""

import time
import unittest
from pathlib import Path

from kodolog.runner import run_tests

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
TEST_FILE = EXAMPLES / "test_submissions.py"


class TestRunner(unittest.TestCase):
    def test_full_run_counts(self):
        report = run_tests(TEST_FILE)
        self.assertEqual(report.total, 5)
        self.assertEqual(report.passed, 4)
        self.assertEqual(report.failed, 1)
        self.assertEqual(report.errors, 0)

    def test_failed_test_has_detail(self):
        report = run_tests(TEST_FILE)
        failed = [r for r in report.results if r.status == "fail"]
        self.assertEqual(len(failed), 1)
        self.assertIn("fizzbuzz", failed[0].name)
        self.assertTrue(failed[0].detail)  # последняя строка traceback

    def test_pass_rate(self):
        report = run_tests(TEST_FILE)
        self.assertEqual(report.pass_rate, 0.8)

    def test_hanging_tests_are_killed_by_timeout(self):
        source = (
            "import time, unittest\n"
            "class TestHang(unittest.TestCase):\n"
            "    def test_sleep(self):\n"
            "        time.sleep(10)\n"
        )
        tmp = Path(__file__).parent / "_tmp_hang_test.py"
        try:
            tmp.write_text(source, encoding="utf-8")
            report = run_tests(tmp, timeout=1)
            self.assertEqual(report.errors, 1)
            self.assertEqual(report.results[0].name, "<timeout>")
            self.assertIn("не завершились", report.results[0].detail or "")
        finally:
            tmp.unlink(missing_ok=True)

    def test_broken_test_file_reports_import_error(self):
        tmp = Path(__file__).parent / "_tmp_broken_test.py"
        try:
            tmp.write_text("this is not python at all", encoding="utf-8")
            report = run_tests(tmp)
            self.assertEqual(report.errors, 1)
            self.assertEqual(report.results[0].status, "error")
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
