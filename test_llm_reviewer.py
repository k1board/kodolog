"""Тесты LLM-слоя: заглушка, парсинг ответов, полное ревью в офлайн-режиме."""

import unittest
from pathlib import Path

from kodolog.llm import MockLLMClient, get_client
from kodolog.models import Review
from kodolog.reviewer import ReviewParseError, build_prompt, parse_review, review_file

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SUBMISSIONS = EXAMPLES / "submissions"


class TestMockClient(unittest.TestCase):
    def test_get_client_without_key_is_mock(self):
        import os
        saved = (os.environ.pop("KOODOLOG_API_KEY", None), os.environ.pop("OPENAI_API_KEY", None))
        try:
            self.assertEqual(type(get_client()).__name__, "MockLLMClient")
        finally:
            for key, value in zip(("KOODOLOG_API_KEY", "OPENAI_API_KEY"), saved):
                if value:
                    os.environ[key] = value

    def test_mock_returns_valid_review_json(self):
        client = MockLLMClient()
        static = '{"score": 60.0, "issues": [{"code": "W002", "title": "голый except", "severity": "error", "line": 5, "hint": "ловите конкретное"}]}'
        tests = '{"total": 5, "passed": 3}'
        prompt = f"### ДАННЫЕ АНАЛИЗА\nstatic: {static}\ntests: {tests}"
        review = parse_review(client.complete("system", prompt))
        self.assertEqual(review.grade, 8)  # 10 - 2*1 error
        self.assertTrue(review.hints)
        self.assertEqual(review.model, "mock")


class TestParseReview(unittest.TestCase):
    def test_plain_json(self):
        payload = '{"overall": "ок", "hints": [], "grade": 7, "model": "m"}'
        review = parse_review(payload)
        self.assertEqual(review.grade, 7)

    def test_markdown_fenced_json_with_junk(self):
        payload = 'Вот моё ревью:\n```json\n{"overall": "ок", "hints": [], "grade": 5, "model": "m"}\n```\nУдачи!'
        review = parse_review(payload)
        self.assertEqual(review.grade, 5)

    def test_garbage_raises(self):
        with self.assertRaises(ReviewParseError):
            parse_review("мне кажется, работа хорошая, но без структуры")

    def test_invalid_schema_raises(self):
        # grade вне диапазона 0..10 должен быть отклонён Pydantic.
        payload = '{"overall": "ок", "hints": [], "grade": 42, "model": "m"}'
        with self.assertRaises(Exception):
            parse_review(payload)


class TestFullReview(unittest.TestCase):
    def test_review_bad_file_offline(self):
        review = review_file(SUBMISSIONS / "bad_solve.py",
                             client=MockLLMClient(),
                             test_path=EXAMPLES / "test_submissions.py")
        self.assertIsInstance(review, Review)
        self.assertIn("mock", review.model)
        self.assertLessEqual(review.grade, 6)
        self.assertTrue(review.hints)  # по плохой работе точно есть что сказать

    def test_review_good_file_offline(self):
        review = review_file(SUBMISSIONS / "good_solve.py", client=MockLLMClient())
        self.assertEqual(review.grade, 10)
        self.assertEqual(review.hints, [])

    def test_prompt_contains_machine_block(self):
        from kodolog.analyzer import analyze_file
        from kodolog.runner import run_tests
        code = (SUBMISSIONS / "good_solve.py").read_text(encoding="utf-8")
        static = analyze_file(SUBMISSIONS / "good_solve.py")
        tests = run_tests(EXAMPLES / "test_submissions.py")
        prompt = build_prompt(code, static, tests)
        self.assertIn("static: ", prompt)
        self.assertIn("tests: ", prompt)
        self.assertIn("```python", prompt)


if __name__ == "__main__":
    unittest.main()
