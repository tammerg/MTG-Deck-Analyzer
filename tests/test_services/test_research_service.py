"""Tests for the research service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mtg_deck_maker.advisor.llm_provider import LLMProvider
from mtg_deck_maker.services.research_service import (
    ResearchResult,
    ResearchService,
    _parse_research_response,
)


class _FakeProvider(LLMProvider):
    """Fake provider for testing."""

    def __init__(self, response: str = "") -> None:
        self._response = response

    def chat(self, messages, *, max_tokens=1024, temperature=0.7, timeout_s=60.0) -> str:
        return self._response

    def is_available(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "Fake Provider"


_GOOD_JSON = '''\
Here is my analysis:

```json
{
  "strategy_overview": "Atraxa excels at proliferate strategies.",
  "key_cards": ["Doubling Season", "Deepglow Skate", "Vorinclex, Monstrous Raider"],
  "budget_staples": ["Evolution Sage", "Grateful Apparition"],
  "combos": ["Doubling Season + planeswalker = instant ultimate"],
  "win_conditions": ["Planeswalker ultimates", "Infect"],
  "cards_to_avoid": ["Vorinclex (draws hate)"]
}
```

Hope this helps!'''


class TestParseResearchResponse:
    def test_good_json(self):
        result = _parse_research_response(_GOOD_JSON, "Atraxa")
        assert result.parse_success is True
        assert result.commander_name == "Atraxa"
        assert result.strategy_overview == "Atraxa excels at proliferate strategies."
        assert len(result.key_cards) == 3
        assert "Doubling Season" in result.key_cards
        assert len(result.budget_staples) == 2
        assert len(result.combos) == 1
        assert len(result.win_conditions) == 2
        assert len(result.cards_to_avoid) == 1

    @pytest.mark.parametrize(
        "raw",
        [
            "Just some text without JSON.",
            '```json\n{bad json here}\n```',
            '```json\n["a", "b"]\n```',
        ],
        ids=["no_fenced_block", "malformed_json", "json_not_a_dict"],
    )
    def test_parse_failure(self, raw):
        result = _parse_research_response(raw, "Atraxa")
        assert result.parse_success is False

    def test_missing_keys_uses_defaults(self):
        raw = '```json\n{"strategy_overview": "Go wide."}\n```'
        result = _parse_research_response(raw, "Atraxa")
        assert result.parse_success is True
        assert result.strategy_overview == "Go wide."
        assert result.key_cards == []
        assert result.combos == []

    def test_non_list_key_cards(self):
        raw = '```json\n{"key_cards": "not a list"}\n```'
        result = _parse_research_response(raw, "Atraxa")
        assert result.parse_success is True
        assert result.key_cards == []


class TestResearchService:
    def test_research_commander_happy_path(self):
        provider = _FakeProvider(response=_GOOD_JSON)
        service = ResearchService(provider=provider)
        result = service.research_commander(
            commander_name="Atraxa, Praetors' Voice",
            oracle_text="Flying, vigilance, deathtouch, lifelink\nProliferate.",
            color_identity=["W", "U", "B", "G"],
            budget=100.0,
        )
        assert result.parse_success is True
        assert result.commander_name == "Atraxa, Praetors' Voice"
        assert len(result.key_cards) > 0

    def test_research_commander_no_provider(self):
        service = ResearchService(provider=None)
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(RuntimeError, match="No LLM provider"):
                service.research_commander("Atraxa")

    def test_research_commander_parse_failure(self):
        provider = _FakeProvider(response="I can't help with that.")
        service = ResearchService(provider=provider)
        result = service.research_commander("Atraxa")
        assert result.parse_success is False
        assert "I can't help with that." in result.raw_response


class TestResearchResult:
    def test_defaults(self):
        r = ResearchResult(commander_name="Test")
        assert r.commander_name == "Test"
        assert r.strategy_overview == ""
        assert r.key_cards == []
        assert r.parse_success is True
