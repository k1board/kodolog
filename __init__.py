"""Kodolog — ассистент для проверки учебного Python-кода.

Мини-проект под заявку в учебно-научную лабораторию AIST (Университет ИТМО).
Объединяет четыре инструмента в одном пайплайне:

  * статический анализ (AST) — kodolog.analyzer
  * изолированный прогон тестов — kodolog.runner
  * LLM-ревью с Pydantic-валидацией ответа — kodolog.reviewer + kodolog.llm
  * синтетические тесты и датасеты — kodolog.synth, kodolog.dataset
"""

__version__ = "0.1.0"

from .analyzer import analyze_file, analyze_source
from .dataset import build_dataset, to_jsonl
from .llm import get_client
from .metrics import compute_metrics, to_markdown
from .models import Review, StaticReport, TestReport
from .reviewer import review_file
from .runner import run_tests
from .synth import generate_tests

__all__ = [
    "analyze_file",
    "analyze_source",
    "build_dataset",
    "compute_metrics",
    "generate_tests",
    "get_client",
    "review_file",
    "run_tests",
    "to_jsonl",
    "to_markdown",
    "Review",
    "StaticReport",
    "TestReport",
    "__version__",
]
