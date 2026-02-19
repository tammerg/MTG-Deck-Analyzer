"""Deck and DeckCard data models for representing Commander decklists."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DeckCard:
    """A single card entry within a deck."""

    card_id: int
    quantity: int = 1
    category: str = ""
    is_commander: bool = False
    is_companion: bool = False
    # Denormalized fields for convenience (not stored in DB deck_cards table)
    card_name: str = ""
    cmc: float = 0.0
    colors: list[str] = field(default_factory=list)
    price: float = 0.0


@dataclass(slots=True)
class Deck:
    """A complete Commander decklist with metadata and analysis methods."""

    name: str
    cards: list[DeckCard] = field(default_factory=list)
    format: str = "commander"
    budget_target: float | None = None
    created_at: str = ""
    id: int | None = None

    def total_cards(self) -> int:
        """Return total number of cards in the deck (counting quantities)."""
        return sum(card.quantity for card in self.cards)

    def total_price(self) -> float:
        """Return total price of all cards in the deck."""
        return sum(card.price * card.quantity for card in self.cards)

    def average_cmc(self) -> float:
        """Return average converted mana cost of non-land cards.

        Lands (cmc == 0 and no mana cost) are excluded from the average.
        Only counts cards that have a positive CMC.
        """
        non_land_cards = [
            card for card in self.cards if card.cmc > 0
        ]
        if not non_land_cards:
            return 0.0
        total_cmc = sum(card.cmc * card.quantity for card in non_land_cards)
        total_count = sum(card.quantity for card in non_land_cards)
        return total_cmc / total_count

    def color_distribution(self) -> dict[str, int]:
        """Return count of cards per color across the deck.

        Each card contributes to all its colors. Colorless cards are
        counted under an empty string key.
        """
        distribution: dict[str, int] = {}
        for card in self.cards:
            if not card.colors:
                distribution[""] = distribution.get("", 0) + card.quantity
            else:
                for color in card.colors:
                    distribution[color] = (
                        distribution.get(color, 0) + card.quantity
                    )
        return distribution

    def commanders(self) -> list[DeckCard]:
        """Return the commander card(s) from the deck."""
        return [card for card in self.cards if card.is_commander]

    def companions(self) -> list[DeckCard]:
        """Return companion card(s) from the deck."""
        return [card for card in self.cards if card.is_companion]

    def mainboard(self) -> list[DeckCard]:
        """Return non-commander, non-companion cards."""
        return [
            card
            for card in self.cards
            if not card.is_commander and not card.is_companion
        ]
