"""Structural protocol types for the MTG Deck Maker models.

Using Protocol instead of concrete base classes keeps optional dependencies
(e.g. ML libraries) truly optional: code that accepts a PowerPredictorProtocol
does not need to import the actual PowerPredictor implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from mtg_deck_maker.models.card import Card


class PowerPredictorProtocol(Protocol):
    """Structural interface for ML-based card power prediction.

    Any object that implements ``predict`` and ``is_available`` with the
    correct signatures satisfies this Protocol without explicit inheritance.
    """

    def predict(self, card: Card, commander: Card) -> float | None:
        """Predict a power score for a card-commander pair.

        Args:
            card: The candidate card to score.
            commander: The commander the deck is built around.

        Returns:
            A float in [0.0, 1.0], or None if the predictor is unavailable.
        """
        ...

    def is_available(self) -> bool:
        """Return True if the predictor is loaded and ready to predict."""
        ...
