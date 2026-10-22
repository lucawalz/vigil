{ addresses, ... }:
let
  auditPolicyEtcPath = "rancher/k3s/audit-policy.yaml";
  auditLogPath = "/var/lib/rancher/k3s/server/logs/audit.log";
  auditLogMaxSizeMb = 100;
  auditLogMaxBackups = 3;
in
{
  imports = [ ./common.nix ];

  environment.etc.${auditPolicyEtcPath}.text = ''
    apiVersion: audit.k8s.io/v1
    kind: Policy
    omitStages:
      - RequestReceived
    rules:
      - level: Metadata
  '';

  services.k3s = {
    enable = true;
    role = "server";
    extraFlags = [
      "--write-kubeconfig-mode=0600"
      "--secrets-encryption"
      "--kube-apiserver-arg=audit-policy-file=/etc/${auditPolicyEtcPath}"
      "--kube-apiserver-arg=audit-log-path=${auditLogPath}"
      "--kube-apiserver-arg=audit-log-maxsize=${toString auditLogMaxSizeMb}"
      "--kube-apiserver-arg=audit-log-maxbackup=${toString auditLogMaxBackups}"
      "--disable=servicelb"
      "--disable=traefik"
      "--cluster-cidr=${addresses.podCidr}"
      "--service-cidr=${addresses.serviceCidr}"
    ];
    tokenFile = "/etc/k3s/token";
    clusterInit = true;
  };

  networking.firewall.allowedTCPPorts = [ 6443 10250 ];
  networking.firewall.allowedUDPPorts = [ 8472 ];
}
