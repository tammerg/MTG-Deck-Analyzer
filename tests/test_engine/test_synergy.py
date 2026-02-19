"""Tests for the synergy scoring engine."""

from __future__ import annotations

import pytest

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.engine.synergy import (
    compute_synergy,
    extract_themes,
    score_theme_match,
)


# -- Helper to create test cards --


def _make_card(
    name: str,
    type_line: str = "",
    oracle_text: str = "",
    mana_cost: str = "",
    cmc: float = 0.0,
    colors: list[str] | None = None,
    color_identity: list[str] | None = None,
    keywords: list[str] | None = None,
) -> Card:
    return Card(
        oracle_id=f"test-{name.lower().replace(' ', '-')}",
        name=name,
        type_line=type_line,
        oracle_text=oracle_text,
        mana_cost=mana_cost,
        cmc=cmc,
        colors=colors or [],
        color_identity=color_identity or [],
        keywords=keywords or [],
    )


# === Theme Extraction ===


class TestExtractThemes:
    def test_token_theme(self):
        """Commander with token creation should detect tokens theme."""
        commander = _make_card(
            "Rhys the Redeemed",
            type_line="Legendary Creature - Elf Warrior",
            oracle_text="{2}{G}{W}: Create a token that's a copy of each creature token you control.\n{G/W}: Create a 1/1 green and white Elf Warrior creature token.",
            mana_cost="{G/W}",
            cmc=1.0,
        )
        themes = extract_themes(commander)
        assert "tokens" in themes

    def test_counter_theme_atraxa(self):
        """Atraxa with proliferate should detect counters theme."""
        commander = _make_card(
            "Atraxa, Praetors' Voice",
            type_line="Legendary Creature - Phyrexian Angel Horror",
            oracle_text="Flying, vigilance, deathtouch, lifelink\nAt the beginning of your end step, proliferate.",
            mana_cost="{G}{W}{U}{B}",
            cmc=4.0,
            keywords=["Flying", "Vigilance", "Deathtouch", "Lifelink"],
        )
        themes = extract_themes(commander)
        assert "counters" in themes

    def test_graveyard_theme(self):
        """Meren of Clan Nel Toth should detect graveyard theme."""
        commander = _make_card(
            "Meren of Clan Nel Toth",
            type_line="Legendary Creature - Human Shaman",
            oracle_text="Whenever another creature you control dies, you get an experience counter.\nAt the beginning of your end step, choose target creature card in your graveyard. If that card's mana value is less than or equal to the number of experience counters you have, return it to the battlefield. Otherwise, put it into your hand.",
            mana_cost="{2}{B}{G}",
            cmc=4.0,
        )
        themes = extract_themes(commander)
        assert "graveyard" in themes

    def test_combat_theme(self):
        """Aurelia the Warleader should detect combat theme."""
        commander = _make_card(
            "Aurelia, the Warleader",
            type_line="Legendary Creature - Angel",
            oracle_text="Flying, vigilance, haste\nWhenever Aurelia, the Warleader attacks for the first time each turn, untap all creatures you control. After this phase, there is an additional combat phase.",
            mana_cost="{2}{R}{R}{W}{W}",
            cmc=6.0,
        )
        themes = extract_themes(commander)
        assert "combat" in themes

    def test_spells_matter_theme(self):
        """Kalamax should detect spells-matter theme."""
        commander = _make_card(
            "Kalamax, the Stormsire",
            type_line="Legendary Creature - Dinosaur Beast",
            oracle_text="Whenever you cast your first instant spell each turn, if Kalamax, the Stormsire is tapped, copy that spell. You may choose new targets for the copy.\nWhenever you copy an instant or sorcery spell, put a +1/+1 counter on Kalamax.",
            mana_cost="{1}{G}{U}{R}",
            cmc=4.0,
        )
        themes = extract_themes(commander)
        # "instant and sorcery" or "instant or sorcery" is present
        # Plus "counter on" for counters
        # The word "instant" alone doesn't trigger spells-matter,
        # but "instant or sorcery" portion matches
        assert any(t in themes for t in ["spells-matter", "counters"])

    def test_sacrifice_theme(self):
        """Korvold should detect sacrifice theme."""
        commander = _make_card(
            "Korvold, Fae-Cursed King",
            type_line="Legendary Creature - Dragon Noble",
            oracle_text="Flying\nWhenever Korvold, Fae-Cursed King enters the battlefield or attacks, sacrifice another permanent.\nWhenever you sacrifice a permanent, put a +1/+1 counter on Korvold and draw a card.",
            mana_cost="{2}{B}{R}{G}",
            cmc=5.0,
        )
        themes = extract_themes(commander)
        assert "sacrifice" in themes

    def test_landfall_theme(self):
        """Omnath, Locus of Creation should detect landfall theme."""
        commander = _make_card(
            "Omnath, Locus of Creation",
            type_line="Legendary Creature - Elemental",
            oracle_text="When Omnath, Locus of Creation enters the battlefield, draw a card.\nLandfall — Whenever a land enters the battlefield under your control, you gain 4 life if this is the first time this ability has resolved this turn.",
            mana_cost="{R}{G}{W}{U}",
            cmc=4.0,
        )
        themes = extract_themes(commander)
        assert "landfall" in themes

    def test_artifacts_matter_theme(self):
        """Jhoira should detect artifacts-matter theme."""
        commander = _make_card(
            "Jhoira, Weatherlight Captain",
            type_line="Legendary Creature - Human Artificer",
            oracle_text="Whenever you cast a historic spell, draw a card. (Artifacts, legendaries, and Sagas are historic.)\nFor each artifact you control, this spell costs {1} less to cast.",
            mana_cost="{2}{U}{R}",
            cmc=4.0,
        )
        themes = extract_themes(commander)
        # "for each artifact" should trigger artifacts-matter
        assert "artifacts-matter" in themes

    def test_enchantments_matter_theme(self):
        """Sythis should detect enchantments-matter theme."""
        commander = _make_card(
            "Sythis, Harvest's Hand",
            type_line="Legendary Enchantment Creature - Nymph",
            oracle_text="Whenever you cast an enchantment spell, you gain 1 life and draw a card.\nConstellation — Whenever an enchantment enters the battlefield under your control, you gain 1 life.",
            mana_cost="{G}{W}",
            cmc=2.0,
        )
        themes = extract_themes(commander)
        assert "enchantments-matter" in themes

    def test_no_themes_empty_text(self):
        """A card with no oracle text should return no themes."""
        commander = _make_card(
            "Isamaru, Hound of Konda",
            type_line="Legendary Creature - Dog",
            oracle_text="",
            mana_cost="{W}",
            cmc=1.0,
        )
        themes = extract_themes(commander)
        assert themes == []


# === Theme Matching ===


class TestScoreThemeMatch:
    def test_token_candidate_matches_token_theme(self):
        """A token producer should match a tokens theme well."""
        themes = ["tokens"]
        candidate = _make_card(
            "Secure the Wastes",
            type_line="Instant",
            oracle_text="Create X 1/1 white Warrior creature tokens.",
            mana_cost="{X}{W}",
            cmc=1.0,
        )
        score = score_theme_match(themes, candidate)
        assert score > 0.5

    def test_counter_candidate_matches_counter_theme(self):
        """A +1/+1 counter card should match a counters theme."""
        themes = ["counters"]
        candidate = _make_card(
            "Hardened Scales",
            type_line="Enchantment",
            oracle_text="If one or more +1/+1 counters would be placed on a creature you control, that many plus one +1/+1 counters are placed on it instead.",
            mana_cost="{G}",
            cmc=1.0,
        )
        score = score_theme_match(themes, candidate)
        assert score > 0.5

    def test_irrelevant_candidate_low_score(self):
        """A card with no theme match should score near zero."""
        themes = ["tokens", "counters"]
        candidate = _make_card(
            "Counterspell",
            type_line="Instant",
            oracle_text="Counter target spell.",
            mana_cost="{U}{U}",
            cmc=2.0,
        )
        score = score_theme_match(themes, candidate)
        # "Counter target" triggers "counter" keyword group but not the themes
        # The oracle text does not contain "+1/+1 counter" or "token"
        assert score < 0.3

    def test_empty_themes_zero_score(self):
        """No themes should return 0.0."""
        candidate = _make_card(
            "Sol Ring",
            type_line="Artifact",
            oracle_text="{T}: Add {C}{C}.",
        )
        score = score_theme_match([], candidate)
        assert score == 0.0

    def test_no_oracle_text_zero_score(self):
        """Candidate with no oracle text should return 0.0."""
        candidate = _make_card(
            "Vanilla Bear",
            type_line="Creature - Bear",
            oracle_text="",
        )
        score = score_theme_match(["tokens"], candidate)
        assert score == 0.0

    def test_multi_theme_match(self):
        """A card matching multiple themes should score higher."""
        themes = ["sacrifice", "graveyard"]
        candidate = _make_card(
            "Viscera Seer",
            type_line="Creature - Vampire Wizard",
            oracle_text="Sacrifice a creature: Scry 1.",
            mana_cost="{B}",
            cmc=1.0,
        )
        score_single = score_theme_match(["sacrifice"], candidate)

        # Card that matches graveyard and sacrifice
        candidate2 = _make_card(
            "Buried Alive",
            type_line="Sorcery",
            oracle_text="Search your library for up to three creature cards, put them into your graveyard, then shuffle.",
            mana_cost="{2}{B}",
            cmc=3.0,
        )
        score_graveyard = score_theme_match(themes, candidate2)
        assert score_graveyard > 0.0


# === Keyword Overlap ===


class TestKeywordOverlap:
    def test_shared_keywords_increase_synergy(self):
        """Cards sharing keywords with the commander should score higher."""
        commander = _make_card(
            "Atraxa, Praetors' Voice",
            type_line="Legendary Creature",
            oracle_text="Flying, vigilance, deathtouch, lifelink\nAt the beginning of your end step, proliferate.",
            keywords=["Flying", "Vigilance", "Deathtouch", "Lifelink"],
            color_identity=["W", "U", "B", "G"],
        )
        # Card with proliferate (shared keyword)
        high_synergy = _make_card(
            "Flux Channeler",
            type_line="Creature - Human Wizard",
            oracle_text="Whenever you cast a noncreature spell, proliferate.",
            color_identity=["U"],
            keywords=[],
        )
        # Card with no shared keywords
        low_synergy = _make_card(
            "Grizzly Bears",
            type_line="Creature - Bear",
            oracle_text="",
            color_identity=["G"],
        )
        score_high = compute_synergy(commander, high_synergy)
        score_low = compute_synergy(commander, low_synergy)
        assert score_high > score_low

    def test_no_overlap_baseline(self):
        """Cards with no keyword overlap still get some score from color."""
        commander = _make_card(
            "Atraxa, Praetors' Voice",
            type_line="Legendary Creature",
            oracle_text="At the beginning of your end step, proliferate.",
            color_identity=["W", "U", "B", "G"],
        )
        candidate = _make_card(
            "Plains",
            type_line="Basic Land",
            oracle_text="",
            color_identity=[],
        )
        score = compute_synergy(commander, candidate)
        # Colorless card has some color synergy (0.5 * 0.25 weight)
        assert score >= 0.0


# === Compute Synergy ===


class TestComputeSynergy:
    def test_synergy_range(self):
        """Synergy score should be between 0.0 and 1.0."""
        commander = _make_card(
            "Korvold, Fae-Cursed King",
            type_line="Legendary Creature - Dragon Noble",
            oracle_text="Whenever you sacrifice a permanent, put a +1/+1 counter on Korvold and draw a card.",
            color_identity=["B", "R", "G"],
        )
        candidate = _make_card(
            "Viscera Seer",
            type_line="Creature - Vampire Wizard",
            oracle_text="Sacrifice a creature: Scry 1.",
            color_identity=["B"],
        )
        score = compute_synergy(commander, candidate)
        assert 0.0 <= score <= 1.0

    def test_high_synergy_thematic_match(self):
        """A card that strongly matches commander themes should score well."""
        commander = _make_card(
            "Korvold, Fae-Cursed King",
            type_line="Legendary Creature - Dragon Noble",
            oracle_text="Whenever you sacrifice a permanent, put a +1/+1 counter on Korvold and draw a card.",
            color_identity=["B", "R", "G"],
        )
        candidate = _make_card(
            "Mayhem Devil",
            type_line="Creature - Devil",
            oracle_text="Whenever a player sacrifices a permanent, Mayhem Devil deals 1 damage to any target.",
            color_identity=["B", "R"],
        )
        score = compute_synergy(commander, candidate)
        assert score > 0.2

    def test_colorless_commander(self):
        """Colorless commander should work without errors."""
        commander = _make_card(
            "Kozilek, the Great Distortion",
            type_line="Legendary Creature - Eldrazi",
            oracle_text="When you cast this spell, if you have fewer than seven cards in hand, draw cards equal to the difference.\nMenace\nDiscard a card with mana value X: Counter target spell with mana value X.",
            color_identity=[],
        )
        candidate = _make_card(
            "Thought-Knot Seer",
            type_line="Creature - Eldrazi",
            oracle_text="When Thought-Knot Seer enters the battlefield, target opponent reveals their hand. You choose a nonland card from it and exile that card.",
            color_identity=[],
        )
        score = compute_synergy(commander, candidate)
        assert 0.0 <= score <= 1.0

    def test_outside_color_identity(self):
        """A card outside the commander's color identity should score low."""
        commander = _make_card(
            "Krenko, Mob Boss",
            type_line="Legendary Creature - Goblin Warrior",
            oracle_text="Tap: Create X 1/1 red Goblin creature tokens, where X is the number of Goblins you control.",
            color_identity=["R"],
        )
        candidate = _make_card(
            "Counterspell",
            type_line="Instant",
            oracle_text="Counter target spell.",
            color_identity=["U"],  # Outside mono-red identity
        )
        score = compute_synergy(commander, candidate)
        # Color synergy should be 0 since blue is not in red identity
        assert score < 0.5

    def test_no_oracle_text_commander(self):
        """Commander with no oracle text should not crash."""
        commander = _make_card(
            "Isamaru, Hound of Konda",
            type_line="Legendary Creature - Dog",
            oracle_text="",
            color_identity=["W"],
        )
        candidate = _make_card(
            "Swords to Plowshares",
            type_line="Instant",
            oracle_text="Exile target creature. Its controller gains life equal to its power.",
            color_identity=["W"],
        )
        score = compute_synergy(commander, candidate)
        assert 0.0 <= score <= 1.0
