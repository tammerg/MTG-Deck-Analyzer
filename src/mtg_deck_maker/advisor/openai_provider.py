"""OpenAI ChatGPT LLM provider implementation."""

from __future__ import annotations

import logging
import os

from mtg_deck_maker.advisor.llm_provider import LLMProvider
from mtg_deck_maker.advisor.retry import with_retries

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-4o"


class OpenAIProvider(LLMProvider):
    """LLM provider using the OpenAI ChatGPT API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._model = model

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float = 60.0,
    ) -> str:
        try:
            import openai
        except ImportError:
            raise RuntimeError(
                "OpenAI provider requires the 'openai' package. "
                "Install with: pip install mtg-deck-maker[openai]"
            )

        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY is not set.")

        client = openai.OpenAI(
            api_key=self._api_key,
            timeout=timeout_s,
        )

        def _call() -> str:
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
                temperature=temperature,
            )

            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            return ""

        return with_retries(_call)

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "OpenAI ChatGPT"
