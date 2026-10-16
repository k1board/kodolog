"""Пример «хорошей» работы: чистые функции, докстринги, типизация."""


def solve(numbers: list[int]) -> int:
    """Возвращает сумму положительных чисел списка.

    Отрицательные значения и нули игнорируются.
    """
    return sum(n for n in numbers if n > 0)


def count_words(text: str) -> dict[str, int]:
    """Считает частоты слов в тексте (регистр игнорируется)."""
    frequencies: dict[str, int] = {}
    for word in text.lower().split():
        frequencies[word] = frequencies.get(word, 0) + 1
    return frequencies
