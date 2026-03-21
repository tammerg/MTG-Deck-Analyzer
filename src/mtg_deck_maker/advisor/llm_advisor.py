"""LLM-powered deck advisor using the Anthropic Claude API.

Provides AI-powered deck advice by combining structured deck analysis
context with user questions. Gracefully falls back when no API key is
configured.
"""

from __future__ import annotations

from mtg_deck_maker.advisor.analyzer import DeckAnalysis

_NO_API_KEY_MSG = "LLM advice requires ANTHROPIC_API_KEY"
_RATE_LIMIT_MSG = (
    "Rate limit reached. Please wait a moment and try again."
)
_API_ERROR_MSG = "Failed to get LLM advice: {error}"


def _build_context(deck_analysis: DeckAnalysis) -> str:
    """Build a structured context string from a DeckAnalysis.

    Formats the deck analysis into a clear text block that provides
    the LLM with all relevant deck information.

    Args:
        deck_analysis: The analyzed deck data.

    Returns:
        Formatted context string for the LLM prompt.
    """
    lines: list[str] = []
    lines.append("## Deck Analysis Context")
    lines.append("")

    lines.append(f"**Average CMC:** {deck_analysis.avg_cmc:.2f}")
    lines.append(f"**Power Level:** {deck_analysis.power_level}/10")
    lines.append(f"**Total Price:** ${deck_analysis.total_price:.2f}")
    lines.append("")

    lines.append("### Category Breakdown")
    for cat, count in sorted(deck_analysis.category_breakdown.items()):
        lines.append(f"- {cat}: {count}")
    lines.append("")

    lines.append("### Mana Curve")
    for cmc_val in sorted(deck_analysis.mana_curve.keys()):
        count = deck_analysis.mana_curve[cmc_val]
        label = f"{cmc_val}+" if cmc_val == 7 else str(cmc_val)
        lines.append(f"- CMC {label}: {count} cards")
    lines.append("")

    lines.append("### Color Distribution")
    for color, count in sorted(deck_analysis.color_distribution.items()):
        lines.append(f"- {color}: {count}")
    lines.append("")

    if deck_analysis.weak_categories:
        lines.append("### Weak Areas")
        for cat in deck_analysis.weak_categories:
            lines.append(f"- {cat} (below minimum)")
        lines.append("")

    if deck_analysis.strong_categories:
        lines.append("### Strong Areas")
        for cat in deck_analysis.strong_categories:
            lines.append(f"- {cat} (well above minimum)")
        lines.append("")

    if deck_analysis.recommendations:
        lines.append("### Current Recommendations")
        for rec in deck_analysis.recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    return "\n".join(lines)


def get_deck_advice(
    deck_analysis: DeckAnalysis,
    question: str,
    api_key: str | None = None,
    provider: object | None = None,
) -> str:
    """Get AI-powered advice for a Commander deck.

    Builds structured context from the deck analysis and sends it along
    with the user's question to an LLM. Returns a text response with
    deck-building advice.

    Falls back gracefully when no API key is available.

    Args:
        deck_analysis: Analyzed deck data providing context.
        question: The user's question or description of a problem.
        api_key: Optional Anthropic API key (deprecated, kept for compat).
        provider: Optional LLMProvider instance. If None, uses
            get_provider("auto") or falls back to legacy Anthropic path.

    Returns:
        Text response with deck advice, or a fallback message if the
        API is unavailable.
    """
    from mtg_deck_maker.advisor.llm_provider import LLMProvider, get_provider

    # Use provider abstraction if available
    resolved_provider: LLMProvider | None = None
    if isinstance(provider, LLMProvider):
        resolved_provider = provider
    else:
        resolved_provider = get_provider("auto")

    if resolved_provider is not None:
        return _get_advice_via_provider(resolved_provider, deck_analysis, question)

    # No provider available
    return _NO_API_KEY_MSG


def _get_advice_via_provider(
    provider: object,
    deck_analysis: DeckAnalysis,
    question: str,
) -> str:
    """Get advice using the provider abstraction."""
    from mtg_deck_maker.advisor.llm_provider import LLMProvider

    assert isinstance(provider, LLMProvider)

    context = _build_context(deck_analysis)

    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert Magic: The Gathering Commander deck builder. "
                "You provide concise, actionable advice based on deck analysis data. "
                "Focus on practical suggestions the player can implement."
            ),
        },
        {
            "role": "user",
            "content": f"{context}\n\n## Player Question\n{question}",
        },
    ]

    try:
        result = provider.chat(messages, max_tokens=1024)
        return result if result else "No response generated. Please try again."
    except Exception as exc:
        error_str = str(exc)
        if "rate_limit" in error_str.lower() or "429" in error_str:
            return _RATE_LIMIT_MSG
        return _API_ERROR_MSG.format(error=error_str)


