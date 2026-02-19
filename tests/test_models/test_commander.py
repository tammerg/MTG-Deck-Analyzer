"""Tests for the Commander data model."""

from __future__ import annotations

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.commander import Commander


class TestSoloCommander:
    """Test solo commander configuration."""

    def test_solo_commander_color_identity(
        self, sample_commander_card: Card
    ) -> None:
        cmdr = Commander(primary=sample_commander_card)
        identity = cmdr.combined_color_identity()
        assert identity == ["W", "U", "B", "G"]

    def test_solo_commander_deck_size(
        self, sample_commander_card: Card
    ) -> None:
        cmdr = Commander(primary=sample_commander_card)
        assert cmdr.deck_size() == 99

    def test_solo_commander_total_deck_size(
        self, sample_commander_card: Card
    ) -> None:
        cmdr = Commander(primary=sample_commander_card)
        assert cmdr.total_deck_size() == 100

    def test_solo_commander_validate_valid(
        self, sample_commander_card: Card
    ) -> None:
        cmdr = Commander(primary=sample_commander_card)
        errors = cmdr.validate()
        assert errors == []

    def test_solo_commander_not_legal(self) -> None:
        card = Card(
            oracle_id="illegal",
            name="Banned Card",
            type_line="Legendary Creature",
            legal_commander=False,
        )
        cmdr = Commander(primary=card)
        errors = cmdr.validate()
        assert any("not legal as a commander" in e for e in errors)

    def test_solo_commander_not_legendary(self) -> None:
        card = Card(
            oracle_id="not-legend",
            name="Random Creature",
            type_line="Creature - Human",
            legal_commander=True,
        )
        cmdr = Commander(primary=card)
        errors = cmdr.validate()
        assert any("not a legendary card" in e for e in errors)

    def test_solo_colorless_commander(self) -> None:
        card = Card(
            oracle_id="colorless-cmdr",
            name="Kozilek, the Great Distortion",
            type_line="Legendary Creature - Eldrazi",
            color_identity=[],
            legal_commander=True,
        )
        cmdr = Commander(primary=card)
        assert cmdr.combined_color_identity() == []
        assert cmdr.deck_size() == 99

    def test_all_commander_cards_solo(
        self, sample_commander_card: Card
    ) -> None:
        cmdr = Commander(primary=sample_commander_card)
        cards = cmdr.all_commander_cards()
        assert len(cards) == 1
        assert cards[0].name == "Atraxa, Praetors' Voice"


class TestPartnerCommanders:
    """Test partner commander configuration."""

    def test_partner_combined_color_identity(
        self, sample_partner_a: Card, sample_partner_b: Card
    ) -> None:
        cmdr = Commander(primary=sample_partner_a, partner=sample_partner_b)
        identity = cmdr.combined_color_identity()
        # Thrasios (U,G) + Tymna (W,B) = W,U,B,G
        assert identity == ["W", "U", "B", "G"]

    def test_partner_deck_size(
        self, sample_partner_a: Card, sample_partner_b: Card
    ) -> None:
        cmdr = Commander(primary=sample_partner_a, partner=sample_partner_b)
        assert cmdr.deck_size() == 98

    def test_partner_validate_valid(
        self, sample_partner_a: Card, sample_partner_b: Card
    ) -> None:
        cmdr = Commander(primary=sample_partner_a, partner=sample_partner_b)
        errors = cmdr.validate()
        assert errors == []

    def test_partner_missing_keyword(
        self, sample_partner_a: Card
    ) -> None:
        no_partner = Card(
            oracle_id="no-partner",
            name="Not a Partner",
            type_line="Legendary Creature",
            color_identity=["R"],
            keywords=[],
            legal_commander=True,
        )
        cmdr = Commander(primary=sample_partner_a, partner=no_partner)
        errors = cmdr.validate()
        assert any("Partner keyword" in e for e in errors)

    def test_partner_primary_missing_keyword(
        self, sample_partner_b: Card
    ) -> None:
        no_partner = Card(
            oracle_id="no-partner-primary",
            name="Not a Partner Primary",
            type_line="Legendary Creature",
            color_identity=["R"],
            keywords=[],
            legal_commander=True,
        )
        cmdr = Commander(primary=no_partner, partner=sample_partner_b)
        errors = cmdr.validate()
        assert any("Partner keyword" in e for e in errors)

    def test_all_commander_cards_partner(
        self, sample_partner_a: Card, sample_partner_b: Card
    ) -> None:
        cmdr = Commander(primary=sample_partner_a, partner=sample_partner_b)
        cards = cmdr.all_commander_cards()
        assert len(cards) == 2


class TestBackgroundCommander:
    """Test Choose a Background commander configuration."""

    def test_background_combined_identity(
        self, sample_background_commander: Card, sample_background: Card
    ) -> None:
        cmdr = Commander(
            primary=sample_background_commander,
            background=sample_background,
        )
        identity = cmdr.combined_color_identity()
        # Both are green
        assert identity == ["G"]

    def test_background_deck_size(
        self, sample_background_commander: Card, sample_background: Card
    ) -> None:
        cmdr = Commander(
            primary=sample_background_commander,
            background=sample_background,
        )
        assert cmdr.deck_size() == 98

    def test_background_validate_valid(
        self, sample_background_commander: Card, sample_background: Card
    ) -> None:
        cmdr = Commander(
            primary=sample_background_commander,
            background=sample_background,
        )
        errors = cmdr.validate()
        assert errors == []

    def test_background_missing_choose_keyword(
        self, sample_commander_card: Card, sample_background: Card
    ) -> None:
        # Atraxa doesn't have "Choose a Background"
        cmdr = Commander(
            primary=sample_commander_card,
            background=sample_background,
        )
        errors = cmdr.validate()
        assert any("Choose a Background" in e for e in errors)

    def test_background_not_a_background(
        self, sample_background_commander: Card
    ) -> None:
        not_bg = Card(
            oracle_id="not-bg",
            name="Not a Background",
            type_line="Enchantment",
            color_identity=["R"],
            legal_commander=True,
        )
        cmdr = Commander(
            primary=sample_background_commander,
            background=not_bg,
        )
        errors = cmdr.validate()
        assert any("not a Background enchantment" in e for e in errors)

    def test_all_commander_cards_background(
        self, sample_background_commander: Card, sample_background: Card
    ) -> None:
        cmdr = Commander(
            primary=sample_background_commander,
            background=sample_background,
        )
        cards = cmdr.all_commander_cards()
        assert len(cards) == 2


class TestCompanionCommander:
    """Test commander with companion configuration."""

    def test_companion_valid(
        self, sample_commander_card: Card, sample_companion: Card
    ) -> None:
        # Atraxa has W,U,B,G. Keruga has U,G. Keruga is within identity.
        cmdr = Commander(
            primary=sample_commander_card,
            companion=sample_companion,
        )
        errors = cmdr.validate()
        assert errors == []

    def test_companion_outside_identity(self) -> None:
        mono_white = Card(
            oracle_id="mono-w",
            name="Mono White Commander",
            type_line="Legendary Creature",
            color_identity=["W"],
            keywords=[],
            legal_commander=True,
        )
        ug_companion = Card(
            oracle_id="ug-comp",
            name="UG Companion",
            type_line="Legendary Creature",
            color_identity=["U", "G"],
            keywords=["Companion"],
            legal_commander=True,
        )
        cmdr = Commander(primary=mono_white, companion=ug_companion)
        errors = cmdr.validate()
        assert any("outside the commander's color identity" in e for e in errors)

    def test_companion_missing_keyword(
        self, sample_commander_card: Card
    ) -> None:
        not_companion = Card(
            oracle_id="not-comp",
            name="Not a Companion",
            type_line="Legendary Creature",
            color_identity=["U"],
            keywords=[],
            legal_commander=True,
        )
        cmdr = Commander(
            primary=sample_commander_card,
            companion=not_companion,
        )
        errors = cmdr.validate()
        assert any("Companion keyword" in e for e in errors)


class TestPartnerAndBackgroundConflict:
    """Test that partner and background cannot coexist."""

    def test_partner_and_background_error(
        self,
        sample_partner_a: Card,
        sample_partner_b: Card,
        sample_background: Card,
    ) -> None:
        cmdr = Commander(
            primary=sample_partner_a,
            partner=sample_partner_b,
            background=sample_background,
        )
        errors = cmdr.validate()
        assert any("both a partner and a background" in e for e in errors)
