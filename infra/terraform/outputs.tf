output "master_public_ip" {
  value = hcloud_server.master.ipv4_address
}

output "master_private_ip" {
  value = "10.0.0.10"
}

output "worker_1_public_ip" {
  value = hcloud_server.worker_1.ipv4_address
}

output "worker_1_private_ip" {
  value = "10.0.0.20"
}

output "worker_2_public_ip" {
  value = hcloud_server.worker_2.ipv4_address
}

output "worker_2_private_ip" {
  value = "10.0.0.30"
}

output "agent_public_ip" {
  value = hcloud_server.agent.ipv4_address
}

output "agent_private_ip" {
  value = "10.0.0.40"
}

output "kubeconfig_hint" {
  value = "KUBECONFIG=~/.kube/hetzner-vigil kubectl get nodes  # context: hetzner-vigil"
}
