variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "us-central1-a"
}

variable "vm_name" {
  description = "GCE VM name"
  type        = string
  default     = "eventflow-api"
}

variable "machine_type" {
  description = "GCE machine type"
  type        = string
  default     = "e2-small"
}

variable "disk_size_gb" {
  description = "Boot disk size in GB"
  type        = number
  default     = 30
}

variable "api_port" {
  description = "API port"
  type        = number
  default     = 8000
}

variable "github_owner" {
  description = "GitHub owner (user or org) for Workload Identity Federation"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name for Workload Identity Federation"
  type        = string
}

variable "grafana_admin_password" {
  description = "Grafana admin password (stored in Secret Manager)"
  type        = string
  sensitive   = true
  default     = null
}

variable "domain" {
  description = "Domain for the API (e.g. api.eventflow.app). Leave empty to skip TLS."
  type        = string
  default     = ""
}
