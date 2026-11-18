import numpy as np, pandas as pd
rng = np.random.default_rng(42)
n = 5000
df = pd.DataFrame({
    "humidity": rng.uniform(20, 100, n),
    "pressure": rng.normal(1010, 8, n),
    "temp": rng.normal(28, 6, n),
    "rain_prev_24h": rng.gamma(1.5, 8, n),
    "rain_prev_72h": rng.gamma(2.0, 15, n),
    "slope_deg": rng.uniform(0, 45, n),
    "soil_saturation": rng.uniform(0, 1, n),
})
score = 0.04*df.humidity - 0.15*(df.pressure-1010) + 0.05*df.rain_prev_24h + rng.normal(0, 1, n)
df["rain_mm"] = np.clip(score*3 - 2, 0, None)
df["rain_yes"] = (df.rain_mm > 1).astype(int)
flood = 0.03*df.rain_prev_72h + 0.05*df.rain_mm + 2*df.soil_saturation
df["flood_risk"] = pd.cut(flood, [-1, 2.5, 4.5, 99], labels=[0, 1, 2]).astype(int)
land = 0.05*df.slope_deg + 2.5*df.soil_saturation + 0.02*df.rain_prev_72h
df["landslide_risk"] = pd.cut(land, [-1, 2.5, 4, 99], labels=[0, 1, 2]).astype(int)
df.to_csv("disaster_data.csv", index=False)
print(df.head())

import joblib
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, accuracy_score

FEATURES = ["humidity","pressure","temp","rain_prev_24h","rain_prev_72h","slope_deg","soil_saturation"]
X = df[FEATURES]
specs = {
    "rain_mm": RandomForestRegressor(n_estimators=150, random_state=0),
    "rain_yes": RandomForestClassifier(n_estimators=150, random_state=0),
    "flood_risk": RandomForestClassifier(n_estimators=150, random_state=0),
    "landslide_risk": RandomForestClassifier(n_estimators=150, random_state=0),
}
models = {}
for target, model in specs.items():
    Xtr, Xte, ytr, yte = train_test_split(X, df[target], test_size=0.2, random_state=0)
    model.fit(Xtr, ytr)
    pred = model.predict(Xte)
    metric = mean_absolute_error(yte, pred) if target == "rain_mm" else accuracy_score(yte, pred)
    print(target, round(metric, 3))
    models[target] = model
joblib.dump({"models": models, "features": FEATURES}, "resqnet_model.joblib")