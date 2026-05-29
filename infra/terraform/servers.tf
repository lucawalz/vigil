data "hcloud_image" "master_snapshot" {
  with_selector = "vigil-role=master"
  most_recent   = true
}

data "hcloud_image" "worker_1_snapshot" {
  with_selector = "vigil-role=worker-1"
  most_recent   = true
}

data "hcloud_image" "worker_2_snapshot" {
  with_selector = "vigil-role=worker-2"
  most_recent   = true
}

data "hcloud_image" "agent_snapshot" {
  with_selector = "vigil-role=agent"
  most_recent   = true
}

resource "hcloud_server" "master" {
  name        = "${var.group_name}-${var.run_id}-master"
  server_type = "cpx22"
  image       = data.hcloud_image.master_snapshot.id
  location    = "hel1"

  ssh_keys = [hcloud_ssh_key.operator.id]

  network {
    network_id = hcloud_network.vigil.id
    ip         = "10.0.0.10"
    alias_ips  = []
  }

  firewall_ids = [hcloud_firewall.vigil.id]

  depends_on = [hcloud_network_subnet.vigil]
}

resource "null_resource" "k3s_token_master" {
  depends_on = [hcloud_server.master]

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
      var.operator_ssh_pubkey != "" ? "grep -qxF '${var.operator_ssh_pubkey}' /root/.ssh/authorized_keys 2>/dev/null || echo '${var.operator_ssh_pubkey}' >> /root/.ssh/authorized_keys" : "true",
    ]
  }
}

resource "hcloud_server" "worker_1" {
  name        = "${var.group_name}-${var.run_id}-worker-1"
  server_type = "cpx22"
  image       = data.hcloud_image.worker_1_snapshot.id
  location    = "hel1"

  ssh_keys = [hcloud_ssh_key.operator.id]

  network {
    network_id = hcloud_network.vigil.id
    ip         = "10.0.0.20"
    alias_ips  = []
  }

  firewall_ids = [hcloud_firewall.vigil.id]

  depends_on = [hcloud_network_subnet.vigil]
}

resource "null_resource" "k3s_token_worker_1" {
  depends_on = [hcloud_server.worker_1]

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
      "chmod 400 /etc/k3s/token",
      var.operator_ssh_pubkey != "" ? "grep -qxF '${var.operator_ssh_pubkey}' /root/.ssh/authorized_keys 2>/dev/null || echo '${var.operator_ssh_pubkey}' >> /root/.ssh/authorized_keys" : "true",
    ]
  }
}

resource "hcloud_server" "worker_2" {
  name        = "${var.group_name}-${var.run_id}-worker-2"
  server_type = "cpx22"
  image       = data.hcloud_image.worker_2_snapshot.id
  location    = "hel1"

  ssh_keys = [hcloud_ssh_key.operator.id]

  network {
    network_id = hcloud_network.vigil.id
    ip         = "10.0.0.30"
    alias_ips  = []
  }

  firewall_ids = [hcloud_firewall.vigil.id]

  depends_on = [hcloud_network_subnet.vigil]
}

resource "null_resource" "k3s_token_worker_2" {
  depends_on = [hcloud_server.worker_2]

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
      "chmod 400 /etc/k3s/token",
      var.operator_ssh_pubkey != "" ? "grep -qxF '${var.operator_ssh_pubkey}' /root/.ssh/authorized_keys 2>/dev/null || echo '${var.operator_ssh_pubkey}' >> /root/.ssh/authorized_keys" : "true",
    ]
  }
}

resource "hcloud_server" "agent" {
  name        = "${var.group_name}-${var.run_id}-agent"
  server_type = "cpx22"
  image       = data.hcloud_image.agent_snapshot.id
  location    = "hel1"

  ssh_keys = [hcloud_ssh_key.operator.id]

  network {
    network_id = hcloud_network.vigil.id
    ip         = "10.0.0.40"
    alias_ips  = []
  }

  firewall_ids = [hcloud_firewall.vigil.id]

  depends_on = [hcloud_network_subnet.vigil]
}

resource "null_resource" "kubeconfig" {
  depends_on = [null_resource.k3s_token_master]

  triggers = {
    master_id = hcloud_server.master.id
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
        | sed 's/name: default/name: hetzner-vigil-${var.group_name}/g' \
        | sed 's/cluster: default/cluster: hetzner-vigil-${var.group_name}/g' \
        | sed 's/user: default/user: hetzner-vigil-${var.group_name}/g' \
        | sed 's/current-context: default/current-context: hetzner-vigil-${var.group_name}/' \
        > ~/.kube/hetzner-vigil-${var.group_name}
      chmod 600 ~/.kube/hetzner-vigil-${var.group_name}
    EOF
  }
}

resource "null_resource" "kubeconfig_agent" {
  depends_on = [null_resource.kubeconfig, hcloud_server.agent]

  triggers = {
    master_id = hcloud_server.master.id
    agent_id  = hcloud_server.agent.id
  }

  provisioner "local-exec" {
    command = <<-EOF
      DEADLINE=$(($(date +%s) + 300))
      until ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 \
          root@${hcloud_server.agent.ipv4_address} true 2>/dev/null; do
        if [ $(date +%s) -gt $DEADLINE ]; then echo "Agent SSH not ready after 5 minutes"; exit 1; fi
        sleep 5
      done
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.master.ipv4_address} "cat /etc/rancher/k3s/k3s.yaml" \
        | sed 's|https://127.0.0.1:6443|https://10.0.0.10:6443|' \
        | ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
          root@${hcloud_server.agent.ipv4_address} \
          "mkdir -p ~/.kube && cat > ~/.kube/config && chmod 600 ~/.kube/config"
    EOF
  }
}

resource "null_resource" "worker_nixos_config" {
  depends_on = [null_resource.k3s_token_worker_1, null_resource.k3s_token_worker_2]

  triggers = {
    worker_1_ip = hcloud_server.worker_1.ipv4_address
    worker_2_ip = hcloud_server.worker_2.ipv4_address
    branch      = var.vigil_branch
  }

  provisioner "local-exec" {
    command = <<-EOF
      for IP in ${hcloud_server.worker_1.ipv4_address} ${hcloud_server.worker_2.ipv4_address}; do
        ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$IP \
          "if [ ! -d /opt/vigil/.git ]; then
            git clone --branch '${var.vigil_branch}' https://github.com/lucawalz/vigil /opt/vigil
          else
            cd /opt/vigil && git fetch origin && git checkout '${var.vigil_branch}' && git reset --hard origin/'${var.vigil_branch}'
          fi
          ln -sfn /opt/vigil/infra/nixos /opt/nixos-config"
      done
    EOF
  }
}

resource "null_resource" "agent_ssh_auth" {
  depends_on = [null_resource.vigil_agent_setup]

  triggers = {
    agent_ip    = hcloud_server.agent.ipv4_address
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
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.agent.ipv4_address} \
        "grep -qxF '$PUBKEY' /root/.ssh/authorized_keys 2>/dev/null || echo '$PUBKEY' >> /root/.ssh/authorized_keys"
    EOF
  }
}

resource "local_sensitive_file" "vigil_env" {
  filename        = "/tmp/vigil-env-${var.run_id}.env"
  file_permission = "0600"
  content         = <<-ENV
    VIGIL_WEBHOOK_SECRET=${var.vigil_webhook_secret}
    GITHUB_TOKEN=${var.github_token}
    REPO_URL=https://github.com/lucawalz/vigil.git
    %{~if var.anthropic_api_key != ""~}
    ANTHROPIC_API_KEY=${var.anthropic_api_key}
    %{~endif~}
    %{~if var.ollama_api_key != ""~}
    OLLAMA_API_KEY=${var.ollama_api_key}
    OLLAMA_BASE_URL=${var.ollama_base_url}
    %{~endif~}
    LLM_MODEL_NAME=${var.llm_model_name}
    VIGIL_ORCHESTRATOR_URL=http://10.0.0.40:9099
    EVAL_RUNS_DIR=/root/vigil/eval/runs
    VIGIL_SCENARIOS_DIR=/root/vigil/eval/scenarios
    VIGIL_REPO_ROOT=/root/vigil
    SSH_HOSTS=hetzner-worker-1,hetzner-worker-2
    SSH_USER=root
    SSH_KEY_PATH=/root/.ssh/id_ed25519
    EVAL_RUNNER_KUBECONFIG=/etc/vigil/kubeconfig-eval-runner
    FAULT_INJECTION_KUBECONFIG=/etc/vigil/kubeconfig-fault-injection
  ENV
}

resource "null_resource" "vigil_agent_setup" {
  depends_on = [null_resource.kubeconfig_agent, null_resource.rbac_kubeconfig_eval_runner, null_resource.rbac_kubeconfig_fault_injection]

  triggers = {
    agent_id              = hcloud_server.agent.id
    branch                = var.vigil_branch
    webhook_secret_sha    = sha256(var.vigil_webhook_secret)
    ollama_api_key_sha    = sha256(var.ollama_api_key)
    ollama_base_url_sha   = sha256(var.ollama_base_url)
    anthropic_api_key_sha = sha256(var.anthropic_api_key)
    llm_model_name_sha    = sha256(var.llm_model_name)
    kubeconfigs_ready     = "${null_resource.rbac_kubeconfig_eval_runner.id}-${null_resource.rbac_kubeconfig_fault_injection.id}"
  }

  provisioner "local-exec" {
    command = <<-EOF
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.agent.ipv4_address} \
        "mkdir -p /etc/vigil && echo '${var.vigil_branch}' > /etc/vigil/branch"
      scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        ${local_sensitive_file.vigil_env.filename} \
        root@${hcloud_server.agent.ipv4_address}:/etc/vigil/env
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.agent.ipv4_address} \
        "chmod 600 /etc/vigil/env && systemctl start --no-block vigil-orchestrator.service"
      rm -f ${local_sensitive_file.vigil_env.filename}
      %{if var.operator_ssh_pubkey != ""}
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.agent.ipv4_address} \
        "grep -qxF '${var.operator_ssh_pubkey}' /root/.ssh/authorized_keys 2>/dev/null || echo '${var.operator_ssh_pubkey}' >> /root/.ssh/authorized_keys"
      %{endif}
    EOF
  }
}
