{ config, lib, pkgs, ... }:
{
  systemd.services.k3s = {
    wants = [ "network-online.target" ];
    after = [ "network-online.target" ];
    
    serviceConfig = {
      Type = "notify";
      ExecStart = "${config.services.k3s.package}/bin/k3s ${
        if config.services.k3s.role == "server"
        then "server"
        else "agent"
      } ${lib.escapeShellArgs config.services.k3s.extraFlags}";
      ExecStop = "${config.services.k3s.package}/bin/k3s kill";
      KillMode = "process";
      Delegate = "yes";
      LimitNOFILE = 1048576;
      LimitNPROC = "infinity";
      LimitCORE = "infinity";
      TasksMax = "infinity";
      TimeoutStartSec = "0";
      Restart = "always";
      RestartSec = "5s";
    };
    
    environment = config.services.k3s.environment;
    
    path = [
      config.services.k3s.package
      pkgs.coreutils
      pkgs.gnused
      pkgs.gnugrep
    ];
  };
}