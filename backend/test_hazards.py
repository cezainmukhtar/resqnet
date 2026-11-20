"""Run from backend/:  python3 test_hazards.py     (no internet needed)"""
import math

import hazards
from hazards import (annual_maxima, assess_flood, assess_landslide, caine_threshold_mm,
                     gumbel_return_levels, slope_stats)


def check(name, condition):
    print(("PASS  " if condition else "FAIL  ") + name)
    if not condition:
        raise SystemExit(1)


# ---- Caine threshold ----------------------------------------------------------
check("Caine 24 h threshold is about 103 mm", abs(caine_threshold_mm(24) - 103.0) < 0.5)
check("Caine 72 h threshold is about 201 mm", abs(caine_threshold_mm(72) - 201.2) < 0.5)
check("Caine: P = 14.82 * D^0.61 (same thing written as cumulative rain)",
      abs(caine_threshold_mm(10) - 14.82 * 10 ** 0.61) < 1e-9)

# ---- slope from an elevation grid ---------------------------------------------
def tilted_grid(angle_deg, spacing=250.0, direction="north"):
    rise = math.tan(math.radians(angle_deg)) * spacing
    grid = []
    for i in range(5):
        row = []
        for j in range(5):
            row.append(1000 + rise * (i if direction == "north" else j))
        grid.append(row)
    return grid

mean, steepest = slope_stats(tilted_grid(20), 250.0)
check("a 20 degree plane measures 20 degrees (north-facing)", abs(mean - 20) < 0.01 and abs(steepest - 20) < 0.01)
mean, _ = slope_stats(tilted_grid(35, direction="east"), 250.0)
check("a 35 degree plane measures 35 degrees (east-facing)", abs(mean - 35) < 0.01)
mean, steepest = slope_stats([[500.0] * 5 for _ in range(5)], 250.0)
check("a flat grid has zero slope", mean == 0 and steepest == 0)

# ---- landslide combination ----------------------------------------------------
heavy = assess_landslide(25, 35, 120, 220)          # steep + above both thresholds
check("steep slope + rain above threshold -> MEDIUM (steep caps it below HIGH)", heavy["level"] == "MEDIUM")
very_steep = assess_landslide(33, 40, 120, 220)
check("very steep slope + rain above threshold -> HIGH", very_steep["level"] == "HIGH")
flat = assess_landslide(1, 3, 300, 500)
check("flat ground stays MINIMAL even in extreme rain", flat["level"] == "MINIMAL")
dry = assess_landslide(35, 45, 2, 5)
check("very steep slope but little rain -> MINIMAL", dry["level"] == "MINIMAL")
moderate = assess_landslide(25, 30, 70, 100)        # ratio 0.68 -> rain score 2
check("rain at 60-100% of threshold on steep ground -> MEDIUM", moderate["level"] == "MEDIUM")
low = assess_landslide(25, 30, 35, 40)              # ratio 0.34 -> rain score 1
check("rain at 30-60% of threshold -> LOW", low["level"] == "LOW")
check("ratio uses whichever of 24 h / 72 h is worse",
      assess_landslide(25, 30, 10, 190)["rain"]["ratio"] == assess_landslide(25, 30, 10, 190)["rain"]["ratio_72h"])
check("explanation mentions the flat-ground rule", any("gentle" in line for line in flat["explanation"]))

# ---- Gumbel return levels -----------------------------------------------------
# For a Gumbel with beta=1, alpha=0 the textbook levels are 0.3665, 1.4999, 2.9702
beta, alpha = 1.0, 0.0
sample = [alpha - beta * math.log(-math.log((k + 0.5) / 400)) for k in range(400)]   # near-exact Gumbel sample
levels = gumbel_return_levels(sample)
check("2-year level matches theory", abs(levels["2"] - 0.37) < 0.08)
check("5-year level matches theory", abs(levels["5"] - 1.50) < 0.10)
check("20-year level matches theory", abs(levels["20"] - 2.97) < 0.15)
check("levels rise with return period", levels["2"] < levels["5"] < levels["20"])
check("too few years -> no levels", gumbel_return_levels([1, 2, 3]) is None)
check("constant series -> no levels", gumbel_return_levels([5.0] * 30) is None)

# ---- annual maxima ------------------------------------------------------------
dates, values = [], []
for year in (2000, 2001, 2002):
    for day in range(365):
        dates.append(f"{year}-01-01")           # only the year prefix matters
        values.append(10.0)
values[5] = 99.0                                 # peak in 2000
values[365 + 7] = 55.0                           # peak in 2001
for k in range(2 * 365, 3 * 365 - 10):           # 2002 has only 355 valid days...
    pass
for k in range(2 * 365 + 100, 3 * 365):
    values[k] = None                             # ...but 2002 loses 265 days -> too many gaps
maxima = annual_maxima(dates, values)
check("annual maxima picks each year's peak", maxima == [99.0, 55.0])
check("a year with too many gaps is dropped", len(maxima) == 2)

# ---- flood assessment ---------------------------------------------------------
thresholds = {"2": 100.0, "5": 150.0, "20": 220.0}
days = ["2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"]
quiet = assess_flood(days, [40, 45, 50, 48, 42], thresholds, "2026-11-18")
check("flow below the 2-year level -> MINIMAL", quiet["level"] == "MINIMAL")
check("peak only counts from today on (the past peak of 200 is ignored)",
      assess_flood(days, [200, 30, 50, 60, 55], thresholds, "2026-11-18")["peak_m3s"] == 60.0)
check("between 2- and 5-year -> LOW", assess_flood(days, [1, 1, 120, 90, 80], thresholds, "2026-11-18")["level"] == "LOW")
check("between 5- and 20-year -> MEDIUM", assess_flood(days, [1, 1, 160, 90, 80], thresholds, "2026-11-18")["level"] == "MEDIUM")
check("above the 20-year level -> HIGH", assess_flood(days, [1, 1, 230, 90, 80], thresholds, "2026-11-18")["level"] == "HIGH")
check("peak date is reported", assess_flood(days, [1, 1, 80, 130, 80], thresholds, "2026-11-18")["peak_date"] == "2026-11-19")
check("missing values are skipped", assess_flood(days, [None, None, 50, None, 70], thresholds, "2026-11-18")["peak_m3s"] == 70.0)
try:
    assess_flood(days, [None] * 5, thresholds, "2026-11-18")
    check("no data raises a clear error", False)
except hazards.HazardDataError:
    check("no data raises a clear error", True)

# ---- coordinates --------------------------------------------------------------
check("valid coordinates parse", hazards.parse_coordinates("28.5", "77.3") == (28.5, 77.3))
check("out-of-range coordinates are rejected", hazards.parse_coordinates("95", "10") is None)
check("NaN is rejected", hazards.parse_coordinates("nan", "10") is None)
check("text is rejected", hazards.parse_coordinates("abc", "10") is None)

print("\nAll checks passed.")
