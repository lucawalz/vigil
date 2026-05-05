resource "null_resource" "rbac_manifests" {
  depends_on = [null_resource.flux_bootstrap]

  triggers = {
    master_id = hcloud_server.master.id
    manifests = filebase64sha256("${path.module}/../kubernetes/rbac/eval-runner-clusterrole.yaml")
  }

  provisioner "local-exec" {
    command = <<-EOF
      DEADLINE=$(($(date +%s) + 300))
      until ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 \
          root@${hcloud_server.master.ipv4_address} "kubectl get sa default -n default" > /dev/null 2>&1; do
        if [ $(date +%s) -gt $DEADLINE ]; then echo "kubectl not ready after 5 minutes"; exit 1; fi
        sleep 5
      done
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.master.ipv4_address} \
        "rm -rf /tmp/vigil-rbac && mkdir -p /tmp/vigil-rbac"
      scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -r \
        ${path.module}/../kubernetes/rbac/. \
        root@${hcloud_server.master.ipv4_address}:/tmp/vigil-rbac/
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.master.ipv4_address} \
        "kubectl apply -k /tmp/vigil-rbac/"
    EOF
  }
}

resource "null_resource" "rbac_kubeconfig_eval_runner" {
  depends_on = [null_resource.rbac_manifests, null_resource.kubeconfig_agent]

  triggers = {
    master_id = hcloud_server.master.id
    agent_id  = hcloud_server.agent.id
  }

  provisioner "local-exec" {
    command = <<-EOF
      TOKEN=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.master.ipv4_address} \
        "kubectl create token vigil-eval-runner -n default --duration=86400s")
      CA=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.master.ipv4_address} \
        "kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}'")
      cat > /tmp/kubeconfig-eval-runner-${var.group_name} <<KUBECFG
apiVersion: v1
kind: Config
clusters:
- name: vigil-eval-${var.group_name}
  cluster:
    server: https://10.0.0.10:6443
    certificate-authority-data: $CA
users:
- name: vigil-eval-runner
  user:
    token: $TOKEN
contexts:
- name: vigil-eval-runner@vigil-eval-${var.group_name}
  context:
    cluster: vigil-eval-${var.group_name}
    user: vigil-eval-runner
current-context: vigil-eval-runner@vigil-eval-${var.group_name}
KUBECFG
      scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        /tmp/kubeconfig-eval-runner-${var.group_name} \
        root@${hcloud_server.agent.ipv4_address}:/etc/vigil/kubeconfig-eval-runner
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.agent.ipv4_address} \
        "chmod 600 /etc/vigil/kubeconfig-eval-runner"
      rm -f /tmp/kubeconfig-eval-runner-${var.group_name}
    EOF
  }
}

resource "null_resource" "rbac_kubeconfig_fault_injection" {
  depends_on = [null_resource.rbac_manifests, null_resource.kubeconfig_agent]

  triggers = {
    master_id = hcloud_server.master.id
    agent_id  = hcloud_server.agent.id
  }

  provisioner "local-exec" {
    command = <<-EOF
      TOKEN=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.master.ipv4_address} \
        "kubectl create token vigil-fault-injection -n default --duration=86400s")
      CA=$(ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.master.ipv4_address} \
        "kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}'")
      cat > /tmp/kubeconfig-fault-injection-${var.group_name} <<KUBECFG
apiVersion: v1
kind: Config
clusters:
- name: vigil-eval-${var.group_name}
  cluster:
    server: https://10.0.0.10:6443
    certificate-authority-data: $CA
users:
- name: vigil-fault-injection
  user:
    token: $TOKEN
contexts:
- name: vigil-fault-injection@vigil-eval-${var.group_name}
  context:
    cluster: vigil-eval-${var.group_name}
    user: vigil-fault-injection
current-context: vigil-fault-injection@vigil-eval-${var.group_name}
KUBECFG
      scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        /tmp/kubeconfig-fault-injection-${var.group_name} \
        root@${hcloud_server.agent.ipv4_address}:/etc/vigil/kubeconfig-fault-injection
      ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        root@${hcloud_server.agent.ipv4_address} \
        "chmod 600 /etc/vigil/kubeconfig-fault-injection"
      rm -f /tmp/kubeconfig-fault-injection-${var.group_name}
    EOF
  }
}
