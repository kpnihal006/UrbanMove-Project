"""
log_to_mlflow.py
Trains the BigQuery ML model, evaluates it, and logs all metrics
to the self-hosted MLflow tracking server on Cloud Run.

Usage:
    MLFLOW_TRACKING_URI=https://mlflow-server-<hash>-uc.a.run.app \
    python ml/log_to_mlflow.py
"""

from __future__ import annotations

import os
import sys

import mlflow
from google.cloud import bigquery

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "urbanmove-project-493010")
BQ_DATASET     = os.getenv("BIGQUERY_DATASET", "urbanmove")

bq = bigquery.Client(project=GCP_PROJECT_ID)


def run_training() -> None:
    """Submit BigQuery ML training job."""
    print("Submitting BigQuery ML training job…")
    with open("ml/train_model.sql") as f:
        sql = f.read()
    job = bq.query(sql)
    job.result()
    print("Training complete.")


def evaluate_model() -> list[dict]:
    """Run ML.EVALUATE and return per-zone metrics."""
    sql = f"""
        SELECT
          zone_id,
          mean_absolute_error           AS mae,
          root_mean_squared_error       AS rmse,
          mean_absolute_percentage_error AS mape
        FROM ML.EVALUATE(
          MODEL `{GCP_PROJECT_ID}.{BQ_DATASET}.congestion_model`
        )
        ORDER BY mae ASC
    """
    rows = list(bq.query(sql).result())
    return [dict(row) for row in rows]


def count_training_rows() -> int:
    """Count rows used for training."""
    sql = f"""
        SELECT COUNT(*) AS cnt
        FROM `{GCP_PROJECT_ID}.{BQ_DATASET}.mobility_events`
        WHERE event_ts >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
          AND status = 'active'
    """
    rows = list(bq.query(sql).result())
    return int(rows[0].cnt) if rows else 0


def main() -> None:
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI")
    if not tracking_uri:
        print("ERROR: MLFLOW_TRACKING_URI is not set.")
        sys.exit(1)

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("urbanmove-congestion-prediction")

    with mlflow.start_run(run_name="bqml-arima-plus") as run:
        # ── Log parameters ───────────────────────────────────────
        mlflow.log_params({
            "model_type":         "ARIMA_PLUS",
            "data_frequency":     "per_minute",
            "horizon":            120,
            "confidence_level":   0.9,
            "auto_arima":         True,
            "clean_spikes_dips":  True,
            "holiday_region":     "FR",
            "training_window_days": 7,
            "gcp_project":        GCP_PROJECT_ID,
            "bq_dataset":         BQ_DATASET,
            "city":               "Paris",
        })

        # ── Train model ──────────────────────────────────────────
        run_training()

        # ── Log dataset size ─────────────────────────────────────
        n_rows = count_training_rows()
        mlflow.log_metric("training_rows", n_rows)
        print(f"Training rows: {n_rows:,}")

        # ── Evaluate and log per-zone metrics ────────────────────
        metrics = evaluate_model()
        print(f"Evaluated {len(metrics)} zones.")

        if metrics:
            avg_mae  = sum(m["mae"]  for m in metrics) / len(metrics)
            avg_rmse = sum(m["rmse"] for m in metrics) / len(metrics)
            avg_mape = sum(m["mape"] for m in metrics) / len(metrics)

            mlflow.log_metrics({
                "avg_mae":  round(avg_mae,  4),
                "avg_rmse": round(avg_rmse, 4),
                "avg_mape": round(avg_mape, 4),
                "n_zones":  len(metrics),
            })

            # Log per-zone metrics
            for row in metrics:
                zone_key = row["zone_id"].replace("-", "_").lower()
                mlflow.log_metrics({
                    f"{zone_key}_mae":  round(row["mae"],  4),
                    f"{zone_key}_rmse": round(row["rmse"], 4),
                    f"{zone_key}_mape": round(row["mape"], 4),
                })

            print(f"Average MAE: {avg_mae:.4f}")
            print(f"Average RMSE: {avg_rmse:.4f}")
            print(f"Average MAPE: {avg_mape:.4f}")

        # ── Tag the run ──────────────────────────────────────────
        mlflow.set_tags({
            "model_framework":    "BigQuery ML",
            "deployment_target":  "analytics-service /congestion/predict",
            "data_source":        f"{GCP_PROJECT_ID}.{BQ_DATASET}.mobility_events",
        })

        print(f"\nMLflow run ID: {run.info.run_id}")
        print(f"View at: {tracking_uri}/#/experiments")


if __name__ == "__main__":
    main()
