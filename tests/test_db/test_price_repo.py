"""Tests for the PriceRepository CRUD operations."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from mtg_deck_maker.db.card_repo import CardRepository
from mtg_deck_maker.db.database import Database
from mtg_deck_maker.db.price_repo import PriceRepository
from mtg_deck_maker.db.printing_repo import PrintingRepository
from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.printing import Printing


@pytest.fixture
def all_repos(
    db: Database,
) -> tuple[CardRepository, PrintingRepository, PriceRepository]:
    """Create all three repositories."""
    return (
        CardRepository(db),
        PrintingRepository(db),
        PriceRepository(db),
    )


@pytest.fixture
def printing_ids(
    all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
) -> tuple[int, int]:
    """Insert a card with two printings and return their IDs."""
    card_repo, printing_repo, _ = all_repos

    card = Card(
        oracle_id="price-test-oracle",
        name="Price Test Card",
        type_line="Creature",
        mana_cost="{1}{W}",
        cmc=2.0,
        legal_commander=True,
    )
    card_id = card_repo.insert_card(card)

    p1 = Printing(
        scryfall_id="price-print-1",
        card_id=card_id,
        set_code="SET1",
        collector_number="1",
    )
    p2 = Printing(
        scryfall_id="price-print-2",
        card_id=card_id,
        set_code="SET2",
        collector_number="1",
    )
    pid1 = printing_repo.insert_printing(p1)
    pid2 = printing_repo.insert_printing(p2)
    return pid1, pid2


class TestInsertPrice:
    """Test price insertion."""

    def test_insert_price_returns_id(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        _, _, price_repo = all_repos
        pid1, _ = printing_ids
        price_id = price_repo.insert_price(
            printing_id=pid1,
            source="tcgplayer",
            price=5.50,
        )
        assert price_id is not None
        assert price_id > 0

    def test_insert_price_with_all_fields(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        _, _, price_repo = all_repos
        pid1, _ = printing_ids
        price_id = price_repo.insert_price(
            printing_id=pid1,
            source="cardmarket",
            price=4.20,
            currency="EUR",
            finish="foil",
            retrieved_at="2026-01-15T12:00:00Z",
        )
        assert price_id > 0


class TestGetLatestPrice:
    """Test retrieving the most recent price."""

    def test_get_latest_price(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        _, _, price_repo = all_repos
        pid1, _ = printing_ids

        # Insert older price
        price_repo.insert_price(
            printing_id=pid1,
            source="tcgplayer",
            price=3.00,
            retrieved_at="2026-01-01T00:00:00Z",
        )
        # Insert newer price
        price_repo.insert_price(
            printing_id=pid1,
            source="tcgplayer",
            price=5.00,
            retrieved_at="2026-01-15T00:00:00Z",
        )

        latest = price_repo.get_latest_price(
            printing_id=pid1, source="tcgplayer"
        )
        assert latest == 5.00

    def test_get_latest_price_filters_source(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        _, _, price_repo = all_repos
        pid1, _ = printing_ids

        price_repo.insert_price(
            printing_id=pid1,
            source="tcgplayer",
            price=5.00,
            retrieved_at="2026-01-15T00:00:00Z",
        )
        price_repo.insert_price(
            printing_id=pid1,
            source="scryfall",
            price=4.50,
            retrieved_at="2026-01-15T00:00:00Z",
        )

        tcg_price = price_repo.get_latest_price(
            printing_id=pid1, source="tcgplayer"
        )
        scry_price = price_repo.get_latest_price(
            printing_id=pid1, source="scryfall"
        )
        assert tcg_price == 5.00
        assert scry_price == 4.50

    def test_get_latest_price_filters_finish(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        _, _, price_repo = all_repos
        pid1, _ = printing_ids

        price_repo.insert_price(
            printing_id=pid1,
            source="tcgplayer",
            price=5.00,
            finish="nonfoil",
            retrieved_at="2026-01-15T00:00:00Z",
        )
        price_repo.insert_price(
            printing_id=pid1,
            source="tcgplayer",
            price=10.00,
            finish="foil",
            retrieved_at="2026-01-15T00:00:00Z",
        )

        nonfoil = price_repo.get_latest_price(
            printing_id=pid1, source="tcgplayer", finish="nonfoil"
        )
        foil = price_repo.get_latest_price(
            printing_id=pid1, source="tcgplayer", finish="foil"
        )
        assert nonfoil == 5.00
        assert foil == 10.00

    def test_get_latest_price_not_found(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
    ) -> None:
        _, _, price_repo = all_repos
        price = price_repo.get_latest_price(
            printing_id=99999, source="tcgplayer"
        )
        assert price is None


class TestGetCheapestPrice:
    """Test getting the cheapest price across all printings of a card."""

    def test_cheapest_across_printings(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        card_repo, _, price_repo = all_repos
        pid1, pid2 = printing_ids

        price_repo.insert_price(
            printing_id=pid1,
            source="tcgplayer",
            price=5.00,
            retrieved_at="2026-01-15T00:00:00Z",
        )
        price_repo.insert_price(
            printing_id=pid2,
            source="tcgplayer",
            price=3.00,
            retrieved_at="2026-01-15T00:00:00Z",
        )

        card = card_repo.get_card_by_name("Price Test Card")
        assert card is not None
        cheapest = price_repo.get_cheapest_price(card.id)
        assert cheapest == 3.00

    def test_cheapest_filters_currency(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        card_repo, _, price_repo = all_repos
        pid1, _ = printing_ids

        price_repo.insert_price(
            printing_id=pid1,
            source="tcgplayer",
            price=5.00,
            currency="USD",
            retrieved_at="2026-01-15T00:00:00Z",
        )
        price_repo.insert_price(
            printing_id=pid1,
            source="cardmarket",
            price=4.00,
            currency="EUR",
            retrieved_at="2026-01-15T00:00:00Z",
        )

        card = card_repo.get_card_by_name("Price Test Card")
        assert card is not None

        usd = price_repo.get_cheapest_price(card.id, currency="USD")
        eur = price_repo.get_cheapest_price(card.id, currency="EUR")
        assert usd == 5.00
        assert eur == 4.00

    def test_cheapest_not_found(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
    ) -> None:
        _, _, price_repo = all_repos
        cheapest = price_repo.get_cheapest_price(99999)
        assert cheapest is None


class TestGetCheapestPrices:
    """Test batch price loading for multiple cards."""

    def test_bulk_cheapest_prices(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        card_repo, printing_repo, price_repo = all_repos
        pid1, pid2 = printing_ids

        # Card 1 already exists from printing_ids fixture
        # Insert a second card with its own printing
        card2 = Card(
            oracle_id="bulk-price-card-2",
            name="Bulk Price Card 2",
            type_line="Instant",
            mana_cost="{U}",
            cmc=1.0,
            legal_commander=True,
        )
        card2_id = card_repo.insert_card(card2)
        p3 = Printing(
            scryfall_id="bulk-price-print-3",
            card_id=card2_id,
            set_code="SET3",
            collector_number="1",
        )
        pid3 = printing_repo.insert_printing(p3)

        # Insert prices for both cards
        price_repo.insert_price(printing_id=pid1, source="tcgplayer", price=5.00)
        price_repo.insert_price(printing_id=pid2, source="tcgplayer", price=3.00)
        price_repo.insert_price(printing_id=pid3, source="tcgplayer", price=2.50)

        card1 = card_repo.get_card_by_name("Price Test Card")
        assert card1 is not None

        prices = price_repo.get_cheapest_prices([card1.id, card2_id])
        assert prices[card1.id] == 3.00  # min of 5.00 and 3.00
        assert prices[card2_id] == 2.50

    def test_bulk_cheapest_empty_list(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
    ) -> None:
        _, _, price_repo = all_repos
        prices = price_repo.get_cheapest_prices([])
        assert prices == {}

    def test_bulk_cheapest_no_prices(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        card_repo, _, price_repo = all_repos
        # Card exists but has no prices inserted
        card = card_repo.get_card_by_name("Price Test Card")
        assert card is not None
        prices = price_repo.get_cheapest_prices([card.id])
        assert prices == {}

    def test_bulk_cheapest_large_batch(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
    ) -> None:
        card_repo, printing_repo, price_repo = all_repos
        # Create >900 cards to test chunking
        card_ids = []
        for i in range(950):
            card = Card(
                oracle_id=f"chunk-test-{i}",
                name=f"Chunk Card {i}",
                type_line="Creature",
                mana_cost="{1}",
                cmc=1.0,
                legal_commander=True,
            )
            cid = card_repo.insert_card(card)
            card_ids.append(cid)

            p = Printing(
                scryfall_id=f"chunk-print-{i}",
                card_id=cid,
                set_code="CHK",
                collector_number=str(i),
            )
            pid = printing_repo.insert_printing(p)
            price_repo.insert_price(printing_id=pid, source="scryfall", price=float(i % 10))

        prices = price_repo.get_cheapest_prices(card_ids)
        assert len(prices) == 950
        # Cards with price=0.0 are excluded (price IS NOT NULL, but 0.0 is not null)
        # Actually 0.0 is not None so they should be included
        for cid in card_ids:
            assert cid in prices


class TestBulkInsertPrices:
    """Test bulk price insertion."""

    def test_bulk_insert_count(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        _, _, price_repo = all_repos
        pid1, pid2 = printing_ids

        prices = [
            {"printing_id": pid1, "source": "tcgplayer", "price": 5.00},
            {"printing_id": pid1, "source": "scryfall", "price": 4.50},
            {"printing_id": pid2, "source": "tcgplayer", "price": 3.00},
        ]
        count = price_repo.bulk_insert_prices(prices)
        assert count == 3

    def test_bulk_insert_with_all_fields(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        _, _, price_repo = all_repos
        pid1, _ = printing_ids

        prices = [
            {
                "printing_id": pid1,
                "source": "cardmarket",
                "price": 4.20,
                "currency": "EUR",
                "finish": "foil",
                "retrieved_at": "2026-02-01T00:00:00Z",
            },
        ]
        count = price_repo.bulk_insert_prices(prices)
        assert count == 1


class TestGetPricesNewerThan:
    """Test TTL-based price filtering."""

    def test_get_recent_prices(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        _, _, price_repo = all_repos
        pid1, _ = printing_ids

        # Old price
        price_repo.insert_price(
            printing_id=pid1,
            source="scryfall",
            price=3.00,
            retrieved_at="2025-01-01T00:00:00Z",
        )
        # Recent price
        price_repo.insert_price(
            printing_id=pid1,
            source="tcgplayer",
            price=5.00,
            retrieved_at="2026-02-01T00:00:00Z",
        )

        recent = price_repo.get_prices_newer_than("2026-01-01T00:00:00Z")
        assert len(recent) == 1
        assert recent[0]["source"] == "tcgplayer"
        assert recent[0]["price"] == 5.00

    def test_get_no_recent_prices(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        _, _, price_repo = all_repos
        pid1, _ = printing_ids

        price_repo.insert_price(
            printing_id=pid1,
            source="scryfall",
            price=3.00,
            retrieved_at="2025-01-01T00:00:00Z",
        )

        recent = price_repo.get_prices_newer_than("2026-01-01T00:00:00Z")
        assert recent == []

    def test_get_prices_newer_than_returns_all_fields(
        self,
        all_repos: tuple[CardRepository, PrintingRepository, PriceRepository],
        printing_ids: tuple[int, int],
    ) -> None:
        _, _, price_repo = all_repos
        pid1, _ = printing_ids

        price_repo.insert_price(
            printing_id=pid1,
            source="tcgplayer",
            price=5.50,
            currency="USD",
            finish="foil",
            retrieved_at="2026-02-15T12:00:00Z",
        )

        recent = price_repo.get_prices_newer_than("2026-02-01T00:00:00Z")
        assert len(recent) == 1
        record = recent[0]
        assert "id" in record
        assert record["printing_id"] == pid1
        assert record["source"] == "tcgplayer"
        assert record["currency"] == "USD"
        assert record["price"] == 5.50
        assert record["finish"] == "foil"
        assert record["retrieved_at"] == "2026-02-15T12:00:00Z"
