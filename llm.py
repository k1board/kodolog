"""LLM-клиент: OpenAI-совместимый API и офлайн-заглушка.

Проект работает в двух режимах:
  * MockLLMClient — детерминированная заглушка без сети (по умолчанию,
    чтобы демо запускалось у любого человека за минуту);
  * OpenAICompatClient — любой API с endpoint'ом /chat/completions
    (OpenAI, OpenRouter, vLLM, локальный Ollama с прокси-обёрткой).

Переключение — переменными окружения, см. get_client().
"""

from __future__ import annotations

import os
import re
import time
from typing import Protocol

import requests

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"


class LLMError(RuntimeError):
    """Ошибка обращения к LLM API."""


class LLMClient(Protocol):
    """Интерфейс, общий для настоящего клиента и заглушки."""

    name: str

    def complete(self, system: str, user: str) -> str:
        """Возвращает текст ответа модели на пару промптов."""
        ...


class OpenAICompatClient:
    """Клиент для любого OpenAI-совместимого chat/completions API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.name = f"api:{model}"

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}/chat/completions"

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                if response.status_code in (429, 500, 502, 503):
                    # Плавная пауза перед повтором: 1 с, 2 с, ...
                    time.sleep(2 ** attempt)
                    last_error = LLMError(f"API вернул {response.status_code}: {response.text[:200]}")
                    continue
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
            except (requests.RequestException, KeyError, IndexError) as exc:
                last_error = exc
                time.sleep(2 ** attempt)
        raise LLMError(f"LLM API недоступен после {self.max_retries + 1} попыток: {last_error}")


class MockLLMClient:
    """Детерминированная заглушка: полезна для тестов и офлайн-демо.

    Заглушка «читает» машинночитаемый блок данных из промпта ревьюера
    (строки static: {...} и tests: {...}) и собирает по ним правдоподобный
    ответ — так пайплайн можно прогнать целиком без ключа API.
    """

    name = "mock"

    _STATIC_RE = re.compile(r"^static: (\{.*\})$", re.MULTILINE)
    _TESTS_RE = re.compile(r"^tests: (\{.*\})$", re.MULTILINE)

    def complete(self, system: str, user: str) -> str:
        import json

        static = self._parse_block(self._STATIC_RE.search(user))
        tests = self._parse_block(self._TESTS_RE.search(user))

        issues = static.get("issues", [])
        errors = sum(1 for issue in issues if issue.get("severity") == "error")
        warnings = sum(1 for issue in issues if issue.get("severity") == "warning")
        grade = max(0, min(10, 10 - errors * 2 - warnings))

        hints = []
        for issue in issues[:3]:
            hints.append({
                "area": f"строка {issue.get('line', '?')}: {issue.get('title', 'замечание')}",
                "text": issue.get("hint", "исправьте замечание анализатора"),
                "severity": issue.get("severity", "info"),
            })

        total, passed = tests.get("total", 0), tests.get("passed", 0)
        if total and passed < total:
            hints.append({
                "area": "тесты",
                "text": f"проходит {passed} из {total} тестов: сначала добейтесь зелёного прогона, потом наводите красоту",
                "severity": "error",
            })

        overall = (
            f"Работа выглядит как типичное решение первокурсника: "
            f"статический анализ нашёл {len(issues)} замечаний (ошибок: {errors}). "
        )
        if total:
            overall += f"Тесты: {passed}/{total} зелёные. "
        overall += "Начните с ошибок уровня error — они ломают поведение, остальное косметика."

        return json.dumps({
            "overall": overall,
            "hints": hints,
            "grade": grade,
            "model": "mock",
        }, ensure_ascii=False)

    @staticmethod
    def _parse_block(match: re.Match | None) -> dict:
        if match is None:
            return {}
        try:
            import json
            return json.loads(match.group(1))
        except ValueError:
            return {}


def get_client() -> LLMClient:
    """Фабрика: возвращает API-клиент, если есть ключ, иначе заглушку.

    Переменные окружения:
      KOODOLOG_API_KEY / OPENAI_API_KEY — ключ API;
      KOODOLOG_BASE_URL — базовый URL (по умолчанию api.openai.com/v1);
      KODOLOG_MODEL     — имя модели (по умолчанию gpt-4o-mini).
    """
    api_key = os.environ.get("KOODOLOG_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return MockLLMClient()
    return OpenAICompatClient(
        api_key=api_key,
        base_url=os.environ.get("KOODOLOG_BASE_URL", DEFAULT_BASE_URL),
        model=os.environ.get("KODOLOG_MODEL", DEFAULT_MODEL),
    )
