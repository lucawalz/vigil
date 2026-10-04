{ lib, addresses, ... }:
{
  imports = [ ./common.nix ];

  services.k3s = {
    enable = true;
    role = "agent";
    serverAddr = lib.mkDefault addresses.apiServerUrl;
    tokenFile = "/etc/k3s/token";
    extraFlags = [ "--node-label=node.kubernetes.io/role=worker" ];
  };

  boot.kernel.sysctl."net.bridge.bridge-nf-call-iptables" = lib.mkDefault 1;

  networking.firewall.allowedTCPPorts = [ 10250 ];
  networking.firewall.allowedUDPPorts = [ 8472 ];
}
