"""Tests for the sync service module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from mtg_deck_maker.db.database import Database
from mtg_deck_maker.services.sync_service import (
    SyncResult,
    SyncService,
    _extract_prices,
    _process_cards,
)

# --- Sample Scryfall card data ---

SAMPLE_CARD_SOL_RING = {
    "id": "abc-123-sol",
    "oracle_id": "oracle-sol-ring",
    "name": "Sol Ring",
    "type_line": "Artifact",
    "oracle_text": "{T}: Add {C}{C}.",
    "mana_cost": "{1}",
    "cmc": 1.0,
    "colors": [],
    "color_identity": [],
    "keywords": [],
    "legalities": {"commander": "legal", "brawl": "legal"},
    "edhrec_rank": 1,
    "set": "c21",
    "collector_number": "263",
    "lang": "en",
    "rarity": "uncommon",
    "finishes": ["nonfoil"],
    "tcgplayer_id": 12345,
    "cardmarket_id": 67890,
    "released_at": "2021-04-16",
    "promo": False,
    "reprint": True,
    "updated_at": "2024-01-15",
    "prices": {
        "usd": "3.50",
        "usd_foil": "5.00",
        "usd_etched": None,
        "eur": "3.00",
        "eur_foil": "4.50",
    },
}

SAMPLE_CARD_COMMAND_TOWER = {
    "id": "def-456-tower",
    "oracle_id": "oracle-command-tower",
    "name": "Command Tower",
    "type_line": "Land",
    "oracle_text": "{T}: Add one mana of any color in your commander's color identity.",
    "mana_cost": "",
    "cmc": 0.0,
    "colors": [],
    "color_identity": [],
    "keywords": [],
    "legalities": {"commander": "legal", "brawl": "legal"},
    "edhrec_rank": 2,
    "set": "c21",
    "collector_number": "264",
    "lang": "en",
    "rarity": "common",
    "finishes": ["nonfoil"],
    "tcgplayer_id": 23456,
    "cardmarket_id": 78901,
    "released_at": "2021-04-16",
    "promo": False,
    "reprint": True,
    "updated_at": "2024-01-15",
    "prices": {
        "usd": "0.50",
        "usd_foil": None,
        "usd_etched": None,
        "eur": "0.40",
        "eur_foil": None,
    },
}

NON_COMMANDER_CARD = {
    "id": "ghi-789-banned",
    "oracle_id": "oracle-banned-card",
    "name": "Banned Card",
    "type_line": "Creature",
    "oracle_text": "Too powerful for Commander.",
    "mana_cost": "{B}",
    "cmc": 1.0,
    "colors": ["B"],
    "color_identity": ["B"],
    "keywords": [],
    "legalities": {"commander": "banned", "brawl": "banned"},
    "set": "xxx",
    "collector_number": "1",
    "lang": "en",
    "rarity": "rare",
    "finishes": ["nonfoil"],
    "released_at": "2024-01-01",
    "promo": False,
    "reprint": False,
    "updated_at": "2024-01-15",
    "prices": {"usd": "1.00"},
}

SOL_RING_ALT_PRINTING = {
    **SAMPLE_CARD_SOL_RING,
    "id": "xyz-999-sol-alt",
    "set": "cmd",
    "collector_number": "100",
    "tcgplayer_id": 99999,
    "prices": {"usd": "2.00"},
}

BULK_DATA_CATALOG = [
    {
        "type": "oracle_cards",
        "download_uri": "https://example.com/oracle.json",
    },
    {
        "type": "default_cards",
        "download_uri": "https://example.com/default.json",
    },
]


# --- SyncResult tests ---


class TestSyncResult:
    def test_default_values(self):
        result = SyncResult()
        assert result.cards_added == 0
        assert result.cards_updated == 0
        assert result.printings_added == 0
        assert result.prices_added == 0
        assert result.duration_seconds == 0.0
        assert result.errors == []

    def test_success_when_no_errors(self):
        result = SyncResult(cards_added=100)
        assert result.success is True

    def test_failure_when_errors(self):
        result = SyncResult(errors=["something went wrong"])
        assert result.success is False

    def test_summary_includes_counts(self):
        result = SyncResult(
            cards_added=100,
            printings_added=150,
            prices_added=300,
            duration_seconds=5.5,
        )
        summary = result.summary()
        assert "Cards added: 100" in summary
        assert "Printings added: 150" in summary
        assert "Prices added: 300" in summary
        assert "5.5s" in summary

    def test_summary_includes_errors_count(self):
        result = SyncResult(errors=["err1", "err2"])
        summary = result.summary()
        assert "Errors: 2" in summary

    def test_summary_includes_updates_when_present(self):
        result = SyncResult(cards_added=50, cards_updated=10)
        summary = result.summary()
        assert "Cards updated: 10" in summary

    def test_summary_omits_updates_when_zero(self):
        result = SyncResult(cards_added=50)
        summary = result.summary()
        assert "updated" not in summary.lower()


# --- _extract_prices tests ---


class TestExtractPrices:
    def test_extracts_usd_nonfoil(self):
        prices = _extract_prices(SAMPLE_CARD_SOL_RING)
        usd_nonfoil = [
            p for p in prices
            if p["currency"] == "USD" and p["finish"] == "nonfoil"
        ]
        assert len(usd_nonfoil) == 1
        assert usd_nonfoil[0]["price"] == 3.50
        assert usd_nonfoil[0]["source"] == "scryfall"

    def test_extracts_usd_foil(self):
        prices = _extract_prices(SAMPLE_CARD_SOL_RING)
        usd_foil = [
            p for p in prices
            if p["currency"] == "USD" and p["finish"] == "foil"
        ]
        assert len(usd_foil) == 1
        assert usd_foil[0]["price"] == 5.00

    def test_extracts_eur_prices(self):
        prices = _extract_prices(SAMPLE_CARD_SOL_RING)
        eur_prices = [p for p in prices if p["currency"] == "EUR"]
        assert len(eur_prices) == 2

    def test_skips_none_values(self):
        card = {
            "prices": {
                "usd": None,
                "usd_foil": None,
                "eur": None,
                "eur_foil": None,
            }
        }
        assert _extract_prices(card) == []

    def test_skips_missing_prices_key(self):
        assert _extract_prices({}) == []

    def test_handles_invalid_price_string(self):
        card = {"prices": {"usd": "not-a-number"}}
        assert _extract_prices(card) == []

    def test_total_count_for_sol_ring(self):
        # Sol Ring has: usd, usd_foil, eur, eur_foil (usd_etched is None)
        prices = _extract_prices(SAMPLE_CARD_SOL_RING)
        assert len(prices) == 4

    def test_command_tower_prices(self):
        # Command Tower: usd + eur only (foils are None)
        prices = _extract_prices(SAMPLE_CARD_COMMAND_TOWER)
        assert len(prices) == 2


# --- _process_cards tests ---


class TestProcessCards:
    def test_inserts_commander_legal_cards(self):
        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards(
                [SAMPLE_CARD_SOL_RING, SAMPLE_CARD_COMMAND_TOWER],
                db, result, None,
            )

            assert result.cards_added == 2
            assert result.printings_added == 2
            assert result.prices_added > 0

            cursor = db.execute("SELECT COUNT(*) as cnt FROM cards")
            assert cursor.fetchone()["cnt"] == 2

    def test_skips_non_commander_legal_cards(self):
        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards([NON_COMMANDER_CARD], db, result, None)

            assert result.cards_added == 0
            assert result.printings_added == 0

            cursor = db.execute("SELECT COUNT(*) as cnt FROM cards")
            assert cursor.fetchone()["cnt"] == 0

    def test_deduplicates_cards_by_oracle_id(self):
        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards(
                [SAMPLE_CARD_SOL_RING, SOL_RING_ALT_PRINTING],
                db, result, None,
            )

            assert result.cards_added == 1  # same oracle_id
            assert result.printings_added == 2  # different scryfall_ids

            cursor = db.execute("SELECT COUNT(*) as cnt FROM cards")
            assert cursor.fetchone()["cnt"] == 1

            cursor = db.execute("SELECT COUNT(*) as cnt FROM printings")
            assert cursor.fetchone()["cnt"] == 2

    def test_links_printings_to_correct_card(self):
        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards(
                [SAMPLE_CARD_SOL_RING, SAMPLE_CARD_COMMAND_TOWER],
                db, result, None,
            )

            cursor = db.execute(
                "SELECT p.card_id, c.name "
                "FROM printings p JOIN cards c ON p.card_id = c.id "
                "ORDER BY c.name"
            )
            rows = cursor.fetchall()
            assert len(rows) == 2
            names = [r["name"] for r in rows]
            assert "Command Tower" in names
            assert "Sol Ring" in names

    def test_inserts_prices_for_each_card(self):
        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result, None)

            cursor = db.execute("SELECT * FROM prices ORDER BY currency, finish")
            prices = [dict(row) for row in cursor.fetchall()]

            assert len(prices) == 4  # usd, usd_foil, eur, eur_foil

            usd_nonfoil = [
                p for p in prices
                if p["currency"] == "USD" and p["finish"] == "nonfoil"
            ]
            assert len(usd_nonfoil) == 1
            assert usd_nonfoil[0]["price"] == 3.50
            assert usd_nonfoil[0]["source"] == "scryfall"

    def test_handles_malformed_card_data(self):
        # Card that triggers ValueError in parse_scryfall_card (bad cmc)
        bad_card = {
            "name": "Bad Card",
            "cmc": "not-a-number",
            "legalities": {"commander": "legal"},
        }
        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards(
                [SAMPLE_CARD_SOL_RING, bad_card], db, result, None,
            )

            assert result.cards_added == 1
            assert len(result.errors) >= 1

    def test_invokes_progress_callback(self):
        calls = []

        def cb(stage: str, current: int, total: int) -> None:
            calls.append((stage, current, total))

        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result, cb)

        assert len(calls) > 0
        assert calls[0][0] == "Processing cards"

    def test_stops_after_too_many_errors(self):
        bad_cards = [
            {"name": f"Bad {i}", "cmc": "broken",
             "legalities": {"commander": "legal"}}
            for i in range(150)
        ]

        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards(bad_cards, db, result, None)

            # Should stop at 101 errors + 1 "aborting" message
            assert len(result.errors) <= 102

    def test_idempotent_reprocessing(self):
        """Processing the same data twice should not duplicate cards."""
        with Database(":memory:") as db:
            result1 = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result1, None)

            result2 = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result2, None)

            # Second run: card already exists, printing already exists
            assert result2.cards_added == 0
            assert result2.printings_added == 0

            cursor = db.execute("SELECT COUNT(*) as cnt FROM cards")
            assert cursor.fetchone()["cnt"] == 1

    def test_prices_replaced_on_resync(self):
        """Re-syncing should replace old prices, not duplicate them."""
        with Database(":memory:") as db:
            result1 = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result1, None)
            first_price_count = result1.prices_added

            result2 = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result2, None)

            # Price count in DB should not grow
            cursor = db.execute("SELECT COUNT(*) as cnt FROM prices")
            total_prices = cursor.fetchone()["cnt"]
            assert total_prices == first_price_count

    def test_mixed_legal_and_illegal_cards(self):
        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards(
                [SAMPLE_CARD_SOL_RING, NON_COMMANDER_CARD,
                 SAMPLE_CARD_COMMAND_TOWER],
                db, result, None,
            )

            assert result.cards_added == 2  # Only legal cards
            assert result.printings_added == 2

    def test_card_data_stored_correctly(self):
        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result, None)

            cursor = db.execute("SELECT * FROM cards WHERE name = 'Sol Ring'")
            card = dict(cursor.fetchone())
            assert card["oracle_id"] == "oracle-sol-ring"
            assert card["type_line"] == "Artifact"
            assert card["cmc"] == 1.0
            assert card["legal_commander"] == 1

    def test_printing_data_stored_correctly(self):
        with Database(":memory:") as db:
            result = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result, None)

            cursor = db.execute(
                "SELECT * FROM printings WHERE scryfall_id = 'abc-123-sol'"
            )
            printing = dict(cursor.fetchone())
            assert printing["set_code"] == "c21"
            assert printing["collector_number"] == "263"
            assert printing["rarity"] == "uncommon"
            assert printing["tcgplayer_id"] == 12345


# --- SyncService integration tests (mocked network) ---


class TestSyncServiceFullSync:
    @patch("mtg_deck_maker.services.sync_service.fetch_combos", new_callable=AsyncMock, return_value=[])
    @patch("mtg_deck_maker.services.sync_service.SyncService._download_bulk_json")
    @patch("mtg_deck_maker.services.sync_service.ScryfallClient")
    def test_full_sync_succeeds(self, mock_scryfall_cls, mock_download, _mock_combos, tmp_path):
        db_path = tmp_path / "test.db"

        # Mock ScryfallClient
        mock_scryfall = AsyncMock()
        mock_scryfall.get_bulk_data.return_value = BULK_DATA_CATALOG
        mock_scryfall_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_scryfall
        )
        mock_scryfall_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock download to return sample data
        mock_download.return_value = [
            SAMPLE_CARD_SOL_RING, SAMPLE_CARD_COMMAND_TOWER,
        ]

        service = SyncService(db_path=db_path)
        result = service.sync(full=True)

        assert result.success
        assert result.cards_added == 2
        assert result.printings_added == 2
        assert result.prices_added > 0
        assert result.duration_seconds > 0

    @patch("mtg_deck_maker.services.sync_service.fetch_combos", new_callable=AsyncMock, return_value=[])
    @patch("mtg_deck_maker.services.sync_service.SyncService._download_bulk_json")
    @patch("mtg_deck_maker.services.sync_service.ScryfallClient")
    def test_full_sync_with_progress_callback(
        self, mock_scryfall_cls, mock_download, _mock_combos, tmp_path
    ):
        db_path = tmp_path / "test.db"

        mock_scryfall = AsyncMock()
        mock_scryfall.get_bulk_data.return_value = BULK_DATA_CATALOG
        mock_scryfall_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_scryfall
        )
        mock_scryfall_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_download.return_value = [SAMPLE_CARD_SOL_RING]

        calls = []

        def cb(stage: str, current: int, total: int) -> None:
            calls.append((stage, current, total))

        service = SyncService(db_path=db_path)
        service.sync(full=True, progress_callback=cb)

        # Should have received progress callbacks
        stages = [c[0] for c in calls]
        assert "Fetching bulk data catalog" in stages
        assert "Processing cards" in stages

    @patch("mtg_deck_maker.services.sync_service.ScryfallClient")
    def test_full_sync_handles_catalog_error(self, mock_scryfall_cls, tmp_path):
        db_path = tmp_path / "test.db"

        mock_scryfall = AsyncMock()
        mock_scryfall.get_bulk_data.side_effect = Exception("Network error")
        mock_scryfall_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_scryfall
        )
        mock_scryfall_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = SyncService(db_path=db_path)
        result = service.sync(full=True)

        assert not result.success
        assert any("catalog" in e.lower() for e in result.errors)

    @patch("mtg_deck_maker.services.sync_service.ScryfallClient")
    def test_full_sync_handles_missing_bulk_type(self, mock_scryfall_cls, tmp_path):
        db_path = tmp_path / "test.db"

        mock_scryfall = AsyncMock()
        # Return catalog without default_cards type
        mock_scryfall.get_bulk_data.return_value = [
            {"type": "oracle_cards", "download_uri": "https://example.com/oracle.json"},
        ]
        mock_scryfall_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_scryfall
        )
        mock_scryfall_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = SyncService(db_path=db_path)
        result = service.sync(full=True)

        assert not result.success
        assert any("default_cards" in e for e in result.errors)

    @patch("mtg_deck_maker.services.sync_service.SyncService._download_bulk_json")
    @patch("mtg_deck_maker.services.sync_service.ScryfallClient")
    def test_full_sync_handles_download_error(
        self, mock_scryfall_cls, mock_download, tmp_path
    ):
        db_path = tmp_path / "test.db"

        mock_scryfall = AsyncMock()
        mock_scryfall.get_bulk_data.return_value = BULK_DATA_CATALOG
        mock_scryfall_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_scryfall
        )
        mock_scryfall_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_download.side_effect = Exception("Download failed")

        service = SyncService(db_path=db_path)
        result = service.sync(full=True)

        assert not result.success
        assert any("download" in e.lower() for e in result.errors)


class TestSyncServiceIncrementalSync:
    @patch("mtg_deck_maker.services.sync_service.ScryfallClient")
    def test_incremental_sync_no_cards_in_db(self, mock_scryfall_cls, tmp_path):
        db_path = tmp_path / "test.db"

        mock_scryfall = AsyncMock()
        mock_scryfall_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_scryfall
        )
        mock_scryfall_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = SyncService(db_path=db_path)
        result = service.sync(full=False)

        assert not result.success
        assert any("full sync" in e.lower() for e in result.errors)

    @patch("mtg_deck_maker.services.sync_service.ScryfallClient")
    def test_incremental_sync_with_existing_data(self, mock_scryfall_cls, tmp_path):
        db_path = tmp_path / "test.db"

        # Seed database first
        with Database(db_path) as db:
            result_seed = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result_seed, None)

        # Set up mock for incremental search
        mock_scryfall = AsyncMock()
        mock_scryfall.search_cards_all.return_value = [
            SAMPLE_CARD_COMMAND_TOWER,
        ]
        mock_scryfall_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_scryfall
        )
        mock_scryfall_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = SyncService(db_path=db_path)
        result = service.sync(full=False)

        assert result.success
        assert result.cards_added == 1  # Command Tower added
        mock_scryfall.search_cards_all.assert_called_once()

    @patch("mtg_deck_maker.services.sync_service.ScryfallClient")
    def test_incremental_sync_no_updates(self, mock_scryfall_cls, tmp_path):
        db_path = tmp_path / "test.db"

        # Seed database
        with Database(db_path) as db:
            result_seed = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result_seed, None)

        # Search returns empty
        mock_scryfall = AsyncMock()
        mock_scryfall.search_cards_all.return_value = []
        mock_scryfall_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_scryfall
        )
        mock_scryfall_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = SyncService(db_path=db_path)
        result = service.sync(full=False)

        assert result.success
        assert result.cards_added == 0

    @patch("mtg_deck_maker.services.sync_service.ScryfallClient")
    def test_incremental_sync_handles_search_error(
        self, mock_scryfall_cls, tmp_path
    ):
        db_path = tmp_path / "test.db"

        # Seed database
        with Database(db_path) as db:
            result_seed = SyncResult()
            _process_cards([SAMPLE_CARD_SOL_RING], db, result_seed, None)

        # Search raises exception
        mock_scryfall = AsyncMock()
        mock_scryfall.search_cards_all.side_effect = Exception("Search failed")
        mock_scryfall_cls.return_value.__aenter__ = AsyncMock(
            return_value=mock_scryfall
        )
        mock_scryfall_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        service = SyncService(db_path=db_path)
        result = service.sync(full=False)

        # Gracefully handles - returns empty result, no errors
        assert result.success
        assert result.cards_added == 0


class TestSyncServiceConfig:
    def test_uses_default_db_path_from_config(self):
        service = SyncService()
        assert "mtg_deck_maker.db" in str(service._db_path)

    def test_accepts_custom_db_path(self, tmp_path):
        custom_path = tmp_path / "custom.db"
        service = SyncService(db_path=custom_path)
        assert service._db_path == custom_path

    def test_accepts_memory_db_path(self):
        service = SyncService(db_path=":memory:")
        assert str(service._db_path) == ":memory:"
