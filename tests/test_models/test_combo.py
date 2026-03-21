"""Tests for the Combo data model."""

from __future__ import annotations

from mtg_deck_maker.models.combo import Combo


class TestComboCreation:
    """Test Combo dataclass creation and field access."""

    def test_combo_creation(self) -> None:
        combo = Combo(
            combo_id="csb-123",
            card_names=["Exquisite Blood", "Sanguine Bond"],
            result="Infinite damage, infinite lifegain",
            color_identity=["B"],
            prerequisite="Both permanents on the battlefield",
            description="Whenever you gain life, Sanguine Bond deals damage. "
            "Whenever an opponent loses life, Exquisite Blood gains you life.",
        )
        assert combo.combo_id == "csb-123"
        assert combo.card_names == ["Exquisite Blood", "Sanguine Bond"]
        assert combo.result == "Infinite damage, infinite lifegain"
        assert combo.color_identity == ["B"]
        assert combo.prerequisite == "Both permanents on the battlefield"
        assert "Sanguine Bond deals damage" in combo.description

    def test_combo_has_slots(self) -> None:
        combo = Combo(
            combo_id="csb-456",
            card_names=["Mikaeus, the Unhallowed", "Triskelion"],
            result="Infinite damage",
            color_identity=["B"],
        )
        assert hasattr(combo, "__slots__")

    def test_combo_default_fields(self) -> None:
        combo = Combo(
            combo_id="csb-789",
            card_names=["Dramatic Reversal", "Isochron Scepter"],
            result="Infinite mana",
            color_identity=["U"],
        )
        assert combo.prerequisite == ""
        assert combo.description == ""

    def test_combo_with_multiple_colors(self) -> None:
        combo = Combo(
            combo_id="csb-multi",
            card_names=["Deadeye Navigator", "Peregrine Drake"],
            result="Infinite mana",
            color_identity=["U"],
        )
        assert combo.color_identity == ["U"]
        assert len(combo.card_names) == 2

    def test_combo_many_cards(self) -> None:
        combo = Combo(
            combo_id="csb-many",
            card_names=[
                "Ashnod's Altar",
                "Nim Deathmantle",
                "Grave Titan",
            ],
            result="Infinite colorless mana, infinite tokens",
            color_identity=["B"],
        )
        assert len(combo.card_names) == 3
