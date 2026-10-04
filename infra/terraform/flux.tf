resource "null_resource" "flux_bootstrap" {
  depends_on = [null_resource.kubeconfig]

  triggers = {
    branch           = var.vigil_branch
    control_plane_id = hcloud_server.control_plane.id
  }

  provisioner "local-exec" {
    command = <<-EOF
      nix shell nixpkgs#fluxcd nixpkgs#kubectl nixpkgs#bash --command bash ${path.module}/../scripts/flux-sync.sh \
        https://github.com/lucawalz/vigil.git \
        '${var.vigil_branch}' \
        ./infra/overlays/hetzner/kubernetes/clusters/hetzner
    EOF
    environment = {
      KUBECONFIG = pathexpand("~/.kube/hetzner-vigil-${var.group_name}")
    }
  }
}
