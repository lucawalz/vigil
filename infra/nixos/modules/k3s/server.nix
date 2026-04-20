{ config, pkgs, meta, secretsDir ? ../../secrets, ... }:
{
  imports = [ ./common.nix ];

  services.k3s = {
    enable = true;
    role = "server";
    extraFlags = [
      "--write-kubeconfig-mode=0644"
      "--disable=servicelb"
      "--disable=traefik"
      "--disable=local-storage"
    ];
    tokenFile = config.age.secrets.k3s-token.path;
    clusterInit = true;
  };

  networking.firewall.allowedTCPPorts = [ 6443 10250 ];
  networking.firewall.allowedUDPPorts = [ 8472 ];
}
