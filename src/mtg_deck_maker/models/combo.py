"""Combo data model representing a verified card combo from CommanderSpellbook."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Combo:
    """A verified card combo from CommanderSpellbook.

    Represents a known interaction between two or more cards that produces
    a powerful or infinite effect.
    """

    combo_id: str
    card_names: list[str]
    result: str
    color_identity: list[str]
    prerequisite: str = ""
    description: str = ""
