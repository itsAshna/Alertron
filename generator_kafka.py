import os, json, asyncio, random, time
import numpy as np
from aiokafka import AIOKafkaProducer

ANOMALY_RATE = float(os.getenv("ANOMALY_RATE", "0.08"))
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
TOPIC = os.getenv("KAFKA_READINGS_TOPIC", "readings")
DEVICES = [f"edge-{i}" for i in range(1, 6)]
rng = np.random.default_rng(7)

def normal():
    return [
        float(rng.normal(50, 5)),
        float(rng.normal(100, 10)),
        float(rng.normal(0.5, 0.05)),
    ]

def anomaly():
    return [
        float(rng.normal(70, 6)),
        float(rng.normal(140, 12)),
        float(rng.normal(0.9, 0.1)),
    ]

async def main():
    producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await producer.start()
    try:
        while True:
            dev = random.choice(DEVICES)
            feats = anomaly() if rng.random() < ANOMALY_RATE else normal()
            msg = {"device_id": dev, "features": feats, "ts": time.time()}
            await producer.send_and_wait(TOPIC, value=msg)
            await asyncio.sleep(0.1)  # ~10 msgs/sec
    finally:
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(main())
