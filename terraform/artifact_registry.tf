resource "google_artifact_registry_repository" "main" {
  provider      = google-beta
  location      = var.region
  repository_id = local.service_name
  format        = "DOCKER"
  description   = "Docker repository for EventFlow"
  labels        = local.labels

  docker_config {
    immutable_tags = true
  }
}
