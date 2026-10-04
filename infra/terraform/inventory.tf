locals {
  inventory         = jsondecode(file("${path.module}/../inventory.json"))
  node_subnet_bits  = 8
  node_subnet_index = 0
  kube_api_port     = 6443
  orchestrator_port = 9099
  eval_target       = "hetzner"

  node_cidr        = cidrsubnet(local.inventory.network.base, local.node_subnet_bits, local.node_subnet_index)
  host_ips         = { for host in local.inventory.hosts : host.name => cidrhost(local.node_cidr, host.index) }
  control_plane_ip = local.host_ips["vigil-control-plane-1"]
  agent_ip         = local.host_ips["vigil-agent"]
  api_server_url   = "https://${local.control_plane_ip}:${local.kube_api_port}"
  ssh_hosts        = join(",", [for host in local.inventory.hosts : host.name if host.role == "worker"])
}
