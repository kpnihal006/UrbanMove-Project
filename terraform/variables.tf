variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "urbanmove-project-493010"
}

variable "project_number" {
  description = "GCP project number"
  type        = string
  default     = "72038880424"
}

variable "region" {
  description = "GCP region — us-central1 gives broadest always-free tier coverage"
  type        = string
  default     = "us-central1"
}

variable "google_maps_api_key" {
  description = "Google Maps API key — stored in Secret Manager, not in state"
  type        = string
  sensitive   = true
}

variable "firebase_api_key" {
  description = "Firebase web API key"
  type        = string
  sensitive   = true
}

variable "github_org" {
  description = "GitHub organisation or username for Workload Identity Federation"
  type        = string
  default     = "kpnihal006"
}

variable "github_repo" {
  description = "GitHub repository name for Workload Identity Federation"
  type        = string
  default     = "UrbanMove-Project"
}

variable "image_tag" {
  description = "Docker image tag to deploy (set by CI/CD pipeline)"
  type        = string
  default     = "latest"
}
