"""Tests for the EdhrecCommanderData data model."""

from __future__ import annotations

from mtg_deck_maker.models.edhrec_data import EdhrecCommanderData


class TestEdhrecDataCreation:
    """Tests for creating EdhrecCommanderData instances."""

    def test_edhrec_data_creation(self) -> None:
        """EdhrecCommanderData should store all required fields."""
        data = EdhrecCommanderData(
            commander_name="Atraxa, Praetors' Voice",
            card_name="Doubling Season",
            inclusion_rate=0.45,
            num_decks=9000,
            potential_decks=20000,
            synergy_score=0.12,
        )
        assert data.commander_name == "Atraxa, Praetors' Voice"
        assert data.card_name == "Doubling Season"
        assert data.inclusion_rate == 0.45
        assert data.num_decks == 9000
        assert data.potential_decks == 20000
        assert data.synergy_score == 0.12

    def test_edhrec_data_has_slots(self) -> None:
        """EdhrecCommanderData should use __slots__ for memory efficiency."""
        data = EdhrecCommanderData(
            commander_name="Test",
            card_name="Test Card",
            inclusion_rate=0.5,
            num_decks=100,
            potential_decks=200,
        )
        assert hasattr(data, "__slots__") or hasattr(
            data.__class__, "__dataclass_fields__"
        )
        # slots=True means no __dict__
        assert not hasattr(data, "__dict__")

    def test_edhrec_data_defaults(self) -> None:
        """synergy_score should default to 0.0."""
        data = EdhrecCommanderData(
            commander_name="Test Commander",
            card_name="Test Card",
            inclusion_rate=0.3,
            num_decks=50,
            potential_decks=200,
        )
        assert data.synergy_score == 0.0
