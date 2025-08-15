import os, json, time, asyncio
from typing import List, Optional
from fastapi import FastAPI, Response
from pydantic import BaseModel
import joblib
import numpy as np
import contextlib


from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

ART = joblib.load("/app/artifacts/anomaly_iforest.joblib")
SCALER, MODEL = ART["scaler"], ART["model"]

app = FastAPI(title="Hybrid Anomaly Service (Kafka + Prometheus)")

INFER_LATENCY = Histogram("inference_latency_seconds", "Inference latency")
ANOMALY_COUNT = Counter("anomaly_count_total", "Total anomalies flagged", ["device_id", "severity"])
LAST_SCORE = Gauge("last_anomaly_score", "Last anomaly score per device (higher=worse)", ["device_id"])
REQUESTS = Counter("requests_total", "Total /ingest requests", ["status"])
PRED_RATE = Counter("predictions_total", "Total predictions made")
KAFKA_CONSUMED = Counter("kafka_messages_consumed_total", "Kafka messages consumed", ["topic"])
KAFKA_ERRORS = Counter("kafka_errors_total", "Kafka consumer/producer errors")

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "redpanda:9092")
READINGS_TOPIC = os.getenv("KAFKA_READINGS_TOPIC", "readings")
ANOMALIES_TOPIC = os.getenv("KAFKA_ANOMALIES_TOPIC", "anomalies")
GROUP_ID = os.getenv("KAFKA_GROUP_ID", "anomaly-service")

_consumer: AIOKafkaConsumer = None
_producer: AIOKafkaProducer = None
_consume_task: asyncio.Task = None

class Reading(BaseModel):
    device_id: str
    features: List[float]    
    ts: Optional[float] = None

def _score_and_record(r: Reading) -> dict:
    t0 = time.time()
    x = np.array(r.features, dtype=np.float32).reshape(1, -1)
    x = SCALER.transform(x)

    raw = MODEL.score_samples(x)[0]     #
    anomaly_score = float(-raw)         
    is_anom = MODEL.predict(x)[0] == -1

    if anomaly_score < 0.1:
        severity = "low"
    elif anomaly_score < 0.3:
        severity = "medium"
    else:
        severity = "high"

    LAST_SCORE.labels(r.device_id).set(anomaly_score)
    if is_anom:
        ANOMALY_COUNT.labels(r.device_id, severity).inc()

    PRED_RATE.inc()
    INFER_LATENCY.observe(time.time() - t0)

    return {
        "device_id": r.device_id,
        "anomaly": bool(is_anom),
        "severity": severity if is_anom else "none",
        "anomaly_score": anomaly_score,
        "ts": r.ts
    }

@app.post("/ingest")
def ingest(r: Reading):
    try:
        out = _score_and_record(r)
        REQUESTS.labels("200").inc()
        return out
    except Exception as e:
        REQUESTS.labels("500").inc()
        return {"error": str(e)}

@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)

async def _consume_loop():
    global _consumer, _producer
    try:
        async for msg in _consumer:
            try:
                KAFKA_CONSUMED.labels(msg.topic).inc()
                payload = msg.value  
                r = Reading(**payload)
                result = _score_and_record(r)

                if result["anomaly"]:
                    await _producer.send_and_wait(ANOMALIES_TOPIC, value=result)
            except Exception:
                KAFKA_ERRORS.inc()
    except asyncio.CancelledError:
        pass 

@app.on_event("startup")
async def on_startup():
    global _consumer, _producer, _consume_task
    _consumer = AIOKafkaConsumer(
        READINGS_TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id=GROUP_ID,
        enable_auto_commit=True,
        auto_offset_reset="latest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    _producer = AIOKafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )
    await _consumer.start()
    await _producer.start()
    _consume_task = asyncio.create_task(_consume_loop())

@app.on_event("shutdown")
async def on_shutdown():
    global _consumer, _producer, _consume_task
    if _consume_task:
        _consume_task.cancel()
        with contextlib.suppress(Exception):
            await _consume_task
    if _consumer:
        await _consumer.stop()
    if _producer:
        await _producer.stop()
