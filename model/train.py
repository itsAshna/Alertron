import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path

rng = np.random.default_rng(42)

N = 50_000
X_normal = np.column_stack([
    rng.normal(50, 5, N),  
    rng.normal(100, 10, N), 
    rng.normal(0.5, 0.05, N)
]).astype(np.float32)

scaler = StandardScaler().fit(X_normal)
Xn = scaler.transform(X_normal)

iso = IsolationForest(
    n_estimators=200,
    contamination=0.01,
    random_state=42
).fit(Xn)

Path("artifacts").mkdir(exist_ok=True, parents=True)
joblib.dump({"scaler": scaler, "model": iso}, "artifacts/anomaly_iforest.joblib")
print("Saved artifacts/anomaly_iforest.joblib")
