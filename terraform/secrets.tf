locals {
  secret_names = [
    "DB_URL",
    "SUPABASE_JWKS_URL",
    "SUPABASE_JWT_ISSUER",
    "GEMINI_API_KEY",
    "GOOGLE_MAPS_API_KEY",
    "GOOGLE_CALENDAR_CREDENTIALS_JSON",
    "GOOGLE_OAUTH_REDIRECT_URI",
    "CALENDAR_TOKEN_KEY",
    "EXPO_ACCESS_TOKEN",
    "ADMIN_API_TOKEN",
    "ADMIN_OPERATOR_EMAILS",
    "ADMIN_USER_IDS",
    "YTDLP_COOKIE_FILE",
    "CORS_ALLOW_ORIGINS",
    "TRUSTED_HOSTS",
    "GRAFANA_ADMIN_PASSWORD",
  ]
}

resource "google_secret_manager_secret" "secrets" {
  for_each = toset(local.secret_names)

  secret_id = "${local.service_name}-${lower(each.value)}"
  labels    = local.labels

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "vm_secrets" {
  for_each = toset(local.secret_names)

  secret_id = google_secret_manager_secret.secrets[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.vm.email}"
}

resource "google_secret_manager_secret_iam_member" "github_secrets" {
  for_each = toset(local.secret_names)

  secret_id = google_secret_manager_secret.secrets[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.github_actions.email}"
}
