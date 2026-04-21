resource "null_resource" "flux_bootstrap" {
  depends_on = [null_resource.kubeconfig]

  triggers = {
    branch = var.vigil_branch
  }

  provisioner "local-exec" {
    command = <<-EOF
      nix shell nixpkgs#fluxcd nixpkgs#bash --command flux bootstrap github \
        --owner=lucawalz \
        --repository=vigil \
        --branch=${var.vigil_branch} \
        --path=infra/overlays/hetzner/kubernetes/clusters/hetzner \
        --personal
    EOF
    environment = {
      KUBECONFIG   = pathexpand("~/.kube/hetzner-vigil")
      GITHUB_TOKEN = var.github_token
    }
  }
}
