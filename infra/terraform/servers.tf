resource "hcloud_server" "master" {
  name        = "hetzner-master"
  server_type = "cx33"
  image       = "debian-12"
  location    = "nbg1"
  rescue      = "linux64"

  ssh_keys = [hcloud_ssh_key.operator.id]

  network {
    network_id = hcloud_network.vigil.id
    ip         = "10.0.0.10"
    alias_ips  = []
  }

  firewall_ids = [hcloud_firewall.vigil.id]

  depends_on = [hcloud_network_subnet.vigil]
}

module "install_master" {
  source = "github.com/nix-community/nixos-anywhere//terraform/all-in-one"

  nixos_system_attr      = "github:lucawalz/nixos-homelab/${var.nixos_homelab_branch}#nixosConfigurations.hetzner-master.config.system.build.toplevel"
  nixos_partitioner_attr = "github:lucawalz/nixos-homelab/${var.nixos_homelab_branch}#nixosConfigurations.hetzner-master.config.system.build.diskoScript"
  target_host            = hcloud_server.master.ipv4_address
  instance_id            = tostring(hcloud_server.master.id)
  build_on_remote        = true
  extra_files_script     = "${path.module}/scripts/inject-secrets.sh"
  copy_host_keys         = true
  extra_environment = {
    ROLE = "hetzner-master"
  }
}

resource "hcloud_server" "worker_1" {
  name        = "hetzner-worker-1"
  server_type = "cx23"
  image       = "debian-12"
  location    = "nbg1"
  rescue      = "linux64"

  ssh_keys = [hcloud_ssh_key.operator.id]

  network {
    network_id = hcloud_network.vigil.id
    ip         = "10.0.0.20"
    alias_ips  = []
  }

  firewall_ids = [hcloud_firewall.vigil.id]

  depends_on = [hcloud_network_subnet.vigil]
}

module "install_worker_1" {
  source = "github.com/nix-community/nixos-anywhere//terraform/all-in-one"

  nixos_system_attr      = "github:lucawalz/nixos-homelab/${var.nixos_homelab_branch}#nixosConfigurations.hetzner-worker-1.config.system.build.toplevel"
  nixos_partitioner_attr = "github:lucawalz/nixos-homelab/${var.nixos_homelab_branch}#nixosConfigurations.hetzner-worker-1.config.system.build.diskoScript"
  target_host            = hcloud_server.worker_1.ipv4_address
  instance_id            = tostring(hcloud_server.worker_1.id)
  build_on_remote        = true
  extra_files_script     = "${path.module}/scripts/inject-secrets.sh"
  copy_host_keys         = true
  extra_environment = {
    ROLE = "hetzner-worker-1"
  }
}

resource "hcloud_server" "worker_2" {
  name        = "hetzner-worker-2"
  server_type = "cx23"
  image       = "debian-12"
  location    = "nbg1"
  rescue      = "linux64"

  ssh_keys = [hcloud_ssh_key.operator.id]

  network {
    network_id = hcloud_network.vigil.id
    ip         = "10.0.0.30"
    alias_ips  = []
  }

  firewall_ids = [hcloud_firewall.vigil.id]

  depends_on = [hcloud_network_subnet.vigil]
}

module "install_worker_2" {
  source = "github.com/nix-community/nixos-anywhere//terraform/all-in-one"

  nixos_system_attr      = "github:lucawalz/nixos-homelab/${var.nixos_homelab_branch}#nixosConfigurations.hetzner-worker-2.config.system.build.toplevel"
  nixos_partitioner_attr = "github:lucawalz/nixos-homelab/${var.nixos_homelab_branch}#nixosConfigurations.hetzner-worker-2.config.system.build.diskoScript"
  target_host            = hcloud_server.worker_2.ipv4_address
  instance_id            = tostring(hcloud_server.worker_2.id)
  build_on_remote        = true
  extra_files_script     = "${path.module}/scripts/inject-secrets.sh"
  copy_host_keys         = true
  extra_environment = {
    ROLE = "hetzner-worker-2"
  }
}

resource "hcloud_server" "agent" {
  name        = "hetzner-agent"
  server_type = "cx23"
  image       = "debian-12"
  location    = "nbg1"
  rescue      = "linux64"

  ssh_keys = [hcloud_ssh_key.operator.id]

  network {
    network_id = hcloud_network.vigil.id
    ip         = "10.0.0.40"
    alias_ips  = []
  }

  firewall_ids = [hcloud_firewall.vigil.id]

  depends_on = [hcloud_network_subnet.vigil]
}

module "install_agent" {
  source = "github.com/nix-community/nixos-anywhere//terraform/all-in-one"

  nixos_system_attr      = "github:lucawalz/nixos-homelab/${var.nixos_homelab_branch}#nixosConfigurations.hetzner-agent.config.system.build.toplevel"
  nixos_partitioner_attr = "github:lucawalz/nixos-homelab/${var.nixos_homelab_branch}#nixosConfigurations.hetzner-agent.config.system.build.diskoScript"
  target_host            = hcloud_server.agent.ipv4_address
  instance_id            = tostring(hcloud_server.agent.id)
  build_on_remote        = true
  extra_files_script     = "${path.module}/scripts/inject-secrets.sh"
  copy_host_keys         = true
  extra_environment = {
    ROLE = "hetzner-agent"
  }
}
