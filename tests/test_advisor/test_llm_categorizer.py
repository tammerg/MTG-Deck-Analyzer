"""Tests for the LLM-assisted card categorization module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from mtg_deck_maker.advisor.llm_categorizer import (
    LLMCategorizer,
    _is_uncategorized,
    _parse_llm_categories,
)
from mtg_deck_maker.advisor.llm_provider import LLMProvider
from mtg_deck_maker.models.card import Card


def _make_card(
    name: str,
    oracle_text: str = "",
    type_line: str = "Creature",
    card_id: int | None = None,
) -> Card:
    """Helper to create a Card for testing."""
    return Card(
        oracle_id=f"oid-{name}",
        name=name,
        type_line=type_line,
        oracle_text=oracle_text,
        id=card_id,
    )


def _fake_provider(response: str) -> MagicMock:
    """Create a MagicMock LLM provider returning a fixed response."""
    provider = MagicMock(spec=LLMProvider)
    provider.chat.return_value = response
    provider.is_available.return_value = True
    provider.name = "FakeProvider"
    return provider


# === _is_uncategorized helper ===


class TestIsUncategorized:
    def test_with_only_type_categories(self):
        """A card with only type-based categories is uncategorized."""
        categories = [("creature", 1.0)]
        assert _is_uncategorized(categories) is True

    def test_with_functional_category(self):
        """A card with a functional category is NOT uncategorized."""
        categories = [("creature", 1.0), ("ramp", 0.8)]
        assert _is_uncategorized(categories) is False

    def test_with_utility_only(self):
        """A card with only utility is uncategorized."""
        categories = [("utility", 0.5)]
        assert _is_uncategorized(categories) is True

    def test_with_multiple_type_categories(self):
        """A card with multiple type-based categories is still uncategorized."""
        categories = [("artifact", 1.0), ("creature", 1.0)]
        assert _is_uncategorized(categories) is True

    def test_with_type_and_utility(self):
        """A card with type + utility is still uncategorized."""
        categories = [("creature", 1.0), ("utility", 0.5)]
        assert _is_uncategorized(categories) is True

    def test_empty_categories(self):
        """A card with no categories at all is uncategorized."""
        assert _is_uncategorized([]) is True


# === _parse_llm_categories helper ===


class TestParseLLMCategories:
    def test_valid_json(self):
        """Should parse valid JSON correctly."""
        raw = json.dumps({
            "Sol Ring": [["ramp", 0.95]],
            "Swords to Plowshares": [["removal", 0.9]],
        })
        result = _parse_llm_categories(raw)
        assert "Sol Ring" in result
        assert result["Sol Ring"] == [("ramp", 0.95)]
        assert result["Swords to Plowshares"] == [("removal", 0.9)]

    def test_handles_fenced_json_block(self):
        """Should handle ```json fenced blocks."""
        raw = '```json\n{"Sol Ring": [["ramp", 0.95]]}\n```'
        result = _parse_llm_categories(raw)
        assert "Sol Ring" in result
        assert result["Sol Ring"] == [("ramp", 0.95)]

    def test_clamps_confidence(self):
        """Confidence values above 1.0 or below 0.0 should be clamped."""
        raw = json.dumps({
            "Card A": [["ramp", 1.5]],
            "Card B": [["removal", -0.3]],
        })
        result = _parse_llm_categories(raw)
        assert result["Card A"] == [("ramp", 1.0)]
        assert result["Card B"] == [("removal", 0.0)]

    def test_filters_invalid_categories(self):
        """Invalid category names should be filtered out."""
        raw = json.dumps({
            "Card A": [["ramp", 0.9], ["flying", 0.8]],
        })
        result = _parse_llm_categories(raw)
        assert result["Card A"] == [("ramp", 0.9)]

    def test_filters_card_with_all_invalid_categories(self):
        """A card with only invalid categories should have an empty list."""
        raw = json.dumps({
            "Card A": [["flying", 0.8], ["trample", 0.7]],
        })
        result = _parse_llm_categories(raw)
        assert result["Card A"] == []

    def test_parse_failure_returns_empty(self):
        """Garbage input should return an empty dict."""
        result = _parse_llm_categories("this is not json at all")
        assert result == {}

    def test_empty_string(self):
        """Empty string should return an empty dict."""
        result = _parse_llm_categories("")
        assert result == {}


# === LLMCategorizer.categorize_batch ===


class TestCategorizeBatch:
    def test_parses_valid_response(self):
        """Should parse a valid LLM JSON response into categories."""
        llm_response = json.dumps({
            "Sol Ring": [["ramp", 0.95]],
            "Rhystic Study": [["card_draw", 0.9]],
        })
        provider = _fake_provider(llm_response)
        categorizer = LLMCategorizer(provider=provider, batch_size=25)

        cards = [
            _make_card("Sol Ring", oracle_text="{T}: Add {C}{C}."),
            _make_card("Rhystic Study", oracle_text="Whenever an opponent casts a spell..."),
        ]
        result = categorizer.categorize_batch(cards)

        assert result["Sol Ring"] == [("ramp", 0.95)]
        assert result["Rhystic Study"] == [("card_draw", 0.9)]
        provider.chat.assert_called_once()

    def test_handles_parse_failure(self):
        """Should return empty dict when LLM returns garbage."""
        provider = _fake_provider("I don't understand the question")
        categorizer = LLMCategorizer(provider=provider)

        cards = [_make_card("Sol Ring")]
        result = categorizer.categorize_batch(cards)

        assert result == {}

    def test_splits_into_chunks(self):
        """30 cards with batch_size=25 should make 2 LLM calls."""
        llm_response = json.dumps({})
        provider = _fake_provider(llm_response)
        categorizer = LLMCategorizer(provider=provider, batch_size=25)

        cards = [_make_card(f"Card {i}") for i in range(30)]
        categorizer.categorize_batch(cards)

        assert provider.chat.call_count == 2

    def test_clamps_confidence(self):
        """Confidence values > 1.0 should be clamped to 1.0."""
        llm_response = json.dumps({
            "Broken Card": [["ramp", 2.5]],
        })
        provider = _fake_provider(llm_response)
        categorizer = LLMCategorizer(provider=provider)

        cards = [_make_card("Broken Card")]
        result = categorizer.categorize_batch(cards)

        assert result["Broken Card"] == [("ramp", 1.0)]

    def test_filters_invalid_categories(self):
        """Invalid category names should be filtered out from results."""
        llm_response = json.dumps({
            "Card A": [["ramp", 0.9], ["flying", 0.8]],
        })
        provider = _fake_provider(llm_response)
        categorizer = LLMCategorizer(provider=provider)

        cards = [_make_card("Card A")]
        result = categorizer.categorize_batch(cards)

        assert result["Card A"] == [("ramp", 0.9)]

    def test_empty_input(self):
        """Empty card list should return empty dict without calling LLM."""
        provider = _fake_provider("")
        categorizer = LLMCategorizer(provider=provider)

        result = categorizer.categorize_batch([])

        assert result == {}
        provider.chat.assert_not_called()

    def test_no_provider(self):
        """Should raise RuntimeError if no provider is available."""
        categorizer = LLMCategorizer(provider=None)

        with pytest.raises(RuntimeError, match="No LLM provider"):
            categorizer.categorize_batch([_make_card("Sol Ring")])

    def test_prompt_includes_card_names_and_oracle_text(self):
        """The prompt sent to the LLM should contain card info."""
        llm_response = json.dumps({"Sol Ring": [["ramp", 0.95]]})
        provider = _fake_provider(llm_response)
        categorizer = LLMCategorizer(provider=provider)

        cards = [_make_card("Sol Ring", oracle_text="{T}: Add {C}{C}.")]
        categorizer.categorize_batch(cards)

        # Extract the messages sent to the LLM
        call_args = provider.chat.call_args
        messages = call_args[0][0] if call_args[0] else call_args[1]["messages"]
        prompt_text = " ".join(m["content"] for m in messages)

        assert "Sol Ring" in prompt_text
        assert "{T}: Add {C}{C}." in prompt_text

    def test_handles_fenced_json_block(self):
        """Should handle LLM wrapping response in ```json ... ```."""
        llm_response = '```json\n{"Sol Ring": [["ramp", 0.95]]}\n```'
        provider = _fake_provider(llm_response)
        categorizer = LLMCategorizer(provider=provider)

        cards = [_make_card("Sol Ring", oracle_text="{T}: Add {C}{C}.")]
        result = categorizer.categorize_batch(cards)

        assert result["Sol Ring"] == [("ramp", 0.95)]


# === LLMCategorizer.categorize_uncategorized ===


class TestCategorizeUncategorized:
    def test_filters_correctly(self) -> None:
        """Only cards missing functional categories should be sent to LLM."""
        llm_response = json.dumps({
            "Mystery Creature": [["recursion", 0.8]],
        })
        provider = _fake_provider(llm_response)
        categorizer = LLMCategorizer(provider=provider)

        cards = [
            _make_card("Sol Ring", oracle_text="{T}: Add {C}{C}.", card_id=1),
            _make_card("Mystery Creature", oracle_text="When ~ dies, do something weird.", card_id=2),
        ]
        # Sol Ring has ramp (functional), Mystery Creature only has creature (type-based)
        existing: dict[int, list[tuple[str, float]]] = {
            1: [("artifact", 1.0), ("ramp", 0.85)],
            2: [("creature", 1.0)],
        }

        result = categorizer.categorize_uncategorized(cards, existing)

        # Only Mystery Creature should be in results
        assert "Mystery Creature" in result
        assert "Sol Ring" not in result
        assert result["Mystery Creature"] == [("recursion", 0.8)]

    def test_no_uncategorized_cards_skips_llm(self) -> None:
        """If all cards have functional categories, no LLM call is made."""
        provider = _fake_provider("{}")
        categorizer = LLMCategorizer(provider=provider)

        cards = [_make_card("Sol Ring", card_id=1)]
        existing: dict[int, list[tuple[str, float]]] = {
            1: [("artifact", 1.0), ("ramp", 0.85)],
        }

        result = categorizer.categorize_uncategorized(cards, existing)

        assert result == {}
        provider.chat.assert_not_called()

    def test_card_without_existing_entry_is_uncategorized(self) -> None:
        """A card not present in existing dict should be treated as uncategorized."""
        llm_response = json.dumps({
            "New Card": [["protection", 0.7]],
        })
        provider = _fake_provider(llm_response)
        categorizer = LLMCategorizer(provider=provider)

        cards = [_make_card("New Card", card_id=3)]
        existing: dict[int, list[tuple[str, float]]] = {}

        result = categorizer.categorize_uncategorized(cards, existing)

        assert "New Card" in result
