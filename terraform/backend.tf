# Terraform remote state backend
# The GCS bucket must be created BEFORE running terraform init:
#   gcloud storage buckets create gs://urbanmove-project-493010-tfstate \
#     --location=us-central1 --uniform-bucket-level-access
terraform {
  backend "gcs" {
    bucket = "urbanmove-project-493010-tfstate"
    prefix = "terraform/state"
  }
}
