{ config, pkgs, meta, secretsDir ? ../../secrets, ... }:
{
  age.secrets.k3s-token = {
    file = "${secretsDir}/k3s-token.age";
    mode = "0400";
    owner = "root";
    group = "root";
  };

  systemd.services.k3s = {
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
  };
}
