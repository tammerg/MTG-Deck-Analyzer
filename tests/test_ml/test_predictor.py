"""Tests for PowerPredictor inference class."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from mtg_deck_maker.models.card import Card


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


_COMMANDER = _card(
    name="Test Commander",
    type_line="Legendary Creature",
    color_identity=["W", "U"],
)


class FakeModel:
    """Minimal model stub with a predict method."""

    def __init__(self, return_value: float = 0.75) -> None:
        self._return_value = return_value

    def predict(self, x):  # noqa: ANN001, ANN201
        return [self._return_value]


class FakeModelRaises:
    """Model stub that raises on predict."""

    def predict(self, x):  # noqa: ANN001, ANN201
        raise RuntimeError("predict failed")


# ---------------------------------------------------------------------------
# 1. Initialization tests
# ---------------------------------------------------------------------------


class TestInit:
    """Initialization behavior of PowerPredictor."""

    def test_nonexistent_path_not_available(self, tmp_path: Path) -> None:
        """is_available returns False when model file does not exist."""
        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=tmp_path / "no_such_model.joblib")
        assert predictor.is_available() is False

    def test_custom_path_stored(self, tmp_path: Path) -> None:
        """Custom model_path is used instead of the default."""
        from mtg_deck_maker.ml.predictor import PowerPredictor

        custom = tmp_path / "custom.joblib"
        predictor = PowerPredictor(model_path=custom)
        assert predictor._model_path == custom

    def test_default_path_used_when_none(self) -> None:
        """When model_path is None, DEFAULT_MODEL_PATH is used."""
        from mtg_deck_maker.ml.predictor import PowerPredictor
        from mtg_deck_maker.ml.trainer import DEFAULT_MODEL_PATH

        predictor = PowerPredictor(model_path=None)
        assert predictor._model_path == DEFAULT_MODEL_PATH

    def test_corrupt_file_not_available(self, tmp_path: Path) -> None:
        """is_available returns False when the file contains garbage bytes."""
        pytest.importorskip("joblib")
        corrupt_file = tmp_path / "corrupt.joblib"
        corrupt_file.write_bytes(b"\x00\xff\xfe garbage data")

        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=corrupt_file)
        assert predictor.is_available() is False


# ---------------------------------------------------------------------------
# 2. predict tests
# ---------------------------------------------------------------------------


class TestPredict:
    """Prediction behavior of PowerPredictor."""

    def test_returns_none_when_no_model(self, tmp_path: Path) -> None:
        """predict returns None when no model is loaded."""
        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=tmp_path / "missing.joblib")
        result = predictor.predict(_card(), _COMMANDER)
        assert result is None

    def test_returns_float_with_model(self, tmp_path: Path) -> None:
        """predict returns a float when a model is available."""
        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=tmp_path / "missing.joblib")
        predictor._model = FakeModel(0.75)

        with patch(
            "mtg_deck_maker.ml.features.extract_features",
            return_value=[0.0] * 22,
        ):
            result = predictor.predict(_card(), _COMMANDER)

        assert result is not None
        assert isinstance(result, float)
        assert result == pytest.approx(0.75)

    def test_clamps_above_one(self, tmp_path: Path) -> None:
        """predict clamps values greater than 1.0 to 1.0."""
        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=tmp_path / "missing.joblib")
        predictor._model = FakeModel(1.5)

        with patch(
            "mtg_deck_maker.ml.features.extract_features",
            return_value=[0.0] * 22,
        ):
            result = predictor.predict(_card(), _COMMANDER)

        assert result == pytest.approx(1.0)

    def test_clamps_below_zero(self, tmp_path: Path) -> None:
        """predict clamps values less than 0.0 to 0.0."""
        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=tmp_path / "missing.joblib")
        predictor._model = FakeModel(-0.5)

        with patch(
            "mtg_deck_maker.ml.features.extract_features",
            return_value=[0.0] * 22,
        ):
            result = predictor.predict(_card(), _COMMANDER)

        assert result == pytest.approx(0.0)

    def test_returns_none_on_feature_extraction_error(
        self, tmp_path: Path
    ) -> None:
        """predict returns None when extract_features raises."""
        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=tmp_path / "missing.joblib")
        predictor._model = FakeModel(0.5)

        with patch(
            "mtg_deck_maker.ml.features.extract_features",
            side_effect=ValueError("bad features"),
        ):
            result = predictor.predict(_card(), _COMMANDER)

        assert result is None

    def test_returns_none_on_model_predict_error(
        self, tmp_path: Path
    ) -> None:
        """predict returns None when model.predict raises."""
        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=tmp_path / "missing.joblib")
        predictor._model = FakeModelRaises()

        with patch(
            "mtg_deck_maker.ml.features.extract_features",
            return_value=[0.0] * 22,
        ):
            result = predictor.predict(_card(), _COMMANDER)

        assert result is None


# ---------------------------------------------------------------------------
# 3. is_available tests
# ---------------------------------------------------------------------------


class TestIsAvailable:
    """is_available status reporting."""

    def test_false_when_model_none(self, tmp_path: Path) -> None:
        """is_available returns False when _model is None."""
        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=tmp_path / "nope.joblib")
        assert predictor._model is None
        assert predictor.is_available() is False

    def test_true_when_model_set(self, tmp_path: Path) -> None:
        """is_available returns True when _model is populated."""
        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=tmp_path / "nope.joblib")
        predictor._model = FakeModel()
        assert predictor.is_available() is True


# ---------------------------------------------------------------------------
# 4. Integration with joblib
# ---------------------------------------------------------------------------


class TestJoblibIntegration:
    """Tests that exercise real joblib save/load round-trips."""

    def test_loads_real_joblib_model(self, tmp_path: Path) -> None:
        """PowerPredictor loads a genuine joblib-serialized object."""
        joblib = pytest.importorskip("joblib")

        model = FakeModel(0.42)
        model_path = tmp_path / "model.joblib"
        joblib.dump(model, model_path)

        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=model_path)
        assert predictor.is_available() is True

    def test_round_trip_predict(self, tmp_path: Path) -> None:
        """Save a tiny sklearn model, load it, and get a prediction."""
        pytest.importorskip("sklearn")
        joblib = pytest.importorskip("joblib")
        np = pytest.importorskip("numpy")
        from sklearn.linear_model import SGDRegressor

        # Train a trivial model on synthetic data
        rng = np.random.default_rng(42)
        n_features = 22  # matches FEATURE_NAMES length
        x_train = rng.random((50, n_features))
        y_train = rng.random(50)

        model = SGDRegressor(random_state=42)
        model.fit(x_train, y_train)

        model_path = tmp_path / "sgd_model.joblib"
        joblib.dump(model, model_path)

        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=model_path)
        assert predictor.is_available() is True

        with patch(
            "mtg_deck_maker.ml.features.extract_features",
            return_value=[0.5] * n_features,
        ):
            result = predictor.predict(_card(), _COMMANDER)

        assert result is not None
        assert 0.0 <= result <= 1.0

    def test_is_available_true_after_valid_load(self, tmp_path: Path) -> None:
        """is_available returns True after loading a valid joblib model."""
        joblib = pytest.importorskip("joblib")

        model_path = tmp_path / "valid.joblib"
        joblib.dump(FakeModel(0.6), model_path)

        from mtg_deck_maker.ml.predictor import PowerPredictor

        predictor = PowerPredictor(model_path=model_path)
        assert predictor.is_available() is True
        assert predictor._model is not None
