"""Load the trained rain model and turn recent hourly weather into a probability."""
import json
from pathlib import Path

import joblib

from ml.features import FEATURE_COLUMNS, HISTORY_HOURS, build_features

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "rain_model.joblib"
CARD_PATH = MODEL_DIR / "rain_model_card.json"

_loaded = {}


class ModelNotReady(Exception):
    """The model has not been trained yet."""


def load_rain_model():
    """Load the model, and reload it if a newly trained file has appeared."""
    if not MODEL_PATH.exists() or not CARD_PATH.exists():
        raise ModelNotReady(
            "Model not trained yet. Run: python3 ml/train_rain_model.py"
        )

    stamp = (MODEL_PATH.stat().st_mtime, CARD_PATH.stat().st_mtime)
    if _loaded.get("stamp") != stamp:
        _loaded["model"] = joblib.load(MODEL_PATH)
        _loaded["card"] = json.loads(CARD_PATH.read_text())
        _loaded["stamp"] = stamp
    return _loaded["model"], _loaded["card"]


def predict_rain(recent_hourly):
    """recent_hourly: hourly DataFrame (UTC index) ending at the current hour,
    with at least HISTORY_HOURS + 1 rows. Returns (probability, timestamp, card)."""
    model, card = load_rain_model()

    if len(recent_hourly) <= HISTORY_HOURS:
        raise ValueError("Not enough recent hourly data to build the features")

    features = build_features(recent_hourly)
    latest = features.iloc[[-1]]

    if latest[FEATURE_COLUMNS].isna().any(axis=None):
        raise ValueError("Recent weather data has gaps; cannot build all features")

    probability = float(model.predict_proba(latest[FEATURE_COLUMNS])[0, 1])
    return probability, latest.index[-1], card
