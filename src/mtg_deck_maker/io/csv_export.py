"""CSV export for Commander decklists.

Exports a Deck to CSV with full metadata columns and an appended summary section.
Uses only the Python stdlib csv module (no pandas).
"""

from __future__ import annotations

import csv
import io
from datetime import date

from mtg_deck_maker.models.card import Card
from mtg_deck_maker.models.deck import Deck, DeckCard


# Standard column headers for the exported CSV.
CSV_COLUMNS = [
    "Quantity",
    "Card Name",
    "Category",
    "Mana Cost",
    "CMC",
    "Type",
    "Price (USD)",
    "Set",
    "Set Code",
    "Notes",
]


def _build_card_row(
    deck_card: DeckCard,
    cards: dict[int, Card] | None,
    prices: dict[int, float] | None,
) -> list[str]:
    """Build a single CSV row for a DeckCard.

    Args:
        deck_card: The deck card entry to serialize.
        cards: Optional mapping of card_id -> Card for enriched data.
        prices: Optional mapping of card_id -> price in USD.

    Returns:
        A list of string values matching CSV_COLUMNS order.
    """
    card = cards.get(deck_card.card_id) if cards else None

    name = card.name if card else deck_card.card_name
    mana_cost = card.mana_cost if card else ""
    cmc_val = card.cmc if card else deck_card.cmc
    type_line = card.type_line if card else ""

    price_val = "N/A"
    if prices and deck_card.card_id in prices:
        price_val = f"{prices[deck_card.card_id]:.2f}"
    elif deck_card.price > 0:
        price_val = f"{deck_card.price:.2f}"

    notes = ""
    if deck_card.is_commander:
        notes = "Commander"
    elif deck_card.is_companion:
        notes = "Companion"

    return [
        str(deck_card.quantity),
        name,
        deck_card.category,
        mana_cost,
        f"{cmc_val:g}",
        type_line,
        price_val,
        "",  # Set name - not stored in DeckCard, left blank
        "",  # Set Code - not stored in DeckCard, left blank
        notes,
    ]


def _build_summary_rows(
    deck: Deck,
    prices: dict[int, float] | None,
) -> list[list[str]]:
    """Build the summary section rows appended after the card list.

    Args:
        deck: The deck to summarize.
        prices: Optional mapping of card_id -> price for total calculation.

    Returns:
        A list of rows (each a list of strings) for the summary section.
    """
    total_cards = deck.total_cards()

    # Compute total price from prices dict if available, otherwise from deck
    if prices:
        total_price = sum(
            prices.get(card.card_id, 0.0) * card.quantity
            for card in deck.cards
        )
    else:
        total_price = deck.total_price()

    avg_cmc = deck.average_cmc()

    # Collect color identity from commanders
    commanders = deck.commanders()
    commander_colors: set[str] = set()
    for cmd in commanders:
        commander_colors.update(cmd.colors)
    colors_str = ",".join(sorted(commander_colors)) if commander_colors else "Colorless"

    commander_names = ", ".join(cmd.card_name for cmd in commanders) if commanders else ""

    budget_str = f"${deck.budget_target:.2f}" if deck.budget_target is not None else "None"

    prices_as_of = date.today().isoformat()

    # Each summary row is padded to match the CSV_COLUMNS width
    col_count = len(CSV_COLUMNS)
    blank_row = [""] * col_count
    header_row = [""] * col_count
    header_row[1] = "DECK SUMMARY"

    def _summary_line(label: str, value: str) -> list[str]:
        row = [""] * col_count
        row[1] = label
        row[2] = value
        return row

    return [
        blank_row,
        header_row,
        _summary_line("Total Cards:", str(total_cards)),
        _summary_line("Total Price:", f"${total_price:.2f}"),
        _summary_line("Average CMC:", f"{avg_cmc:.1f}"),
        _summary_line("Colors:", colors_str),
        _summary_line("Commander:", commander_names),
        _summary_line("Budget Target:", budget_str),
        _summary_line("Prices As Of:", prices_as_of),
    ]


def export_deck_to_csv(
    deck: Deck,
    filepath: str | None = None,
    cards: dict[int, Card] | None = None,
    prices: dict[int, float] | None = None,
) -> str | None:
    """Export a deck to CSV format.

    Cards are sorted by category alphabetically, then by name within each
    category. A summary section is appended after the card list.

    Args:
        deck: The Deck to export.
        filepath: Path to write the CSV file. If None, returns the CSV as a string.
        cards: Optional mapping of card_id -> Card for enriched metadata.
        prices: Optional mapping of card_id -> price (USD) per card.

    Returns:
        The CSV content as a string when filepath is None, otherwise None
        (writes to file).
    """
    # Sort cards: by category alphabetically, then by name within category
    sorted_cards = sorted(
        deck.cards,
        key=lambda dc: (
            dc.category.lower() if dc.category else "",
            (cards[dc.card_id].name if cards and dc.card_id in cards else dc.card_name).lower(),
        ),
    )

    # Build all rows
    card_rows = [_build_card_row(dc, cards, prices) for dc in sorted_cards]
    summary_rows = _build_summary_rows(deck, prices)

    if filepath is not None:
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(CSV_COLUMNS)
            writer.writerows(card_rows)
            writer.writerows(summary_rows)
        return None

    # Write to string
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_COLUMNS)
    writer.writerows(card_rows)
    writer.writerows(summary_rows)
    return output.getvalue()
