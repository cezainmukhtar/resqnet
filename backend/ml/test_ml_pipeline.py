"""Checks the ML code without touching the internet.   Run from backend/:

    python3 ml/test_ml_pipeline.py

These tests use SYNTHETIC weather, only to prove the code is correct (no
look-ahead in the features, correct labels, training and serving agree).
They say nothing about how good the model is on real weather: the real
numbers come from train_rain_model.py.
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml import predictor, train_rain_model  # noqa: E402
from ml.features import FEATURE_COLUMNS, HOURLY_VARIABLES, build_features, build_labels  # noqa: E402


def check(name, condition):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        raise SystemExit(1)


def synthetic_history(start, end, seed=0):
    """Fake hourly weather with some real structure (monsoon season, falling pressure before rain)."""
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, end, freq="h", tz="UTC")
    n = len(index)
    day = index.dayofyear.values
    season = np.exp(-((day - 210) / 45.0) ** 2)            # peaks in late July

    moisture = np.zeros(n)
    for i in range(1, n):
        moisture[i] = 0.97 * moisture[i - 1] + rng.normal(0, 0.25)
    wetness = moisture + 2.5 * season

    rain = np.where(wetness > 1.6, rng.exponential(1.2, n) * (wetness - 1.2), 0.0)
    pressure = 1000 - 4 * season - 2.5 * moisture + rng.normal(0, 0.3, n)
    temp = 25 + 8 * np.sin((day - 100) / 365.25 * 2 * np.pi) + rng.normal(0, 1, n)
    humidity = np.clip(55 + 12 * wetness + rng.normal(0, 5, n), 5, 100)
    return pd.DataFrame({
        "temperature_2m": temp,
        "relative_humidity_2m": humidity,
        "dew_point_2m": temp - (100 - humidity) / 5,
        "surface_pressure": pressure,
        "cloud_cover": np.clip(30 + 25 * wetness + rng.normal(0, 10, n), 0, 100),
        "wind_speed_10m": np.abs(rng.normal(8, 4, n)),
        "wind_direction_10m": rng.uniform(0, 360, n),
        "precipitation": rain,
    }, index=index)


# ---- 1. features never look into the future -------------------------------
history = synthetic_history("2024-01-01", "2024-03-01")
full = build_features(history)
cut = len(history) - 500
truncated = build_features(history.iloc[: cut + 1])
same = np.allclose(full.iloc[cut].values, truncated.iloc[-1].values, equal_nan=True)
check("features at time t are identical when the future is removed (no look-ahead)", same)
check("feature columns match the declared list", list(full.columns) == FEATURE_COLUMNS)
check("first 24 rows are NaN (incomplete history), the rest are complete",
      full.iloc[:24].isna().any(axis=1).all() and not full.iloc[24:].isna().any(axis=None))

# ---- 2. labels look only at the next 24 hours ------------------------------
index = pd.date_range("2024-01-01", periods=60, freq="h", tz="UTC")
rain = pd.Series(0.0, index=index)
rain.iloc[30] = 3.0                                          # 3 mm at hour 30
tiny = pd.DataFrame({"precipitation": rain})
labels = build_labels(tiny)
check("rain at hour 30 counts for hours 6..29 (inside the 24 h before it)", labels.iloc[6:30].eq(1.0).all())
check("rain at hour 30 does not count for hour 30 itself or later", labels.iloc[30:36].eq(0.0).all())
check("rain at hour 30 does not count for hours before 6", labels.iloc[:6].eq(0.0).all())
check("the last 24 rows have no label (future unknown)", labels.iloc[-24:].isna().all())

# ---- 3. end-to-end: train, save, load, predict -----------------------------
with tempfile.TemporaryDirectory() as folder:
    synthetic = synthetic_history("2019-01-01", "2026-06-30", seed=1)
    card = train_rain_model.train(28.4744, 77.5040, 2019, output_dir=folder, history=synthetic)

    check("model file was saved", (Path(folder) / "rain_model.joblib").exists())
    check("model card was saved", (Path(folder) / "rain_model_card.json").exists())
    for key in ["test_scores", "baselines", "calibration_on_test", "top_features", "split", "notes"]:
        check(f"model card contains '{key}'", key in card)
    check("test period is later than the training period", card["split"]["test"].startswith("from 2024"))

    predictor.MODEL_PATH = Path(folder) / "rain_model.joblib"
    predictor.CARD_PATH = Path(folder) / "rain_model_card.json"
    predictor._loaded.clear()

    recent = synthetic.iloc[-49:][HOURLY_VARIABLES]
    probability, timestamp, loaded_card = predictor.predict_rain(recent)
    check("prediction is a probability between 0 and 1", 0.0 <= probability <= 1.0)
    check("prediction is for the latest hour", timestamp == recent.index[-1])

    try:
        predictor.predict_rain(recent.iloc[:10])
        check("too little history is rejected", False)
    except ValueError:
        check("too little history is rejected", True)

    predictor.MODEL_PATH = Path(folder) / "missing.joblib"
    predictor._loaded.clear()
    try:
        predictor.load_rain_model()
        check("a missing model raises ModelNotReady", False)
    except predictor.ModelNotReady:
        check("a missing model raises ModelNotReady", True)

print("\nAll checks passed.")
