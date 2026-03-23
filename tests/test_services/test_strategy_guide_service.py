"""Tests for the strategy guide service."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.deck import Deck, DeckCard
from mtg_deck_maker.models.strategy_guide import StrategyGuide
from mtg_deck_maker.services.strategy_guide_service import StrategyGuideService


def _make_card(name: str, card_id: int, **kwargs) -> Card:
    defaults = {
        "oracle_id": f"test-{name.lower().replace(' ', '-')}",
        "name": name,
        "type_line": "Creature — Human",
        "oracle_text": "",
        "mana_cost": "{2}{W}",
        "cmc": 3.0,
        "colors": ["W"],
        "color_identity": ["W"],
        "keywords": [],
        "id": card_id,
    }
    defaults.update(kwargs)
    return Card(**defaults)


def _make_deck(deck_id: int = 1) -> Deck:
    """Build a minimal deck with commander + 99."""
    cards = [
        DeckCard(card_id=0, quantity=1, category="commander",
                 is_commander=True, card_name="Test Commander", cmc=4.0),
    ]
    for i in range(1, 37):
        cards.append(DeckCard(card_id=i, quantity=1, category="land",
                              card_name=f"Land{i}", cmc=0.0))
    for i in range(37, 100):
        cards.append(DeckCard(card_id=i, quantity=1, category="creature",
                              card_name=f"Creature{i}", cmc=3.0))
    return Deck(name="Test Deck", cards=cards, id=deck_id)


def _build_card_lookup(deck: Deck) -> dict[int, Card]:
    """Map card_id -> Card for all cards in deck."""
    lookup: dict[int, Card] = {}
    for dc in deck.cards:
        if dc.is_commander:
            lookup[dc.card_id] = _make_card(
                dc.card_name, dc.card_id,
                type_line="Legendary Creature — Human Wizard",
                oracle_text="Whenever you cast an instant or sorcery, draw a card.",
                cmc=4.0, colors=["U", "R"], color_identity=["U", "R"],
            )
        elif dc.card_name.startswith("Land"):
            lookup[dc.card_id] = _make_card(
                dc.card_name, dc.card_id,
                type_line="Basic Land — Plains", oracle_text="",
                mana_cost="", cmc=0.0, colors=[], color_identity=[],
            )
        else:
            lookup[dc.card_id] = _make_card(dc.card_name, dc.card_id)
    return lookup


class TestStrategyGuideService:
    def _setup_mocks(self, deck: Deck | None = None):
        """Return mocked db, deck_repo, card_repo, combo_repo."""
        if deck is None:
            deck = _make_deck()
        card_lookup = _build_card_lookup(deck)

        mock_db = MagicMock()
        mock_deck_repo = MagicMock()
        mock_deck_repo.get_deck.return_value = deck

        mock_card_repo = MagicMock()
        mock_card_repo.get_card_by_id.side_effect = lambda cid: card_lookup.get(cid)

        mock_combo_repo = MagicMock()
        mock_combo_repo.get_combos_for_cards.return_value = []

        return mock_db, mock_deck_repo, mock_card_repo, mock_combo_repo

    def test_generates_guide_successfully(self):
        mock_db, mock_deck_repo, mock_card_repo, mock_combo_repo = self._setup_mocks()

        with (
            patch("mtg_deck_maker.services.strategy_guide_service.DeckRepository", return_value=mock_deck_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.CardRepository", return_value=mock_card_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.ComboRepository", return_value=mock_combo_repo),
        ):
            service = StrategyGuideService()
            guide = service.generate(1, mock_db, num_sims=50)

        assert isinstance(guide, StrategyGuide)
        assert guide.archetype != ""
        assert guide.hand_simulation is not None
        assert len(guide.game_phases) == 3

    def test_deck_not_found_raises(self):
        mock_db = MagicMock()
        mock_deck_repo = MagicMock()
        mock_deck_repo.get_deck.return_value = None

        with (
            patch("mtg_deck_maker.services.strategy_guide_service.DeckRepository", return_value=mock_deck_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.CardRepository"),
            patch("mtg_deck_maker.services.strategy_guide_service.ComboRepository"),
        ):
            service = StrategyGuideService()
            try:
                service.generate(999, mock_db)
                assert False, "Should have raised ValueError"
            except ValueError as exc:
                assert "999" in str(exc)

    def test_llm_enrichment_called(self):
        mock_db, mock_deck_repo, mock_card_repo, mock_combo_repo = self._setup_mocks()
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "This is a great deck."

        with (
            patch("mtg_deck_maker.services.strategy_guide_service.DeckRepository", return_value=mock_deck_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.CardRepository", return_value=mock_card_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.ComboRepository", return_value=mock_combo_repo),
        ):
            service = StrategyGuideService()
            guide = service.generate(1, mock_db, llm_provider=mock_llm, num_sims=50)

        assert guide.llm_narrative == "This is a great deck."
        mock_llm.chat.assert_called_once()

    def test_llm_failure_graceful(self):
        mock_db, mock_deck_repo, mock_card_repo, mock_combo_repo = self._setup_mocks()
        mock_llm = MagicMock()
        mock_llm.chat.side_effect = RuntimeError("LLM unavailable")

        with (
            patch("mtg_deck_maker.services.strategy_guide_service.DeckRepository", return_value=mock_deck_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.CardRepository", return_value=mock_card_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.ComboRepository", return_value=mock_combo_repo),
        ):
            service = StrategyGuideService()
            guide = service.generate(1, mock_db, llm_provider=mock_llm, num_sims=50)

        # Should still return a guide, just without narrative
        assert isinstance(guide, StrategyGuide)
        assert guide.llm_narrative is None

    def test_without_llm_provider(self):
        mock_db, mock_deck_repo, mock_card_repo, mock_combo_repo = self._setup_mocks()

        with (
            patch("mtg_deck_maker.services.strategy_guide_service.DeckRepository", return_value=mock_deck_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.CardRepository", return_value=mock_card_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.ComboRepository", return_value=mock_combo_repo),
        ):
            service = StrategyGuideService()
            guide = service.generate(1, mock_db, llm_provider=None, num_sims=50)

        assert guide.llm_narrative is None

    def test_narrative_uses_system_role_message(self):
        """LLM call must include a system role message for the persona."""
        mock_db, mock_deck_repo, mock_card_repo, mock_combo_repo = self._setup_mocks()
        mock_llm = MagicMock()
        mock_llm.chat.return_value = "Narrative text."

        with (
            patch("mtg_deck_maker.services.strategy_guide_service.DeckRepository", return_value=mock_deck_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.CardRepository", return_value=mock_card_repo),
            patch("mtg_deck_maker.services.strategy_guide_service.ComboRepository", return_value=mock_combo_repo),
        ):
            service = StrategyGuideService()
            service.generate(1, mock_db, llm_provider=mock_llm, num_sims=50)

        messages = mock_llm.chat.call_args[0][0]  # first positional arg is messages list
        roles = [m["role"] for m in messages]
        assert "system" in roles, "LLM call must include a 'system' role message"
        assert "user" in roles, "LLM call must include a 'user' role message"

        system_msgs = [m for m in messages if m["role"] == "system"]
        user_msgs = [m for m in messages if m["role"] == "user"]
        # Persona/instructions belong in system; the deck context in user
        assert len(system_msgs) == 1
        assert len(user_msgs) == 1
        # The system message should describe the analyst persona
        assert "analyst" in system_msgs[0]["content"].lower() or "magic" in system_msgs[0]["content"].lower()
        # The user message should contain the deck analysis context
        assert "archetype" in user_msgs[0]["content"].lower() or "win" in user_msgs[0]["content"].lower()
