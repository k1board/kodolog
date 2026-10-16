"""Ревьюер: собирает анализ + тесты + код и просит LLM оценить работу.

Ключевая идея: LLM не заменяет детерминированные проверки, а дополняет
их. Сначала kodolog сам находит голые except и падающие тесты, потом
модель получает уже «разжёванный» контекст и пишет человеческое
резюме с подсказками. Ответ модели строго валидируется схемой Review.
"""

from __future__ import annotations

import json
from pathlib import Path

from .analyzer import analyze_file
from .llm import LLMClient, get_client
from .models import Review, StaticReport, TestReport
from .runner import run_tests

SYSTEM_PROMPT = (
    "Ты — внимательный и доброжелательный преподаватель программирования. "
    "Ты проверяешь учебные работы студентов первого курса по Python. "
    "Отвечай ТОЛЬКО валидным JSON без markdown-разметки по схеме: "
    '{"overall": str, "hints": [{"area": str, "text": str, "severity": '
    '"info|warning|error"}], "grade": int 0..10, "model": str}. '
    "Оценивай строго, но по-доброму: укажи, что уже хорошо, и что чинить первым."
)


class ReviewParseError(ValueError):
    """LLM вернула ответ, который не удалось разобрать как Review."""


def build_prompt(code: str, static: StaticReport, tests: TestReport) -> str:
    """Собирает промпт с кодом и машинночитаемым блоком данных."""
    static_json = json.dumps(static.model_dump(mode="json"), ensure_ascii=False)
    tests_json = json.dumps(tests.model_dump(mode="json"), ensure_ascii=False)
    return (
        "Оцени учебную работу по Python.\n\n"
        f"### КОД\n```python\n{code}\n```\n\n"
        "### ДАННЫЕ АНАЛИЗА (машинночитаемый блок)\n"
        f"static: {static_json}\n"
        f"tests: {tests_json}\n\n"
        "Напиши общий комментарий, 2-4 конкретные подсказки и поставь оценку от 0 до 10. "
        "Не решай задачу за студента — подсказывай."
    )


def parse_review(raw: str) -> Review:
    """Достаёт JSON из ответа LLM и валидирует его схемой Review.

    Модели любят оборачивать JSON в ```-блоки и добавлять лишний текст —
    поэтому ищем первую '{' и последнюю '}' перед разбором.
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ReviewParseError(f"в ответе LLM нет JSON: {raw[:120]!r}")
    try:
        payload = json.loads(text[start:end + 1])
    except ValueError as exc:
        raise ReviewParseError(f"некорректный JSON от LLM: {exc}") from exc
    return Review.model_validate(payload)


def review_file(path: str | Path, client: LLMClient | None = None,
                test_path: str | Path | None = None) -> Review:
    """Полный цикл проверки одного файла: анализ, тесты, ревью LLM.

    :param path: файл с работой студента.
    :param client: LLM-клиент (по умолчанию берётся get_client()).
    :param test_path: файл тестов; если не указан, тесты считаются
        отсутствующими (total == 0).
    """
    file_path = Path(path)
    code = file_path.read_text(encoding="utf-8")

    static = analyze_file(file_path)
    tests = run_tests(test_path) if test_path else TestReport(path="<no tests>")

    client = client or get_client()
    raw = client.complete(SYSTEM_PROMPT, build_prompt(code, static, tests))
    review = parse_review(raw)
    if review.model == "mock":
        review.model = "mock (офлайн-режим)"
    return review
