"""Генерация синтетических тестов к функциям студенческого кода.

Задача модуля — не написать за студента полноценные тесты, а быстро
собрать «нулевое покрытие»: смок-тесты, которые проверяют, что функции
вообще импортируются и вызываются. Настоящие тесты по докстрингам и
логике генерирует LLM-режим; шаблонный режим работает офлайн.

Оба режима возвращают строго одну и ту же модель GeneratedTest —
потребителю всё равно, откуда взялся тест.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from .analyzer import analyze_file
from .llm import LLMClient, get_client
from .models import FunctionInfo, GeneratedTest

_SYNTH_SYSTEM_PROMPT = (
    "Ты генерируешь смок-тесты на unittest для учебных функций Python. "
    "Тебе дают код функции — верни JSON-массив объектов "
    '[{"function": str, "description": str, "code": str}], где code — '
    "готовый файл теста с импортом тестируемой функции из модуля "
    "{module_name}. Не выдумывай поведение, которого нет в коде. "
    "Отвечай только JSON, без markdown."
)


def extract_functions(code: str) -> list[FunctionInfo]:
    """Достаёт функции верхнего уровня вместе с аргументами и докстрингами."""
    tree = ast.parse(code)
    functions = []
    for node in tree.body:  # только верхний уровень: методы классов не трогаем
        if isinstance(node, ast.FunctionDef):
            functions.append(FunctionInfo(
                name=node.name,
                args=[arg.arg for arg in node.args.args],
                docstring=ast.get_docstring(node),
                line=node.lineno,
            ))
    return functions


def _smoke_test(module_name: str, function: FunctionInfo) -> GeneratedTest:
    """Шаблонный смок-тест: импорт + вызываемость (офлайн, без LLM)."""
    code = (
        f'"""Синтетический смок-тест для {function.name}() — сгенерирован Kodolog."""\n\n'
        f"import unittest\n\n"
        f"from {module_name} import {function.name}\n\n"
        f"\n"
        f"class Test{function.name.capitalize()}Smoke(unittest.TestCase):\n"
        f"    def test_importable_and_callable(self):\n"
        f"        # Проверяем, что функция существует и её можно вызвать.\n"
        f"        self.assertTrue(callable({function.name}))\n"
        f"\n"
        f"\n"
        f"if __name__ == '__main__':\n"
        f"    unittest.main()\n"
    )
    description = (
        f"смок-тест: {module_name}.{function.name} импортируется и вызываем"
        + (f"; сигнатура: ({', '.join(function.args)})" if function.args else "")
    )
    return GeneratedTest(function=function.name, description=description,
                         code=code, origin="template")


def generate_tests(path: str | Path, client: LLMClient | None = None,
                   max_functions: int = 5) -> list[GeneratedTest]:
    """Генерирует тесты ко всем функциям файла.

    В режиме Mock (офлайн) каждый функции ставится в соответствие
    шаблонный смок-тест. В режиме API модель получает код функций
    и возвращает более осмысленные тесты — но всё равно валидируемые.
    """
    file_path = Path(path)
    module_name = file_path.stem
    code = file_path.read_text(encoding="utf-8")
    functions = extract_functions(code)[:max_functions]

    client = client or get_client()
    if type(client).__name__ == "MockLLMClient":
        return [_smoke_test(module_name, function) for function in functions]

    prompt = (
        f"Модуль называется {module_name}. Вот его код:\n\n```python\n{code}\n```\n\n"
        f"Сгенерируй тесты к функциям: {', '.join(f.name for f in functions)}."
    )
    raw = client.complete(_SYNTH_SYSTEM_PROMPT.format(module_name=module_name), prompt)

    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end <= start:
        # Модель ответала неожиданно — откатываемся к шаблонам.
        return [_smoke_test(module_name, function) for function in functions]
    try:
        payload = json.loads(raw[start:end + 1])
        tests = []
        for item in payload:
            tests.append(GeneratedTest(
                function=item.get("function", "?"),
                description=item.get("description", "сгенерирован LLM"),
                code=item["code"],
                origin="llm",
            ))
        return tests
    except (ValueError, KeyError):
        return [_smoke_test(module_name, function) for function in functions]


def save_tests(tests: list[GeneratedTest], out_dir: str | Path,
               prefix: str = "synth") -> list[Path]:
    """Сохраняет тесты файлами и возвращает список путей."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for index, test in enumerate(tests, start=1):
        target = directory / f"{prefix}_{index}_test_{test.function}.py"
        target.write_text(test.code, encoding="utf-8")
        written.append(target)
    return written


def describe_coverage(path: str | Path) -> str:
    """Короткая человекочитаемая сводка: сколько функций и сколько из них с тестами."""
    report = analyze_file(path)
    functions = extract_functions(Path(path).read_text(encoding="utf-8"))
    documented = sum(1 for function in functions if function.docstring)
    return (
        f"{len(functions)} функций, из них с докстрингом: {documented}; "
        f"статический анализ: {len(report.issues)} замечаний, score {report.score}"
    )
