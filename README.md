# UrbanMove — Cloud-Native Smart Mobility Platform

> **EPITA Final Cloud Computing Project · Spring 2025**
> Team: Nihal K P · Prerona Mitra
> Platform: Google Cloud Platform (100% Always-Free tier)
> City: Paris, France

---

## Architecture Overview

```
Internet → Cloud Run (HTTPS *.run.app)
             ├── frontend (Next.js 15)
             ├── user-service (FastAPI + Firestore)
             ├── routing-engine (FastAPI + Maps API)
             └── analytics-service (FastAPI + BigQuery ML)

IoT Simulator (Cloud Run Job)
  → Pub/Sub raw-events topic
    → push subscription
      → stream-processor (Cloud Run function)
        ├── Firestore  (live vehicle state)
        └── BigQuery   (historical events → ML model)

MLflow Server (Cloud Run) ← BigQuery ML metrics
Grafana Cloud ← Cloud Monitoring metrics
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| gcloud CLI | latest | brew install google-cloud-sdk |
| Terraform | ≥ 1.7 | brew install terraform |
| Docker | ≥ 25 | brew install --cask docker |
| Node.js | ≥ 20 | brew install node |
| Python | ≥ 3.12 | brew install python |

---

## Step 0 — One-time GCP Setup

```bash
# Set project
gcloud config set project urbanmove-project-493010
gcloud auth application-default login

# Enable all required APIs (takes ~2 min)
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com firestore.googleapis.com \
  pubsub.googleapis.com bigquery.googleapis.com \
  storage.googleapis.com secretmanager.googleapis.com \
  cloudscheduler.googleapis.com monitoring.googleapis.com \
  cloudtrace.googleapis.com identitytoolkit.googleapis.com \
  iamcredentials.googleapis.com firebase.googleapis.com \
  routes.googleapis.com maps-backend.googleapis.com

# Create Terraform state bucket
gcloud storage buckets create gs://urbanmove-project-493010-tfstate \
  --location=us-central1 --uniform-bucket-level-access

# Authenticate Docker to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev
```

---

## Step 1 — Get Required API Keys

### Google Maps API Key
1. Go to https://console.cloud.google.com/apis/credentials
2. Click **Create credentials → API key**
3. Click **Restrict key** → select **Maps JavaScript API** + **Directions API**
4. Copy the key — you'll need it in Step 2

### Firebase Web Config
1. Go to https://console.firebase.google.com
2. Click **Add project** → select `urbanmove-project-493010`
3. Go to **Project settings → Web apps → Add app**
4. Name it `urbanmove-web` → copy the full config object
5. You need: `apiKey`, `authDomain`, `projectId`, `storageBucket`, `messagingSenderId`, `appId`

### Enable Firebase Auth
1. In Firebase console → **Authentication → Sign-in method**
2. Enable **Email/Password** and **Google**

---

## Step 2 — Configure Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars and fill in:
# google_maps_api_key = "YOUR_GOOGLE_MAPS_API_KEY"
# firebase_api_key    = "YOUR_FIREBASE_API_KEY"
nano terraform.tfvars
```

---

## Step 3 — Deploy Infrastructure

```bash
cd terraform
terraform init
terraform plan    # Review what will be created
terraform apply   # Type 'yes' when prompted (~5 min)

# Save the outputs — you'll need them for GitHub Secrets
terraform output
```

---

## Step 4 — Build and Push Docker Images

```bash
# From repo root
export PROJECT=urbanmove-project-493010
export REGION=us-central1
export AR="${REGION}-docker.pkg.dev/${PROJECT}/urbanmove"

# Build and push all services
for svc in user-service routing-engine analytics-service iot-simulator stream-processor mlflow-server; do
  docker build -t ${AR}/${svc}:latest services/${svc}
  docker push ${AR}/${svc}:latest
  echo "✓ ${svc} pushed"
done

# Build frontend (with real env vars)
docker build \
  --build-arg NEXT_PUBLIC_FIREBASE_API_KEY="YOUR_FIREBASE_API_KEY" \
  --build-arg NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="urbanmove-project-493010.firebaseapp.com" \
  --build-arg NEXT_PUBLIC_FIREBASE_PROJECT_ID="urbanmove-project-493010" \
  --build-arg NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET="urbanmove-project-493010.appspot.com" \
  --build-arg NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID="72038880424" \
  --build-arg NEXT_PUBLIC_FIREBASE_APP_ID="YOUR_FIREBASE_APP_ID" \
  --build-arg NEXT_PUBLIC_GOOGLE_MAPS_API_KEY="YOUR_MAPS_KEY" \
  --build-arg NEXT_PUBLIC_USER_SERVICE_URL="$(terraform -chdir=terraform output -raw user_service_url)" \
  --build-arg NEXT_PUBLIC_ROUTING_ENGINE_URL="$(terraform -chdir=terraform output -raw routing_engine_url)" \
  --build-arg NEXT_PUBLIC_ANALYTICS_SERVICE_URL="$(terraform -chdir=terraform output -raw analytics_service_url)" \
  -t ${AR}/frontend:latest frontend/

docker push ${AR}/frontend:latest
```

---

## Step 5 — Deploy Services to Cloud Run

```bash
# Update all Cloud Run services with the new images
for svc in stream-processor user-service routing-engine analytics-service mlflow-server frontend; do
  gcloud run services update ${svc} \
    --region=${REGION} \
    --image=${AR}/${svc}:latest
  echo "✓ ${svc} deployed"
done

# Get all public URLs
terraform -chdir=terraform output
```

---

## Step 6 — Configure GitHub Actions (CI/CD)

Add these secrets to your GitHub repo (Settings → Secrets → Actions):

| Secret | Value | Where to get it |
|--------|-------|-----------------|
| `GCP_WIF_PROVIDER` | `terraform output workload_identity_provider` | After terraform apply |
| `GCP_SA_EMAIL` | `terraform output cicd_service_account` | After terraform apply |
| `GOOGLE_MAPS_API_KEY` | Your Maps API key | Step 1 |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Your Firebase apiKey | Step 1 |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | Your Firebase appId | Step 1 |
| `FIREBASE_API_KEY` | Same as above | Step 1 |

---

## Step 7 — Run the IoT Simulator

```bash
# Trigger the simulator manually (runs 4 minutes of vehicle events)
gcloud run jobs execute iot-simulator --region=us-central1 --wait

# Or it triggers automatically every 5 minutes via Cloud Scheduler
gcloud scheduler jobs list --location=us-central1
```

---

## Step 8 — Train the ML Model

```bash
# After at least 1 hour of IoT simulator data has accumulated:
bq query --use_legacy_sql=false --project_id=urbanmove-project-493010 < ml/train_model.sql

# Evaluate the model
bq query --use_legacy_sql=false --project_id=urbanmove-project-493010 < ml/evaluate_model.sql

# Log to MLflow
export MLFLOW_TRACKING_URI=$(terraform -chdir=terraform output -raw mlflow_server_url)
pip install mlflow google-cloud-bigquery
python ml/log_to_mlflow.py
```

---

## Step 9 — Set Up Grafana Dashboard

1. Go to https://kpnihal006fr.grafana.net
2. **Connections → Add new connection → Google Cloud Monitoring**
3. Configure with your GCP project ID and service account
4. **Dashboards → Import → Upload JSON file** → select `exports/grafana_dashboard.json`

---

## Step 10 — Run Load Tests

```bash
pip install locust

# Against deployed GCP services
export ANALYTICS_SERVICE_URL=$(terraform -chdir=terraform output -raw analytics_service_url)
export ROUTING_ENGINE_URL=$(terraform -chdir=terraform output -raw routing_engine_url)

locust --headless -u 50 -r 5 --run-time 120s \
  --host ${ANALYTICS_SERVICE_URL} \
  -f tests/locustfile.py

# Watch Cloud Run scale in Cloud Monitoring during the test
```

---

## Local Development

```bash
# 1. Copy and fill .env
cp .env.example .env
# Edit .env with your real Firebase config and Maps API key

# 2. Start full stack
docker compose up --build

# Services available at:
# Frontend:          http://localhost:3000
# User service:      http://localhost:8001/docs
# Routing engine:    http://localhost:8002/docs
# Analytics:         http://localhost:8003/docs
# MLflow:            http://localhost:5000
```

---

## Free Tier Usage Summary

| Service | Free Limit | Estimated Usage |
|---------|-----------|-----------------|
| Cloud Run | 2M req + 180K vCPU-s/mo | ~40K req / ~9K vCPU-s |
| Firestore | 50K reads + 20K writes/day | ~10K reads / ~3K writes |
| BigQuery | 1 TB queries + 10 GB/mo | ~5 GB queries |
| Pub/Sub | 10 GB/mo | ~800 MB |
| Cloud Storage | 5 GB | ~400 MB |
| Artifact Registry | 500 MB | ~150 MB |
| Firebase Auth | 10K MAU | ~5 users |
| **Total cost** | | **$0.00/month** |

---

## Repository Structure

```
urbanmove/
├── .github/workflows/   # CI (lint+test+trivy) + CD (build+deploy)
├── terraform/           # Complete GCP infrastructure as code
├── services/
│   ├── user-service/    # FastAPI: auth, profiles, trips
│   ├── routing-engine/  # FastAPI: Google Maps Directions
│   ├── analytics-service/ # FastAPI: BigQuery + ML predictions
│   ├── iot-simulator/   # Paris vehicle GPS event generator
│   ├── stream-processor/ # Pub/Sub push → Firestore + BigQuery
│   └── mlflow-server/   # MLflow experiment tracking
├── frontend/            # Next.js 15: map, dashboard, auth
├── ml/                  # BigQuery ML training + MLflow logging
├── tests/               # Locust load tests + pytest unit tests
├── exports/             # Grafana dashboard, IAM, BQ schema
└── docker-compose.yml   # Full local development stack
```

---

## Team

| Name | GitHub | Role |
|------|--------|------|
| Nihal K P | @kpnihal006 | Cloud architecture, backend services, Terraform |
| Prerona Mitra | @prerna2912 | Frontend, ML pipeline, observability |

**EPITA — Cloud Computing Final Project — Spring 2025**
