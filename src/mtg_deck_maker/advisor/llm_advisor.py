"""LLM-powered deck advisor using the Anthropic Claude API.

Provides AI-powered deck advice by combining structured deck analysis
context with user questions. Gracefully falls back when no API key is
configured.
"""

from __future__ import annotations

import os

try:
    import anthropic as _anthropic_module
except ImportError:
    _anthropic_module = None  # type: ignore[assignment]

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
) -> str:
    """Get AI-powered advice for a Commander deck.

    Builds structured context from the deck analysis and sends it along
    with the user's question to the Claude API. Returns a text response
    with deck-building advice.

    Falls back gracefully when no API key is available.

    Args:
        deck_analysis: Analyzed deck data providing context.
        question: The user's question or description of a problem.
        api_key: Optional Anthropic API key. If None, checks the
            ANTHROPIC_API_KEY environment variable.

    Returns:
        Text response with deck advice, or a fallback message if the
        API is unavailable.
    """
    resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not resolved_key:
        return _NO_API_KEY_MSG

    context = _build_context(deck_analysis)

    system_prompt = (
        "You are an expert Magic: The Gathering Commander deck builder. "
        "You provide concise, actionable advice based on deck analysis data. "
        "Focus on practical suggestions the player can implement."
    )

    user_message = (
        f"{context}\n\n"
        f"## Player Question\n{question}"
    )

    if _anthropic_module is None:
        return "LLM advice requires the 'anthropic' package to be installed."

    try:
        client = _anthropic_module.Anthropic(api_key=resolved_key)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message},
            ],
        )

        # Extract text from the response
        if message.content and len(message.content) > 0:
            return message.content[0].text

        return "No response generated. Please try again."

    except Exception as exc:
        error_str = str(exc)
        if "rate_limit" in error_str.lower() or "429" in error_str:
            return _RATE_LIMIT_MSG
        return _API_ERROR_MSG.format(error=error_str)
