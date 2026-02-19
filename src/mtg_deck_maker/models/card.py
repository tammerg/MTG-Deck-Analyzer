"""Card data model representing an oracle-level Magic: The Gathering card."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Card:
    """Oracle-level card entity with unique rules text.

    Represents the logical card independent of any specific printing.
    """

    oracle_id: str
    name: str
    type_line: str = ""
    oracle_text: str = ""
    mana_cost: str = ""
    cmc: float = 0.0
    colors: list[str] = field(default_factory=list)
    color_identity: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    edhrec_rank: int | None = None
    legal_commander: bool = False
    legal_brawl: bool = False
    updated_at: str = ""
    id: int | None = None

    @property
    def colors_str(self) -> str:
        """Return colors as a comma-separated string for DB storage."""
        return ",".join(self.colors)

    @property
    def color_identity_str(self) -> str:
        """Return color identity as a comma-separated string for DB storage."""
        return ",".join(self.color_identity)

    @property
    def keywords_str(self) -> str:
        """Return keywords as a comma-separated string for DB storage."""
        return ",".join(self.keywords)

    @property
    def is_colorless(self) -> bool:
        """Check if the card has no color identity."""
        return len(self.color_identity) == 0

    @property
    def is_land(self) -> bool:
        """Check if the card is a land."""
        return "Land" in self.type_line

    @property
    def is_creature(self) -> bool:
        """Check if the card is a creature."""
        return "Creature" in self.type_line

    def to_db_row(self) -> dict:
        """Convert to a dict suitable for database insertion."""
        return {
            "oracle_id": self.oracle_id,
            "name": self.name,
            "type_line": self.type_line,
            "oracle_text": self.oracle_text,
            "mana_cost": self.mana_cost,
            "cmc": self.cmc,
            "colors": self.colors_str,
            "color_identity": self.color_identity_str,
            "keywords": self.keywords_str,
            "edhrec_rank": self.edhrec_rank,
            "legal_commander": int(self.legal_commander),
            "legal_brawl": int(self.legal_brawl),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_db_row(cls, row: dict) -> Card:
        """Create a Card instance from a database row dict."""
        colors_raw = row.get("colors", "")
        color_identity_raw = row.get("color_identity", "")
        keywords_raw = row.get("keywords", "")

        return cls(
            id=row.get("id"),
            oracle_id=row["oracle_id"],
            name=row["name"],
            type_line=row.get("type_line", ""),
            oracle_text=row.get("oracle_text", ""),
            mana_cost=row.get("mana_cost", ""),
            cmc=float(row.get("cmc", 0.0)),
            colors=[c for c in colors_raw.split(",") if c] if colors_raw else [],
            color_identity=(
                [c for c in color_identity_raw.split(",") if c]
                if color_identity_raw
                else []
            ),
            keywords=(
                [k for k in keywords_raw.split(",") if k]
                if keywords_raw
                else []
            ),
            edhrec_rank=row.get("edhrec_rank"),
            legal_commander=bool(row.get("legal_commander", 0)),
            legal_brawl=bool(row.get("legal_brawl", 0)),
            updated_at=row.get("updated_at", ""),
        )
