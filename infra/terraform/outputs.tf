output "control_plane_public_ip" {
  value = hcloud_server.control_plane.ipv4_address
}

output "control_plane_private_ip" {
  value = local.control_plane_ip
}

output "worker_1_public_ip" {
  value = hcloud_server.worker_1.ipv4_address
}

output "worker_1_private_ip" {
  value = local.host_ips["vigil-worker-1"]
}

output "worker_2_public_ip" {
  value = hcloud_server.worker_2.ipv4_address
}

output "worker_2_private_ip" {
  value = local.host_ips["vigil-worker-2"]
}

output "agent_public_ip" {
  value = hcloud_server.agent.ipv4_address
}

output "agent_private_ip" {
  value = local.agent_ip
}

output "kubeconfig_hint" {
  value = "KUBECONFIG=~/.kube/hetzner-vigil-${var.group_name} kubectl get nodes  # context: hetzner-vigil-${var.group_name}"
}
