"""Power prediction inference for card-commander pairs.

Loads a trained ML model and predicts EDHREC-like inclusion rates
for cards, enabling smarter power scoring for commanders without
EDHREC data.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from mtg_deck_maker.ml.constants import DEFAULT_MODEL_PATH
from mtg_deck_maker.models.card import Card

logger = logging.getLogger(__name__)


class PowerPredictor:
    """Predicts card power scores using a trained ML model.

    Loads a scikit-learn pipeline from disk and exposes a simple
    predict interface for card-commander pairs.

    Attributes:
        _model: The loaded sklearn pipeline, or None if unavailable.
        _model_path: Path to the model file.
    """

    def __init__(self, model_path: Path | str | None = None) -> None:
        """Initialize the predictor.

        Args:
            model_path: Path to the joblib model file.
                Defaults to DEFAULT_MODEL_PATH.
        """
        self._model_path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        self._model: Any | None = None
        self._load()

    def _load(self) -> None:
        """Attempt to load the model from disk."""
        if not self._model_path.exists():
            return
        try:
            import joblib

            self._model = joblib.load(self._model_path)
            logger.info("Loaded power model from %s", self._model_path)
        except Exception as exc:
            logger.warning(
                "Failed to load power model from %s: %s", self._model_path, exc
            )
            self._model = None

    def is_available(self) -> bool:
        """Check if a model is loaded and ready for predictions."""
        return self._model is not None

    def predict(self, card: Card, commander: Card) -> float | None:
        """Predict power score for a card-commander pair.

        Args:
            card: The candidate card.
            commander: The commander card.

        Returns:
            Float score clamped to [0.0, 1.0], or None if the model
            is unavailable.
        """
        if self._model is None:
            return None

        try:
            from mtg_deck_maker.ml.features import extract_features

            features = extract_features(card, commander)
            import numpy as np

            x = np.array([features])
            prediction = float(self._model.predict(x)[0])
            return max(0.0, min(1.0, prediction))
        except Exception as exc:
            logger.warning("Power prediction failed for %s: %s", card.name, exc)
            return None
