# infra/local

Vigil-specific overlays for the ThinkCentre m920q home-lab cluster. The base cluster config lives in a separate private repo; files here are the additions needed to support Vigil.

## Contents

- `kubernetes/clusters/home/infrastructure/monitoring/kube-prometheus-stack/values-alertmanager.yaml` — enables Alertmanager and configures the `vigil-webhook` receiver pointing at `https://vigil.syslabs.dev/webhook`
- `kubernetes/clusters/home/infrastructure/networking/cloudflare-tunnel/vigil-route.md` — Cloudflare Tunnel route for `vigil.syslabs.dev`

## Applying the Alertmanager overlay

Merge `values-alertmanager.yaml` into the `values.yaml` key of the `prometheus-values` ConfigMap in the `monitoring` namespace, then reconcile:

```bash
kubectl get configmap prometheus-values -n monitoring \
  -o jsonpath='{.data.values\.yaml}' > /tmp/current-values.yaml

# Edit /tmp/current-values.yaml: replace the alertmanager block with the content from values-alertmanager.yaml

kubectl create configmap prometheus-values -n monitoring \
  --from-file=values.yaml=/tmp/merged-values.yaml \
  --dry-run=client -o yaml | kubectl apply -f -

flux reconcile helmrelease kube-prometheus-stack -n monitoring --with-source
```
