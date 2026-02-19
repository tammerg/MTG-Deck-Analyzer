"""SQLite database connection manager with schema versioning."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

CURRENT_SCHEMA_VERSION = 1
DEFAULT_DB_PATH = Path("data/mtg_deck_maker.db")


class Database:
    """SQLite connection manager with automatic schema creation and versioning.

    Usage:
        with Database() as db:
            db.execute("SELECT * FROM cards")

        # Or for explicit lifecycle management:
        db = Database("/path/to/db")
        db.connect()
        ...
        db.close()
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize database manager.

        Args:
            db_path: Path to SQLite database file. Use ":memory:" for
                in-memory databases (useful for testing). Defaults to
                data/mtg_deck_maker.db.
        """
        if db_path is None:
            self.db_path = DEFAULT_DB_PATH
        elif str(db_path) == ":memory:":
            self.db_path = Path(":memory:")
        else:
            self.db_path = Path(db_path)

        self._conn: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the active database connection.

        Raises:
            RuntimeError: If no connection is active.
        """
        if self._conn is None:
            raise RuntimeError(
                "Database not connected. Use connect() or context manager."
            )
        return self._conn

    def connect(self) -> None:
        """Open database connection and ensure schema is initialized."""
        if self._conn is not None:
            return

        # Ensure parent directory exists for file-based databases
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        self._initialize_schema()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> Database:
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        self.close()

    def execute(
        self, sql: str, params: tuple | dict | None = None
    ) -> sqlite3.Cursor:
        """Execute a SQL statement with optional parameters.

        Args:
            sql: SQL statement to execute.
            params: Parameters for the SQL statement.

        Returns:
            The cursor after execution.
        """
        if params is None:
            return self.connection.execute(sql)
        return self.connection.execute(sql, params)

    def executemany(
        self, sql: str, params_seq: list[tuple] | list[dict]
    ) -> sqlite3.Cursor:
        """Execute a SQL statement against multiple parameter sets.

        Args:
            sql: SQL statement to execute.
            params_seq: Sequence of parameter sets.

        Returns:
            The cursor after execution.
        """
        return self.connection.executemany(sql, params_seq)

    def commit(self) -> None:
        """Commit the current transaction."""
        self.connection.commit()

    def get_schema_version(self) -> int:
        """Return the current schema version, or 0 if not initialized."""
        try:
            cursor = self.connection.execute(
                "SELECT MAX(version) FROM schema_version"
            )
            row = cursor.fetchone()
            if row and row[0] is not None:
                return int(row[0])
            return 0
        except sqlite3.OperationalError:
            # Table doesn't exist yet
            return 0

    def _initialize_schema(self) -> None:
        """Create or update the database schema."""
        current_version = self.get_schema_version()

        if current_version < CURRENT_SCHEMA_VERSION:
            schema_sql = self._load_schema_sql()
            self.connection.executescript(schema_sql)

            # Record the schema version
            now = datetime.now(timezone.utc).isoformat()
            self.connection.execute(
                "INSERT OR REPLACE INTO schema_version (version, applied_at) "
                "VALUES (?, ?)",
                (CURRENT_SCHEMA_VERSION, now),
            )
            self.connection.commit()

    def _load_schema_sql(self) -> str:
        """Load the SQL schema from the schema.sql file."""
        schema_path = Path(__file__).parent / "schema.sql"
        return schema_path.read_text()
