"""Tests for the strategy guide engine."""

from __future__ import annotations

from mtg_deck_maker.engine.strategy_guide import (
    _score_hand,
    analyze_win_conditions,
    generate_strategy_guide,
    identify_key_synergies,
    plan_game_phases,
    simulate_opening_hands,
)
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.combo import Combo


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


def _make_land(name: str) -> Card:
    return _make_card(name, type_line="Basic Land — Plains")


def _make_ramp(name: str, cmc: float = 2.0) -> Card:
    return _make_card(
        name, type_line="Artifact", oracle_text="{T}: Add {G}",
        mana_cost="{2}", cmc=cmc, colors=[], color_identity=["G"],
    )


def _make_creature(name: str, cmc: float = 3.0) -> Card:
    return _make_card(
        name, type_line="Creature — Human", oracle_text="",
        mana_cost="{2}{W}", cmc=cmc, colors=["W"], color_identity=["W"],
    )


def _make_win_con(name: str, oracle_text: str = "you win the game", cmc: float = 5.0) -> Card:
    return _make_card(
        name, type_line="Enchantment", oracle_text=oracle_text,
        mana_cost="{4}{W}", cmc=cmc, colors=["W"], color_identity=["W"],
    )


def _make_tutor(name: str) -> Card:
    return _make_card(
        name, type_line="Instant", oracle_text="Search your library for a card",
        mana_cost="{1}{B}", cmc=2.0, colors=["B"], color_identity=["B"],
    )


# ---------------------------------------------------------------------------
# _score_hand tests
# ---------------------------------------------------------------------------


class TestScoreHand:
    def test_ideal_hand_scores_high(self):
        """Hand with 3 lands, ramp, and a tutor should score >= 5."""
        cards = ["Plains", "Forest", "Island", "Sol Ring", "Demonic Tutor", "Llanowar Elves", "Kodama's Reach"]
        lookup = {
            "Plains": _make_land("Plains"),
            "Forest": _make_land("Forest"),
            "Island": _make_land("Island"),
            "Sol Ring": _make_ramp("Sol Ring"),
            "Demonic Tutor": _make_tutor("Demonic Tutor"),
            "Llanowar Elves": _make_ramp("Llanowar Elves", cmc=1.0),
            "Kodama's Reach": _make_ramp("Kodama's Reach", cmc=3.0),
        }
        score, _reason = _score_hand(cards, lookup)
        assert score >= 5

    def test_no_land_hand_scores_low(self):
        """Hand with 0 lands should score low."""
        cards = [f"Spell{i}" for i in range(7)]
        lookup = {f"Spell{i}": _make_creature(f"Spell{i}", cmc=3.0) for i in range(7)}
        score, _reason = _score_hand(cards, lookup)
        assert score <= 4

    def test_all_land_hand_scores_low(self):
        """Hand with 7 lands should score low (flood)."""
        cards = [f"Land{i}" for i in range(7)]
        lookup = {f"Land{i}": _make_land(f"Land{i}") for i in range(7)}
        score, reason = _score_hand(cards, lookup)
        assert score <= 4
        assert "flood" in reason

    def test_ramp_bonus_applied(self):
        """Ramp cards should add a bonus."""
        base_cards = ["Land1", "Land2", "Land3", "Creature1", "Creature2", "Creature3", "Creature4"]
        lookup = {}
        for name in base_cards:
            if name.startswith("Land"):
                lookup[name] = _make_land(name)
            else:
                lookup[name] = _make_creature(name, cmc=3.0)

        score_no_ramp, _ = _score_hand(base_cards, lookup)

        # Replace one creature with ramp
        ramp_cards = ["Land1", "Land2", "Land3", "Sol Ring", "Creature2", "Creature3", "Creature4"]
        lookup["Sol Ring"] = _make_ramp("Sol Ring")
        score_with_ramp, _ = _score_hand(ramp_cards, lookup)

        assert score_with_ramp >= score_no_ramp

    def test_high_cmc_penalty(self):
        """High average CMC in hand should reduce score."""
        cards = ["Land1", "Land2", "Land3", "BigSpell1", "BigSpell2", "BigSpell3", "BigSpell4"]
        lookup = {
            "Land1": _make_land("Land1"),
            "Land2": _make_land("Land2"),
            "Land3": _make_land("Land3"),
        }
        for i in range(1, 5):
            lookup[f"BigSpell{i}"] = _make_creature(f"BigSpell{i}", cmc=7.0)

        score, reason = _score_hand(cards, lookup)
        assert "high avg CMC" in reason

    def test_win_enabler_bonus(self):
        """Having a win condition or tutor should give a bonus."""
        cards = ["Land1", "Land2", "Land3", "WinCon", "Spell1", "Spell2", "Spell3"]
        lookup = {
            "Land1": _make_land("Land1"),
            "Land2": _make_land("Land2"),
            "Land3": _make_land("Land3"),
            "WinCon": _make_win_con("WinCon"),
            "Spell1": _make_creature("Spell1"),
            "Spell2": _make_creature("Spell2"),
            "Spell3": _make_creature("Spell3"),
        }
        score, reason = _score_hand(cards, lookup)
        assert "win enabler" in reason

    def test_score_clamped_0_to_10(self):
        """Score should never go below 0 or above 10."""
        # Worst possible scenario
        cards = [f"Bad{i}" for i in range(7)]
        lookup = {f"Bad{i}": _make_creature(f"Bad{i}", cmc=8.0) for i in range(7)}
        score, _ = _score_hand(cards, lookup)
        assert 0 <= score <= 10


# ---------------------------------------------------------------------------
# simulate_opening_hands tests
# ---------------------------------------------------------------------------


class TestSimulateOpeningHands:
    def _balanced_deck(self) -> tuple[list[str], dict[str, Card]]:
        """Create a balanced 99-card deck: 37 lands, 10 ramp, 52 creatures."""
        cards: list[str] = []
        lookup: dict[str, Card] = {}
        for i in range(37):
            name = f"Land{i}"
            cards.append(name)
            lookup[name] = _make_land(name)
        for i in range(10):
            name = f"Ramp{i}"
            cards.append(name)
            lookup[name] = _make_ramp(name)
        for i in range(52):
            name = f"Creature{i}"
            cards.append(name)
            lookup[name] = _make_creature(name)
        return cards, lookup

    def test_balanced_deck_good_keep_rate(self):
        cards, lookup = self._balanced_deck()
        result = simulate_opening_hands(cards, lookup, num_simulations=500)
        assert result.keep_rate > 0.5

    def test_all_land_deck_low_keep_rate(self):
        cards = [f"Land{i}" for i in range(99)]
        lookup = {name: _make_land(name) for name in cards}
        result = simulate_opening_hands(cards, lookup, num_simulations=500)
        assert result.keep_rate < 0.5

    def test_all_spells_deck_low_keep_rate(self):
        cards = [f"Spell{i}" for i in range(99)]
        lookup = {name: _make_creature(name, cmc=4.0) for name in cards}
        result = simulate_opening_hands(cards, lookup, num_simulations=500)
        assert result.keep_rate < 0.5

    def test_deterministic_with_seed(self):
        cards, lookup = self._balanced_deck()
        r1 = simulate_opening_hands(cards, lookup, num_simulations=100, seed=123)
        r2 = simulate_opening_hands(cards, lookup, num_simulations=100, seed=123)
        assert r1.keep_rate == r2.keep_rate
        assert r1.avg_land_count == r2.avg_land_count

    def test_small_deck_returns_empty(self):
        cards = ["Card1", "Card2"]
        lookup = {name: _make_creature(name) for name in cards}
        result = simulate_opening_hands(cards, lookup)
        assert result.total_simulations == 0
        assert "fewer than 7" in result.mulligan_advice

    def test_sample_hands_populated(self):
        cards, lookup = self._balanced_deck()
        result = simulate_opening_hands(cards, lookup, num_simulations=100)
        assert len(result.sample_hands) >= 3  # At least worst, best, median

    def test_mulligan_advice_present(self):
        cards, lookup = self._balanced_deck()
        result = simulate_opening_hands(cards, lookup, num_simulations=100)
        assert result.mulligan_advice != ""


# ---------------------------------------------------------------------------
# analyze_win_conditions tests
# ---------------------------------------------------------------------------


class TestAnalyzeWinConditions:
    def test_direct_win_card_detected(self):
        cards = ["Lab Maniac"]
        lookup = {"Lab Maniac": _make_win_con("Lab Maniac", "you win the game if you would draw from empty library")}
        result = analyze_win_conditions(cards, lookup, [], "combo", "Commander")
        assert len(result) > 0
        assert any("Direct Win" in wp.name for wp in result)

    def test_complete_combo_creates_win_path(self):
        combo = Combo(
            combo_id="c1",
            card_names=["CardA", "CardB"],
            result="Infinite damage",
            color_identity=["R"],
            description="Infinite damage combo",
        )
        cards = ["CardA", "CardB", "Filler"]
        lookup = {
            "CardA": _make_creature("CardA"),
            "CardB": _make_creature("CardB"),
            "Filler": _make_creature("Filler"),
        }
        result = analyze_win_conditions(cards, lookup, [combo], "combo", "Commander")
        assert any(wp.combo_id == "c1" for wp in result)

    def test_partial_combo_excluded(self):
        combo = Combo(
            combo_id="c2",
            card_names=["CardA", "CardB", "CardC"],
            result="Infinite combo",
            color_identity=["U"],
        )
        # Only CardA and CardB are in deck, missing CardC
        cards = ["CardA", "CardB"]
        lookup = {
            "CardA": _make_creature("CardA"),
            "CardB": _make_creature("CardB"),
        }
        result = analyze_win_conditions(cards, lookup, [combo], "combo", "Commander")
        assert not any(wp.combo_id == "c2" for wp in result)

    def test_infect_grouped(self):
        cards = ["InfectCreature"]
        lookup = {"InfectCreature": _make_win_con("InfectCreature", "Infect", cmc=2.0)}
        result = analyze_win_conditions(cards, lookup, [], "aggro", "Commander")
        assert any("Infect" in wp.name for wp in result)

    def test_empty_for_utility_deck(self):
        cards = ["Bear1", "Bear2"]
        lookup = {
            "Bear1": _make_creature("Bear1"),
            "Bear2": _make_creature("Bear2"),
        }
        result = analyze_win_conditions(cards, lookup, [], "midrange", "Commander")
        assert len(result) == 0

    def test_combos_sorted_first(self):
        combo = Combo(
            combo_id="c3",
            card_names=["ComboA", "ComboB"],
            result="Win",
            color_identity=["B"],
        )
        cards = ["ComboA", "ComboB", "WinCon"]
        lookup = {
            "ComboA": _make_creature("ComboA"),
            "ComboB": _make_creature("ComboB"),
            "WinCon": _make_win_con("WinCon"),
        }
        result = analyze_win_conditions(cards, lookup, [combo], "combo", "Commander")
        assert result[0].combo_id == "c3"

    def test_mill_win_condition(self):
        cards = ["Mill Engine"]
        lookup = {"Mill Engine": _make_win_con("Mill Engine", "Each opponent mills 10 cards")}
        result = analyze_win_conditions(cards, lookup, [], "control", "Commander")
        assert any("Mill" in wp.name for wp in result)


# ---------------------------------------------------------------------------
# plan_game_phases tests
# ---------------------------------------------------------------------------


class TestPlanGamePhases:
    def _build_deck_with_curve(self) -> tuple[list[str], dict[str, Card]]:
        cards: list[str] = []
        lookup: dict[str, Card] = {}
        # Low CMC ramp
        for i in range(5):
            name = f"Ramp{i}"
            cards.append(name)
            lookup[name] = _make_ramp(name, cmc=2.0)
        # Mid CMC removal
        for i in range(5):
            name = f"Removal{i}"
            cards.append(name)
            lookup[name] = _make_card(name, type_line="Instant", oracle_text="Destroy target creature", cmc=3.0)
        # High CMC win cons
        for i in range(3):
            name = f"Finisher{i}"
            cards.append(name)
            lookup[name] = _make_win_con(name, cmc=7.0)
        # Lands
        for i in range(20):
            name = f"Land{i}"
            cards.append(name)
            lookup[name] = _make_land(name)
        return cards, lookup

    def test_always_three_phases(self):
        cards, lookup = self._build_deck_with_curve()
        phases = plan_game_phases(cards, lookup, "midrange", [], 3.0)
        assert len(phases) == 3

    def test_phase_names(self):
        cards, lookup = self._build_deck_with_curve()
        phases = plan_game_phases(cards, lookup, "midrange", [], 3.0)
        names = [p.phase_name for p in phases]
        assert names == ["Early Game", "Mid Game", "Late Game"]

    def test_turn_ranges(self):
        cards, lookup = self._build_deck_with_curve()
        phases = plan_game_phases(cards, lookup, "midrange", [], 3.0)
        assert phases[0].turn_range == "Turns 1-3"
        assert phases[1].turn_range == "Turns 4-7"
        assert phases[2].turn_range == "Turns 8+"

    def test_archetype_specific_priorities(self):
        cards, lookup = self._build_deck_with_curve()
        aggro_phases = plan_game_phases(cards, lookup, "aggro", [], 3.0)
        control_phases = plan_game_phases(cards, lookup, "control", [], 3.0)
        # Aggro and control should have different early priorities
        assert aggro_phases[0].priorities != control_phases[0].priorities

    def test_early_key_cards_low_cmc(self):
        cards, lookup = self._build_deck_with_curve()
        phases = plan_game_phases(cards, lookup, "midrange", [], 3.0)
        early = phases[0]
        for card_name in early.key_cards:
            card = lookup.get(card_name)
            if card:
                assert card.cmc <= 2

    def test_empty_deck(self):
        phases = plan_game_phases([], {}, "midrange", [], 0.0)
        assert len(phases) == 3  # Should still return 3 phases with empty key_cards


# ---------------------------------------------------------------------------
# identify_key_synergies tests
# ---------------------------------------------------------------------------


class TestIdentifyKeySynergies:
    def test_respects_max_results(self):
        cards = []
        lookup = {}
        # Create cards that share a theme so they'll have synergy
        for i in range(10):
            name = f"TokenMaker{i}"
            cards.append(name)
            lookup[name] = _make_card(
                name, type_line="Creature — Elf",
                oracle_text="Create a 1/1 token",
                cmc=2.0, color_identity=["G"],
            )
        result = identify_key_synergies(cards, lookup, max_results=3)
        assert len(result) <= 3

    def test_empty_input_returns_empty(self):
        result = identify_key_synergies([], {})
        assert result == []

    def test_single_card_returns_empty(self):
        lookup = {"Card1": _make_creature("Card1")}
        result = identify_key_synergies(["Card1"], lookup)
        assert result == []

    def test_synergistic_pair_found(self):
        cards = ["TokenMaker", "TokenPayoff"]
        lookup = {
            "TokenMaker": _make_card(
                "TokenMaker", type_line="Creature — Elf",
                oracle_text="Create a 1/1 green Elf creature token",
                cmc=2.0, color_identity=["G"],
            ),
            "TokenPayoff": _make_card(
                "TokenPayoff", type_line="Creature — Elf",
                oracle_text="Whenever a creature token enters the battlefield, draw a card",
                cmc=3.0, color_identity=["G"],
            ),
        }
        result = identify_key_synergies(cards, lookup)
        # Should find synergy between these two
        assert len(result) >= 1

    def test_reason_populated(self):
        cards = ["Elf1", "Elf2"]
        lookup = {
            "Elf1": _make_card("Elf1", type_line="Creature — Elf", oracle_text="Create a 1/1 token", cmc=2.0),
            "Elf2": _make_card("Elf2", type_line="Creature — Elf", oracle_text="Create a 1/1 token", cmc=2.0),
        }
        result = identify_key_synergies(cards, lookup)
        if result:
            assert result[0].reason != ""


# ---------------------------------------------------------------------------
# generate_strategy_guide integration tests
# ---------------------------------------------------------------------------


class TestGenerateStrategyGuide:
    def _build_full_deck(self) -> tuple[list[str], dict[str, Card], list[Combo]]:
        cards: list[str] = []
        lookup: dict[str, Card] = {}

        # Commander
        commander = _make_card(
            "Test Commander",
            type_line="Legendary Creature — Human Wizard",
            oracle_text="Whenever you cast an instant or sorcery, draw a card.",
            cmc=4.0, colors=["U", "R"], color_identity=["U", "R"],
        )
        cards.append("Test Commander")
        lookup["Test Commander"] = commander

        # Lands
        for i in range(36):
            name = f"Land{i}"
            cards.append(name)
            lookup[name] = _make_land(name)

        # Ramp
        for i in range(10):
            name = f"Ramp{i}"
            cards.append(name)
            lookup[name] = _make_ramp(name)

        # Creatures
        for i in range(40):
            name = f"Creature{i}"
            cards.append(name)
            lookup[name] = _make_creature(name)

        # Win conditions
        for i in range(3):
            name = f"WinCon{i}"
            cards.append(name)
            lookup[name] = _make_win_con(name)

        # Tutor
        cards.append("Tutor1")
        lookup["Tutor1"] = _make_tutor("Tutor1")

        # Filler to get to 100
        remaining = 100 - len(cards)
        for i in range(remaining):
            name = f"Filler{i}"
            cards.append(name)
            lookup[name] = _make_creature(name, cmc=3.0)

        combos = [
            Combo(
                combo_id="test-combo",
                card_names=["Creature0", "Creature1"],
                result="Infinite tokens",
                color_identity=["U", "R"],
                description="Creates infinite tokens",
            )
        ]

        return cards, lookup, combos

    def test_all_fields_populated(self):
        cards, lookup, combos = self._build_full_deck()
        guide = generate_strategy_guide(
            cards, lookup, combos, "Test Commander", num_sims=50,
        )
        assert guide.archetype != ""
        assert guide.hand_simulation is not None
        assert guide.hand_simulation.total_simulations == 50
        assert len(guide.game_phases) == 3
        assert isinstance(guide.win_paths, list)
        assert isinstance(guide.key_synergies, list)
        assert guide.llm_narrative is None  # No LLM in engine

    def test_works_without_combos(self):
        cards, lookup, _ = self._build_full_deck()
        guide = generate_strategy_guide(cards, lookup, [], "Test Commander", num_sims=50)
        assert guide.archetype != ""
        assert len(guide.game_phases) == 3

    def test_explicit_archetype_used(self):
        cards, lookup, combos = self._build_full_deck()
        guide = generate_strategy_guide(
            cards, lookup, combos, "Test Commander",
            archetype="aggro", num_sims=50,
        )
        assert guide.archetype == "aggro"

    def test_commander_excluded_from_hand_sim(self):
        cards, lookup, combos = self._build_full_deck()
        guide = generate_strategy_guide(
            cards, lookup, combos, "Test Commander", num_sims=50,
        )
        sim = guide.hand_simulation
        assert sim is not None
        # Commander should not appear in any sample hand
        for sample in sim.sample_hands:
            assert "Test Commander" not in sample.cards
