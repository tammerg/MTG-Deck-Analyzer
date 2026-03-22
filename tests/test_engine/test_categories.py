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


# === Protection Detection ===


class TestProtectionDetection:
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
    def test_solemn_simulacrum(self):
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


# === Reminder Text Exclusion ===


class TestReminderTextExclusion:
    def test_reminder_text_stripped(self):
        """Oracle text in parentheses should be ignored for categorization."""
        card = _make_card(
            "Test Card",
            type_line="Creature - Human",
            oracle_text="Vigilance (This creature doesn't draw a card when attacking.)",
            mana_cost="{W}",
            cmc=1.0,
        )
        cats = categorize_card(card)
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

    def test_bulk_categorize_empty(self):
        """Bulk categorize with empty list returns empty dict."""
        results = bulk_categorize([])
        assert results == {}


# === Category Enum ===


class TestCategoryEnum:
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


# === Expanded Win Condition Detection ===


class TestExpandedWinConditions:
    def test_extra_combat_is_win_condition(self):
        """A card granting an additional combat phase is a win condition."""
        card = _make_card(
            "Aurelia, the Warleader",
            type_line="Legendary Creature - Angel",
            oracle_text="Flying, vigilance, haste\nWhenever Aurelia, the Warleader attacks for the first time each turn, untap all creatures you control. After this phase, there is an additional combat phase.",
            mana_cost="{2}{R}{R}{W}{W}",
            cmc=6.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.WIN_CONDITION.value)
        conf = _get_confidence(cats, Category.WIN_CONDITION.value)
        assert conf >= 0.7

    def test_infect_is_win_condition(self):
        """A card with infect is a win condition."""
        card = _make_card(
            "Blighted Agent",
            type_line="Creature - Phyrexian Human Rogue",
            oracle_text="Infect (This creature deals damage to creatures in the form of -1/-1 counters and to players in the form of poison counters.)\nBlighted Agent can't be blocked.",
            mana_cost="{1}{U}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.WIN_CONDITION.value)
        conf = _get_confidence(cats, Category.WIN_CONDITION.value)
        assert conf >= 0.8

    def test_opponent_loses_game_is_win_condition(self):
        """A card that causes an opponent to lose the game is a win condition."""
        card = _make_card(
            "Door to Nothingness",
            type_line="Artifact",
            oracle_text="{W}{W}{U}{U}{B}{B}{R}{R}{G}{G}, {T}, Sacrifice Door to Nothingness: Target opponent loses the game.",
            mana_cost="{5}",
            cmc=5.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.WIN_CONDITION.value)
        conf = _get_confidence(cats, Category.WIN_CONDITION.value)
        assert conf >= 0.9

    def test_removal_not_win_condition(self):
        """A removal spell should not be categorized as a win condition."""
        card = _make_card(
            "Murder",
            type_line="Instant",
            oracle_text="Destroy target creature.",
            mana_cost="{1}{B}{B}",
            cmc=3.0,
        )
        cats = categorize_card(card)
        assert not _has_category(cats, Category.WIN_CONDITION.value)


# === Expanded Pattern Detection ===


class TestExpandedPatterns:
    """Tests for expanded regex patterns covering common card archetypes.
    One representative test per sub-category.
    """

    def test_treasure_token_is_ramp(self):
        """Creating a Treasure token is ramp."""
        card = _make_card(
            "Dockside Extortionist",
            type_line="Creature - Goblin Pirate",
            oracle_text="When Dockside Extortionist enters the battlefield, create a Treasure token for each artifact and enchantment your opponents control.",
            mana_cost="{1}{R}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.RAMP.value)

    def test_mana_dork_is_ramp(self):
        """A creature with '{T}: Add {G}' is a mana dork (ramp)."""
        card = _make_card(
            "Llanowar Elves",
            type_line="Creature - Elf Druid",
            oracle_text="{T}: Add {G}.",
            mana_cost="{G}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.RAMP.value)
        assert _has_category(cats, Category.CREATURE.value)

    def test_impulsive_draw_is_card_draw(self):
        """Exiling top cards with 'you may play them' is impulsive draw."""
        card = _make_card(
            "Light Up the Stage",
            type_line="Sorcery",
            oracle_text="Exile the top two cards of your library. Until the end of your next turn, you may play those cards.",
            mana_cost="{2}{R}",
            cmc=3.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.CARD_DRAW.value)

    def test_scry_is_card_draw_low_confidence(self):
        """Scry is card selection categorized as card_draw with low confidence."""
        card = _make_card(
            "Opt",
            type_line="Instant",
            oracle_text="Scry 2.",
            mana_cost="{U}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.CARD_DRAW.value)
        conf = _get_confidence(cats, Category.CARD_DRAW.value)
        assert conf <= 0.6

    def test_fights_is_removal(self):
        """'Target creature you control fights target creature' is removal."""
        card = _make_card(
            "Prey Upon",
            type_line="Sorcery",
            oracle_text="Target creature you control fights target creature you don't control.",
            mana_cost="{G}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.REMOVAL.value)

    def test_bounce_is_removal(self):
        """'Return target creature to its owner's hand' is soft removal."""
        card = _make_card(
            "Unsummon",
            type_line="Instant",
            oracle_text="Return target creature to its owner's hand.",
            mana_cost="{U}",
            cmc=1.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.REMOVAL.value)
        conf = _get_confidence(cats, Category.REMOVAL.value)
        assert conf <= 0.7

    def test_ward_is_protection(self):
        """Cards with ward keyword provide protection."""
        card = _make_card(
            "Ledger Shredder Ward",
            type_line="Creature - Bird",
            oracle_text="Flying\nWard {2}",
            mana_cost="{1}{U}",
            cmc=2.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.PROTECTION.value)

    def test_each_player_sacrifices_is_board_wipe(self):
        """'Each player sacrifices' is a pseudo-board-wipe."""
        card = _make_card(
            "Cataclysm",
            type_line="Sorcery",
            oracle_text="Each player chooses from among the permanents they control an artifact, a creature, an enchantment, and a land, then sacrifices the rest.",
            mana_cost="{2}{W}{W}",
            cmc=4.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.BOARD_WIPE.value)

    def test_damage_each_creature_is_board_wipe(self):
        """'Deals 3 damage to each creature' is a damage-based board wipe."""
        card = _make_card(
            "Anger of the Gods",
            type_line="Sorcery",
            oracle_text="Anger of the Gods deals 3 damage to each creature.",
            mana_cost="{1}{R}{R}",
            cmc=3.0,
        )
        cats = categorize_card(card)
        assert _has_category(cats, Category.BOARD_WIPE.value)
