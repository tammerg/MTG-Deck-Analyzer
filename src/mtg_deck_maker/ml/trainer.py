"""ML model training pipeline for card power prediction.

Trains a GradientBoostingRegressor to predict EDHREC inclusion rates
from card-commander feature vectors, enabling smarter power scoring
for commanders without EDHREC data.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from mtg_deck_maker.models.card import Card

logger = logging.getLogger(__name__)

# Default model save path
DEFAULT_MODEL_PATH = Path("data/power_model.joblib")


def build_dataset(
    commander_cards: list[tuple[Card, list[Any]]],
    card_pool_fn: Callable[[Card], list[Card]] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Build training dataset from commander EDHREC data.

    For each commander, creates:
    - Positive samples: cards in EDHREC data with target = inclusion_rate
    - Negative samples: random cards in color identity NOT in EDHREC data
      with target = 0.0

    Args:
        commander_cards: List of (commander_card, edhrec_data_list) tuples.
            Each edhrec entry needs .card_name and .inclusion_rate.
        card_pool_fn: Optional callable(commander_card) -> list[Card]
            that returns the card pool for negative sampling.
            If None, no negative samples are generated.

    Returns:
        Tuple of (X, y) where X is feature matrix and y is target vector.
    """
    from mtg_deck_maker.ml.features import extract_features

    x_rows: list[list[float]] = []
    y_values: list[float] = []

    for commander, edhrec_entries in commander_cards:
        # Build name set for negative sampling exclusion
        edhrec_names: set[str] = set()

        for entry in edhrec_entries:
            edhrec_names.add(entry.card_name)

            # Only extract features when a Card object is attached
            if hasattr(entry, "_card") and entry._card is not None:
                features = extract_features(entry._card, commander)
                x_rows.append(features)
                y_values.append(entry.inclusion_rate)

        # Negative samples
        if card_pool_fn is not None:
            pool = card_pool_fn(commander)
            negatives = [c for c in pool if c.name not in edhrec_names]
            # Sample up to same number as positives
            rng = random.Random(42)
            sample_size = min(len(negatives), len(edhrec_entries))
            neg_sample = rng.sample(negatives, sample_size) if negatives else []

            for card in neg_sample:
                features = extract_features(card, commander)
                x_rows.append(features)
                y_values.append(0.0)

    if not x_rows:
        return np.empty((0, 0)), np.empty(0)

    return np.array(x_rows), np.array(y_values)


def train_model(
    x: np.ndarray,
    y: np.ndarray,
    n_estimators: int = 200,
    max_depth: int = 5,
    learning_rate: float = 0.1,
    random_state: int = 42,
) -> Any:
    """Train a GradientBoostingRegressor on the dataset.

    Args:
        x: Feature matrix.
        y: Target vector (inclusion rates).
        n_estimators: Number of boosting iterations.
        max_depth: Maximum tree depth.
        learning_rate: Shrinkage rate.
        random_state: Random seed.

    Returns:
        Fitted sklearn Pipeline with StandardScaler + GradientBoostingRegressor.
    """
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("model", GradientBoostingRegressor(
            n_estimators=n_estimators,
            max_depth=max_depth,
            learning_rate=learning_rate,
            random_state=random_state,
        )),
    ])

    pipeline.fit(x, y)
    return pipeline


def evaluate_model(
    model: Any,
    x_test: np.ndarray,
    y_test: np.ndarray,
) -> dict[str, float]:
    """Evaluate a trained model on test data.

    Args:
        model: Fitted sklearn pipeline.
        x_test: Test feature matrix.
        y_test: Test target vector.

    Returns:
        Dict with 'mae', 'rmse', 'r2' metrics.
    """
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    y_pred = model.predict(x_test)

    return {
        "mae": float(mean_absolute_error(y_test, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_pred))),
        "r2": float(r2_score(y_test, y_pred)),
    }


def save_model(model: Any, path: Path | str | None = None) -> Path:
    """Save a trained model to disk using joblib.

    Args:
        model: Fitted sklearn pipeline.
        path: Save path. Defaults to DEFAULT_MODEL_PATH.

    Returns:
        The path the model was saved to.
    """
    import joblib

    save_path = Path(path) if path else DEFAULT_MODEL_PATH
    save_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, save_path)
    logger.info("Model saved to %s", save_path)
    return save_path


def load_model(path: Path | str | None = None) -> Any | None:
    """Load a trained model from disk.

    Args:
        path: Model path. Defaults to DEFAULT_MODEL_PATH.

    Returns:
        The loaded sklearn pipeline, or None if file doesn't exist.
    """
    import joblib

    load_path = Path(path) if path else DEFAULT_MODEL_PATH
    if not load_path.exists():
        return None

    return joblib.load(load_path)
