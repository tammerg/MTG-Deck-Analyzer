"""Tests for the deck builder engine module."""

from __future__ import annotations

import pytest

from mtg_deck_maker.config import AppConfig
from mtg_deck_maker.engine.deck_builder import (
    DeckBuildError,
    build_deck,
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
    """Build a realistic card pool for testing.

    Generates a diverse pool of cards across multiple categories
    within the specified color identity.

    Args:
        color_identity: Colors the pool should span.
        size: Approximate number of non-land cards to generate.
        include_lands: Whether to include land cards.

    Returns:
        List of Card objects.
    """
    pool: list[Card] = []
    card_id = 1

    # Map colors to basic info
    color_mana = {
        "W": ("{W}", ["W"]),
        "U": ("{U}", ["U"]),
        "B": ("{B}", ["B"]),
        "R": ("{R}", ["R"]),
        "G": ("{G}", ["G"]),
    }

    relevant_colors = color_identity if color_identity else [""]

    # --- Ramp cards (15-20) ---
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

    # Color-specific ramp
    for color in relevant_colors:
        if not color:
            continue
        mana_str, color_list = color_mana.get(color, ("{1}", []))
        if color == "G":
            for j in range(5):
                pool.append(_make_card(
                    card_id, f"Nature's Lore Variant {j}",
                    "Sorcery", f"Search your library for a Forest card, put it onto the battlefield tapped.",
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

    # --- Card draw (15-20) ---
    draw_templates = [
        ("Rhystic Study", "Enchantment", "Whenever an opponent casts a spell, draw a card unless that player pays {1}.", "{2}{U}", 3.0, ["U"], ["U"]),
        ("Mystic Remora", "Enchantment", "Whenever an opponent casts a noncreature spell, draw a card.", "{U}", 1.0, ["U"], ["U"]),
        ("Phyrexian Arena", "Enchantment", "At the beginning of your upkeep, you draw a card and you lose 1 life.", "{1}{B}{B}", 3.0, ["B"], ["B"]),
    ]

    for name, tl, ot, mc, cmc, cols, ci in draw_templates:
        if is_within_identity(ci, color_identity):
            pool.append(_make_card(card_id, name, tl, ot, mc, cmc, cols, ci, edhrec_rank=card_id * 5))
            card_id += 1

    # Generic draw cards (colorless or in-identity)
    for j in range(15):
        if j % 3 == 0:
            cols = []
            ci = []
            mc = "{3}"
            cmc_val = 3.0
        else:
            color = relevant_colors[j % len(relevant_colors)]
            if not color:
                cols = []
                ci = []
                mc = "{2}"
                cmc_val = 2.0
            else:
                ms, cl = color_mana.get(color, ("{1}", []))
                cols = cl
                ci = cl
                mc = f"{{1}}{ms}"
                cmc_val = 2.0

        pool.append(_make_card(
            card_id, f"Draw Spell {j}",
            "Instant", "Draw a card. Draw another card.",
            mc, cmc_val, cols, ci, edhrec_rank=400 + j,
        ))
        card_id += 1

    # --- Removal (10-15) ---
    for j in range(12):
        color = relevant_colors[j % len(relevant_colors)]
        if not color:
            cols = []
            ci = []
            mc = "{3}"
            cmc_val = 3.0
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols = cl
            ci = cl
            mc = f"{{1}}{ms}"
            cmc_val = 2.0

        pool.append(_make_card(
            card_id, f"Removal Spell {j}",
            "Instant", "Destroy target creature.",
            mc, cmc_val, cols, ci, edhrec_rank=500 + j,
        ))
        card_id += 1

    # --- Board wipes (5) ---
    for j in range(5):
        pool.append(_make_card(
            card_id, f"Board Wipe {j}",
            "Sorcery", "Destroy all creatures.",
            "{4}", 4.0, [], [], edhrec_rank=600 + j,
        ))
        card_id += 1

    # --- Protection (6) ---
    for j in range(6):
        color = relevant_colors[j % len(relevant_colors)]
        if not color:
            cols = []
            ci = []
            mc = "{2}"
            cmc_val = 2.0
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols = cl
            ci = cl
            mc = ms
            cmc_val = 1.0

        pool.append(_make_card(
            card_id, f"Protection Spell {j}",
            "Instant", "Target permanent gains hexproof until end of turn.",
            mc, cmc_val, cols, ci, edhrec_rank=700 + j,
        ))
        card_id += 1

    # --- Win conditions (10) ---
    for j in range(10):
        color = relevant_colors[j % len(relevant_colors)]
        if not color:
            cols = []
            ci = []
            mc = "{5}"
            cmc_val = 5.0
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols = cl
            ci = cl
            mc = f"{{4}}{ms}"
            cmc_val = 5.0

        pool.append(_make_card(
            card_id, f"Win Condition {j}",
            "Creature - Angel", "Flying\nEach opponent loses 2 life and you gain 2 life.",
            mc, cmc_val, cols, ci,
            keywords=["Flying"],
            edhrec_rank=100 + j,
        ))
        card_id += 1

    # --- Synergy/Utility creatures (60+) ---
    for j in range(70):
        color = relevant_colors[j % len(relevant_colors)]
        if not color:
            cols = []
            ci = []
            mc = "{3}"
            cmc_val = 3.0
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols = cl
            ci = cl
            mc = f"{{2}}{ms}"
            cmc_val = 3.0

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
            card_id, f"Utility Creature {j}",
            "Creature - Human",
            oracle,
            mc, cmc_val, cols, ci,
            keywords=kws,
            edhrec_rank=800 + j,
        ))
        card_id += 1

    # --- Enchantments and artifacts (20+) ---
    for j in range(25):
        color = relevant_colors[j % len(relevant_colors)]
        if not color:
            cols = []
            ci = []
            mc = "{2}"
            cmc_val = 2.0
            tl = "Artifact"
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols = cl
            ci = cl
            mc = f"{{1}}{ms}"
            cmc_val = 2.0
            tl = "Enchantment"

        pool.append(_make_card(
            card_id, f"Utility Permanent {j}",
            tl, "At the beginning of your upkeep, you gain 1 life.",
            mc, cmc_val, cols, ci, edhrec_rank=900 + j,
        ))
        card_id += 1

    # --- Filler spells (fill to size) ---
    while len(pool) < size:
        color = relevant_colors[card_id % len(relevant_colors)]
        if not color:
            cols = []
            ci = []
            mc = "{2}"
            cmc_val = 2.0
        else:
            ms, cl = color_mana.get(color, ("{1}", []))
            cols = cl
            ci = cl
            mc = f"{{1}}{ms}"
            cmc_val = 2.0

        pool.append(_make_card(
            card_id, f"Filler Card {card_id}",
            "Sorcery", "Target player draws a card.",
            mc, cmc_val, cols, ci, edhrec_rank=1500 + card_id,
        ))
        card_id += 1

    # --- Lands ---
    if include_lands:
        # Basic lands
        basic_map = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
        for color in color_identity:
            basic_name = basic_map.get(color)
            if basic_name:
                pool.append(_make_card(
                    card_id, basic_name,
                    "Basic Land", "",
                    "", 0.0, [], [], edhrec_rank=None,
                ))
                card_id += 1

        # Command Tower
        pool.append(_make_card(
            card_id, "Command Tower",
            "Land", "{T}: Add one mana of any color in your commander's color identity.",
            "", 0.0, [], [], edhrec_rank=2,
        ))
        card_id += 1

        # A few nonbasic dual-ish lands
        for j in range(5):
            pool.append(_make_card(
                card_id, f"Tapland {j}",
                "Land", f"This land enters the battlefield tapped.\n{{T}}: Add mana.",
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
            # Vary prices: lands cheap, creatures moderate, staples pricier
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
    """UW (Azorius) solo commander."""
    return Commander(primary=_build_uw_commander())


@pytest.fixture
def partner_commander() -> Commander:
    """Partner pair (WUBG 4-color commander)."""
    return Commander(
        primary=_build_partner_a(),
        partner=_build_partner_b(),
    )


@pytest.fixture
def uw_card_pool() -> list[Card]:
    """Card pool for a UW deck with 250+ cards."""
    return _build_card_pool(["W", "U"], size=250)


@pytest.fixture
def wubg_card_pool() -> list[Card]:
    """Card pool for a 4-color WUBG deck."""
    return _build_card_pool(["W", "U", "B", "G"], size=300)


@pytest.fixture
def config() -> AppConfig:
    """Default app config for testing."""
    return AppConfig()


# ===========================================================================
# Tests: build_deck
# ===========================================================================


class TestBuildDeckBasic:
    """Basic deck building tests."""

    def test_produces_exactly_100_cards(self, uw_commander, uw_card_pool, config):
        """A built deck must have exactly 100 total cards."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)
        assert deck.total_cards() == 100

    def test_all_cards_within_color_identity(self, uw_commander, uw_card_pool, config):
        """Every card in the deck must be within the commander's color identity."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)
        cmd_identity = uw_commander.combined_color_identity()

        for dc in deck.cards:
            # Basic lands and colorless are always fine
            if not dc.colors:
                continue
            assert is_within_identity(dc.colors, cmd_identity), (
                f"Card {dc.card_name!r} colors {dc.colors} "
                f"not within identity {cmd_identity}"
            )

    def test_singleton_constraint(self, uw_commander, uw_card_pool, config):
        """No non-basic card should appear more than once."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)

        basic_names = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}
        seen: set[str] = set()
        for dc in deck.cards:
            if dc.card_name in basic_names:
                continue
            assert dc.card_name not in seen, (
                f"Duplicate non-basic card: {dc.card_name!r}"
            )
            seen.add(dc.card_name)

    def test_budget_compliance(self, uw_commander, uw_card_pool, config):
        """Deck total price should be within 5% of the budget target."""
        budget = 100.0
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, budget, uw_card_pool, config, prices=prices)
        total_price = deck.total_price()
        # 5% tolerance
        assert total_price <= budget * 1.05, (
            f"Deck cost ${total_price:.2f} exceeds budget ${budget:.2f} "
            f"(max ${budget * 1.05:.2f})"
        )

    def test_has_commander_cards(self, uw_commander, uw_card_pool, config):
        """The deck should contain the commander card(s)."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)
        commanders = deck.commanders()
        assert len(commanders) == 1
        assert commanders[0].card_name == "Test Commander, Azure Sage"

    def test_deck_name_includes_commander(self, uw_commander, uw_card_pool, config):
        """The deck name should include the commander name."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)
        assert "Test Commander, Azure Sage" in deck.name

    def test_deck_format_is_commander(self, uw_commander, uw_card_pool, config):
        """Deck format should be 'commander'."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)
        assert deck.format == "commander"


class TestBuildDeckPartner:
    """Tests for partner commander deck building."""

    def test_partner_produces_100_cards(self, partner_commander, wubg_card_pool, config):
        """Partner deck should still have exactly 100 cards."""
        prices = _build_prices(wubg_card_pool)
        deck = build_deck(partner_commander, 250.0, wubg_card_pool, config, prices=prices)
        assert deck.total_cards() == 100

    def test_partner_has_two_commanders(self, partner_commander, wubg_card_pool, config):
        """Partner deck should list both commanders."""
        prices = _build_prices(wubg_card_pool)
        deck = build_deck(partner_commander, 250.0, wubg_card_pool, config, prices=prices)
        commanders = deck.commanders()
        assert len(commanders) == 2
        cmd_names = {c.card_name for c in commanders}
        assert "Test Partner Alpha" in cmd_names
        assert "Test Partner Beta" in cmd_names

    def test_partner_98_noncommander_cards(self, partner_commander, wubg_card_pool, config):
        """Partner deck should have 98 non-commander cards (100 - 2 commanders)."""
        prices = _build_prices(wubg_card_pool)
        deck = build_deck(partner_commander, 250.0, wubg_card_pool, config, prices=prices)
        mainboard = deck.mainboard()
        mainboard_count = sum(c.quantity for c in mainboard)
        assert mainboard_count == 98

    def test_partner_color_identity_union(self, partner_commander, wubg_card_pool, config):
        """Partner deck should use the union of both partners' color identities."""
        prices = _build_prices(wubg_card_pool)
        deck = build_deck(partner_commander, 250.0, wubg_card_pool, config, prices=prices)
        expected_identity = partner_commander.combined_color_identity()
        # Expected: W, U, B, G
        assert set(expected_identity) == {"W", "U", "B", "G"}

        # All cards should be within this identity
        for dc in deck.cards:
            if not dc.colors:
                continue
            assert is_within_identity(dc.colors, expected_identity)


class TestBuildDeckDeterminism:
    """Tests for deterministic output with seeded RNG."""

    def test_same_seed_same_deck(self, uw_commander, uw_card_pool, config):
        """Same seed should produce identical decks."""
        prices = _build_prices(uw_card_pool)
        deck1 = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices, seed=42)
        deck2 = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices, seed=42)

        names1 = sorted(c.card_name for c in deck1.cards)
        names2 = sorted(c.card_name for c in deck2.cards)
        assert names1 == names2

    def test_different_seed_produces_valid_deck(self, uw_commander, uw_card_pool, config):
        """Different seeds should each produce valid 100-card decks.

        With a constrained pool, different seeds may select the same top
        cards since scoring is deterministic. The key property is that
        both builds remain valid.
        """
        prices = _build_prices(uw_card_pool)
        deck1 = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices, seed=42)
        deck2 = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices, seed=999)

        assert deck1.total_cards() == 100
        assert deck2.total_cards() == 100


class TestBuildDeckCategories:
    """Tests for category distribution in built decks."""

    def test_has_ramp_cards(self, uw_commander, uw_card_pool, config):
        """Deck should contain ramp cards."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)
        ramp = [c for c in deck.cards if c.category == Category.RAMP.value]
        assert len(ramp) >= 3, f"Only {len(ramp)} ramp cards found"

    def test_has_card_draw(self, uw_commander, uw_card_pool, config):
        """Deck should contain card draw cards."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)
        draw = [c for c in deck.cards if c.category == Category.CARD_DRAW.value]
        assert len(draw) >= 3, f"Only {len(draw)} card draw cards found"

    def test_has_removal(self, uw_commander, uw_card_pool, config):
        """Deck should contain removal cards."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)
        removal = [c for c in deck.cards if c.category == Category.REMOVAL.value]
        assert len(removal) >= 2, f"Only {len(removal)} removal cards found"

    def test_has_lands(self, uw_commander, uw_card_pool, config):
        """Deck should contain a reasonable number of lands."""
        prices = _build_prices(uw_card_pool)
        deck = build_deck(uw_commander, 200.0, uw_card_pool, config, prices=prices)
        land_count = sum(
            c.quantity for c in deck.cards if c.category == Category.LAND.value
        )
        assert 28 <= land_count <= 42, f"Land count {land_count} outside expected range"


class TestBuildDeckValidation:
    """Tests for commander validation in the build process."""

    def test_invalid_commander_raises_error(self, uw_card_pool, config):
        """Building with an invalid commander should raise DeckBuildError."""
        # Non-legendary creature
        bad_commander = _make_card(
            9999, "Not A Legend",
            "Creature - Human", "Nothing special.",
            "{1}{W}", 2.0, ["W"], ["W"],
        )
        commander = Commander(primary=bad_commander)
        prices = _build_prices(uw_card_pool)

        with pytest.raises(DeckBuildError, match="Invalid commander"):
            build_deck(commander, 200.0, uw_card_pool, config, prices=prices)

    def test_insufficient_pool_raises_error(self, uw_commander, config):
        """Building with too few cards should raise DeckBuildError."""
        tiny_pool = [
            _make_card(i, f"Card {i}", legal_commander=True)
            for i in range(1, 10)
        ]
        with pytest.raises(DeckBuildError, match="Insufficient card pool"):
            build_deck(uw_commander, 200.0, tiny_pool, config)


class TestNormalizeEdhrec:
    """Tests for _normalize_edhrec_rank helper."""

    def test_none_rank(self):
        """None rank should give default middle-low score."""
        assert _normalize_edhrec_rank(None) == 0.3

    def test_rank_1_is_near_max(self):
        """Rank 1 (best) should give a score near 1.0."""
        score = _normalize_edhrec_rank(1)
        assert score > 0.99

    def test_rank_20000_is_zero(self):
        """Rank equal to max should give 0.0."""
        assert _normalize_edhrec_rank(20000) == 0.0

    def test_rank_10000_is_half(self):
        """Rank 10000 should give ~0.5."""
        assert _normalize_edhrec_rank(10000) == 0.5


class TestGetPrimaryCategory:
    """Tests for _get_primary_category helper."""

    def test_prefers_functional_over_type(self):
        """Functional categories should be preferred over type-based ones."""
        categories = [
            (Category.CREATURE.value, 1.0),
            (Category.RAMP.value, 0.85),
        ]
        cat, conf = _get_primary_category(categories)
        assert cat == Category.RAMP.value

    def test_falls_back_to_type_if_no_functional(self):
        """If no functional category, should return the first type category."""
        categories = [
            (Category.CREATURE.value, 1.0),
            (Category.ARTIFACT.value, 1.0),
        ]
        cat, conf = _get_primary_category(categories)
        assert cat == Category.CREATURE.value

    def test_empty_categories_returns_utility(self):
        """Empty category list should default to utility."""
        cat, conf = _get_primary_category([])
        assert cat == Category.UTILITY.value
