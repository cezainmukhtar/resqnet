"""Run with:  python3 test_alerts.py"""
from alerts import evaluate_alerts, overall_risk, summarize_forecast


def ids(summary):
    return [(a["category"], a["severity"]) for a in evaluate_alerts(summary)]


def check(name, condition):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        raise SystemExit(1)


quiet = {"rain_24h_mm": 0.0, "max_gust_kmh": 20.0, "max_temp_c": 28.0}
check("quiet day -> no alerts", ids(quiet) == [])
check("quiet day -> LOW risk", overall_risk(evaluate_alerts(quiet)) == "LOW")

check("15.5 mm -> no rain alert", ids({**quiet, "rain_24h_mm": 15.5}) == [])
check("15.6 mm -> low rain", ids({**quiet, "rain_24h_mm": 15.6}) == [("rain", "low")])
check("64.5 mm -> medium flood advisory", ids({**quiet, "rain_24h_mm": 64.5}) == [("rain", "medium")])
check("115.6 mm -> high", ids({**quiet, "rain_24h_mm": 115.6}) == [("rain", "high")])
check("204.5 mm -> extreme title",
      evaluate_alerts({**quiet, "rain_24h_mm": 204.5})[0]["title"] == "Extreme Rainfall Warning")

flood = evaluate_alerts({**quiet, "rain_24h_mm": 80})
check("80 mm title is Flood Risk Advisory", flood[0]["title"] == "Flood Risk Advisory")
check("80 mm -> MODERATE risk", overall_risk(flood) == "MODERATE")

combo = evaluate_alerts({"rain_24h_mm": 130, "max_gust_kmh": 55, "max_temp_c": 41})
check("combined alerts sorted high first", [a["severity"] for a in combo] == ["high", "low", "low"])
check("combined -> HIGH risk", overall_risk(combo) == "HIGH")

check("62 km/h -> medium wind", ids({**quiet, "max_gust_kmh": 62}) == [("wind", "medium")])
check("47 C -> high heat", ids({**quiet, "max_temp_c": 47}) == [("heat", "high")])
check("missing metric is skipped", ids({"rain_24h_mm": None, "max_gust_kmh": None, "max_temp_c": 50}) == [("heat", "high")])

hourly = {
    "precipitation": [1.0, 2.5, None, 0.5] + [0.0] * 30,
    "wind_gusts_10m": [10, 40, 25] + [5] * 31,
    "temperature_2m": [20, 25, 31] + [18] * 31,
}
summary = summarize_forecast(hourly, 24)
check("summary sums rain, ignoring None", summary["rain_24h_mm"] == 4.0)
check("summary takes peak gust", summary["max_gust_kmh"] == 40)
check("summary takes peak temp", summary["max_temp_c"] == 31)
check("summary with no data -> None", summarize_forecast({}, 24) is None)
check("summary only looks at first 24 hours",
      summarize_forecast({"precipitation": [0.0] * 24 + [500.0]}, 24)["rain_24h_mm"] == 0.0)

print("\nAll checks passed.")
