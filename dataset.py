"""Сбор папки работ в структурированный датасет (JSONL).

Превращает «кучу файлов» в данные, с которыми можно работать: каждая
работа становится записью с метриками и кодами замечаний. Бонус —
матрица совместной встречаемости замечаний: какие ошибки ходят парами.
Это toy-версия того, что делает анализ любой открытой экосистемы
(публикации, репозитории, люди) — только на папке с работами.
"""

from __future__ import annotations

import json
from pathlib import Path

from .analyzer import analyze_file
from .models import DatasetRecord


def build_dataset(directory: str | Path, pattern: str = "*.py") -> list[DatasetRecord]:
    """Собирает записи по всем .py-файлам каталога (без подкаталогов)."""
    root = Path(directory)
    if not root.is_dir():
        raise NotADirectoryError(f"каталог не найден: {root}")

    records = []
    for file_path in sorted(root.glob(pattern)):
        try:
            report = analyze_file(file_path)
        except (SyntaxError, ValueError, OSError):
            # Битый файл не должен ронять весь датасет — пропускаем.
            continue
        records.append(DatasetRecord(
            file=file_path.name,
            lines=report.lines,
            functions=report.functions,
            issues_total=len(report.issues),
            issue_codes=[issue.code for issue in report.issues],
            score=report.score,
        ))
    return records


def to_jsonl(records: list[DatasetRecord], out_path: str | Path) -> Path:
    """Сохраняет записи построчно в JSONL — формат датасетов для LLM."""
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as stream:
        for record in records:
            stream.write(record.model_dump_json() + "\n")
    return target


def issue_cooccurrence(records: list[DatasetRecord]) -> dict[str, dict[str, int]]:
    """Матрица совместной встречаемости кодов замечаний.

    Пример: {'W001': {'W002': 2, 'W003': 1}, ...} — в двух работах
    одновременно встретились W001 и W002. Полезно, чтобы понять,
    какие ошибки «ходят парами» и что объяснять на семинаре вместе.
    """
    matrix: dict[str, dict[str, int]] = {}
    for record in records:
        unique = sorted(set(record.issue_codes))
        for i, first in enumerate(unique):
            for second in unique[i + 1:]:
                matrix.setdefault(first, {}).setdefault(second, 0)
                matrix[first][second] += 1
    return matrix


def load_jsonl(path: str | Path) -> list[DatasetRecord]:
    """Читает JSONL обратно в модели — для последующих экспериментов."""
    records = []
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line:
                records.append(DatasetRecord.model_validate_json(line))
    return records


def summary_text(records: list[DatasetRecord]) -> str:
    """Короткий текстовый отчёт по датасету — для CLI и логов."""
    if not records:
        return "датасет пуст: в каталоге нет подходящих .py файлов"
    total_issues = sum(record.issues_total for record in records)
    avg_score = sum(record.score for record in records) / len(records)
    return (
        f"записей: {len(records)}, суммарно замечаний: {total_issues}, "
        f"средний score: {avg_score:.1f}/100"
    )
