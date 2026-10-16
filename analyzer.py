"""Статический анализ учебного Python-кода через модуль ast.

Анализатор не запускает чужой код и не ходит в сеть — он читает файл,
строит дерево разбора и ищет типичные ошибки первокурсника: голые
except, изменяемые аргументы по умолчанию, функции без докстрингов.
Правила намеренно простые: важна не полнота, а предсказуемость.
"""

from __future__ import annotations

import ast
import builtins
from pathlib import Path

from .models import Issue, Severity, StaticReport

# Штрафы за замечания: из 100 баллов вычитается по уровню серьёзности.
_PENALTY = {Severity.ERROR: 10.0, Severity.WARNING: 5.0, Severity.INFO: 1.0}

_MAX_FUNCTION_LINES = 40
_BUILTIN_NAMES = {name for name in dir(builtins) if not name.startswith("_")}


def _issue(code: str, title: str, severity: Severity, line: int, hint: str) -> Issue:
    return Issue(code=code, title=title, severity=severity, line=line, hint=hint)


def analyze_source(source: str, path: str = "<string>") -> StaticReport:
    """Анализирует исходный код и возвращает отчёт со score 0..100."""
    issues: list[Issue] = []
    lines = source.splitlines()
    tree = ast.parse(source)

    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]

    for node in ast.walk(tree):
        # Глобальные statement'ы — источник трудноуловимых багов.
        if isinstance(node, ast.Global):
            issues.append(_issue(
                "E001", "оператор global", Severity.WARNING, node.lineno,
                "global делает поток данных непредсказуемым; верните значение из функции",
            ))
        # Сравнение с None через == игнорирует переопределённый __eq__.
        if isinstance(node, ast.Compare):
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant) and comparator.value is None:
                    issues.append(_issue(
                        "W006", "сравнение с None через ==", Severity.INFO, node.lineno,
                        "используйте 'is None' / 'is not None'",
                    ))

    for func in functions:
        # Функция без докстринга.
        if ast.get_docstring(func) is None:
            issues.append(_issue(
                "W001", "функция без докстринга", Severity.WARNING, func.lineno,
                f"опишите в двух строках, что делает {func.name}()",
            ))
        # Имя, затеняющее встроенное (def list(...), def sum(...)).
        if func.name in _BUILTIN_NAMES:
            issues.append(_issue(
                "W005", f"имя '{func.name}' затеняет встроенное", Severity.WARNING,
                func.lineno,
                f"переименуйте функцию: {func.name} перекрывает builtins.{func.name}",
            ))
        # Изменяемое значение аргумента по умолчанию.
        for default in func.args.defaults:
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                issues.append(_issue(
                    "W003", "изменяемый аргумент по умолчанию", Severity.ERROR,
                    func.lineno,
                    "значение по умолчанию создаётся один раз при импорте; используйте None",
                ))
        # Слишком длинная функция.
        length = (func.end_lineno or func.lineno) - func.lineno + 1
        if length > _MAX_FUNCTION_LINES:
            issues.append(_issue(
                "W004", f"функция длиннее {_MAX_FUNCTION_LINES} строк ({length})", Severity.INFO,
                func.lineno,
                "разбейте функцию на части — каждую будет проще тестировать",
            ))

    for node in ast.walk(tree):
        # Голый except ловит всё, включая KeyboardInterrupt.
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append(_issue(
                "W002", "голый except", Severity.ERROR, node.lineno,
                "ловите конкретное исключение, например ValueError",
            ))

    # TODO/FIXME — маркеры незавершённой работы.
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if "TODO" in stripped or "FIXME" in stripped:
            issues.append(_issue(
                "W007", "незакрытый TODO/FIXME", Severity.INFO, lineno,
                "уберите маркер или заведите задачу в трекере",
            ))

    issues.sort(key=lambda issue: (issue.line, issue.code))
    score = max(0.0, 100.0 - sum(_PENALTY[issue.severity] for issue in issues))
    return StaticReport(
        path=path,
        lines=len(lines),
        functions=len(functions),
        issues=issues,
        score=round(score, 1),
    )


def analyze_file(path: str | Path) -> StaticReport:
    """Читает файл с диска и анализирует его содержимое."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"файл не найден: {file_path}")
    if file_path.suffix != ".py":
        raise ValueError(f"ожидался .py файл, получен: {file_path.suffix or 'без расширения'}")
    source = file_path.read_text(encoding="utf-8")
    return analyze_source(source, path=str(file_path))
