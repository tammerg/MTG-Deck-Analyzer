"""Tests for the Card data model."""

from __future__ import annotations

from mtg_deck_maker.models.card import Card


class TestCardCreation:
    """Test Card dataclass creation and field access."""

    def test_create_card_with_all_fields(self, sample_card: Card) -> None:
        assert sample_card.name == "Sol Ring"
        assert sample_card.oracle_id == "9b4cf4ef-0ea4-43f4-b529-9c5de5c3b22c"
        assert sample_card.type_line == "Artifact"
        assert sample_card.cmc == 1.0
        assert sample_card.legal_commander is True
        assert sample_card.legal_brawl is False

    def test_create_card_with_defaults(self) -> None:
        card = Card(oracle_id="test-id", name="Test Card")
        assert card.type_line == ""
        assert card.oracle_text == ""
        assert card.mana_cost == ""
        assert card.cmc == 0.0
        assert card.colors == []
        assert card.color_identity == []
        assert card.keywords == []
        assert card.edhrec_rank is None
        assert card.legal_commander is False
        assert card.legal_brawl is False
        assert card.updated_at == ""
        assert card.id is None

    def test_create_multicolor_card(self, sample_commander_card: Card) -> None:
        assert sample_commander_card.colors == ["W", "U", "B", "G"]
        assert sample_commander_card.color_identity == ["W", "U", "B", "G"]
        assert sample_commander_card.cmc == 4.0


class TestCardProperties:
    """Test Card computed properties."""

    def test_colors_str_empty(self, sample_card: Card) -> None:
        assert sample_card.colors_str == ""

    def test_colors_str_multicolor(self, sample_commander_card: Card) -> None:
        assert sample_commander_card.colors_str == "W,U,B,G"

    def test_color_identity_str_empty(self, sample_card: Card) -> None:
        assert sample_card.color_identity_str == ""

    def test_color_identity_str_multicolor(
        self, sample_commander_card: Card
    ) -> None:
        assert sample_commander_card.color_identity_str == "W,U,B,G"

    def test_keywords_str(self, sample_commander_card: Card) -> None:
        assert (
            sample_commander_card.keywords_str
            == "Flying,Vigilance,Deathtouch,Lifelink"
        )

    def test_keywords_str_empty(self, sample_card: Card) -> None:
        assert sample_card.keywords_str == ""

    def test_is_colorless(self, sample_card: Card) -> None:
        assert sample_card.is_colorless is True

    def test_is_not_colorless(self, sample_commander_card: Card) -> None:
        assert sample_commander_card.is_colorless is False

    def test_is_land(self) -> None:
        card = Card(
            oracle_id="land-id", name="Island", type_line="Basic Land - Island"
        )
        assert card.is_land is True

    def test_is_not_land(self, sample_card: Card) -> None:
        assert sample_card.is_land is False

    def test_is_creature(self, sample_commander_card: Card) -> None:
        assert sample_commander_card.is_creature is True

    def test_is_not_creature(self, sample_card: Card) -> None:
        assert sample_card.is_creature is False


class TestCardSerialization:
    """Test Card to/from database row conversion."""

    def test_to_db_row(self, sample_card: Card) -> None:
        row = sample_card.to_db_row()
        assert row["oracle_id"] == "9b4cf4ef-0ea4-43f4-b529-9c5de5c3b22c"
        assert row["name"] == "Sol Ring"
        assert row["type_line"] == "Artifact"
        assert row["mana_cost"] == "{1}"
        assert row["cmc"] == 1.0
        assert row["colors"] == ""
        assert row["color_identity"] == ""
        assert row["keywords"] == ""
        assert row["legal_commander"] == 1
        assert row["legal_brawl"] == 0

    def test_to_db_row_multicolor(self, sample_commander_card: Card) -> None:
        row = sample_commander_card.to_db_row()
        assert row["colors"] == "W,U,B,G"
        assert row["color_identity"] == "W,U,B,G"
        assert row["keywords"] == "Flying,Vigilance,Deathtouch,Lifelink"
        assert row["legal_commander"] == 1
        assert row["legal_brawl"] == 1

    def test_from_db_row(self) -> None:
        row = {
            "id": 42,
            "oracle_id": "test-oracle",
            "name": "Test Card",
            "type_line": "Creature",
            "oracle_text": "Some text",
            "mana_cost": "{1}{W}",
            "cmc": 2.0,
            "colors": "W",
            "color_identity": "W",
            "keywords": "Flying,Vigilance",
            "edhrec_rank": 100,
            "legal_commander": 1,
            "legal_brawl": 0,
            "updated_at": "2026-01-01",
        }
        card = Card.from_db_row(row)
        assert card.id == 42
        assert card.oracle_id == "test-oracle"
        assert card.name == "Test Card"
        assert card.colors == ["W"]
        assert card.color_identity == ["W"]
        assert card.keywords == ["Flying", "Vigilance"]
        assert card.legal_commander is True
        assert card.legal_brawl is False

    def test_from_db_row_empty_fields(self) -> None:
        row = {
            "id": 1,
            "oracle_id": "empty-test",
            "name": "Empty Card",
            "type_line": "",
            "oracle_text": "",
            "mana_cost": "",
            "cmc": 0.0,
            "colors": "",
            "color_identity": "",
            "keywords": "",
            "edhrec_rank": None,
            "legal_commander": 0,
            "legal_brawl": 0,
            "updated_at": "",
        }
        card = Card.from_db_row(row)
        assert card.colors == []
        assert card.color_identity == []
        assert card.keywords == []
        assert card.edhrec_rank is None

