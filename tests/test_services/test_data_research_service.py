"""Tests for the data-driven research service (no LLM)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.combo import Combo
from mtg_deck_maker.models.edhrec_data import EdhrecCommanderData
from mtg_deck_maker.services.data_research_service import data_research_commander


def _make_commander() -> Card:
    return Card(
        id=1,
        oracle_id="atraxa-oracle",
        name="Atraxa, Praetors' Voice",
        type_line="Legendary Creature \u2014 Phyrexian Angel Horror",
        oracle_text="Flying, vigilance, deathtouch, lifelink\nAt the beginning of your end step, proliferate.",
        mana_cost="{G}{W}{U}{B}",
        cmc=4.0,
        colors=["W", "U", "B", "G"],
        color_identity=["W", "U", "B", "G"],
        keywords=["Flying", "Vigilance", "Deathtouch", "Lifelink", "Proliferate"],
        edhrec_rank=5,
        legal_commander=True,
    )


def _make_edhrec_data() -> list[EdhrecCommanderData]:
    return [
        EdhrecCommanderData(
            commander_name="Atraxa, Praetors' Voice",
            card_name="Doubling Season",
            inclusion_rate=0.85,
            num_decks=5000,
            potential_decks=6000,
        ),
        EdhrecCommanderData(
            commander_name="Atraxa, Praetors' Voice",
            card_name="Sol Ring",
            inclusion_rate=0.95,
            num_decks=5700,
            potential_decks=6000,
        ),
        EdhrecCommanderData(
            commander_name="Atraxa, Praetors' Voice",
            card_name="Arcane Signet",
            inclusion_rate=0.90,
            num_decks=5400,
            potential_decks=6000,
        ),
    ]


def _make_sol_ring() -> Card:
    return Card(
        id=10,
        oracle_id="sol-ring-oracle",
        name="Sol Ring",
        type_line="Artifact",
        oracle_text="{T}: Add {C}{C}.",
        mana_cost="{1}",
        cmc=1.0,
        colors=[],
        color_identity=[],
        keywords=[],
        edhrec_rank=1,
        legal_commander=True,
    )


def _make_win_con_card() -> Card:
    return Card(
        id=20,
        oracle_id="triumph-oracle",
        name="Triumph of the Hordes",
        type_line="Sorcery",
        oracle_text="Until end of turn, creatures you control get +1/+1 and gain trample and infect.",
        mana_cost="{2}{G}{G}",
        cmc=4.0,
        colors=["G"],
        color_identity=["G"],
        keywords=[],
        edhrec_rank=50,
        legal_commander=True,
    )


@pytest.fixture
def mock_db() -> MagicMock:
    return MagicMock()


class TestDataResearchService:
    def test_strategy_overview_with_archetype_and_themes(self, mock_db: MagicMock) -> None:
        """Strategy overview includes archetype, themes, and color identity."""
        commander = _make_commander()

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository"),
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            MockCardRepo.return_value.get_card_by_name.return_value = commander
            MockComboRepo.return_value.get_combos_for_card.return_value = []
            mock_edhrec.return_value = []

            result = data_research_commander(mock_db, "Atraxa, Praetors' Voice")

        assert result.parse_success is True
        assert "Atraxa, Praetors' Voice" in result.strategy_overview
        assert result.commander_name == "Atraxa, Praetors' Voice"

    def test_key_cards_from_edhrec(self, mock_db: MagicMock) -> None:
        """Key cards are populated from EDHREC data sorted by inclusion rate."""
        commander = _make_commander()
        edhrec_data = _make_edhrec_data()

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository") as MockPriceRepo,
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            MockCardRepo.return_value.get_card_by_name.return_value = commander
            MockPriceRepo.return_value.get_cheapest_price.return_value = None
            MockComboRepo.return_value.get_combos_for_card.return_value = []
            mock_edhrec.return_value = edhrec_data

            result = data_research_commander(mock_db, "Atraxa, Praetors' Voice")

        # Sorted by inclusion_rate descending: Sol Ring (0.95), Arcane Signet (0.90), Doubling Season (0.85)
        assert result.key_cards[0] == "Sol Ring"
        assert "Doubling Season" in result.key_cards
        assert len(result.key_cards) == 3

    def test_budget_staples_with_price_filtering(self, mock_db: MagicMock) -> None:
        """Budget staples only include cards under $5."""
        commander = _make_commander()
        sol_ring = _make_sol_ring()
        edhrec_data = _make_edhrec_data()

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository") as MockPriceRepo,
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            # Commander lookup returns commander, Sol Ring lookup returns sol_ring, others None
            def get_card_by_name(name: str) -> Card | None:
                if name == "Atraxa, Praetors' Voice":
                    return commander
                if name == "Sol Ring":
                    return sol_ring
                return None

            MockCardRepo.return_value.get_card_by_name.side_effect = get_card_by_name
            # Sol Ring costs $2, Doubling Season and Arcane Signet not found in DB
            MockPriceRepo.return_value.get_cheapest_price.return_value = 2.0
            MockComboRepo.return_value.get_combos_for_card.return_value = []
            mock_edhrec.return_value = edhrec_data

            result = data_research_commander(mock_db, "Atraxa, Praetors' Voice")

        assert "Sol Ring" in result.budget_staples

    def test_combos_from_combo_repo(self, mock_db: MagicMock) -> None:
        """Combos are fetched from ComboRepository and formatted."""
        commander = _make_commander()
        combo = Combo(
            combo_id="c1",
            card_names=["Atraxa, Praetors' Voice", "Doubling Season"],
            result="Infinite counters",
            color_identity=["W", "U", "B", "G"],
        )

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository"),
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            MockCardRepo.return_value.get_card_by_name.return_value = commander
            MockComboRepo.return_value.get_combos_for_card.return_value = [combo]
            mock_edhrec.return_value = []

            result = data_research_commander(mock_db, "Atraxa, Praetors' Voice")

        assert len(result.combos) == 1
        assert "Infinite counters" in result.combos[0]
        assert "Doubling Season" in result.combos[0]

    def test_combos_filtered_by_color_identity(self, mock_db: MagicMock) -> None:
        """Combos outside the commander's color identity are excluded."""
        commander = _make_commander()
        # This combo requires Red, which Atraxa doesn't have
        red_combo = Combo(
            combo_id="c2",
            card_names=["Atraxa, Praetors' Voice", "Red Card"],
            result="Some effect",
            color_identity=["W", "U", "B", "G", "R"],
        )

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository"),
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            MockCardRepo.return_value.get_card_by_name.return_value = commander
            MockComboRepo.return_value.get_combos_for_card.return_value = [red_combo]
            mock_edhrec.return_value = []

            result = data_research_commander(mock_db, "Atraxa, Praetors' Voice")

        assert len(result.combos) == 0

    def test_win_conditions_from_category_engine(self, mock_db: MagicMock) -> None:
        """Win conditions are identified by the category engine."""
        commander = _make_commander()
        win_card = _make_win_con_card()
        edhrec_data = [
            EdhrecCommanderData(
                commander_name="Atraxa, Praetors' Voice",
                card_name="Triumph of the Hordes",
                inclusion_rate=0.70,
                num_decks=4200,
                potential_decks=6000,
            ),
        ]

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository") as MockPriceRepo,
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            def get_card_by_name(name: str) -> Card | None:
                if name == "Atraxa, Praetors' Voice":
                    return commander
                if name == "Triumph of the Hordes":
                    return win_card
                return None

            MockCardRepo.return_value.get_card_by_name.side_effect = get_card_by_name
            MockPriceRepo.return_value.get_cheapest_price.return_value = None
            MockComboRepo.return_value.get_combos_for_card.return_value = []
            mock_edhrec.return_value = edhrec_data

            result = data_research_commander(mock_db, "Atraxa, Praetors' Voice")

        assert "Triumph of the Hordes" in result.win_conditions

    def test_category_targets_from_archetype(self, mock_db: MagicMock) -> None:
        """Category targets are populated from archetype detection."""
        commander = _make_commander()

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository"),
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            MockCardRepo.return_value.get_card_by_name.return_value = commander
            MockComboRepo.return_value.get_combos_for_card.return_value = []
            mock_edhrec.return_value = []

            result = data_research_commander(mock_db, "Atraxa, Praetors' Voice")

        assert len(result.category_targets) > 0
        assert "ramp" in result.category_targets

    def test_graceful_fallback_when_edhrec_empty(self, mock_db: MagicMock) -> None:
        """Service returns valid result even when EDHREC returns empty."""
        commander = _make_commander()

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository"),
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            MockCardRepo.return_value.get_card_by_name.return_value = commander
            MockComboRepo.return_value.get_combos_for_card.return_value = []
            mock_edhrec.return_value = []

            result = data_research_commander(mock_db, "Atraxa, Praetors' Voice")

        assert result.parse_success is True
        assert result.key_cards == []
        assert result.budget_staples == []
        assert result.win_conditions == []
        assert result.cards_to_avoid == []

    def test_commander_not_in_db(self, mock_db: MagicMock) -> None:
        """Service works when commander is not in local DB."""
        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository"),
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            MockCardRepo.return_value.get_card_by_name.return_value = None
            MockComboRepo.return_value.get_combos_for_card.return_value = []
            mock_edhrec.return_value = []

            result = data_research_commander(mock_db, "Unknown Commander")

        assert result.parse_success is True
        assert result.commander_name == "Unknown Commander"
        assert "not found in local database" in result.strategy_overview

    def test_edhrec_failure_returns_partial_result(self, mock_db: MagicMock) -> None:
        """EDHREC failure caught internally returns partial result with commander data."""
        commander = _make_commander()

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository"),
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            MockCardRepo.return_value.get_card_by_name.return_value = commander
            MockComboRepo.return_value.get_combos_for_card.return_value = []
            # Simulate EDHREC timeout
            mock_edhrec.side_effect = Exception("EDHREC timeout")

            result = data_research_commander(mock_db, "Atraxa, Praetors' Voice")

        # Function catches exception and continues with empty EDHREC data
        assert result.parse_success is True
        assert "Atraxa, Praetors' Voice" in result.strategy_overview
        assert result.key_cards == []

    def test_win_conditions_capped_at_limit(self, mock_db: MagicMock) -> None:
        """Win conditions list is capped at WIN_CONDITIONS_LIMIT (10)."""
        commander = _make_commander()

        # Create 15 EDHREC entries where each card is a win condition
        edhrec_data = []
        for i in range(15):
            edhrec_data.append(
                EdhrecCommanderData(
                    commander_name="Atraxa, Praetors' Voice",
                    card_name=f"Win Con {i}",
                    inclusion_rate=0.80 - (i * 0.01),
                    num_decks=5000,
                    potential_decks=6000,
                )
            )

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository") as MockPriceRepo,
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            def get_card_by_name(name: str) -> Card | None:
                if name == "Atraxa, Praetors' Voice":
                    return commander
                # All other cards are win conditions with "infect" in oracle text
                if name.startswith("Win Con"):
                    return Card(
                        id=100 + int(name.split()[-1]),
                        oracle_id=f"win-{name}",
                        name=name,
                        type_line="Sorcery",
                        oracle_text="Deal damage as infect.",
                        mana_cost="{2}{G}",
                        cmc=3.0,
                        colors=["G"],
                        color_identity=["G"],
                        keywords=[],
                        edhrec_rank=100,
                        legal_commander=True,
                    )
                return None

            MockCardRepo.return_value.get_card_by_name.side_effect = get_card_by_name
            MockPriceRepo.return_value.get_cheapest_price.return_value = None
            MockComboRepo.return_value.get_combos_for_card.return_value = []
            mock_edhrec.return_value = edhrec_data

            result = data_research_commander(mock_db, "Atraxa, Praetors' Voice")

        # Should be capped at 10
        assert len(result.win_conditions) <= 10

    def test_combos_skipped_when_commander_not_in_db(self, mock_db: MagicMock) -> None:
        """Combos are skipped when commander is not found (empty color identity)."""
        combo = Combo(
            combo_id="c1",
            card_names=["Unknown Commander", "Some Card"],
            result="Some effect",
            color_identity=["W", "U"],
        )

        with (
            patch("mtg_deck_maker.services.data_research_service.CardRepository") as MockCardRepo,
            patch("mtg_deck_maker.services.data_research_service.PriceRepository"),
            patch("mtg_deck_maker.services.data_research_service.ComboRepository") as MockComboRepo,
            patch("mtg_deck_maker.services.data_research_service.fetch_commander_data", new_callable=AsyncMock) as mock_edhrec,
        ):
            # Commander not found
            MockCardRepo.return_value.get_card_by_name.return_value = None
            # Combo repo has combos
            MockComboRepo.return_value.get_combos_for_card.return_value = [combo]
            mock_edhrec.return_value = []

            result = data_research_commander(mock_db, "Unknown Commander")

        # Combos should be empty because color_identity is empty (commander not found)
        assert result.combos == []
