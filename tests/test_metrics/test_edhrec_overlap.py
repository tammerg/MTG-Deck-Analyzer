"""Tests for the EDHREC overlap metric module."""

from __future__ import annotations

from mtg_deck_maker.metrics.edhrec_overlap import (
    EDHRECOverlapResult,
    edhrec_overlap,
)
from mtg_deck_maker.models.deck import Deck, DeckCard


def _make_deck(
    card_names: list[str],
    *,
    commander_names: list[str] | None = None,
    companion_names: list[str] | None = None,
    land_names: list[str] | None = None,
) -> Deck:
    """Helper to build a Deck with named cards."""
    cards: list[DeckCard] = []
    card_id = 1
    for name in (commander_names or []):
        cards.append(
            DeckCard(card_id=card_id, card_name=name, is_commander=True)
        )
        card_id += 1
    for name in (companion_names or []):
        cards.append(
            DeckCard(card_id=card_id, card_name=name, is_companion=True)
        )
        card_id += 1
    for name in (land_names or []):
        cards.append(
            DeckCard(card_id=card_id, card_name=name, category="land")
        )
        card_id += 1
    for name in card_names:
        cards.append(DeckCard(card_id=card_id, card_name=name))
        card_id += 1
    return Deck(name="Test Deck", cards=cards)


class TestEDHRECOverlapResult:
    """Verify the result dataclass shape."""

    def test_fields(self) -> None:
        result = EDHRECOverlapResult(
            overlap_pct=0.5,
            weighted_overlap=0.6,
            matched_cards=3,
            total_cards=6,
            missing_from_edhrec=["Card A"],
            top_missing_edhrec=["Card B"],
        )
        assert result.overlap_pct == 0.5
        assert result.weighted_overlap == 0.6
        assert result.matched_cards == 3
        assert result.total_cards == 6
        assert result.missing_from_edhrec == ["Card A"]
        assert result.top_missing_edhrec == ["Card B"]


class TestPerfectOverlap:
    """All deck cards appear in EDHREC data."""

    def test_all_cards_present(self) -> None:
        deck = _make_deck(["Sol Ring", "Arcane Signet", "Command Tower"])
        edhrec = {
            "Sol Ring": 0.95,
            "Arcane Signet": 0.80,
            "Command Tower": 0.70,
        }
        # Command Tower is not a land here (no category set)
        result = edhrec_overlap(deck, edhrec)
        assert result.overlap_pct == 1.0
        assert result.matched_cards == 3
        assert result.total_cards == 3
        assert result.missing_from_edhrec == []

    def test_weighted_overlap_is_average_inclusion(self) -> None:
        deck = _make_deck(["Sol Ring", "Arcane Signet"])
        edhrec = {"Sol Ring": 0.90, "Arcane Signet": 0.60}
        result = edhrec_overlap(deck, edhrec)
        assert result.weighted_overlap == (0.90 + 0.60) / 2


class TestZeroOverlap:
    """No deck cards appear in EDHREC data."""

    def test_no_cards_match(self) -> None:
        deck = _make_deck(["Weird Janky Card", "Another Jank"])
        edhrec = {"Sol Ring": 0.95, "Arcane Signet": 0.80}
        result = edhrec_overlap(deck, edhrec)
        assert result.overlap_pct == 0.0
        assert result.weighted_overlap == 0.0
        assert result.matched_cards == 0
        assert result.total_cards == 2
        assert sorted(result.missing_from_edhrec) == [
            "Another Jank",
            "Weird Janky Card",
        ]


class TestPartialOverlap:
    """Some deck cards appear in EDHREC data."""

    def test_half_overlap(self) -> None:
        deck = _make_deck(["Sol Ring", "Arcane Signet", "Jank A", "Jank B"])
        edhrec = {"Sol Ring": 0.95, "Arcane Signet": 0.80}
        result = edhrec_overlap(deck, edhrec)
        assert result.overlap_pct == 0.5
        assert result.matched_cards == 2
        assert result.total_cards == 4
        assert sorted(result.missing_from_edhrec) == ["Jank A", "Jank B"]


class TestEmptyEDHRECData:
    """EDHREC inclusion dict is empty."""

    def test_empty_edhrec(self) -> None:
        deck = _make_deck(["Sol Ring", "Arcane Signet"])
        result = edhrec_overlap(deck, {})
        assert result.overlap_pct == 0.0
        assert result.weighted_overlap == 0.0
        assert result.matched_cards == 0
        assert result.total_cards == 2
        assert sorted(result.missing_from_edhrec) == [
            "Arcane Signet",
            "Sol Ring",
        ]
        assert result.top_missing_edhrec == []


class TestEmptyDeck:
    """Deck has no eligible cards."""

    def test_no_mainboard_cards(self) -> None:
        deck = _make_deck(
            [],
            commander_names=["Atraxa"],
            land_names=["Command Tower"],
        )
        edhrec = {"Sol Ring": 0.95}
        result = edhrec_overlap(deck, edhrec)
        assert result.overlap_pct == 0.0
        assert result.weighted_overlap == 0.0
        assert result.matched_cards == 0
        assert result.total_cards == 0
        assert result.missing_from_edhrec == []

    def test_completely_empty_deck(self) -> None:
        deck = Deck(name="Empty")
        result = edhrec_overlap(deck, {"Sol Ring": 0.95})
        assert result.overlap_pct == 0.0
        assert result.total_cards == 0


class TestExclusions:
    """Commanders, companions, and lands are excluded."""

    def test_commander_excluded(self) -> None:
        deck = _make_deck(
            ["Sol Ring"],
            commander_names=["Atraxa"],
        )
        edhrec = {"Atraxa": 1.0, "Sol Ring": 0.95}
        result = edhrec_overlap(deck, edhrec)
        # Only Sol Ring counted, Atraxa excluded
        assert result.total_cards == 1
        assert result.matched_cards == 1

    def test_companion_excluded(self) -> None:
        deck = _make_deck(
            ["Sol Ring"],
            companion_names=["Lurrus"],
        )
        edhrec = {"Lurrus": 1.0, "Sol Ring": 0.95}
        result = edhrec_overlap(deck, edhrec)
        assert result.total_cards == 1
        assert result.matched_cards == 1

    def test_lands_excluded(self) -> None:
        deck = _make_deck(
            ["Sol Ring"],
            land_names=["Command Tower", "Island"],
        )
        edhrec = {
            "Command Tower": 0.90,
            "Island": 0.50,
            "Sol Ring": 0.95,
        }
        result = edhrec_overlap(deck, edhrec)
        assert result.total_cards == 1
        assert result.matched_cards == 1


class TestCaseInsensitiveMatching:
    """Card name matching should be case-insensitive."""

    def test_lowercase_edhrec_key(self) -> None:
        deck = _make_deck(["Sol Ring"])
        edhrec = {"sol ring": 0.95}
        result = edhrec_overlap(deck, edhrec)
        assert result.matched_cards == 1
        assert result.overlap_pct == 1.0

    def test_mixed_case(self) -> None:
        deck = _make_deck(["sol ring", "ARCANE SIGNET"])
        edhrec = {"Sol Ring": 0.95, "Arcane Signet": 0.80}
        result = edhrec_overlap(deck, edhrec)
        assert result.matched_cards == 2
        assert result.overlap_pct == 1.0

    def test_missing_from_edhrec_preserves_deck_name(self) -> None:
        """missing_from_edhrec should use the card name as it appears in the deck."""
        deck = _make_deck(["My Jank Card"])
        result = edhrec_overlap(deck, {})
        assert result.missing_from_edhrec == ["My Jank Card"]


class TestTopMissingEDHREC:
    """top_missing_edhrec shows highest-inclusion EDHREC cards not in deck."""

    def test_top_5_returned(self) -> None:
        deck = _make_deck(["Sol Ring"])
        edhrec = {
            "Sol Ring": 0.95,
            "Arcane Signet": 0.85,
            "Swords to Plowshares": 0.80,
            "Beast Within": 0.70,
            "Counterspell": 0.65,
            "Lightning Greaves": 0.60,
            "Swiftfoot Boots": 0.55,
        }
        result = edhrec_overlap(deck, edhrec)
        assert len(result.top_missing_edhrec) == 5
        # Should be sorted by inclusion rate descending
        assert result.top_missing_edhrec == [
            "Arcane Signet",
            "Swords to Plowshares",
            "Beast Within",
            "Counterspell",
            "Lightning Greaves",
        ]

    def test_fewer_than_5_missing(self) -> None:
        deck = _make_deck(["Sol Ring"])
        edhrec = {"Sol Ring": 0.95, "Arcane Signet": 0.85}
        result = edhrec_overlap(deck, edhrec)
        assert result.top_missing_edhrec == ["Arcane Signet"]

    def test_all_edhrec_cards_in_deck(self) -> None:
        deck = _make_deck(["Sol Ring", "Arcane Signet"])
        edhrec = {"Sol Ring": 0.95, "Arcane Signet": 0.85}
        result = edhrec_overlap(deck, edhrec)
        assert result.top_missing_edhrec == []

    def test_case_insensitive_exclusion(self) -> None:
        """Cards in deck (case-insensitive) should not appear in top_missing."""
        deck = _make_deck(["sol ring"])
        edhrec = {"Sol Ring": 0.95, "Arcane Signet": 0.85}
        result = edhrec_overlap(deck, edhrec)
        # Sol Ring is in deck (case-insensitive), so only Arcane Signet missing
        assert result.top_missing_edhrec == ["Arcane Signet"]
