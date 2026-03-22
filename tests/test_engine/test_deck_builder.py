"""Tests for the deck builder engine module."""

from __future__ import annotations

import pytest

from mtg_deck_maker.config import AppConfig
from unittest.mock import patch

from mtg_deck_maker.engine.deck_builder import (
    ARCHETYPE_CATEGORY_TARGETS,
    IDEAL_CURVE,
    Archetype,
    DeckBuildError,
    build_deck,
    detect_archetype,
    DEFAULT_CATEGORY_TARGETS,
    _normalize_edhrec_rank,
    _get_primary_category,
)
from mtg_deck_maker.engine.categories import Category
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.commander import Commander
from mtg_deck_maker.utils.colors import is_within_identity


# ---------------------------------------------------------------------------
# Helpers: build a realistic card pool programmatically
# ---------------------------------------------------------------------------


def _make_card(
    card_id: int,
    name: str,
    type_line: str = "Instant",
    oracle_text: str = "",
    mana_cost: str = "{1}",
    cmc: float = 1.0,
    colors: list[str] | None = None,
    color_identity: list[str] | None = None,
    keywords: list[str] | None = None,
    edhrec_rank: int = 1000,
    legal_commander: bool = True,
) -> Card:
    """Create a test Card with sensible defaults."""
    return Card(
        oracle_id=f"oracle-{card_id}",
        name=name,
        type_line=type_line,
        oracle_text=oracle_text,
        mana_cost=mana_cost,
        cmc=cmc,
        colors=colors or [],
        color_identity=color_identity or [],
        keywords=keywords or [],
        edhrec_rank=edhrec_rank,
        legal_commander=legal_commander,
        id=card_id,
    )


def _build_uw_commander() -> Card:
    """Create a UW (Azorius) commander card."""
    return _make_card(
        card_id=9000,
        name="Test Commander, Azure Sage",
        type_line="Legendary Creature - Human Wizard",
        oracle_text="Flying\nWhenever you draw a card, create a 1/1 white Bird creature token with flying.",
        mana_cost="{2}{W}{U}",
        cmc=4.0,
        colors=["W", "U"],
        color_identity=["W", "U"],
        keywords=["Flying"],
        edhrec_rank=50,
    )


def _build_partner_a() -> Card:
    """Create a UG partner commander."""
    return _make_card(
        card_id=9001,
        name="Test Partner Alpha",
        type_line="Legendary Creature - Merfolk Wizard",
        oracle_text="Whenever a land enters the battlefield under your control, draw a card.",
        mana_cost="{G}{U}",
        cmc=2.0,
        colors=["U", "G"],
        color_identity=["U", "G"],
        keywords=["Partner"],
        edhrec_rank=20,
    )


def _build_partner_b() -> Card:
    """Create a WB partner commander."""
    return _make_card(
        card_id=9002,
        name="Test Partner Beta",
        type_line="Legendary Creature - Human Cleric",
        oracle_text="At the beginning of your postcombat main phase, draw cards equal to opponents dealt damage this turn.",
        mana_cost="{1}{W}{B}",
        cmc=3.0,
        colors=["W", "B"],
        color_identity=["W", "B"],
        keywords=["Partner"],
        edhrec_rank=25,
    )


def _build_card_pool(
    color_identity: list[str],
    size: int = 250,
    include_lands: bool = True,
) -> list[Card]:
    """Build a realistic card pool for testing."""
    pool: list[Card] = []
    card_id = 1

    color_mana = {
        "W": ("{W}", ["W"]),
        "U": ("{U}", ["U"]),
        "B": ("{B}", ["B"]),
        "R": ("{R}", ["R"]),
        "G": ("{G}", ["G"]),
    }

    relevant_colors = color_identity if color_identity else [""]

    # --- Ramp cards ---
    ramp_templates = [
        ("Sol Ring", "Artifact", "{T}: Add {C}{C}.", "{1}", 1.0, [], []),
        ("Arcane Signet", "Artifact", "{T}: Add one mana of any color in your commander's color identity.", "{2}", 2.0, [], []),
        ("Mind Stone", "Artifact", "{T}: Add {C}.\n{1}, {T}, Sacrifice Mind Stone: Draw a card.", "{2}", 2.0, [], []),
        ("Fellwar Stone", "Artifact", "{T}: Add one mana of any color.", "{2}", 2.0, [], []),
        ("Thought Vessel", "Artifact", "{T}: Add {C}.\nYou have no maximum hand size.", "{2}", 2.0, [], []),
        ("Commander's Sphere", "Artifact", "{T}: Add one mana of any color.\nSacrifice: Draw a card.", "{3}", 3.0, [], []),
        ("Worn Powerstone", "Artifact", "{T}: Add {C}{C}.", "{3}", 3.0, [], []),
        ("Gilded Lotus", "Artifact", "{T}: Add three mana of any one color.", "{5}", 5.0, [], []),
        ("Thran Dynamo", "Artifact", "{T}: Add {C}{C}{C}.", "{4}", 4.0, [], []),
        ("Star Compass", "Artifact", "{T}: Add one mana of any color.", "{2}", 2.0, [], []),
    ]

    for name, tl, ot, mc, cmc, cols, ci in ramp_templates:
        pool.append(_make_card(card_id, name, tl, ot, mc, cmc, cols, ci, edhrec_rank=card_id * 10))
        card_id += 1

    for color in relevant_colors:
        if not color:
            continue
        mana_str, color_list = color_mana.get(color, ("{1}", []))
        if color == "G":
            for j in range(5):
                pool.append(_make_card(
                    card_id, f"Nature's Lore Variant {j}",
                    "Sorcery", "Search your library for a Forest card, put it onto the battlefield tapped.",
                    f"{{1}}{mana_str}", 2.0, color_list, color_list, edhrec_rank=200 + j,
                ))
                card_id += 1
        else:
            for j in range(2):
                pool.append(_make_card(
                    card_id, f"{color} Ramp Spell {j}",
                    "Instant", f"Add {mana_str}{mana_str}{mana_str}.",
                    mana_str, 1.0, color_list, color_list, edhrec_rank=300 + j,
                ))
                card_id += 1

    # --- Card draw ---
    draw_templates = [
        ("Rhystic Study", "Enchantment", "Whenever an opponent casts a spell, draw a card unless that player pays {1}.", "{2}{U}", 3.0, ["U"], ["U"]),
        ("Mystic Remora", "Enchantment", "Whenever an opponent casts a noncreature spell, draw a card.", "{U}", 1.0, ["U"], ["U"]),
        ("Phyrexian Arena", "Enchantment", "At the beginning of your upkeep, you draw a card and you lose 1 life.", "{1}{B}{B}", 3.0, ["B"], ["B"]),
    ]

    for name, tl, ot, mc, cmc, cols, ci in draw_templates:
        if is_within_identity(ci, color_identity):
            pool.append(_make_card(card_id, name, tl, ot, mc, cmc, cols, ci, edhrec_rank=card_id * 5))
            card_id += 1

    for j in range(15):
        if j % 3 == 0:
            cols, ci, mc, cmc_val = [], [], "{3}", 3.0
        else:
            color = relevant_colors[j % len(relevant_colors)]
            if not color:
                cols, ci, mc, cmc_val = [], [], "{2}", 2.0
            else:
                ms, cl = color_mana.get(color, ("{1}", []))
                cols, ci = cl, cl
                mc, cmc_val = f"{{1}}{ms}", 2.0

        pool.append(_make_card(
            card_id, f"Draw Spell {j}", "Instant", "Draw a card. Draw another card.",
            mc, cmc_val, cols, ci, edhrec_rank=400 + j,
        ))
        card_id += 1

    # --- Removal ---
    for j in range(12):
        color = relevant_colors[j % len(relevant_colors)]
        if not color:
            cols, ci, mc, cmc_val = [], [], "{3}", 3.0
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols, ci = cl, cl
            mc, cmc_val = f"{{1}}{ms}", 2.0

        pool.append(_make_card(
            card_id, f"Removal Spell {j}", "Instant", "Destroy target creature.",
            mc, cmc_val, cols, ci, edhrec_rank=500 + j,
        ))
        card_id += 1

    # --- Board wipes ---
    for j in range(5):
        pool.append(_make_card(
            card_id, f"Board Wipe {j}", "Sorcery", "Destroy all creatures.",
            "{4}", 4.0, [], [], edhrec_rank=600 + j,
        ))
        card_id += 1

    # --- Protection ---
    for j in range(6):
        color = relevant_colors[j % len(relevant_colors)]
        if not color:
            cols, ci, mc, cmc_val = [], [], "{2}", 2.0
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols, ci = cl, cl
            mc, cmc_val = ms, 1.0

        pool.append(_make_card(
            card_id, f"Protection Spell {j}", "Instant", "Target permanent gains hexproof until end of turn.",
            mc, cmc_val, cols, ci, edhrec_rank=700 + j,
        ))
        card_id += 1

    # --- Win conditions ---
    for j in range(10):
        color = relevant_colors[j % len(relevant_colors)]
        if not color:
            cols, ci, mc, cmc_val = [], [], "{5}", 5.0
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols, ci = cl, cl
            mc, cmc_val = f"{{4}}{ms}", 5.0

        pool.append(_make_card(
            card_id, f"Win Condition {j}", "Creature - Angel",
            "Flying\nEach opponent loses 2 life and you gain 2 life.",
            mc, cmc_val, cols, ci, keywords=["Flying"], edhrec_rank=100 + j,
        ))
        card_id += 1

    # --- Creatures ---
    for j in range(70):
        color = relevant_colors[j % len(relevant_colors)]
        if not color:
            cols, ci, mc, cmc_val = [], [], "{3}", 3.0
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols, ci = cl, cl
            mc, cmc_val = f"{{2}}{ms}", 3.0

        texts = [
            "When this creature enters the battlefield, create a 1/1 token.",
            "Whenever you cast a spell, scry 1.",
            "When this creature enters the battlefield, you gain 3 life.",
            "{T}: Add {C}.",
            "Flying",
        ]
        oracle = texts[j % len(texts)]
        kws = ["Flying"] if "Flying" in oracle else []

        pool.append(_make_card(
            card_id, f"Utility Creature {j}", "Creature - Human", oracle,
            mc, cmc_val, cols, ci, keywords=kws, edhrec_rank=800 + j,
        ))
        card_id += 1

    # --- Enchantments/Artifacts ---
    for j in range(25):
        color = relevant_colors[j % len(relevant_colors)]
        if not color:
            cols, ci, mc, cmc_val, tl = [], [], "{2}", 2.0, "Artifact"
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols, ci = cl, cl
            mc, cmc_val, tl = f"{{1}}{ms}", 2.0, "Enchantment"

        pool.append(_make_card(
            card_id, f"Utility Permanent {j}", tl,
            "At the beginning of your upkeep, you gain 1 life.",
            mc, cmc_val, cols, ci, edhrec_rank=900 + j,
        ))
        card_id += 1

    # --- Filler ---
    while len(pool) < size:
        color = relevant_colors[card_id % len(relevant_colors)]
        if not color:
            cols, ci, mc, cmc_val = [], [], "{2}", 2.0
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols, ci = cl, cl
            mc, cmc_val = f"{{1}}{ms}", 2.0

        pool.append(_make_card(
            card_id, f"Filler Card {card_id}", "Sorcery", "Target player draws a card.",
            mc, cmc_val, cols, ci, edhrec_rank=1500 + card_id,
        ))
        card_id += 1

    # --- Lands ---
    if include_lands:
        basic_map = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
        for color in color_identity:
            basic_name = basic_map.get(color)
            if basic_name:
                pool.append(_make_card(card_id, basic_name, "Basic Land", "", "", 0.0, [], [], edhrec_rank=None))
                card_id += 1

        pool.append(_make_card(
            card_id, "Command Tower", "Land",
            "{T}: Add one mana of any color in your commander's color identity.",
            "", 0.0, [], [], edhrec_rank=2,
        ))
        card_id += 1

        for j in range(5):
            pool.append(_make_card(
                card_id, f"Tapland {j}", "Land",
                "This land enters the battlefield tapped.\n{T}: Add mana.",
                "", 0.0, [], color_identity[:2] if len(color_identity) >= 2 else color_identity,
                edhrec_rank=1200 + j,
            ))
            card_id += 1

    return pool


def _build_prices(pool: list[Card], default_price: float = 0.50) -> dict[int, float]:
    """Build a price dict for all cards in the pool."""
    prices: dict[int, float] = {}
    for card in pool:
        if card.id is not None:
            if card.is_land:
                prices[card.id] = 0.10
            elif card.edhrec_rank is not None and card.edhrec_rank < 100:
                prices[card.id] = 3.00
            elif card.edhrec_rank is not None and card.edhrec_rank < 500:
                prices[card.id] = 1.50
            else:
                prices[card.id] = default_price
    return prices


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def uw_commander() -> Commander:
    return Commander(primary=_build_uw_commander())


@pytest.fixture
def partner_commander() -> Commander:
    return Commander(primary=_build_partner_a(), partner=_build_partner_b())


@pytest.fixture
def uw_card_pool() -> list[Card]:
    return _build_card_pool(["W", "U"], size=250)


@pytest.fixture
def wubg_card_pool() -> list[Card]:
    return _build_card_pool(["W", "U", "B", "G"], size=300)


@pytest.fixture
def config() -> AppConfig:
    return AppConfig()


# ===========================================================================
# Tests: build_deck
# ===========================================================================


class TestBuildDeckBasic:
    """Basic deck building invariants consolidated into one test."""

    def test_basic_invariants(self, uw_commander, uw_card_pool, config):
        """A built deck must satisfy: 100 cards, color identity, singleton, budget, commander present, correct name/format."""
        prices = _build_prices(uw_card_pool)
        budget = 200.0
        deck = build_deck(uw_commander, budget, uw_card_pool, config, prices=prices)

        # Exactly 100 cards
        assert deck.total_cards() == 100

        # All cards within color identity
        cmd_identity = uw_commander.combined_color_identity()
        for dc in deck.cards:
            if not dc.colors:
                continue
            assert is_within_identity(dc.colors, cmd_identity), (
                f"Card {dc.card_name!r} colors {dc.colors} not within identity {cmd_identity}"
            )

        # Singleton constraint
        basic_names = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
        seen: set[str] = set()
        for dc in deck.cards:
            if dc.card_name in basic_names:
                continue
            assert dc.card_name not in seen, f"Duplicate non-basic card: {dc.card_name!r}"
            seen.add(dc.card_name)

        # Budget compliance (5% tolerance)
        assert deck.total_price() <= budget * 1.05

        # Commander present
        commanders = deck.commanders()
        assert len(commanders) == 1
        assert commanders[0].card_name == "Test Commander, Azure Sage"

        # Format and name
        assert deck.format == "commander"
        assert "Test Commander, Azure Sage" in deck.name


class TestBuildDeckPartner:
    """Partner commander deck building consolidated into one test."""

    def test_partner_invariants(self, partner_commander, wubg_card_pool, config):
        """Partner deck: 100 cards, 2 commanders, 98 mainboard, correct color identity."""
        prices = _build_prices(wubg_card_pool)
        deck = build_deck(partner_commander, 250.0, wubg_card_pool, config, prices=prices)

        assert deck.total_cards() == 100

        commanders = deck.commanders()
        assert len(commanders) == 2
        cmd_names = {c.card_name for c in commanders}
        assert "Test Partner Alpha" in cmd_names
        assert "Test Partner Beta" in cmd_names

        mainboard_count = sum(c.quantity for c in deck.mainboard())
        assert mainboard_count == 98

        expected_identity = partner_commander.combined_color_identity()
        assert set(expected_identity) == {"W", "U", "B", "G"}
        for dc in deck.cards:
            if not dc.colors:
                continue
            assert is_within_identity(dc.colors, expected_identity)


class TestBuildDeckDeterminism:
    def test_same_seed_same_deck(self, uw_commander, uw_card_pool, config):
        prices = _build_prices(uw_card_pool)
        deck1 = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices, seed=42)
        deck2 = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices, seed=42)
        names1 = sorted(c.card_name for c in deck1.cards)
        names2 = sorted(c.card_name for c in deck2.cards)
        assert names1 == names2


class TestBuildDeckCategories:
    """Category distribution consolidated into one test."""

    def test_category_distribution(self, uw_commander, uw_card_pool, config):
        """Deck should contain ramp, draw, removal, and lands in reasonable amounts."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)

        ramp = [c for c in deck.cards if c.category == Category.RAMP.value]
        draw = [c for c in deck.cards if c.category == Category.CARD_DRAW.value]
        removal = [c for c in deck.cards if c.category == Category.REMOVAL.value]
        land_count = sum(c.quantity for c in deck.cards if c.category == Category.LAND.value)

        assert len(ramp) >= 3, f"Only {len(ramp)} ramp cards found"
        assert len(draw) >= 3, f"Only {len(draw)} card draw cards found"
        assert len(removal) >= 2, f"Only {len(removal)} removal cards found"
        assert 28 <= land_count <= 42, f"Land count {land_count} outside expected range"


class TestBuildDeckValidation:
    def test_invalid_commander_raises_error(self, uw_card_pool, config):
        bad_commander = _make_card(
            9999, "Not A Legend", "Creature - Human", "Nothing special.",
            "{1}{W}", 2.0, ["W"], ["W"],
        )
        commander = Commander(primary=bad_commander)
        prices = _build_prices(uw_card_pool)
        with pytest.raises(DeckBuildError, match="Invalid commander"):
            build_deck(commander, 200.0, uw_card_pool, config, prices=prices)

    def test_insufficient_pool_raises_error(self, uw_commander, config):
        tiny_pool = [_make_card(i, f"Card {i}", legal_commander=True) for i in range(1, 10)]
        with pytest.raises(DeckBuildError, match="Insufficient card pool"):
            build_deck(uw_commander, 200.0, tiny_pool, config)


class TestArchetypeDetection:
    def test_detect_tribal_commander(self):
        commander = _make_card(
            9100, "Zombie Tribal Lord",
            type_line="Legendary Creature \u2014 Zombie",
            oracle_text="Other Zombies you control get +1/+1.",
            color_identity=["B"],
        )
        assert detect_archetype(commander) == Archetype.TRIBAL.value

    def test_detect_spellslinger(self):
        commander = _make_card(
            9101, "Spell Slinger Leader",
            type_line="Legendary Creature \u2014 Human Wizard",
            oracle_text="Whenever you cast an instant or sorcery spell, draw a card.",
            color_identity=["U", "R"],
        )
        assert detect_archetype(commander) == Archetype.SPELLSLINGER.value

    def test_detect_aggro(self):
        commander = _make_card(
            9102, "Aggro Beater",
            type_line="Legendary Creature \u2014 Warrior",
            oracle_text="Whenever Aggro Beater attacks, it gets +3/+0 until end of turn.",
            color_identity=["R"],
        )
        assert detect_archetype(commander) == Archetype.AGGRO.value

    def test_detect_default_midrange(self):
        commander = _make_card(
            9104, "Generic Commander",
            type_line="Legendary Creature \u2014 Human",
            oracle_text="Vigilance",
            color_identity=["W"],
        )
        assert detect_archetype(commander) == Archetype.MIDRANGE.value


class TestManaCurveShaping:
    def test_ideal_curve_profiles_exist(self):
        for archetype in Archetype:
            assert archetype.value in IDEAL_CURVE

    def test_ideal_curve_values_sum_to_one(self):
        for archetype_name, curve in IDEAL_CURVE.items():
            total = sum(curve.values())
            assert abs(total - 1.0) < 0.01
