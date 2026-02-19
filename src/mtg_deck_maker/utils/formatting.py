"""Output formatting helpers for deck display and reporting.

This module provides utility functions for formatting card data, prices,
and deck information for terminal display. Full implementation will be
added in a later phase.
"""

from __future__ import annotations


def format_price(price: float, currency: str = "USD") -> str:
    """Format a price value with currency symbol.

    Args:
        price: The price value.
        currency: Currency code.

    Returns:
        Formatted price string (e.g., "$12.50").
    """
    symbols = {"USD": "$", "EUR": "\u20ac"}
    symbol = symbols.get(currency, currency + " ")
    return f"{symbol}{price:.2f}"


def format_mana_cost(mana_cost: str) -> str:
    """Format a mana cost string for display.

    Passes through the standard {X} notation as-is for now.

    Args:
        mana_cost: Mana cost in {X} notation.

    Returns:
        Formatted mana cost string.
    """
    return mana_cost


def format_color_identity(colors: list[str]) -> str:
    """Format a color identity list as a display string.

    Args:
        colors: List of color characters.

    Returns:
        Comma-separated string or "Colorless" for empty.
    """
    if not colors:
        return "Colorless"
    return ",".join(colors)
