"""Тесты к примерам работ: часть зелёная, часть ловит баги.

Файл лежит рядом с submissions/, чтобы импорты работали из cwd
подпроцесса. Запускается командой:
    python -m kodolog test examples/test_submissions.py
"""

import sys
import unittest
from pathlib import Path

# Работы лежат в соседнем каталоге submissions/ — добавляем его в путь,
# чтобы тесты запускались из любого места.
sys.path.insert(0, str(Path(__file__).resolve().parent / "submissions"))

from bad_solve import list as list_shadow
from buggy_solve import fizzbuzz
from good_solve import count_words, solve


class TestGoodSolve(unittest.TestCase):
    def test_positive_sum(self):
        self.assertEqual(solve([1, -2, 3, 0]), 4)

    def test_empty(self):
        self.assertEqual(solve([]), 0)

    def test_word_counts(self):
        self.assertEqual(count_words("а б а"), {"а": 2, "б": 1})


class TestBuggySolve(unittest.TestCase):
    def test_fizzbuzz_includes_n(self):
        # Упадёт: в решении range(1, n) вместо range(1, n + 1).
        result = fizzbuzz(15)
        self.assertEqual(len(result), 15)
        self.assertEqual(result[-1], "FizzBuzz")


class TestBadSolve(unittest.TestCase):
    def test_shadow_behaves_as_equality_with_none(self):
        # Само по себе работает, но так делать нельзя — см. анализатор.
        self.assertFalse(list_shadow([1, 2]))


if __name__ == "__main__":
    unittest.main()
