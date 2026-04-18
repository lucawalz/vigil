# infra/overlays/hetzner

Vigil-specific overlays for the Hetzner Cloud eval cluster. The base cluster config lives in the same nixos-homelab flake as the local cluster; files here are the additions and replacements needed to support Vigil on Hetzner.

## Differences vs infra/local

Four environment-specific values differ from the local ThinkCentre cluster:

- Disk device — `/dev/sda` (Hetzner Cloud VMs) instead of `/dev/nvme0n1` (ThinkCentres). Captured in the nixos-homelab flake's `hetzner-*` host disko configs, not in this overlay.
- Private network interface — `enp7s0` (Hetzner CX23/CX33) instead of `eth0`/`enp*` on local nodes. Captured in the nixos-homelab `modules/k3s/hetzner.nix` module.
- Alertmanager webhook URL — `http://10.0.0.40:9099/webhook` (agent host private IP, no TLS) instead of `https://vigil.syslabs.dev/webhook` (Cloudflare Tunnel). Captured in this overlay's `values-alertmanager.yaml`.
- Rollback-gate `OnActiveSec` — re-measured on Hetzner CX23/CX33 hardware after provisioning. Documented in `docs/timing.md`; the value is set per-host in the `hetzner-*` NixOS configs.

## Contents

- `kubernetes/clusters/hetzner/infrastructure/monitoring/kube-prometheus-stack/kustomization.yaml` — references `alertmanager-secret.yaml`
- `kubernetes/clusters/hetzner/infrastructure/monitoring/kube-prometheus-stack/values-alertmanager.yaml` — Alertmanager Helm values; routes `vigil-webhook` receiver to the private agent IP
- `kubernetes/clusters/hetzner/infrastructure/monitoring/kube-prometheus-stack/alertmanager-secret.yaml` — `vigil-webhook-secret` placeholder (SOPS-encrypt with the eval cluster's age key before commit)

## Applying the Alertmanager overlay

Same procedure as `infra/local`: merge `values-alertmanager.yaml` into the `prometheus-values` ConfigMap and reconcile the kube-prometheus-stack HelmRelease via Flux. The eval cluster reconciles `kubernetes/clusters/hetzner/` from the same nixos-homelab repo.
