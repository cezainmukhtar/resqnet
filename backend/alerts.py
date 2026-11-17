"""Rule-based weather alerts for ResQnet.

Everything in this file is a pure function: no Flask, no network. That keeps the
alert logic easy to test (see test_alerts.py) and easy to replace with an ML
model later, because app.py only depends on evaluate_alerts().

Where the thresholds come from
- Rain: India Meteorological Department (IMD) 24-hour rainfall categories
  (moderate 15.6 mm, heavy 64.5 mm, very heavy 115.6 mm, extremely heavy 204.5 mm).
- Wind: Beaufort scale applied to forecast gusts in km/h
  (7 = 50, 8 = 62, 10 = 89).
- Heat: IMD maximum-temperature thresholds (40 C plains, 45 C heat wave,
  47 C severe heat wave). IMD also requires departure-from-normal and
  persistence over several stations and days, which this simple version cannot
  check, so heat alerts are advisory only.

These alerts are indicative and are NOT official warnings.
"""

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
RISK_BY_SEVERITY = {"low": "LOW", "medium": "MODERATE", "high": "HIGH"}

# Each rule: (threshold, severity, title, band, advice). Highest threshold first.
RULES = {
    "rain": {
        "metric": "rain_24h_mm",
        "label": "Forecast rainfall, next 24 h",
        "unit": "mm",
        "template": (
            "About {value} mm of rain is forecast in the next 24 hours, "
            "which is in IMD's {band} rainfall range. {advice}"
        ),
        "rules": [
            (204.5, "high", "Extreme Rainfall Warning", "extremely heavy",
             "Severe flooding is possible. Move away from low-lying areas and rivers."),
            (115.6, "high", "Heavy Rainfall Warning", "very heavy",
             "Flooding and severe waterlogging are likely in low-lying areas."),
            (64.5, "medium", "Flood Risk Advisory", "heavy",
             "Waterlogging and local flooding are possible. Avoid flooded roads."),
            (15.6, "low", "Rainfall Expected", "moderate",
             "Expect wet roads and reduced visibility."),
        ],
    },
    "wind": {
        "metric": "max_gust_kmh",
        "label": "Peak forecast gust, next 24 h",
        "unit": "km/h",
        "template": (
            "Gusts up to {value} km/h are forecast in the next 24 hours "
            "({band}). {advice}"
        ),
        "rules": [
            (89, "high", "Storm-Force Wind Warning", "Beaufort 10 or above",
             "Stay indoors, secure loose objects and avoid travel."),
            (62, "medium", "Gale Wind Advisory", "Beaufort 8 to 9",
             "Trees and loose structures may be damaged. Avoid unnecessary travel."),
            (50, "low", "Strong Wind Expected", "Beaufort 7",
             "Secure loose outdoor objects."),
        ],
    },
    "heat": {
        "metric": "max_temp_c",
        "label": "Peak forecast temperature, next 24 h",
        "unit": "°C",
        "template": (
            "A high of {value} °C is forecast in the next 24 hours "
            "({band}). {advice}"
        ),
        "rules": [
            (47, "high", "Severe Heat Warning", "IMD severe heat-wave level, 47 °C or above",
             "Avoid going out in the daytime. Seek cool shelter and drink water often."),
            (45, "medium", "Heat Wave Advisory", "IMD heat-wave level, 45 °C or above",
             "Limit time outdoors in the afternoon and drink water often."),
            (40, "low", "Hot Conditions", "IMD plains threshold, 40 °C or above",
             "Avoid strenuous activity in the midday sun."),
        ],
    },
}


def summarize_forecast(hourly, hours=24):
    """Reduce an Open-Meteo hourly block to the three numbers the rules use.

    Returns None when the block holds no usable data at all.
    """
    def clean(values):
        return [v for v in (values or [])[:hours] if v is not None]

    rain = clean(hourly.get("precipitation"))
    gusts = clean(hourly.get("wind_gusts_10m"))
    temps = clean(hourly.get("temperature_2m"))

    if not (rain or gusts or temps):
        return None

    return {
        "rain_24h_mm": round(sum(rain), 1) if rain else None,
        "max_gust_kmh": round(max(gusts), 1) if gusts else None,
        "max_temp_c": round(max(temps), 1) if temps else None,
        "hours_covered": max(len(rain), len(gusts), len(temps)),
    }


def evaluate_alerts(summary):
    """Return the active alerts for a forecast summary, most severe first.

    At most one alert per category: the highest threshold the value reaches.
    """
    alerts = []

    for category, spec in RULES.items():
        value = summary.get(spec["metric"])
        if value is None:
            continue

        for threshold, severity, title, band, advice in spec["rules"]:
            if value >= threshold:
                alerts.append({
                    "id": category,
                    "category": category,
                    "severity": severity,
                    "title": title,
                    "message": spec["template"].format(value=value, band=band, advice=advice),
                    "metric": spec["metric"],
                    "metric_label": spec["label"],
                    "value": value,
                    "threshold": threshold,
                    "unit": spec["unit"],
                })
                break

    alerts.sort(key=lambda alert: -SEVERITY_RANK[alert["severity"]])
    return alerts


def overall_risk(alerts):
    """LOW when nothing is active, otherwise driven by the most severe alert."""
    if not alerts:
        return "LOW"
    return RISK_BY_SEVERITY[alerts[0]["severity"]]


def describe_rules():
    """The rule table in display form, so the UI never duplicates thresholds."""
    described = []
    for category, spec in RULES.items():
        for threshold, severity, title, band, _advice in spec["rules"]:
            described.append({
                "category": category,
                "severity": severity,
                "title": title,
                "threshold": threshold,
                "unit": spec["unit"],
                "basis": band,
                "metric_label": spec["label"],
            })
    return described
