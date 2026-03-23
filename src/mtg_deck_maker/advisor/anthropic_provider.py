"""Anthropic Claude LLM provider implementation."""

from __future__ import annotations

import logging
import os
from typing import Any

from mtg_deck_maker.advisor.llm_provider import LLMProvider
from mtg_deck_maker.advisor.retry import with_retries

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "claude-sonnet-4-20250514"


class AnthropicProvider(LLMProvider):
    """LLM provider using the Anthropic Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._model = model
        self._client = None

    def _get_client(self) -> Any:  # Returns anthropic.Anthropic
        """Lazy-initialize the Anthropic client (created once and reused)."""
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise RuntimeError(
                    "Anthropic provider requires the 'anthropic' package. "
                    "Install with: pip install anthropic"
                ) from exc
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float = 60.0,
    ) -> str:
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set.")

        client = self._get_client()

        # Extract system message if present
        system_msg = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append(msg)

        def _call() -> str:
            kwargs: dict = {
                "model": self._model,
                "max_tokens": max_tokens,
                "messages": user_messages,
                "temperature": temperature,
                "timeout": timeout_s,
            }
            if system_msg:
                kwargs["system"] = system_msg

            response = client.messages.create(**kwargs)

            if response.content and len(response.content) > 0:
                return response.content[0].text
            return ""

        return with_retries(_call)

    def is_available(self) -> bool:
        if not self._api_key:
            return False
        try:
            import anthropic  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "Anthropic Claude"

    @property
    def model_id(self) -> str:
        return self._model
