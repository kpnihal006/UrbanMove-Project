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
  authorized_domains = [
    "localhost",
    "urbanmove-project-493010.firebaseapp.com",
    "urbanmove-project-493010.web.app",
    "frontend-5k2cszxnza-uc.a.run.app",
  ]

  depends_on = [google_project_service.apis]
}

# ── Google Sign-In provider ───────────────────────────────────────────────────
#
# Requires a web OAuth 2.0 client.  One-time setup:
#   1. GCP Console → APIs & Services → Credentials → Create Credentials
#      → OAuth client ID → Web application
#   2. Name: "UrbanMove Firebase Sign-In"
#   3. Authorised redirect URI:
#        https://urbanmove-project-493010.firebaseapp.com/__/auth/handler
#   4. Copy the Client ID and Client Secret into GitHub Secrets:
#        FIREBASE_GOOGLE_CLIENT_ID
#        FIREBASE_GOOGLE_CLIENT_SECRET
#   5. Re-run: terraform apply
#
# Alternatively: Firebase Console → Authentication → Sign-in method → Google
# (Firebase auto-creates the OAuth client for you).

resource "google_identity_platform_default_supported_idp_config" "google_sign_in" {
  # Only created when credentials have been supplied.
  count = (
    var.google_sign_in_client_id != "" &&
    var.google_sign_in_client_secret != ""
  ) ? 1 : 0

  enabled       = true
  idp_id        = "google.com"
  client_id     = var.google_sign_in_client_id
  client_secret = var.google_sign_in_client_secret
  project       = var.project_id

  depends_on = [google_identity_platform_config.default]
}
