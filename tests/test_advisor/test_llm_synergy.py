"""Tests for the LLM-assisted pairwise synergy scoring module."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from mtg_deck_maker.advisor.llm_synergy import (
    _build_pair_prompt,
    _canonical_key,
    _parse_synergy_response,
    generate_synergy_matrix,
)
from mtg_deck_maker.advisor.llm_provider import LLMProvider
from mtg_deck_maker.models.card import Card


def _card(name: str, oracle: str = "") -> Card:
    """Helper to create a Card for testing."""
    return Card(oracle_id=f"oid-{name}", name=name, oracle_text=oracle)


def _fake_provider(response: str) -> MagicMock:
    """Create a MagicMock LLM provider returning a fixed response."""
    provider = MagicMock(spec=LLMProvider)
    provider.chat.return_value = response
    provider.is_available.return_value = True
    provider.name = "FakeProvider"
    return provider


# === _canonical_key tests ===


class TestCanonicalKey:
    def test_alphabetical_order_preserved(self):
        """When a < b alphabetically, order is preserved."""
        assert _canonical_key("Alpha", "Beta") == ("Alpha", "Beta")

    def test_reversed_when_b_less_than_a(self):
        """When b < a alphabetically, the pair is reversed."""
        assert _canonical_key("Beta", "Alpha") == ("Alpha", "Beta")

    def test_equal_names(self):
        """Equal names return the same tuple."""
        assert _canonical_key("Sol Ring", "Sol Ring") == ("Sol Ring", "Sol Ring")

    def test_case_sensitivity(self):
        """Uppercase sorts before lowercase in standard string comparison."""
        # 'A' < 'a' in Python string comparison
        assert _canonical_key("alpha", "Alpha") == ("Alpha", "alpha")


# === _parse_synergy_response tests ===


class TestParseSynergyResponse:
    def test_empty_string_returns_empty(self):
        """Empty string input returns empty dict."""
        assert _parse_synergy_response("") == {}

    def test_valid_json_without_fencing(self):
        """Plain JSON without code fences parses correctly."""
        raw = '{"Sol Ring | Arcane Signet": 0.3}'
        result = _parse_synergy_response(raw)
        assert result == {("Arcane Signet", "Sol Ring"): 0.3}

    def test_fenced_json_parses(self):
        """JSON inside ```json ... ``` fences parses correctly."""
        raw = '```json\n{"Sol Ring | Arcane Signet": 0.5}\n```'
        result = _parse_synergy_response(raw)
        assert result == {("Arcane Signet", "Sol Ring"): 0.5}

    def test_fenced_json_no_lang_tag(self):
        """JSON inside ``` ... ``` fences (no json tag) parses correctly."""
        raw = '```\n{"Sol Ring | Arcane Signet": 0.5}\n```'
        result = _parse_synergy_response(raw)
        assert result == {("Arcane Signet", "Sol Ring"): 0.5}

    def test_invalid_json_returns_empty(self):
        """Malformed JSON returns empty dict."""
        assert _parse_synergy_response("{not valid json}") == {}

    def test_non_dict_json_returns_empty(self):
        """JSON that is not a dict (e.g., a list) returns empty dict."""
        assert _parse_synergy_response("[1, 2, 3]") == {}

    def test_missing_pipe_separator_skipped(self):
        """Entries without a pipe separator are skipped."""
        raw = '{"Sol Ring - Arcane Signet": 0.3}'
        assert _parse_synergy_response(raw) == {}

    def test_empty_card_names_skipped(self):
        """Entries with empty card names after split are skipped."""
        raw = json.dumps({" | Arcane Signet": 0.3, "Sol Ring | ": 0.4})
        assert _parse_synergy_response(raw) == {}

    def test_non_numeric_scores_skipped(self):
        """Entries with non-numeric score values are skipped."""
        raw = '{"Sol Ring | Arcane Signet": "high"}'
        assert _parse_synergy_response(raw) == {}

    def test_scores_clamped_negative(self):
        """Negative scores are clamped to 0.0."""
        raw = '{"Sol Ring | Arcane Signet": -0.5}'
        result = _parse_synergy_response(raw)
        assert result[("Arcane Signet", "Sol Ring")] == 0.0

    def test_scores_clamped_above_one(self):
        """Scores above 1.0 are clamped to 1.0."""
        raw = '{"Sol Ring | Arcane Signet": 1.5}'
        result = _parse_synergy_response(raw)
        assert result[("Arcane Signet", "Sol Ring")] == 1.0

    def test_canonical_key_ordering_applied(self):
        """Keys are canonically ordered regardless of LLM response order."""
        raw = '{"Zebra | Alpha": 0.7}'
        result = _parse_synergy_response(raw)
        assert ("Alpha", "Zebra") in result
        assert result[("Alpha", "Zebra")] == 0.7

    def test_multiple_valid_entries(self):
        """Multiple valid entries are all parsed."""
        raw = json.dumps({
            "Sol Ring | Arcane Signet": 0.3,
            "Ashnod's Altar | Gravecrawler": 0.95,
        })
        result = _parse_synergy_response(raw)
        assert len(result) == 2
        assert result[("Arcane Signet", "Sol Ring")] == 0.3
        assert result[("Ashnod's Altar", "Gravecrawler")] == 0.95

    def test_integer_score_accepted(self):
        """Integer scores (0, 1) are accepted and converted to float."""
        raw = '{"Sol Ring | Arcane Signet": 1}'
        result = _parse_synergy_response(raw)
        assert result[("Arcane Signet", "Sol Ring")] == 1.0


# === _build_pair_prompt tests ===


class TestBuildPairPrompt:
    def test_commander_name_and_text_included(self):
        """Prompt includes commander name and oracle text."""
        prompt = _build_pair_prompt(
            "Korvold", "Whenever you sacrifice a permanent, draw a card.", []
        )
        assert "Commander: Korvold" in prompt
        assert "Whenever you sacrifice a permanent, draw a card." in prompt

    def test_all_pairs_included(self):
        """All card pairs appear in the prompt output."""
        card_a = _card("Sol Ring", "Tap: Add two colorless mana.")
        card_b = _card("Arcane Signet", "Tap: Add one mana.")
        card_c = _card("Mana Crypt", "Tap: Add two colorless mana.")
        pairs = [(card_a, card_b), (card_a, card_c)]
        prompt = _build_pair_prompt("Korvold", "Draw a card.", pairs)
        assert "Sol Ring" in prompt
        assert "Arcane Signet" in prompt
        assert "Mana Crypt" in prompt

    def test_cards_with_no_oracle_text_show_placeholder(self):
        """Cards with no oracle text display '(no text)'."""
        card_a = _card("Mountain")
        card_b = _card("Island")
        pairs = [(card_a, card_b)]
        prompt = _build_pair_prompt("Korvold", "Draw.", pairs)
        assert "(no text)" in prompt


# === generate_synergy_matrix tests ===


class TestGenerateSynergyMatrix:
    def test_empty_candidates_returns_empty(self):
        """No candidates produces empty matrix."""
        commander = _card("Korvold", "Draw a card.")
        provider = _fake_provider("{}")
        result = generate_synergy_matrix(commander, [], provider)
        assert result == {}
        provider.chat.assert_not_called()

    def test_single_candidate_returns_empty(self):
        """A single candidate cannot form any pairs."""
        commander = _card("Korvold", "Draw a card.")
        provider = _fake_provider("{}")
        result = generate_synergy_matrix(
            commander, [_card("Sol Ring")], provider
        )
        assert result == {}
        provider.chat.assert_not_called()

    def test_two_candidates_one_pair(self):
        """Two candidates generate exactly one pair and return the score."""
        commander = _card("Korvold", "Draw a card.")
        response = json.dumps({"Sol Ring | Arcane Signet": 0.4})
        provider = _fake_provider(response)

        cards = [_card("Sol Ring"), _card("Arcane Signet")]
        result = generate_synergy_matrix(commander, cards, provider)

        assert len(result) == 1
        assert result[("Arcane Signet", "Sol Ring")] == 0.4
        provider.chat.assert_called_once()

    def test_top_n_limits_candidates(self):
        """Only the first top_n candidates are considered."""
        commander = _card("Korvold", "Draw a card.")
        # Create 5 cards, but set top_n=3 => C(3,2)=3 pairs
        cards = [_card(f"Card {i}") for i in range(5)]
        response = json.dumps({
            "Card 0 | Card 1": 0.5,
            "Card 0 | Card 2": 0.6,
            "Card 1 | Card 2": 0.7,
        })
        provider = _fake_provider(response)

        result = generate_synergy_matrix(
            commander, cards, provider, top_n=3, batch_size=50
        )
        # Should only have pairs from first 3 cards
        assert len(result) == 3
        # Card 3 and Card 4 should not appear
        for key in result:
            for name in key:
                assert name not in ("Card 3", "Card 4")

    def test_batch_size_controls_call_grouping(self):
        """Multiple LLM calls are made when pairs exceed batch_size."""
        commander = _card("Korvold", "Draw a card.")
        # 4 cards => C(4,2)=6 pairs; batch_size=2 => 3 calls
        cards = [_card(f"Card {i}") for i in range(4)]
        response = "{}"
        provider = _fake_provider(response)

        generate_synergy_matrix(
            commander, cards, provider, top_n=4, batch_size=2
        )
        assert provider.chat.call_count == 3

    def test_llm_exception_one_batch_doesnt_block_others(self):
        """An exception in one batch still allows other batches to succeed."""
        commander = _card("Korvold", "Draw a card.")
        # 3 cards => C(3,2)=3 pairs; batch_size=1 => 3 calls
        cards = [
            _card("Alpha"),
            _card("Beta"),
            _card("Gamma"),
        ]
        responses = [
            json.dumps({"Alpha | Beta": 0.8}),
            RuntimeError("API timeout"),
            json.dumps({"Beta | Gamma": 0.6}),
        ]

        provider = MagicMock(spec=LLMProvider)
        provider.chat.side_effect = responses
        provider.is_available.return_value = True
        provider.name = "FakeProvider"

        result = generate_synergy_matrix(
            commander, cards, provider, top_n=3, batch_size=1
        )
        # First and third batches succeed, second raises
        assert len(result) == 2
        assert result[("Alpha", "Beta")] == 0.8
        assert result[("Beta", "Gamma")] == 0.6

    def test_complete_failure_returns_empty(self):
        """If every LLM call fails, return empty dict gracefully."""
        commander = _card("Korvold", "Draw a card.")
        cards = [_card("Alpha"), _card("Beta")]

        provider = MagicMock(spec=LLMProvider)
        provider.chat.side_effect = RuntimeError("Service down")
        provider.is_available.return_value = True
        provider.name = "FakeProvider"

        result = generate_synergy_matrix(commander, cards, provider)
        assert result == {}
