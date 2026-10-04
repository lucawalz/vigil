resource "null_resource" "flux_bootstrap" {
  depends_on = [null_resource.kubeconfig]

  triggers = {
    branch           = var.vigil_branch
    control_plane_id = hcloud_server.control_plane.id
  }

  provisioner "local-exec" {
    command = <<-EOF
      nix shell nixpkgs#fluxcd nixpkgs#bash --command flux bootstrap github \
        --owner=lucawalz \
        --repository=vigil \
        --branch=${var.vigil_branch} \
        --path=infra/overlays/hetzner/kubernetes/clusters/hetzner \
        --personal \
        --token-auth \
        --timeout=10m
    EOF
    environment = {
      KUBECONFIG   = pathexpand("~/.kube/hetzner-vigil-${var.group_name}")
      GITHUB_TOKEN = var.github_token
    }
  }
}
