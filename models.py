"""Pydantic-модели Kodolog: единые схемы для всех модулей.

Каждый модуль (анализатор, раннер тестов, ревьюер, генератор) работает
не с «сырыми» словарями, а со строгими моделями — так ошибка в данных
ловится на границе, а не в глубине пайплайна.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Уровень серьёзности замечания статического анализатора."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class Issue(BaseModel):
    """Одно замечание статического анализа (AST)."""

    code: str = Field(description="Код правила, например W002")
    title: str = Field(description="Короткое название правила")
    severity: Severity
    line: int = Field(ge=1, description="Номер строки, где найдено замечание")
    hint: str = Field(description="Подсказка, как исправить")


class StaticReport(BaseModel):
    """Отчёт статического анализатора по одному файлу."""

    path: str
    lines: int = 0
    functions: int = 0
    issues: list[Issue] = []
    score: float = Field(default=0.0, ge=0, le=100, description="0..100")

    def count_by_severity(self) -> dict[str, int]:
        """Сколько замечаний каждого уровня серьёзности."""
        counts = {level.value: 0 for level in Severity}
        for issue in self.issues:
            counts[issue.severity.value] += 1
        return counts


class TestCaseResult(BaseModel):
    """Результат одного теста."""

    name: str = Field(description="Идентификатор теста, например module.Class.test_x")
    status: str = Field(description="pass | fail | error | skip")
    detail: Optional[str] = None


class TestReport(BaseModel):
    """Отчёт о прогоне тестов одного файла."""

    path: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    results: list[TestCaseResult] = []

    @property
    def pass_rate(self) -> Optional[float]:
        """Доля пройденных тестов; None, если тестов нет."""
        if self.total == 0:
            return None
        return round(self.passed / self.total, 4)


class Hint(BaseModel):
    """Одна подсказка ревьюера для автора кода."""

    area: str = Field(description="К чему относится подсказка")
    text: str = Field(description="Сама подсказка")
    severity: Severity = Severity.INFO


class Review(BaseModel):
    """Структурированное LLM-ревью работы.

    Модель отвечает за то, что ответ языковой модели всегда валиден:
    если LLM вернула мусор, валидация упадёт здесь, а не у пользователя.
    """

    overall: str = Field(description="Общий комментарий по работе")
    hints: list[Hint] = []
    grade: int = Field(ge=0, le=10, description="Оценка работы от 0 до 10")
    model: str = Field(description="Какая модель делала ревью")


class FunctionInfo(BaseModel):
    """Информация о функции, извлечённая из AST."""

    name: str
    args: list[str] = []
    docstring: Optional[str] = None
    line: int = Field(ge=1)


class GeneratedTest(BaseModel):
    """Синтетический тест, сгенерированный LLM или шаблоном."""

    function: str = Field(description="Какую функцию покрывает тест")
    description: str
    code: str = Field(description="Готовый к запуску код теста на unittest")
    origin: str = Field(default="template", description="template | llm")


class DatasetRecord(BaseModel):
    """Одна запись датасета «мини-экосистема работ».

    Превращает папку с учебными работами в структурированные данные:
    это тот же принцип, что и при сборе открытых данных о научной
    экосистеме — только на игрушечном масштабе.
    """

    file: str
    lines: int = 0
    functions: int = 0
    issues_total: int = 0
    issue_codes: list[str] = []
    score: float = 0.0


class MetricsSummary(BaseModel):
    """Сводные метрики по набору работ."""

    files: int = 0
    total_issues: int = 0
    avg_score: float = 0.0
    avg_lines: float = 0.0
    by_severity: dict[str, int] = {}
    top_issue_codes: dict[str, int] = {}
