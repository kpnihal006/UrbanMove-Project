# ── Firebase / Identity Platform ─────────────────────────────────────────────
#
# Initialises Identity Platform for this project and sets the list of domains
# that are allowed to trigger OAuth redirects (auth/unauthorized-domain fix).
#
# This resource CREATES the config the first time; subsequent applies PATCH it.
# Cloud Run URL is known after the first Terraform apply that creates the
# frontend service, so add it here and re-apply.

resource "google_identity_platform_config" "default" {
  project = var.project_id

  # Domains that Firebase Authentication will accept sign-in redirects from.
  # Add the Cloud Run frontend URL after the first deploy.
  authorized_domains = [
    "localhost",
    "urbanmove-project-493010.firebaseapp.com",
    "urbanmove-project-493010.web.app",
    "frontend-5k2cszxnza-uc.a.run.app",
  ]

  depends_on = [google_project_service.apis]
}
