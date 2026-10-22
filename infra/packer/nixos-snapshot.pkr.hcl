packer {
  required_plugins {
    hcloud = {
      version = ">= 1.5.0"
      source  = "github.com/hetznercloud/hcloud"
    }
  }
}

locals {
  vigil_labels = {
    "vigil-managed" = "true"
    "vigil-run"     = var.campaign_run_id
  }
  build_ssh = "ssh -i ${var.ssh_private_key_file} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes"
}

source "hcloud" "nixos" {
  token                = var.hcloud_token
  image                = "debian-12"
  location             = "hel1"
  server_type          = "cpx22"
  ssh_username         = "root"
  ssh_private_key_file = var.ssh_private_key_file

  snapshot_name = "vigil-nixos-${var.role}-${var.nixos_hash}"
  snapshot_labels = merge(local.vigil_labels, {
    "vigil-role"       = var.role
    "vigil-nixos-hash" = var.nixos_hash
  })
  server_labels   = local.vigil_labels
  ssh_keys_labels = local.vigil_labels

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
      "nix run --accept-flake-config 'github:nix-community/nixos-anywhere?ref=1.13.0' -- --extra-files /tmp/packer-extra-files --ssh-option 'IdentityFile=${var.ssh_private_key_file}' --ssh-option 'StrictHostKeyChecking=no' --ssh-option 'UserKnownHostsFile=/dev/null' --flake 'github:${var.github_repository}/${var.nixos_commit_sha}?dir=infra/nixos#vigil-${var.role}' root@${build.Host}"
    ]
  }

  provisioner "shell-local" {
    inline = [
      "sleep 120",
      "until ${local.build_ssh} root@${build.Host} 'systemctl is-system-running --wait || true && sync'; do sleep 15; done"
    ]
  }

  provisioner "shell-local" {
    inline = [
      "${local.build_ssh} root@${build.Host} 'systemctl stop k3s 2>/dev/null; rm -rf /var/lib/rancher/k3s/server /etc/rancher/k3s/k3s.yaml /etc/ssh/ssh_host_* /root/.ssh/id_ed25519 /root/.ssh/id_ed25519.pub && sync'"
    ]
  }

}
