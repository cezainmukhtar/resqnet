"""HTTP routes for flood and landslide risk (registered in app.py).

Data comes from Open-Meteo (free, attribution required):
- river discharge: GloFAS via the Flood API (reanalysis from 1984)
- terrain: Copernicus DEM, 90 m, via the Elevation API
- rain: hourly forecast API
"""
import json
import os
import time
from datetime import datetime, timezone
from math import cos, radians
from urllib.parse import urlencode
from urllib.request import urlopen

from flask import Blueprint, current_app, jsonify, request

import hazards

hazards_blueprint = Blueprint("hazards", __name__)

FLOOD_URL = "https://flood-api.open-meteo.com/v1/flood"
ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hazard_cache")
FLOOD_HISTORY_START = "1984-01-01"
FLOOD_HISTORY_END = "2022-12-31"       # GloFAS v4 reanalysis period
GRID_SPACING_M = 250.0                 # 5 x 5 elevation grid, so about 1 km across

SHORT_CACHE_SECONDS = 600
FLOOD_FORECAST_CACHE_SECONDS = 3600
_rain_cache = {}
_flood_forecast_cache = {}

CAVEATS = {
    "flood": [
        "Simulated river discharge (GloFAS model), not a gauge reading.",
        "The model does not fully represent dams, barrages and water withdrawals, so flows on heavily managed rivers can differ from reality.",
        "Flood levels come from about 40 years of simulated history at the nearest river in a 5 km cell.",
        "Indicative screening only. It is not an official flood warning.",
    ],
    "landslide": [
        "Screening heuristic: Caine's (1980) global minimum rainfall threshold combined with terrain slope.",
        "Local thresholds in the Himalaya and other regions differ, and soil, geology, vegetation and past slope failures are not considered.",
        "It does not predict that a landslide will occur. It flags where heavy rain meets steep ground.",
        "Not an official warning. For warnings, check the Geological Survey of India and IMD.",
    ],
}


def fetch_json(url, timeout=20):
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode())


def utc_now_text():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------ disk cache
def _cache_path(kind, latitude, longitude):
    return os.path.join(CACHE_DIR, "%s_%.3f_%.3f.json" % (kind, latitude, longitude))


def load_cached(kind, latitude, longitude):
    try:
        with open(_cache_path(kind, latitude, longitude)) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def save_cached(kind, latitude, longitude, data):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_path(kind, latitude, longitude), "w") as handle:
            json.dump(data, handle)
    except OSError:
        pass   # caching is an optimisation, never a requirement


# ----------------------------------------------------------------- flood
def flood_climate(latitude, longitude):
    """Flood levels for the nearest river. Slow (about 14,000 days of data), so cached on disk."""
    cached = load_cached("flood", latitude, longitude)
    if cached:
        return cached

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "river_discharge",
        "start_date": FLOOD_HISTORY_START,
        "end_date": FLOOD_HISTORY_END,
    }
    data = fetch_json(FLOOD_URL + "?" + urlencode(params), timeout=60)

    daily = data.get("daily") or {}
    dates = daily.get("time") or []
    values = daily.get("river_discharge") or []
    valid = [v for v in values if v is not None]

    if not dates or not valid:
        raise hazards.HazardDataError(
            "No river data for this point. Choose a location on or beside a large river.")

    mean_flow = sum(valid) / len(valid)
    if mean_flow < 2:
        raise hazards.HazardDataError(
            "Only a very small stream was found near this point, so flood levels would not be meaningful. "
            "Choose a point on a larger river.")

    maxima = hazards.annual_maxima(dates, values)
    levels = hazards.gumbel_return_levels(maxima)
    if levels is None:
        raise hazards.HazardDataError("Not enough river history here to work out flood levels.")

    climate = {
        "levels": levels,
        "years_used": len(maxima),
        "period": "%s-%s" % (dates[0][:4], dates[-1][:4]),
        "mean_flow_m3s": round(mean_flow, 1),
        "cell": {"latitude": data.get("latitude"), "longitude": data.get("longitude")},
    }
    save_cached("flood", latitude, longitude, climate)
    return climate


def flood_forecast(latitude, longitude):
    key = (round(latitude, 3), round(longitude, 3))
    cached = _flood_forecast_cache.get(key)
    if cached and time.time() - cached["time"] < FLOOD_FORECAST_CACHE_SECONDS:
        return cached["data"]

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "river_discharge",
        "past_days": 2,
        "forecast_days": 7,
    }
    data = fetch_json(FLOOD_URL + "?" + urlencode(params))
    daily = data.get("daily") or {}
    result = {"dates": daily.get("time") or [], "values": daily.get("river_discharge") or []}
    _flood_forecast_cache[key] = {"time": time.time(), "data": result}
    return result


@hazards_blueprint.route("/hazards/flood")
def flood_risk():
    coordinates = hazards.parse_coordinates(
        request.args.get("latitude"), request.args.get("longitude"))
    if coordinates is None:
        return jsonify({"error": "Valid latitude (-90 to 90) and longitude (-180 to 180) are required"}), 400
    latitude, longitude = coordinates

    try:
        climate = flood_climate(latitude, longitude)
        forecast = flood_forecast(latitude, longitude)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assessment = hazards.assess_flood(
            forecast["dates"], forecast["values"], climate["levels"], today)
    except hazards.HazardDataError as error:
        return jsonify({"status": "error", "message": str(error)}), 502
    except Exception:
        current_app.logger.exception("Flood risk request failed")
        return jsonify({"status": "error", "message": "Flood data unavailable"}), 502

    return jsonify({
        "status": "success",
        "location": {"latitude": latitude, "longitude": longitude},
        "river_cell": climate["cell"],
        "generated_at": utc_now_text(),
        "history": {
            "period": climate["period"],
            "years_used": climate["years_used"],
            "mean_flow_m3s": climate["mean_flow_m3s"],
        },
        "method": "Forecast river discharge compared with 2-, 5- and 20-year flood levels from about 40 years of GloFAS history",
        "caveats": CAVEATS["flood"],
        **assessment,
    })


# ------------------------------------------------------------- landslide
def terrain_slope(latitude, longitude):
    """Average and steepest slope around a point. Terrain does not change, so it is cached on disk."""
    cached = load_cached("terrain", latitude, longitude)
    if cached:
        return cached

    d_lat = GRID_SPACING_M / 111320.0
    d_lon = GRID_SPACING_M / (111320.0 * max(cos(radians(latitude)), 0.01))
    lats, lons = [], []
    for i in range(-2, 3):          # south to north
        for j in range(-2, 3):      # west to east
            lats.append(round(latitude + i * d_lat, 6))
            lons.append(round(longitude + j * d_lon, 6))

    params = {
        "latitude": ",".join(str(v) for v in lats),
        "longitude": ",".join(str(v) for v in lons),
    }
    data = fetch_json(ELEVATION_URL + "?" + urlencode(params))
    elevations = data.get("elevation")

    if not elevations or len(elevations) != 25 or any(e is None for e in elevations):
        raise hazards.HazardDataError("No terrain data is available for this location.")

    grid = [elevations[row * 5:(row + 1) * 5] for row in range(5)]
    mean_slope, steepest = hazards.slope_stats(grid, GRID_SPACING_M)

    terrain = {
        "mean_slope_deg": round(mean_slope, 1),
        "steepest_slope_deg": round(steepest, 1),
        "elevation_m": round(grid[2][2]),
    }
    save_cached("terrain", latitude, longitude, terrain)
    return terrain


def recent_rain(latitude, longitude):
    """Rain over the last 48 h plus the next 24 h, from the hourly forecast API."""
    key = (round(latitude, 2), round(longitude, 2))
    cached = _rain_cache.get(key)
    if cached and time.time() - cached["time"] < SHORT_CACHE_SECONDS:
        return cached["data"]

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "precipitation",
        "past_hours": 48,
        "forecast_hours": 24,
        "timezone": "UTC",
    }
    data = fetch_json(FORECAST_URL + "?" + urlencode(params))
    values = [v for v in (data.get("hourly") or {}).get("precipitation", []) if v is not None]

    if len(values) < 24:
        raise hazards.HazardDataError("Rainfall data for this location is incomplete.")

    result = {
        "rain_24h_mm": sum(values[-24:]),      # the next 24 hours
        "rain_72h_mm": sum(values),            # the last 48 hours plus the next 24
        "hours_covered": len(values),
    }
    _rain_cache[key] = {"time": time.time(), "data": result}
    return result


@hazards_blueprint.route("/hazards/landslide")
def landslide_risk():
    coordinates = hazards.parse_coordinates(
        request.args.get("latitude"), request.args.get("longitude"))
    if coordinates is None:
        return jsonify({"error": "Valid latitude (-90 to 90) and longitude (-180 to 180) are required"}), 400
    latitude, longitude = coordinates

    # Optional what-if: the user supplies the rainfall instead of the live forecast
    scenario = None
    raw_24 = request.args.get("scenario_rain_24h")
    if raw_24 not in (None, ""):
        raw_72 = request.args.get("scenario_rain_72h")
        try:
            rain_24 = float(raw_24)
            rain_72 = float(raw_72) if raw_72 not in (None, "") else rain_24
        except ValueError:
            return jsonify({"error": "Scenario rainfall must be a number"}), 400
        if not (0 <= rain_24 <= 1000 and 0 <= rain_72 <= 2000):
            return jsonify({"error": "Scenario rainfall is out of range (24 h: 0-1000 mm, 72 h: 0-2000 mm)"}), 400
        scenario = {"rain_24h_mm": rain_24, "rain_72h_mm": max(rain_72, rain_24)}   # 72 h can't be less than 24 h

    try:
        terrain = terrain_slope(latitude, longitude)
        rain = scenario or recent_rain(latitude, longitude)
        assessment = hazards.assess_landslide(
            terrain["mean_slope_deg"], terrain["steepest_slope_deg"],
            rain["rain_24h_mm"], rain["rain_72h_mm"])
    except hazards.HazardDataError as error:
        return jsonify({"status": "error", "message": str(error)}), 502
    except Exception:
        current_app.logger.exception("Landslide risk request failed")
        return jsonify({"status": "error", "message": "Landslide data unavailable"}), 502

    return jsonify({
        "status": "success",
        "scenario": scenario is not None,
        "location": {"latitude": latitude, "longitude": longitude},
        "elevation_m": terrain["elevation_m"],
        "generated_at": utc_now_text(),
        "method": "Rainfall compared with Caine's (1980) global minimum landslide threshold, limited by terrain slope",
        "caveats": CAVEATS["landslide"],
        **assessment,
    })
