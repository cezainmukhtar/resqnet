"""Feature engineering shared by training and serving.

The SAME function builds the features in both places. That is deliberate:
if training and serving computed features differently, the model would be
quietly wrong in the app. Every feature at time t uses only data from time t
and earlier (no look-ahead), and test_ml_pipeline.py checks that.
"""
import numpy as np
import pandas as pd

# Hourly variables requested from Open-Meteo (same names in the archive and forecast APIs)
HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "precipitation",
]

# What we predict: will at least this much rain fall in the next 24 hours?
RAIN_THRESHOLD_MM = 2.5   # IMD's lower bound for "light rain" in 24 h
HORIZON_HOURS = 24

# Hours of history needed before the first usable row
HISTORY_HOURS = 24

FEATURE_COLUMNS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "temp_dew_spread",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_dir_sin",
    "wind_dir_cos",
    "pressure_change_3h",
    "pressure_change_12h",
    "pressure_change_24h",
    "humidity_change_6h",
    "temp_change_24h",
    "rain_last_3h",
    "rain_last_24h",
    "hour_sin",
    "hour_cos",
    "doy_sin",
    "doy_cos",
]


def build_features(hourly):
    """hourly: DataFrame with a UTC DatetimeIndex (hourly, sorted) and HOURLY_VARIABLES columns.

    Returns a DataFrame of FEATURE_COLUMNS on the same index. The first
    HISTORY_HOURS rows contain NaN because their history is incomplete.
    """
    data = hourly[HOURLY_VARIABLES].astype(float)

    features = pd.DataFrame(index=data.index)
    features["temperature_2m"] = data["temperature_2m"]
    features["relative_humidity_2m"] = data["relative_humidity_2m"]
    features["dew_point_2m"] = data["dew_point_2m"]
    features["temp_dew_spread"] = data["temperature_2m"] - data["dew_point_2m"]
    features["surface_pressure"] = data["surface_pressure"]
    features["cloud_cover"] = data["cloud_cover"]
    features["wind_speed_10m"] = data["wind_speed_10m"]

    direction = np.deg2rad(data["wind_direction_10m"])
    features["wind_dir_sin"] = np.sin(direction)
    features["wind_dir_cos"] = np.cos(direction)

    features["pressure_change_3h"] = data["surface_pressure"].diff(3)
    features["pressure_change_12h"] = data["surface_pressure"].diff(12)
    features["pressure_change_24h"] = data["surface_pressure"].diff(24)
    features["humidity_change_6h"] = data["relative_humidity_2m"].diff(6)
    features["temp_change_24h"] = data["temperature_2m"].diff(24)

    features["rain_last_3h"] = data["precipitation"].rolling(3, min_periods=3).sum()
    features["rain_last_24h"] = data["precipitation"].rolling(24, min_periods=24).sum()

    hour = features.index.hour + features.index.minute / 60.0
    day_of_year = features.index.dayofyear
    features["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
    features["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)
    features["doy_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
    features["doy_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)

    return features[FEATURE_COLUMNS]


def build_labels(hourly):
    """1 if the rain falling in the NEXT 24 hours (t+1 .. t+24) is >= RAIN_THRESHOLD_MM.

    Rows without a full 24 hours of future data get NaN and must be dropped.
    """
    rain = hourly["precipitation"].astype(float)
    future_sum = rain[::-1].rolling(HORIZON_HOURS, min_periods=HORIZON_HOURS).sum()[::-1].shift(-1)
    labels = (future_sum >= RAIN_THRESHOLD_MM).astype(float)
    labels[future_sum.isna()] = np.nan
    return labels
