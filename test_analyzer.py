"""Тесты статического анализатора."""

import unittest
from pathlib import Path

from kodolog.analyzer import analyze_file, analyze_source
from kodolog.models import Severity

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SUBMISSIONS = EXAMPLES / "submissions"


class TestAnalyzer(unittest.TestCase):
    def test_clean_file_has_no_issues(self):
        report = analyze_file(SUBMISSIONS / "good_solve.py")
        self.assertEqual(report.issues, [])
        self.assertEqual(report.score, 100.0)
        self.assertEqual(report.functions, 2)

    def test_bad_file_finds_core_rules(self):
        report = analyze_file(SUBMISSIONS / "bad_solve.py")
        codes = {issue.code for issue in report.issues}
        # Каждое правило, которое должен поймать «плохой» пример.
        self.assertIn("W001", codes)  # нет докстрингов
        self.assertIn("W002", codes)  # голый except
        self.assertIn("W003", codes)  # изменяемый default
        self.assertIn("W005", codes)  # затенение builtins.list
        self.assertIn("W006", codes)  # == None
        self.assertIn("E001", codes)  # global
        self.assertIn("W007", codes)  # TODO
        self.assertLess(report.score, 100.0)

    def test_long_function_is_flagged(self):
        body = "\n".join(f"    x{i} = {i}" for i in range(45))
        source = f"def big():\n    '''Длинная функция.'''\n{body}\n    return x0\n"
        report = analyze_source(source)
        codes = {issue.code for issue in report.issues}
        self.assertIn("W004", codes)

    def test_issues_sorted_by_line(self):
        report = analyze_file(SUBMISSIONS / "bad_solve.py")
        lines = [issue.line for issue in report.issues]
        self.assertEqual(lines, sorted(lines))

    def test_error_rules_reduce_score_more_than_info(self):
        source = (
            "def f(data=[]):\n"       # W003 (error, -10) + W001 (warning, -5)
            "    try:\n"
            "        return data\n"
            "    except:\n"            # W002 (error, -10)
            "        return []\n"
            "def g():\n"
            "    '''Дока.'''\n"
            "    # FIXME: потом\n"     # W007 (info, -1)
            "    return g\n"
        )
        report = analyze_source(source)
        self.assertEqual(report.score, 74.0)  # 100 - 10 - 5 - 10 - 1
        self.assertEqual(report.count_by_severity()[Severity.ERROR.value], 2)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            analyze_file(SUBMISSIONS / "no_such_file.py")

    def test_non_python_file_rejected(self):
        with self.assertRaises(ValueError):
            analyze_file(EXAMPLES / "test_submissions.txt" if (EXAMPLES / "test_submissions.txt").exists()
                         else "/etc/hostname")


if __name__ == "__main__":
    unittest.main()
