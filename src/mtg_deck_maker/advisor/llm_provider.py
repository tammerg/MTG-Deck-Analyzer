"""Abstract LLM provider interface and factory function."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        timeout_s: float = 60.0,
    ) -> str:
        """Send a chat message and return the text response."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider has a valid API key AND the SDK is installed."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider display name (e.g. 'OpenAI ChatGPT')."""
        ...

    @property
    @abstractmethod
    def model_id(self) -> str:
        """Return the specific model identifier used for API calls.

        This is the value passed to the provider's API (e.g.
        ``'claude-sonnet-4-20250514'`` or ``'gpt-4o'``).  It is distinct from
        ``name`` (the human-readable display label) and must be used wherever
        a stable, unambiguous identifier is required — for instance as a cache
        key for the LLM synergy repository.
        """
        ...


def get_provider(
    preferred: str = "auto",
    model: str | None = None,
) -> LLMProvider | None:
    """Resolve an LLM provider.

    Args:
        preferred: "openai", "anthropic", or "auto" (tries openai first,
            then anthropic).
        model: Optional model name override passed to the provider constructor.

    Returns:
        An available LLMProvider, or None if no API keys are set.
    """
    from mtg_deck_maker.advisor.anthropic_provider import AnthropicProvider
    from mtg_deck_maker.advisor.openai_provider import OpenAIProvider

    kwargs: dict[str, str] = {}
    if model is not None:
        kwargs["model"] = model

    if preferred == "openai":
        p: LLMProvider = OpenAIProvider(**kwargs)
        return p if p.is_available() else None
    elif preferred == "anthropic":
        p = AnthropicProvider(**kwargs)
        return p if p.is_available() else None
    else:
        # Auto: try OpenAI first, then Anthropic
        for cls in (OpenAIProvider, AnthropicProvider):
            p = cls(**kwargs)
            if p.is_available():
                return p
        return None
