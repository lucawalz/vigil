{ config, lib, pkgs, meta, secretsDir ? ../../secrets, ... }:
{
  imports = [ ./common.nix ];

  services.k3s = {
    enable = true;
    role = "agent";
    serverAddr = lib.mkDefault "https://10.0.0.10:6443";
    tokenFile = config.age.secrets.k3s-token.path;
  };

  networking.firewall.allowedTCPPorts = [ 10250 ];
  networking.firewall.allowedUDPPorts = [ 8472 ];
}
