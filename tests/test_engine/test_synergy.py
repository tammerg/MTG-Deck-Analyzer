"""Tests for the synergy scoring engine."""

from __future__ import annotations

import pytest

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.engine.synergy import (
    _compute_tribal_synergy,
    _extract_creature_types,
    compute_combo_synergy,
    compute_package_score,
    compute_pairwise_synergy,
    compute_synergy,
    extract_themes,
    find_synergy_packages,
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
    @pytest.mark.parametrize(
        "themes, card_name, type_line, oracle_text, min_score, max_score",
        [
            (
                ["tokens"],
                "Secure the Wastes",
                "Instant",
                "Create X 1/1 white Warrior creature tokens.",
                0.5, 1.0,
            ),
            (
                ["counters"],
                "Hardened Scales",
                "Enchantment",
                "If one or more +1/+1 counters would be placed on a creature you control, that many plus one +1/+1 counters are placed on it instead.",
                0.5, 1.0,
            ),
            (
                ["tokens", "counters"],
                "Counterspell",
                "Instant",
                "Counter target spell.",
                0.0, 0.3,
            ),
            (
                [],
                "Sol Ring",
                "Artifact",
                "{T}: Add {C}{C}.",
                0.0, 0.0,
            ),
        ],
        ids=["token_match", "counter_match", "irrelevant_low", "empty_themes"],
    )
    def test_score_theme_match(self, themes, card_name, type_line, oracle_text, min_score, max_score):
        candidate = _make_card(card_name, type_line=type_line, oracle_text=oracle_text)
        score = score_theme_match(themes, candidate)
        assert min_score <= score <= max_score


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
        high_synergy = _make_card(
            "Flux Channeler",
            type_line="Creature - Human Wizard",
            oracle_text="Whenever you cast a noncreature spell, proliferate.",
            color_identity=["U"],
            keywords=[],
        )
        low_synergy = _make_card(
            "Grizzly Bears",
            type_line="Creature - Bear",
            oracle_text="",
            color_identity=["G"],
        )
        score_high = compute_synergy(commander, high_synergy)
        score_low = compute_synergy(commander, low_synergy)
        assert score_high > score_low


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
            color_identity=["U"],
        )
        score = compute_synergy(commander, candidate)
        assert score < 0.5

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


# === Tribal Synergy ===


class TestTribalSynergy:
    def test_extract_creature_types_basic(self):
        """'Creature - Zombie Wizard' should extract {'Zombie', 'Wizard'}."""
        card = _make_card("Zombie Wizard", type_line="Creature \u2014 Zombie Wizard")
        result = _extract_creature_types(card)
        assert result == {"Zombie", "Wizard"}

    def test_extract_creature_types_no_dash(self):
        """'Instant' should return an empty set."""
        card = _make_card("Lightning Bolt", type_line="Instant")
        result = _extract_creature_types(card)
        assert result == set()

    def test_tribal_synergy_shared_type(self):
        """Zombie commander + Zombie candidate should produce a high score."""
        commander = _make_card(
            "Zombie Lord",
            type_line="Legendary Creature \u2014 Zombie",
            oracle_text="Other Zombies you control get +1/+1.",
            color_identity=["B"],
        )
        candidate = _make_card(
            "Zombie Knight",
            type_line="Creature \u2014 Zombie Knight",
            color_identity=["B"],
        )
        score = _compute_tribal_synergy(commander, candidate)
        assert score >= 0.5

    def test_tribal_synergy_no_shared_type(self):
        """Zombie commander + Elf candidate should return 0.0."""
        commander = _make_card(
            "Zombie Lord",
            type_line="Legendary Creature \u2014 Zombie",
            oracle_text="Other Zombies you control get +1/+1.",
            color_identity=["B"],
        )
        candidate = _make_card(
            "Elf Scout",
            type_line="Creature \u2014 Elf Scout",
            color_identity=["G"],
        )
        score = _compute_tribal_synergy(commander, candidate)
        assert score == 0.0


# === Combo Synergy ===


class TestComboSynergy:
    def test_combo_synergy_with_partner_in_deck(self):
        """A card with a combo partner already in the deck should score high."""
        combo_partners = {
            "Exquisite Blood": ["Sanguine Bond", "Vito, Thorn of the Dusk Rose"],
            "Sanguine Bond": ["Exquisite Blood"],
        }
        deck_card_names = {"Sanguine Bond", "Sol Ring", "Swamp"}
        score = compute_combo_synergy(
            "Exquisite Blood", deck_card_names, combo_partners
        )
        assert score >= 0.8
        assert score <= 1.0

    def test_combo_synergy_no_partners(self):
        """A card with no combo partners at all should score 0.0."""
        combo_partners: dict[str, list[str]] = {}
        deck_card_names = {"Sol Ring", "Swamp"}
        score = compute_combo_synergy(
            "Lightning Bolt", deck_card_names, combo_partners
        )
        assert score == 0.0

    def test_combo_synergy_partner_in_pool(self):
        """A card with combo partners known but none in deck should score moderate."""
        combo_partners = {
            "Exquisite Blood": ["Sanguine Bond", "Vito, Thorn of the Dusk Rose"],
        }
        deck_card_names = {"Sol Ring", "Swamp"}
        score = compute_combo_synergy(
            "Exquisite Blood", deck_card_names, combo_partners
        )
        assert score >= 0.3
        assert score <= 0.5


# === Pairwise Synergy ===



class TestComputePairwiseSynergy:
    def test_keyword_overlap_component(self):
        """Two cards sharing 'sacrifice' keyword should have nonzero synergy."""
        card_a = _make_card(
            "Viscera Seer",
            type_line="Creature \u2014 Vampire Wizard",
            oracle_text="Sacrifice a creature: Scry 1.",
            color_identity=["B"],
        )
        card_b = _make_card(
            "Carrion Feeder",
            type_line="Creature \u2014 Zombie",
            oracle_text="Sacrifice a creature: Put a +1/+1 counter on Carrion Feeder.",
            color_identity=["B"],
        )
        score = compute_pairwise_synergy(card_a, card_b)
        assert score > 0.0

    def test_theme_co_support(self):
        """Two cards both matching 'tokens' theme should score well."""
        card_a = _make_card(
            "Secure the Wastes",
            type_line="Instant",
            oracle_text="Create X 1/1 white Warrior creature tokens.",
            color_identity=["W"],
        )
        card_b = _make_card(
            "Anointed Procession",
            type_line="Enchantment",
            oracle_text="If an effect would create one or more tokens under your control, it creates twice that many of those tokens instead.",
            color_identity=["W"],
        )
        score = compute_pairwise_synergy(card_a, card_b)
        assert score > 0.0

    def test_tribal_match_same_type(self):
        """Two Goblins should have tribal synergy."""
        card_a = _make_card(
            "Goblin Warchief",
            type_line="Creature \u2014 Goblin Warrior",
            oracle_text="Goblin spells you cast cost {1} less to cast. Goblins you control have haste.",
            color_identity=["R"],
        )
        card_b = _make_card(
            "Goblin Chieftain",
            type_line="Creature \u2014 Goblin",
            oracle_text="Haste\nOther Goblins you control get +1/+1 and have haste.",
            color_identity=["R"],
        )
        score = compute_pairwise_synergy(card_a, card_b)
        assert score > 0.0

    def test_tribal_match_different_type(self):
        """Goblin vs Elf should have no tribal synergy component."""
        card_a = _make_card(
            "Goblin Warchief",
            type_line="Creature \u2014 Goblin Warrior",
            oracle_text="Goblin spells you cast cost {1} less.",
            color_identity=["R"],
        )
        card_b = _make_card(
            "Llanowar Elves",
            type_line="Creature \u2014 Elf Druid",
            oracle_text="{T}: Add {G}.",
            color_identity=["G"],
        )
        # Tribal component is 0, but other components might contribute
        score_same = compute_pairwise_synergy(card_a, _make_card(
            "Goblin Chieftain",
            type_line="Creature \u2014 Goblin",
            oracle_text="Other Goblins you control get +1/+1.",
            color_identity=["R"],
        ))
        score_diff = compute_pairwise_synergy(card_a, card_b)
        assert score_same > score_diff

    def test_enabler_payoff_sacrifice_death(self):
        """Sacrifice outlet + death trigger should score on enabler/payoff."""
        sac_outlet = _make_card(
            "Ashnod's Altar",
            type_line="Artifact",
            oracle_text="Sacrifice a creature: Add {C}{C}.",
        )
        death_trigger = _make_card(
            "Blood Artist",
            type_line="Creature \u2014 Vampire",
            oracle_text="Whenever Blood Artist or another creature dies, target player loses 1 life and you gain 1 life.",
            color_identity=["B"],
        )
        score = compute_pairwise_synergy(sac_outlet, death_trigger)
        assert score > 0.0

    def test_enabler_payoff_tokens_etb(self):
        """Token creator + creature ETB payoff should score on enabler/payoff."""
        token_maker = _make_card(
            "Krenko, Mob Boss",
            type_line="Legendary Creature \u2014 Goblin Warrior",
            oracle_text="Tap: Create X 1/1 red Goblin creature tokens.",
            color_identity=["R"],
        )
        etb_payoff = _make_card(
            "Impact Tremors",
            type_line="Enchantment",
            oracle_text="Whenever a creature enters the battlefield under your control, Impact Tremors deals 1 damage to each opponent.",
            color_identity=["R"],
        )
        score = compute_pairwise_synergy(token_maker, etb_payoff)
        assert score > 0.0

    def test_no_synergy_unrelated_cards(self):
        """Two completely unrelated cards should score very low."""
        card_a = _make_card(
            "Lightning Bolt",
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            color_identity=["R"],
        )
        card_b = _make_card(
            "Llanowar Elves",
            type_line="Creature \u2014 Elf Druid",
            oracle_text="{T}: Add {G}.",
            color_identity=["G"],
        )
        score = compute_pairwise_synergy(card_a, card_b)
        assert score < 0.15

    def test_score_in_range(self):
        """Score must be between 0.0 and 1.0 inclusive."""
        card_a = _make_card(
            "Sol Ring",
            type_line="Artifact",
            oracle_text="{T}: Add {C}{C}.",
        )
        card_b = _make_card(
            "Arcane Signet",
            type_line="Artifact",
            oracle_text="{T}: Add one mana of any color in your commander's color identity.",
        )
        score = compute_pairwise_synergy(card_a, card_b)
        assert 0.0 <= score <= 1.0

    def test_enabler_payoff_draw(self):
        """Card draw enabler + draw payoff should score on enabler/payoff."""
        draw_enabler = _make_card(
            "Rhystic Study",
            type_line="Enchantment",
            oracle_text="Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.",
            color_identity=["U"],
        )
        draw_payoff = _make_card(
            "Psychosis Crawler",
            type_line="Artifact Creature \u2014 Horror",
            oracle_text="Psychosis Crawler's power and toughness are each equal to the number of cards in your hand.\nWhenever you draw a card, each opponent loses 1 life.",
            color_identity=[],
        )
        score = compute_pairwise_synergy(draw_enabler, draw_payoff)
        assert score > 0.0

    def test_enabler_payoff_counters_proliferate(self):
        """+1/+1 counter source + proliferate should score on enabler/payoff."""
        counter_source = _make_card(
            "Hardened Scales",
            type_line="Enchantment",
            oracle_text="If one or more +1/+1 counters would be placed on a creature you control, that many plus one +1/+1 counters are placed on it instead.",
            color_identity=["G"],
        )
        proliferator = _make_card(
            "Flux Channeler",
            type_line="Creature \u2014 Human Wizard",
            oracle_text="Whenever you cast a noncreature spell, proliferate.",
            color_identity=["U"],
        )
        score = compute_pairwise_synergy(counter_source, proliferator)
        assert score > 0.0

    def test_enabler_payoff_graveyard(self):
        """Graveyard filler + graveyard retriever should score on enabler/payoff."""
        graveyard_filler = _make_card(
            "Stitcher's Supplier",
            type_line="Creature \u2014 Zombie",
            oracle_text="When Stitcher's Supplier enters the battlefield or dies, mill three cards.",
            color_identity=["B"],
        )
        graveyard_retriever = _make_card(
            "Reanimate",
            type_line="Sorcery",
            oracle_text="Put target creature card from a graveyard onto the battlefield under your control. You lose life equal to its mana value.",
            color_identity=["B"],
        )
        score = compute_pairwise_synergy(graveyard_filler, graveyard_retriever)
        assert score > 0.0


class TestComputePackageScore:
    def test_zero_cards(self):
        """Empty list should return 0.0."""
        assert compute_package_score([]) == 0.0

    def test_one_card(self):
        """Single card should return 0.0."""
        card = _make_card("Sol Ring", oracle_text="{T}: Add {C}{C}.")
        assert compute_package_score([card]) == 0.0

    def test_two_cards(self):
        """Two cards should return the pairwise score."""
        card_a = _make_card(
            "Ashnod's Altar",
            type_line="Artifact",
            oracle_text="Sacrifice a creature: Add {C}{C}.",
        )
        card_b = _make_card(
            "Blood Artist",
            type_line="Creature \u2014 Vampire",
            oracle_text="Whenever Blood Artist or another creature dies, target player loses 1 life and you gain 1 life.",
            color_identity=["B"],
        )
        score = compute_package_score([card_a, card_b])
        expected = compute_pairwise_synergy(card_a, card_b)
        assert score == pytest.approx(expected)

    def test_three_cards(self):
        """Three cards should return the mean of all three pairwise scores."""
        card_a = _make_card(
            "Ashnod's Altar",
            type_line="Artifact",
            oracle_text="Sacrifice a creature: Add {C}{C}.",
        )
        card_b = _make_card(
            "Blood Artist",
            type_line="Creature \u2014 Vampire",
            oracle_text="Whenever Blood Artist or another creature dies, target player loses 1 life.",
            color_identity=["B"],
        )
        card_c = _make_card(
            "Reassembling Skeleton",
            type_line="Creature \u2014 Skeleton Warrior",
            oracle_text="{1}{B}: Return Reassembling Skeleton from your graveyard to the battlefield tapped.",
            color_identity=["B"],
        )
        score = compute_package_score([card_a, card_b, card_c])
        pair_ab = compute_pairwise_synergy(card_a, card_b)
        pair_ac = compute_pairwise_synergy(card_a, card_c)
        pair_bc = compute_pairwise_synergy(card_b, card_c)
        expected = (pair_ab + pair_ac + pair_bc) / 3
        assert score == pytest.approx(expected)


class TestFindSynergyPackages:
    def test_empty_list(self):
        """Empty candidate list should return empty results."""
        assert find_synergy_packages([]) == []

    def test_single_card(self):
        """Single card should return empty results."""
        card = _make_card("Sol Ring", oracle_text="{T}: Add {C}{C}.")
        assert find_synergy_packages([card]) == []

    def test_returns_sorted_above_threshold(self):
        """Results should be sorted descending by score, all above min_synergy."""
        sac_outlet = _make_card(
            "Ashnod's Altar",
            type_line="Artifact",
            oracle_text="Sacrifice a creature: Add {C}{C}.",
        )
        death_trigger = _make_card(
            "Blood Artist",
            type_line="Creature \u2014 Vampire",
            oracle_text="Whenever Blood Artist or another creature dies, target player loses 1 life.",
            color_identity=["B"],
        )
        unrelated = _make_card(
            "Lightning Bolt",
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            color_identity=["R"],
        )
        results = find_synergy_packages(
            [sac_outlet, death_trigger, unrelated], min_synergy=0.1
        )
        # All results should be above threshold
        for _, _, score in results:
            assert score >= 0.1
        # Results should be sorted descending
        scores = [s for _, _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_respects_min_synergy(self):
        """Pairs below min_synergy should be excluded."""
        card_a = _make_card(
            "Lightning Bolt",
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            color_identity=["R"],
        )
        card_b = _make_card(
            "Llanowar Elves",
            type_line="Creature \u2014 Elf Druid",
            oracle_text="{T}: Add {G}.",
            color_identity=["G"],
        )
        # Very high threshold should exclude unrelated cards
        results = find_synergy_packages([card_a, card_b], min_synergy=0.9)
        assert results == []

    def test_respects_top_n(self):
        """Only the first top_n candidates should be considered."""
        cards = [
            _make_card(f"Card {i}", oracle_text=f"Text {i}")
            for i in range(10)
        ]
        # top_n=2 means only 1 pair (cards[0], cards[1])
        results = find_synergy_packages(cards, top_n=2, min_synergy=0.0)
        # Should have at most 1 pair
        assert len(results) <= 1

    def test_result_tuple_format(self):
        """Each result should be a (name_a, name_b, score) tuple."""
        card_a = _make_card(
            "Ashnod's Altar",
            type_line="Artifact",
            oracle_text="Sacrifice a creature: Add {C}{C}.",
        )
        card_b = _make_card(
            "Blood Artist",
            type_line="Creature \u2014 Vampire",
            oracle_text="Whenever Blood Artist or another creature dies, target player loses 1 life.",
            color_identity=["B"],
        )
        results = find_synergy_packages([card_a, card_b], min_synergy=0.0)
        assert len(results) == 1
        name_a, name_b, score = results[0]
        assert isinstance(name_a, str)
        assert isinstance(name_b, str)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
