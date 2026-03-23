"""Tests for ML training pipeline (build_dataset, train, evaluate, save/load)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from mtg_deck_maker.models.card import Card


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card(name: str = "Test Card", **kwargs) -> Card:
    """Create a Card with sensible defaults for testing."""
    defaults: dict = {
        "oracle_id": f"oid-{name}",
        "name": name,
        "type_line": "Creature",
        "oracle_text": "",
        "cmc": 3.0,
        "color_identity": [],
        "colors": [],
        "keywords": [],
    }
    defaults.update(kwargs)
    return Card(**defaults)


def _edhrec_entry(
    card_name: str,
    inclusion_rate: float,
    card: Card | None = None,
) -> SimpleNamespace:
    """Create a mock EDHREC entry with optional _card attribute."""
    entry = SimpleNamespace(card_name=card_name, inclusion_rate=inclusion_rate)
    if card is not None:
        entry._card = card
    return entry


# Deterministic fake features (length must match FEATURE_NAMES = 22)
_FAKE_FEATURES = [0.0] * 22


def _fake_extract_features(card: Card, commander: Card) -> list[float]:
    """Return a deterministic feature vector for testing."""
    return list(_FAKE_FEATURES)


# ---------------------------------------------------------------------------
# build_dataset tests
# ---------------------------------------------------------------------------

class TestBuildDataset:
    """Tests for build_dataset."""

    @patch(
        "mtg_deck_maker.ml.features.extract_features",
        side_effect=_fake_extract_features,
    )
    def test_empty_input_returns_empty_arrays(self, _mock: object) -> None:
        from mtg_deck_maker.ml.trainer import build_dataset

        x, y = build_dataset([], None)

        assert x.shape == (0, 0)
        assert y.shape == (0,)

    @patch(
        "mtg_deck_maker.ml.features.extract_features",
        side_effect=_fake_extract_features,
    )
    def test_single_commander_positive_samples_only(self, _mock: object) -> None:
        """Positive entries with _card produce rows; no card_pool_fn means no negatives."""
        from mtg_deck_maker.ml.trainer import build_dataset

        commander = _card("Commander A", cmc=4.0)
        card_a = _card("Card A")
        card_b = _card("Card B")

        entries = [
            _edhrec_entry("Card A", 0.8, card=card_a),
            _edhrec_entry("Card B", 0.5, card=card_b),
        ]

        x, y = build_dataset([(commander, entries)], card_pool_fn=None)

        assert x.shape == (2, 22)
        np.testing.assert_array_almost_equal(y, [0.8, 0.5])

    @patch(
        "mtg_deck_maker.ml.features.extract_features",
        side_effect=_fake_extract_features,
    )
    def test_entry_without_card_attribute_skipped(self, _mock: object) -> None:
        """Entries missing the _card attribute are not included as positive samples."""
        from mtg_deck_maker.ml.trainer import build_dataset

        commander = _card("Commander")
        # _edhrec_entry without card= does NOT set _card attribute
        entries = [_edhrec_entry("No Card Entry", 0.9)]

        x, y = build_dataset([(commander, entries)], card_pool_fn=None)

        assert x.shape == (0, 0)
        assert len(y) == 0

    @patch(
        "mtg_deck_maker.ml.features.extract_features",
        side_effect=_fake_extract_features,
    )
    def test_entry_with_card_none_skipped(self, _mock: object) -> None:
        """Entries with _card=None are not included as positive samples."""
        from mtg_deck_maker.ml.trainer import build_dataset

        commander = _card("Commander")
        entry = _edhrec_entry("None Card Entry", 0.7)
        entry._card = None

        x, y = build_dataset([(commander, [entry])], card_pool_fn=None)

        assert x.shape == (0, 0)
        assert len(y) == 0

    @patch(
        "mtg_deck_maker.ml.features.extract_features",
        side_effect=_fake_extract_features,
    )
    def test_positive_and_negative_samples_with_card_pool(
        self, _mock: object
    ) -> None:
        """card_pool_fn provides negative samples filtered by EDHREC names."""
        from mtg_deck_maker.ml.trainer import build_dataset

        commander = _card("Commander")
        card_a = _card("Card A")
        entries = [_edhrec_entry("Card A", 0.6, card=card_a)]

        # Pool includes Card A (should be excluded) and two negatives
        neg_1 = _card("Neg 1")
        neg_2 = _card("Neg 2")

        def pool_fn(_cmd: Card) -> list[Card]:
            return [card_a, neg_1, neg_2]

        x, y = build_dataset([(commander, entries)], card_pool_fn=pool_fn)

        # 1 positive + 1 negative (sample_size = min(2, len(entries)=1) = 1)
        assert x.shape[0] == 2
        assert y[-1] == 0.0  # last row is negative

    @patch(
        "mtg_deck_maker.ml.features.extract_features",
        side_effect=_fake_extract_features,
    )
    def test_negative_sample_count_matches_positive_count(
        self, _mock: object
    ) -> None:
        """Number of negative samples should equal number of EDHREC entries."""
        from mtg_deck_maker.ml.trainer import build_dataset

        commander = _card("Commander")
        positives = [
            _edhrec_entry(f"Card {i}", 0.5, card=_card(f"Card {i}"))
            for i in range(3)
        ]

        # Provide more negatives than positives to verify capping
        neg_pool = [_card(f"Neg {i}") for i in range(10)]

        def pool_fn(_cmd: Card) -> list[Card]:
            return neg_pool

        x, y = build_dataset([(commander, positives)], card_pool_fn=pool_fn)

        # 3 positives + 3 negatives = 6
        assert x.shape[0] == 6
        assert np.sum(y == 0.0) == 3

    @patch(
        "mtg_deck_maker.ml.features.extract_features",
        side_effect=_fake_extract_features,
    )
    def test_negative_samples_get_zero_target(self, _mock: object) -> None:
        """All negative samples should have target value 0.0."""
        from mtg_deck_maker.ml.trainer import build_dataset

        commander = _card("Commander")
        entries = [_edhrec_entry("Card A", 0.9, card=_card("Card A"))]
        neg_pool = [_card("Neg 1"), _card("Neg 2")]

        def pool_fn(_cmd: Card) -> list[Card]:
            return neg_pool

        x, y = build_dataset([(commander, entries)], card_pool_fn=pool_fn)

        # Positives have non-zero targets, negatives have 0.0
        positive_targets = y[:1]
        negative_targets = y[1:]
        assert all(t > 0.0 for t in positive_targets)
        assert all(t == 0.0 for t in negative_targets)

    @patch(
        "mtg_deck_maker.ml.features.extract_features",
        side_effect=_fake_extract_features,
    )
    def test_multiple_commanders_accumulate_data(self, _mock: object) -> None:
        """Data from multiple commanders is concatenated."""
        from mtg_deck_maker.ml.trainer import build_dataset

        cmd_a = _card("Commander A")
        cmd_b = _card("Commander B")

        entries_a = [_edhrec_entry("Card A", 0.7, card=_card("Card A"))]
        entries_b = [
            _edhrec_entry("Card B", 0.6, card=_card("Card B")),
            _edhrec_entry("Card C", 0.4, card=_card("Card C")),
        ]

        x, y = build_dataset(
            [(cmd_a, entries_a), (cmd_b, entries_b)], card_pool_fn=None
        )

        assert x.shape[0] == 3
        np.testing.assert_array_almost_equal(y, [0.7, 0.6, 0.4])


# ---------------------------------------------------------------------------
# train_model tests
# ---------------------------------------------------------------------------

class TestTrainModel:
    """Tests for train_model (requires sklearn)."""

    @pytest.fixture(autouse=True)
    def _require_sklearn(self) -> None:
        pytest.importorskip("sklearn")

    @pytest.fixture()
    def synthetic_data(self) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.RandomState(42)
        x = rng.rand(50, 5)
        y = x[:, 0] * 0.5 + x[:, 1] * 0.3 + rng.rand(50) * 0.05
        return x, y

    def test_returns_pipeline_with_predict(
        self, synthetic_data: tuple[np.ndarray, np.ndarray]
    ) -> None:
        from mtg_deck_maker.ml.trainer import train_model

        x, y = synthetic_data
        model = train_model(x, y)

        assert hasattr(model, "predict")

    def test_predictions_are_floats(
        self, synthetic_data: tuple[np.ndarray, np.ndarray]
    ) -> None:
        from mtg_deck_maker.ml.trainer import train_model

        x, y = synthetic_data
        model = train_model(x, y)
        preds = model.predict(x[:5])

        assert preds.dtype == np.float64

    def test_custom_hyperparameters_accepted(
        self, synthetic_data: tuple[np.ndarray, np.ndarray]
    ) -> None:
        from mtg_deck_maker.ml.trainer import train_model

        x, y = synthetic_data
        model = train_model(
            x, y, n_estimators=10, max_depth=2, learning_rate=0.05, random_state=99
        )

        assert hasattr(model, "predict")
        preds = model.predict(x[:3])
        assert len(preds) == 3

    def test_deterministic_with_same_random_state(
        self, synthetic_data: tuple[np.ndarray, np.ndarray]
    ) -> None:
        from mtg_deck_maker.ml.trainer import train_model

        x, y = synthetic_data
        model_a = train_model(x, y, random_state=123)
        model_b = train_model(x, y, random_state=123)

        preds_a = model_a.predict(x)
        preds_b = model_b.predict(x)

        np.testing.assert_array_equal(preds_a, preds_b)


# ---------------------------------------------------------------------------
# evaluate_model tests
# ---------------------------------------------------------------------------

class TestEvaluateModel:
    """Tests for evaluate_model (requires sklearn)."""

    @pytest.fixture(autouse=True)
    def _require_sklearn(self) -> None:
        pytest.importorskip("sklearn")

    def test_returns_dict_with_expected_keys(self) -> None:
        from mtg_deck_maker.ml.trainer import evaluate_model, train_model

        rng = np.random.RandomState(0)
        x = rng.rand(30, 4)
        y = rng.rand(30)
        model = train_model(x, y, n_estimators=10, max_depth=2)

        metrics = evaluate_model(model, x, y)

        assert set(metrics.keys()) == {"mae", "rmse", "r2"}

    def test_all_values_are_floats(self) -> None:
        from mtg_deck_maker.ml.trainer import evaluate_model, train_model

        rng = np.random.RandomState(1)
        x = rng.rand(30, 4)
        y = rng.rand(30)
        model = train_model(x, y, n_estimators=10, max_depth=2)

        metrics = evaluate_model(model, x, y)

        for key, val in metrics.items():
            assert isinstance(val, float), f"{key} is not float: {type(val)}"

    def test_perfect_predictions_give_zero_mae_and_r2_one(self) -> None:
        """A model that predicts perfectly should have MAE=0 and R2=1."""
        from unittest.mock import MagicMock

        from mtg_deck_maker.ml.trainer import evaluate_model

        y_test = np.array([0.1, 0.5, 0.9])
        x_test = np.zeros((3, 2))  # not used by mock

        mock_model = MagicMock()
        mock_model.predict.return_value = y_test.copy()

        metrics = evaluate_model(mock_model, x_test, y_test)

        assert metrics["mae"] == pytest.approx(0.0)
        assert metrics["r2"] == pytest.approx(1.0)
        assert metrics["rmse"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# save_model / load_model tests
# ---------------------------------------------------------------------------

class TestSaveLoadModel:
    """Tests for save_model and load_model."""

    def test_save_creates_file(self, tmp_path: Path) -> None:
        pytest.importorskip("joblib")
        from mtg_deck_maker.ml.trainer import save_model

        model = {"dummy": "model"}
        out = tmp_path / "model.joblib"

        result = save_model(model, out)

        assert result == out
        assert out.exists()

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        pytest.importorskip("joblib")
        from mtg_deck_maker.ml.trainer import save_model

        nested = tmp_path / "a" / "b" / "c" / "model.joblib"
        save_model({"nested": True}, nested)

        assert nested.exists()

    def test_load_returns_none_for_nonexistent_path(self, tmp_path: Path) -> None:
        pytest.importorskip("joblib")
        from mtg_deck_maker.ml.trainer import load_model

        result = load_model(tmp_path / "does_not_exist.joblib")

        assert result is None

    def test_round_trip_preserves_predictions(self, tmp_path: Path) -> None:
        """Save then load should produce a model with identical predictions."""
        pytest.importorskip("sklearn")
        from mtg_deck_maker.ml.trainer import load_model, save_model, train_model

        rng = np.random.RandomState(42)
        x = rng.rand(30, 4)
        y = rng.rand(30)

        model = train_model(x, y, n_estimators=10, max_depth=2)
        path = tmp_path / "rt_model.joblib"

        save_model(model, path)
        loaded = load_model(path)

        assert loaded is not None
        preds_orig = model.predict(x)
        preds_loaded = loaded.predict(x)
        np.testing.assert_array_equal(preds_orig, preds_loaded)

    def test_default_model_path_constant(self) -> None:
        from mtg_deck_maker.ml.trainer import DEFAULT_MODEL_PATH

        assert DEFAULT_MODEL_PATH.name == "power_model.joblib"
        assert DEFAULT_MODEL_PATH.parent.name == "data"
        assert DEFAULT_MODEL_PATH.is_absolute()
