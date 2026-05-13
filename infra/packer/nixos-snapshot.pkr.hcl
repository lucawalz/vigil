packer {
  required_plugins {
    hcloud = {
      version = ">= 1.5.0"
      source  = "github.com/hetznercloud/hcloud"
    }
  }
}

source "hcloud" "nixos" {
  token                = var.hcloud_token
  image                = "debian-12"
  location             = "fsn1"
  server_type          = "cpx22"
  ssh_username         = "root"
  ssh_private_key_file = var.ssh_private_key_file

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
      "nix run --accept-flake-config 'github:nix-community/nixos-anywhere?ref=1.13.0' -- --ssh-option 'IdentityFile=${var.ssh_private_key_file}' --ssh-option 'StrictHostKeyChecking=no' --ssh-option 'UserKnownHostsFile=/dev/null' --flake 'github:lucawalz/vigil/${var.nixos_commit_sha}?dir=infra/nixos#hetzner-${var.role}' root@${build.Host}"
    ]
  }

  provisioner "shell-local" {
    inline = [
      "sleep 120",
      "until ssh -i ${var.ssh_private_key_file} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes root@${build.Host} 'systemctl is-system-running --wait || true && sync' 2>/dev/null; do sleep 15; done"
    ]
  }

}
