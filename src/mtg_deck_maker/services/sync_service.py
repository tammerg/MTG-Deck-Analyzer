"""Sync service for downloading and updating card data from Scryfall.

Downloads bulk card data from Scryfall's bulk-data endpoint and populates
the local SQLite database with cards, printings, and cached prices.
"""

from __future__ import annotations

import asyncio
import json
import logging
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

from mtg_deck_maker.api.commanderspellbook import (
    CommanderSpellbookError,
    fetch_combos,
    load_fallback_combos,
)
from mtg_deck_maker.api.scryfall import ScryfallClient, parse_scryfall_card
from mtg_deck_maker.config import AppConfig, load_config
from mtg_deck_maker.db.combo_repo import ComboRepository
from mtg_deck_maker.db.database import Database

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000
BULK_DATA_TYPE = "default_cards"


@dataclass(slots=True)
class SyncResult:
    """Statistics from a sync operation."""

    cards_added: int = 0
    cards_updated: int = 0
    printings_added: int = 0
    prices_added: int = 0
    combos_synced: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """True if no errors occurred."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """Return a human-readable summary string."""
        lines = [f"Cards added: {self.cards_added}"]
        if self.cards_updated:
            lines.append(f"Cards updated: {self.cards_updated}")
        lines.append(f"Printings added: {self.printings_added}")
        lines.append(f"Prices added: {self.prices_added}")
        if self.combos_synced:
            lines.append(f"Combos synced: {self.combos_synced}")
        lines.append(f"Duration: {self.duration_seconds:.1f}s")
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
        return "\n".join(lines)


def _extract_prices(raw_card: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract price records from a Scryfall card JSON object.

    Args:
        raw_card: A Scryfall card dict with a "prices" key.

    Returns:
        List of price record dicts with keys: price, finish, currency, source.
    """
    prices_raw = raw_card.get("prices", {})
    records: list[dict[str, Any]] = []
    price_keys = [
        ("usd", "nonfoil", "USD"),
        ("usd_foil", "foil", "USD"),
        ("usd_etched", "etched", "USD"),
        ("eur", "nonfoil", "EUR"),
        ("eur_foil", "foil", "EUR"),
    ]

    for key, finish, currency in price_keys:
        val = prices_raw.get(key)
        if val is not None:
            try:
                records.append({
                    "price": float(val),
                    "finish": finish,
                    "currency": currency,
                    "source": "scryfall",
                })
            except (ValueError, TypeError):
                continue

    return records


def _process_cards(
    card_data: list[dict[str, Any]],
    db: Database,
    result: SyncResult,
    callback: Callable[[str, int, int], None] | None,
) -> None:
    """Parse and insert cards, printings, and prices into the database.

    Uses raw SQL with batched commits for performance during bulk operations.

    Args:
        card_data: List of Scryfall card JSON dicts.
        db: Active Database connection.
        result: SyncResult to accumulate statistics into.
        callback: Optional progress callback(stage, current, total).
    """
    total = len(card_data)
    oracle_id_cache: dict[str, int] = {}
    now = datetime.now(timezone.utc).isoformat()

    for i, raw_card in enumerate(card_data):
        if callback and i % BATCH_SIZE == 0:
            callback("Processing cards", i, total)

        try:
            card, printing = parse_scryfall_card(raw_card)

            if not card.legal_commander:
                continue

            # Upsert card by oracle_id
            if card.oracle_id in oracle_id_cache:
                card_db_id = oracle_id_cache[card.oracle_id]
            else:
                cursor = db.execute(
                    "SELECT id FROM cards WHERE oracle_id = ?",
                    (card.oracle_id,),
                )
                existing = cursor.fetchone()
                if existing:
                    card_db_id = existing["id"]
                    oracle_id_cache[card.oracle_id] = card_db_id
                else:
                    row = card.to_db_row()
                    cursor = db.execute(
                        """INSERT INTO cards (
                            oracle_id, name, type_line, oracle_text,
                            mana_cost, cmc, colors, color_identity,
                            keywords, edhrec_rank, legal_commander,
                            legal_brawl, updated_at
                        ) VALUES (
                            :oracle_id, :name, :type_line, :oracle_text,
                            :mana_cost, :cmc, :colors, :color_identity,
                            :keywords, :edhrec_rank, :legal_commander,
                            :legal_brawl, :updated_at
                        )""",
                        row,
                    )
                    card_db_id = cursor.lastrowid
                    oracle_id_cache[card.oracle_id] = card_db_id
                    result.cards_added += 1

            # Insert printing
            printing.card_id = card_db_id
            cursor = db.execute(
                "SELECT id FROM printings WHERE scryfall_id = ?",
                (printing.scryfall_id,),
            )
            existing_printing = cursor.fetchone()
            if existing_printing:
                printing_db_id = existing_printing["id"]
            else:
                row = printing.to_db_row()
                cursor = db.execute(
                    """INSERT OR IGNORE INTO printings (
                        scryfall_id, card_id, set_code, collector_number,
                        lang, rarity, finishes, tcgplayer_id,
                        cardmarket_id, released_at, is_promo, is_reprint
                    ) VALUES (
                        :scryfall_id, :card_id, :set_code,
                        :collector_number, :lang, :rarity, :finishes,
                        :tcgplayer_id, :cardmarket_id, :released_at,
                        :is_promo, :is_reprint
                    )""",
                    row,
                )
                printing_db_id = cursor.lastrowid
                result.printings_added += 1

            # Upsert prices - delete stale then insert fresh
            price_records = _extract_prices(raw_card)
            if price_records:
                db.execute(
                    "DELETE FROM prices WHERE printing_id = ? AND source = 'scryfall'",
                    (printing_db_id,),
                )
                for price_info in price_records:
                    db.execute(
                        """INSERT INTO prices (
                            printing_id, source, currency, price, finish,
                            retrieved_at
                        ) VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            printing_db_id,
                            price_info["source"],
                            price_info["currency"],
                            price_info["price"],
                            price_info["finish"],
                            now,
                        ),
                    )
                    result.prices_added += 1

        except Exception as exc:
            card_name = raw_card.get("name", "unknown")
            result.errors.append(f"Error processing '{card_name}': {exc}")
            if len(result.errors) > 100:
                result.errors.append("Too many errors, aborting")
                break

        # Batch commit for performance
        if i % BATCH_SIZE == 0:
            db.commit()

    # Final commit
    db.commit()


class SyncService:
    """Service for syncing the local card database with Scryfall data.

    Downloads Scryfall's bulk card data and populates the local SQLite
    database with cards, printings, and cached prices.

    Args:
        db_path: Path to the SQLite database. Defaults to config data_dir.
        config: Application config. Defaults to load_config().
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        config: AppConfig | None = None,
    ) -> None:
        self._config = config or load_config()
        if db_path is None:
            self._db_path: str | Path = (
                Path(self._config.general.data_dir) / "mtg_deck_maker.db"
            )
        else:
            self._db_path = db_path

    def sync(
        self,
        full: bool = False,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> SyncResult:
        """Run a sync operation.

        Args:
            full: If True, download full bulk data from Scryfall.
                If False, perform incremental update.
            progress_callback: Optional callback(stage, current, total)
                for progress reporting.

        Returns:
            SyncResult with statistics about the operation.
        """
        return asyncio.run(self._run_sync(full, progress_callback))

    async def _run_sync(
        self,
        full: bool,
        callback: Callable[[str, int, int], None] | None,
    ) -> SyncResult:
        start = time.monotonic()

        with Database(self._db_path) as db:
            async with ScryfallClient() as scryfall:
                if full:
                    result = await self._full_sync(scryfall, db, callback)
                else:
                    result = await self._incremental_sync(
                        scryfall, db, callback
                    )

        result.duration_seconds = time.monotonic() - start
        return result

    async def _full_sync(
        self,
        scryfall: ScryfallClient,
        db: Database,
        callback: Callable[[str, int, int], None] | None,
    ) -> SyncResult:
        """Download Scryfall bulk data and populate the database."""
        result = SyncResult()

        # Step 1: Get bulk data catalog
        if callback:
            callback("Fetching bulk data catalog", 0, 0)

        try:
            bulk_items = await scryfall.get_bulk_data()
        except Exception as exc:
            result.errors.append(
                f"Failed to fetch bulk data catalog: {exc}"
            )
            return result

        download_url = None
        for item in bulk_items:
            if item.get("type") == BULK_DATA_TYPE:
                download_url = item.get("download_uri")
                break

        if not download_url:
            result.errors.append(
                f"Bulk data type '{BULK_DATA_TYPE}' not found in catalog"
            )
            return result

        # Step 2: Download bulk data
        if callback:
            callback("Downloading bulk card data", 0, 0)

        try:
            card_data = await self._download_bulk_json(
                download_url, callback
            )
        except Exception as exc:
            result.errors.append(f"Failed to download bulk data: {exc}")
            return result

        # Step 3: Process cards into database
        if callback:
            callback("Processing cards", 0, len(card_data))

        _process_cards(card_data, db, result, callback)

        # Step 4: Sync combos from CommanderSpellbook
        await self._sync_combos(db, result, callback)

        return result

    async def _incremental_sync(
        self,
        scryfall: ScryfallClient,
        db: Database,
        callback: Callable[[str, int, int], None] | None,
    ) -> SyncResult:
        """Search for recently updated cards and sync them."""
        result = SyncResult()

        # Find the most recent updated_at in our database
        cursor = db.execute(
            "SELECT MAX(updated_at) as last_update FROM cards"
        )
        row = cursor.fetchone()
        last_update = (
            row["last_update"] if row and row["last_update"] else None
        )

        if last_update is None:
            result.errors.append(
                "No cards in database. Run full sync first: "
                "mtg-deck sync --full"
            )
            return result

        if callback:
            callback("Searching for updated cards", 0, 0)

        try:
            date_str = last_update[:10]  # YYYY-MM-DD
            query = f"date>={date_str} f:commander"
            updated_cards = await scryfall.search_cards_all(query)
        except Exception as exc:
            logger.info("Incremental search returned no results: %s", exc)
            updated_cards = []

        if not updated_cards:
            return result

        if callback:
            callback("Processing updated cards", 0, len(updated_cards))

        _process_cards(updated_cards, db, result, callback)
        return result

    async def _sync_combos(
        self,
        db: Database,
        result: SyncResult,
        callback: Callable[[str, int, int], None] | None,
    ) -> None:
        """Fetch and store combo data from CommanderSpellbook.

        Attempts the API first; falls back to the bundled static JSON file
        if the API is unavailable.

        Args:
            db: Active Database connection.
            result: SyncResult to accumulate statistics into.
            callback: Optional progress callback.
        """
        if callback:
            callback("Syncing combos", 0, 0)

        combo_repo = ComboRepository(db)
        combo_repo.create_tables()

        try:
            combos = await fetch_combos()
            logger.info(
                "Fetched %d combos from CommanderSpellbook API", len(combos)
            )
        except CommanderSpellbookError as exc:
            logger.warning(
                "CommanderSpellbook API unavailable (%s), using fallback",
                exc,
            )
            combos = load_fallback_combos()
            logger.info("Loaded %d combos from fallback file", len(combos))

        for i, combo in enumerate(combos):
            combo_repo.upsert_combo(combo)
            if callback and i % 500 == 0:
                callback("Syncing combos", i, len(combos))

        result.combos_synced = len(combos)

    async def _download_bulk_json(
        self,
        url: str,
        callback: Callable[[str, int, int], None] | None,
    ) -> list[dict[str, Any]]:
        """Download and parse a Scryfall bulk data JSON file.

        Streams the download to a temporary file, then parses it.

        Args:
            url: URL to the bulk data JSON file.
            callback: Optional progress callback.

        Returns:
            Parsed list of card dicts.
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(300.0),
            follow_redirects=True,
        ) as client:
            with tempfile.NamedTemporaryFile(
                suffix=".json", delete=False
            ) as tmp:
                tmp_path = Path(tmp.name)

                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    total = int(
                        response.headers.get("content-length", 0)
                    )
                    downloaded = 0

                    async for chunk in response.aiter_bytes(
                        chunk_size=65536
                    ):
                        tmp.write(chunk)
                        downloaded += len(chunk)
                        if callback and total:
                            callback("Downloading", downloaded, total)

        try:
            if callback:
                callback("Parsing JSON", 0, 0)
            with open(tmp_path) as f:
                data = json.load(f)
            return data
        finally:
            tmp_path.unlink(missing_ok=True)
