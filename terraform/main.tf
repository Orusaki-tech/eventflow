locals {
  service_name = "eventflow"
  api_port     = var.api_port
  labels = {
    service = local.service_name
    managed = "terraform"
  }
}

# --- Workload Identity Federation for GitHub Actions ---
resource "google_iam_workload_identity_pool" "github" {
  provider                  = google-beta
  workload_identity_pool_id = "${local.service_name}-github-pool"
  display_name              = "EventFlow GitHub Actions"
  description               = "Workload Identity Pool for GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  provider                           = google-beta
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "${local.service_name}-github-provider"
  display_name                       = "EventFlow GitHub Provider"
  description                        = "OIDC provider bound to ${var.github_owner}/${var.github_repo}"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# --- Service account for GitHub Actions (CI/CD) ---
resource "google_service_account" "github_actions" {
  account_id   = "eventflow-gh-actions"
  display_name = "EventFlow GitHub Actions"
  description  = "Used by GitHub Actions for CI/CD operations"
}

resource "google_service_account_iam_member" "github_actions_impersonation" {
  service_account_id = google_service_account.github_actions.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_owner}/${var.github_repo}"
}

# --- Service account for GCE VM ---
resource "google_service_account" "vm" {
  account_id   = "eventflow-vm"
  display_name = "EventFlow GCE VM"
  description  = "Service account attached to the EventFlow GCE VM"
}

# --- GCS bucket for Terraform state ---
resource "google_storage_bucket" "terraform_state" {
  name          = "${local.service_name}-terraform-state"
  location      = var.region
  storage_class = "STANDARD"
  versioning {
    enabled = true
  }
  public_access_prevention = "enforced"
  labels                   = local.labels
}
