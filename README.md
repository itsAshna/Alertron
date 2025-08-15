# Alertron (Kafka + Prometheus + Slack)

Alterton is an anomaly detection system that predicts anomalies on a live stream, exports Prometheus metrics, alerts to Slack when the fleet goes off-nominal, and visualizes everything in Grafana.

## ✨ Features

* **Streaming ML** with an Isolation Forest model (scikit-learn)
* **Hybrid pipeline:** Kafka (Redpanda) → FastAPI inference → Prometheus metrics
* **Alerting:** Prometheus rule → Alertmanager → Slack (Incoming Webhook or Bot)
* **Dashboards:** Grafana with panels for anomalies, throughput, latency
* **One-command up** with Docker Compose

## 🧱 Stack

* **Model/Serving:** Python 3.11, FastAPI, scikit-learn, joblib
* **Streaming:** Redpanda (Kafka-API compatible), aiokafka
* **Observability:** prometheus\_client, Prometheus, Alertmanager, Grafana
* **Infra:** Docker / Docker Compose

---

## ▶️ Quick start

```bash
# 0) Clone repo and cd in
git clone <YOUR REPO URL>
cd realtime_anomaly_alert  

# 1) Train the model once (writes artifacts/anomaly_iforest.joblib)
python model/train.py

# 2) Build and run the stack
docker compose up -d --build

# 3) Open the UIs
# FastAPI metrics:   http://localhost:8000/metrics
# Prometheus:        http://localhost:9090
# Alertmanager:      http://localhost:9093
# Grafana:           http://localhost:3000 (admin / admin on first login)
```

---

## 🔌 Ports

| Service                   | URL                                                            |
| ------------------------- | -------------------------------------------------------------- |
| Inference metrics         | [http://localhost:8000/metrics](http://localhost:8000/metrics) |
| Prometheus                | [http://localhost:9090](http://localhost:9090)                 |
| Alertmanager              | [http://localhost:9093](http://localhost:9093)                 |
| Grafana                   | [http://localhost:3000](http://localhost:3000)                 |
| Redpanda Admin            | [http://localhost:9644](http://localhost:9644)                 |

---

## 🗺️ Architecture

```
IoT generator → Kafka 'readings' topic
                        │
                        ▼
            FastAPI consumer (aiokafka)
     ┌─────────────────────────────────────┐
     │  - score with Isolation Forest      │
     │  - emit Prometheus metrics          │
     │  - (optional) produce 'anomalies'   │
     └─────────────────────────────────────┘
                        │
                  /metrics  ← Prometheus scrape
                        │
              Prometheus alert rules
                        │
                   Alertmanager
                        │
                       Slack
```

---


## ⚙️ How it works

* **Data:** each event has `[temperature, pressure, vibration]` (floats). The generator produces mostly normal values with a configurable anomaly rate.
* **Model:** Isolation Forest trains on synthetic “normal” samples; inference returns an anomaly score.
* **Metrics exposed:**

  * `anomaly_count_total{device_id,severity}`
  * `last_anomaly_score{device_id}`
  * `inference_latency_seconds_bucket` (+ `_count`, `_sum`)
  * `predictions_total`
  * `kafka_messages_consumed_total{topic}`
  * `kafka_errors_total`
* **Alert (default):**

  * **HighAnomalyRate**: fires when the fleet sees a burst of anomalies

    ```promql
    sum(increase(anomaly_count_total[5m])) > 50
    ```


---

## 📊 Grafana

### Import the ready dashboard

1. Open Grafana → **Dashboards → New → Import**.
2. Paste the dashboard JSON from this repo (see `docs/grafana-dashboard.json`).
3. Select your Prometheus datasource (`http://prometheus:9090` inside Docker).

### Handy PromQL (use as panels)

* Predictions/sec: `rate(predictions_total[1m])`
* Anomalies/min (fleet): `sum(increase(anomaly_count_total[1m]))`
* By severity (stack): `sum by (severity) (increase(anomaly_count_total[1m]))`
* Top 5 noisy devices (5m): `topk(5, sum by (device_id)(increase(anomaly_count_total[5m])))`
* p95 latency (ms): `1000 * histogram_quantile(0.95, sum by (le)(rate(inference_latency_seconds_bucket[5m])))`
* Kafka error %:

  ```
  100 * (sum(rate(kafka_errors_total[5m])) 
        / clamp_min(sum(rate(kafka_messages_consumed_total[5m])), 1))
  ```

---

## 🔔 Slack setup 

### A) Incoming Webhook 

1. Create a Slack channel (e.g., `#anomaly-alerts`).
2. Create a Slack App → **Incoming Webhooks → Activate** → **Add New Webhook to Workspace** → select the channel → copy URL (`https://hooks.slack.com/services/T…/B…/Z…`).
3. Edit `ops/alertmanager.yml` and set:

   ```yaml
   receivers:
     - name: slack-notifs
       slack_configs:
         - api_url: "https://hooks.slack.com/services/TXXX/BYYY/ZZZ"
           channel: "#anomaly-alerts"
           send_resolved: true
           title: "{{ .CommonAnnotations.summary }}"
           text: "{{ .CommonAnnotations.description }}"
   ```
4. Restart Alertmanager:

   ```bash
   docker compose restart alertmanager
   ```
