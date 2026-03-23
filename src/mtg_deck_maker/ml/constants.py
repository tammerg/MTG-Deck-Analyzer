"""Constants for the ML module.

Kept in a separate file so that modules importing only these constants
do not trigger heavy ML dependencies (numpy, sklearn, joblib).
"""

from __future__ import annotations

from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Default path for the trained power-prediction model.
DEFAULT_MODEL_PATH = _PROJECT_ROOT / "data" / "power_model.joblib"
