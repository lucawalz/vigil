terraform {
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
    sops = {
      source  = "carlpett/sops"
      version = "~> 1.1"
    }
  }
}

resource "random_password" "k3s_token" {
  length  = 64
  special = false
}

provider "hcloud" {
  token = var.hcloud_token
}

resource "hcloud_network" "vigil" {
  name     = "vigil-eval-${var.group_name}-${var.run_id}"
  ip_range = "10.0.0.0/24"
}

resource "hcloud_network_subnet" "vigil" {
  network_id   = hcloud_network.vigil.id
  type         = "cloud"
  network_zone = "eu-central"
  ip_range     = "10.0.0.0/24"
}

resource "hcloud_firewall" "vigil" {
  name = "vigil-eval-${var.group_name}-${var.run_id}"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "6443"
    source_ips = ["0.0.0.0/0", "::/0"]
  }
}
