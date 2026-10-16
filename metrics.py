"""Метрики по набору работ: доля прохождения тестов, распределение ошибок.

Отдельный модуль нужен, чтобы отвечать на вопрос «стало ли лучше?»
не на глаз, а числами: средний score, топ замечаний, доля зелёных
тестов. Это мини-версия того, что делают бенчмарк-фреймворки.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from .models import MetricsSummary, StaticReport, TestReport


def compute_metrics(static_reports: list[StaticReport],
                    test_reports: Optional[list[TestReport]] = None) -> MetricsSummary:
    """Считает сводные метрики по отчётам анализатора и тестов."""
    if not static_reports:
        return MetricsSummary()

    by_severity: Counter[str] = Counter()
    issue_codes: Counter[str] = Counter()
    for report in static_reports:
        for issue in report.issues:
            by_severity[issue.severity.value] += 1
            issue_codes[issue.code] += 1

    return MetricsSummary(
        files=len(static_reports),
        total_issues=sum(by_severity.values()),
        avg_score=round(sum(r.score for r in static_reports) / len(static_reports), 1),
        avg_lines=round(sum(r.lines for r in static_reports) / len(static_reports), 1),
        by_severity=dict(sorted(by_severity.items())),
        top_issue_codes=dict(issue_codes.most_common(5)),
    )


def overall_pass_rate(test_reports: list[TestReport]) -> Optional[float]:
    """Средневзвешенная доля пройденных тестов по всем прогонам."""
    total = sum(report.total for report in test_reports)
    if total == 0:
        return None
    passed = sum(report.passed for report in test_reports)
    return round(passed / total, 4)


def to_markdown(summary: MetricsSummary,
                test_reports: Optional[list[TestReport]] = None) -> str:
    """Рендерит сводку в Markdown — удобно вставить в PR или отчёт."""
    lines = [
        f"Файлов: **{summary.files}**, суммарно замечаний: **{summary.total_issues}**",
        f"Средний score: **{summary.avg_score} / 100**, средний размер: **{summary.avg_lines} строк**",
    ]
    rate = overall_pass_rate(test_reports or [])
    if rate is not None:
        lines.append(f"Доля зелёных тестов: **{rate:.0%}**")
    if summary.by_severity:
        severity = ", ".join(f"{level}: {count}" for level, count in summary.by_severity.items())
        lines.append(f"Замечания по серьёзности — {severity}")
    if summary.top_issue_codes:
        codes = ", ".join(f"`{code}` ×{count}" for code, count in summary.top_issue_codes.items())
        lines.append(f"Топ правил: {codes}")
    return "\n\n".join(lines)
