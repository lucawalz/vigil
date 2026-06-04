data "sops_file" "vigil_webhook_secret" {
  source_file = "${path.module}/../overlays/hetzner/kubernetes/clusters/hetzner/secrets/vigil-webhook-secret.sops.yaml"
}
