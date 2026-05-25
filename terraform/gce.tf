data "google_compute_image" "debian" {
  family  = "debian-12"
  project = "debian-cloud"
}

resource "google_compute_address" "static_ip" {
  name    = "${var.vm_name}-ip"
  region  = var.region
  labels  = local.labels
}

resource "google_compute_firewall" "api" {
  name    = "${var.vm_name}-allow-api"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["${var.api_port}"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.vm_name]
}

resource "google_compute_firewall" "caddy_http" {
  count   = var.domain != "" ? 1 : 0
  name    = "${var.vm_name}-allow-http"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = [var.vm_name]
}

resource "google_compute_instance" "vm" {
  name         = var.vm_name
  zone         = var.zone
  machine_type = var.machine_type
  tags         = [var.vm_name]

  labels = local.labels

  boot_disk {
    initialize_params {
      image = data.google_compute_image.debian.self_link
      size  = var.disk_size_gb
      type  = "pd-balanced"
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.static_ip.address
    }
  }

  service_account {
    email  = google_service_account.vm.email
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  metadata = {
    startup-script = file("${path.module}/startup-script.sh")
  }

  depends_on = [
    google_service_account.vm,
    google_compute_address.static_ip,
  ]
}
