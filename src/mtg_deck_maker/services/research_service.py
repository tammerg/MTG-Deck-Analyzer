"""Commander research service powered by LLM."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from mtg_deck_maker.advisor.llm_provider import LLMProvider, get_provider

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ResearchResult:
    """Result of a commander research query."""

    commander_name: str
    strategy_overview: str = ""
    key_cards: list[str] = field(default_factory=list)
    budget_staples: list[str] = field(default_factory=list)
    combos: list[str] = field(default_factory=list)
    win_conditions: list[str] = field(default_factory=list)
    cards_to_avoid: list[str] = field(default_factory=list)
    raw_response: str = ""
    parse_success: bool = True


_RESEARCH_PROMPT = """\
You are an expert Magic: The Gathering Commander deck builder.
Analyze the following commander and provide your recommendations.

Commander: {name}
Oracle Text: {oracle_text}
Color Identity: {colors}
{budget_line}

Respond with a JSON object inside a ```json fenced code block with these exact keys:
{{
  "strategy_overview": "...",
  "key_cards": ["card1", "card2", ...],
  "budget_staples": ["card1", "card2", ...],
  "combos": ["description1", "description2", ...],
  "win_conditions": ["win con 1", "win con 2", ...],
  "cards_to_avoid": ["card1", "card2", ...]
}}

Limit key_cards to 15 max, budget_staples to 10 max, combos to 5 max.
If unsure about a section, use an empty list."""

_JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)\n\s*```", re.DOTALL)


def _parse_research_response(raw: str, commander_name: str) -> ResearchResult:
    """Parse a research response from the LLM.

    Extracts JSON from a fenced code block and maps it to a ResearchResult.
    If parsing fails, returns a result with parse_success=False and the
    raw response preserved.
    """
    result = ResearchResult(
        commander_name=commander_name,
        raw_response=raw,
    )

    match = _JSON_BLOCK_RE.search(raw)
    if not match:
        result.parse_success = False
        return result

    try:
        data = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        result.parse_success = False
        return result

    if not isinstance(data, dict):
        result.parse_success = False
        return result

    result.strategy_overview = str(data.get("strategy_overview", ""))
    result.key_cards = _to_str_list(data.get("key_cards", []))
    result.budget_staples = _to_str_list(data.get("budget_staples", []))
    result.combos = _to_str_list(data.get("combos", []))
    result.win_conditions = _to_str_list(data.get("win_conditions", []))
    result.cards_to_avoid = _to_str_list(data.get("cards_to_avoid", []))

    return result


def _to_str_list(value: object) -> list[str]:
    """Safely convert a value to a list of strings."""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


class ResearchService:
    """Commander research powered by an LLM provider."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider

    def research_commander(
        self,
        commander_name: str,
        oracle_text: str = "",
        color_identity: list[str] | None = None,
        budget: float | None = None,
    ) -> ResearchResult:
        """Research a commander and return structured recommendations.

        Args:
            commander_name: Name of the commander card.
            oracle_text: Oracle text of the commander.
            color_identity: List of color letters (e.g. ["W", "U", "B", "G"]).
            budget: Optional budget constraint in USD.

        Returns:
            ResearchResult with structured recommendations or raw fallback.

        Raises:
            RuntimeError: If no LLM provider is available.
        """
        provider = self._provider or get_provider("auto")
        if provider is None:
            raise RuntimeError(
                "No LLM provider available. Set OPENAI_API_KEY or "
                "ANTHROPIC_API_KEY environment variable."
            )

        colors = "/".join(color_identity) if color_identity else "colorless"
        budget_line = f"Budget: ${budget:.2f}" if budget is not None else ""

        user_msg = _RESEARCH_PROMPT.format(
            name=commander_name,
            oracle_text=oracle_text or "(not provided)",
            colors=colors,
            budget_line=budget_line,
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert Magic: The Gathering Commander deck "
                    "builder. Respond only with the requested JSON block."
                ),
            },
            {"role": "user", "content": user_msg},
        ]

        raw = provider.chat(messages, max_tokens=2048, temperature=0.7)
        return _parse_research_response(raw, commander_name)
