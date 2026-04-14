# vigil.syslabs.dev Cloudflare Tunnel Route

The tunnel runs in `--token` mode (remotely managed via the Cloudflare Zero Trust dashboard). There is no local YAML for ingress rules — all routing is configured through the dashboard.

## Route

| Field | Value |
|-------|-------|
| Hostname | `vigil.syslabs.dev` |
| Service | `http://<MACBOOK_LAN_IP>:9099` |

cloudflared runs in-cluster and forwards directly to the MacBook on the LAN — no Traefik IngressRoute needed. Port 9099 is the vigil webhook listener. Alertmanager is configured to POST to `https://vigil.syslabs.dev/webhook`; cloudflared handles the TLS termination and forwards the plain HTTP request to the MacBook.

## Adding the route

1. Cloudflare Zero Trust → Networks → Tunnels → (the vigil tunnel) → Public Hostnames → Add
2. Hostname: `vigil.syslabs.dev`, Service: `http://<MACBOOK_LAN_IP>:9099`
3. Save — Cloudflare creates the CNAME record automatically

Verify the route is active:
```bash
curl -I https://vigil.syslabs.dev
# Should return an HTTP status code. Connection error means the route isn't configured or cloudflared is down.
```

To test the full pipeline with a live listener on the MacBook:
```bash
# MacBook
nc -l 9099

# Cluster (separate terminal)
kubectl port-forward statefulset/alertmanager-kube-prometheus-stack-alertmanager -n monitoring 9093:9093
curl -H 'Content-Type: application/json' \
  -d '[{"labels":{"alertname":"TestAlert","severity":"warning"}}]' \
  http://127.0.0.1:9093/api/v1/alerts
```

The `nc` listener should receive a POST within ~30 seconds (group_wait: 10s + delivery).

## Moving the agent host

When moving MacBook → Raspi → Hetzner VM, update only the service IP in the dashboard. The hostname `vigil.syslabs.dev` and the Alertmanager webhook URL stay constant — no cluster changes needed.
