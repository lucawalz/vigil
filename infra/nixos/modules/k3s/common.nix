{ ... }:
{
  systemd.services.k3s = {
    wants = [ "network-online.target" ];
    after  = [ "network-online.target" ];
    serviceConfig = {
      ExecStart = "/run/current-system/sw/bin/k3s agent";
    };
  };
}
