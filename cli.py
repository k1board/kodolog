"""Командный интерфейс Kodolog.

Примеры:
    python -m kodolog analyze examples/submissions/bad_solve.py
    python -m kodolog test examples/test_submissions.py
    python -m kodolog review examples/submissions/bad_solve.py --tests examples/test_submissions.py
    python -m kodolog synth examples/submissions/good_solve.py --out generated
    python -m kodolog dataset examples/submissions --out data.jsonl
    python -m kodolog metrics examples/submissions --tests examples/test_submissions.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .analyzer import analyze_file
from .dataset import build_dataset, issue_cooccurrence, summary_text, to_jsonl
from .llm import get_client
from .metrics import compute_metrics, overall_pass_rate, to_markdown
from .models import Review, StaticReport, TestReport
from .reviewer import review_file
from .runner import run_tests
from .synth import generate_tests, save_tests


def _print_json(model) -> None:
    """Печатает pydantic-модель человекочитаемым JSON."""
    print(json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2))


def cmd_analyze(args: argparse.Namespace) -> int:
    reports = []
    for pattern in args.files:
        paths = sorted(Path().glob(pattern)) if any(ch in pattern for ch in "*?[") else [Path(pattern)]
        if not paths:
            print(f"не найдено файлов по шаблону: {pattern}", file=sys.stderr)
            return 2
        for path in paths:
            report = analyze_file(path)
            reports.append(report)
            _print_json(report)
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    report = run_tests(args.file, timeout=args.timeout)
    _print_json(report)
    return 0 if report.failed == 0 and report.errors == 0 else 1


def cmd_review(args: argparse.Namespace) -> int:
    print(f"режим LLM: {get_client().name}", file=sys.stderr)
    review = review_file(args.file, test_path=args.tests)
    _print_json(review)
    return 0


def cmd_synth(args: argparse.Namespace) -> int:
    tests = generate_tests(args.file, max_functions=args.max_functions)
    if not tests:
        print("в файле не нашлось функций верхнего уровня", file=sys.stderr)
        return 1
    written = save_tests(tests, args.out)
    for path, test in zip(written, tests):
        print(f"[{test.origin}] {path}  —  {test.description}")
    print(f"готово: {len(written)} синтетических тестов в {args.out}/")
    return 0


def cmd_dataset(args: argparse.Namespace) -> int:
    records = build_dataset(args.directory)
    print(summary_text(records))
    if records and args.out:
        out = to_jsonl(records, args.out)
        print(f"датасет сохранён: {out}")
    matrix = issue_cooccurrence(records)
    if matrix:
        print("совместная встречаемость замечаний:")
        for first, neighbours in matrix.items():
            pairs = ", ".join(f"{second}×{count}" for second, count in neighbours.items())
            print(f"  {first} -> {pairs}")
    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    static_reports = [analyze_file(path) for path in sorted(Path(args.directory).glob("*.py"))]
    test_reports = [run_tests(args.tests)] if args.tests else []
    summary = compute_metrics(static_reports, test_reports)
    print(to_markdown(summary, test_reports))
    if args.json:
        _print_json(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kodolog",
        description="Kodolog — ассистент проверки учебного Python-кода: "
                    "статический анализ, тесты, LLM-ревью и синтетические кейсы.",
    )
    parser.add_argument("--version", action="version", version=f"kodolog {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="статический анализ файла(ов)")
    p_analyze.add_argument("files", nargs="+", help="путь или glob-шаблон, например 'examples/submissions/*.py'")
    p_analyze.set_defaults(func=cmd_analyze)

    p_test = sub.add_parser("test", help="прогнать unittest-тесты в изолированном процессе")
    p_test.add_argument("file", help="файл с тестами")
    p_test.add_argument("--timeout", type=int, default=30, help="таймаут в секундах (по умолчанию 30)")
    p_test.set_defaults(func=cmd_test)

    p_review = sub.add_parser("review", help="полное ревью: анализ + тесты + LLM")
    p_review.add_argument("file", help="файл с работой")
    p_review.add_argument("--tests", help="файл тестов (необязательно)")
    p_review.set_defaults(func=cmd_review)

    p_synth = sub.add_parser("synth", help="сгенерировать синтетические тесты к функциям")
    p_synth.add_argument("file", help="файл с работой")
    p_synth.add_argument("--out", default="generated_tests", help="куда сохранить тесты")
    p_synth.add_argument("--max-functions", type=int, default=5, help="максимум функций")
    p_synth.set_defaults(func=cmd_synth)

    p_dataset = sub.add_parser("dataset", help="собрать каталог работ в JSONL-датасет")
    p_dataset.add_argument("directory", help="каталог с .py файлами")
    p_dataset.add_argument("--out", help="путь к файлу .jsonl")
    p_dataset.set_defaults(func=cmd_dataset)

    p_metrics = sub.add_parser("metrics", help="сводные метрики по каталогу работ")
    p_metrics.add_argument("directory", help="каталог с .py файлами")
    p_metrics.add_argument("--tests", help="файл тестов для доли зелёных")
    p_metrics.add_argument("--json", action="store_true", help="дополнительно напечатать JSON")
    p_metrics.set_defaults(func=cmd_metrics)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
