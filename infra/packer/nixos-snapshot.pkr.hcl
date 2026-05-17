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
  location             = "hel1"
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
      "rm -rf /tmp/packer-extra-files",
      "mkdir -p /tmp/packer-extra-files/root/.ssh",
      "chmod 700 /tmp/packer-extra-files/root/.ssh",
      "cp ${var.ssh_private_key_file}.pub /tmp/packer-extra-files/root/.ssh/authorized_keys",
      "chmod 600 /tmp/packer-extra-files/root/.ssh/authorized_keys",
      "nix run --accept-flake-config 'github:nix-community/nixos-anywhere?ref=1.13.0' -- --extra-files /tmp/packer-extra-files --ssh-option 'IdentityFile=${var.ssh_private_key_file}' --ssh-option 'StrictHostKeyChecking=no' --ssh-option 'UserKnownHostsFile=/dev/null' --flake 'github:lucawalz/vigil/${var.nixos_commit_sha}?dir=infra/nixos#hetzner-${var.role}' root@${build.Host}"
    ]
  }

  provisioner "shell-local" {
    inline = [
      "sleep 120",
      "until ssh -i ${var.ssh_private_key_file} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes root@${build.Host} 'systemctl is-system-running --wait || true && sync'; do sleep 15; done"
    ]
  }

}
