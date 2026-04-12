FROM python:3.12-slim
WORKDIR /mlflow

RUN pip install --no-cache-dir \
    mlflow==2.19.0 \
    google-cloud-storage==2.19.0 \
    psutil==6.1.0

ENV PYTHONUNBUFFERED=1 \
    MLFLOW_BACKEND_STORE_URI=sqlite:////tmp/mlflow.db \
    PORT=8080

EXPOSE 8080

# On every cold start:
#   1. Pull the latest mlflow.db from GCS (if it exists)
#   2. Start the MLflow server
#   3. On SIGTERM push mlflow.db back to GCS before exiting
#
# This makes the SQLite backend survive container restarts at the cost
# of ~1-2 s extra cold-start time.  A proper production setup would
# use Cloud SQL, but GCS sync is free and sufficient for a demo.
CMD ["sh", "-c", "\
  echo 'Pulling mlflow.db from GCS...' && \
  gsutil cp gs://${GCS_BUCKET}/mlflow.db /tmp/mlflow.db 2>/dev/null || echo 'No existing DB found, starting fresh.' && \
  trap 'echo Pushing mlflow.db to GCS...; gsutil cp /tmp/mlflow.db gs://${GCS_BUCKET}/mlflow.db; exit' TERM INT && \
  mlflow server \
    --backend-store-uri \"${MLFLOW_BACKEND_STORE_URI}\" \
    --artifacts-destination \"gs://${GCS_BUCKET}/artifacts\" \
    --host 0.0.0.0 --port 8080 --workers 1 --serve-artifacts & \
  wait $!"]
