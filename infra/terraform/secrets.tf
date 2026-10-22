locals {
  webhook_secret_name      = "vigil-webhook-secret"
  webhook_secret_namespace = "monitoring"
}

resource "random_password" "vigil_webhook_secret" {
  length  = local.generated_token_length
  special = false
}

resource "null_resource" "vigil_webhook_secret" {
  depends_on = [null_resource.kubeconfig]

  triggers = {
    control_plane_id   = hcloud_server.control_plane.id
    webhook_secret_sha = sha256(random_password.vigil_webhook_secret.result)
  }

  provisioner "local-exec" {
    command = <<-EOF
      nix shell nixpkgs#kubectl nixpkgs#bash --command bash -euo pipefail -c '
        kubectl create namespace ${local.webhook_secret_namespace} --dry-run=client -o yaml | kubectl apply -f -
        printf "%s" "$WEBHOOK_SECRET" \
          | kubectl create secret generic ${local.webhook_secret_name} -n ${local.webhook_secret_namespace} \
            --from-file=token=/dev/stdin --dry-run=client -o yaml \
          | kubectl apply -f -
      '
    EOF
    environment = {
      KUBECONFIG     = pathexpand("~/.kube/hetzner-vigil-${var.group_name}")
      WEBHOOK_SECRET = random_password.vigil_webhook_secret.result
    }
  }
}
