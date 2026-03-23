"""Shared test fixtures for the MTG Deck Maker test suite."""

from __future__ import annotations

import os

import pytest

# Prevent CLI group callback from loading .env during tests
os.environ["MTG_SKIP_DOTENV"] = "1"

from mtg_deck_maker.db.database import Database
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.printing import Printing


@pytest.fixture
def db():
    """Create an in-memory database with schema initialized."""
    database = Database(":memory:")
    database.connect()
    yield database
    database.close()


@pytest.fixture
def sample_card() -> Card:
    """Return a sample Card for testing (Sol Ring)."""
    return Card(
        oracle_id="9b4cf4ef-0ea4-43f4-b529-9c5de5c3b22c",
        name="Sol Ring",
        type_line="Artifact",
        oracle_text="{T}: Add {C}{C}.",
        mana_cost="{1}",
        cmc=1.0,
        colors=[],
        color_identity=[],
        keywords=[],
        edhrec_rank=1,
        legal_commander=True,
        legal_brawl=False,
        updated_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_commander_card() -> Card:
    """Return a sample legendary creature for commander testing (Atraxa)."""
    return Card(
        oracle_id="aaaa-bbbb-cccc-dddd",
        name="Atraxa, Praetors' Voice",
        type_line="Legendary Creature - Phyrexian Angel Horror",
        oracle_text="Flying, vigilance, deathtouch, lifelink\nAt the beginning of your end step, proliferate.",
        mana_cost="{G}{W}{U}{B}",
        cmc=4.0,
        colors=["W", "U", "B", "G"],
        color_identity=["W", "U", "B", "G"],
        keywords=["Flying", "Vigilance", "Deathtouch", "Lifelink"],
        edhrec_rank=5,
        legal_commander=True,
        legal_brawl=True,
        updated_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_partner_a() -> Card:
    """Return a sample partner commander (Thrasios)."""
    return Card(
        oracle_id="partner-a-oracle-id",
        name="Thrasios, Triton Hero",
        type_line="Legendary Creature - Merfolk Wizard",
        oracle_text="{4}: Scry 1, then reveal the top card of your library. If it's a land card, put it onto the battlefield tapped. Otherwise, draw a card.",
        mana_cost="{G}{U}",
        cmc=2.0,
        colors=["U", "G"],
        color_identity=["U", "G"],
        keywords=["Partner"],
        edhrec_rank=10,
        legal_commander=True,
        legal_brawl=False,
        updated_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_partner_b() -> Card:
    """Return a sample partner commander (Tymna)."""
    return Card(
        oracle_id="partner-b-oracle-id",
        name="Tymna the Weaver",
        type_line="Legendary Creature - Human Cleric",
        oracle_text="At the beginning of your postcombat main phase, you may pay X life, where X is the number of opponents that were dealt combat damage this turn. If you do, draw X cards.",
        mana_cost="{1}{W}{B}",
        cmc=3.0,
        colors=["W", "B"],
        color_identity=["W", "B"],
        keywords=["Partner"],
        edhrec_rank=15,
        legal_commander=True,
        legal_brawl=False,
        updated_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_background_commander() -> Card:
    """Return a sample 'Choose a Background' commander."""
    return Card(
        oracle_id="bg-commander-oracle-id",
        name="Wilson, Refined Grizzly",
        type_line="Legendary Creature - Bear Warrior",
        oracle_text="Reach, trample, ward {2}",
        mana_cost="{G}",
        cmc=1.0,
        colors=["G"],
        color_identity=["G"],
        keywords=["Reach", "Trample", "Ward", "Choose a Background"],
        edhrec_rank=100,
        legal_commander=True,
        legal_brawl=False,
        updated_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_background() -> Card:
    """Return a sample Background enchantment."""
    return Card(
        oracle_id="background-oracle-id",
        name="Raised by Giants",
        type_line="Legendary Enchantment - Background",
        oracle_text="Commander creatures you own have base power and toughness 10/10 and are Giants in addition to their other types.",
        mana_cost="{5}{G}",
        cmc=6.0,
        colors=["G"],
        color_identity=["G"],
        keywords=[],
        edhrec_rank=500,
        legal_commander=True,
        legal_brawl=False,
        updated_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_companion() -> Card:
    """Return a sample Companion creature."""
    return Card(
        oracle_id="companion-oracle-id",
        name="Keruga, the Macrosage",
        type_line="Legendary Creature - Dinosaur Hippo",
        oracle_text="Companion - Your starting deck contains only cards with mana value 3 or greater and land cards.\nWhen Keruga, the Macrosage enters the battlefield, draw a card for each other permanent you control with mana value 3 or greater.",
        mana_cost="{3}{G}{U}",
        cmc=5.0,
        colors=["U", "G"],
        color_identity=["U", "G"],
        keywords=["Companion"],
        edhrec_rank=200,
        legal_commander=True,
        legal_brawl=False,
        updated_at="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_printing(sample_card: Card) -> Printing:
    """Return a sample Printing for Sol Ring."""
    return Printing(
        scryfall_id="f1d1e196-1a14-4e18-9136-e34c71f55836",
        card_id=1,  # Will be set after card insert
        set_code="C21",
        collector_number="263",
        lang="en",
        rarity="uncommon",
        finishes=["nonfoil"],
        tcgplayer_id=123456,
        cardmarket_id=654321,
        released_at="2021-04-16",
        is_promo=False,
        is_reprint=True,
    )


@pytest.fixture
def sample_cards_for_db() -> list[Card]:
    """Return a list of sample cards for bulk database operations."""
    return [
        Card(
            oracle_id="sol-ring-oracle",
            name="Sol Ring",
            type_line="Artifact",
            oracle_text="{T}: Add {C}{C}.",
            mana_cost="{1}",
            cmc=1.0,
            colors=[],
            color_identity=[],
            keywords=[],
            edhrec_rank=1,
            legal_commander=True,
            legal_brawl=False,
            updated_at="2026-01-01T00:00:00Z",
        ),
        Card(
            oracle_id="command-tower-oracle",
            name="Command Tower",
            type_line="Land",
            oracle_text="{T}: Add one mana of any color in your commander's color identity.",
            mana_cost="",
            cmc=0.0,
            colors=[],
            color_identity=[],
            keywords=[],
            edhrec_rank=2,
            legal_commander=True,
            legal_brawl=True,
            updated_at="2026-01-01T00:00:00Z",
        ),
        Card(
            oracle_id="swords-oracle",
            name="Swords to Plowshares",
            type_line="Instant",
            oracle_text="Exile target creature. Its controller gains life equal to its power.",
            mana_cost="{W}",
            cmc=1.0,
            colors=["W"],
            color_identity=["W"],
            keywords=[],
            edhrec_rank=3,
            legal_commander=True,
            legal_brawl=False,
            updated_at="2026-01-01T00:00:00Z",
        ),
        Card(
            oracle_id="counterspell-oracle",
            name="Counterspell",
            type_line="Instant",
            oracle_text="Counter target spell.",
            mana_cost="{U}{U}",
            cmc=2.0,
            colors=["U"],
            color_identity=["U"],
            keywords=[],
            edhrec_rank=10,
            legal_commander=True,
            legal_brawl=False,
            updated_at="2026-01-01T00:00:00Z",
        ),
        Card(
            oracle_id="lightning-bolt-oracle",
            name="Lightning Bolt",
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            mana_cost="{R}",
            cmc=1.0,
            colors=["R"],
            color_identity=["R"],
            keywords=[],
            edhrec_rank=50,
            legal_commander=True,
            legal_brawl=False,
            updated_at="2026-01-01T00:00:00Z",
        ),
    ]
