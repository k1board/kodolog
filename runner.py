"""Запуск тестов чужого кода в изолированном подпроцессе.

Главное правило: чужой код нельзя доверять запускать в своём процессе.
Решение ученика может зависнуть в бесконечном цикле, упасть с segfault
или положить сборщик мусора — поэтому тесты выполняются отдельным
интерпретатором с таймаутом, а результаты приходят обратно в JSON.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from .models import TestCaseResult, TestReport

# Скрипт, который исполняется внутри подпроцесса. Собирает результаты
# unittest в структуре и печатает их одной JSON-строкой с маркером,
# чтобы отделить их от возможного вывода самих тестов.
_COLLECTOR_CODE = r"""
import json
import sys
import unittest


class Collector(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.records = {}

    def startTest(self, test):
        super().startTest(test)
        self.records[test.id()] = {"status": "pass", "detail": None}

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records[test.id()] = {"status": "fail", "detail": self._tail(err)}

    def addError(self, test, err):
        super().addError(test, err)
        self.records[test.id()] = {"status": "error", "detail": self._tail(err)}

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records[test.id()] = {"status": "skip", "detail": str(reason)}

    @staticmethod
    def _tail(err):
        # Последняя строка traceback — обычно самое информативное.
        lines = [line for line in str(err[1]).splitlines() if line.strip()]
        return lines[-1] if lines else ""


module_path = sys.argv[1]
import importlib.util
from pathlib import Path

# Имя модуля — как у файла, чтобы идентификаторы тестов были читаемыми.
module_name = Path(module_path).stem
spec = importlib.util.spec_from_file_location(module_name, module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

suite = unittest.TestLoader().loadTestsFromModule(module)
collector = Collector()
suite.run(collector)

print("KODOLOG_RESULT:" + json.dumps(collector.records, ensure_ascii=False))
"""


def run_tests(test_path: str | Path, timeout: int = 30) -> TestReport:
    """Прогоняет unittest-тесты из файла в отдельном процессе.

    :param test_path: путь к файлу с тестами (например, examples/test_submissions.py).
    :param timeout: сколько секунд ждать зависший процесс.
    """
    file_path = Path(test_path)
    if not file_path.exists():
        raise FileNotFoundError(f"файл тестов не найден: {file_path}")

    try:
        proc = subprocess.run(
            [sys.executable, "-c", _COLLECTOR_CODE, str(file_path.resolve())],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(file_path.parent),
        )
    except subprocess.TimeoutExpired:
        return TestReport(
            path=str(file_path),
            results=[TestCaseResult(name="<timeout>", status="error",
                                    detail=f"тесты не завершились за {timeout} с (вероятно, бесконечный цикл)")],
            total=1, errors=1,
        )

    records = _extract_records(proc.stdout)
    if records is None:
        # Тесты упали до вывода результатов: синтаксическая ошибка и т.п.
        detail = (proc.stderr or proc.stdout or "неизвестная ошибка").strip().splitlines()
        return TestReport(
            path=str(file_path),
            results=[TestCaseResult(name="<import>", status="error",
                                    detail=detail[-1] if detail else "ошибка импорта тестов")],
            total=1, errors=1,
        )

    results = [
        TestCaseResult(name=name, status=info["status"], detail=info.get("detail"))
        for name, info in records.items()
    ]
    return TestReport(
        path=str(file_path),
        total=len(results),
        passed=sum(1 for r in results if r.status == "pass"),
        failed=sum(1 for r in results if r.status == "fail"),
        errors=sum(1 for r in results if r.status == "error"),
        skipped=sum(1 for r in results if r.status == "skip"),
        results=results,
    )


def _extract_records(stdout: str) -> dict | None:
    """Достаёт JSON-строку с маркером KODOLOG_RESULT из вывода подпроцесса."""
    for line in reversed(stdout.splitlines()):
        if line.startswith("KODOLOG_RESULT:"):
            payload = line[len("KODOLOG_RESULT:"):]
            return json.loads(payload)
    return None
