packer {
  required_plugins {
    hcloud = {
      version = ">= 1.5.0"
      source  = "github.com/hetznercloud/hcloud"
    }
  }
}

source "hcloud" "nixos" {
  token        = var.hcloud_token
  image        = "debian-12"
  location     = "fsn1"
  server_type  = "cpx22"
  ssh_username = "root"

  snapshot_name = "vigil-nixos-${var.role}-${var.nixos_hash}"
  snapshot_labels = {
    "vigil-role"       = var.role
    "vigil-nixos-hash" = var.nixos_hash
    "vigil-managed"    = "true"
  }

  ssh_handshake_attempts = 60
  ssh_timeout            = "15m"
}

build {
  sources = ["source.hcloud.nixos"]

  provisioner "shell-local" {
    inline = [
      "nix run --accept-flake-config 'github:nix-community/nixos-anywhere?ref=1.13.0' -- --flake 'github:lucawalz/vigil/${var.nixos_commit_sha}?dir=infra/nixos#hetzner-${var.role}' root@${build.Host}"
    ]
  }

  provisioner "shell" {
    pause_before = "60s"
    inline       = ["echo 'snapshot ready: vigil-nixos-${var.role}-${var.nixos_hash}'"]
  }
}
