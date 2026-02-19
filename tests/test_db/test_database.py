"""Tests for the Database connection manager and schema versioning."""

from __future__ import annotations

import sqlite3

import pytest

from mtg_deck_maker.db.database import CURRENT_SCHEMA_VERSION, Database


class TestDatabaseConnection:
    """Test database connection lifecycle."""

    def test_connect_in_memory(self) -> None:
        db = Database(":memory:")
        db.connect()
        assert db.connection is not None
        db.close()

    def test_context_manager(self) -> None:
        with Database(":memory:") as db:
            assert db.connection is not None

    def test_connection_error_without_connect(self) -> None:
        db = Database(":memory:")
        with pytest.raises(RuntimeError, match="Database not connected"):
            _ = db.connection

    def test_close_and_reconnect(self) -> None:
        db = Database(":memory:")
        db.connect()
        db.close()
        with pytest.raises(RuntimeError):
            _ = db.connection
        db.connect()
        assert db.connection is not None
        db.close()

    def test_connect_idempotent(self) -> None:
        db = Database(":memory:")
        db.connect()
        conn1 = db.connection
        db.connect()  # Should not create new connection
        assert db.connection is conn1
        db.close()

    def test_file_based_database(self, tmp_path) -> None:
        db_path = tmp_path / "test.db"
        with Database(db_path) as db:
            cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row["name"] for row in cursor.fetchall()]
            assert "cards" in tables
        assert db_path.exists()


class TestSchemaCreation:
    """Test that the schema is properly created."""

    def test_all_tables_created(self, db: Database) -> None:
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cursor.fetchall()}
        expected_tables = {
            "cards",
            "printings",
            "card_faces",
            "prices",
            "card_tags",
            "commander_pairs",
            "decks",
            "deck_cards",
            "id_mappings",
            "schema_version",
        }
        assert expected_tables.issubset(tables)

    def test_indexes_created(self, db: Database) -> None:
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = {row["name"] for row in cursor.fetchall()}
        expected_indexes = {
            "idx_cards_name",
            "idx_cards_color_identity",
            "idx_cards_legal_commander",
            "idx_printings_card_id",
            "idx_printings_tcgplayer_id",
            "idx_prices_printing_id",
            "idx_prices_retrieved_at",
            "idx_card_tags_card_id",
            "idx_card_tags_tag",
        }
        assert expected_indexes.issubset(indexes)

    def test_foreign_keys_enabled(self, db: Database) -> None:
        cursor = db.execute("PRAGMA foreign_keys")
        row = cursor.fetchone()
        assert row[0] == 1


class TestSchemaVersioning:
    """Test schema version tracking."""

    def test_schema_version_recorded(self, db: Database) -> None:
        version = db.get_schema_version()
        assert version == CURRENT_SCHEMA_VERSION

    def test_schema_version_has_timestamp(self, db: Database) -> None:
        cursor = db.execute(
            "SELECT applied_at FROM schema_version WHERE version = ?",
            (CURRENT_SCHEMA_VERSION,),
        )
        row = cursor.fetchone()
        assert row is not None
        assert row["applied_at"] != ""

    def test_schema_not_reapplied(self, db: Database) -> None:
        """Schema should not be reapplied on second connect."""
        # Insert a test row
        db.execute(
            "INSERT INTO cards (oracle_id, name) VALUES (?, ?)",
            ("test-version", "Version Test Card"),
        )
        db.commit()

        # Reconnect (simulate by calling _initialize_schema again)
        # Since version matches, it should not re-run schema
        db._initialize_schema()

        cursor = db.execute(
            "SELECT * FROM cards WHERE oracle_id = ?", ("test-version",)
        )
        row = cursor.fetchone()
        assert row is not None


class TestDatabaseOperations:
    """Test basic database operations."""

    def test_execute_select(self, db: Database) -> None:
        cursor = db.execute("SELECT 1 as num")
        row = cursor.fetchone()
        assert row["num"] == 1

    def test_execute_with_params(self, db: Database) -> None:
        db.execute(
            "INSERT INTO cards (oracle_id, name) VALUES (?, ?)",
            ("test-id", "Test Card"),
        )
        db.commit()
        cursor = db.execute(
            "SELECT name FROM cards WHERE oracle_id = ?", ("test-id",)
        )
        row = cursor.fetchone()
        assert row["name"] == "Test Card"

    def test_executemany(self, db: Database) -> None:
        rows = [
            ("id1", "Card 1"),
            ("id2", "Card 2"),
            ("id3", "Card 3"),
        ]
        db.executemany(
            "INSERT INTO cards (oracle_id, name) VALUES (?, ?)", rows
        )
        db.commit()
        cursor = db.execute("SELECT COUNT(*) as cnt FROM cards")
        assert cursor.fetchone()["cnt"] == 3
