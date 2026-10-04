{ addresses, ... }:
{
  imports = [ ./common.nix ];

  services.k3s = {
    enable = true;
    role = "server";
    extraFlags = [
      "--write-kubeconfig-mode=0644"
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
