"""Flood and landslide risk screening for ResQnet.

IMPORTANT: this is rule-based screening built on published methods, NOT machine
learning. We have no labelled flood or landslide records to train a model on,
so presenting a trained model here would be dishonest.

FLOOD
  Open-Meteo serves river discharge from GloFAS, the Copernicus flood model.
  We take about 40 years of simulated daily discharge (1984-2022) for the
  river nearest a point, find each year's peak, fit a Gumbel distribution, and
  read off the 2-, 5- and 20-year flood levels (the return-period convention
  GloFAS uses for its own alerts). Risk is how high the 7-day discharge
  forecast climbs against those levels.

LANDSLIDE
  Two ingredients, and risk is limited by the weaker one:
  - Rainfall: Caine's (1980) global minimum threshold for shallow landslides,
    I = 14.82 * D^-0.39 (mm/h, D in hours), compared with the forecast rain.
  - Terrain: average slope from a 90 m elevation model.
  Combining them this way is a simplified screening heuristic of ours; it is
  not a calibrated model and not a prediction that a landslide will occur.
"""
import math

LEVELS = ["MINIMAL", "LOW", "MEDIUM", "HIGH"]

# Caine (1980): rainfall intensity-duration lower bound for shallow landslides
CAINE_COEFFICIENT = 14.82
CAINE_EXPONENT = -0.39
LANDSLIDE_DURATIONS_H = (24, 72)

FLOOD_RETURN_PERIODS = (2, 5, 20)
EULER_GAMMA = 0.5772156649


class HazardDataError(Exception):
    """A data problem we can explain to the user (not a bug)."""


def parse_coordinates(raw_latitude, raw_longitude):
    try:
        latitude = float(raw_latitude)
        longitude = float(raw_longitude)
    except (TypeError, ValueError):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


# ----------------------------------------------------------------- landslide
def caine_threshold_mm(duration_hours):
    """Rain (mm) over duration_hours that reaches Caine's global minimum threshold."""
    intensity = CAINE_COEFFICIENT * duration_hours ** CAINE_EXPONENT   # mm per hour
    return intensity * duration_hours


def slope_stats(grid, spacing_m):
    """Slope in degrees from a 5x5 elevation grid (rows run south to north,
    columns west to east, points spacing_m apart). Uses central differences at
    the 9 interior points. Returns (mean_slope_deg, steepest_slope_deg)."""
    slopes = []
    for i in range(1, len(grid) - 1):
        for j in range(1, len(grid[0]) - 1):
            d_north = (grid[i + 1][j] - grid[i - 1][j]) / (2 * spacing_m)
            d_east = (grid[i][j + 1] - grid[i][j - 1]) / (2 * spacing_m)
            slopes.append(math.degrees(math.atan(math.hypot(d_north, d_east))))
    return sum(slopes) / len(slopes), max(slopes)


def rain_score(ratio):
    if ratio >= 1.0:
        return 3
    if ratio >= 0.6:
        return 2
    if ratio >= 0.3:
        return 1
    return 0


def terrain_score(mean_slope_deg):
    if mean_slope_deg < 5:
        return 0, "flat"
    if mean_slope_deg < 15:
        return 1, "gentle"
    if mean_slope_deg < 30:
        return 2, "steep"
    return 3, "very steep"


def assess_landslide(mean_slope_deg, steepest_slope_deg, rain_24h_mm, rain_72h_mm):
    threshold_24 = caine_threshold_mm(24)
    threshold_72 = caine_threshold_mm(72)
    ratio_24 = rain_24h_mm / threshold_24
    ratio_72 = rain_72h_mm / threshold_72
    ratio = max(ratio_24, ratio_72)

    r_score = rain_score(ratio)
    t_score, t_class = terrain_score(mean_slope_deg)
    level = LEVELS[min(r_score, t_score)]

    explanation = [
        "Terrain around this point is %s (average slope %.0f°, steepest %.0f°, measured over about 500 m)."
        % (t_class, mean_slope_deg, steepest_slope_deg),
        "Rain of %.0f mm in 24 h and %.0f mm in 72 h is %.0f%% of the global minimum level that has triggered "
        "landslides (%.0f mm in 24 h, %.0f mm in 72 h)."
        % (rain_24h_mm, rain_72h_mm, ratio * 100, threshold_24, threshold_72),
        "The risk level is limited by the weaker of the two factors, terrain steepness and rainfall.",
    ]
    if t_score == 0:
        explanation.append("Slopes this gentle rarely fail because of rainfall alone, so the level stays minimal.")

    return {
        "level": level,
        "rain": {
            "rain_24h_mm": round(rain_24h_mm, 1),
            "rain_72h_mm": round(rain_72h_mm, 1),
            "threshold_24h_mm": round(threshold_24, 1),
            "threshold_72h_mm": round(threshold_72, 1),
            "ratio_24h": round(ratio_24, 3),
            "ratio_72h": round(ratio_72, 3),
            "ratio": round(ratio, 3),
            "score": r_score,
        },
        "terrain": {
            "mean_slope_deg": round(mean_slope_deg, 1),
            "steepest_slope_deg": round(steepest_slope_deg, 1),
            "class": t_class,
            "score": t_score,
        },
        "explanation": explanation,
    }


# --------------------------------------------------------------------- flood
def annual_maxima(dates, values, min_days=300):
    """Each year's peak daily value, skipping years with too many gaps."""
    by_year = {}
    for day, value in zip(dates, values):
        if value is None:
            continue
        by_year.setdefault(int(day[:4]), []).append(value)
    return [max(vals) for _, vals in sorted(by_year.items()) if len(vals) >= min_days]


def gumbel_return_levels(maxima, periods=FLOOD_RETURN_PERIODS):
    """Flood level for each return period, from a Gumbel fit (method of moments)."""
    n = len(maxima)
    if n < 15:
        return None
    mean = sum(maxima) / n
    std = math.sqrt(sum((m - mean) ** 2 for m in maxima) / (n - 1))
    if std == 0:
        return None
    beta = std * math.sqrt(6) / math.pi
    alpha = mean - EULER_GAMMA * beta
    return {
        str(t): round(alpha - beta * math.log(-math.log(1 - 1 / t)), 1)
        for t in periods
    }


def assess_flood(dates, values, levels, today_iso):
    """Compare the forecast peak discharge (from today on) with the flood levels."""
    series = [(d, v) for d, v in zip(dates, values) if v is not None]
    if not series:
        raise HazardDataError("No river discharge forecast is available here.")

    window = [(d, v) for d, v in series if d >= today_iso] or series
    peak_date, peak = max(window, key=lambda pair: pair[1])

    if peak >= levels["20"]:
        index = 3
    elif peak >= levels["5"]:
        index = 2
    elif peak >= levels["2"]:
        index = 1
    else:
        index = 0

    return {
        "level": LEVELS[index],
        "peak_m3s": round(peak, 1),
        "peak_date": peak_date,
        "ratio_to_2yr": round(peak / levels["2"], 3) if levels["2"] else None,
        "thresholds": levels,
        "series": [{"date": d, "discharge": round(v, 1)} for d, v in series],
    }
