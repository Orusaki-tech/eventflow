output "vm_external_ip" {
  description = "External IP of the GCE VM"
  value       = google_compute_address.static_ip.address
}

output "artifact_registry_repo" {
  description = "Docker repository path for Artifact Registry"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.main.repository_id}"
}

output "github_actions_service_account" {
  description = "Service account email for GitHub Actions"
  value       = google_service_account.github_actions.email
}

output "workload_identity_provider" {
  description = "Workload Identity Provider name for GitHub Actions"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "vm_service_account" {
  description = "Service account email attached to the GCE VM"
  value       = google_service_account.vm.email
}

output "secrets" {
  description = "Secret Manager secret names"
  value = {
    for k, v in google_secret_manager_secret.secrets : k => v.name
  }
}

output "terraform_state_bucket" {
  description = "GCS bucket for Terraform state"
  value       = google_storage_bucket.terraform_state.name
}
