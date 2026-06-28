{ config, lib, ... }:
{
  systemd.services.k3s = lib.mkIf config.services.k3s.enable {
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
  };
}