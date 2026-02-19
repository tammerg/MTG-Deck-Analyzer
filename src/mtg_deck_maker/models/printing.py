"""Printing data model representing a set-level Magic: The Gathering card printing."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Printing:
    """Set-level printing entity representing a unique physical card.

    A card can have many printings across different sets and variants.
    """

    scryfall_id: str
    card_id: int
    set_code: str
    collector_number: str
    lang: str = "en"
    rarity: str = ""
    finishes: list[str] = field(default_factory=list)
    tcgplayer_id: int | None = None
    cardmarket_id: int | None = None
    released_at: str = ""
    is_promo: bool = False
    is_reprint: bool = False
    id: int | None = None

    @property
    def finishes_str(self) -> str:
        """Return finishes as a comma-separated string for DB storage."""
        return ",".join(self.finishes)

    def to_db_row(self) -> dict:
        """Convert to a dict suitable for database insertion."""
        return {
            "scryfall_id": self.scryfall_id,
            "card_id": self.card_id,
            "set_code": self.set_code,
            "collector_number": self.collector_number,
            "lang": self.lang,
            "rarity": self.rarity,
            "finishes": self.finishes_str,
            "tcgplayer_id": self.tcgplayer_id,
            "cardmarket_id": self.cardmarket_id,
            "released_at": self.released_at,
            "is_promo": int(self.is_promo),
            "is_reprint": int(self.is_reprint),
        }

    @classmethod
    def from_db_row(cls, row: dict) -> Printing:
        """Create a Printing instance from a database row dict."""
        finishes_raw = row.get("finishes", "")

        return cls(
            id=row.get("id"),
            scryfall_id=row["scryfall_id"],
            card_id=row["card_id"],
            set_code=row["set_code"],
            collector_number=row["collector_number"],
            lang=row.get("lang", "en"),
            rarity=row.get("rarity", ""),
            finishes=(
                [f for f in finishes_raw.split(",") if f]
                if finishes_raw
                else []
            ),
            tcgplayer_id=row.get("tcgplayer_id"),
            cardmarket_id=row.get("cardmarket_id"),
            released_at=row.get("released_at", ""),
            is_promo=bool(row.get("is_promo", 0)),
            is_reprint=bool(row.get("is_reprint", 0)),
        )
