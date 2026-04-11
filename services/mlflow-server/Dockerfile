FROM python:3.12-slim
WORKDIR /mlflow

RUN pip install --no-cache-dir \
    mlflow==2.19.0 \
    google-cloud-storage==2.19.0 \
    psutil==6.1.0

RUN mkdir -p /mlflow/data

ENV PYTHONUNBUFFERED=1 \
    MLFLOW_BACKEND_STORE_URI=sqlite:////mlflow/data/mlflow.db \
    PORT=8080

EXPOSE 8080

CMD mlflow server \
    --backend-store-uri "${MLFLOW_BACKEND_STORE_URI}" \
    --artifacts-destination "gs://${GCS_BUCKET}/artifacts" \
    --host 0.0.0.0 \
    --port 8080 \
    --workers 1
