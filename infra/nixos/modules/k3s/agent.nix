{ lib, meta, ... }:
{
  imports = [ ./common.nix ];

  services.k3s = {
    enable = true;
    role = "agent";
    serverAddr = lib.mkDefault "https://10.0.0.10:6443";
    tokenFile = "/etc/k3s/token";
  };

  networking.firewall.allowedTCPPorts = [ 10250 ];
  networking.firewall.allowedUDPPorts = [ 8472 ];
}
