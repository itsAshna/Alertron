import time, random, json, os
import requests
import numpy as np

SERVICE = os.environ.get("SERVICE_URL", "http://localhost:8000/ingest")
DEVICES = [f"edge-{i}" for i in range(1, 6)]
rng = np.random.default_rng(7)

def normal():
    return [
        float(rng.normal(50, 5)),   
        float(rng.normal(100, 10)), 
        float(rng.normal(0.5, 0.05))
    ]

def anomaly():
    return [
        float(rng.normal(70, 6)),
        float(rng.normal(140, 12)),
        float(rng.normal(0.9, 0.1))
    ]

while True:
    dev = random.choice(DEVICES)
    feats = anomaly() if rng.random() < 0.08 else normal()
    try:
        requests.post(SERVICE, json={"device_id": dev, "features": feats}, timeout=2)
    except Exception as e:
        print("post failed:", e)
    time.sleep(0.1)  