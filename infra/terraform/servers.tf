resource "hcloud_server" "master" {
  name        = "hetzner-master"
  server_type = "cx33"
  image       = "debian-12"
  location    = "nbg1"

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

  nixos_system_attr      = "github:lucawalz/vigil/${var.vigil_branch}?dir=infra/nixos#nixosConfigurations.hetzner-master.config.system.build.toplevel"
  nixos_partitioner_attr = "github:lucawalz/vigil/${var.vigil_branch}?dir=infra/nixos#nixosConfigurations.hetzner-master.config.system.build.diskoScript"
  target_host            = hcloud_server.master.ipv4_address
  instance_id            = tostring(hcloud_server.master.id)
  build_on_remote        = true
  debug_logging          = true
  install_bootloader     = true
  nix_options            = { "tarball-ttl" = "0" }
}

resource "null_resource" "k3s_token_master" {
  depends_on = [module.install_master]

  triggers = {
    instance_id = tostring(hcloud_server.master.id)
  }

  connection {
    type        = "ssh"
    host        = hcloud_server.master.ipv4_address
    user        = "root"
    private_key = file(pathexpand(var.ssh_private_key_path))
  }

  provisioner "remote-exec" {
    inline = [
      "mkdir -p /etc/k3s /etc/rancher/k3s",
      "echo '${random_password.k3s_token.result}' > /etc/k3s/token",
      "chmod 400 /etc/k3s/token",
      "printf 'tls-san:\\n  - ${hcloud_server.master.ipv4_address}\\n' > /etc/rancher/k3s/config.yaml",
      "systemctl stop k3s || true",
      "rm -f /var/lib/rancher/k3s/server/tls/dynamic-cert.json",
      "systemctl start k3s",
    ]
  }
}

resource "hcloud_server" "worker_1" {
  name        = "hetzner-worker-1"
  server_type = "cx23"
  image       = "debian-12"
  location    = "nbg1"

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

  nixos_system_attr      = "github:lucawalz/vigil/${var.vigil_branch}?dir=infra/nixos#nixosConfigurations.hetzner-worker-1.config.system.build.toplevel"
  nixos_partitioner_attr = "github:lucawalz/vigil/${var.vigil_branch}?dir=infra/nixos#nixosConfigurations.hetzner-worker-1.config.system.build.diskoScript"
  target_host            = hcloud_server.worker_1.ipv4_address
  instance_id            = tostring(hcloud_server.worker_1.id)
  build_on_remote        = true
  debug_logging          = true
  install_bootloader     = true
  nix_options            = { "tarball-ttl" = "0" }
}

resource "null_resource" "k3s_token_worker_1" {
  depends_on = [module.install_worker_1]

  triggers = {
    instance_id = tostring(hcloud_server.worker_1.id)
  }

  connection {
    type        = "ssh"
    host        = hcloud_server.worker_1.ipv4_address
    user        = "root"
    private_key = file(pathexpand(var.ssh_private_key_path))
  }

  provisioner "remote-exec" {
    inline = [
      "mkdir -p /etc/k3s",
      "echo '${random_password.k3s_token.result}' > /etc/k3s/token",
      "chmod 400 /etc/k3s/token"
    ]
  }
}

resource "hcloud_server" "worker_2" {
  name        = "hetzner-worker-2"
  server_type = "cx23"
  image       = "debian-12"
  location    = "nbg1"

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

  nixos_system_attr      = "github:lucawalz/vigil/${var.vigil_branch}?dir=infra/nixos#nixosConfigurations.hetzner-worker-2.config.system.build.toplevel"
  nixos_partitioner_attr = "github:lucawalz/vigil/${var.vigil_branch}?dir=infra/nixos#nixosConfigurations.hetzner-worker-2.config.system.build.diskoScript"
  target_host            = hcloud_server.worker_2.ipv4_address
  instance_id            = tostring(hcloud_server.worker_2.id)
  build_on_remote        = true
  debug_logging          = true
  install_bootloader     = true
  nix_options            = { "tarball-ttl" = "0" }
}

resource "null_resource" "k3s_token_worker_2" {
  depends_on = [module.install_worker_2]

  triggers = {
    instance_id = tostring(hcloud_server.worker_2.id)
  }

  connection {
    type        = "ssh"
    host        = hcloud_server.worker_2.ipv4_address
    user        = "root"
    private_key = file(pathexpand(var.ssh_private_key_path))
  }

  provisioner "remote-exec" {
    inline = [
      "mkdir -p /etc/k3s",
      "echo '${random_password.k3s_token.result}' > /etc/k3s/token",
      "chmod 400 /etc/k3s/token"
    ]
  }
}

resource "hcloud_server" "agent" {
  name        = "hetzner-agent"
  server_type = "cx23"
  image       = "debian-12"
  location    = "nbg1"

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

  nixos_system_attr      = "github:lucawalz/vigil/${var.vigil_branch}?dir=infra/nixos#nixosConfigurations.hetzner-agent.config.system.build.toplevel"
  nixos_partitioner_attr = "github:lucawalz/vigil/${var.vigil_branch}?dir=infra/nixos#nixosConfigurations.hetzner-agent.config.system.build.diskoScript"
  target_host            = hcloud_server.agent.ipv4_address
  instance_id            = tostring(hcloud_server.agent.id)
  build_on_remote        = true
  debug_logging          = true
  install_bootloader     = true
  nix_options            = { "tarball-ttl" = "0" }
}

resource "null_resource" "kubeconfig" {
  depends_on = [null_resource.k3s_token_master]

  triggers = {
    master_ip = hcloud_server.master.ipv4_address
  }

  provisioner "local-exec" {
    command = <<-EOF
      DEADLINE=$(($(date +%s) + 600))
      until ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 \
          root@${hcloud_server.master.ipv4_address} "kubectl get nodes" > /dev/null 2>&1; do
        if [ $(date +%s) -gt $DEADLINE ]; then echo "K3s API not ready after 10 minutes"; exit 1; fi
        sleep 5
      done
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@${hcloud_server.master.ipv4_address} "cat /etc/rancher/k3s/k3s.yaml" \
        | sed 's|https://127.0.0.1:6443|https://${hcloud_server.master.ipv4_address}:6443|' \
        | sed 's/name: default/name: hetzner-vigil/g' \
        | sed 's/cluster: default/cluster: hetzner-vigil/g' \
        | sed 's/user: default/user: hetzner-vigil/g' \
        | sed 's/current-context: default/current-context: hetzner-vigil/' \
        > ~/.kube/hetzner-vigil
      chmod 600 ~/.kube/hetzner-vigil
    EOF
  }
}

resource "null_resource" "kubeconfig_agent" {
  depends_on = [null_resource.kubeconfig, module.install_agent]

  triggers = {
    master_ip = hcloud_server.master.ipv4_address
    agent_ip  = hcloud_server.agent.ipv4_address
  }

  provisioner "local-exec" {
    command = <<-EOF
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.master.ipv4_address} "cat /etc/rancher/k3s/k3s.yaml" \
        | sed 's|https://127.0.0.1:6443|https://10.0.0.10:6443|' \
        | ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
          root@${hcloud_server.agent.ipv4_address} \
          "mkdir -p ~/.kube && cat > ~/.kube/config && chmod 600 ~/.kube/config"
    EOF
  }
}

resource "null_resource" "agent_ssh_auth" {
  depends_on = [null_resource.vigil_agent_setup]

  triggers = {
    agent_ip   = hcloud_server.agent.ipv4_address
    worker_1_ip = hcloud_server.worker_1.ipv4_address
    worker_2_ip = hcloud_server.worker_2.ipv4_address
  }

  provisioner "local-exec" {
    command = <<-EOF
      DEADLINE=$(($(date +%s) + 120))
      until ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
          root@${hcloud_server.agent.ipv4_address} "test -f /root/.ssh/id_ed25519.pub" 2>/dev/null; do
        if [ $(date +%s) -gt $DEADLINE ]; then echo "Agent SSH key not ready after 2 minutes"; exit 1; fi
        sleep 5
      done
      PUBKEY=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.agent.ipv4_address} "cat /root/.ssh/id_ed25519.pub")
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.worker_1.ipv4_address} \
        "grep -qxF '$PUBKEY' /root/.ssh/authorized_keys 2>/dev/null || echo '$PUBKEY' >> /root/.ssh/authorized_keys"
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.worker_2.ipv4_address} \
        "grep -qxF '$PUBKEY' /root/.ssh/authorized_keys 2>/dev/null || echo '$PUBKEY' >> /root/.ssh/authorized_keys"
    EOF
  }
}

resource "null_resource" "vigil_agent_setup" {
  depends_on = [null_resource.kubeconfig_agent]

  triggers = {
    agent_ip       = hcloud_server.agent.ipv4_address
    branch         = var.vigil_branch
    webhook_secret = var.vigil_webhook_secret
    llm_api_key    = var.llm_api_key
    llm_base_url   = var.llm_base_url
    llm_model_name = var.llm_model_name
  }

  provisioner "local-exec" {
    command = <<-EOF
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.agent.ipv4_address} \
        "mkdir -p /etc/vigil && \
         echo '${var.vigil_branch}' > /etc/vigil/branch && \
         printf 'VIGIL_WEBHOOK_SECRET=${var.vigil_webhook_secret}\nLLM_API_KEY=${var.llm_api_key}\nLLM_BASE_URL=${var.llm_base_url}\nLLM_MODEL_NAME=${var.llm_model_name}\nVIGIL_ORCHESTRATOR_URL=http://10.0.0.40:9099\nEVAL_RUNS_DIR=eval/runs\n' > /etc/vigil/env && \
         chmod 600 /etc/vigil/env && \
         systemctl start --no-block vigil-orchestrator.service"
    EOF
  }
}
