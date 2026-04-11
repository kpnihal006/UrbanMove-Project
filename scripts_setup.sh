#!/usr/bin/env bash
# ============================================================
# UrbanMove — One-shot GCP + GitHub setup script
# Run this ONCE after cloning the repo.
# Prerequisites: gcloud CLI, gh CLI, terraform installed
# ============================================================
set -euo pipefail

PROJECT_ID="urbanmove-project-493010"
REGION="us-central1"

echo "=== Step 1: Set GCP project ==="
gcloud config set project "$PROJECT_ID"
gcloud auth application-default login

echo "=== Step 2: Enable APIs ==="
gcloud services enable \
  run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com firestore.googleapis.com \
  pubsub.googleapis.com bigquery.googleapis.com \
  storage.googleapis.com secretmanager.googleapis.com \
  cloudscheduler.googleapis.com monitoring.googleapis.com \
  cloudtrace.googleapis.com identitytoolkit.googleapis.com \
  iamcredentials.googleapis.com firebase.googleapis.com \
  routes.googleapis.com maps-backend.googleapis.com

echo "=== Step 3: Create Terraform state bucket ==="
gcloud storage buckets create "gs://${PROJECT_ID}-tfstate" \
  --location="$REGION" --uniform-bucket-level-access || echo "Bucket may already exist"

echo "=== Step 4: Configure Docker ==="
gcloud auth configure-docker "us-central1-docker.pkg.dev" --quiet

echo "=== Step 5: Terraform deploy ==="
cd terraform
cp terraform.tfvars.example terraform.tfvars
echo ""
echo ">>> EDIT terraform/terraform.tfvars and fill in:"
echo "    google_maps_api_key = \"YOUR_MAPS_KEY\""
echo "    firebase_api_key    = \"YOUR_FIREBASE_KEY\""
echo ""
read -p "Press ENTER after editing terraform.tfvars..."
terraform init
terraform apply -auto-approve

echo "=== Step 6: Set GitHub Secrets ==="
WIF_PROVIDER=$(terraform output -raw workload_identity_provider)
SA_EMAIL=$(terraform output -raw cicd_service_account)
echo ""
echo ">>> Add these secrets to GitHub (Settings → Secrets → Actions):"
echo "    GCP_WIF_PROVIDER = $WIF_PROVIDER"
echo "    GCP_SA_EMAIL     = $SA_EMAIL"
echo "    GOOGLE_MAPS_API_KEY       = YOUR_MAPS_API_KEY"
echo "    NEXT_PUBLIC_FIREBASE_API_KEY = YOUR_FIREBASE_API_KEY"
echo "    NEXT_PUBLIC_FIREBASE_APP_ID  = YOUR_FIREBASE_APP_ID"
echo "    FIREBASE_API_KEY             = YOUR_FIREBASE_API_KEY"
echo ""
echo "=== Setup complete! Push to main to trigger deployment. ==="
