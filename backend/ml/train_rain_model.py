"""Train the ResQnet rain model on real historical weather.

Run from the backend folder, with the virtual environment active:

    python3 ml/train_rain_model.py

What it does
1. Downloads hourly ERA5 reanalysis for one location from Open-Meteo's free
   archive API (about 10 years; cached in ml/data/ so re-runs are fast).
2. Builds features and the label "will >= 2.5 mm of rain fall in the next 24 h?".
3. Splits BY TIME (train up to 2022, validate 2023, test 2024 onwards), so the
   model is always tested on a period it never saw. A random split would leak.
4. Picks hyperparameters on the validation year, then measures once on the test
   period against two simple baselines (month-by-month climatology, and
   "did it rain in the last 24 h").
5. Refits on all data and saves the model plus a model card (JSON) with the
   honest numbers, which the dashboard displays.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.features import (  # noqa: E402
    FEATURE_COLUMNS,
    HISTORY_HOURS,
    HORIZON_HOURS,
    HOURLY_VARIABLES,
    RAIN_THRESHOLD_MM,
    build_features,
    build_labels,
)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
ML_DIR = Path(__file__).resolve().parent
DATA_DIR = ML_DIR / "data"
MODEL_DIR = ML_DIR / "models"

# Time-based split
TRAIN_END = pd.Timestamp("2023-01-01", tz="UTC")   # train: before this
VALID_END = pd.Timestamp("2024-01-01", tz="UTC")   # validation: [TRAIN_END, VALID_END); test: from here

CANDIDATES = [
    {"learning_rate": 0.05, "max_iter": 150, "max_leaf_nodes": 8, "min_samples_leaf": 200},
    {"learning_rate": 0.05, "max_iter": 300, "max_leaf_nodes": 15, "min_samples_leaf": 100},
    {"learning_rate": 0.03, "max_iter": 400, "max_leaf_nodes": 15, "min_samples_leaf": 200},
    {"learning_rate": 0.05, "max_iter": 200, "max_leaf_nodes": 31, "min_samples_leaf": 100},
]


def download_range(latitude, longitude, start, end):
    """One archive request (cached on disk when the range is a full past year)."""
    DATA_DIR.mkdir(exist_ok=True)
    cache = DATA_DIR / f"archive_{latitude:.3f}_{longitude:.3f}_{start}_{end}.csv"
    if cache.exists():
        return pd.read_csv(cache, index_col=0, parse_dates=True)

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "UTC",
    }
    url = ARCHIVE_URL + "?" + urlencode(params)

    for attempt in range(4):
        try:
            with urlopen(url, timeout=60) as response:
                payload = json.loads(response.read().decode())
            break
        except HTTPError as error:
            if error.code == 429 and attempt < 3:
                print("  rate limited, waiting 60 s ...")
                time.sleep(60)
                continue
            raise SystemExit(f"Open-Meteo returned HTTP {error.code} for {start}..{end}")
        except URLError as error:
            raise SystemExit(f"Could not reach Open-Meteo ({error.reason}). Check your internet connection.")

    hourly = payload.get("hourly")
    if not hourly:
        raise SystemExit(f"Open-Meteo returned no hourly data: {payload.get('reason', payload)}")

    frame = pd.DataFrame(hourly)
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    frame = frame.set_index("time")
    frame.to_csv(cache)
    return frame


def load_history(latitude, longitude, start_year):
    """Hourly history from start_year to ~10 days ago (the archive lags about 5 days)."""
    last_day = (datetime.now(timezone.utc) - timedelta(days=10)).date()
    parts = []

    for year in range(start_year, last_day.year + 1):
        start = f"{year}-01-01"
        end = min(f"{year}-12-31", last_day.isoformat())
        print(f"  downloading {start} .. {end}")
        parts.append(download_range(latitude, longitude, start, end))
        time.sleep(1)

    history = pd.concat(parts).sort_index()
    history = history[~history.index.duplicated(keep="first")]
    history.index = pd.DatetimeIndex(history.index).tz_convert("UTC")
    return history


def make_dataset(history):
    features = build_features(history)
    labels = build_labels(history)
    frame = features.copy()
    frame["label"] = labels
    frame["rain_last_24h_raw"] = features["rain_last_24h"]
    frame = frame.dropna(subset=FEATURE_COLUMNS + ["label"])
    return frame


def scores(y_true, probabilities):
    return {
        "roc_auc": round(float(roc_auc_score(y_true, probabilities)), 4),
        "average_precision": round(float(average_precision_score(y_true, probabilities)), 4),
        "brier": round(float(brier_score_loss(y_true, np.clip(probabilities, 0, 1))), 4),
    }


def reliability_table(y_true, probabilities):
    """Predicted probability vs how often it really rained, in bands."""
    edges = [0.0, 0.05, 0.10, 0.20, 0.35, 0.50, 0.75, 1.0001]
    rows = []
    for low, high in zip(edges[:-1], edges[1:]):
        mask = (probabilities >= low) & (probabilities < high)
        if mask.sum() == 0:
            continue
        rows.append({
            "band": f"{low:.0%}-{min(high, 1):.0%}",
            "hours": int(mask.sum()),
            "mean_predicted": round(float(probabilities[mask].mean()), 3),
            "observed_rate": round(float(y_true[mask].mean()), 3),
        })
    return rows


def make_model(params):
    return HistGradientBoostingClassifier(
        loss="log_loss",
        l2_regularization=1.0,
        early_stopping=False,
        random_state=0,
        **params,
    )


def train(latitude, longitude, start_year, output_dir=MODEL_DIR, history=None):
    if history is None:
        print("Downloading hourly history from Open-Meteo ...")
        history = load_history(latitude, longitude, start_year)

    dataset = make_dataset(history)
    print(f"Usable rows: {len(dataset):,}  ({dataset.index.min().date()} .. {dataset.index.max().date()})")

    train_set = dataset[dataset.index < TRAIN_END]
    valid_set = dataset[(dataset.index >= TRAIN_END) & (dataset.index < VALID_END)]
    test_set = dataset[dataset.index >= VALID_END]

    for name, part in [("train", train_set), ("validation", valid_set), ("test", test_set)]:
        if len(part) < 1000 or part["label"].nunique() < 2:
            raise SystemExit(f"The {name} period has too little data ({len(part)} rows). Try an earlier --start-year.")
        print(f"  {name:<10} {len(part):>7,} rows   rain-day rate {part['label'].mean():.1%}")

    x_train, y_train = train_set[FEATURE_COLUMNS], train_set["label"].values
    x_valid, y_valid = valid_set[FEATURE_COLUMNS], valid_set["label"].values
    x_test, y_test = test_set[FEATURE_COLUMNS], test_set["label"].values

    # 1) choose hyperparameters on the validation year
    print("Choosing settings on the validation year ...")
    best = None
    for params in CANDIDATES:
        model = make_model(params).fit(x_train, y_train)
        loss = log_loss(y_valid, np.clip(model.predict_proba(x_valid)[:, 1], 1e-6, 1 - 1e-6))
        print(f"  {params}  validation log-loss {loss:.4f}")
        if best is None or loss < best[0]:
            best = (loss, params)
    chosen = best[1]

    # 2) refit on train + validation, then measure ONCE on the untouched test period
    train_valid = pd.concat([train_set, valid_set])
    evaluated = make_model(chosen).fit(train_valid[FEATURE_COLUMNS], train_valid["label"].values)
    test_prob = evaluated.predict_proba(x_test)[:, 1]
    model_scores = scores(y_test, test_prob)

    # baselines
    month_rate = train_valid.groupby(train_valid.index.month)["label"].mean()
    climatology = test_set.index.month.map(month_rate).values.astype(float)
    persistence = test_set["rain_last_24h_raw"].values
    baseline_scores = {
        "climatology_by_month": scores(y_test, climatology),
        "rained_in_last_24h": {
            "roc_auc": round(float(roc_auc_score(y_test, persistence)), 4),
            "average_precision": round(float(average_precision_score(y_test, persistence)), 4),
        },
    }

    # 3) what drives the predictions
    rng = np.random.default_rng(0)
    sample = rng.choice(len(x_test), size=min(5000, len(x_test)), replace=False)
    importance = permutation_importance(
        evaluated, x_test.iloc[sample], y_test[sample],
        scoring="roc_auc", n_repeats=3, random_state=0,
    )
    order = np.argsort(importance.importances_mean)[::-1][:8]
    top_features = [
        {"feature": FEATURE_COLUMNS[i], "auc_drop_when_shuffled": round(float(importance.importances_mean[i]), 4)}
        for i in order
    ]

    # 4) final model for the app: refit on every row available
    final_model = make_model(chosen).fit(dataset[FEATURE_COLUMNS], dataset["label"].values)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(final_model, output_dir / "rain_model.joblib")

    card = {
        "name": "ResQnet 24-hour rain outlook",
        "trained_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "location": {"latitude": latitude, "longitude": longitude},
        "data_source": "Open-Meteo archive (ERA5 reanalysis, hourly)",
        "data_range": {"from": str(dataset.index.min().date()), "to": str(dataset.index.max().date())},
        "rows_used": int(len(dataset)),
        "target": f"at least {RAIN_THRESHOLD_MM} mm of rain in the next {HORIZON_HOURS} hours",
        "features": FEATURE_COLUMNS,
        "hyperparameters": chosen,
        "split": {
            "train": f"before {TRAIN_END.date()}",
            "validation": f"{TRAIN_END.date()} to {VALID_END.date()}",
            "test": f"from {VALID_END.date()}",
            "test_rows": int(len(test_set)),
            "test_rain_rate": round(float(y_test.mean()), 4),
        },
        "test_scores": model_scores,
        "baselines": baseline_scores,
        "calibration_on_test": reliability_table(y_test, test_prob),
        "top_features": top_features,
        "notes": [
            "Scores come from a model fitted on data before 2024 and tested on 2024 onwards; the saved model is refitted on all rows.",
            "Trained on ERA5 reanalysis; live predictions use Open-Meteo's recent model data, which can differ slightly.",
            "Trained for one location only.",
            "Neighbouring hours are highly correlated, so scores are less certain than the row count suggests.",
            "A statistical model like this is weaker than a physical weather-model forecast; use it as a complement.",
        ],
    }
    (output_dir / "rain_model_card.json").write_text(json.dumps(card, indent=2))

    print("\n=== TEST RESULTS (data the model never saw) ===")
    print(f"  model                 ROC-AUC {model_scores['roc_auc']:.3f}   avg-precision {model_scores['average_precision']:.3f}   Brier {model_scores['brier']:.4f}")
    clim = baseline_scores["climatology_by_month"]
    print(f"  climatology baseline  ROC-AUC {clim['roc_auc']:.3f}   avg-precision {clim['average_precision']:.3f}   Brier {clim['brier']:.4f}")
    pers = baseline_scores["rained_in_last_24h"]
    print(f"  rained-last-24h       ROC-AUC {pers['roc_auc']:.3f}   avg-precision {pers['average_precision']:.3f}")
    print("  top features:", ", ".join(f["feature"] for f in top_features[:5]))
    print(f"\nSaved: {output_dir / 'rain_model.joblib'}")
    print(f"Saved: {output_dir / 'rain_model_card.json'}")
    return card


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the ResQnet rain model")
    parser.add_argument("--lat", type=float, default=28.4744)
    parser.add_argument("--lon", type=float, default=77.5040)
    parser.add_argument("--start-year", type=int, default=2015)
    arguments = parser.parse_args()
    train(arguments.lat, arguments.lon, arguments.start_year)
