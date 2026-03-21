"""Shared fixtures for the web API test suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mtg_deck_maker.api.web.app import create_app
from mtg_deck_maker.api.web.dependencies import get_db
from mtg_deck_maker.db.card_repo import CardRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.price_repo import PriceRepository
from mtg_deck_maker.db.printing_repo import PrintingRepository
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.printing import Printing


@pytest.fixture
def mem_db():
    """Return an in-memory database with schema initialized."""
    db = Database(":memory:")
    db.connect()
    yield db
    db.close()


@pytest.fixture
def seeded_db(mem_db: Database) -> Database:
    """Seed the in-memory database with sample cards, printings, and prices."""
    card_repo = CardRepository(mem_db)
    printing_repo = PrintingRepository(mem_db)
    price_repo = PriceRepository(mem_db)

    # Insert commander card
    cmd_card = Card(
        oracle_id="atraxa-oracle-id",
        name="Atraxa, Praetors' Voice",
        type_line="Legendary Creature - Phyrexian Angel Horror",
        oracle_text="Flying, vigilance, deathtouch, lifelink",
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
    cmd_id = card_repo.insert_card(cmd_card)

    # Insert a few pool cards
    sol_ring = Card(
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
    )
    sol_id = card_repo.insert_card(sol_ring)

    counterspell = Card(
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
    )
    counter_id = card_repo.insert_card(counterspell)

    # Insert printings
    cmd_printing = Printing(
        scryfall_id="c26d1f4c-0000-0000-0000-000000000001",
        card_id=cmd_id,
        set_code="C16",
        collector_number="37",
        lang="en",
        rarity="mythic",
        finishes=["nonfoil"],
        released_at="2016-11-11",
        is_promo=False,
        is_reprint=False,
    )
    cmd_printing_id = printing_repo.insert_printing(cmd_printing)

    sol_printing = Printing(
        scryfall_id="f1d1e196-0000-0000-0000-000000000002",
        card_id=sol_id,
        set_code="C21",
        collector_number="263",
        lang="en",
        rarity="uncommon",
        finishes=["nonfoil"],
        released_at="2021-04-16",
        is_promo=False,
        is_reprint=True,
    )
    sol_printing_id = printing_repo.insert_printing(sol_printing)

    counter_printing = Printing(
        scryfall_id="8b07ef98-0000-0000-0000-000000000003",
        card_id=counter_id,
        set_code="MH2",
        collector_number="46",
        lang="en",
        rarity="uncommon",
        finishes=["nonfoil"],
        released_at="2021-06-18",
        is_promo=False,
        is_reprint=True,
    )
    counter_printing_id = printing_repo.insert_printing(counter_printing)

    # Insert prices
    price_repo.insert_price(cmd_printing_id, "scryfall", 8.50)
    price_repo.insert_price(sol_printing_id, "scryfall", 2.00)
    price_repo.insert_price(counter_printing_id, "scryfall", 0.75)

    return mem_db


@pytest.fixture
def app(seeded_db: Database):
    """Create a test FastAPI app with the in-memory seeded database injected."""
    application = create_app()

    def override_get_db():
        yield seeded_db

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture
def client(app) -> TestClient:
    """Return a synchronous TestClient bound to the test app."""
    return TestClient(app)
