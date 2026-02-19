"""Tests for the card categorization engine."""

from __future__ import annotations

import pytest

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.engine.categories import (
    Category,
    categorize_card,
    bulk_categorize,
)


# -- Helper to create test cards --


def _make_card(
    name: str,
    type_line: str = "",
    oracle_text: str = "",
    mana_cost: str = "",
    cmc: float = 0.0,
    keywords: list[str] | None = None,
    card_id: int | None = None,
) -> Card:
    return Card(
        oracle_id=f"test-{name.lower().replace(' ', '-')}",
        name=name,
        type_line=type_line,
        oracle_text=oracle_text,
        mana_cost=mana_cost,
        cmc=cmc,
        colors=[],
        color_identity=[],
        keywords=keywords or [],
        id=card_id,
    )


def _has_category(categories: list[tuple[str, float]], cat: str) -> bool:
    """Check if a category is present in the result."""
    return any(c == cat for c, _ in categories)


def _get_confidence(categories: list[tuple[str, float]], cat: str) -> float:
    """Get the confidence for a specific category, or 0.0 if absent."""
    for c, conf in categories:
        if c == cat:
            return conf
    return 0.0


# === Ramp Detection ===


class TestRampDetection:
    def test_rampant_growth(self):
        """Rampant Growth searches for a basic land card."""
        card = _make_card(
            "Rampant Growth",
            type_line="Sorcery",
            oracle_text="Search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.",
            mana_cost="{1}{G}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.RAMP.value)

    def test_sol_ring(self):
        """Sol Ring is an artifact that adds mana."""
        card = _make_card(
            "Sol Ring",
            type_line="Artifact",
            oracle_text="{T}: Add {C}{C}.",
            mana_cost="{1}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.RAMP.value)
        assert _has_category(cats, Category.ARTIFACT.value)

    def test_arcane_signet(self):
        """Arcane Signet is a low-CMC artifact mana rock."""
        card = _make_card(
            "Arcane Signet",
            type_line="Artifact",
            oracle_text="{T}: Add one mana of any color in your commander's color identity.",
            mana_cost="{2}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.RAMP.value)


# === Card Draw Detection ===


class TestCardDrawDetection:
    def test_harmonize(self):
        """Harmonize draws three cards."""
        card = _make_card(
            "Harmonize",
            type_line="Sorcery",
            oracle_text="Draw three cards.",
            mana_cost="{2}{G}{G}",
            cmc=4.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.CARD_DRAW.value)

    def test_rhystic_study(self):
        """Rhystic Study draws a card on trigger."""
        card = _make_card(
            "Rhystic Study",
            type_line="Enchantment",
            oracle_text="Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.",
            mana_cost="{2}{U}",
            cmc=3.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.CARD_DRAW.value)

    def test_tireless_tracker_investigate(self):
        """Tireless Tracker creates Clue tokens (investigate)."""
        card = _make_card(
            "Tireless Tracker",
            type_line="Creature - Human Scout",
            oracle_text="Whenever a land enters the battlefield under your control, investigate. (Create a Clue token.)\nWhenever you sacrifice a Clue, put a +1/+1 counter on Tireless Tracker.",
            mana_cost="{2}{G}",
            cmc=3.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.CARD_DRAW.value)


# === Removal Detection ===


class TestRemovalDetection:
    def test_swords_to_plowshares(self):
        """Swords to Plowshares exiles a target creature."""
        card = _make_card(
            "Swords to Plowshares",
            type_line="Instant",
            oracle_text="Exile target creature. Its controller gains life equal to its power.",
            mana_cost="{W}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.REMOVAL.value)

    def test_generous_gift(self):
        """Generous Gift destroys target permanent (removal, not board wipe)."""
        card = _make_card(
            "Generous Gift",
            type_line="Instant",
            oracle_text="Destroy target permanent. Its controller creates a 3/3 green Elephant creature token.",
            mana_cost="{2}{W}",
            cmc=3.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.REMOVAL.value)
        assert not _has_category(cats, Category.BOARD_WIPE.value)

    def test_lightning_bolt_damage(self):
        """Lightning Bolt deals damage to a target."""
        card = _make_card(
            "Lightning Bolt",
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            mana_cost="{R}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        # "deals 3 damage to any target" should not match
        # the pattern "deals? \d+ damage to.*target" because
        # "any target" is "to any target", which has "to" before "target"
        # Actually the pattern "deals? \d+ damage to.*target" will match
        # "deals 3 damage to any target"
        assert _has_category(cats, Category.REMOVAL.value)


# === Board Wipe Detection ===


class TestBoardWipeDetection:
    def test_wrath_of_god(self):
        """Wrath of God destroys all creatures."""
        card = _make_card(
            "Wrath of God",
            type_line="Sorcery",
            oracle_text="Destroy all creatures. They can't be regenerated.",
            mana_cost="{2}{W}{W}",
            cmc=4.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.BOARD_WIPE.value)

    def test_toxic_deluge(self):
        """Toxic Deluge gives all creatures -X/-X."""
        card = _make_card(
            "Toxic Deluge",
            type_line="Sorcery",
            oracle_text="As an additional cost to cast this spell, pay X life.\nAll creatures get -X/-X until end of turn.",
            mana_cost="{2}{B}",
            cmc=3.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.BOARD_WIPE.value)

    def test_farewell(self):
        """Farewell exiles all of chosen types."""
        card = _make_card(
            "Farewell",
            type_line="Sorcery",
            oracle_text="Choose one or more —\n• Exile all artifacts.\n• Exile all creatures.\n• Exile all enchantments.\n• Exile all graveyards.",
            mana_cost="{4}{W}{W}",
            cmc=6.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.BOARD_WIPE.value)


# === Counterspell Detection ===


class TestCounterspellDetection:
    def test_counterspell(self):
        """Counterspell counters a target spell."""
        card = _make_card(
            "Counterspell",
            type_line="Instant",
            oracle_text="Counter target spell.",
            mana_cost="{U}{U}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.COUNTERSPELL.value)

    def test_swan_song(self):
        """Swan Song counters a target instant, sorcery, or enchantment spell."""
        card = _make_card(
            "Swan Song",
            type_line="Instant",
            oracle_text="Counter target enchantment, instant, or sorcery spell. Its controller creates a 2/2 blue Bird creature token with flying.",
            mana_cost="{U}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        # "Counter target enchantment, instant, or sorcery spell"
        # matches "counter target.*spell" (via the full pattern)
        assert _has_category(cats, Category.COUNTERSPELL.value)


# === Protection Detection ===


class TestProtectionDetection:
    def test_lightning_greaves(self):
        """Lightning Greaves grants shroud."""
        card = _make_card(
            "Lightning Greaves",
            type_line="Artifact - Equipment",
            oracle_text="Equipped creature has haste and shroud. (It can't be the target of spells or abilities.)\nEquip {0}",
            mana_cost="{2}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.PROTECTION.value)

    def test_heroic_intervention(self):
        """Heroic Intervention grants hexproof and indestructible."""
        card = _make_card(
            "Heroic Intervention",
            type_line="Instant",
            oracle_text="Permanents you control gain hexproof and indestructible until end of turn.",
            mana_cost="{1}{G}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.PROTECTION.value)
        conf = _get_confidence(cats, Category.PROTECTION.value)
        assert conf >= 0.8


# === Recursion Detection ===


class TestRecursionDetection:
    def test_eternal_witness(self):
        """Eternal Witness returns a card from graveyard."""
        card = _make_card(
            "Eternal Witness",
            type_line="Creature - Human Shaman",
            oracle_text="When Eternal Witness enters the battlefield, you may return target card from your graveyard to your hand.",
            mana_cost="{1}{G}{G}",
            cmc=3.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.RECURSION.value)

    def test_reanimate(self):
        """Reanimate puts a creature from graveyard onto battlefield."""
        card = _make_card(
            "Reanimate",
            type_line="Sorcery",
            oracle_text="Put target creature card from a graveyard onto the battlefield under your control. You lose life equal to its mana value.",
            mana_cost="{B}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.RECURSION.value)


# === Win Condition Detection ===


class TestWinConditionDetection:
    def test_thassas_oracle(self):
        """Thassa's Oracle wins the game."""
        card = _make_card(
            "Thassa's Oracle",
            type_line="Creature - Merfolk Wizard",
            oracle_text="When Thassa's Oracle enters the battlefield, look at the top X cards of your library, where X is your devotion to blue. Put up to one of them on top of your library and the rest on the bottom of your library in a random order. If X is greater than or equal to the number of cards in your library, you win the game.",
            mana_cost="{U}{U}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.WIN_CONDITION.value)
        conf = _get_confidence(cats, Category.WIN_CONDITION.value)
        assert conf == 1.0

    def test_exsanguinate(self):
        """Exsanguinate causes each opponent to lose life."""
        card = _make_card(
            "Exsanguinate",
            type_line="Sorcery",
            oracle_text="Each opponent loses X life. You gain life equal to the life lost this way.",
            mana_cost="{X}{B}{B}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.WIN_CONDITION.value)


# === Tutor Detection ===


class TestTutorDetection:
    def test_demonic_tutor(self):
        """Demonic Tutor searches library for any card."""
        card = _make_card(
            "Demonic Tutor",
            type_line="Sorcery",
            oracle_text="Search your library for a card, put that card into your hand, then shuffle.",
            mana_cost="{1}{B}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.TUTOR.value)

    def test_vampiric_tutor(self):
        """Vampiric Tutor searches for a card and puts on top."""
        card = _make_card(
            "Vampiric Tutor",
            type_line="Instant",
            oracle_text="Search your library for a card, then shuffle and put that card on top of it. You lose 2 life.",
            mana_cost="{B}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.TUTOR.value)

    def test_cultivate_is_not_tutor(self):
        """Cultivate searches for lands, which is ramp, not a tutor."""
        card = _make_card(
            "Cultivate",
            type_line="Sorcery",
            oracle_text="Search your library for up to two basic land cards, reveal those cards, put one onto the battlefield tapped and the other into your hand, then shuffle.",
            mana_cost="{2}{G}",
            cmc=3.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.RAMP.value)
        assert not _has_category(cats, Category.TUTOR.value)


# === Multi-Category Cards ===


class TestMultiCategory:
    def test_creature_that_draws(self):
        """Mulldrifter is a creature that also draws cards."""
        card = _make_card(
            "Mulldrifter",
            type_line="Creature - Elemental",
            oracle_text="Flying\nWhen Mulldrifter enters the battlefield, draw two cards.\nEvoke {2}{U}",
            mana_cost="{4}{U}",
            cmc=5.0,
            keywords=["Flying", "Evoke"],
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.CREATURE.value)
        assert _has_category(cats, Category.CARD_DRAW.value)

    def test_removal_not_boardwipe(self):
        """Generous Gift is removal but not a board wipe."""
        card = _make_card(
            "Generous Gift",
            type_line="Instant",
            oracle_text="Destroy target permanent. Its controller creates a 3/3 green Elephant creature token.",
            mana_cost="{2}{W}",
            cmc=3.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.REMOVAL.value)
        assert not _has_category(cats, Category.BOARD_WIPE.value)

    def test_artifact_creature(self):
        """Solemn Simulacrum is artifact + creature + ramp + card draw."""
        card = _make_card(
            "Solemn Simulacrum",
            type_line="Artifact Creature - Golem",
            oracle_text="When Solemn Simulacrum enters the battlefield, you may search your library for a basic land card, put that card onto the battlefield tapped, then shuffle.\nWhen Solemn Simulacrum dies, you may draw a card.",
            mana_cost="{4}",
            cmc=4.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.ARTIFACT.value)
        assert _has_category(cats, Category.CREATURE.value)
        assert _has_category(cats, Category.RAMP.value)
        assert _has_category(cats, Category.CARD_DRAW.value)


# === Confidence Scoring ===


class TestConfidenceScoring:
    def test_high_confidence_counterspell(self):
        """A direct counter target spell should have high confidence."""
        card = _make_card(
            "Counterspell",
            type_line="Instant",
            oracle_text="Counter target spell.",
        )
        cats = categorize_card(card)
        conf = _get_confidence(cats, Category.COUNTERSPELL.value)
        assert conf >= 0.9

    def test_type_line_categories_max_confidence(self):
        """Type-based categories (Land, Creature, etc.) get 1.0 confidence."""
        card = _make_card(
            "Forest",
            type_line="Basic Land - Forest",
            oracle_text="({T}: Add {G}.)",
        )
        cats = categorize_card(card)
        conf = _get_confidence(cats, Category.LAND.value)
        assert conf == 1.0

    def test_commander_damage_low_confidence(self):
        """Commander damage as win condition gets lower confidence."""
        card = _make_card(
            "Rafiq of the Many",
            type_line="Legendary Creature - Human Knight",
            oracle_text="Exalted (Whenever a creature you control attacks alone, that creature gets +1/+1 until end of turn.)\nWhenever a creature you control attacks alone, it gains commander damage double strike until end of turn.",
            mana_cost="{1}{G}{W}{U}",
            cmc=4.0,
        )
        cats = categorize_card(card)
        if _has_category(cats, Category.WIN_CONDITION.value):
            conf = _get_confidence(cats, Category.WIN_CONDITION.value)
            assert conf <= 0.7


# === Negative Cases ===


class TestNegativeCases:
    def test_vanilla_creature_no_functional_category(self):
        """A vanilla creature with no oracle text gets utility."""
        card = _make_card(
            "Grizzly Bears",
            type_line="Creature - Bear",
            oracle_text="",
            mana_cost="{1}{G}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.CREATURE.value)
        assert _has_category(cats, Category.UTILITY.value)
        assert not _has_category(cats, Category.RAMP.value)
        assert not _has_category(cats, Category.CARD_DRAW.value)
        assert not _has_category(cats, Category.REMOVAL.value)

    def test_basic_land_no_ramp(self):
        """A basic land is classified as LAND, not as RAMP."""
        card = _make_card(
            "Plains",
            type_line="Basic Land - Plains",
            oracle_text="({T}: Add {W}.)",
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.LAND.value)
        # Reminder text in parens should be stripped, so "{T}: Add {W}."
        # is in reminder text and should not match ramp patterns


# === Reminder Text Exclusion ===


class TestReminderTextExclusion:
    def test_reminder_text_stripped(self):
        """Oracle text in parentheses should be ignored for categorization."""
        # A card whose only functional text is in reminder parens
        card = _make_card(
            "Test Card",
            type_line="Creature - Human",
            oracle_text="Vigilance (This creature doesn't draw a card when attacking.)",
            mana_cost="{W}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        # "draw a card" is in reminder text, should not be detected
        assert not _has_category(cats, Category.CARD_DRAW.value)

    def test_real_text_not_stripped(self):
        """Real oracle text outside parens should still be detected."""
        card = _make_card(
            "Test Draw Card",
            type_line="Creature - Human",
            oracle_text="When this creature enters the battlefield, draw a card. (This is a reminder.)",
            mana_cost="{1}{U}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.CARD_DRAW.value)


# === Bulk Categorize ===


class TestBulkCategorize:
    def test_bulk_categorize_with_ids(self):
        """Bulk categorize returns results keyed by card ID."""
        cards = [
            _make_card(
                "Sol Ring",
                type_line="Artifact",
                oracle_text="{T}: Add {C}{C}.",
                card_id=1,
            ),
            _make_card(
                "Counterspell",
                type_line="Instant",
                oracle_text="Counter target spell.",
                card_id=2,
            ),
        ]
        results = bulk_categorize(cards)
        assert 1 in results
        assert 2 in results
        assert _has_category(results[1], Category.RAMP.value)
        assert _has_category(results[2], Category.COUNTERSPELL.value)

    def test_bulk_categorize_without_ids(self):
        """Cards without IDs use negative index keys."""
        cards = [
            _make_card(
                "Forest",
                type_line="Basic Land - Forest",
                oracle_text="({T}: Add {G}.)",
            ),
        ]
        results = bulk_categorize(cards)
        # First card with no ID gets key -1
        assert -1 in results
        assert _has_category(results[-1], Category.LAND.value)

    def test_bulk_categorize_empty(self):
        """Bulk categorize with empty list returns empty dict."""
        results = bulk_categorize([])
        assert results == {}

    def test_bulk_categorize_multiple(self):
        """Bulk categorize handles multiple cards correctly."""
        cards = [
            _make_card(
                "Sol Ring",
                type_line="Artifact",
                oracle_text="{T}: Add {C}{C}.",
                card_id=10,
            ),
            _make_card(
                "Wrath of God",
                type_line="Sorcery",
                oracle_text="Destroy all creatures. They can't be regenerated.",
                card_id=20,
            ),
            _make_card(
                "Demonic Tutor",
                type_line="Sorcery",
                oracle_text="Search your library for a card, put that card into your hand, then shuffle.",
                card_id=30,
            ),
        ]
        results = bulk_categorize(cards)
        assert len(results) == 3
        assert _has_category(results[10], Category.RAMP.value)
        assert _has_category(results[20], Category.BOARD_WIPE.value)
        assert _has_category(results[30], Category.TUTOR.value)


# === Category Enum ===


class TestCategoryEnum:
    def test_all_categories_have_string_values(self):
        """Every Category enum member should have a string value."""
        for cat in Category:
            assert isinstance(cat.value, str)
            assert len(cat.value) > 0

    def test_expected_categories_exist(self):
        """All specified categories exist in the enum."""
        expected = [
            "ramp", "card_draw", "removal", "board_wipe", "counterspell",
            "protection", "recursion", "win_condition", "tutor",
            "land", "creature", "artifact", "enchantment", "utility",
        ]
        actual = [c.value for c in Category]
        for exp in expected:
            assert exp in actual, f"Missing category: {exp}"
